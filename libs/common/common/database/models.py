import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, Integer, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    BLOCKED_SUSPICIOUS = "BLOCKED_SUSPICIOUS"


class TransactionDirection(str, enum.Enum):
    CASH_IN = "CASH_IN"
    CASH_OUT = "CASH_OUT"


class CriticalityLevel(str, enum.Enum):
    BAIXA = "BAIXA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    CRITICA = "CRITICA"


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    cpf_cnpj = Column(String(18), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    status = Column(SQLEnum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    threats = relationship("ThreatLog", back_populates="user", cascade="all, delete-orphan")


class ThreatLog(Base):
    __tablename__ = "threat_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    transaction_id = Column(String(64), nullable=False, index=True)
    direction = Column(SQLEnum(TransactionDirection), nullable=False)
    original_message = Column(Text, nullable=False)
    ollaya_score = Column(Float, nullable=True)
    ollaya_category = Column(String(64), nullable=True)
    gemini_criticality = Column(SQLEnum(CriticalityLevel), nullable=True)
    gemini_category = Column(String(64), nullable=True)
    gemini_rationale = Column(Text, nullable=True)

    # Telemetria financeira e contagem de tokens da chamada ao Gemini
    gemini_model = Column(String(64), nullable=True)
    prompt_tokens = Column(Integer, nullable=True, default=0)
    completion_tokens = Column(Integer, nullable=True, default=0)
    total_tokens = Column(Integer, nullable=True, default=0)
    cost_usd = Column(Float, nullable=True, default=0.0)
    cost_brl = Column(Float, nullable=True, default=0.0)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    user = relationship("User", back_populates="threats")
