from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from common.database.models import TransactionDirection


class PixTransactionRequest(BaseModel):
    transaction_id: str = Field(..., description="Identificador único da transação Pix")
    sender_id: str = Field(..., description="ID do usuário remetente no sistema")
    sender_cpf: str = Field(..., description="CPF/CNPJ do remetente")
    receiver_id: str = Field(..., description="ID do usuário destinatário")
    receiver_cpf: str = Field(..., description="CPF/CNPJ do destinatário")
    direction: TransactionDirection = Field(
        default=TransactionDirection.CASH_OUT,
        description="Direção da transação (CASH_IN ou CASH_OUT)",
    )
    amount: float = Field(..., gt=0, description="Valor da transação em BRL")
    description: Optional[str] = Field(default=None, description="Mensagem opcional de texto do Pix")
    engine: Literal["laya", "laya_tuned"] = Field(
        default="laya_tuned",
        description="Modelo de triagem: 'laya' (original, via Ollaya) ou 'laya_tuned' (retreinado para ameaças em Pix)",
    )
    enable_investigation: bool = Field(
        default=False,
        description="Se True, executa a investigação forense profunda com o Google Gemini. "
                    "Quando False (padrão em tráfego ao vivo e testes), economiza custos de IA.",
    )
    source_screen: Optional[str] = Field(
        default=None,
        description="Identificador da tela de origem ('journey', 'live', 'compare', etc.)",
    )


TraceStepId = Literal["amount_rule", "anti_evasion", "ollaya", "delivery"]
TraceStatus = Literal["pass", "skip", "detect", "error"]
DecidedBy = Literal["none", "skipped", "ollaya", "ollaya_fallback"]


class TraceStep(BaseModel):
    """Uma estação da jornada síncrona da mensagem dentro do gateway."""
    step: TraceStepId = Field(..., description="Identificador da estação")
    status: TraceStatus = Field(..., description="pass=passou, skip=não precisou, detect=detectou, error=falhou")
    ms: Optional[float] = Field(default=None, description="Tempo real medido na estação, em milissegundos")
    detail: Optional[str] = Field(default=None, description="Explicação curta do resultado")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Dados estruturados da estação (score, motivo, texto canônico...)")


class PixTransactionResponse(BaseModel):
    transaction_id: str
    status: str = Field(..., description="Status da transação (APPROVED ou BLOCKED)")
    amount: float
    description: Optional[str] = None
    original_masked: bool = False
    blocked: bool = Field(default=False, description="Indica se o Pix foi bloqueado por ameaça")
    engine: str = Field(default="laya", description="Modelo que fez a triagem desta mensagem")
    canonical_message: Optional[str] = Field(default=None, description="Texto desofuscado detectado pela camada anti-evasão")
    evasion_detected: bool = Field(default=False, description="Indica se houve tentativa de leetspeak ou ofuscação")
    detail: Optional[str] = None
    timing: Optional[dict] = Field(default=None, description="Métricas de latência de cada etapa em milissegundos")
    decided_by: DecidedBy = Field(default="none", description="Estação que determinou o desfecho da mensagem")
    trace: List[TraceStep] = Field(default_factory=list, description="Rastro das estações síncronas percorridas pela mensagem")
