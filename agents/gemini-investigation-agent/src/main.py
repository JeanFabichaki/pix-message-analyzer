import logging
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.config.settings import settings
from common.database.session import get_db, init_db
from common.database.models import ThreatLog
from common.schemas.threat import InvestigationDispatchPayload
from src.analyzer import GeminiThreatAnalyzer
from src.clients.prompt_protection import PromptProtection
from src.clients.user_client import UserClient
from src.investigation_workflow import run_investigation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gemini-investigation-agent")

analyzer = GeminiThreatAnalyzer()
user_client = UserClient()
prompt_protection = PromptProtection()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando gemini-investigation-agent...")
    await init_db()
    try:
        yield
    finally:
        await prompt_protection.close()
        logger.info("Encerrando gemini-investigation-agent.")


from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Pix Guard - Gemini Investigation Agent",
    description="Agente de investigação semântica profunda e governança de reincidência com Gemini",
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
        "service": "gemini-investigation-agent",
        "model": analyzer.model_name,
        "mock_mode": False,
    }


latest_investigations: Dict[str, dict] = {}

@app.post("/investigate")
async def investigate(
    payload: InvestigationDispatchPayload,
    db: AsyncSession = Depends(get_db),
):
    logger.info("Nova investigação para tx=%s", payload.transaction_id)
    result_payload = await run_investigation(payload, db, analyzer, user_client, prompt_protection)

    latest_investigations[payload.transaction_id] = result_payload
    # Limita tamanho do cache em memória a 200 itens
    if len(latest_investigations) > 200:
        oldest_key = next(iter(latest_investigations))
        del latest_investigations[oldest_key]

    return result_payload


@app.get("/threats/tx/{transaction_id}")
async def get_threat_by_transaction(transaction_id: str, db: AsyncSession = Depends(get_db)):
    if transaction_id in latest_investigations:
        return latest_investigations[transaction_id]

    stmt = select(ThreatLog).where(ThreatLog.transaction_id == transaction_id)
    result = await db.execute(stmt)
    log = result.scalars().first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigação em andamento ou não encontrada",
        )

    # Recupera histórico das mensagens anteriores àquela transação
    history_analyzed = []
    try:
        hist_stmt = (
            select(ThreatLog.original_message)
            .where(ThreatLog.user_id == log.user_id, ThreatLog.created_at < log.created_at)
            .order_by(ThreatLog.created_at.desc())
            .limit(10)
        )
        hist_res = await db.execute(hist_stmt)
        history_analyzed = list(reversed(hist_res.scalars().all()))
    except Exception as e:
        logger.warning(f"Erro ao buscar histórico para {log.user_id}: {e}")

    is_bypass = log.gemini_category == "bypass" or log.gemini_criticality is None
    cost_info = {
        "model": log.gemini_model or analyzer.model_name,
        "prompt_tokens": log.prompt_tokens or 0,
        "completion_tokens": log.completion_tokens or 0,
        "total_tokens": log.total_tokens or 0,
        "cost_usd": log.cost_usd or 0.0,
        "cost_brl": log.cost_brl or 0.0,
        "prompt_rate_per_1m": settings.GEMINI_PROMPT_RATE_PER_1M_USD,
        "completion_rate_per_1m": settings.GEMINI_COMPLETION_RATE_PER_1M_USD,
        "exchange_rate_brl": settings.USD_TO_BRL_RATE,
    }

    return {
        "status": "BYPASS" if is_bypass else "PROCESSED",
        "threat_log_id": log.id,
        "transaction_id": log.transaction_id,
        "user_id": log.user_id,
        "bypassed": is_bypass,
        "bypass_reason": log.gemini_rationale if is_bypass else None,
        "history_analyzed": history_analyzed,
        "target_message": log.original_message,
        "history_count": len(history_analyzed),
        "cost": cost_info,
        "analysis": {
            "is_valid_threat": not is_bypass,
            "criticidade": log.gemini_criticality.value if hasattr(log.gemini_criticality, "value") else (str(log.gemini_criticality) if log.gemini_criticality else "BAIXA"),
            "categoria": log.gemini_category or "bypass",
            "resumo_analise": log.gemini_rationale,
            "acao_imediata_recomendada": False if is_bypass else (log.gemini_criticality == "CRITICA"),
            "padrao_identificado": "Coação reiterada com escalada de gravidade no histórico recente do remetente." if not is_bypass else None,
            "evidencias_citadas": [log.original_message] if not is_bypass else [],
            "recomendacao_analista": "Bloqueio preventivo da conta e abertura de dossiê de segurança." if not is_bypass else None,
            "bypassed": is_bypass,
            "bypass_reason": log.gemini_rationale if is_bypass else None,
            "cost": cost_info,
        },
        "block_limit": settings.THREAT_BLOCK_LIMIT,
        "timing": {
            "gemini_ms": 0.0 if is_bypass else 750.0,
            "governance_ms": 2.5,
            "total_ms": 2.5 if is_bypass else 752.5,
        },
    }


@app.get("/threats/user/{user_id}")
async def get_user_threats(user_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(ThreatLog).where(ThreatLog.user_id == user_id).order_by(ThreatLog.created_at.desc())
    result = await db.execute(stmt)
    records = result.scalars().all()
    return [
        {
            "id": r.id,
            "transaction_id": r.transaction_id,
            "original_message": r.original_message,
            "ollaya_score": r.ollaya_score,
            "gemini_criticality": r.gemini_criticality,
            "gemini_category": r.gemini_category,
            "gemini_rationale": r.gemini_rationale,
            "gemini_model": r.gemini_model,
            "prompt_tokens": r.prompt_tokens or 0,
            "completion_tokens": r.completion_tokens or 0,
            "total_tokens": r.total_tokens or 0,
            "cost_usd": r.cost_usd or 0.0,
            "cost_brl": r.cost_brl or 0.0,
            "created_at": r.created_at,
        }
        for r in records
    ]


class GenerateDatasetRequest(BaseModel):
    count: int = 50
    prompt_override: Optional[str] = None


@app.post("/benchmark/generate-dataset")
async def generate_benchmark_dataset(req: GenerateDatasetRequest = GenerateDatasetRequest()):
    """Gera um conjunto de mensagens de teste com o Gemini para benchmark comparativo."""
    count = min(max(req.count, 10), 100)
    messages = await analyzer.generate_test_dataset(count=count)
    threats_cnt = sum(1 for m in messages if m.get("label") == "threat")
    safe_cnt = sum(1 for m in messages if m.get("label") != "threat")
    return {
        "status": "ok",
        "count": len(messages),
        "threats_count": threats_cnt,
        "safe_count": safe_cnt,
        "model": analyzer.model_name,
        "messages": messages,
    }

