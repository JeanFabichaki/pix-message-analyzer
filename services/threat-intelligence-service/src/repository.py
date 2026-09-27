import logging
from typing import Optional, List, Dict, Any
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from common.database.models import ConfirmedThreat, utc_now
from common.utils.normalizer import normalize_threat_text, compute_threat_hash
from common.schemas.threat import (
    ConfirmedThreatCreate,
    ThreatCheckResult,
    ThreatIntelligenceStats,
)

logger = logging.getLogger("threat-intel.repository")


class ThreatIntelligenceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_threat(self, threat_in: ConfirmedThreatCreate) -> ConfirmedThreat:
        """Registra ou atualiza contagem de uma ameaça confirmada por consenso Laya + Gemini."""
        norm_text = normalize_threat_text(threat_in.raw_text)
        thash = compute_threat_hash(norm_text)

        stmt = select(ConfirmedThreat).where(ConfirmedThreat.text_hash == thash)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.occurrences_count += 1.0
            existing.last_detected_at = utc_now()
            if threat_in.laya_score and (existing.laya_score is None or threat_in.laya_score > existing.laya_score):
                existing.laya_score = threat_in.laya_score
            if threat_in.gemini_score and (existing.gemini_score is None or threat_in.gemini_score > existing.gemini_score):
                existing.gemini_score = threat_in.gemini_score
            if threat_in.gemini_rationale:
                existing.gemini_rationale = threat_in.gemini_rationale
            await self.session.commit()
            await self.session.refresh(existing)
            logger.info(f"Ameaça recorrente atualizada na base: hash={thash[:12]} (total={existing.occurrences_count})")
            return existing

        new_threat = ConfirmedThreat(
            text_hash=thash,
            normalized_text=norm_text,
            raw_text=threat_in.raw_text,
            laya_score=threat_in.laya_score,
            gemini_score=threat_in.gemini_score,
            category=threat_in.category or "ameaca_confirmada",
            gemini_rationale=threat_in.gemini_rationale,
            occurrences_count=1.0,
            first_detected_at=utc_now(),
            last_detected_at=utc_now(),
        )
        self.session.add(new_threat)
        await self.session.commit()
        await self.session.refresh(new_threat)
        logger.info(f"Nova ameaça confirmada catalogada: hash={thash[:12]}, cat={new_threat.category}")
        return new_threat

    async def check_threat(self, text: str) -> ThreatCheckResult:
        """Verifica se a mensagem corresponde a uma ameaça previamente confirmada.
        Lookup indexado O(1) por hash SHA-256 do texto normalizado.
        """
        norm_text = normalize_threat_text(text)
        if not norm_text:
            return ThreatCheckResult(is_threat=False, confidence=0.0, detail="Texto vazio")

        thash = compute_threat_hash(norm_text)

        # 1. Match exato por hash indexado (sub-milissegundo no Postgres)
        stmt = select(ConfirmedThreat).where(ConfirmedThreat.text_hash == thash)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()

        if record:
            conf = 0.99
            if record.laya_score and record.gemini_score:
                conf = max(record.laya_score, record.gemini_score)
            return ThreatCheckResult(
                is_threat=True,
                source="threat_intel_hash_match",
                text_hash=record.text_hash,
                category=record.category,
                confidence=conf,
                detail=f"Match exato de ameaça confirmada (detectada {int(record.occurrences_count)}x)",
            )

        # 2. Busca por contenção para frases com pelo menos 15 caracteres
        if len(norm_text) >= 15:
            containment_stmt = (
                select(ConfirmedThreat)
                .where(
                    or_(
                        ConfirmedThreat.normalized_text.ilike(f"%{norm_text}%"),
                        func.length(ConfirmedThreat.normalized_text) >= 15
                    )
                )
                .limit(5)
            )
            # Para manter ultrarrápido, comparamos apenas se a assinatura de ameaça está contida no texto recebido
            c_result = await self.session.execute(containment_stmt)
            candidates = c_result.scalars().all()
            for cand in candidates:
                if cand.normalized_text in norm_text:
                    return ThreatCheckResult(
                        is_threat=True,
                        source="threat_intel_pattern_containment",
                        text_hash=cand.text_hash,
                        category=cand.category,
                        confidence=0.95,
                        detail=f"Padrão de ameaça confirmada identificado na mensagem: '{cand.normalized_text[:30]}...'",
                    )

        return ThreatCheckResult(
            is_threat=False,
            source="threat_intel_service",
            confidence=0.0,
            detail="Nenhuma assinatura conhecida encontrada na base de ameaças",
        )

    async def get_stats(self) -> ThreatIntelligenceStats:
        """Obtém volumetria de assinaturas e ocorrências."""
        stmt = select(
            func.count(ConfirmedThreat.id),
            func.coalesce(func.sum(ConfirmedThreat.occurrences_count), 0),
            func.max(ConfirmedThreat.last_detected_at),
        )
        res = await self.session.execute(stmt)
        count, occurrences, max_date = res.one()
        return ThreatIntelligenceStats(
            total_signatures=int(count or 0),
            total_occurrences=int(occurrences or 0),
            last_updated=max_date.isoformat() if max_date else None,
        )

    async def list_threats(self, limit: int = 50) -> List[ConfirmedThreat]:
        stmt = select(ConfirmedThreat).order_by(ConfirmedThreat.last_detected_at.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
