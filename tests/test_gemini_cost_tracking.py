import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from common.utils.cost_calculator import calculate_gemini_cost, estimate_text_tokens, get_model_rates
from common.schemas.threat import GeminiCostMetadata, GeminiThreatAnalysis
from common.database.models import ThreatLog, TransactionDirection, CriticalityLevel
from common.config.settings import settings
from tests.modules import gemini_agent_app, user_service_app, GeminiThreatAnalyzer


def test_cost_calculator_rates_and_calculation():
    """Valida o cálculo exato de custos em USD e BRL para diferentes modelos do Gemini."""
    p_rate, c_rate = get_model_rates("gemini-2.5-flash")
    assert p_rate == 0.10
    assert c_rate == 0.40

    # 1.000 prompt tokens + 500 completion tokens no Gemini 2.5 Flash
    # Custo esperado: (1000 * 0.10 + 500 * 0.40) / 1_000_000 = (100 + 200) / 1_000_000 = $0.000300
    meta = calculate_gemini_cost(
        model="gemini-2.5-flash",
        prompt_tokens=1000,
        completion_tokens=500,
        exchange_rate=5.70,
    )

    assert meta.model == "gemini-2.5-flash"
    assert meta.prompt_tokens == 1000
    assert meta.completion_tokens == 500
    assert meta.total_tokens == 1500
    assert meta.cost_usd == pytest.approx(0.0003, rel=1e-4)
    assert meta.cost_brl == pytest.approx(0.0003 * 5.70, rel=1e-4)
    assert meta.exchange_rate_brl == 5.70


def test_cost_calculator_gemini_pro():
    """Valida tarifas do Gemini Pro."""
    meta = calculate_gemini_cost(
        model="gemini-1.5-pro",
        prompt_tokens=2000,
        completion_tokens=1000,
        exchange_rate=5.50,
    )
    # Pro: $1.25 in / $5.00 out por 1M
    # Prompt: 2000 * 1.25 / 1M = 0.0025
    # Comp: 1000 * 5.00 / 1M = 0.0050
    # Total USD: 0.0075
    assert meta.cost_usd == pytest.approx(0.0075, rel=1e-4)
    assert meta.cost_brl == pytest.approx(0.0075 * 5.50, rel=1e-4)


def test_token_estimation_fallback():
    """Valida estimativa heurística de tokens caso a API não envie usage_metadata."""
    text = "Vou te pegar na saída se não me pagar agora mesmo com juros e correção"
    tokens = estimate_text_tokens(text)
    assert tokens > 0
    assert 12 <= tokens <= 35


@pytest.mark.asyncio
async def test_investigation_cost_tracking_in_endpoint():
    """Valida que o endpoint /investigate persiste e retorna metadados de custo do Gemini."""
    transport = ASGITransport(app=gemini_agent_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tx_id = f"tx_cost_test_{uuid.uuid4().hex[:8]}"
        payload = {
            "user_id": "usr_cost_01",
            "transaction_id": tx_id,
            "direction": "CASH_OUT",
            "text": "Paga o que deve ou mando a cobrança na sua porta",
            "history": ["primeiro aviso"],
        }
        resp = await client.post("/investigate", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert "cost" in data
        assert data["cost"] is not None
        assert "prompt_tokens" in data["cost"]
        assert "completion_tokens" in data["cost"]
        assert "total_tokens" in data["cost"]
        assert "cost_usd" in data["cost"]
        assert "cost_brl" in data["cost"]
        assert "model" in data["cost"]

        # Consulta endpoint por transação
        resp_tx = await client.get(f"/threats/tx/{tx_id}")
        assert resp_tx.status_code == 200
        data_tx = resp_tx.json()
        assert "cost" in data_tx
        assert data_tx["cost"]["model"] == data["cost"]["model"]


@pytest.mark.asyncio
async def test_user_service_audit_metrics_cost_aggregation(db_session):
    """Valida agregação de custos financeiros no /audit/metrics do user-service."""
    # Insere 2 registros com custos no banco
    t1 = ThreatLog(
        id=str(uuid.uuid4()),
        user_id="usr_abc123",
        transaction_id="tx_met_01",
        direction=TransactionDirection.CASH_OUT,
        original_message="Ameaça 1",
        gemini_criticality=CriticalityLevel.ALTA,
        gemini_category="extorsao",
        gemini_model="gemini-2.5-flash",
        prompt_tokens=400,
        completion_tokens=100,
        total_tokens=500,
        cost_usd=0.00008,
        cost_brl=0.000456,
    )
    t2 = ThreatLog(
        id=str(uuid.uuid4()),
        user_id="usr_abc123",
        transaction_id="tx_met_02",
        direction=TransactionDirection.CASH_OUT,
        original_message="Ameaça 2",
        gemini_criticality=CriticalityLevel.CRITICA,
        gemini_category="violencia_fisica",
        gemini_model="gemini-2.5-flash",
        prompt_tokens=600,
        completion_tokens=200,
        total_tokens=800,
        cost_usd=0.00014,
        cost_brl=0.000798,
    )
    db_session.add_all([t1, t2])
    await db_session.commit()

    transport = ASGITransport(app=user_service_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Sobrescreve get_db com db_session do teste
        from common.database.session import get_db
        user_service_app.dependency_overrides[get_db] = lambda: db_session

        resp = await client.get("/audit/metrics")
        assert resp.status_code == 200
        metrics = resp.json()

        assert "total_cost_usd" in metrics
        assert "total_cost_brl" in metrics
        assert "total_tokens" in metrics
        assert metrics["total_tokens"] >= 1300
        assert metrics["total_cost_usd"] >= 0.00022
        assert metrics["total_cost_brl"] >= 0.001254

        # Testa também o list_all_threats
        resp_threats = await client.get("/audit/threats")
        assert resp_threats.status_code == 200
        threats = resp_threats.json()
        assert len(threats) >= 2
        first = next(t for t in threats if t["transaction_id"] == "tx_met_01")
        assert first["gemini_model"] == "gemini-2.5-flash"
        assert first["total_tokens"] == 500
        assert first["cost_usd"] == pytest.approx(0.00008)

        user_service_app.dependency_overrides.clear()
