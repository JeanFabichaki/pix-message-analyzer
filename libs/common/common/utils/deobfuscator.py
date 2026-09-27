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


def deobfuscate_text(text: str) -> Tuple[str, bool]:
    """Decodifica e desofusca texto para forma canônica legível em português.
    Retorna uma tupla: (texto_canonico, houve_tentativa_de_evasao).
    
    Técnicas tratadas:
    1. Remoção de caracteres invisíveis e zero-width.
    2. Detecção de spongecase / alternância artificial de maiúsculas.
    3. Decodificação de Leetspeak (ex: 0->o, 3->e, 4->a, @->a, $->s, 1->i, 7->t).
    4. Remoção de separadores intrassilábicos (ex: v.o.u -> vou, v_o_u -> vou).
    5. Junção de letras isoladas separadas por espaços (ex: v o u   t e   p e g a r -> vou te pegar).
    6. Colapso de repetições exageradas de caracteres preservando dígrafos do português (rr, ss).
    7. Normalização Unicode de acentos e diacríticos.
    """
    if not text or not text.strip():
        return "", False

    t = text
    evasion_detected = False

    # 1. Limpeza de caracteres invisíveis
    for inv in INVISIBLE_CHARS:
        if inv in t:
            t = t.replace(inv, "")
            evasion_detected = True

    # 2. Detecção de alternância excessiva de caixa (spongecase / leetcase: ex: "vOuTePeGaR" ou "pEgAr")
    words = t.split()
    for w in words:
        if len(w) >= 3:
            transitions = sum(1 for i in range(len(w) - 1) if w[i].isupper() != w[i + 1].isupper())
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

    # Substitui leetspeak token a token, preservando números puros legítimos (ex: "50", "100.00")
    tokens = t_lower.split()
    processed_tokens = []
    for tok in tokens:
        # Se for um valor numérico puro (ex: "50", "10", "2.50", "1000"), preserva
        if re.match(r"^\d+([.,]\d+)?$", tok):
            processed_tokens.append(tok)
            continue

        # Se tiver símbolos leet ou números misturados com letras (ex: "v0u", "p4gu3", "m3")
        new_tok = []
        token_modified = False
        for char in tok:
            if char in leet_map:
                new_tok.append(leet_map[char])
                token_modified = True
            else:
                new_tok.append(char)

        if token_modified:
            evasion_detected = True
        processed_tokens.append("".join(new_tok))

    t = " ".join(processed_tokens)

    # 7. Normalização Unicode de acentos e diacríticos (ortografia padrão, não conta como evasão)
    t_norm = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t_norm if not unicodedata.combining(c))

    # 8. Remoção de pontuações residuais e colapso de espaços
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    return t, evasion_detected
