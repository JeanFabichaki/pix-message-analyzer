import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Enum as SQLEnum
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
    jev_score = Column(Float, nullable=True)
    jev_category = Column(String(64), nullable=True)
    gemini_criticality = Column(SQLEnum(CriticalityLevel), nullable=True)
    gemini_category = Column(String(64), nullable=True)
    gemini_rationale = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    user = relationship("User", back_populates="threats")


class ConfirmedThreat(Base):
    """Base de conhecimento de ameaças confirmadas por consenso entre Laya e Gemini.
    Usada como cache de ultra-alta velocidade (<1-2ms) para proteção de pagamentos Pix.
    """
    __tablename__ = "confirmed_threats"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    text_hash = Column(String(64), unique=True, nullable=False, index=True)
    normalized_text = Column(Text, nullable=False, index=True)
    raw_text = Column(Text, nullable=False)
    laya_score = Column(Float, nullable=True)
    gemini_score = Column(Float, nullable=True)
    category = Column(String(64), nullable=True)
    gemini_rationale = Column(Text, nullable=True)
    occurrences_count = Column(Float, default=1.0, nullable=False)
    first_detected_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_detected_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
