import re
from typing import Optional


# 1. CPF formatado: ex: 123.456.789-00
CPF_FORMATTED_REGEX = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")

# 2. Telefones brasileiros com DDD e celulares (inclui formato 11 dígitos com DDD, com ou sem +55 / parênteses / traços)
PHONE_REGEX = re.compile(
    r"(?<!\w)(?:\+?55\s?)?(?:\([1-9]{2}\)\s?|[1-9]{2}[\s-]?)?9\d{4}[-\s]?\d{4}(?!\w)|"
    r"(?<!\w)(?:\+?55\s?)?(?:\([1-9]{2}\)\s?|[1-9]{2}[\s-]?)?[2-5]\d{3}[-\s]?\d{4}(?!\w)"
)

# 3. CPF de 11 dígitos brutos isolados (sem formatação)
CPF_RAW_REGEX = re.compile(r"(?<!\d)\d{11}(?!\d)")

# 4. E-mail (ex: vitima@empresa.com.br, criminoso_pix@gmail.com)
EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

# 5. Chave Pix aleatória (UUIDv4)
UUID_PIX_REGEX = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

# 6. Agência e conta bancária padrão (ex: ag 1234 cc 12345-6, ag: 0001 c/c: 123456-7)
BANK_ACCOUNT_REGEX = re.compile(
    r"\b(?:ag(?:[eê]ncia)?[:\s]*\d{1,5})[\s,]+(?:c(?:onta)?[:\s/]*\d{4,10}-?[0-9xX]?)\b",
    re.IGNORECASE,
)


def mask_pii(text: str) -> str:
    """Mascara formatos conhecidos de dados pessoais, chaves Pix e contas bancárias."""
    # 1. Agência / conta bancária
    t = BANK_ACCOUNT_REGEX.sub("[DADO_BANCARIO_OCULTO]", text)

    # 2. E-mails
    t = EMAIL_REGEX.sub("[EMAIL_OCULTO]", t)

    # 3. UUIDs / Chaves aleatórias Pix
    t = UUID_PIX_REGEX.sub("[CHAVE_PIX_OCULTA]", t)

    # 4. CPFs formatados (000.000.000-00)
    t = CPF_FORMATTED_REGEX.sub("[CPF_OCULTO]", t)

    # 5. Telefones celulares e fixos com DDD ou formatação
    t = PHONE_REGEX.sub("[TEL_OCULTO]", t)

    # 6. CPFs de 11 dígitos brutos isolados
    return CPF_RAW_REGEX.sub("[CPF_OCULTO]", t)


def anonymize_text(text: Optional[str]) -> str:
    """Mascara identificadores e normaliza espaços para o prompt forense."""
    return re.sub(r"\s+", " ", mask_pii(text or "")).strip()
