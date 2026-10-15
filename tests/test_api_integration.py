import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from tests.modules import pix_gateway_app as gateway_app
from common.config.settings import settings


@pytest.mark.asyncio
async def test_gateway_endpoint_benign_transaction(db_session):
    """Valida o endpoint POST /pix/transactions do gateway para transação normal."""
    uid = uuid.uuid4().hex[:8]
    transport = ASGITransport(app=gateway_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "transaction_id": f"tx_api_01_{uid}",
            "sender_id": f"usr_fresh_{uid}",
            "sender_cpf": f"12{uid}",
            "receiver_id": "usr_xyz789",
            "receiver_cpf": "98765432100",
            "direction": "CASH_OUT",
            "amount": 5.0,
            "description": "Pagamento de almoco",
        }
        resp = await client.post("/pix/transactions", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "APPROVED"
        assert data["original_masked"] is False
        assert data["description"] == "Pagamento de almoco"


@pytest.mark.asyncio
async def test_gateway_endpoint_threat_masking(db_session, monkeypatch):
    """Valida o endpoint POST /pix/transactions do gateway com mascaramento imediato de ameaça."""
    from tests.fakes import HeuristicOllaya
    for route in gateway_app.routes:
        if getattr(route, "path", None) == "/pix/transactions":
            fake = HeuristicOllaya()
            monkeypatch.setattr(route.endpoint.__globals__["interceptor"], "ollaya", fake)
            monkeypatch.setattr(route.endpoint.__globals__["interceptor"], "ollaya_tuned", fake)
    uid = uuid.uuid4().hex[:8]
    transport = ASGITransport(app=gateway_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "transaction_id": f"tx_api_02_{uid}",
            "sender_id": f"usr_fresh_threat_{uid}",
            "sender_cpf": f"13{uid}",
            "receiver_id": "usr_xyz789",
            "receiver_cpf": "98765432100",
            "direction": "CASH_OUT",
            "amount": 0.50,
            "description": "Vou te pegar na saida do trabalho se nao me responder",
        }
        resp = await client.post("/pix/transactions", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "BLOCKED"
        assert data["blocked"] is True
        assert data["original_masked"] is False
        assert data["description"] == payload["description"]
