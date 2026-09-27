import json
import logging
import os
from typing import Optional
from common.config.settings import settings
from common.schemas.threat import GeminiThreatAnalysis

logger = logging.getLogger("gemini-agent.analyzer")


class GeminiThreatAnalyzer:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None, **kwargs):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self._client = None
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY não configurada. A API real do Google Gemini é obrigatória (mocks desativados)."
            )

        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            logger.info(f"Cliente Google GenAI inicializado com sucesso para o modelo {self.model_name}.")
        except Exception as e:
            logger.error(f"Não foi possível inicializar google.genai ({e}).")
            raise RuntimeError(f"Erro ao inicializar cliente Google GenAI: {e}") from e

    async def analyze(self, message: str) -> GeminiThreatAnalysis:
        """Executa a investigação semântica da mensagem exclusivamente via API real do Google Gemini."""
        if not message or not message.strip():
            return GeminiThreatAnalysis(
                is_valid_threat=False,
                criticidade="BAIXA",
                categoria="outros",
                resumo_analise="Mensagem vazia ou sem conteúdo semântico relevante.",
                acao_imediata_recomendada=False,
            )

        if not self._client:
            self._init_client()

        return await self._analyze_with_gemini(message)

    async def _analyze_with_gemini(self, message: str) -> GeminiThreatAnalysis:
        prompt = (
            "Você é um especialista em análise de ameaças e segurança bancária do Pix Guard. "
            "Avalie detalhadamente a mensagem enviada na transferência Pix a seguir quanto à presença de intimidação, "
            "extorsão, assédio, perseguição física ou violência. "
            "Retorne a análise estritamente estruturada conforme o esquema solicitado.\n\n"
            f"Mensagem sob investigação: \"{message}\""
        )

        try:
            config = {
                "response_mime_type": "application/json",
                "response_schema": GeminiThreatAnalysis,
            }
            logger.info(f"Chamando API real do Google Gemini ({self.model_name}) para análise semântica...")
            if hasattr(self._client, "aio") and hasattr(self._client.aio, "models"):
                response = await self._client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
            else:
                response = self._client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
            parsed_json = json.loads(response.text)
            logger.info(
                f"Análise estruturada do Gemini ({self.model_name}) concluída: "
                f"is_threat={parsed_json.get('is_valid_threat')}, "
                f"criticidade={parsed_json.get('criticidade')}, "
                f"categoria={parsed_json.get('categoria')}"
            )
            return GeminiThreatAnalysis(**parsed_json)
        except Exception as e:
            logger.error(f"Erro na chamada à API real do Google Gemini ({self.model_name}): {e}")
            raise RuntimeError(f"Falha na API do Google Gemini: {e}") from e

