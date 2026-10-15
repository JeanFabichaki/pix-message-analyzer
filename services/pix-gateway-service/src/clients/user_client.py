import logging
from typing import Optional
import httpx
from common.config.settings import settings
from common.schemas.user import UserResponse, UserCreate

logger = logging.getLogger("gateway.user-client")


class GatewayUserClient:
    def __init__(self, user_service_url: str = settings.USER_SERVICE_URL):
        self.user_service_url = user_service_url.rstrip("/")

    async def ensure_user(self, user_id: str, cpf_cnpj: str, name: str) -> Optional[UserResponse]:
        """Garante que o usuário existe cadastrado."""
        url = f"{self.user_service_url}/users/ensure"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                payload = UserCreate(id=user_id, cpf_cnpj=cpf_cnpj, name=name)
                resp = await client.post(url, json=payload.model_dump())
                if resp.status_code == 200:
                    return UserResponse(**resp.json())
        except Exception as e:
            logger.warning(f"Erro ao auto-provisionar usuário {user_id}: {e}")
        return None
