from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from common.config.settings import settings
from common.database.models import Base, User, UserStatus
from sqlalchemy import select

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.LOG_LEVEL.upper() == "DEBUG"),
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Cria tabelas e insere seeds essenciais se não existirem."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Inserção de seeds iniciais para os testes da PoC
    async with AsyncSessionLocal() as session:
        async with session.begin():
            seeds = [
                {"id": "usr_abc123", "cpf_cnpj": "12345678901", "name": "Alice Sender", "status": UserStatus.ACTIVE},
                {"id": "usr_xyz789", "cpf_cnpj": "98765432100", "name": "Bob Receiver", "status": UserStatus.ACTIVE},
            ]
            for seed in seeds:
                existing = await session.execute(select(User).where(User.id == seed["id"]))
                if not existing.scalar_one_or_none():
                    session.add(User(**seed))
