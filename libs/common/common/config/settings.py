import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Banco de Dados
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pix_guard_db"

    # Regras de Negócio do Gateway
    PIX_THRESHOLD_AMOUNT_BRL: float = 10.00
    PIX_MASKED_MESSAGE: str = "Mensagem retida por conter conteúdo inadequado sob análise de segurança."

    # Ollaya Decision Model Server (ollaya.dev)
    OLLAYA_BASE_URL: str = "http://localhost:11435"
    OLLAYA_CLUSTER_URLS: str = ""
    OLLAYA_MODEL: str = "laya:multilingual"
    OLLAYA_TIMEOUT_SECONDS: float = 25.0

    # Laya retreinado nativo no Ollaya (Pix: ameaças e extorsão)
    LAYA_TUNED_BASE_URL: str = "http://localhost:11435"
    LAYA_TUNED_CLUSTER_URLS: str = ""
    LAYA_TUNED_MODEL: str = "laya:pix-threats"


    # Dados de teste da página "Comparar" (montados em /data no container do gateway)
    BENCHMARK_DATA_DIR: str = "/data"


    # Google Gemini API
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    MOCK_GEMINI: bool = False

    # Tarifas de Custo do Gemini (em USD por 1M de tokens) e Câmbio
    GEMINI_PROMPT_RATE_PER_1M_USD: float = 0.10      # $0.10 por 1M de tokens de entrada (Gemini 2.5 Flash)
    GEMINI_COMPLETION_RATE_PER_1M_USD: float = 0.40  # $0.40 por 1M de tokens de saída (Gemini 2.5 Flash)
    USD_TO_BRL_RATE: float = 5.70                    # Cotação estimada USD -> BRL

    # Endpoints Internos
    USER_SERVICE_URL: str = "http://localhost:8002"
    GEMINI_AGENT_URL: str = "http://localhost:8003"

    # Limite de Ameaças para Bloqueio
    THREAT_BLOCK_LIMIT: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
