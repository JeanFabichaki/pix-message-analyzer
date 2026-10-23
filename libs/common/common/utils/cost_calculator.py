from typing import Optional, Tuple
from common.config.settings import settings
from common.schemas.threat import GeminiCostMetadata

# Tarifas oficiais da Google API por 1M de tokens (prompt <= 128k)
# Fonte: Google Cloud / Google AI Studio Pricing
MODEL_PRICING_TABLE = {
    "gemini-2.5-flash": {"prompt": 0.10, "completion": 0.40},
    "gemini-2.0-flash": {"prompt": 0.10, "completion": 0.40},
    "gemini-1.5-flash": {"prompt": 0.075, "completion": 0.30},
    "gemini-1.5-flash-8b": {"prompt": 0.0375, "completion": 0.15},
    "gemini-2.5-pro": {"prompt": 1.25, "completion": 5.00},
    "gemini-1.5-pro": {"prompt": 1.25, "completion": 5.00},
}


def get_model_rates(model_name: Optional[str] = None) -> Tuple[float, float]:
    """Retorna as tarifas (prompt_rate, completion_rate) em USD por 1M de tokens para o modelo especificado."""
    if model_name:
        clean_model = model_name.lower().strip()
        # Busca exata ou por prefixo (ex: gemini-2.5-flash-preview)
        for key, rates in MODEL_PRICING_TABLE.items():
            if clean_model.startswith(key):
                return rates["prompt"], rates["completion"]

    # Fallback para as tarifas configuradas em settings
    prompt_rate = getattr(settings, "GEMINI_PROMPT_RATE_PER_1M_USD", 0.10)
    completion_rate = getattr(settings, "GEMINI_COMPLETION_RATE_PER_1M_USD", 0.40)
    return prompt_rate, completion_rate


def estimate_text_tokens(text: Optional[str]) -> int:
    """Estimativa rápida de contagem de tokens para texto em português quando a API não retorna usage_metadata."""
    if not text or not text.strip():
        return 0
    words = text.strip().split()
    # Em média no Gemini para português: ~1.35 tokens por palavra ou 1 token a cada 3.6 caracteres
    by_words = int(len(words) * 1.35)
    by_chars = int(len(text) / 3.6)
    return max(1, (by_words + by_chars) // 2)


def calculate_gemini_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    prompt_rate: Optional[float] = None,
    completion_rate: Optional[float] = None,
    exchange_rate: Optional[float] = None,
) -> GeminiCostMetadata:
    """Calcula o custo em USD e BRL de uma chamada à API do Gemini com base na contagem de tokens."""
    default_p_rate, default_c_rate = get_model_rates(model)
    p_rate = prompt_rate if prompt_rate is not None else default_p_rate
    c_rate = completion_rate if completion_rate is not None else default_c_rate
    fx_rate = exchange_rate if exchange_rate is not None else getattr(settings, "USD_TO_BRL_RATE", 5.70)

    prompt_tokens = max(0, int(prompt_tokens or 0))
    completion_tokens = max(0, int(completion_tokens or 0))
    total_tokens = prompt_tokens + completion_tokens

    # Custo em USD: (tokens * taxa / 1.000.000)
    cost_prompt_usd = (prompt_tokens * p_rate) / 1_000_000.0
    cost_completion_usd = (completion_tokens * c_rate) / 1_000_000.0
    cost_usd = round(cost_prompt_usd + cost_completion_usd, 7)

    # Custo em BRL: USD * cotação
    cost_brl = round(cost_usd * fx_rate, 6)

    return GeminiCostMetadata(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        cost_brl=cost_brl,
        prompt_rate_per_1m=p_rate,
        completion_rate_per_1m=c_rate,
        exchange_rate_brl=fx_rate,
    )
