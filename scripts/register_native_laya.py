#!/usr/bin/env python3
"""Registra o modelo Laya retreinado nativamente no Ollaya (C++ / ONNX Runtime).

O Ollaya executa grafos ONNX (application/vnd.ollaya.graph.onnx) que usam inicializadores
com tensores externos (data_location=1). Esses grafos contêm referências relativas para
o blob de pesos (location) e os deslocamentos em bytes (offset/length).

Este script:
1. Extrai os grafos originais FP32 e FP16 do Laya multilíngue no Ollaya.
2. Recalcula os offsets em bytes com base no cabeçalho do `model.safetensors` retreinado.
3. Patcha os grafos ONNX para apontar diretamente para o hash do blob retreinado.
4. Gera o blob de calibração de temperatura a partir de `rl_agent_config.json`.
5. Publica os grafos, pesos e manifesto `laya:pix-threats` diretamente no Ollaya.
"""
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

# Garante que roda com o Python do .venv caso o python do sistema não tenha dependências (como onnx)
try:
    import onnx  # noqa: F401
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

    print(f"Calculando SHA-256 de {MODEL_PATH}...")
    weights_digest = compute_sha256(MODEL_PATH)
    weights_size = MODEL_PATH.stat().st_size
    weights_blob = f"sha256-{weights_digest}"
    print(f"Pesos retreinados: {weights_digest} ({weights_size} bytes)")

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

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # 3. Extrai grafos base do Laya multilíngue no container
        base_fp32 = tmp_path / "graph_fp32.onnx"
        base_fp16 = tmp_path / "graph_fp16.onnx"
        subprocess.run(
            ["docker", "cp", f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/sha256-ace962240e4cf7c69c0e65ea7224aa791777880003950a81347a206f6bfbed45", str(base_fp32)],
            check=True,
        )
        subprocess.run(
            ["docker", "cp", f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/sha256-236fbdec33bd2aa44ee4dae43a83173ef3351c4eed6afd073df387c9486ec7d6", str(base_fp16)],
            check=True,
        )

        # 4. Patcha os grafos ONNX para apontar para os offsets dos pesos retreinados
        print("Adaptando grafos ONNX (FP32 e FP16) para os tensores retreinados...")
        patched_fp32 = tmp_path / "patched_fp32.onnx"
        patched_fp16 = tmp_path / "patched_fp16.onnx"
        patch_onnx_graph(base_fp32, patched_fp32, st_header, base_data_start, weights_blob)
        patch_onnx_graph(base_fp16, patched_fp16, st_header, base_data_start, weights_blob)

        fp32_digest = compute_sha256(patched_fp32)
        fp32_size = patched_fp32.stat().st_size
        fp16_digest = compute_sha256(patched_fp16)
        fp16_size = patched_fp16.stat().st_size

        # 5. Blob de calibração (temperatura)
        temperatures = [1.0, 1.0, 1.0]
        if CFG_PATH.is_file():
            cfg_data = json.loads(CFG_PATH.read_text())
            temperatures = cfg_data.get("temperature", temperatures)
        calib_data = json.dumps({"temperature": temperatures, "temperature_by_options": {}}, indent=2).encode()
        calib_digest = hashlib.sha256(calib_data).hexdigest()
        calib_file = tmp_path / f"sha256-{calib_digest}"
        calib_file.write_bytes(calib_data)

        # 6. Copia blobs para o container
        print(f"Copiando pesos e grafos para o container {CONTAINER_NAME}...")
        subprocess.run(["docker", "cp", str(MODEL_PATH), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/{weights_blob}"], check=True)
        subprocess.run(["docker", "cp", str(patched_fp32), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/sha256-{fp32_digest}"], check=True)
        subprocess.run(["docker", "cp", str(patched_fp16), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/sha256-{fp16_digest}"], check=True)
        subprocess.run(["docker", "cp", str(calib_file), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/sha256-{calib_digest}"], check=True)

        # 7. Cria o manifesto do modelo nativo `laya:pix-threats`
        print("Registrando manifesto do modelo laya:pix-threats...")
        manifest_raw = subprocess.check_output(
            ["docker", "exec", CONTAINER_NAME, "cat", "/home/ollaya/.ollaya/models/manifests/ollaya.dev/library/laya/multilingual"]
        ).decode()
        manifest = json.loads(manifest_raw)
        for layer in manifest["layers"]:
            mtype = layer.get("mediaType")
            if mtype == "application/vnd.ollaya.weights":
                layer["digest"] = f"sha256:{weights_digest}"
                layer["size"] = weights_size
            elif mtype == "application/vnd.ollaya.graph.onnx":
                prec = layer.get("annotations", {}).get("org.ollaya.precision")
                if prec == "fp32":
                    layer["digest"] = f"sha256:{fp32_digest}"
                    layer["size"] = fp32_size
                elif prec == "fp16":
                    layer["digest"] = f"sha256:{fp16_digest}"
                    layer["size"] = fp16_size
            elif mtype == "application/vnd.ollaya.calibration":
                layer["digest"] = f"sha256:{calib_digest}"
                layer["size"] = len(calib_data)

        manifest_file = tmp_path / "pix-threats-manifest.json"
        manifest_file.write_text(json.dumps(manifest, indent=2))
        subprocess.run(
            ["docker", "cp", str(manifest_file), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/manifests/ollaya.dev/library/laya/pix-threats"],
            check=True,
        )

    # 8. Reinicia o runner do laya:pix-threats para recarregar o grafo
    print("Recarregando modelo no Ollaya...")
    for c in [CONTAINER_NAME, "pix-ollaya-tuned-1", "pix-ollaya-tuned-2", "pix-ollaya-2"]:
        subprocess.run(["docker", "exec", c, "/usr/bin/ollaya", "stop", "laya:pix-threats"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["docker", "exec", CONTAINER_NAME, "/usr/bin/ollaya", "list"], check=True)
    print("Sucesso! Modelo laya:pix-threats registrado com pesos retreinados e aceleração ONNX.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
