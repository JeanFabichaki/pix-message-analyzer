import re
import unicodedata
from typing import Tuple


# Mapeamento abrangente de leetspeak e caracteres visuais semelhantes para o português
LEET_CHAR_MAP = {
    # Vogal A
    "4": "a",
    "@": "a",
    "ª": "a",
    "/\\": "a",
    "^": "a",
    # Vogal E
    "3": "e",
    "€": "e",
    "&": "e",
    # Vogal I
    "1": "i",
    "!": "i",
    "|": "i",
    # Vogal O
    "0": "o",
    "()": "o",
    "[]": "o",
    # Vogal U
    "µ": "u",
    "v": "u",  # em contextos específicos ou tratado com cuidado
    # Consoante S
    "5": "s",
    "$": "s",
    "§": "s",
    # Consoante T
    "7": "t",
    "+": "t",
    # Consoante B
    "8": "b",
    # Consoante Z
    "2": "z",
}

# Caracteres invisíveis (zero-width, soft hyphens, etc.)
INVISIBLE_CHARS = [
    "\u200b",  # zero-width space
    "\u200c",  # zero-width non-joiner
    "\u200d",  # zero-width joiner
    "\u2060",  # word joiner
    "\ufeff",  # zero-width no-break space
    "\u00ad",  # soft hyphen
    "\u200e",  # left-to-right mark
    "\u200f",  # right-to-left mark
]

# Regexes para proteção de dados sensíveis e estruturados (PII e formatos padrão brasileiros).
# Pontos, traços, barras e parênteses legítimos em CPF, CNPJ, telefone, e-mail e chave Pix
# NÃO devem ser considerados evasão/disfarce e devem ser preservados intactos para Model Armor e Cloud DLP.
CPF_FORMATTED_REGEX = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
CNPJ_FORMATTED_REGEX = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
PHONE_REGEX = re.compile(
    r"(?<!\w)(?:\+?55\s*)?(?:\([1-9]{2}\)\s*|[1-9]{2}[\s-]?)?"
    r"(?:9[.\s-]?\d{4}[.\s-]?\d{4}|[2-5]\d{3}[.\s-]?\d{4})(?!\w)"
)
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
UUID_PIX_REGEX = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
BANK_ACCOUNT_REGEX = re.compile(
    r"\b(?:ag(?:[eê]ncia)?[:\s]*\d{1,5})[\s,]+(?:c(?:onta)?[:\s/]*\d{4,10}-?[0-9xX]?)\b",
    re.IGNORECASE,
)

PROTECT_PATTERNS = [
    CPF_FORMATTED_REGEX,
    CNPJ_FORMATTED_REGEX,
    EMAIL_REGEX,
    UUID_PIX_REGEX,
    PHONE_REGEX,
    BANK_ACCOUNT_REGEX,
]


def _make_placeholder(idx: int) -> str:
    """Gera marcadores alfabéticos unificados como PROTECTEDTOKENA, evitando transições de caixa ou leet."""
    chars = []
    n = idx
    while True:
        chars.append(chr(ord("A") + (n % 26)))
        n //= 26
        if n == 0:
            break
    return "PROTECTEDTOKEN" + "".join(reversed(chars))


def deobfuscate_text(text: str) -> Tuple[str, bool]:
    """Decodifica e desofusca texto para forma canônica legível em português.
    Retorna uma tupla: (texto_canonico, houve_tentativa_de_evasao).
    
    Técnicas tratadas:
    1. Preservação de PII estruturada (CPF, telefone com DDD, CNPJ, e-mail) para DLP/Armor.
    2. Remoção de caracteres invisíveis e zero-width.
    3. Detecção de spongecase / alternância artificial de maiúsculas.
    4. Decodificação de Leetspeak (ex: 0->o, 3->e, 4->a, @->a, $->s, 1->i, 7->t).
    5. Remoção de separadores intrassilábicos (ex: v.o.u -> vou, v_o_u -> vou).
    6. Junção de letras isoladas separadas por espaços (ex: v o u   t e   p e g a r -> vou te pegar).
    7. Colapso de repetições exageradas de caracteres preservando dígrafos do português (rr, ss).
    8. Normalização Unicode de acentos e diacríticos.
    """
    if not text or not text.strip():
        return "", False

    t = text
    evasion_detected = False

    # 0. Extrai e protege formatos estruturados legítimos de PII (CPF, CNPJ, telefone, e-mail, chaves Pix)
    # para evitar que pontos, traços e parênteses legítimos sejam removidos ou distorçam a detecção de evasão.
    all_matches = []
    for pattern in PROTECT_PATTERNS:
        for m in pattern.finditer(t):
            all_matches.append((m.start(), m.end(), m.group(0)))
    all_matches.sort(key=lambda x: (x[0], -x[1]))

    filtered_matches = []
    last_end = -1
    for start, end, match_str in all_matches:
        if start >= last_end:
            filtered_matches.append((start, end, match_str))
            last_end = end

    protected_map = {}
    for i, (start, end, match_str) in enumerate(reversed(filtered_matches)):
        token = _make_placeholder(len(filtered_matches) - 1 - i)
        protected_map[token] = match_str
        t = t[:start] + token + t[end:]

    # 1. Limpeza de caracteres invisíveis
    for inv in INVISIBLE_CHARS:
        if inv in t:
            t = t.replace(inv, "")
            evasion_detected = True

    # 2. Detecção de alternância excessiva de caixa (spongecase / leetcase: ex: "vOuTePeGaR" ou "pEgAr")
    # Considera apenas caracteres alfabéticos para não disparar falso positivo em pontuações, aspas ou parênteses
    words = t.split()
    for w in words:
        letters = [c for c in w if c.isalpha()]
        if len(letters) >= 3:
            transitions = sum(1 for i in range(len(letters) - 1) if letters[i].isupper() != letters[i + 1].isupper())
            if transitions >= 2:  # ex: vOu -> 2 transições
                evasion_detected = True
                break

    # 3. Tratamento de separadores intrassilábicos (ex: v.o.u, v_o_u, v-o-u, v*o*u)
    # Separadores múltiplos entre palavras
    t_multi = re.sub(r"[\._\-\*\/\~]{2,}", " ", t)
    if t_multi != t:
        t = t_multi
        evasion_detected = True

    # Separador único inserido dentro de palavras (sem espaço depois, entre caracteres alfanuméricos)
    if re.search(r"(?<=[a-zA-Z0-9])[\._\-\*\/\~](?=[a-zA-Z0-9])", t):
        t = re.sub(r"(?<=[a-zA-Z0-9])[\._\-\*\/\~](?=[a-zA-Z0-9])", "", t)
        evasion_detected = True

    # 4. Detecção e colapso de repetições exageradas (3 ou mais iguais: "voooou", "pegaaaar", "morrrra")
    if re.search(r"(.)\1{2,}", t, flags=re.IGNORECASE):
        evasion_detected = True
        # Preserva dígrafos legítimos entre vogais no português (rr e ss: "morra", "passa", "isso")
        t = re.sub(r"(?<=[aeiouAEIOU])([rsRS])\1{2,}(?=[aeiouAEIOU])", r"\1\1", t)
        # Demais repetições colapsam para 1 único caractere
        t = re.sub(r"(.)\1{2,}", r"\1", t)

    # 5. Letras isoladas separadas por espaços (ex: "v o u   t e   p e g a r" ou "p.a.g.u.e")
    if re.search(r"\b([a-zA-Z]\s+){2,}[a-zA-Z]\b", t):
        evasion_detected = True
        # Se houver múltiplos espaços entre grupos, preserva as fronteiras
        parts = re.split(r"\s{2,}", t)
        joined_parts = []
        for part in parts:
            joined_part = re.sub(r"\b([a-zA-Z]\s+)+[a-zA-Z]\b", lambda m: m.group(0).replace(" ", ""), part)
            joined_parts.append(joined_part)
        t = " ".join(joined_parts)

    # 6. Decodificação de Leetspeak e substituições visuais
    t_lower = t.lower()

    # Símbolos compostos
    if "()" in t_lower or "[]" in t_lower:
        t_lower = t_lower.replace("()", "o").replace("[]", "o")
        evasion_detected = True

    leet_map = {
        "4": "a",
        "@": "a",
        "ª": "a",
        "3": "e",
        "€": "e",
        "1": "i",
        "!": "i",
        "|": "i",
        "0": "o",
        "5": "s",
        "$": "s",
        "§": "s",
        "7": "t",
        "+": "t",
        "8": "b",
        "2": "z",
    }

    # Substitui leetspeak token a token, preservando números puros legítimos (ex: "50", "100.00", "(11)")
    tokens = t_lower.split()
    processed_tokens = []
    for tok in tokens:
        # Se for token protegido de PII, preserva diretamente sem alteração
        if any(tok.startswith(k.lower()) for k in protected_map):
            processed_tokens.append(tok)
            continue

        # Números puros (mesmo com pontuação externa como "(11)" ou "50,") não são leetspeak
        core_num = tok.strip("()[]\"'\u201c\u201d\u2018\u2019,.?!;:")
        if re.match(r"^\d+([.,]\d+)?$", core_num):
            processed_tokens.append(tok)
            continue

        # Horários e unidades legítimas (ex: "18h", "10kg", "2x") não são leetspeak
        if re.match(r"^\d+[a-z]{1,3}$", core_num):
            processed_tokens.append(tok)
            continue

        # Pontuação final é pontuação, não leetspeak (ex: "festa!" não vira "festai")
        trailing_match = re.search(r"[!?.,;:]+$", tok)
        trailing = trailing_match.group(0) if trailing_match else ""
        core = tok[: len(tok) - len(trailing)] if trailing else tok

        # Se tiver símbolos leet ou números misturados com letras (ex: "v0u", "p4gu3", "m3")
        new_tok = []
        token_modified = False
        for char in core:
            if char in leet_map:
                new_tok.append(leet_map[char])
                token_modified = True
            else:
                new_tok.append(char)

        if token_modified:
            evasion_detected = True
        processed_tokens.append("".join(new_tok) + trailing)

    t = " ".join(processed_tokens)

    # 7. Normalização Unicode de acentos e diacríticos (ortografia padrão, não conta como evasão)
    t_norm = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t_norm if not unicodedata.combining(c))

    # 8. Remoção de pontuações residuais e colapso de espaços
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    # 9. Restauração das entidades estruturadas protegidas com sua formatação original
    for token, original in protected_map.items():
        t = re.sub(re.escape(token), lambda _: original, t, flags=re.IGNORECASE)

    return t, evasion_detected
