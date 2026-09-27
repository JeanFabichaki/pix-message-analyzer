import logging
from typing import Optional
import httpx
from common.config.settings import settings
from common.schemas.threat import ConfirmedThreatCreate, ConfirmedThreatResponse

logger = logging.getLogger("gemini-agent.threat-intel-client")


class ThreatIntelClient:
    """Cliente para registrar ameaças confirmadas por consenso no Threat Intelligence Service."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.THREAT_INTEL_SERVICE_URL).rstrip("/")

    async def record_confirmed_threat(self, threat_in: ConfirmedThreatCreate) -> Optional[ConfirmedThreatResponse]:
        url = f"{self.base_url}/threats/confirmed"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.post(url, json=threat_in.model_dump())
                if resp.status_code == 201:
                    data = resp.json()
                    logger.info(f"✅ Ameaça confirmada registrada no Threat Intelligence Service: hash={data.get('text_hash')[:12]}")
                    return ConfirmedThreatResponse(**data)
                else:
                    logger.warning(f"Falha ao registrar ameaça no Threat Intel: status={resp.status_code}, body={resp.text}")
        except Exception as e:
            logger.error(f"Erro ao conectar com Threat Intel Service ({url}): {e}")
        return None
