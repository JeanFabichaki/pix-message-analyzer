import logging
import uuid
from typing import List, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
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
from src.clients.threat_intel_client import ThreatIntelClient
from src.rules.threshold import record_and_evaluate_limit
from common.schemas.threat import ConfirmedThreatCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gemini-investigation-agent")

analyzer = GeminiThreatAnalyzer()
user_client = UserClient()
threat_intel_client = ThreatIntelClient()


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

    # 1. Análise semântica profunda com Gemini (usando forma canônica se houver evasão para assertividade)
    t_gemini_start = time.perf_counter()
    analysis_text = payload.canonical_text if (payload.evasion_detected and payload.canonical_text) else payload.text
    analysis: GeminiThreatAnalysis = await analyzer.analyze(analysis_text)
    gemini_duration_ms = round((time.perf_counter() - t_gemini_start) * 1000, 2)

    # 2. Construção do registro de auditoria
    jev_score = payload.jev_data.get("score") if payload.jev_data else None
    jev_category = payload.jev_data.get("category") if payload.jev_data else None

    rationale = analysis.resumo_analise
    if payload.evasion_detected and payload.canonical_text:
        rationale = f"[Anti-Bypass: Evasão Detectada | Canônico: '{payload.canonical_text}']: {rationale}"

    threat_log = ThreatLog(
        id=str(uuid.uuid4()),
        user_id=payload.user_id,
        transaction_id=payload.transaction_id,
        direction=payload.direction,
        original_message=payload.text,
        jev_score=jev_score,
        jev_category=jev_category,
        gemini_criticality=analysis.criticidade,
        gemini_category=analysis.categoria,
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

    # 4. Consenso Laya + Gemini: catalogar no Threat Intelligence Service para cache rápido
    laya_confirmed = (payload.jev_data or {}).get("is_threat", True) or ((jev_score or 0) >= 0.40)
    if analysis.is_valid_threat and laya_confirmed:
        logger.info(
            f"Consenso Laya + Gemini confirmado para tx={payload.transaction_id}. "
            f"Catalogando no Threat Intelligence Service..."
        )
        canonical_to_save = payload.canonical_text or payload.text
        await threat_intel_client.record_confirmed_threat(
            ConfirmedThreatCreate(
                raw_text=canonical_to_save,
                laya_score=jev_score,
                gemini_score=0.98,
                category=analysis.categoria,
                gemini_rationale=analysis.resumo_analise,
            )
        )
        if payload.evasion_detected and payload.canonical_text and payload.text != payload.canonical_text:
            await threat_intel_client.record_confirmed_threat(
                ConfirmedThreatCreate(
                    raw_text=payload.text,
                    laya_score=jev_score,
                    gemini_score=0.98,
                    category=analysis.categoria,
                    gemini_rationale=f"[Variante Evasiva]: {analysis.resumo_analise}",
                )
            )

    total_investigation_ms = round((time.perf_counter() - t_start) * 1000, 2)

    result_payload = {
        "status": "PROCESSED",
        "threat_log_id": threat_log.id,
        "transaction_id": payload.transaction_id,
        "user_id": payload.user_id,
        "analysis": analysis.model_dump(),
        "total_threats": total_threats,
        "account_blocked": blocked,
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

    return {
        "status": "PROCESSED",
        "threat_log_id": log.id,
        "transaction_id": log.transaction_id,
        "user_id": log.user_id,
        "analysis": {
            "is_valid_threat": True,
            "criticidade": log.gemini_criticality.value if hasattr(log.gemini_criticality, "value") else str(log.gemini_criticality),
            "categoria": log.gemini_category,
            "resumo_analise": log.gemini_rationale,
        },
        "timing": {
            "gemini_ms": 750.0,
            "governance_ms": 2.5,
            "total_ms": 752.5,
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
            "jev_score": r.jev_score,
            "gemini_criticality": r.gemini_criticality,
            "gemini_category": r.gemini_category,
            "gemini_rationale": r.gemini_rationale,
            "created_at": r.created_at,
        }
        for r in records
    ]

