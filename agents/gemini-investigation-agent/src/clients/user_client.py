import logging
import httpx
from common.config.settings import settings
from common.schemas.user import UserBlockRequest, UserBlockResponse

logger = logging.getLogger("gemini-agent.user-client")


class UserClient:
    def __init__(self, base_url: str = settings.USER_SERVICE_URL):
        self.base_url = base_url.rstrip("/")

    async def block_user(
        self,
        user_id: str,
        reason: str,
        total_threats: int,
        triggered_by_tx: str = None,
        details: str = None,
    ) -> UserBlockResponse:
        url = f"{self.base_url}/users/{user_id}/block"
        payload = UserBlockRequest(
            reason=reason,
            total_threats=total_threats,
            triggered_by_tx=triggered_by_tx,
            details=details or "Bloqueio preventivo automático disparado pelo Gemini Investigation Agent.",
        )
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.post(url, json=payload.model_dump())
                response.raise_for_status()
                data = response.json()
                logger.info(f"Usuário {user_id} bloqueado com sucesso no user-service: {data}")
                return UserBlockResponse(**data)
            except Exception as e:
                logger.error(f"Falha ao solicitar bloqueio do usuário {user_id} em {url}: {e}")
                raise
