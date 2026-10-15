"""Dublês de teste. O OllayaClient de produção sempre chama o serviço real; os testes injetam estes no interceptor."""
from common.schemas.threat import OllayaClassificationResult
from common.utils.normalizer import check_explicit_threat_patterns


class HeuristicOllaya:
    """Classifica com a lista de padrões explícitos. Só para testes."""

    model = "fake-heuristic"
    base_url = "fake"

    async def classify(self, text: str) -> OllayaClassificationResult:
        if not text or not text.strip():
            return OllayaClassificationResult(is_threat=False, score=0.0, model=self.model, detail="Mensagem vazia")
        is_threat, _ = check_explicit_threat_patterns(text)
        return OllayaClassificationResult(
            is_threat=is_threat,
            score=0.95 if is_threat else 0.05,
            category="ameaca_ou_extorsao" if is_threat else "benigno",
            model=self.model,
        )


class FakeGeminiAnalyzer:
    """Dublê do Gemini para cenários de teste controlados."""

    async def analyze(self, text: str):
        from common.schemas.threat import GeminiThreatAnalysis

        return GeminiThreatAnalysis(
            is_valid_threat=True,
            criticidade="ALTA",
            categoria="stalking_perseguicao",
            resumo_analise="Detectada ameaça em teste de unidade",
            acao_imediata_recomendada=True,
            bypassed=False,
        )

