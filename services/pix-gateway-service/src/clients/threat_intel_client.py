import time
import logging
from typing import Optional, Dict, Tuple
import httpx
from common.config.settings import settings
from common.schemas.threat import ThreatCheckResult
from common.utils.normalizer import normalize_threat_text, compute_threat_hash

logger = logging.getLogger("gateway.threat-intel-client")


class ThreatIntelClient:
    """Cliente de alta velocidade com cache LRU em memória para consulta à base de ameaças confirmadas."""

    def __init__(self, base_url: Optional[str] = None, ttl_seconds: float = 600.0):
        self.base_url = (base_url or settings.THREAT_INTEL_SERVICE_URL).rstrip("/")
        self.ttl_seconds = ttl_seconds
        # Cache em memória: text_hash -> (ThreatCheckResult, timestamp_expiracao)
        self._cache: Dict[str, Tuple[ThreatCheckResult, float]] = {}

    def _get_from_cache(self, thash: str) -> Optional[ThreatCheckResult]:
        now = time.time()
        entry = self._cache.get(thash)
        if entry:
            res, expires_at = entry
            if now < expires_at:
                return res
            # Expirado
            del self._cache[thash]
        return None

    def _set_in_cache(self, thash: str, result: ThreatCheckResult):
        # Limita tamanho máximo do cache para evitar vazamento de memória
        if len(self._cache) > 20000:
            self._cache.clear()
        self._cache[thash] = (result, time.time() + self.ttl_seconds)

    async def check(self, text: str) -> ThreatCheckResult:
        """Verifica se a mensagem é uma ameaça catalogada.
        Passo 1: Lookup em memória local (<0.05ms)
        Passo 2: Lookup HTTP no threat-intelligence-service (<1-2ms)
        """
        if not text or not text.strip():
            return ThreatCheckResult(is_threat=False, confidence=0.0)

        norm = normalize_threat_text(text)
        thash = compute_threat_hash(norm)

        # 1. Checagem em memória
        cached = self._get_from_cache(thash)
        if cached is not None:
            if cached.is_threat:
                logger.info(f"⚡ [CACHE LOCAL HIT] Ameaça confirmada identificada em memória: hash={thash[:12]}")
            return cached

        # 2. Checagem HTTP rápida no serviço
        url = f"{self.base_url}/threats/check"
        try:
            async with httpx.AsyncClient(timeout=0.5) as client:
                resp = await client.get(url, params={"text": text})
                if resp.status_code == 200:
                    data = resp.json()
                    res = ThreatCheckResult(**data)
                    if res.is_threat:
                        self._set_in_cache(thash, res)
                        logger.info(f"⚡ [THREAT INTEL HIT] Ameaça confirmada catalogada no Postgres: hash={thash[:12]}")
                    return res
        except Exception as e:
            logger.debug(f"Aviso ao consultar Threat Intel Service ({url}): {e}. Prosseguindo para Laya.")

        # Não cacheia falso negativo em memória para permitir que novas ameaças confirmadas sejam detectadas
        return ThreatCheckResult(is_threat=False, confidence=0.0)
