import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from common.database.models import User, UserStatus
from common.schemas.user import UserBlockRequest

logger = logging.getLogger("user-service")


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_cpf(self, cpf_cnpj: str) -> Optional[User]:
        stmt = select(User).where(User.cpf_cnpj == cpf_cnpj)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def ensure_user(self, user_id: str, cpf_cnpj: str, name: str) -> User:
        user = await self.get_by_id(user_id)
        if user:
            return user

        # Verifica se existe por CPF
        user_by_cpf = await self.get_by_cpf(cpf_cnpj)
        if user_by_cpf:
            return user_by_cpf

        now = datetime.now(timezone.utc)
        # Cria novo usuário se não existir
        user = User(
            id=user_id,
            cpf_cnpj=cpf_cnpj,
            name=name,
            status=UserStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        logger.info(f"Usuário auto-provisionado: {user.id} ({user.name})")
        return user

    async def block_user(self, user_id: str, req: UserBlockRequest) -> Optional[User]:
        user = await self.get_by_id(user_id)
        now = datetime.now(timezone.utc)
        if not user:
            # Se não existir ainda, provisiona como bloqueado
            user = User(
                id=user_id,
                cpf_cnpj=f"CPF_{user_id[-8:]}",
                name=f"User {user_id}",
                status=UserStatus.BLOCKED_SUSPICIOUS,
                created_at=now,
                updated_at=now,
            )
            self.db.add(user)
        else:
            user.status = UserStatus.BLOCKED_SUSPICIOUS
            user.updated_at = now

        await self.db.commit()
        await self.db.refresh(user)

        logger.warning(
            f"USUÁRIO BLOQUEADO: id={user.id} status={user.status} "
            f"motivo={req.reason} total_ameacas={req.total_threats} tx={req.triggered_by_tx}"
        )
        return user

    async def unblock_user(self, user_id: str) -> Optional[User]:
        user = await self.get_by_id(user_id)
        if not user:
            return None
        user.status = UserStatus.ACTIVE
        user.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(user)
        logger.info(f"USUÁRIO DESBLOQUEADO: id={user.id} status={user.status}")
        return user

    async def reset_threats(self, user_id: str) -> int:
        from common.database.models import ThreatLog
        from sqlalchemy import delete
        stmt = delete(ThreatLog).where(ThreatLog.user_id == user_id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        logger.info(f"Ocorrências resetadas para user={user_id}: {result.rowcount} registros removidos")
        return result.rowcount

    async def clear_all_history(self) -> dict:
        from common.database.models import ThreatLog, User
        from sqlalchemy import delete, update

        stmt_threats = delete(ThreatLog)
        res_threats = await self.db.execute(stmt_threats)

        stmt_users = update(User).values(status=UserStatus.ACTIVE)
        res_users = await self.db.execute(stmt_users)

        await self.db.commit()
        logger.info(
            f"BASE HISTÓRICA ZERADA: {res_threats.rowcount} logs excluídos, "
            f"{res_users.rowcount} usuários reativados."
        )
        return {
            "deleted_threat_logs": res_threats.rowcount,
            "reactivated_users": res_users.rowcount,
        }

