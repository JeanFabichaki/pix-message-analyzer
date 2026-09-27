import pytest
from common.utils.normalizer import normalize_threat_text, compute_threat_hash
from common.schemas.threat import ConfirmedThreatCreate, ThreatCheckResult
from common.schemas.pix import PixTransactionRequest
from common.config.settings import settings
from tests.modules import (
    ThreatIntelligenceRepository,
    PixInterceptor,
    ThreatIntelClient,
    OllayaClient,
)


def test_normalizer_and_hashing():
    """Valida que variações com acentos, maiúsculas e pontuação geram a mesma assinatura hash."""
    t1 = "Vou te pegar na saída do trabalho se não me responder!!!"
    t2 = "vou te pegar na saida do trabalho se nao me responder"
    t3 = "  VOU TE PEGAR NA SAÍDA DO TRABALHO SE NÃO ME RESPONDER...  "

    n1 = normalize_threat_text(t1)
    n2 = normalize_threat_text(t2)
    n3 = normalize_threat_text(t3)

    assert n1 == n2 == n3 == "vou te pegar na saida do trabalho se nao me responder"
    assert compute_threat_hash(n1) == compute_threat_hash(n2) == compute_threat_hash(n3)


@pytest.mark.asyncio
async def test_threat_intelligence_repository(db_session):
    """Valida gravação e verificação O(1) de ameaças confirmadas por Laya + Gemini."""
    repo = ThreatIntelligenceRepository(db_session)

    # 1. Grava ameaça confirmada
    threat_in = ConfirmedThreatCreate(
        raw_text="Vou te pegar na saida do trabalho se nao me responder",
        laya_score=0.7678,
        gemini_score=0.98,
        category="violencia_fisica",
        gemini_rationale="Ameaça explícita de emboscada e perseguição.",
    )
    saved = await repo.record_threat(threat_in)
    assert saved.occurrences_count == 1.0

    # 2. Consulta idêntica deve retornar match de alta velocidade
    res = await repo.check_threat("Vou te pegar na saída do trabalho se não me responder!!!")
    assert res.is_threat is True
    assert res.source == "threat_intel_hash_match"
    assert res.confidence >= 0.95

    # 3. Consulta de mensagem benigna não deve dar match
    res_clean = await repo.check_threat("Pagamento do café de hoje, obrigado")
    assert res_clean.is_threat is False

    # 4. Gravação recorrente incrementa contador
    updated = await repo.record_threat(threat_in)
    assert updated.occurrences_count == 2.0


@pytest.mark.asyncio
async def test_interceptor_fast_path_bypass(db_session):
    """Valida que o interceptor do Gateway prioriza o Threat Intel Cache antes de chamar o Laya."""
    repo = ThreatIntelligenceRepository(db_session)
    await repo.record_threat(
        ConfirmedThreatCreate(
            raw_text="Pague agora ou conto tudo pra sua esposa",
            laya_score=0.92,
            gemini_score=0.99,
            category="extorsao",
            gemini_rationale="Chantagem de difamação.",
        )
    )

    class MockThreatIntelClient:
        async def check(self, text: str):
            return await repo.check_threat(text)

    class FailingOllayaClient(OllayaClient):
        async def classify(self, text: str):
            # Se for chamado, falha o teste, pois o fast-path deveria ter dado bypass!
            raise RuntimeError("Laya não deveria ser chamado quando o Threat Intel Cache dá match!")

    interceptor = PixInterceptor(
        ollaya=FailingOllayaClient(use_mock=False),
        threat_intel=MockThreatIntelClient(),
    )

    tx = PixTransactionRequest(
        transaction_id="tx_fast_path_01",
        sender_id="usr_extortionist_01",
        sender_cpf="11122233344",
        receiver_id="usr_victim_01",
        receiver_cpf="55566677788",
        amount=5.00,
        description="Pague agora ou conto tudo pra sua esposa!!!",
    )

    masked_text, is_masked = await interceptor.inspect_and_filter(tx)
    assert is_masked is True
    assert masked_text == settings.PIX_MASKED_MESSAGE
