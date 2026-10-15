"""Valida o rastro (`trace`) e o campo `decided_by` devolvidos pelo gateway.

Cada caso pronto da interface de demonstração deve percorrer um caminho distinto.
"""
import pytest
from httpx import AsyncClient, ASGITransport

from common.database.models import TransactionDirection
from common.schemas.pix import PixTransactionRequest
from common.schemas.threat import OllayaClassificationResult
from tests.fakes import HeuristicOllaya
from tests.modules import PixInterceptor, pix_gateway_app


class ScriptedOllaya:
    """Ollaya com respostas roteirizadas (ameaça sutil ou indisponível)."""

    def __init__(self, threat: bool = False, fail: bool = False):
        self.threat = threat
        self.fail = fail
        self.model = "scripted"
        self.base_url = "stub"

    async def classify(self, text: str) -> OllayaClassificationResult:
        if self.fail:
            raise RuntimeError("Ollaya fora do ar")
        return OllayaClassificationResult(
            is_threat=self.threat,
            score=0.91 if self.threat else 0.04,
            category="ameaca_ou_extorsao" if self.threat else "benigno",
            model=self.model,
        )


def gateway_globals() -> dict:
    """Namespace do módulo main do pix-gateway (sys.modules['src.main'] é sobrescrito por outros serviços)."""
    for route in pix_gateway_app.routes:
        if getattr(route, "path", None) == "/pix/transactions":
            return route.endpoint.__globals__
    raise AssertionError("rota /pix/transactions não encontrada")


def make_tx(description, amount=1.0, tx_id="tx_trace"):
    return PixTransactionRequest(
        transaction_id=tx_id,
        sender_id="usr_abc123",
        sender_cpf="12345678901",
        receiver_id="usr_xyz789",
        receiver_cpf="98765432100",
        direction=TransactionDirection.CASH_OUT,
        amount=amount,
        description=description,
    )


def steps(res):
    return {s.step: s for s in res.trace}


def interceptor(ollaya=None):
    return PixInterceptor(ollaya=ollaya or HeuristicOllaya(), investigation=None)


@pytest.mark.asyncio
async def test_amount_above_limit_is_skipped():
    res = await interceptor().inspect_and_filter(make_tx("Vou te achar na saida do trabalho", amount=50.0))
    st = steps(res)
    assert res.decided_by == "skipped"
    assert res.is_masked is False
    assert st["amount_rule"].status == "skip"
    assert st["ollaya"].status == "skip"
    assert st["delivery"].status == "pass"


@pytest.mark.asyncio
async def test_blank_message_is_skipped():
    res = await interceptor().inspect_and_filter(make_tx("   "))
    assert res.decided_by == "skipped"
    assert steps(res)["amount_rule"].status == "skip"


@pytest.mark.asyncio
async def test_benign_message_passes_every_station():
    res = await interceptor().inspect_and_filter(
        make_tx("Amigo, quase morri de rir ontem na festa! Segue o valor da vaquinha")
    )
    st = steps(res)
    assert res.decided_by == "none"
    assert res.is_masked is False
    assert st["anti_evasion"].status == "pass"  # pontuação não é disfarce
    assert st["ollaya"].status == "pass"
    assert st["delivery"].status == "pass"


@pytest.mark.asyncio
async def test_threat_always_goes_to_ollaya():
    """Não há mais atalho por padrão/lista: toda mensagem analisada passa pela IA rápida."""
    res = await interceptor(ollaya=ScriptedOllaya(threat=True)).inspect_and_filter(
        make_tx("Vou te pegar na saida do trabalho se nao me responder")
    )
    st = steps(res)
    assert res.decided_by == "ollaya"
    assert res.is_masked is True
    assert "known_threat" not in st
    assert st["ollaya"].status == "detect"
    assert st["delivery"].status == "detect"


@pytest.mark.asyncio
async def test_obfuscated_message_shows_before_and_after():
    res = await interceptor().inspect_and_filter(
        make_tx("v.0.u  t_3  p_3_g_4_r  n4  s41d4  d0  tr4b4lh0  s3  n40  m3  p4g4r  h0j3")
    )
    ev = steps(res)["anti_evasion"]
    assert ev.status == "detect"
    assert ev.data["canonical"].startswith("vou te pegar")
    assert res.evasion_detected is True
    assert res.decided_by == "ollaya"
    assert steps(res)["ollaya"].status == "detect"


@pytest.mark.asyncio
async def test_subtle_threat_is_caught_by_ollaya():
    res = await interceptor(ollaya=ScriptedOllaya(threat=True)).inspect_and_filter(
        make_tx("Sei exatamente que horas voce chega em casa. Seria uma pena se algo acontecesse")
    )
    st = steps(res)
    assert res.decided_by == "ollaya"
    assert res.is_masked is True
    assert st["ollaya"].status == "detect"
    assert st["ollaya"].data["score"] == pytest.approx(0.91)


@pytest.mark.asyncio
async def test_ollaya_outage_approves_with_error_step():
    res = await interceptor(ollaya=ScriptedOllaya(fail=True)).inspect_and_filter(make_tx("Pagamento do almoco"))
    st = steps(res)
    assert res.decided_by == "ollaya_fallback"
    assert res.is_masked is False
    assert st["ollaya"].status == "error"
    assert st["delivery"].status == "pass"


@pytest.mark.asyncio
async def test_gateway_response_includes_account_step_first(monkeypatch):
    async def noop(*args, **kwargs):
        return None

    g = gateway_globals()
    monkeypatch.setattr(g["user_client"], "ensure_user", noop)
    monkeypatch.setattr(g["interceptor"], "investigation", None)
    monkeypatch.setattr(g["interceptor"], "ollaya", HeuristicOllaya())
    monkeypatch.setattr(g["interceptor"], "ollaya_tuned", HeuristicOllaya())

    payload = {
        "transaction_id": "tx_http_01",
        "sender_id": "usr_abc123",
        "sender_cpf": "12345678901",
        "receiver_id": "usr_xyz789",
        "receiver_cpf": "98765432100",
        "direction": "CASH_OUT",
        "amount": 1.0,
        "description": "Vou te pegar na saida",
    }
    async with AsyncClient(transport=ASGITransport(app=pix_gateway_app), base_url="http://test") as client:
        resp = await client.post("/pix/transactions", json=payload)

    assert resp.status_code == 200
    body = resp.json()
    assert body["decided_by"] == "ollaya"
    assert [s["step"] for s in body["trace"]] == [
        "amount_rule", "anti_evasion", "ollaya", "delivery",
    ]


@pytest.mark.asyncio
async def test_ollaya_client_uses_short_criteria_and_shared_connection():
    """O cliente real envia critérios curtos e reaproveita a conexão (sem criar um AsyncClient por chamada)."""
    import httpx
    from tests.modules import OllayaClient

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"model": "m", "answers": {"threat": {"choice": "threat", "confidence": 0.9, "probabilities": {"threat": 0.93, "safe": 0.07}}}},
        )

    client = OllayaClient(base_url="http://ollaya.test", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    r1 = await client.classify("vou te pegar")
    r2 = await client.classify("sei onde você mora")

    assert r1.is_threat and r2.is_threat
    assert len(seen) == 2
    q = seen[0]["questions"]["threat"]
    assert q["instructions"] == "A mensagem de Pix contém ameaça, chantagem ou perseguição?"
    assert q["criteria"] == {"threat": "ameaça, chantagem ou perseguição", "safe": "conversa normal ou amigável"}
    await client.aclose()


@pytest.mark.asyncio
async def test_ollaya_client_exposes_degraded_status_with_actionable_error():
    """Falha da IA deixa de ser silenciosa: o status fica `degraded` com o corpo do erro (MODEL_NOT_FOUND)."""
    import httpx
    from tests.modules import OllayaClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": 'model "laya:multilingual" not found', "code": "MODEL_NOT_FOUND"})

    client = OllayaClient(base_url="http://ollaya.test", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert client.status()["status"] == "unknown"

    with pytest.raises(RuntimeError):
        await client.classify("oi tudo bem")

    st = client.status()
    assert st["status"] == "degraded"
    assert st["consecutive_failures"] == 1
    assert "MODEL_NOT_FOUND" in st["last_error"]

    # Voltando a responder, o estado se recupera sozinho.
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"answers": {"threat": {"choice": "safe", "probabilities": {"threat": 0.01}}}})
        )
    )
    await client.classify("oi tudo bem")
    assert client.status()["status"] == "ok"
    await client.aclose()


@pytest.mark.asyncio
async def test_ollaya_client_cluster_round_robin_and_failover():
    """Valida que o cliente do Ollaya distribui as requisições em round-robin e faz failover entre nós."""
    import httpx
    from tests.modules import OllayaClient

    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if "node1" in str(request.url) and len(calls) == 3:
            # Simula falha transitória no node1 na 3ª chamada
            return httpx.Response(500, json={"error": "replica 1 crashed"})
        return httpx.Response(200, json={"answers": {"threat": {"choice": "safe", "probabilities": {"threat": 0.05}}}})

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cluster = OllayaClient(
        base_urls="http://node1:11435, http://node2:11435",
        client=mock_client,
    )

    assert cluster.status()["cluster_size"] == 2
    assert cluster.base_urls == ["http://node1:11435", "http://node2:11435"]

    # Chamada 1: vai para node1
    await cluster.classify("msg 1")
    assert "node1" in calls[0]

    # Chamada 2: vai para node2 (Round-Robin)
    await cluster.classify("msg 2")
    assert "node2" in calls[1]

    # Chamada 3: node1 falha com 500, o cliente faz failover automático para node2!
    res = await cluster.classify("msg 3")
    assert not res.is_threat
    assert "node1" in calls[2]
    assert "node2" in calls[3]

    await cluster.aclose()
