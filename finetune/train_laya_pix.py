"""Fine-tuning do Laya multilíngue (mmBERT-base) para ameaças/extorsão em mensagens de Pix.

GPU única (Colab T4). Baseado no notebook oficial laya_finetune_typed_decisions_2xT4_kaggle.ipynb
(RLCD: policy gradient com proper scoring rules + calibração de temperatura), sem DDP.

Uso:  python train_laya_pix.py DATA_DIR OUT_DIR [EPOCHS]
Entradas: DATA_DIR/{train,val,test,challenge}.jsonl (ver build_dataset.py)
Saídas  : OUT_DIR/model (checkpoint compatível com laya.Agent / laya-serve), OUT_DIR/metrics.json, OUT_DIR/report.md
"""
import json, math, os, random, sys, time
from pathlib import Path

import numpy as np
import torch
from huggingface_hub import snapshot_download
from safetensors.torch import load_file
from transformers import AutoTokenizer

import laya
from laya.calibrate import fit_temperature_map
from laya.common import build_model, collate_items
from laya.agent import _fix_tokenizer_config
from laya.train import calibration_records, encode_item, items_from_rows, rlcd_loss, save_checkpoint, sigma_at

DATA = Path(sys.argv[1]); OUT = Path(sys.argv[2]); EPOCHS = int(sys.argv[3]) if len(sys.argv) > 3 else 5
REPO, SUB = "convaiinnovations/laya", "multilingual"   # o português usa o checkpoint multilíngue (mmBERT-base)

# MESMA pergunta que o pix-gateway-service/src/clients/ollaya_client.py envia ao modelo.
QUESTIONS = {"threat": {"type": "choice", "instructions": "A mensagem de Pix contém ameaça, extorsão ou intimidação?", "criteria": {"threat": "ameaça", "safe": "agradecimento ou conversa normal"}}}
THRESHOLD = 0.40  # THREAT_THRESHOLD do gateway
SMOOTH = 0.02

MICRO_BATCH, GRAD_ACCUM, GROUP_SIZE = 16, 2, 4
LR_ENCODER, LR_HEAD, SIGMA_START, SIGMA_END = 2.5e-5, 1.0e-4, 0.4, 0.1


def read(split):
    return [json.loads(l) for l in open(DATA / f"{split}.jsonl", encoding="utf-8")]


def to_rows(recs):
    rows = []
    for r in recs:
        p = 1 - SMOOTH if r["label"] == "threat" else SMOOTH
        rows.append({"state": r["text"], "questions": QUESTIONS,
                     "gold": {"threat": {"label": r["label"], "probabilities": {"threat": p, "safe": 1 - p}}}})
    return rows


def evaluate(agent, recs, name, bs=64):
    probs, t_ms = [], []
    for i in range(0, len(recs), bs):
        chunk = [r["text"] for r in recs[i:i + bs]]
        t0 = time.perf_counter()
        try:
            res = agent.predict_batch(chunk, QUESTIONS)
        except Exception:
            res = [agent.predict(s, QUESTIONS) for s in chunk]
        t_ms.append((time.perf_counter() - t0) * 1000 / len(chunk))
        for x in res:
            a = x["answers"]["threat"]
            probs.append(float(a["probabilities"].get("threat", a.get("confidence", 0) if a["choice"] == "threat" else 0)))
    y = np.array([r["label"] == "threat" for r in recs]); p = np.array(probs)
    out = {"name": name, "n": len(recs), "n_threat": int(y.sum()), "latency_ms_per_msg": round(float(np.mean(t_ms)), 2)}
    for th in (0.3, THRESHOLD, 0.5, 0.7):
        pred = p >= th
        tp, fp, fn, tn = int((pred & y).sum()), int((pred & ~y).sum()), int((~pred & y).sum()), int((~pred & ~y).sum())
        prec = tp / (tp + fp) if tp + fp else 0.0; rec = tp / (tp + fn) if tp + fn else 0.0
        out[f"th_{th}"] = {"acc": round((tp + tn) / len(y), 4), "precision": round(prec, 4), "recall": round(rec, 4),
                           "f1": round(2 * prec * rec / (prec + rec), 4) if prec + rec else 0.0, "tp": tp, "fp": fp, "fn": fn, "tn": tn}
    return out, p


def main():
    random.seed(7); torch.manual_seed(7)
    dev = torch.device("cuda")
    snap = snapshot_download(REPO, allow_patterns=[f"{SUB}/*", f"{SUB}/**"])
    mdir = os.path.join(snap, SUB)
    _fix_tokenizer_config(mdir)
    cfg = json.load(open(os.path.join(mdir, "rl_agent_config.json")))
    max_len, head_max_len = cfg["max_len"], cfg["head_max_len"]
    tok = AutoTokenizer.from_pretrained(os.path.join(mdir, "tokenizer"))
    train, val, test, chall = read("train"), read("val"), read("test"), read("challenge")

    # ---- linha de base: Laya multilíngue SEM treino (como no vídeo)
    report = {"repo": f"{REPO}/{SUB}", "epochs": EPOCHS, "threshold": THRESHOLD, "baseline": {}, "tuned": {}}
    base_agent = laya.Agent(mdir, device="cuda")
    for nm, recs in (("test", test), ("challenge", chall)):
        report["baseline"][nm], _ = evaluate(base_agent, recs, nm)
        print("BASE", nm, json.dumps(report["baseline"][nm]))
    del base_agent; torch.cuda.empty_cache()

    # ---- itens de treino / calibração (calibração usa a VALIDAÇÃO, nunca o teste)
    items, skipped = items_from_rows(tok, to_rows(train), max_len, head_max_len)
    calib_items, sk2 = items_from_rows(tok, to_rows(val), max_len, head_max_len)
    print(f"itens treino={len(items)} (skipped={skipped}) calib={len(calib_items)} (skipped={sk2})")
    assert len(items) > 0.99 * len(train), "gold em formato inválido? veja skipped"

    model = build_model(cfg, encoder_dir=os.path.join(mdir, "encoder"))
    model.load_state_dict(load_file(os.path.join(mdir, "model.safetensors")), strict=True)
    model.to(dev).train()

    enc = [p for n, p in model.named_parameters() if "encoder." in n]
    head = [p for n, p in model.named_parameters() if "encoder." not in n]
    opt = torch.optim.AdamW([{"params": enc, "lr": LR_ENCODER}, {"params": head, "lr": LR_HEAD}], weight_decay=0.01)
    total = max(1, (len(items) // (MICRO_BATCH * GRAD_ACCUM)) * EPOCHS)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=total, eta_min=1e-6)
    scaler = torch.amp.GradScaler("cuda", enabled=True)
    t0 = time.time(); history = []

    for ep in range(EPOCHS):
        random.shuffle(items)
        sigma = sigma_at(ep, EPOCHS, SIGMA_START, SIGMA_END)
        ep_loss, nb, step = 0.0, 0, 0
        opt.zero_grad(set_to_none=True)
        for b in range(0, len(items), MICRO_BATCH):
            chunk = items[b:b + MICRO_BATCH]
            batch = collate_items([[encode_item(tok, it, max_len, head_max_len) for it in chunk]], tok.pad_token_id)
            with torch.autocast("cuda", dtype=torch.float16):
                logits, _ = model(batch["input_ids"].to(dev), batch["attention_mask"].to(dev), batch["marker_pos"].to(dev),
                                  batch["marker_mask"].to(dev), batch["qtype"].to(dev))
            loss = rlcd_loss(logits.float(), batch["target"].to(dev), batch["marker_mask"].to(dev), batch["qtype"].to(dev),
                             sigma, samples=GROUP_SIZE, w_sph=0.75, w_rps=1.0)
            scaler.scale(loss / GRAD_ACCUM).backward(); step += 1
            if step % GRAD_ACCUM == 0 or b + MICRO_BATCH >= len(items):
                scaler.unscale_(opt); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                scaler.step(opt); scaler.update(); sched.step(); opt.zero_grad(set_to_none=True)
            ep_loss += loss.item(); nb += 1
            if nb % 50 == 0:
                print(f"  ep {ep+1}/{EPOCHS} step {nb} loss {loss.item():.4f}", flush=True)
        history.append({"epoch": ep + 1, "avg_loss": round(ep_loss / max(1, nb), 4), "sec": round(time.time() - t0)})
        print("=== epoch", history[-1], flush=True)
    report["train_history"] = history

    # ---- calibração de temperatura na validação + salvamento
    del opt, scaler, sched; torch.cuda.empty_cache(); model.eval()
    fitted = fit_temperature_map(calibration_records(model, tok, calib_items, dev, max_len, head_max_len, batch_size=16))
    out_cfg = dict(cfg, max_len=max_len, head_max_len=head_max_len, fine_tuned=True, model_name="laya-pix-threats",
                   temperature=fitted["temperature"])
    out_cfg.pop("temperature_by_options", None)
    if fitted.get("temperature_by_options"):
        out_cfg["temperature_by_options"] = fitted["temperature_by_options"]
    mdl_dir = OUT / "model"; mdl_dir.mkdir(parents=True, exist_ok=True)
    save_checkpoint(model, tok, out_cfg, str(mdl_dir))
    print("checkpoint salvo em", mdl_dir, "| temperaturas:", [round(t, 3) for t in fitted["temperature"]])
    del model; torch.cuda.empty_cache()

    # ---- avaliação final (teste congelado + desafio escrito à mão + validação)
    agent = laya.Agent(str(mdl_dir), device="cuda")
    for nm, recs in (("test", test), ("challenge", chall), ("val", val)):
        report["tuned"][nm], p = evaluate(agent, recs, nm)
        print("TUNED", nm, json.dumps(report["tuned"][nm]))
        if nm == "challenge":
            report["challenge_errors"] = [{"text": r["text"], "label": r["label"], "p_threat": round(float(pp), 3)}
                                          for r, pp in zip(recs, p) if (pp >= THRESHOLD) != (r["label"] == "threat")]
    (OUT / "metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))

    def row(d):
        t = d[f"th_{THRESHOLD}"]; return f'{t["acc"]:.3f} | {t["precision"]:.3f} | {t["recall"]:.3f} | {t["f1"]:.3f} | {t["fp"]} | {t["fn"]}'
    md = ["# Laya multilíngue x Laya retreinado (Pix: ameaças e extorsão)", "", f"Limiar: {THRESHOLD}", "",
          "| modelo / conjunto | acurácia | precisão | recall | F1 | falsos+ | falsos− |", "|---|---|---|---|---|---|---|"]
    for which in ("baseline", "tuned"):
        for nm in ("test", "challenge"):
            md.append(f"| {'sem treino' if which == 'baseline' else 'retreinado'} / {nm} | {row(report[which][nm])} |")
    md += ["", "Teste = dados sintéticos (fragmentos separados do treino, ver build_dataset.py); desafio = 50 mensagens escritas à mão. "
           "O desafio é a leitura mais honesta; o teste sintético tende a ser otimista."]
    (OUT / "report.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
