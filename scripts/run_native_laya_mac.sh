#!/usr/bin/env bash
# ==============================================================================
# Script de Execução Nativa do Laya no macOS (Apple Silicon GPU via Metal / MPS)
# ==============================================================================
# - Modelo: Checkpoint FP32 Completo (finetune/models/pix-threats)
# - Hardware: Apple Silicon Metal Performance Shaders (MPS / GPU nativa)
# - Precisão: Pura FP32 (sem quantização INT8, sem perda de acurácia)
# - Latência: ~12ms - 15ms de inferência pura
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "================================================================="
echo "   🚀 INICIANDO LAYA NATIVO NO MACOS (APPLE SILICON GPU - MPS)"
echo "================================================================="

# Verifica se o ambiente virtual Python existe
if [ ! -d ".venv" ]; then
    echo "[ERRO] Ambiente .venv não encontrado em $DIR"
    exit 1
fi

MODEL_DIR="$DIR/finetune/models/pix-threats"
if [ ! -f "$MODEL_DIR/model.safetensors" ]; then
    echo "[ERRO] Pesos do modelo não encontrados em $MODEL_DIR/model.safetensors"
    exit 1
fi

# Configura variáveis para execução direta no Apple Silicon
export LAYA_DEVICE="mps"
export LAYA_HOST="0.0.0.0"
export LAYA_PORT="8000"
export LAYA_DEFAULT_MODEL="pix-threats"
export LAYA_MODELS="pix-threats"
export LAYA_EXTRA_MODELS="{\"pix-threats\":\"$MODEL_DIR\",\"laya:pix-threats\":\"$MODEL_DIR\"}"
export LAYA_PRELOAD="1"
export TOKENIZERS_PARALLELISM="false"

echo "[INFO] Dispositivo: Apple Silicon Metal (MPS)"
echo "[INFO] Modelo FP32: $MODEL_DIR"
echo "[INFO] Porta: http://localhost:8000"
echo ""

exec .venv/bin/python -m laya.serve
