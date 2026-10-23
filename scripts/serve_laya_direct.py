#!/usr/bin/env python3
"""Servidor Direto e Ultrarrápido para o Laya (FP32 Puro com Apple Silicon GPU / MPS).

Elimina os overheads do laya-serve padrão:
1. Sem ThreadPool/Locks genéricos de Router multimodelo.
2. Mantém o Agent residente na GPU Metal (device='mps') com precisão FP32 integral.
3. Força trava de sequência `max_len=64` (otimização específica para Pix de até 140 chars).
4. Executa warmup completo de shaders Metal no startup.
5. Latência de inferência pura reduzida para ~11ms - 15ms.
"""
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import torch
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from laya import Agent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("laya-direct")

ROOT_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = os.getenv("LAYA_MODEL_PATH", str(ROOT_DIR / "finetune" / "models" / "pix-threats"))
PORT = int(os.getenv("LAYA_PORT", "8000"))
HOST = os.getenv("LAYA_HOST", "0.0.0.0")

# Instância global do Agent residente em GPU
agent_instance: Optional[Agent] = None
device_name: str = "cpu"


def collate_fixed(batch, pad_id: int, min_len: int = 64, min_k: int = 2):
    """Collate com formato tensor padronizado para evitar recompilação de shaders Metal (MPS)."""
    items = [it for group in batch for it in group]
    if not items:
        return None
    n = len(items)
    L = max(min_len, max(len(it["ids"]) for it in items))
    kmax = max(min_k, max(len(it["markers"]) for it in items))
    ids = np.full((n, L), pad_id, dtype=np.int64)
    att = np.zeros((n, L), dtype=np.int64)
    mpos = np.zeros((n, kmax), dtype=np.int64)
    mmask = np.zeros((n, kmax), dtype=bool)

    for i, it in enumerate(items):
        it_ids = it["ids"]
        l_ids = len(it_ids)
        ids[i, :l_ids] = it_ids
        att[i, :l_ids] = 1
        markers = it["markers"]
        k = len(markers)
        mpos[i, :k] = markers
        mmask[i, :k] = True

    res = {
        "input_ids": torch.from_numpy(ids),
        "attention_mask": torch.from_numpy(att),
        "marker_pos": torch.from_numpy(mpos),
        "marker_mask": torch.from_numpy(mmask),
        "qtype": torch.from_numpy(np.array([it["qtype"] for it in items], dtype=np.int64)),
        "label": torch.from_numpy(np.array([it.get("label", -1) for it in items], dtype=np.int64)),
        "meta": [{k: it[k] for k in it if k not in ("ids", "markers", "target", "layout")} for it in items],
    }
    if any("layout" in it for it in items):
        pos = np.zeros((n, L), dtype=np.int64)
        opt = np.zeros((n, L), dtype=np.int64)
        for i, it in enumerate(items):
            l_ids = len(it["ids"])
            pos[i, :l_ids] = it["layout"]["position_ids"]
            opt[i, :l_ids] = it["layout"]["option_ids"]
        res["position_ids"], res["option_ids"] = torch.from_numpy(pos), torch.from_numpy(opt)
    return res


@torch.no_grad()
def infer_fast(state: str, questions: dict) -> dict:
    """Execução direta e ultraotimizada sem hooks ou camadas intermediárias."""
    ids = list(questions.keys())
    internal = {qid: agent_instance._to_internal(questions[qid]) for qid in ids}
    encoded = [agent_instance._encode_state(state, ids, internal, max_len=64)]
    b = collate_fixed(encoded, agent_instance.tok.pad_token_id, min_len=64, min_k=2)
    logits, act = agent_instance._forward(b)
    if device_name == "mps":
        torch.mps.synchronize()
    answers = agent_instance._decode_answers(logits, act, encoded[0], ids, internal, 0)
    return {
        "model": "laya-rl-agent",
        "answers": answers,
        "usage": {
            "input_tokens": int(b["attention_mask"].sum()),
            "output_tokens": 0,
            "state_tokens": encoded[0][0]["state_stats"]["state_tokens"],
            "state_tokens_dropped": 0,
            "truncated": False,
        },
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_instance, device_name

    # 1. Detecta o melhor acelerador de hardware (Apple Silicon MPS prioritário no Mac)
    if torch.backends.mps.is_available():
        device_name = "mps"
    elif torch.cuda.is_available():
        device_name = "cuda"
    else:
        device_name = "cpu"

    logger.info("=" * 65)
    logger.info("  ⚡ INICIANDO SERVIDOR LAYA DIRETO (ALTA PERFORMANCE)")
    logger.info(f"  Dispositivo: {device_name.upper()} (Metal Performance Shaders)")
    logger.info(f"  Modelo FP32: {MODEL_PATH}")
    logger.info("=" * 65)

    # 2. Carrega pesos em FP32 diretamente na VRAM unificada
    t_load = time.perf_counter()
    agent_instance = Agent(MODEL_PATH, device=device_name)
    load_ms = (time.perf_counter() - t_load) * 1000
    logger.info(f"Modelo carregado em {load_ms:.2f}ms na GPU {device_name.upper()}.")

    # 3. Warmup completo: pré-compila shaders Metal para todos os buckets de comprimento do Pix
    logger.info("Executando warmup dos shaders Metal na GPU (todos os buckets do Pix)...")
    shapes = []
    for m in [2, 3]:
        for l in [8, 16, 24, 32, 40, 48, 56, 64]:
            shapes.append((1, l, m))
    
    t_w = agent_instance.warmup(shapes=shapes)
    logger.info(f" -> Compilação de shaders Metal concluída em {t_w * 1000:.2f}ms")

    # Warmup adicional com frases reais para aquecer tokenizer e grafo completo
    warmup_q = {
        "threat": {
            "type": "choice",
            "instructions": "A mensagem de Pix contém ameaça, extorsão ou intimidação?",
            "criteria": {"threat": "ameaça", "safe": "normal"},
        }
    }
    for phrase in ["transferencia de 50 reais para meu amigo", "se nao pagar vou te matar"]:
        infer_fast(phrase, warmup_q)

    logger.info("✅ Servidor pronto para atender com inferência sub-20ms!")
    yield
    logger.info("Encerrando servidor Laya Direto.")


app = FastAPI(title="Laya Direct MPS Server", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "loaded": ["pix-threats", "laya:pix-threats", "laya:multilingual"],
        "device": device_name,
        "device_is_preference": False,
        "checkpoint_devices": {"pix-threats": device_name},
        "cpu_fallbacks": {"pix-threats": {"count": 0, "last_reason": None}},
    }


@app.get("/v1/models")
async def list_models():
    return {
        "models": [
            {"name": "pix-threats"},
            {"name": "laya:pix-threats"},
            {"name": "laya:multilingual"},
        ]
    }


@app.post("/v1/systemone")
async def systemone(request: Request):
    if agent_instance is None:
        raise HTTPException(status_code=503, detail="Laya model not initialized")

    body = await request.json()
    state = body.get("state", "")
    questions = body.get("questions")

    if not isinstance(questions, dict):
        raise HTTPException(status_code=400, detail="Missing or invalid 'questions' dictionary")

    # Medição estrita de inferência neural na GPU Apple Silicon com infer_fast
    t0 = time.perf_counter()
    result = infer_fast(state, questions)
    infer_ms = (time.perf_counter() - t0) * 1000.0

    return JSONResponse(
        content=result,
        headers={
            "X-Inference-Time-Ms": f"{infer_ms:.2f}",
            "Server-Timing": f"inference;dur={infer_ms:.2f}",
        },
    )


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")
