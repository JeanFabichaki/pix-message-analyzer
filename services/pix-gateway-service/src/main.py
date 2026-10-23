import asyncio
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from common.schemas.pix import PixTransactionRequest, PixTransactionResponse
from common.database.models import TransactionDirection
from src.clients.ollaya_client import OllayaClient, TUNED_INSTRUCTIONS, TUNED_CRITERIA
from src.clients.investigation import InvestigationClient
from src.clients.user_client import GatewayUserClient
from src.services.interceptor import PixInterceptor
from src.services.benchmark import BenchmarkRunner, find_data_dir
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import httpx


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pix-gateway-service")

from common.config.settings import settings

ollaya_client = OllayaClient(
    base_urls=settings.OLLAYA_CLUSTER_URLS or settings.OLLAYA_BASE_URL,
    model=settings.OLLAYA_MODEL,
    decomposed=True,
    threat_threshold=0.65,
)
ollaya_tuned_client = OllayaClient(
    base_urls=settings.LAYA_TUNED_CLUSTER_URLS or settings.LAYA_TUNED_BASE_URL or settings.OLLAYA_BASE_URL,
    model=settings.LAYA_TUNED_MODEL,
    instructions=TUNED_INSTRUCTIONS,
    criteria=TUNED_CRITERIA,
    decomposed=False,
    threat_threshold=0.40,
)
investigation_client = InvestigationClient()
user_client = GatewayUserClient()
interceptor = PixInterceptor(
    ollaya=ollaya_client,
    investigation=investigation_client,
    ollaya_tuned=ollaya_tuned_client,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async def _warmup_tuned():
        for attempt in range(1, 13):
            try:
                ms = await ollaya_tuned_client.warmup(timeout=60.0)
                logger.info(f"Laya retreinado nativo aquecido em {ms} ms.")
                return
            except Exception as ex:
                logger.warning(f"Tentativa {attempt}/12 aquecendo Laya retreinado: {ex}")
                await asyncio.sleep(5)
        logger.error(
            f"IA Laya retreinado INDISPONÍVEL: {ollaya_tuned_client.last_error}. "
            f"Enquanto isso, os Pix serão aprovados SEM análise."
        )

    warmup_task = asyncio.create_task(_warmup_tuned())
    yield
    warmup_task.cancel()
    await ollaya_client.aclose()
    await ollaya_tuned_client.aclose()
    logger.info("Encerrando pix-gateway-service.")


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Pix Guard - Pix Gateway Service (Ollaya)",
    description="Gateway de entrada para transações Pix com triagem rápida de ameaças via Ollaya e mascaramento em tempo real",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/pix/engines")
async def list_engines():
    """Modelos de triagem selecionáveis e se cada um está respondendo agora."""
    async def probe(client: OllayaClient) -> bool:
        if client.last_ok_at is not None and client.consecutive_failures == 0:
            return True
        if hasattr(client, "is_available"):
            return await client.is_available()
        return True

    tuned_ok = await probe(ollaya_tuned_client)
    base_ok = await probe(ollaya_client)
    return {
        "default": "laya_tuned",
        "engines": [
            {"id": "laya_tuned", "label": "Laya retreinado", "model": ollaya_tuned_client.model, "available": tuned_ok,
             "description": "Retreinado nativamente para ameaças e extorsão em mensagens de Pix."},
            {"id": "laya", "label": "Laya original", "model": ollaya_client.model, "available": base_ok,
             "description": "Modelo padrão do Ollaya, sem treino específico."},
        ],
    }


benchmark_runner = BenchmarkRunner(
    clients={"laya": ollaya_client, "laya_tuned": ollaya_tuned_client},
    data_dir=find_data_dir(settings.BENCHMARK_DATA_DIR),
)


class BenchmarkRequest(BaseModel):
    dataset: str = "test"
    size: Optional[int] = None  # None = conjunto completo


@app.get("/pix/benchmark/datasets")
async def benchmark_datasets():
    return {"datasets": benchmark_runner.datasets()}


@app.post("/pix/benchmark")
async def benchmark_start(req: BenchmarkRequest):
    """Classifica os dados de teste com o Laya original e com o retreinado e compara."""
    engines = (await list_engines())["engines"]
    down = [e["label"] for e in engines if not e["available"]]
    if down:
        raise HTTPException(status_code=409, detail=f"Modelo fora do ar: {', '.join(down)}. Suba com `make up-tuned`.")
    try:
        job_id = benchmark_runner.start(req.dataset, req.size)
    except (ValueError, FileNotFoundError) as ex:
        raise HTTPException(status_code=422, detail=str(ex))
    return {"job_id": job_id}


@app.get("/pix/benchmark/{job_id}")
async def benchmark_status(job_id: str):
    job = benchmark_runner.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Benchmark não encontrado")
    return job


class GenerateBenchmarkGeminiRequest(BaseModel):
    count: int = 50


@app.post("/pix/benchmark/generate-gemini")
async def benchmark_generate_gemini(req: GenerateBenchmarkGeminiRequest = GenerateBenchmarkGeminiRequest()):
    """Gera 50 novas mensagens de teste via Google Gemini e as registra no benchmark."""
    count = min(max(req.count, 10), 100)
    gemini_url = f"{settings.GEMINI_AGENT_URL.rstrip('/')}/benchmark/generate-dataset"
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(gemini_url, json={"count": count})
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=resp.status_code,
                    detail=f"Falha ao gerar mensagens no Gemini Agent: {resp.text[:200]}",
                )
            data = resp.json()
    except httpx.RequestError as ex:
        raise HTTPException(
            status_code=502,
            detail=f"Não foi possível conectar ao Gemini Investigation Agent ({gemini_url}): {ex}",
        )

    messages = data.get("messages", [])
    if not messages:
        raise HTTPException(status_code=500, detail="O Gemini não retornou mensagens válidas.")

    # Registra no benchmark_runner para uso imediato na comparação
    benchmark_runner.set_dynamic_dataset(
        dataset_id="gemini",
        label="Geradas via Gemini",
        note=f"{len(messages)} mensagens recentes geradas por IA ({data.get('model', 'Gemini')}) com casos desafiadores de teste.",
        rows=messages,
    )

    return {
        "status": "ok",
        "dataset": "gemini",
        "count": len(messages),
        "threats_count": data.get("threats_count"),
        "safe_count": data.get("safe_count"),
        "model": data.get("model"),
        "messages": messages,
    }



@app.get("/health")
async def health():
    # Sem tráfego recente o estado seria "desconhecido"; faz uma sonda para o health refletir a realidade.
    active_client = ollaya_tuned_client
    ok_age = None if active_client.last_ok_at is None else time.time() - active_client.last_ok_at
    if active_client.consecutive_failures > 0 or ok_age is None or ok_age > 30:
        try:
            if await active_client.is_available():
                active_client._record_ok()
        except Exception as ex:
            active_client._record_failure(str(ex))
    return {
        "status": "ok",
        "service": "pix-gateway-service",
        "decision_engine": "ollaya",
        "ollaya_model": active_client.model,
        "ollaya_base_url": active_client.base_url,
        "ollaya_cluster": active_client.base_urls,
        "ollaya": active_client.status(),
        "ollaya_base": ollaya_client.status(),
    }


import time
from collections import deque

# Buffer rotativo de amostras síncronas para cálculo de p50, p95 e p99
SYNC_LATENCY_BUFFER = deque(maxlen=2000)

async def _process_transaction(
    tx: PixTransactionRequest,
    background_tasks: BackgroundTasks,
) -> PixTransactionResponse:
    t_start = time.perf_counter()

    # 1. Garante o registro cadastral dos usuários em background
    background_tasks.add_task(
        user_client.ensure_user,
        user_id=tx.sender_id,
        cpf_cnpj=tx.sender_cpf,
        name=f"User {tx.sender_id}",
    )
    background_tasks.add_task(
        user_client.ensure_user,
        user_id=tx.receiver_id,
        cpf_cnpj=tx.receiver_cpf,
        name=f"User {tx.receiver_id}",
    )

    # 2. Interceptação e triagem rápida de segurança
    res = await interceptor.inspect_and_filter(
        tx=tx,
        background_tasks=background_tasks,
    )

    t_total_gateway_ms = round((time.perf_counter() - t_start) * 1000, 2)

    timing_metrics = {
        "step2_anti_evasion_ms": res.timing.get("anti_evasion_ms", 0.04),
        "step2_ollaya_ms": res.timing.get("ollaya_ms", 0.0),
        "step3_masking_ms": res.timing.get("masking_ms", 0.1),
        "total_gateway_ms": max(t_total_gateway_ms, 1.0),
        "ollaya_pure_inference_ms": res.timing.get("ollaya_inference_ms"),
        "ollaya_network_ms": res.timing.get("ollaya_network_ms"),
    }

    # 3. Liquidação ou bloqueio da transação
    status = "BLOCKED" if res.is_blocked else "APPROVED"
    detail = "Envio do Pix bloqueado por conter ameaça." if res.is_blocked else None

    logger.info(
        f"🏁 [PIX RESULT] TX={tx.transaction_id} | Status={status} | Engine={res.engine} | DecidedBy={res.decided_by} | "
        f"Total={timing_metrics['total_gateway_ms']:.2f}ms | OllayaTotal={timing_metrics['step2_ollaya_ms']:.2f}ms "
        f"(PureInference={timing_metrics.get('ollaya_pure_inference_ms')}ms, Network={timing_metrics.get('ollaya_network_ms')}ms)"
    )

    # Grava amostra no buffer síncrono para telemetria p50/p95/p99
    SYNC_LATENCY_BUFFER.append({
        "total_ms": timing_metrics["total_gateway_ms"],
        "anti_evasion_ms": timing_metrics["step2_anti_evasion_ms"],
        "ollaya_ms": timing_metrics["step2_ollaya_ms"],
        "masking_ms": timing_metrics["step3_masking_ms"],
    })

    return PixTransactionResponse(
        transaction_id=tx.transaction_id,
        status=status,
        amount=tx.amount,
        description=res.message,
        original_masked=False,
        blocked=res.is_blocked,
        engine=tx.engine,
        canonical_message=res.canonical_message,
        evasion_detected=res.evasion_detected,
        detail=detail,
        timing=timing_metrics,
        decided_by=res.decided_by,
        trace=res.trace,
    )


@app.get("/pix/telemetry/latency")
async def get_sync_latency_telemetry():
    """Retorna percentis p50, p95 e p99 do fluxo síncrono do Gateway Pix."""
    if not SYNC_LATENCY_BUFFER:
        return {
            "total_samples": 0,
            "p50_ms": None,
            "p95_ms": None,
            "p99_ms": None,
            "min_ms": None,
            "max_ms": None,
            "avg_ms": None,
            "sla_target_ms": 15.0,
            "within_sla_pct": 100.0,
            "breakdown": {
                "anti_evasion_p50_ms": None,
                "ollaya_p50_ms": None,
            },
            "recent_samples": [],
        }

    totals = sorted([x["total_ms"] for x in SYNC_LATENCY_BUFFER])
    n = len(totals)

    def calc_percentile(arr, p):
        idx = min(int(len(arr) * p), len(arr) - 1)
        return round(arr[idx], 2)

    p50 = calc_percentile(totals, 0.50)
    p95 = calc_percentile(totals, 0.95)
    p99 = calc_percentile(totals, 0.99)
    avg = round(sum(totals) / n, 2)
    min_val = round(totals[0], 2)
    max_val = round(totals[-1], 2)

    ollaya_vals = sorted([x["ollaya_ms"] for x in SYNC_LATENCY_BUFFER])
    evasion_vals = sorted([x["anti_evasion_ms"] for x in SYNC_LATENCY_BUFFER])

    return {
        "total_samples": n,
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
        "min_ms": min_val,
        "max_ms": max_val,
        "avg_ms": avg,
        "sla_target_ms": 15.0,
        "within_sla_pct": round((sum(1 for t in totals if t <= 15.0) / n) * 100, 1),
        "breakdown": {
            "anti_evasion_p50_ms": calc_percentile(evasion_vals, 0.50),
            "ollaya_p50_ms": calc_percentile(ollaya_vals, 0.50),
        },
        "recent_samples": totals[-30:],
    }


@app.post("/pix/telemetry/reset")
async def reset_sync_latency_telemetry():
    SYNC_LATENCY_BUFFER.clear()
    return {"status": "ok", "message": "Buffer de telemetria síncrona zerado."}



@app.post("/pix/transactions", response_model=PixTransactionResponse)
async def process_pix_transaction(
    tx: PixTransactionRequest,
    background_tasks: BackgroundTasks,
):
    return await _process_transaction(tx, background_tasks)


@app.post("/pix/cashin", response_model=PixTransactionResponse)
async def process_pix_cashin(
    tx: PixTransactionRequest,
    background_tasks: BackgroundTasks,
):
    tx.direction = TransactionDirection.CASH_IN
    return await _process_transaction(tx, background_tasks)


@app.post("/pix/cashout", response_model=PixTransactionResponse)
async def process_pix_cashout(
    tx: PixTransactionRequest,
    background_tasks: BackgroundTasks,
):
    tx.direction = TransactionDirection.CASH_OUT
    return await _process_transaction(tx, background_tasks)
