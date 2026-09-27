from typing import Optional
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


class PixTransactionResponse(BaseModel):
    transaction_id: str
    status: str = Field(..., description="Status da transação (APPROVED, REJECTED_BLOCKED, etc)")
    amount: float
    description: Optional[str] = None
    original_masked: bool = False
    canonical_message: Optional[str] = Field(default=None, description="Texto desofuscado detectado pela camada anti-evasão")
    evasion_detected: bool = Field(default=False, description="Indica se houve tentativa de leetspeak ou ofuscação")
    detail: Optional[str] = None
    timing: Optional[dict] = Field(default=None, description="Métricas de latência de cada etapa em milissegundos")
