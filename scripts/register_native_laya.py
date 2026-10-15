#!/usr/bin/env python3
"""Registra o modelo Laya retreinado nativamente no Ollaya (C++ / ONNX Runtime).

O Ollaya executa grafos ONNX (application/vnd.ollaya.graph.onnx) que usam inicializadores
com tensores externos (data_location=1). Esses grafos contêm referências relativas para
o blob de pesos (location) e os deslocamentos em bytes (offset/length).

Este script:
1. Extrai o grafo original FP32 do Laya multilíngue no Ollaya.
2. Recalcula os offsets em bytes com base no cabeçalho do `model.safetensors` retreinado.
3. Patcha o grafo ONNX intermediário para vincular aos tensores retreinados.
4. Aplica o Transformer Optimizer do ONNX Runtime (fusão de atenção, layer norm e ativações),
   eliminando centenas de nós redundantes (Cast, Transpose, Identity).
5. Empacota os tensores externos consolidados no formato de dados externos do ONNX Runtime.
6. Configura `max_seq_length = 64` (context_length, max_len, head_max_len) para inferência < 50ms.
7. Gera o blob de calibração de temperatura a partir de `rl_agent_config.json`.
8. Publica os grafos otimizados, pesos e manifesto `laya:pix-threats` diretamente no Ollaya.
"""
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import types
from pathlib import Path

# Mock do módulo torch caso não esteja instalado no ambiente (necessário para onnxruntime.transformers.optimizer)
if "torch" not in sys.modules:
    torch_mod = types.ModuleType("torch")
    torch_mod.version = types.SimpleNamespace(cuda="12.1", hip=None)
    sys.modules["torch"] = torch_mod

# Garante que roda com o Python do .venv caso o python do sistema não tenha dependências
try:
    import onnx  # noqa: F401
    import onnxruntime  # noqa: F401
    import sympy  # noqa: F401
    from onnxruntime.transformers import optimizer  # noqa: F401
    from onnxruntime.transformers.fusion_options import FusionOptions  # noqa: F401
except ImportError:
    venv_python = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python"
    if venv_python.is_file() and sys.executable != str(venv_python):
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "finetune" / "models" / "pix-threats" / "model.safetensors"
CFG_PATH = ROOT / "finetune" / "models" / "pix-threats" / "rl_agent_config.json"
CONTAINER_NAME = "pix-ollaya"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def patch_onnx_graph(onnx_in_path: Path, onnx_out_path: Path, st_header: dict, base_data_start: int, blob_name: str) -> None:
    import onnx
    model = onnx.load(str(onnx_in_path), load_external_data=False)
    for init in model.graph.initializer:
        if not init.external_data:
            continue
        clean = init.name.removeprefix("w:").removeprefix("p_").removeprefix("b_")
        if clean not in st_header:
            continue
        info = st_header[clean]
        offset = info["data_offsets"][0] + base_data_start
        length = info["data_offsets"][1] - info["data_offsets"][0]
        del init.external_data[:]
        e1 = init.external_data.add()
        e1.key = "location"
        e1.value = blob_name
        e2 = init.external_data.add()
        e2.key = "offset"
        e2.value = str(offset)
        e3 = init.external_data.add()
        e3.key = "length"
        e3.value = str(length)
    onnx.save(model, str(onnx_out_path))


def main():
    if not MODEL_PATH.is_file():
        print(f"[AVISO] Checkpoint retreinado não encontrado em {MODEL_PATH}.")
        print("Para treinar, siga o tutorial em finetune/README.md.")
        return 0

    print(f"Verificando pesos retreinados em {MODEL_PATH}...")

    # 1. Verifica se o container do Ollaya está rodando
    res = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER_NAME],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0 or res.stdout.strip() != "true":
        print(f"[ERRO] Container {CONTAINER_NAME} não está em execução. Suba com `make up` primeiro.")
        return 1

    # 2. Lê cabeçalho do safetensors retreinado
    with open(MODEL_PATH, "rb") as f:
        h_len = struct.unpack("<Q", f.read(8))[0]
        st_header = json.loads(f.read(h_len))
    base_data_start = 8 + h_len

    # Cria diretório temporário dentro de MODEL_PATH.parent para permitir hardlinks e evitar
    # erro do ONNX Runtime "External data path escapes model directory"
    tmpdir = tempfile.mkdtemp(dir=MODEL_PATH.parent)
    try:
        tmp_path = Path(tmpdir)
        weights_name = "retrained_weights.bin"
        local_weights = tmp_path / weights_name
        os.link(MODEL_PATH, local_weights)

        # 3. Extrai grafo base FP32 do Laya multilíngue no container
        base_fp32 = tmp_path / "graph_fp32.onnx"
        print(f"Extraindo grafo FP32 base do container {CONTAINER_NAME}...")
        subprocess.run(
            ["docker", "cp", f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/sha256-ace962240e4cf7c69c0e65ea7224aa791777880003950a81347a206f6bfbed45", str(base_fp32)],
            check=True,
        )

        # 4. Patcha o grafo base com os offsets dos pesos retreinados
        print("Adaptando offsets do grafo ONNX para os tensores retreinados...")
        patched_base = tmp_path / "patched_base.onnx"
        patch_onnx_graph(base_fp32, patched_base, st_header, base_data_start, weights_name)

        # 5. Otimização de grafo com o Transformer Optimizer do ONNX Runtime
        print("Executando Transformer Optimizer do ONNX Runtime (fusão de atenção, layer norm e ativações)...")
        opt_options = FusionOptions("bert")
        opt_model = optimizer.optimize_model(
            str(patched_base),
            "bert",
            num_heads=12,
            hidden_size=768,
            optimization_options=opt_options,
        )
        nodes_before = len(onnx.load(str(patched_base), load_external_data=False).graph.node)
        nodes_after = len(opt_model.model.graph.node)
        print(f"Otimização concluída: Grafo reduzido de {nodes_before} para {nodes_after} nós!")

        # 6. Salva modelo otimizado com dados externos consolidados
        opt_graph_path = tmp_path / "opt_graph.onnx"
        opt_model.save_model_to_file(str(opt_graph_path), use_external_data_format=True, all_tensors_to_one_file=True)

        opt_data_path = tmp_path / "opt_graph.onnx.data"
        weights_digest = compute_sha256(opt_data_path)
        weights_size = opt_data_path.stat().st_size
        weights_blob = f"sha256-{weights_digest}"
        print(f"Novos pesos consolidados: {weights_blob} ({weights_size} bytes)")

        # 7. Atualiza o local dos tensores externos para o blob de hash do Ollaya
        m = onnx.load(str(opt_graph_path), load_external_data=False)
        for init in m.graph.initializer:
            for entry in init.external_data:
                if entry.key == "location":
                    entry.value = weights_blob

        final_graph_path = tmp_path / "final_opt.onnx"
        onnx.save(m, str(final_graph_path))

        graph_digest = compute_sha256(final_graph_path)
        graph_size = final_graph_path.stat().st_size
        graph_blob = f"sha256-{graph_digest}"
        print(f"Grafo otimizado final: {graph_blob} ({graph_size} bytes)")

        # 8. Blob de calibração (temperatura)
        temperatures = [1.0, 1.0, 1.0]
        if CFG_PATH.is_file():
            cfg_data = json.loads(CFG_PATH.read_text())
            temperatures = cfg_data.get("temperature", temperatures)
        calib_data = json.dumps({"temperature": temperatures, "temperature_by_options": {}}, indent=2).encode()
        calib_digest = hashlib.sha256(calib_data).hexdigest()
        calib_file = tmp_path / f"sha256-{calib_digest}"
        calib_file.write_bytes(calib_data)

        # 9. Blobs de configuração e decisão com max_len = 64 (otimização para Pix < 140 chars)
        print("Configurando max_seq_length = 64 para inferência ultrarrápida em borda (<50ms)...")
        raw_dec = subprocess.check_output(
            ["docker", "exec", CONTAINER_NAME, "cat", "/home/ollaya/.ollaya/models/blobs/sha256-70fd2a20d3e0f259063958071637b2047a01f4d8dd5681ab2f3d647ee9193fac"]
        )
        dec_data = json.loads(raw_dec)
        dec_data["max_len"] = 64
        dec_data["head_max_len"] = 64
        dec_bytes = json.dumps(dec_data, indent=2).encode("utf-8")
        dec_digest = hashlib.sha256(dec_bytes).hexdigest()
        dec_file = tmp_path / f"sha256-{dec_digest}"
        dec_file.write_bytes(dec_bytes)

        raw_cfg = subprocess.check_output(
            ["docker", "exec", CONTAINER_NAME, "cat", "/home/ollaya/.ollaya/models/blobs/sha256-05b7fd1e50a9bfc27e9547783b382f2bb2769cb4adc0eebb85bb57ae3060f06d"]
        )
        cfg_data = json.loads(raw_cfg)
        cfg_data["context_length"] = 64
        cfg_bytes = json.dumps(cfg_data, indent=2).encode("utf-8")
        cfg_digest = hashlib.sha256(cfg_bytes).hexdigest()
        cfg_file = tmp_path / f"sha256-{cfg_digest}"
        cfg_file.write_bytes(cfg_bytes)

        # 10. Copia blobs para o container
        print(f"Copiando pesos e grafos otimizados para o container {CONTAINER_NAME}...")
        subprocess.run(["docker", "cp", str(opt_data_path), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/{weights_blob}"], check=True)
        subprocess.run(["docker", "cp", str(final_graph_path), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/{graph_blob}"], check=True)
        subprocess.run(["docker", "cp", str(calib_file), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/sha256-{calib_digest}"], check=True)
        subprocess.run(["docker", "cp", str(dec_file), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/sha256-{dec_digest}"], check=True)
        subprocess.run(["docker", "cp", str(cfg_file), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/sha256-{cfg_digest}"], check=True)

        # Garante permissões de leitura para o usuário não-root `ollaya` no container
        subprocess.run(
            ["docker", "exec", "-u", "0", CONTAINER_NAME, "chmod", "666",
             f"/home/ollaya/.ollaya/models/blobs/{weights_blob}",
             f"/home/ollaya/.ollaya/models/blobs/{graph_blob}",
             f"/home/ollaya/.ollaya/models/blobs/sha256-{calib_digest}",
             f"/home/ollaya/.ollaya/models/blobs/sha256-{dec_digest}",
             f"/home/ollaya/.ollaya/models/blobs/sha256-{cfg_digest}"],
            check=True,
        )

        # 11. Cria o manifesto do modelo nativo `laya:pix-threats`
        print("Registrando manifesto do modelo laya:pix-threats otimizado...")
        manifest_raw = subprocess.check_output(
            ["docker", "exec", CONTAINER_NAME, "cat", "/home/ollaya/.ollaya/models/manifests/ollaya.dev/library/laya/multilingual"]
        ).decode()
        manifest = json.loads(manifest_raw)
        manifest["config"]["digest"] = f"sha256:{cfg_digest}"
        manifest["config"]["size"] = len(cfg_bytes)

        # Filtra camadas: removemos qualquer camada fp16 e atualizamos fp32 com o grafo otimizado
        new_layers = []
        for layer in manifest["layers"]:
            mtype = layer.get("mediaType")
            if mtype == "application/vnd.ollaya.weights":
                layer["digest"] = f"sha256:{weights_digest}"
                layer["size"] = weights_size
                new_layers.append(layer)
            elif mtype == "application/vnd.ollaya.graph.onnx":
                prec = layer.get("annotations", {}).get("org.ollaya.precision")
                if prec == "fp32":
                    layer["digest"] = f"sha256:{graph_digest}"
                    layer["size"] = graph_size
                    new_layers.append(layer)
                # omite fp16
            elif mtype == "application/vnd.ollaya.calibration":
                layer["digest"] = f"sha256:{calib_digest}"
                layer["size"] = len(calib_data)
                new_layers.append(layer)
            elif mtype == "application/vnd.ollaya.decision":
                layer["digest"] = f"sha256:{dec_digest}"
                layer["size"] = len(dec_bytes)
                new_layers.append(layer)
            else:
                new_layers.append(layer)

        manifest["layers"] = new_layers
        manifest_file = tmp_path / "pix-threats-manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2))
        subprocess.run(
            ["docker", "cp", str(manifest_file), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/manifests/ollaya.dev/library/laya/pix-threats"],
            check=True,
        )
        subprocess.run(
            ["docker", "exec", "-u", "0", CONTAINER_NAME, "chmod", "666", "/home/ollaya/.ollaya/models/manifests/ollaya.dev/library/laya/pix-threats"],
            check=True,
        )

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # 12. Reinicia o runner do laya:pix-threats em todas as réplicas ativas para recarregar o grafo
    print("Recarregando modelo em todas as instâncias ativas do Ollaya...")
    for c in [CONTAINER_NAME, "pix-ollaya-tuned-1", "pix-ollaya-tuned-2"]:
        chk = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", c], capture_output=True, text=True)
        if chk.returncode == 0 and chk.stdout.strip() == "true":
            subprocess.run(["docker", "exec", c, "/usr/bin/ollaya", "stop", "laya:pix-threats"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run(["docker", "exec", CONTAINER_NAME, "/usr/bin/ollaya", "list"], check=True)
    print("Sucesso! Modelo laya:pix-threats registrado com otimização Transformer Optimizer ONNX e max_seq_length=64.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
