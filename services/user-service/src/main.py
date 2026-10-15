import logging
from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from common.database.session import get_db, init_db
from common.database.models import User
from common.schemas.user import UserResponse, UserBlockRequest, UserBlockResponse, UserCreate
from src.services.user_service import UserService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("user-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando user-service e garantindo schema do banco de dados...")
    await init_db()
    yield
    logger.info("Encerrando user-service.")


from fastapi.middleware.cors import CORSMiddleware
from common.database.models import ThreatLog, UserStatus

app = FastAPI(
    title="Pix Guard - User Governance Service",
    description="Serviço de governança e bloqueio de usuários para prevenção a abusos em Pix",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "user-service"}


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: str, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuário {user_id} não encontrado",
        )
    return user


@app.post("/users/ensure", response_model=UserResponse)
async def ensure_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    user = await service.ensure_user(
        user_id=payload.id or f"usr_{payload.cpf_cnpj[:6]}",
        cpf_cnpj=payload.cpf_cnpj,
        name=payload.name,
    )
    return user


@app.post("/users/{user_id}/block", response_model=UserBlockResponse)
async def block_user(
    user_id: str,
    payload: UserBlockRequest,
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    user = await service.block_user(user_id, payload)
    return UserBlockResponse(
        user_id=user.id,
        status=user.status,
        updated_at=user.updated_at,
    )


@app.post("/users/{user_id}/unblock", response_model=UserResponse)
async def unblock_user(user_id: str, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    user = await service.unblock_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return user


@app.post("/users/{user_id}/reset-threats")
async def reset_user_threats(user_id: str, db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    count = await service.reset_threats(user_id)
    # Também reativa o usuário
    await service.unblock_user(user_id)
    return {"status": "ok", "user_id": user_id, "deleted_logs": count, "new_status": "ACTIVE"}


@app.post("/audit/clear-history")
async def clear_audit_history(db: AsyncSession = Depends(get_db)):
    service = UserService(db)
    result = await service.clear_all_history()
    return {
        "status": "ok",
        "message": "Toda a base histórica foi limpa com sucesso.",
        "details": result,
    }



@app.get("/users", response_model=List[UserResponse])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    return result.scalars().all()


@app.get("/audit/threats")
async def list_all_threats(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(ThreatLog, User.name.label("user_name"), User.status.label("user_status"))
        .outerjoin(User, ThreatLog.user_id == User.id)
        .order_by(ThreatLog.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()
    threats = []
    for log, user_name, user_status in rows:
        threats.append({
            "id": log.id,
            "user_id": log.user_id,
            "user_name": user_name or "Desconhecido",
            "user_status": user_status.value if user_status else "ACTIVE",
            "transaction_id": log.transaction_id,
            "direction": log.direction.value if hasattr(log.direction, 'value') else str(log.direction),
            "original_message": log.original_message,
            "ollaya_score": log.ollaya_score,
            "ollaya_category": log.ollaya_category,
            "gemini_criticality": log.gemini_criticality.value if hasattr(log.gemini_criticality, 'value') else str(log.gemini_criticality),
            "gemini_category": log.gemini_category,
            "gemini_rationale": log.gemini_rationale,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })
    return threats


@app.get("/audit/metrics")
async def get_audit_metrics(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    total_users_res = await db.execute(select(func.count(User.id)))
    total_users = total_users_res.scalar_one()

    blocked_users_res = await db.execute(
        select(func.count(User.id)).where(User.status == UserStatus.BLOCKED_SUSPICIOUS)
    )
    blocked_users = blocked_users_res.scalar_one()

    total_threats_res = await db.execute(select(func.count(ThreatLog.id)))
    total_threats = total_threats_res.scalar_one()

    crit_res = await db.execute(
        select(ThreatLog.gemini_criticality, func.count(ThreatLog.id)).group_by(ThreatLog.gemini_criticality)
    )
    by_criticality = {str(k.value if hasattr(k, 'value') else k): count for k, count in crit_res.all() if k}

    cat_res = await db.execute(
        select(ThreatLog.gemini_category, func.count(ThreatLog.id)).group_by(ThreatLog.gemini_category)
    )
    by_category = {str(k): count for k, count in cat_res.all() if k}

    return {
        "total_users": total_users,
        "blocked_users": blocked_users,
        "active_users": total_users - blocked_users,
        "total_threats": total_threats,
        "threats_by_criticality": by_criticality,
        "threats_by_category": by_category,
    }

