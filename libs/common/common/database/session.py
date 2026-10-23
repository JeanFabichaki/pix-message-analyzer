from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from common.config.settings import settings
from common.database.models import Base, User, UserStatus
from sqlalchemy import select, text

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

        # Migração idempotente para bases existentes (SQLite e PostgreSQL)
        for col_name, col_type in [
            ("gemini_model", "VARCHAR(64)"),
            ("prompt_tokens", "INTEGER DEFAULT 0"),
            ("completion_tokens", "INTEGER DEFAULT 0"),
            ("total_tokens", "INTEGER DEFAULT 0"),
            ("cost_usd", "FLOAT DEFAULT 0.0"),
            ("cost_brl", "FLOAT DEFAULT 0.0"),
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE threat_logs ADD COLUMN {col_name} {col_type}"))
            except Exception:
                # Coluna já existe ou não aplicável
                pass

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
