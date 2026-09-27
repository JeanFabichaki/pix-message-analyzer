import re
import hashlib
import unicodedata
from typing import Tuple, Optional


EXPLICIT_THREAT_PATTERNS = [
    # Perseguição / Stalking / Emboscada
    (re.compile(r"\bvou\s+(te\s+)?(achar|pegar|encontrar|ca[çc]ar|buscar)\b", re.IGNORECASE), "Perseguição ou caçada (vou te achar/pegar)"),
    (re.compile(r"\b(te\s+pego|te\s+acho|te\s+encontro)\b", re.IGNORECASE), "Perseguição declarada"),
    (re.compile(r"\b(esperar|esperando|te\s+espero)\s+na\s+sa[ií]da\b", re.IGNORECASE), "Emboscada na saída"),
    (re.compile(r"\b(nem\s+que\s+seja\s+)?no\s+fim\s+do\s+mundo\b", re.IGNORECASE), "Perseguição implacável (no fim do mundo)"),
    (re.compile(r"\b(onde\s+quer\s+que|n[aã]o\s+adianta|n[aã]o\s+tem\s+como)\s+(voc[eê]\s+)?(se\s+esconder|fugir)\b", re.IGNORECASE), "Coação por encurralamento"),
    # Violência física / Agressão
    (re.compile(r"\b(vou\s+te|te)\s+(quebrar|arrebentar|matar|esquartejar|espancar)\b", re.IGNORECASE), "Ameaça de agressão física grave"),
    (re.compile(r"\b(voc[eê]\s+)?vai\s+morrer\b", re.IGNORECASE), "Ameaça de morte explícita"),
    (re.compile(r"\b(encher|dar)\s+de\s+porrada\b", re.IGNORECASE), "Ameaça de agressão física"),
    (re.compile(r"\beu\s+te\s+quebro\b", re.IGNORECASE), "Ameaça de violência física"),
    # Extorsão / Coação / Ameaça a família
    (re.compile(r"\b(passa|manda|transfere|paga|devolve|faz\s+o\s+pix|faz\s+um\s+pix)\b.*(ou|sen[aã]o|caso contr[aá]rio)\b.*(vai ver|acontece|sofrer|morrer|apanhar|quebro|mato|arrepender|consequ[eê]ncias)", re.IGNORECASE), "Extorsão sob coação ou chantagem"),
    (re.compile(r"\bse\s+n[aã]o\s+(me\s+)?(pagar|mandar|transferir|devolver)\b.*(vai|sofrer|morrer|quebro|arrepender|pegar)", re.IGNORECASE), "Extorsão condicional violenta"),
    (re.compile(r"\b(voc[eê]\s+)?vai\s+ver\s+(o\s+que\s+acontece|com\s+quantos\s+paus)\b", re.IGNORECASE), "Intimidação e ameaça velada (vai ver o que acontece)"),
    (re.compile(r"\b(fam[ií]lia|filhos?|m[aã]e|esposa)\s+vai\s+(sofrer|pagar|morrer)\b", re.IGNORECASE), "Ameaça contra familiares"),
    (re.compile(r"\b(vai|vai\s+se)\s+arrepender\b", re.IGNORECASE), "Intimidação e ameaça de represália"),
    # Sextorsão / Chantagem de exposição
    (re.compile(r"\b(vazar|espalhar|mandar|publicar)\b.*(fotos?|v[ií]deos?|nudes?|conversas?)\b", re.IGNORECASE), "Sextorsão ou chantagem de exposição digital"),
    (re.compile(r"\b(fotos?|v[ií]deos?|nudes?)\b.*(grupo\s+d[ao]|internet|rede\s+social|todos\s+verem)\b", re.IGNORECASE), "Ameaça de exposição íntima vexatória"),
    # Dano patrimonial / Incêndio
    (re.compile(r"\b(botar|tocar|atear|tac[aá]r)\s+fogo\b|amanhece\s+(pegando\s+fogo|depenad[ao]|destru[ií]d[ao])\b", re.IGNORECASE), "Ameaça de depredação / dano patrimonial"),
    # Falso sequestro / Cárcere
    (re.compile(r"\b(estamos\s+com\s+su[ao]|sequestr|c[aá]rcere)\b.*(filh[ao]|esposa|m[aã]e|irm[aã])\b", re.IGNORECASE), "Extorsão mediante falso sequestro"),
]


def check_explicit_threat_patterns(text: str) -> Tuple[bool, Optional[str]]:
    """Identifica em menos de 0.01ms padrões inequívocos de ameaça física, perseguição ou extorsão."""
    if not text:
        return False, None
    norm = normalize_threat_text(text)
    for pattern, desc in EXPLICIT_THREAT_PATTERNS:
        if pattern.search(text) or pattern.search(norm):
            return True, desc
    return False, None


def normalize_threat_text(text: str) -> str:
    """Normaliza mensagens de texto para comparação determinística de ameaças.
    - Converte para minúsculas
    - Remove diacríticos e acentos (NFKD)
    - Remove caracteres especiais não alfanuméricos supérfluos
    - Colapsa múltiplos espaços
    """
    if not text:
        return ""
    # 1. Lowercase e strip
    t = text.strip().lower()
    # 2. Decompor diacríticos e remover marcas de acento
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    # 3. Substituir pontuações e símbolos por espaços
    t = re.sub(r"[^\w\s]", " ", t)
    # 4. Colapsar espaços múltiplos
    t = re.sub(r"\s+", " ", t).strip()
    return t


def compute_threat_hash(normalized_text: str) -> str:
    """Calcula o hash SHA-256 de 64 caracteres do texto normalizado."""
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()

