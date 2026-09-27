import logging
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from common.database.session import get_db, init_db
from common.config.settings import settings
from common.schemas.threat import (
    ConfirmedThreatCreate,
    ConfirmedThreatResponse,
    ThreatCheckResult,
    ThreatIntelligenceStats,
)
from src.repository import ThreatIntelligenceRepository

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger("threat-intelligence-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando threat-intelligence-service e tabelas de conhecimento...")
    try:
        await init_db()
        logger.info("Banco de dados sincronizado com sucesso.")
    except Exception as e:
        logger.warning(f"Aviso ao inicializar DB (pode estar conectando ao cluster): {e}")
    yield
    logger.info("Encerrando threat-intelligence-service.")


app = FastAPI(
    title="Pix Guard - Threat Intelligence Service",
    description="Serviço de base de conhecimento de ameaças confirmadas por consenso (Laya + Gemini) para triagem rápida (<1-2ms).",
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
        "service": "threat-intelligence-service",
        "database": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "configured",
    }


@app.post("/threats/confirmed", response_model=ConfirmedThreatResponse, status_code=201)
async def record_confirmed_threat(
    threat_in: ConfirmedThreatCreate,
    db: AsyncSession = Depends(get_db),
):
    """Registra uma ameaça após validação de consenso entre Laya e Gemini."""
    repo = ThreatIntelligenceRepository(db)
    threat = await repo.record_threat(threat_in)
    return ConfirmedThreatResponse(
        id=threat.id,
        text_hash=threat.text_hash,
        normalized_text=threat.normalized_text,
        raw_text=threat.raw_text,
        laya_score=threat.laya_score,
        gemini_score=threat.gemini_score,
        category=threat.category,
        gemini_rationale=threat.gemini_rationale,
        occurrences_count=threat.occurrences_count,
        first_detected_at=threat.first_detected_at.isoformat(),
        last_detected_at=threat.last_detected_at.isoformat(),
    )


@app.get("/threats/check", response_model=ThreatCheckResult)
async def check_threat(
    text: str = Query(..., description="Texto da mensagem do Pix a ser verificado"),
    db: AsyncSession = Depends(get_db),
):
    """Consulta de ultra-alta velocidade (<1-2ms) via hash indexado na base de ameaças confirmadas."""
    repo = ThreatIntelligenceRepository(db)
    return await repo.check_threat(text)


@app.get("/threats/stats", response_model=ThreatIntelligenceStats)
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Retorna estatísticas de assinaturas e ocorrências de ameaças cadastradas."""
    repo = ThreatIntelligenceRepository(db)
    return await repo.get_stats()


@app.get("/threats", response_model=List[ConfirmedThreatResponse])
async def list_threats(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Lista as ameaças mais recentes cadastradas na base."""
    repo = ThreatIntelligenceRepository(db)
    threats = await repo.list_threats(limit=limit)
    return [
        ConfirmedThreatResponse(
            id=t.id,
            text_hash=t.text_hash,
            normalized_text=t.normalized_text,
            raw_text=t.raw_text,
            laya_score=t.laya_score,
            gemini_score=t.gemini_score,
            category=t.category,
            gemini_rationale=t.gemini_rationale,
            occurrences_count=t.occurrences_count,
            first_detected_at=t.first_detected_at.isoformat(),
            last_detected_at=t.last_detected_at.isoformat(),
        )
        for t in threats
    ]
