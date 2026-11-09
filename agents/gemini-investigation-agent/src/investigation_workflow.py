import logging
import time
import uuid
from typing import Any

from google.adk import Workflow
from google.adk.runners import InMemoryRunner
from google.genai import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.config.settings import settings
from common.database.models import ThreatLog
from common.schemas.threat import GeminiThreatAnalysis, InvestigationDispatchPayload
from src.analyzer import GeminiThreatAnalyzer
from src.clients.prompt_protection import PromptProtection, PromptProtectionError
from src.clients.user_client import UserClient
from src.rules.threshold import record_and_evaluate_limit

logger = logging.getLogger("gemini-agent.workflow")


async def _load_history(
    payload: InvestigationDispatchPayload, db: AsyncSession | None
) -> list[str]:
    if payload.history is not None:
        return payload.history
    if db is None:
        return []

    try:
        query = (
            select(ThreatLog.original_message)
            .where(ThreatLog.user_id == payload.user_id)
            .order_by(ThreatLog.created_at.desc())
            .limit(10)
        )
        result = await db.execute(query)
        return list(reversed(result.scalars().all()))
    except Exception:
        logger.warning("Não foi possível buscar histórico da investigação", exc_info=True)
        return []


async def run_investigation(
    payload: InvestigationDispatchPayload,
    db: AsyncSession | None,
    analyzer: GeminiThreatAnalyzer,
    user_client: UserClient,
    protection: PromptProtection,
) -> dict[str, Any]:
    """Executa os passos da investigação em um workflow local do ADK."""
    started = time.perf_counter()
    history: list[str] = []
    analysis: GeminiThreatAnalysis | None = None
    armor_ms = 0.0
    dlp_ms = 0.0
    gemini_ms = 0.0
    result: dict[str, Any] | None = None
    text = payload.text
    if payload.evasion_detected and payload.canonical_text:
        text = payload.canonical_text
    needs_protection = analyzer.gemini_available and bool(text.strip())
    protected_messages: list[str] = []

    # Os nós compartilham dados somente nesta chamada. A sessão do ADK não
    # recebe o texto Pix, o histórico, o laudo nem identificadores do cliente.
    async def load_history() -> None:
        nonlocal history
        history = await _load_history(payload, db)

    async def check_model_armor() -> None:
        nonlocal analysis, armor_ms, history
        if not needs_protection:
            return
        check_started = time.perf_counter()
        try:
            await protection.screen([text, *history[-10:]])
        except PromptProtectionError as exc:
            # Se o lote falhou mas temos histórico, verifica se a mensagem atual (alvo) é limpa
            if history:
                try:
                    await protection.screen([text])
                    # A mensagem atual sob investigação é segura contra injeção/jailbreak.
                    # O histórico anterior continha injeção/risco. Expurgamos o histórico contaminado
                    # para que a perícia da nova ameaça no Gemini não seja bloqueada.
                    logger.warning(
                        "Model Armor: mensagem atual limpa, mas histórico continha injeção anterior. "
                        "Expurgando histórico contaminado para prosseguir com a perícia da nova ameaça."
                    )
                    history = []
                except PromptProtectionError:
                    analysis = analyzer.bypass_analysis(str(exc))
                except Exception as inner_exc:
                    logger.warning("Falha ao validar mensagem isolada no Model Armor (%s)", type(inner_exc).__name__)
                    analysis = analyzer.bypass_analysis("Falha ao verificar o conteúdo no Model Armor.")
            else:
                analysis = analyzer.bypass_analysis(str(exc))
        except Exception as exc:
            logger.warning("Falha no Model Armor (%s)", type(exc).__name__)
            analysis = analyzer.bypass_analysis("Falha ao verificar o conteúdo no Model Armor.")
        finally:
            armor_ms = round((time.perf_counter() - check_started) * 1000, 2)

    async def deidentify_sensitive_data() -> None:
        nonlocal analysis, protected_messages, dlp_ms
        if not needs_protection or analysis is not None:
            return
        check_started = time.perf_counter()
        try:
            protected_messages = await protection.deidentify([text, *history[-10:]])
        except PromptProtectionError as exc:
            analysis = analyzer.bypass_analysis(str(exc))
        except Exception as exc:
            logger.warning("Falha no Cloud DLP (%s): %s", type(exc).__name__, exc, exc_info=True)
            analysis = analyzer.bypass_analysis("Falha ao mascarar dados pessoais no Cloud DLP.")
        finally:
            dlp_ms = round((time.perf_counter() - check_started) * 1000, 2)

    async def analyze_message() -> None:
        nonlocal analysis, gemini_ms
        if analysis is not None:
            return
        analysis_started = time.perf_counter()
        if needs_protection:
            target, *protected_history = protected_messages
            analysis = await analyzer.analyze(target, history=protected_history)
        else:
            analysis = await analyzer.analyze(text)
        gemini_ms = round((time.perf_counter() - analysis_started) * 1000, 2)

    async def persist_report() -> None:
        nonlocal result
        if analysis is None:
            raise RuntimeError("A investigação terminou sem resultado de análise")

        score = payload.ollaya_data or {}
        rationale = analysis.resumo_analise
        if payload.evasion_detected and payload.canonical_text and not analysis.bypassed:
            rationale = (
                f"[Anti-Bypass: Evasão Detectada | Canônico: '{payload.canonical_text}']: "
                f"{rationale}"
            )
        cost = analysis.cost
        threat_log = ThreatLog(
            id=str(uuid.uuid4()),
            user_id=payload.user_id,
            transaction_id=payload.transaction_id,
            direction=payload.direction,
            original_message=payload.text,
            ollaya_score=score.get("score"),
            ollaya_category=score.get("category"),
            gemini_criticality=None if analysis.bypassed else analysis.criticidade,
            gemini_category="bypass" if analysis.bypassed else analysis.categoria,
            gemini_rationale=rationale,
            gemini_model=cost.model if cost else analyzer.model_name,
            prompt_tokens=cost.prompt_tokens if cost else 0,
            completion_tokens=cost.completion_tokens if cost else 0,
            total_tokens=cost.total_tokens if cost else 0,
            cost_usd=cost.cost_usd if cost else 0.0,
            cost_brl=cost.cost_brl if cost else 0.0,
        )

        governance_started = time.perf_counter()
        total_threats, blocked = await record_and_evaluate_limit(
            user_id=payload.user_id,
            threat_log=threat_log,
            user_client=user_client,
            session=db,
        )
        governance_ms = round((time.perf_counter() - governance_started) * 1000, 2)
        dlp_target = protected_messages[0] if (needs_protection and protected_messages) else payload.text
        dlp_hist = protected_messages[1:] if (needs_protection and len(protected_messages) > 1) else []
        result = {
            "status": "BYPASS" if analysis.bypassed else "PROCESSED",
            "threat_log_id": threat_log.id,
            "transaction_id": payload.transaction_id,
            "user_id": payload.user_id,
            "analysis": analysis.model_dump(),
            "cost": cost.model_dump() if cost else None,
            "history_analyzed": history,
            "target_message": payload.text,
            "canonical_message": payload.canonical_text if payload.evasion_detected else payload.text,
            "armor_message": text,
            "dlp_message": dlp_target,
            "dlp_history": dlp_hist,
            "evasion_detected": payload.evasion_detected,
            "history_count": len(history),
            "bypassed": analysis.bypassed,
            "bypass_reason": analysis.bypass_reason,
            "total_threats": total_threats,
            "account_blocked": blocked,
            "block_limit": settings.THREAT_BLOCK_LIMIT,
            "timing": {
                "model_armor_ms": armor_ms,
                "cloud_dlp_ms": dlp_ms,
                "gemini_ms": gemini_ms,
                "governance_ms": max(governance_ms, 0.5),
            },
        }

    workflow = Workflow(
        name="pix_investigation",
        edges=[(
            "START",
            load_history,
            check_model_armor,
            deidentify_sensitive_data,
            analyze_message,
            persist_report,
        )],
    )
    async with InMemoryRunner(node=workflow, app_name="pix_investigation") as runner:
        session = await runner.session_service.create_session(
            app_name=runner.app_name, user_id="pix_guard"
        )
        trigger = types.Content(role="user", parts=[types.Part(text="investigate")])
        async for _ in runner.run_async(
            user_id=session.user_id, session_id=session.id, new_message=trigger
        ):
            pass

    if result is None:
        raise RuntimeError("O workflow de investigação não registrou o laudo")
    result["timing"]["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return result
