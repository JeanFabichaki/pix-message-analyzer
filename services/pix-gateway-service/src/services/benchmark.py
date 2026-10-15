"""Benchmark lado a lado: Laya original x Laya retreinado, usando os dados de teste do fine-tuning.

Cada mensagem é classificada pelos DOIS modelos pelo mesmo caminho que o gateway usa em produção
(`OllayaClient.classify`, que aplica o limiar de ameaça). Nada aqui toca em banco, usuários ou Gemini.
Só depende da biblioteca padrão: os clientes são injetados, o que permite testar com dublês.
"""
import asyncio
import json
import random
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ENGINE_IDS = ("laya", "laya_tuned")
DATASETS = {
    "test": {"file": "test.jsonl", "label": "Teste sintético", "note": "1000 mensagens geradas a partir de frases que o modelo nunca viu no treino."},
    "challenge": {"file": "challenge.jsonl", "label": "Escritas à mão", "note": "50 mensagens escritas à mão, com palavras diferentes das do treino."},
}
CATEGORY_LABELS = {
    "violencia": "Ameaça de violência",
    "chantagem": "Chantagem (fotos, segredos)",
    "cobranca_agressiva": "Cobrança com ameaça",
    "extorsao_violenta": "Extorsão com intimidação",
    "stalking": "Perseguição (stalking)",
    "pagamento": "Pagamento comum",
    "idioma_violento": "Gíria que parece ameaça",
    "cobranca_educada": "Cobrança educada",
    "neutra": "Mensagem neutra",
    "manual_threat": "Ameaça escrita à mão",
    "manual_safe": "Mensagem normal escrita à mão",
    "gemini_threat": "Ameaça (Gemini)",
    "gemini_safe": "Mensagem normal (Gemini)",
}



def find_data_dir(configured: Optional[str] = None) -> Optional[Path]:
    candidates = [configured] if configured else []
    here = Path(__file__).resolve()
    candidates += ["/data", *(str(p / "finetune" / "data") for p in here.parents)]
    for c in candidates:
        if c and (Path(c) / "test.jsonl").is_file():
            return Path(c)
    return None


def load_rows(data_dir: Path, dataset: str, size: Optional[int], seed: int = 7) -> List[Dict[str, Any]]:
    meta = DATASETS[dataset]
    rows = [json.loads(l) for l in (data_dir / meta["file"]).read_text(encoding="utf-8").splitlines() if l.strip()]
    for r in rows:  # o conjunto escrito à mão tem uma categoria só; separa por rótulo para o gráfico
        if r.get("category") == "manual":
            r["category"] = f"manual_{r['label']}"
    if size and size < len(rows):
        # amostra estratificada: mantém a proporção de ameaças e de cada categoria
        rnd = random.Random(seed)
        by_cat: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            by_cat.setdefault(r.get("category", "?"), []).append(r)
        picked: List[Dict[str, Any]] = []
        for cat_rows in by_cat.values():
            k = max(1, round(size * len(cat_rows) / len(rows)))
            picked += rnd.sample(cat_rows, min(k, len(cat_rows)))
        rnd.shuffle(picked)
        rows = picked[:size] if len(picked) > size else picked
    return rows


def _pct(x: float) -> float:
    return round(100.0 * x, 1)


def summarize(rows: List[Dict[str, Any]], engine: str, wall_ms: Optional[float] = None) -> Dict[str, Any]:
    ok = [r for r in rows if r[engine].get("error") is None]
    tp = sum(1 for r in ok if r["label"] == "threat" and r[engine]["pred"])
    fn = sum(1 for r in ok if r["label"] == "threat" and not r[engine]["pred"])
    fp = sum(1 for r in ok if r["label"] != "threat" and r[engine]["pred"])
    tn = sum(1 for r in ok if r["label"] != "threat" and not r[engine]["pred"])
    n = len(ok)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    lat = sorted(r[engine]["ms"] for r in ok)

    avg_ms = round(sum(lat) / n, 1) if n else None
    min_ms = round(lat[0], 1) if n else None
    max_ms = round(lat[-1], 1) if n else None
    median_ms = round(lat[min(int(n * 0.50), n - 1)], 1) if n else None
    p50_ms = median_ms
    p90_ms = round(lat[min(int(n * 0.90), n - 1)], 1) if n else None
    p95_ms = round(lat[min(int(n * 0.95), n - 1)], 1) if n else None
    p99_ms = round(lat[min(int(n * 0.99), n - 1)], 1) if n else None

    total_wall_ms = round(wall_ms, 1) if wall_ms is not None else (round(sum(lat), 1) if n else None)
    throughput_rps = round(n / (total_wall_ms / 1000.0), 1) if total_wall_ms and total_wall_ms > 0 else None

    return {
        "n": n,
        "errors": len(rows) - n,
        "tp": tp, "fn": fn, "fp": fp, "tn": tn,
        "threats_total": tp + fn,
        "safe_total": fp + tn,
        "accuracy": _pct((tp + tn) / n) if n else 0.0,
        "precision": _pct(prec),
        "recall": _pct(rec),
        "f1": _pct(2 * prec * rec / (prec + rec)) if prec + rec else 0.0,
        "avg_ms": avg_ms,
        "median_ms": median_ms,
        "p50_ms": p50_ms,
        "p90_ms": p90_ms,
        "p95_ms": p95_ms,
        "p99_ms": p99_ms,
        "min_ms": min_ms,
        "max_ms": max_ms,
        "wall_ms": total_wall_ms,
        "throughput_rps": throughput_rps,
    }


def _correct(r: Dict[str, Any], engine: str) -> bool:
    return r[engine]["pred"] == (r["label"] == "threat")


def build_report(rows: List[Dict[str, Any]], dataset: str, engine_timings: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    engine_timings = engine_timings or {}
    complete = [r for r in rows if all(r[e].get("error") is None for e in ENGINE_IDS)]
    summary = {e: summarize(complete, e, wall_ms=engine_timings.get(e)) for e in ENGINE_IDS}
    errors = {e: sum(1 for r in rows if r[e].get("error") is not None) for e in ENGINE_IDS}
    first_error = next((r[e]["error"] for r in rows for e in ENGINE_IDS if r[e].get("error")), None)

    cats: Dict[str, Dict[str, Any]] = {}
    for r in complete:
        c = cats.setdefault(r["category"], {"category": r["category"], "label": CATEGORY_LABELS.get(r["category"], r["category"]),
                                            "kind": "threat" if r["label"] == "threat" else "safe", "n": 0, "laya": 0, "laya_tuned": 0})
        c["n"] += 1
        for e in ENGINE_IDS:
            c[e] += int(_correct(r, e))
    by_category = sorted(cats.values(), key=lambda c: (c["kind"] != "threat", c["label"]))

    def view(r: Dict[str, Any]) -> Dict[str, Any]:
        return {"text": r["text"], "label": r["label"], "category": CATEGORY_LABELS.get(r["category"], r["category"]),
                "laya": {"pred": r["laya"]["pred"], "score": round(r["laya"]["score"], 3)},
                "laya_tuned": {"pred": r["laya_tuned"]["pred"], "score": round(r["laya_tuned"]["score"], 3)}}

    wins_tuned = [view(r) for r in complete if _correct(r, "laya_tuned") and not _correct(r, "laya")]
    wins_base = [view(r) for r in complete if _correct(r, "laya") and not _correct(r, "laya_tuned")]
    both_wrong = [view(r) for r in complete if not _correct(r, "laya") and not _correct(r, "laya_tuned")]
    # prioriza ameaças que o original deixou passar: é o caso mais didático
    wins_tuned.sort(key=lambda v: (v["label"] != "threat", -abs(v["laya_tuned"]["score"] - v["laya"]["score"])))
    return {
        "dataset": dataset,
        "summary": summary,
        "errors": errors,
        "first_error": first_error,
        "n_requested": len(rows),
        "by_category": by_category,
        "counts": {"wins_tuned": len(wins_tuned), "wins_base": len(wins_base), "both_wrong": len(both_wrong), "both_right": len(complete) - len(wins_tuned) - len(wins_base) - len(both_wrong)},
        "examples": {"wins_tuned": wins_tuned[:12], "wins_base": wins_base[:6], "both_wrong": both_wrong[:6]},
    }


class BenchmarkRunner:
    """Mantém os trabalhos em memória (um benchmark por vez já é o uso esperado)."""

    def __init__(self, clients: Dict[str, Any], data_dir: Optional[Path], concurrency: int = 6):
        self.clients = clients
        self.data_dir = data_dir
        self.concurrency = concurrency
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self.dynamic_datasets: Dict[str, Dict[str, Any]] = {}

    def set_dynamic_dataset(self, dataset_id: str, label: str, note: str, rows: List[Dict[str, Any]]):
        self.dynamic_datasets[dataset_id] = {
            "id": dataset_id,
            "label": label,
            "note": note,
            "rows": rows,
            "size": len(rows),
            "available": True,
            "generated_at": time.time(),
        }

    def datasets(self) -> List[Dict[str, Any]]:
        out = []
        for key, meta in DATASETS.items():
            n = None
            if self.data_dir and (self.data_dir / meta["file"]).is_file():
                n = sum(1 for l in (self.data_dir / meta["file"]).read_text(encoding="utf-8").splitlines() if l.strip())
            out.append({"id": key, "label": meta["label"], "note": meta["note"], "size": n, "available": n is not None})
        for key, dyn in self.dynamic_datasets.items():
            out.append({
                "id": key,
                "label": dyn["label"],
                "note": dyn["note"],
                "size": dyn["size"],
                "available": True,
                "generated_at": dyn.get("generated_at"),
            })
        return out

    def start(self, dataset: str, size: Optional[int]) -> str:
        if dataset in self.dynamic_datasets:
            rows = list(self.dynamic_datasets[dataset]["rows"])
            if size and size < len(rows):
                rows = rows[:size]
        elif dataset in DATASETS:
            if not self.data_dir:
                raise FileNotFoundError("dados de teste não encontrados (monte ./finetune/data em /data)")
            rows = load_rows(self.data_dir, dataset, size)
        else:
            raise ValueError(f"dataset desconhecido: {dataset}")
        job_id = uuid.uuid4().hex[:10]
        self.jobs[job_id] = {"id": job_id, "status": "running", "dataset": dataset, "total": len(rows),
                             "done": {e: 0 for e in ENGINE_IDS}, "started": time.time(), "report": None, "error": None}
        self._tasks[job_id] = asyncio.create_task(self._run(job_id, rows))
        return job_id


    async def _classify(self, engine: str, text: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        try:
            res = await self.clients[engine].classify(text)
            return {"pred": bool(res.is_threat), "score": float(res.score), "ms": (time.perf_counter() - t0) * 1000, "error": None}
        except Exception as ex:  # um erro isolado não derruba o benchmark
            return {"pred": False, "score": 0.0, "ms": 0.0, "error": str(ex)[:200]}

    async def _run(self, job_id: str, rows: List[Dict[str, Any]]) -> None:
        job = self.jobs[job_id]
        results: List[Dict[str, Any]] = [
            {"text": r["text"], "label": r["label"], "category": r.get("category", "?")} for r in rows
        ]
        engine_timings: Dict[str, float] = {}

        async def run_engine(engine: str) -> None:
            t0_eng = time.perf_counter()
            sem = asyncio.Semaphore(self.concurrency)

            async def one(i: int) -> None:
                async with sem:
                    results[i][engine] = await self._classify(engine, rows[i]["text"])
                    job["done"][engine] += 1

            await asyncio.gather(*(one(i) for i in range(len(rows))))
            engine_timings[engine] = (time.perf_counter() - t0_eng) * 1000

        try:
            # Com o cluster segregado (ollaya dedicado ao base e ollaya-tuned ao retreinado),
            # ambos os modelos executam simultaneamente em paralelo sem contenção de memória
            await asyncio.gather(*(run_engine(e) for e in ENGINE_IDS))
            job["engine_timings"] = {e: round(engine_timings.get(e, 0.0), 1) for e in ENGINE_IDS}
            job["report"] = build_report(results, job["dataset"], engine_timings=engine_timings)
            job["status"] = "done"
        except Exception as ex:
            job["status"] = "error"
            job["error"] = str(ex)
        finally:
            job["elapsed_s"] = round(time.time() - job["started"], 1)

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.jobs.get(job_id)
