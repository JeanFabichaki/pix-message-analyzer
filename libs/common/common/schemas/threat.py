from typing import Literal, Optional, Dict, Any, List
from pydantic import BaseModel, Field

from common.database.models import TransactionDirection


class OllayaClassificationResult(BaseModel):
    is_threat: bool = Field(..., description="Indica se a mensagem foi classificada como ameaça pelo modelo de decisão Ollaya")
    score: float = Field(default=0.0, description="Probabilidade ou confiança de ameaça calibrada pelo Ollaya")
    category: Optional[str] = Field(default=None, description="Categoria de decisão detectada pelo Ollaya")
    model: str = Field(default="laya", description="Modelo de decisão do Ollaya utilizado")
    detail: Optional[str] = Field(default=None, description="Detalhes adicionais da resposta do Ollaya")
    decomposed_scores: Optional[Dict[str, float]] = Field(default=None, description="Probabilidades separadas das perguntas decompostas")
    in_gray_zone: bool = Field(default=False, description="Indica se a probabilidade máxima ficou na zona cinzenta (0.45 a 0.65)")


class GeminiCostMetadata(BaseModel):
    model: str = Field(default="gemini-2.5-flash", description="Nome do modelo Gemini utilizado")
    prompt_tokens: int = Field(default=0, description="Tokens de entrada (prompt + histórico + instruções)")
    completion_tokens: int = Field(default=0, description="Tokens de saída gerados pelo modelo (laudo estruturado)")
    total_tokens: int = Field(default=0, description="Total de tokens consumidos na chamada")
    cost_usd: float = Field(default=0.0, description="Custo da chamada em Dólares (USD)")
    cost_brl: float = Field(default=0.0, description="Custo estimado da chamada em Reais (BRL)")
    prompt_rate_per_1m: float = Field(default=0.10, description="Tarifa por 1M de tokens de entrada em USD")
    completion_rate_per_1m: float = Field(default=0.40, description="Tarifa por 1M de tokens de saída em USD")
    exchange_rate_brl: float = Field(default=5.70, description="Taxa de câmbio USD -> BRL utilizada")


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
    padrao_identificado: Optional[str] = Field(
        default=None,
        description="Padrão criminoso ou comportamental identificado na mensagem ou série de mensagens",
    )
    evidencias_citadas: List[str] = Field(
        default_factory=list,
        description="Trechos ou termos textuais específicos extraídos que comprovam a infração",
    )
    recomendacao_analista: Optional[str] = Field(
        default=None,
        description="Ação sugerida para o analista humano de compliance e prevenção a fraudes",
    )
    bypassed: bool = Field(
        default=False,
        description="Indica se a análise do Gemini foi ignorada/bypassed por indisponibilidade",
    )
    bypass_reason: Optional[str] = Field(
        default=None,
        description="Motivo detalhado do bypass caso o Gemini não tenha sido chamado",
    )
    cost: Optional[GeminiCostMetadata] = Field(
        default=None,
        description="Métricas de consumo de tokens e custo financeiro da chamada (USD/BRL)",
    )


class InvestigationDispatchPayload(BaseModel):
    user_id: str
    transaction_id: str
    direction: TransactionDirection
    text: str
    canonical_text: Optional[str] = None
    evasion_detected: bool = False
    ollaya_data: Optional[Dict[str, Any]] = None
    history: Optional[List[str]] = Field(
        default=None,
        description="Histórico recente de mensagens anteriores para análise contextual continuada",
    )


class GeneratedBenchmarkMessage(BaseModel):
    id: str = Field(..., description="Identificador único, ex: gemini-01")
    text: str = Field(..., description="Texto da descrição da transação Pix")
    label: Literal["threat", "safe"] = Field(..., description="Rótulo binário: threat ou safe")
    category: str = Field(
        ...,
        description="Categoria: violencia, chantagem, cobranca_agressiva, extorsao_violenta, stalking, pagamento, idioma_violento, cobranca_educada, neutra",
    )
    explanation: Optional[str] = Field(default=None, description="Breve justificativa da classificação")


class GeneratedBenchmarkDataset(BaseModel):
    messages: List[GeneratedBenchmarkMessage] = Field(default_factory=list)

