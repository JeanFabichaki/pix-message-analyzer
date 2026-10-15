import logging
from typing import Tuple
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from common.database.models import ThreatLog, User, UserStatus
from common.database.session import AsyncSessionLocal
from common.config.settings import settings
from src.clients.user_client import UserClient

logger = logging.getLogger("gemini-agent.threshold")


async def record_and_evaluate_limit(
    user_id: str,
    threat_log: ThreatLog,
    user_client: UserClient,
    session: AsyncSession = None,
) -> Tuple[int, bool]:
    """Registra a ameaça investigada e verifica o limite de reincidência para bloqueio."""
    if session is not None:
        return await _process_threat(session, user_id, threat_log, user_client)

    async with AsyncSessionLocal() as db_session:
        return await _process_threat(db_session, user_id, threat_log, user_client)


async def _process_threat(
    session: AsyncSession,
    user_id: str,
    threat_log: ThreatLog,
    user_client: UserClient,
) -> Tuple[int, bool]:
    import hashlib
    import uuid

    user_stmt = select(User).where(User.id == user_id)
    user_res = await session.execute(user_stmt)
    existing_user = user_res.scalar_one_or_none()

    if not existing_user:
        cpf_num = "".join(str(int(c, 16) % 10) for c in hashlib.md5(user_id.encode()).hexdigest()[:11])
        cpf_check = await session.execute(select(User).where(User.cpf_cnpj == cpf_num))
        if cpf_check.scalar_one_or_none():
            cpf_num = f"{cpf_num[:7]}{uuid.uuid4().hex[:4]}"
        new_user = User(
            id=user_id,
            cpf_cnpj=cpf_num,
            name=f"User {user_id}",
            status=UserStatus.ACTIVE,
        )
        session.add(new_user)
        try:
            await session.flush()
        except Exception:
            await session.rollback()

    # 2. Persiste a ocorrência em threat_logs
    session.add(threat_log)
    await session.commit()

    # 3. Contagem de ameaças registradas para este usuário
    query = select(func.count(ThreatLog.id)).where(ThreatLog.user_id == user_id)
    result = await session.execute(query)
    total_threats = result.scalar_one()

    logger.info(
        f"Ameaça registrada para user={user_id}. Total acumulado: {total_threats}/{settings.THREAT_BLOCK_LIMIT}"
    )

    # 4. Bloqueio de conta agora é decisão do analista humano baseado no laudo do Gemini.
    # Não há mais bloqueio automático por contagem de ameaças.
    blocked = bool(existing_user and existing_user.status == UserStatus.BLOCKED_SUSPICIOUS)
    logger.info(
        f"Ameaça registrada para user={user_id}. Total acumulado: {total_threats}. "
        f"Bloqueio de conta sob governança do analista humano (blocked={blocked})."
    )

    return total_threats, blocked
