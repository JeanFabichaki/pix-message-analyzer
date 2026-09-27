from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from common.database.models import UserStatus


class UserCreate(BaseModel):
    id: Optional[str] = None
    cpf_cnpj: str
    name: str


class UserBlockRequest(BaseModel):
    reason: str = Field(..., description="Motivo do bloqueio")
    total_threats: int = Field(..., description="Contagem acumulada de ameaças")
    triggered_by_tx: Optional[str] = Field(default=None, description="ID da transação gatilho")
    details: Optional[str] = Field(default=None, description="Detalhes adicionais de auditoria")


class UserResponse(BaseModel):
    id: str
    cpf_cnpj: str
    name: str
    status: UserStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserBlockResponse(BaseModel):
    user_id: str
    status: UserStatus
    updated_at: datetime
