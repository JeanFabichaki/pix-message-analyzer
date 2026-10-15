import asyncio
import argparse
import sys
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, delete

from common.database.models import Base, User, UserStatus, ThreatLog

SEED_USERS = [
    # Baseline Users
    {"id": "usr_abc123", "cpf_cnpj": "12345678901", "name": "Alice Sender", "status": UserStatus.ACTIVE},
    {"id": "usr_xyz789", "cpf_cnpj": "98765432100", "name": "Bob Receiver", "status": UserStatus.ACTIVE},

    # Presets do Simulador Pix (Screen 1)
    {"id": "usr_stalker_01", "cpf_cnpj": "11223344556", "name": "Stalker Perseguição", "status": UserStatus.ACTIVE},
    {"id": "usr_extorsao_02", "cpf_cnpj": "22334455667", "name": "Extorsão Familiar", "status": UserStatus.ACTIVE},
    {"id": "usr_sextort_03", "cpf_cnpj": "33445566778", "name": "Chantagem Sextorsão", "status": UserStatus.ACTIVE},
    {"id": "usr_agiotagem_04", "cpf_cnpj": "44556677889", "name": "Agiota Cobrança Predatória", "status": UserStatus.ACTIVE},
    {"id": "usr_evasion_multi", "cpf_cnpj": "55667788990", "name": "Evasão Anti-Bypass", "status": UserStatus.ACTIVE},
    {"id": "usr_amigo_123", "cpf_cnpj": "66778899001", "name": "Amigo Benigno", "status": UserStatus.ACTIVE},
    {"id": "usr_condominio_01", "cpf_cnpj": "77889900112", "name": "Condomínio Formal", "status": UserStatus.ACTIVE},
    {"id": "usr_isento_999", "cpf_cnpj": "88990011223", "name": "Isento BACEN Teto", "status": UserStatus.ACTIVE},
    {"id": "usr_repeat_offender", "cpf_cnpj": "99001122334", "name": "Reincidente Suspensão 5x", "status": UserStatus.ACTIVE},

    # Usuários do Gerador Sintético da Matriz (Screen 2)
    {"id": "usr_repeat_01", "cpf_cnpj": "11122233344", "name": "Carlos Infrator", "status": UserStatus.ACTIVE},
    {"id": "usr_repeat_02", "cpf_cnpj": "55566677788", "name": "Marcos Cobrador", "status": UserStatus.ACTIVE},
    {"id": "usr_client_03", "cpf_cnpj": "44433322211", "name": "Juliana Costa", "status": UserStatus.ACTIVE},
    {"id": "usr_client_04", "cpf_cnpj": "99887766554", "name": "Rafael Souza", "status": UserStatus.ACTIVE},
    {"id": "usr_client_05", "cpf_cnpj": "77665544332", "name": "Beatriz Lima", "status": UserStatus.ACTIVE},
    {"id": "usr_rec_02", "cpf_cnpj": "12345678000199", "name": "Mercado Central LTDA", "status": UserStatus.ACTIVE},
    {"id": "usr_rec_03", "cpf_cnpj": "98765432000188", "name": "Cafe & Cia", "status": UserStatus.ACTIVE},
    {"id": "usr_rec_04", "cpf_cnpj": "33221144000155", "name": "Dona Maria Doces", "status": UserStatus.ACTIVE},
]


async def reset_and_seed_database(database_url: str, db_label: str = ""):
    print(f"\n🔄 Conectando ao banco de dados [{db_label}]: {database_url}...")
    engine = create_async_engine(database_url, echo=False)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    try:
        # Recria tabelas do zero
        async with engine.begin() as conn:
            print("  - Excluindo tabelas antigas (drop_all)...")
            await conn.run_sync(Base.metadata.drop_all)
            print("  - Criando tabelas limpas (create_all)...")
            await conn.run_sync(Base.metadata.create_all)

        # Insere seeds
        now = datetime.now(timezone.utc)
        async with session_maker() as session:
            async with session.begin():
                for user_data in SEED_USERS:
                    user = User(
                        id=user_data["id"],
                        cpf_cnpj=user_data["cpf_cnpj"],
                        name=user_data["name"],
                        status=user_data["status"],
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(user)

        print(f"  ✅ Banco [{db_label}] recriado com sucesso! {len(SEED_USERS)} usuários padrão semeados.")

    except Exception as e:
        print(f"  ❌ Erro ao resetar [{db_label}]: {e}")
        raise
    finally:
        await engine.dispose()


async def main():
    parser = argparse.ArgumentParser(description="Reset e Seed da Base de Dados Pix Guard")
    parser.add_argument(
        "--target",
        choices=["all", "postgres", "sqlite"],
        default="all",
        help="Alvo do reset: 'postgres', 'sqlite', ou 'all' (ambos)",
    )
    args = parser.parse_args()

    postgres_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/pix_guard_db"
    sqlite_url = "sqlite+aiosqlite:///./pix_guard.db"

    print("==================================================")
    print("      PIX GUARD - RESET E GERAÇÃO DA BASE         ")
    print("==================================================")

    if args.target in ["all", "postgres"]:
        try:
            await reset_and_seed_database(postgres_url, "PostgreSQL (Docker)")
        except Exception as ex:
            print(f"Aviso: Não foi possível resetar PostgreSQL: {ex}")

    if args.target in ["all", "sqlite"]:
        try:
            await reset_and_seed_database(sqlite_url, "SQLite Local (pix_guard.db)")
        except Exception as ex:
            print(f"Aviso: Não foi possível resetar SQLite: {ex}")

    print("\n🎉 Processo de preparação da base de dados finalizado!")


if __name__ == "__main__":
    asyncio.run(main())
