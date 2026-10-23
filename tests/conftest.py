import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from common.database.models import Base, User, UserStatus
from common.config.settings import settings

# Força mock do Gemini para a suíte de testes (o Ollaya é injetado nos testes via tests/fakes.py)
settings.MOCK_GEMINI = True
settings.PIX_THRESHOLD_AMOUNT_BRL = 10.00
settings.THREAT_BLOCK_LIMIT = 5
settings.PERSISTENCE_TYPE = "sql"

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        # Insere seeds padrão
        seeds = [
            User(id="usr_abc123", cpf_cnpj="12345678901", name="Alice Sender", status=UserStatus.ACTIVE),
            User(id="usr_xyz789", cpf_cnpj="98765432100", name="Bob Receiver", status=UserStatus.ACTIVE),
        ]
        session.add_all(seeds)
        await session.commit()
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
