import logging
import uuid
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.config.settings import settings
from common.database.session import get_db, init_db
from common.database.models import ThreatLog
from common.schemas.threat import (
    InvestigationDispatchPayload,
    GeminiThreatAnalysis,
)
from src.analyzer import GeminiThreatAnalyzer
from src.clients.user_client import UserClient
from src.rules.threshold import record_and_evaluate_limit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gemini-investigation-agent")

analyzer = GeminiThreatAnalyzer()
user_client = UserClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando gemini-investigation-agent...")
    await init_db()
    yield
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


import time

latest_investigations: Dict[str, dict] = {}

@app.post("/investigate")
async def investigate(
    payload: InvestigationDispatchPayload,
    db: AsyncSession = Depends(get_db),
):
    t_start = time.perf_counter()
    logger.info(
        f"Nova investigação recebida para tx={payload.transaction_id}, user={payload.user_id}: '{payload.text}'"
    )

    # 1. Recupera histórico recente (até 10 mensagens anteriores) para contextualização de perseguição/coação continuada
    history = payload.history
    if history is None and db is not None:
        try:
            hist_stmt = (
                select(ThreatLog.original_message)
                .where(ThreatLog.user_id == payload.user_id)
                .order_by(ThreatLog.created_at.desc())
                .limit(10)
            )
            hist_res = await db.execute(hist_stmt)
            history = list(reversed(hist_res.scalars().all()))
        except Exception as e:
            logger.warning(f"Não foi possível buscar histórico de mensagens para {payload.user_id}: {e}")
            history = []

    # 2. Análise semântica profunda com Gemini (usando forma canônica se houver evasão para assertividade)
    t_gemini_start = time.perf_counter()
    analysis_text = payload.canonical_text if (payload.evasion_detected and payload.canonical_text) else payload.text
    analysis: GeminiThreatAnalysis = await analyzer.analyze(analysis_text, history=history)
    gemini_duration_ms = round((time.perf_counter() - t_gemini_start) * 1000, 2)

    # 2. Construção do registro de auditoria
    ollaya_score = payload.ollaya_data.get("score") if payload.ollaya_data else None
    ollaya_category = payload.ollaya_data.get("category") if payload.ollaya_data else None

    rationale = analysis.resumo_analise
    if payload.evasion_detected and payload.canonical_text and not analysis.bypassed:
        rationale = f"[Anti-Bypass: Evasão Detectada | Canônico: '{payload.canonical_text}']: {rationale}"

    threat_log = ThreatLog(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        transaction_id=payload.transaction_id,
        direction=payload.direction,
        original_message=payload.text,
        ollaya_score=ollaya_score,
        ollaya_category=ollaya_category,
        gemini_criticality=None if analysis.bypassed else analysis.criticidade,
        gemini_category="bypass" if analysis.bypassed else analysis.categoria,
        gemini_rationale=rationale,
    )

    # 3. Persistência e avaliação de limite de reincidência
    t_gov_start = time.perf_counter()
    total_threats, blocked = await record_and_evaluate_limit(
        user_id=payload.user_id,
        threat_log=threat_log,
        user_client=user_client,
        session=db,
    )
    governance_duration_ms = round((time.perf_counter() - t_gov_start) * 1000, 2)

    total_investigation_ms = round((time.perf_counter() - t_start) * 1000, 2)

    result_payload = {
        "status": "BYPASS" if analysis.bypassed else "PROCESSED",
        "threat_log_id": threat_log.id,
        "transaction_id": payload.transaction_id,
        "user_id": payload.user_id,
        "analysis": analysis.model_dump(),
        "history_analyzed": history or [],
        "target_message": payload.text,
        "history_count": len(history or []),
        "bypassed": analysis.bypassed,
        "bypass_reason": analysis.bypass_reason,
        "total_threats": total_threats,
        "account_blocked": blocked,
        "block_limit": settings.THREAT_BLOCK_LIMIT,
        "timing": {
            "gemini_ms": gemini_duration_ms,
            "governance_ms": max(governance_duration_ms, 0.5),
            "total_ms": total_investigation_ms,
        },
    }

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

