import logging
import httpx
from common.config.settings import settings
from common.database.models import TransactionDirection
from common.schemas.threat import InvestigationDispatchPayload

logger = logging.getLogger("gateway.investigation-client")


class InvestigationClient:
    def __init__(self, agent_url: str = settings.GEMINI_AGENT_URL):
        self.agent_url = agent_url.rstrip("/")

    async def dispatch(
        self,
        user_id: str,
        transaction_id: str,
        direction: TransactionDirection,
        text: str,
        canonical_text: str = None,
        evasion_detected: bool = False,
        ollaya_data: dict = None,
    ):
        """Dispara investigação assíncrona para o gemini-investigation-agent."""
        url = f"{self.agent_url}/investigate"
        payload = InvestigationDispatchPayload(
            user_id=user_id,
            transaction_id=transaction_id,
            direction=direction,
            text=text,
            canonical_text=canonical_text,
            evasion_detected=evasion_detected,
            ollaya_data=ollaya_data,
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload.model_dump())
                resp.raise_for_status()
                logger.info(
                    f"Investigação para tx={transaction_id} despachada com sucesso: status={resp.status_code}"
                )
        except Exception as e:
            logger.error(f"Erro ao despachar investigação para {url} (tx={transaction_id}): {e}")
