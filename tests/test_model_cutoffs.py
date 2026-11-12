"""Mesma régua de decisão para comparar modelos original e treinado."""
import pytest

from tests.modules import OllayaClient, ollaya_client, ollaya_tuned_client


def test_gateway_models_share_cutoff():
    assert ollaya_client.threat_threshold == ollaya_tuned_client.threat_threshold == 0.40


@pytest.mark.asyncio
@pytest.mark.parametrize("score,expected", [(0.3999, False), (0.40, True), (0.52, True)])
@pytest.mark.parametrize("model", ["laya:multilingual", "laya-rl-agent"])
async def test_default_decomposed_cutoff_boundary(model, score, expected):
    client = OllayaClient(model=model, decomposed=True)

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"model": model, "answers": {
                key: {"choice": "safe", "probabilities": {"threat": score, "safe": 1 - score}}
                for key in ("ameaca_violencia", "extorsao_chantagem", "coercao_financeira")
            }}

    class HttpClient:
        async def post(self, *args, **kwargs):
            return Response()

    client._get_client = lambda: HttpClient()
    result = await client.classify("Mensagem sintética para validar o corte")
    assert result.is_threat is expected
    assert result.score == score
