#!/usr/bin/env python3
"""Registra o modelo Laya retreinado nativamente para GPU no Ollaya (CUDA / ONNX Runtime).

Diferente da versão para CPU:
1. NÃO aplica quantização dinâmica INT8 (que era específica para SIMD de CPU).
2. Mantém a precisão pura FP32/FP16 para máxima fidelidade e aceleração nativa via Tensor Cores.
3. Não impõe restrições de threads de CPU (OMP_NUM_THREADS).
4. Vincula diretamente os tensores retreinados e a calibração de temperatura do RLCD.
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

# Mock do módulo torch caso não esteja instalado no ambiente
if "torch" not in sys.modules:
    torch_mod = types.ModuleType("torch")
    torch_mod.version = types.SimpleNamespace(cuda="12.1", hip=None)
    sys.modules["torch"] = torch_mod

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
CONTAINER_NAME = os.getenv("OLLAYA_CONTAINER_NAME", "pix-ollaya")


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

    print(f"Verificando pesos retreinados para GPU em {MODEL_PATH}...")

    # 1. Verifica container Ollaya
    res = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", CONTAINER_NAME],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0 or res.stdout.strip() != "true":
        print(f"[ERRO] Container {CONTAINER_NAME} não está em execução.")
        return 1

    # 2. Lê cabeçalho do safetensors
    with open(MODEL_PATH, "rb") as f:
        h_len = struct.unpack("<Q", f.read(8))[0]
        st_header = json.loads(f.read(h_len))
    base_data_start = 8 + h_len

    tmpdir = tempfile.mkdtemp(prefix="ollaya_gpu_")
    tmp_path = Path(tmpdir)

    try:
        weights_name = "model.safetensors"
        local_weights = tmp_path / weights_name
        os.link(MODEL_PATH, local_weights)

        # 3. Extrai grafo base FP32
        base_fp32 = tmp_path / "graph_fp32.onnx"
        print(f"Extraindo grafo base do container {CONTAINER_NAME}...")
        subprocess.run(
            ["docker", "cp", f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/sha256-ace962240e4cf7c69c0e65ea7224aa791777880003950a81347a206f6bfbed45", str(base_fp32)],
            check=True,
        )

        # 4. Patcha com offsets dos pesos retreinados
        print("Vinculando tensores retreinados...")
        patched_base = tmp_path / "patched_base.onnx"
        patch_onnx_graph(base_fp32, patched_base, st_header, base_data_start, weights_name)

        # 5. Otimização de grafo (fusão de atenção e layer norm)
        print("Otimizando grafo para inferência em GPU...")
        opt_options = FusionOptions("bert")
        opt_model = optimizer.optimize_model(
            str(patched_base),
            "bert",
            num_heads=12,
            hidden_size=768,
            optimization_options=opt_options,
        )

        # 6. Salva modelo otimizado sem quantização (precisão nativa para Tensor Cores CUDA)
        opt_graph_path = tmp_path / "opt_graph.onnx"
        opt_model.save_model_to_file(str(opt_graph_path), use_external_data_format=True, all_tensors_to_one_file=True)

        opt_data_path = tmp_path / "opt_graph.onnx.data"
        weights_digest = compute_sha256(opt_data_path)
        weights_size = opt_data_path.stat().st_size
        weights_blob = f"sha256-{weights_digest}"
        print(f"Pesos nativos para GPU (FP32/CUDA): {weights_blob} ({weights_size / (1024*1024):.1f} MB)")

        # 7. Atualiza apontamento de blob no grafo
        m = onnx.load(str(opt_graph_path), load_external_data=False)
        for init in m.graph.initializer:
            for entry in init.external_data:
                if entry.key == "location":
                    entry.value = weights_blob

        final_graph_path = tmp_path / "final_gpu.onnx"
        onnx.save(m, str(final_graph_path))

        graph_digest = compute_sha256(final_graph_path)
        graph_size = final_graph_path.stat().st_size
        graph_blob = f"sha256-{graph_digest}"
        print(f"Grafo GPU final: {graph_blob} ({graph_size} bytes)")

        # 8. Calibração de temperatura do RLCD
        temperatures = [1.0, 1.0, 1.0]
        if CFG_PATH.is_file():
            cfg_data = json.loads(CFG_PATH.read_text())
            temperatures = cfg_data.get("temperature", temperatures)
        calib_data = json.dumps({"temperature": temperatures, "temperature_by_options": {}}, indent=2).encode()
        calib_digest = hashlib.sha256(calib_data).hexdigest()
        calib_file = tmp_path / f"sha256-{calib_digest}"
        calib_file.write_bytes(calib_data)

        # 9. Configuração e decisão
        raw_dec = subprocess.check_output(
            ["docker", "exec", CONTAINER_NAME, "cat", "/home/ollaya/.ollaya/models/blobs/sha256-70fd2a20d3e0f259063958071637b2047a01f4d8dd5681ab2f3d647ee9193fac"]
        )
        dec_data = json.loads(raw_dec)
        dec_bytes = json.dumps(dec_data, indent=2).encode("utf-8")
        dec_digest = hashlib.sha256(dec_bytes).hexdigest()
        dec_file = tmp_path / f"sha256-{dec_digest}"
        dec_file.write_bytes(dec_bytes)

        raw_cfg = subprocess.check_output(
            ["docker", "exec", CONTAINER_NAME, "cat", "/home/ollaya/.ollaya/models/blobs/sha256-05b7fd1e50a9bfc27e9547783b382f2bb2769cb4adc0eebb85bb57ae3060f06d"]
        )
        cfg_data = json.loads(raw_cfg)
        cfg_bytes = json.dumps(cfg_data, indent=2).encode("utf-8")
        cfg_digest = hashlib.sha256(cfg_bytes).hexdigest()
        cfg_file = tmp_path / f"sha256-{cfg_digest}"
        cfg_file.write_bytes(cfg_bytes)

        # 10. Copia blobs para o container
        print(f"Publicando blobs no container {CONTAINER_NAME}...")
        subprocess.run(["docker", "cp", str(opt_data_path), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/{weights_blob}"], check=True)
        subprocess.run(["docker", "cp", str(final_graph_path), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/{graph_blob}"], check=True)
        subprocess.run(["docker", "cp", str(calib_file), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/sha256-{calib_digest}"], check=True)
        subprocess.run(["docker", "cp", str(dec_file), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/sha256-{dec_digest}"], check=True)
        subprocess.run(["docker", "cp", str(cfg_file), f"{CONTAINER_NAME}:/home/ollaya/.ollaya/models/blobs/{cfg_digest}"], check=True)

        subprocess.run(
            ["docker", "exec", "-u", "0", CONTAINER_NAME, "chmod", "666",
             f"/home/ollaya/.ollaya/models/blobs/{weights_blob}",
             f"/home/ollaya/.ollaya/models/blobs/{graph_blob}",
             f"/home/ollaya/.ollaya/models/blobs/sha256-{calib_digest}",
             f"/home/ollaya/.ollaya/models/blobs/sha256-{dec_digest}",
             f"/home/ollaya/.ollaya/models/blobs/sha256-{cfg_digest}"],
            check=True,
        )

        # 11. Atualiza manifesto do modelo
        manifest_raw = subprocess.check_output(
            ["docker", "exec", CONTAINER_NAME, "cat", "/home/ollaya/.ollaya/models/manifests/ollaya.dev/library/laya/multilingual"]
        ).decode()
        manifest = json.loads(manifest_raw)
        manifest["config"]["digest"] = f"sha256:{cfg_digest}"
        manifest["config"]["size"] = len(cfg_bytes)

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

    print("Sucesso! Modelo nativo para GPU laya:pix-threats registrado com precisão plena.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
