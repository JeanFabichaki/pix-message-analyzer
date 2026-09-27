import pytest
from common.utils.deobfuscator import deobfuscate_text
from common.schemas.pix import PixTransactionRequest
from common.config.settings import settings
from tests.modules import PixInterceptor, OllayaClient


def test_deobfuscator_leetspeak_variants():
    """Valida desofuscação de números e caracteres leetspeak comuns."""
    cases = [
        ("v0u t3 p3g4r n4 s41d4 d0 tr4b4lh0", "vou te pegar na saida do trabalho"),
        ("p4gu3 l0g0 s3u v4g4bund0", "pague logo seu vagabundo"),
        ("vOu Te PeGaR nA sAiDa", "vou te pegar na saida"),
        ("m3 p@g4 h0j3", "me paga hoje"),
        ("v0u m4t4r v0c3", "vou matar voce"),
    ]
    for obfuscated, expected in cases:
        clean, detected = deobfuscate_text(obfuscated)
        assert detected is True, f"Deveria detectar evasão em: {obfuscated}"
        assert clean == expected, f"Esperado '{expected}', obtido '{clean}'"


def test_deobfuscator_separators_and_spaces():
    """Valida desofuscação de pontuação intrassilábica e espaços entre letras."""
    cases = [
        ("v.o.u  t.e  p.e.g.a.r", "vou te pegar"),
        ("v_o_u  t_e  p_e_g_a_r", "vou te pegar"),
        ("v-o-u  t-e  p-e-g-a-r", "vou te pegar"),
        ("v o u  t e  p e g a r", "vou te pegar"),
        ("p.a.g.u.e  a.g.o.r.a", "pague agora"),
    ]
    for obfuscated, expected in cases:
        clean, detected = deobfuscate_text(obfuscated)
        assert detected is True, f"Deveria detectar evasão em: {obfuscated}"
        assert clean == expected, f"Esperado '{expected}', obtido '{clean}'"


def test_deobfuscator_repeated_characters():
    """Valida colapso de caracteres exageradamente repetidos."""
    cases = [
        ("vooooou teeeee pegaaaarrrr", "vou te pegar"),
        ("pagueeee logoooo", "pague logo"),
        ("morrrrraaaaa", "morra"),
    ]
    for obfuscated, expected in cases:
        clean, detected = deobfuscate_text(obfuscated)
        assert detected is True, f"Deveria detectar evasão em: {obfuscated}"
        assert clean == expected, f"Esperado '{expected}', obtido '{clean}'"


def test_deobfuscator_clean_text_untouched():
    """Valida que texto normal sem evasão não tem flag ativada indevidamente."""
    clean, detected = deobfuscate_text("Pagamento do café de hoje com a equipe")
    assert detected is False
    assert clean == "pagamento do cafe de hoje com a equipe"

    # Frases comuns legítimas com números não devem ser tratadas como leetspeak indevido
    clean2, detected2 = deobfuscate_text("Pix de 50 reais referente ao churrasco")
    assert clean2 == "pix de 50 reais referente ao churrasco"


def test_deobfuscator_complex_and_zero_width():
    """Valida evasão mista combinando zero-width spaces, leetspeak e separadores."""
    # Zero-width spaces intercalados
    zw_text = "v\u200bo\u200du\u200b t\u200be\u200b p\u200be\u200bg\u200ba\u200br"
    clean_zw, detected_zw = deobfuscate_text(zw_text)
    assert detected_zw is True
    assert clean_zw == "vou te pegar"

    # Spongecase (alternância intencional de maiúsculas/minúsculas para quebrar tokenizador)
    sponge_text = "vOu Te PeGaR nA sAiDa Do TrAbAlHo"
    clean_sp, detected_sp = deobfuscate_text(sponge_text)
    assert detected_sp is True
    assert clean_sp == "vou te pegar na saida do trabalho"

    # Combinação de leet + separadores + repetição (3 ou mais dígitos/letras repetidas)
    combo_text = "v.0.0.0.u  t_3_3_3  p-3-g-4-r"
    clean_combo, detected_combo = deobfuscate_text(combo_text)
    assert detected_combo is True
    assert clean_combo == "vou te pegar"


@pytest.mark.asyncio
async def test_interceptor_anti_bypass_detection():
    """Valida que o interceptor detecta evasão, desofusca e mascara ameaça com sucesso."""
    class MockOllayaClient(OllayaClient):
        async def classify(self, text: str):
            # O Ollaya recebe o texto canônico já desofuscado!
            from common.schemas.threat import OllayaClassificationResult
            if "vou te pegar na saida do trabalho" in text:
                return OllayaClassificationResult(
                    is_threat=True,
                    score=0.95,
                    category="violencia_fisica",
                    model="laya:multilingual",
                )
            return OllayaClassificationResult(
                is_threat=False,
                score=0.01,
                model="laya:multilingual",
            )

    interceptor = PixInterceptor(
        ollaya=MockOllayaClient(use_mock=False),
        threat_intel=None,
    )

    tx = PixTransactionRequest(
        transaction_id="tx_evasion_999",
        sender_id="usr_hacker_01",
        sender_cpf="11122233344",
        receiver_id="usr_victim_01",
        receiver_cpf="55566677788",
        amount=0.50,
        description="v0u t3 p3g4r n4 s41d4 d0 tr4b4lh0",
    )

    result = await interceptor.inspect_and_filter(tx)

    # 1. Deve ser mascarada
    assert result.is_masked is True
    assert result.message == settings.PIX_MASKED_MESSAGE

    # 2. Deve conter dados anti-evasão
    assert result.evasion_detected is True
    assert result.canonical_message == "vou te pegar na saida do trabalho"

    # 3. Suporte a unpack tradicional
    msg, masked = result
    assert masked is True
    assert msg == settings.PIX_MASKED_MESSAGE
