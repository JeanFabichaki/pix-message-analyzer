import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from tests.modules import gemini_agent_app, pix_gateway_app, BenchmarkRunner



@pytest.mark.asyncio
async def test_gemini_agent_generate_dataset_endpoint():
    """Valida o endpoint POST /benchmark/generate-dataset no gemini-investigation-agent."""
    transport = ASGITransport(app=gemini_agent_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/benchmark/generate-dataset", json={"count": 50})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["count"] == 50
        assert len(data["messages"]) == 50
        assert data["threats_count"] > 0
        assert data["safe_count"] > 0

        # Verifica formato das mensagens
        first = data["messages"][0]
        assert "id" in first
        assert "text" in first
        assert first["label"] in ("threat", "safe")
        assert "category" in first


@pytest.mark.asyncio
async def test_benchmark_runner_dynamic_dataset():
    """Valida o suporte a datasets dinâmicos no BenchmarkRunner."""
    from tests.fakes import HeuristicOllaya

    runner = BenchmarkRunner(
        clients={"laya": HeuristicOllaya(), "laya_tuned": HeuristicOllaya()},
        data_dir=None,
    )

    sample_rows = [
        {"id": "m1", "text": "Vou te pegar na saída", "label": "threat", "category": "violencia"},
        {"id": "m2", "text": "Pagamento do cafe", "label": "safe", "category": "pagamento"},
    ]

    runner.set_dynamic_dataset("gemini", "Geradas via Gemini", "Teste dinâmico", sample_rows)
    datasets = runner.datasets()
    gemini_ds = next((d for d in datasets if d["id"] == "gemini"), None)
    assert gemini_ds is not None
    assert gemini_ds["size"] == 2
    assert gemini_ds["available"] is True

    # Roda o benchmark no dataset dinâmico
    job_id = runner.start("gemini", size=None)
    assert job_id is not None
    # Aguarda a tarefa assíncrona terminar
    if job_id in runner._tasks:
        await runner._tasks[job_id]
    job = runner.get(job_id)
    assert job["status"] == "done"
    assert job["report"] is not None
    assert job["report"]["dataset"] == "gemini"
    laya_summary = job["report"]["summary"]["laya"]
    assert laya_summary["n"] == 2
    assert "avg_ms" in laya_summary and laya_summary["avg_ms"] is not None
    assert "median_ms" in laya_summary and laya_summary["median_ms"] is not None
    assert "p50_ms" in laya_summary and laya_summary["p50_ms"] is not None
    assert "p95_ms" in laya_summary and laya_summary["p95_ms"] is not None
    assert "p99_ms" in laya_summary and laya_summary["p99_ms"] is not None
    assert "min_ms" in laya_summary and laya_summary["min_ms"] is not None
    assert "max_ms" in laya_summary and laya_summary["max_ms"] is not None
    assert "wall_ms" in laya_summary and laya_summary["wall_ms"] is not None
    assert "throughput_rps" in laya_summary and laya_summary["throughput_rps"] is not None
    assert "engine_timings" in job
    assert "laya" in job["engine_timings"]
    assert "laya_tuned" in job["engine_timings"]
