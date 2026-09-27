import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from common.schemas.pix import PixTransactionRequest, PixTransactionResponse
from common.database.models import UserStatus, TransactionDirection
from src.clients.ollaya_client import OllayaClient
from src.clients.investigation import InvestigationClient
from src.clients.user_client import GatewayUserClient
from src.services.interceptor import PixInterceptor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pix-gateway-service")

from src.clients.threat_intel_client import ThreatIntelClient

ollaya_client = OllayaClient()
investigation_client = InvestigationClient()
threat_intel_client = ThreatIntelClient()
user_client = GatewayUserClient()
interceptor = PixInterceptor(
    ollaya=ollaya_client,
    investigation=investigation_client,
    threat_intel=threat_intel_client,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando pix-gateway-service integrado com Ollaya...")
    yield
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


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "pix-gateway-service",
        "decision_engine": "ollaya",
        "ollaya_model": ollaya_client.model,
        "ollaya_base_url": ollaya_client.base_url,
        "threat_intel_service": threat_intel_client.base_url,
        "mock_mode": False,
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

    # 1. Governança: checa se o remetente está bloqueado por infrações prévias
    t_gov_start = time.perf_counter()
    sender_status = await user_client.get_user_status(tx.sender_id)
    t_gov_ms = round((time.perf_counter() - t_gov_start) * 1000, 2)

    if sender_status == UserStatus.BLOCKED_SUSPICIOUS.value:
        t_total_blocked_ms = round((time.perf_counter() - t_start) * 1000, 2)
        logger.warning(
            f"Transação rejeitada para o usuário {tx.sender_id}: status={sender_status}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "transaction_id": tx.transaction_id,
                "status": "REJECTED_BLOCKED",
                "message": "Transação Pix rejeitada: conta remetente sob bloqueio preventivo de segurança.",
                "timing": {
                    "step1_gateway_ms": max(t_gov_ms, 0.5),
                    "total_gateway_ms": max(t_total_blocked_ms, 0.5),
                },
            },
        )

    # 2. Garante o registro cadastral dos usuários em background
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

    # 3. Interceptação e triagem rápida de segurança
    res = await interceptor.inspect_and_filter(
        tx=tx,
        background_tasks=background_tasks,
    )

    t_total_gateway_ms = round((time.perf_counter() - t_start) * 1000, 2)

    timing_metrics = {
        "step1_gateway_ms": max(t_gov_ms, 0.5),
        "step2_anti_evasion_ms": res.timing.get("anti_evasion_ms", 0.04),
        "step2_threat_intel_ms": res.timing.get("threat_intel_ms", 0.5),
        "step2_ollaya_ms": res.timing.get("ollaya_ms", 0.0),
        "step3_masking_ms": res.timing.get("masking_ms", 0.1),
        "total_gateway_ms": max(t_total_gateway_ms, 1.0),
    }

    # Grava amostra no buffer síncrono para telemetria p50/p95/p99
    SYNC_LATENCY_BUFFER.append({
        "total_ms": timing_metrics["total_gateway_ms"],
        "anti_evasion_ms": timing_metrics["step2_anti_evasion_ms"],
        "threat_intel_ms": timing_metrics["step2_threat_intel_ms"],
        "ollaya_ms": timing_metrics["step2_ollaya_ms"],
        "masking_ms": timing_metrics["step3_masking_ms"],
    })

    # 4. Liquidação da transação
    return PixTransactionResponse(
        transaction_id=tx.transaction_id,
        status="APPROVED",
        amount=tx.amount,
        description=res.message,
        original_masked=res.is_masked,
        canonical_message=res.canonical_message,
        evasion_detected=res.evasion_detected,
        timing=timing_metrics,
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
                "threat_intel_p50_ms": None,
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
    intel_vals = sorted([x["threat_intel_ms"] for x in SYNC_LATENCY_BUFFER])
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
            "threat_intel_p50_ms": calc_percentile(intel_vals, 0.50),
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
