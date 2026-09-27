import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func

from common.config.settings import settings
from common.database.models import User, UserStatus, ThreatLog, TransactionDirection
from common.schemas.pix import PixTransactionRequest
from common.schemas.threat import GeminiThreatAnalysis
from tests.modules import (
    UserService,
    JevClient,
    InvestigationClient,
    PixInterceptor,
    GeminiThreatAnalyzer,
    record_and_evaluate_limit,
    UserClient,
)


@pytest.mark.asyncio
async def test_scenario_1_amount_above_threshold():
    """Cenário 1: Valor Acima do Limite (amount: 50.00, texto ameaçador).
    Não deve acionar JEV nem Gemini; mensagem deve ser preservada.
    """
    jev = JevClient(use_mock=True)
    investigation = InvestigationClient()
    interceptor = PixInterceptor(jev=jev, investigation=investigation)

    tx = PixTransactionRequest(
        transaction_id="tx_test_01",
        sender_id="usr_abc123",
        sender_cpf="12345678901",
        receiver_id="usr_xyz789",
        receiver_cpf="98765432100",
        direction=TransactionDirection.CASH_OUT,
        amount=50.00,
        description="Vou te achar na saida do trabalho",
    )

    final_msg, was_masked = await interceptor.inspect_and_filter(tx)

    assert was_masked is False
    assert final_msg == "Vou te achar na saida do trabalho"


@pytest.mark.asyncio
async def test_scenario_2_blank_message():
    """Cenário 2: Mensagem em Branco (amount: 1.00, texto vazio).
    Não aciona triagem; transação é processada normalmente.
    """
    jev = JevClient(use_mock=True)
    investigation = InvestigationClient()
    interceptor = PixInterceptor(jev=jev, investigation=investigation)

    tx = PixTransactionRequest(
        transaction_id="tx_test_02",
        sender_id="usr_abc123",
        sender_cpf="12345678901",
        receiver_id="usr_xyz789",
        receiver_cpf="98765432100",
        direction=TransactionDirection.CASH_OUT,
        amount=1.00,
        description="   ",
    )

    final_msg, was_masked = await interceptor.inspect_and_filter(tx)

    assert was_masked is False
    assert final_msg == "   "


@pytest.mark.asyncio
async def test_scenario_3_benign_message():
    """Cenário 3: Mensagem Benigna (amount: 5.00, 'Pagamento do cafe').
    JEV retorna is_threat=False; mensagem é preservada.
    """
    jev = JevClient(use_mock=True)
    investigation = InvestigationClient()
    interceptor = PixInterceptor(jev=jev, investigation=investigation)

    tx = PixTransactionRequest(
        transaction_id="tx_test_03",
        sender_id="usr_abc123",
        sender_cpf="12345678901",
        receiver_id="usr_xyz789",
        receiver_cpf="98765432100",
        direction=TransactionDirection.CASH_OUT,
        amount=5.00,
        description="Pagamento do cafe",
    )

    final_msg, was_masked = await interceptor.inspect_and_filter(tx)

    assert was_masked is False
    assert final_msg == "Pagamento do cafe"


@pytest.mark.asyncio
async def test_scenario_4_threat_detected_under_5_times(db_session):
    """Cenário 4: Ameaça Detectada (< 5x) (amount: 0.05, 'Vou te achar').
    JEV detecta; mensagem é mascarada; Gemini avalia e registra; usuário permanece ACTIVE.
    """
    user_id = "usr_abc123"
    jev = JevClient(use_mock=True)
    analyzer = GeminiThreatAnalyzer()

    # 1. Triagem JEV
    tx = PixTransactionRequest(
        transaction_id="tx_test_04",
        sender_id=user_id,
        sender_cpf="12345678901",
        receiver_id="usr_xyz789",
        receiver_cpf="98765432100",
        direction=TransactionDirection.CASH_OUT,
        amount=0.05,
        description="Vou te pegar na saida do trabalho se nao me responder",
    )

    jev_res = await jev.classify(tx.description)
    assert jev_res.is_threat is True

    # 2. Investigação semântica Gemini
    analysis: GeminiThreatAnalysis = await analyzer.analyze(tx.description)
    assert analysis.is_valid_threat is True
    assert analysis.criticidade in ["ALTA", "CRITICA", "MEDIA"]

    # 3. Registro e avaliação de limite (1ª infração)
    threat_log = ThreatLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        transaction_id=tx.transaction_id,
        direction=tx.direction,
        original_message=tx.description,
        jev_score=jev_res.score,
        jev_category=jev_res.category,
        gemini_criticality=analysis.criticidade,
        gemini_category=analysis.categoria,
        gemini_rationale=analysis.resumo_analise,
    )

    # Mock user_client local para os testes in-memory
    user_svc = UserService(db_session)

    class MockUserClient:
        async def block_user(self, user_id, reason, total_threats, triggered_by_tx=None, details=None):
            from common.schemas.user import UserBlockRequest
            return await user_svc.block_user(
                user_id,
                UserBlockRequest(reason=reason, total_threats=total_threats, triggered_by_tx=triggered_by_tx)
            )

    total_threats, blocked = await record_and_evaluate_limit(
        user_id=user_id,
        threat_log=threat_log,
        user_client=MockUserClient(),
        session=db_session,
    )

    assert total_threats == 1
    assert blocked is False

    # Checa usuário no banco: deve continuar ACTIVE
    user = await user_svc.get_by_id(user_id)
    assert user.status == UserStatus.ACTIVE


@pytest.mark.asyncio
async def test_scenario_5_and_6_blocking_trigger_and_governance(db_session):
    """Cenário 5 e 6: Gatilho de Bloqueio (= 5x) e Governança no Gateway.
    Ao registrar a 5ª ameaça do mesmo sender_id, o status migra para BLOCKED_SUSPICIOUS.
    Na 6ª transação, o usuário bloqueado tem sua transferência rejeitada.
    """
    user_id = "usr_repeat_offender"
    user_svc = UserService(db_session)
    await user_svc.ensure_user(user_id=user_id, cpf_cnpj="99988877766", name="Infrator Reincidente")

    analyzer = GeminiThreatAnalyzer()

    class MockUserClient:
        async def block_user(self, user_id, reason, total_threats, triggered_by_tx=None, details=None):
            from common.schemas.user import UserBlockRequest
            return await user_svc.block_user(
                user_id,
                UserBlockRequest(reason=reason, total_threats=total_threats, triggered_by_tx=triggered_by_tx)
            )

    # Dispara 4 ameaças
    for i in range(1, 5):
        analysis = await analyzer.analyze("Vou te pegar na saida")
        threat_log = ThreatLog(
            id=str(uuid.uuid4()),
            user_id=user_id,
            transaction_id=f"tx_loop_{i}",
            direction=TransactionDirection.CASH_OUT,
            original_message="Vou te pegar na saida",
            jev_score=0.95,
            gemini_criticality=analysis.criticidade,
            gemini_category=analysis.categoria,
            gemini_rationale=analysis.resumo_analise,
        )
        total, blocked = await record_and_evaluate_limit(
            user_id=user_id,
            threat_log=threat_log,
            user_client=MockUserClient(),
            session=db_session,
        )
        assert total == i
        assert blocked is False

    # Usuário ainda deve estar ACTIVE após 4 ameaças
    user = await user_svc.get_by_id(user_id)
    assert user.status == UserStatus.ACTIVE

    # 5ª Ameaça: Gatilho de bloqueio!
    analysis = await analyzer.analyze("Vou te quebrar se nao me pagar")
    threat_log_5 = ThreatLog(
        id=str(uuid.uuid4()),
        user_id=user_id,
        transaction_id="tx_trigger_5",
        direction=TransactionDirection.CASH_OUT,
        original_message="Vou te quebrar se nao me pagar",
        jev_score=0.98,
        gemini_criticality=analysis.criticidade,
        gemini_category=analysis.categoria,
        gemini_rationale=analysis.resumo_analise,
    )
    total_5, blocked_5 = await record_and_evaluate_limit(
        user_id=user_id,
        threat_log=threat_log_5,
        user_client=MockUserClient(),
        session=db_session,
    )

    assert total_5 == 5
    assert blocked_5 is True

    # Verifica status atualizado no banco
    user = await user_svc.get_by_id(user_id)
    assert user.status == UserStatus.BLOCKED_SUSPICIOUS
