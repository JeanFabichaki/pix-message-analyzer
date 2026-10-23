import logging
import time
from typing import List, Optional, Any, Dict
from fastapi import BackgroundTasks
from common.config.settings import settings
from common.schemas.pix import PixTransactionRequest, TraceStep
from common.schemas.threat import OllayaClassificationResult
from common.utils.deobfuscator import deobfuscate_text
from src.clients.ollaya_client import OllayaClient
from src.clients.investigation import InvestigationClient

logger = logging.getLogger("gateway.interceptor")


class InterceptorResult:
    """Resultado da interceptação do Pix com suporte a compatibilidade retroativa.
    Permite tanto desempacotamento tradicional `msg, masked = res` quanto acesso rico
    `res.canonical_message`, `res.evasion_detected`, `res.timing`, `res.decided_by` e `res.trace`.
    """
    def __init__(
        self,
        message: Optional[str],
        is_blocked: bool = False,
        is_masked: bool = False,
        canonical_message: Optional[str] = None,
        evasion_detected: bool = False,
        timing: Optional[Dict[str, float]] = None,
        decided_by: str = "none",
        trace: Optional[List[TraceStep]] = None,
    ):
        self.message = message
        self.is_blocked = is_blocked
        self.is_masked = is_masked
        self.canonical_message = canonical_message
        self.evasion_detected = evasion_detected
        self.timing = timing or {}
        self.decided_by = decided_by
        self.trace = trace or []

    def __iter__(self):
        # Permite unpack de 2 elementos: final_message, is_blocked
        return iter([self.message, self.is_blocked])

    def __getitem__(self, idx: int) -> Any:
        if idx == 0:
            return self.message
        elif idx == 1:
            return self.is_blocked
        elif idx == 2:
            return self.canonical_message
        elif idx == 3:
            return self.evasion_detected
        raise IndexError(f"Index {idx} out of range for InterceptorResult")


def _skipped_steps(detail: str) -> List[TraceStep]:
    return [
        TraceStep(step="anti_evasion", status="skip", ms=0.0, detail=detail),
        TraceStep(step="ollaya", status="skip", ms=0.0, detail=detail),
    ]


class PixInterceptor:
    def __init__(
        self,
        ollaya: Optional[OllayaClient] = None,
        investigation: Optional[InvestigationClient] = None,
        ollaya_tuned: Optional[OllayaClient] = None,
    ):
        self.ollaya = ollaya or OllayaClient()
        self.ollaya_tuned = ollaya_tuned
        self.investigation = investigation

    async def _dispatch(
        self,
        tx: PixTransactionRequest,
        canonical_text: str,
        evasion_detected: bool,
        ollaya_data: Dict[str, Any],
        background_tasks: Optional[BackgroundTasks],
        await_without_background: bool,
    ) -> None:
        """Despacha a investigação assíncrona (em segundo plano quando possível)."""
        if not self.investigation:
            return
        kwargs = dict(
            user_id=tx.sender_id,
            transaction_id=tx.transaction_id,
            direction=tx.direction,
            text=tx.description,
            canonical_text=canonical_text,
            evasion_detected=evasion_detected,
            ollaya_data=ollaya_data,
        )
        if background_tasks:
            background_tasks.add_task(self.investigation.dispatch, **kwargs)
        elif await_without_background:
            await self.investigation.dispatch(**kwargs)

    async def inspect_and_filter(
        self,
        tx: PixTransactionRequest,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> InterceptorResult:
        """Avalia mensagem do Pix aplicando defesas multicamadas:
        - Camada 0 (<0.05ms): Desofuscação Canônica Anti-Bypass (leetspeak, separadores, zero-width)
        - Camada 1 (<15ms): Classificação em tempo real pelo modelo Ollaya (laya), sempre, para toda mensagem analisada
        Se for ameaça sob o threshold, mascara e despacha investigação assíncrona.
        Além da mensagem final, devolve o `trace` das estações percorridas e `decided_by`.
        """
        timing: Dict[str, float] = {}

        # 1. Regra de valor configurável (<= PIX_THRESHOLD_AMOUNT_BRL) e presença de texto
        has_message = bool(tx.description and tx.description.strip())
        is_under_threshold = tx.amount <= settings.PIX_THRESHOLD_AMOUNT_BRL

        if not (is_under_threshold and has_message):
            logger.debug(
                f"Transação {tx.transaction_id} ignorada da triagem (amount={tx.amount}, has_msg={has_message})"
            )
            if not has_message:
                reason = "A mensagem está vazia, então não há texto para analisar."
            else:
                reason = (
                    f"Valor de R$ {tx.amount:.2f} acima do limite de "
                    f"R$ {settings.PIX_THRESHOLD_AMOUNT_BRL:.2f} para análise de mensagem."
                )
            trace = [
                TraceStep(
                    step="amount_rule",
                    status="skip",
                    ms=0.01,
                    detail=reason,
                    data={"amount": tx.amount, "limit": settings.PIX_THRESHOLD_AMOUNT_BRL, "has_message": has_message},
                ),
                *_skipped_steps("Análise dispensada pela regra de valor/mensagem."),
                TraceStep(step="delivery", status="pass", ms=0.01, detail="Mensagem entregue sem alteração."),
            ]
            return InterceptorResult(
                tx.description,
                False,
                timing={"anti_evasion_ms": 0.01, "ollaya_ms": 0.0, "masking_ms": 0.01},
                decided_by="skipped",
                trace=trace,
            )

        amount_step = TraceStep(
            step="amount_rule",
            status="pass",
            ms=0.01,
            detail=(
                f"Valor de R$ {tx.amount:.2f} dentro do limite de "
                f"R$ {settings.PIX_THRESHOLD_AMOUNT_BRL:.2f} e com mensagem: vai para análise."
            ),
            data={"amount": tx.amount, "limit": settings.PIX_THRESHOLD_AMOUNT_BRL, "has_message": True},
        )

        # 2. ANTI-EVASION: Desofuscação Canônica Rápida (<0.05ms)
        t_anti_start = time.perf_counter()
        canonical_text, evasion_detected = deobfuscate_text(tx.description)
        anti_evasion_ms = round((time.perf_counter() - t_anti_start) * 1000, 3)
        timing["anti_evasion_ms"] = max(anti_evasion_ms, 0.02)
        if evasion_detected:
            logger.warning(
                f"⚠️ [ANTI-EVASION DETECTADA] TX {tx.transaction_id}: "
                f"Mensagem ofuscada '{tx.description}' normalizada para '{canonical_text}'"
            )
        evasion_step = TraceStep(
            step="anti_evasion",
            status="detect" if evasion_detected else "pass",
            ms=timing["anti_evasion_ms"],
            detail=(
                "Disfarce detectado e desfeito antes da análise."
                if evasion_detected
                else "Nenhum disfarce encontrado no texto."
            ),
            data={"original": tx.description, "canonical": canonical_text, "evasion_detected": evasion_detected},
        )

        # 3. Avaliação pelo Ollaya (Laya) passando o texto canônico desofuscado para máxima acurácia
        t_ollaya_start = time.perf_counter()
        ollaya_failed = False
        try:
            if tx.engine == "laya_tuned" and self.ollaya_tuned is not None:
                engine_client = self.ollaya_tuned
            else:
                engine_client = self.ollaya
            analysis_text = canonical_text if evasion_detected else tx.description
            ollaya_response = await engine_client.classify(analysis_text)
        except Exception as ex:
            logger.warning(f"Resiliência de Borda: Ollaya indisponível ou timeout ({ex}). Aprovando com fallback seguro.")
            ollaya_failed = True
            ollaya_response = OllayaClassificationResult(
                is_threat=False,
                score=0.0,
                category="fallback_timeout",
                model="ollaya_fallback",
                detail=f"Falha ou timeout Ollaya: {ex}",
            )
        ollaya_ms = round((time.perf_counter() - t_ollaya_start) * 1000, 2)
        timing["ollaya_ms"] = ollaya_ms

        # Tratamento calibrado da Zona Cinzenta (0.45 a 0.65):
        # Em transações de maior valor (> R$ 5,00) ou com tentativa de evasão disfarçada,
        # o risco residual é elevado: retém preventivamente para investigação assíncrona.
        if getattr(ollaya_response, "in_gray_zone", False) and not ollaya_response.is_threat:
            if tx.amount > 5.00 or evasion_detected:
                logger.warning(
                    f"⚠️ [ZONA CINZENTA RETIDA] TX {tx.transaction_id}: score={ollaya_response.score:.4f} "
                    f"em zona cinzenta (0.45-0.65) com amount=R$ {tx.amount:.2f} e evasion={evasion_detected}. Retendo para análise."
                )
                ollaya_response.is_threat = True
                ollaya_response.category = f"{ollaya_response.category}_retencao_preventiva"

        pure_inf_ms = getattr(ollaya_response, "inference_ms", None)
        net_overhead_ms = getattr(ollaya_response, "network_ms", None)
        timing["ollaya_inference_ms"] = pure_inf_ms
        timing["ollaya_network_ms"] = net_overhead_ms

        ollaya_data = {
            "score": ollaya_response.score,
            "category": ollaya_response.category,
            "model": ollaya_response.model,
            "decomposed_scores": getattr(ollaya_response, "decomposed_scores", None),
            "in_gray_zone": getattr(ollaya_response, "in_gray_zone", False),
            "pure_inference_ms": pure_inf_ms,
            "network_ms": net_overhead_ms,
        }

        t_mask_start = time.perf_counter()
        if not ollaya_response.is_threat:
            logger.info(
                f"Mensagem da transação {tx.transaction_id} aprovada pelo Ollaya [{ollaya_response.model}] "
                f"(score={ollaya_response.score:.4f}, evasion={evasion_detected})."
            )
            masking_ms = round((time.perf_counter() - t_mask_start) * 1000, 3)
            timing["masking_ms"] = max(masking_ms, 0.03)
            if ollaya_failed:
                ollaya_step = TraceStep(
                    step="ollaya",
                    status="error",
                    ms=ollaya_ms,
                    detail="A IA rápida não respondeu a tempo. Por segurança do fluxo financeiro, o Pix foi aprovado.",
                    data=ollaya_data,
                )
            else:
                ollaya_step = TraceStep(
                    step="ollaya",
                    status="pass",
                    ms=ollaya_ms,
                    detail="A IA rápida avaliou a mensagem como segura.",
                    data=ollaya_data,
                )
            return InterceptorResult(
                tx.description,
                False,
                canonical_message=canonical_text,
                evasion_detected=evasion_detected,
                timing=timing,
                decided_by="ollaya_fallback" if ollaya_failed else "none",
                trace=[
                    amount_step,
                    evasion_step,
                    ollaya_step,
                    TraceStep(
                        step="delivery",
                        status="pass",
                        ms=timing["masking_ms"],
                        detail="Mensagem entregue sem alteração.",
                    ),
                ],
            )

        logger.warning(
            f"AMEAÇA DETECTADA NA TX {tx.transaction_id} PELO OLLAYA [{ollaya_response.model}]: "
            f"score={ollaya_response.score:.4f}, cat={ollaya_response.category}, evasion={evasion_detected}. Bloqueando envio do Pix."
        )

        # 4. Disparo assíncrono para o Gemini e auditoria
        ollaya_payload = ollaya_response.model_dump()
        ollaya_payload["canonical_text"] = canonical_text
        ollaya_payload["evasion_detected"] = evasion_detected
        await self._dispatch(
            tx,
            canonical_text,
            evasion_detected,
            ollaya_payload,
            background_tasks,
            await_without_background=True,
        )

        # 5. Bloqueio imediato do envio do Pix (a mensagem original não é alterada)
        masking_ms = round((time.perf_counter() - t_mask_start) * 1000, 3)
        timing["masking_ms"] = max(masking_ms, 0.05)
        return InterceptorResult(
            tx.description,
            is_blocked=True,
            is_masked=False,
            canonical_message=canonical_text,
            evasion_detected=evasion_detected,
            timing=timing,
            decided_by="ollaya",
            trace=[
                amount_step,
                evasion_step,
                TraceStep(
                    step="ollaya",
                    status="detect",
                    ms=ollaya_ms,
                    detail="A IA rápida identificou intimidação ou ameaça na mensagem.",
                    data=ollaya_data,
                ),
                TraceStep(
                    step="delivery",
                    status="detect",
                    ms=timing["masking_ms"],
                    detail="Envio do Pix bloqueado por conter ameaça. O valor não foi transferido.",
                ),
            ],
        )
