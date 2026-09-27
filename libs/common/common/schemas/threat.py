from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
from common.database.models import TransactionDirection


class OllayaClassificationResult(BaseModel):
    is_threat: bool = Field(..., description="Indica se a mensagem foi classificada como ameaça pelo modelo de decisão Ollaya")
    score: float = Field(default=0.0, description="Probabilidade ou confiança de ameaça calibrada pelo Ollaya")
    category: Optional[str] = Field(default=None, description="Categoria de decisão detectada pelo Ollaya")
    model: str = Field(default="laya", description="Modelo de decisão do Ollaya utilizado")
    detail: Optional[str] = Field(default=None, description="Detalhes adicionais da resposta do Ollaya")


# Alias para retrocompatibilidade
JevClassificationResult = OllayaClassificationResult


class GeminiThreatAnalysis(BaseModel):
    is_valid_threat: bool = Field(
        description="Confirmação semântica de se a mensagem constitui intimidação, assédio, extorsão ou ameaça"
    )
    criticidade: Literal["BAIXA", "MEDIA", "ALTA", "CRITICA"] = Field(
        description="Nível de gravidade do risco avaliado"
    )
    categoria: Literal[
        "extorsao",
        "violencia_fisica",
        "stalking_perseguicao",
        "injuria_difamacao",
        "outros",
    ] = Field(description="Classificação categórica da ofensa")
    resumo_analise: str = Field(
        description="Justificativa concisa da criticidade para fundamentação de auditoria"
    )
    acao_imediata_recomendada: bool = Field(
        description="Se a infração é grave o suficiente para intervenção prioritária"
    )


class InvestigationDispatchPayload(BaseModel):
    user_id: str
    transaction_id: str
    direction: TransactionDirection
    text: str
    canonical_text: Optional[str] = None
    evasion_detected: bool = False
    jev_data: Optional[Dict[str, Any]] = None


class ConfirmedThreatCreate(BaseModel):
    raw_text: str = Field(..., description="Texto original da mensagem de Pix")
    laya_score: Optional[float] = Field(default=None, description="Score atribuído pelo Laya")
    gemini_score: Optional[float] = Field(default=None, description="Score ou certeza do Gemini")
    category: Optional[str] = Field(default=None, description="Categoria semântica identificada")
    gemini_rationale: Optional[str] = Field(default=None, description="Justificativa do Gemini")


class ConfirmedThreatResponse(BaseModel):
    id: str
    text_hash: str
    normalized_text: str
    raw_text: str
    laya_score: Optional[float] = None
    gemini_score: Optional[float] = None
    category: Optional[str] = None
    gemini_rationale: Optional[str] = None
    occurrences_count: float
    first_detected_at: str
    last_detected_at: str


class ThreatCheckResult(BaseModel):
    is_threat: bool
    source: str = "threat_intel_service"
    text_hash: Optional[str] = None
    category: Optional[str] = None
    confidence: float = 0.0
    detail: Optional[str] = None


class ThreatIntelligenceStats(BaseModel):
    total_signatures: int
    total_occurrences: int
    last_updated: Optional[str] = None
