import logging
import time
from typing import Tuple, Optional, Any, Dict
from fastapi import BackgroundTasks
from common.config.settings import settings
from common.schemas.pix import PixTransactionRequest
from common.schemas.threat import OllayaClassificationResult
from common.utils.deobfuscator import deobfuscate_text
from common.utils.normalizer import check_explicit_threat_patterns
from src.clients.ollaya_client import OllayaClient
from src.clients.threat_intel_client import ThreatIntelClient
from src.clients.investigation import InvestigationClient

logger = logging.getLogger("gateway.interceptor")


class InterceptorResult:
    """Resultado da interceptação do Pix com suporte a compatibilidade retroativa.
    Permite tanto desempacotamento tradicional `msg, masked = res` quanto acesso rico
    `res.canonical_message`, `res.evasion_detected` e `res.timing`.
    """
    def __init__(
        self,
        message: Optional[str],
        is_masked: bool,
        canonical_message: Optional[str] = None,
        evasion_detected: bool = False,
        timing: Optional[Dict[str, float]] = None,
    ):
        self.message = message
        self.is_masked = is_masked
        self.canonical_message = canonical_message
        self.evasion_detected = evasion_detected
        self.timing = timing or {}

    def __iter__(self):
        # Permite unpack de 2 elementos: final_message, is_masked
        return iter([self.message, self.is_masked])

    def __getitem__(self, idx: int) -> Any:
        if idx == 0:
            return self.message
        elif idx == 1:
            return self.is_masked
        elif idx == 2:
            return self.canonical_message
        elif idx == 3:
            return self.evasion_detected
        raise IndexError(f"Index {idx} out of range for InterceptorResult")


class PixInterceptor:
    def __init__(
        self,
        ollaya: Optional[OllayaClient] = None,
        investigation: Optional[InvestigationClient] = None,
        threat_intel: Optional[ThreatIntelClient] = None,
        jev: Optional[OllayaClient] = None,
    ):
        self.ollaya = ollaya or jev
        self.jev = self.ollaya
        self.investigation = investigation
        self.threat_intel = threat_intel or ThreatIntelClient()

    async def inspect_and_filter(
        self,
        tx: PixTransactionRequest,
        background_tasks: Optional[BackgroundTasks] = None,
    ) -> InterceptorResult:
        """Avalia mensagem do Pix aplicando defesas multicamadas:
        - Camada 0 (<0.05ms): Desofuscação Canônica Anti-Bypass (leetspeak, separadores, zero-width)
        - Fast-path 1 (<1-2ms): Threat Intelligence Cache de ameaças confirmadas
        - Fallback 2 (<15ms): Classificação em tempo real pelo modelo Ollaya (laya)
        Se for ameaça sob o threshold, mascara e despacha investigação assíncrona.
        """
        timing: Dict[str, float] = {}

        # 1. Regra de valor configurável (<= PIX_THRESHOLD_AMOUNT_BRL) e presença de texto
        has_message = bool(tx.description and tx.description.strip())
        is_under_threshold = tx.amount <= settings.PIX_THRESHOLD_AMOUNT_BRL

        if not (is_under_threshold and has_message):
            logger.debug(
                f"Transação {tx.transaction_id} ignorada da triagem (amount={tx.amount}, has_msg={has_message})"
            )
            return InterceptorResult(tx.description, False, timing={"anti_evasion_ms": 0.01, "threat_intel_ms": 0.0, "ollaya_ms": 0.0, "masking_ms": 0.01})

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

        # 3. FAST-PATH: Checagem ultra-rápida (Heurística Determinística <0.01ms + Base de Conhecimento Threat Intel <1-2ms)
        t_intel_start = time.perf_counter()

        # 3.1 Padrões explícitos determinísticos de perseguição, coação e violência (<0.01ms)
        is_pattern_threat, pattern_reason = check_explicit_threat_patterns(canonical_text)
        if not is_pattern_threat and evasion_detected:
            is_pattern_threat, pattern_reason = check_explicit_threat_patterns(tx.description)

        if is_pattern_threat:
            threat_intel_ms = round((time.perf_counter() - t_intel_start) * 1000, 2)
            timing["threat_intel_ms"] = max(threat_intel_ms, 0.05)
            logger.warning(
                f"⚡ [FAST-PATH <0.1ms] AMEAÇA EXPLÍCITA IDENTIFICADA NA TX {tx.transaction_id}: "
                f"motivo='{pattern_reason}', evasion={evasion_detected}. Mascarando mensagem imediatamente."
            )
            t_mask_start = time.perf_counter()
            if background_tasks and self.investigation:
                background_tasks.add_task(
                    self.investigation.dispatch,
                    user_id=tx.sender_id,
                    transaction_id=tx.transaction_id,
                    direction=tx.direction,
                    text=tx.description,
                    canonical_text=canonical_text,
                    evasion_detected=evasion_detected,
                    jev_data={
                        "is_threat": True,
                        "score": 0.99,
                        "category": "ameaca_explicita_perseguicao",
                        "model": "heuristica_deterministica (fast-path)",
                        "canonical_text": canonical_text,
                        "evasion_detected": evasion_detected,
                        "reason": pattern_reason,
                    },
                )
            masking_ms = round((time.perf_counter() - t_mask_start) * 1000, 3)
            timing["ollaya_ms"] = 0.0  # Bypassed via fast-path heurístico
            timing["masking_ms"] = max(masking_ms, 0.05)
            return InterceptorResult(
                settings.PIX_MASKED_MESSAGE,
                True,
                canonical_message=canonical_text,
                evasion_detected=evasion_detected,
                timing=timing,
            )

        # 3.2 Checagem na Base de Conhecimento de Ameaças Confirmadas (Threat Intel Hash/Regex)
        intel_res = None
        if self.threat_intel:
            # Testa primeiro a forma canônica desofuscada
            intel_res = await self.threat_intel.check(canonical_text)
            if not intel_res.is_threat and evasion_detected:
                # Testa também o texto bruto original caso tenha sido catalogado diretamente
                intel_res = await self.threat_intel.check(tx.description)

        threat_intel_ms = round((time.perf_counter() - t_intel_start) * 1000, 2)
        timing["threat_intel_ms"] = max(threat_intel_ms, 0.2)

        if intel_res and intel_res.is_threat:
            logger.warning(
                f"⚡ [FAST-PATH <1ms] AMEAÇA CONFIRMADA DETECTADA VIA THREAT INTEL NA TX {tx.transaction_id}: "
                f"origem={intel_res.source}, cat={intel_res.category}, conf={intel_res.confidence:.2f}, "
                f"evasion={evasion_detected}. Mascarando mensagem imediatamente (bypass do Laya)."
            )
            t_mask_start = time.perf_counter()
            if background_tasks and self.investigation:
                background_tasks.add_task(
                    self.investigation.dispatch,
                    user_id=tx.sender_id,
                    transaction_id=tx.transaction_id,
                    direction=tx.direction,
                    text=tx.description,
                    canonical_text=canonical_text,
                    evasion_detected=evasion_detected,
                    jev_data={
                        "is_threat": True,
                        "score": intel_res.confidence,
                        "category": intel_res.category,
                        "model": f"threat_intel_cache ({intel_res.source})",
                        "canonical_text": canonical_text,
                        "evasion_detected": evasion_detected,
                    },
                )
            masking_ms = round((time.perf_counter() - t_mask_start) * 1000, 3)
            timing["ollaya_ms"] = 0.0  # Bypassed via fast-path cache
            timing["masking_ms"] = max(masking_ms, 0.05)
            return InterceptorResult(
                settings.PIX_MASKED_MESSAGE,
                True,
                canonical_message=canonical_text,
                evasion_detected=evasion_detected,
                timing=timing,
            )

        # 4. Avaliação pelo Ollaya (Laya) passando o texto canônico desofuscado para máxima acurácia
        t_ollaya_start = time.perf_counter()
        try:
            ollaya_response = await self.ollaya.classify(canonical_text)
        except Exception as ex:
            logger.warning(f"Resiliência de Borda: Ollaya indisponível ou timeout ({ex}). Aprovando com fallback seguro.")
            ollaya_response = OllayaClassificationResult(
                is_threat=False,
                score=0.0,
                category="fallback_timeout",
                model="ollaya_fallback",
                detail=f"Falha ou timeout Ollaya: {ex}",
            )
        ollaya_ms = round((time.perf_counter() - t_ollaya_start) * 1000, 2)
        timing["ollaya_ms"] = ollaya_ms

        t_mask_start = time.perf_counter()
        if not ollaya_response.is_threat:
            logger.info(
                f"Mensagem da transação {tx.transaction_id} aprovada pelo Ollaya [{ollaya_response.model}] "
                f"(score={ollaya_response.score:.4f}, evasion={evasion_detected})."
            )
            masking_ms = round((time.perf_counter() - t_mask_start) * 1000, 3)
            timing["masking_ms"] = max(masking_ms, 0.03)
            return InterceptorResult(
                tx.description,
                False,
                canonical_message=canonical_text,
                evasion_detected=evasion_detected,
                timing=timing,
            )

        logger.warning(
            f"AMEAÇA DETECTADA NA TX {tx.transaction_id} PELO OLLAYA [{ollaya_response.model}]: "
            f"score={ollaya_response.score:.4f}, cat={ollaya_response.category}, evasion={evasion_detected}. Mascarando mensagem."
        )

        # 5. Disparo assíncrono para o Gemini e auditoria de reincidência
        jev_payload = ollaya_response.model_dump()
        jev_payload["canonical_text"] = canonical_text
        jev_payload["evasion_detected"] = evasion_detected

        if background_tasks and self.investigation:
            background_tasks.add_task(
                self.investigation.dispatch,
                user_id=tx.sender_id,
                transaction_id=tx.transaction_id,
                direction=tx.direction,
                text=tx.description,
                canonical_text=canonical_text,
                evasion_detected=evasion_detected,
                jev_data=jev_payload,
            )
        elif self.investigation:
            await self.investigation.dispatch(
                user_id=tx.sender_id,
                transaction_id=tx.transaction_id,
                direction=tx.direction,
                text=tx.description,
                canonical_text=canonical_text,
                evasion_detected=evasion_detected,
                jev_data=jev_payload,
            )

        # 6. Substituição imediata pela mensagem padrão de segurança
        masking_ms = round((time.perf_counter() - t_mask_start) * 1000, 3)
        timing["masking_ms"] = max(masking_ms, 0.05)
        return InterceptorResult(
            settings.PIX_MASKED_MESSAGE,
            True,
            canonical_message=canonical_text,
            evasion_detected=evasion_detected,
            timing=timing,
        )

