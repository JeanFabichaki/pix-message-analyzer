import logging
from typing import Optional
import httpx
from common.config.settings import settings
from common.schemas.user import UserResponse, UserCreate

logger = logging.getLogger("gateway.user-client")


class GatewayUserClient:
    def __init__(self, user_service_url: str = settings.USER_SERVICE_URL):
        self.user_service_url = user_service_url.rstrip("/")

    async def get_user_status(self, user_id: str) -> Optional[str]:
        """Consulta o status do usuário no user-service."""
        url = f"{self.user_service_url}/users/{user_id}"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("status")
                return None
        except Exception as e:
            logger.warning(f"Não foi possível obter status do usuário {user_id}: {e}")
            return None

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
