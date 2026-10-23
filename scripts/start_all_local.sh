#!/usr/bin/env bash
# ==============================================================================
# Inicia todos os serviços localmente no Mac:
# 1. Laya FP32 Nativo na GPU Apple Silicon (Metal / MPS) - Porta 8000
# 2. User Service - Porta 8002 (SQLite local)
# 3. Gemini Investigation Agent - Porta 8003
# 4. Pix Gateway Service - Porta 8001
# 5. Frontend React (Vite) - Porta 3000
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

mkdir -p "$DIR/.logs" "$DIR/.pids"

echo "================================================================="
echo "   🚀 INICIANDO PIX GUARD LOCALMENTE (APPLE SILICON GPU - MPS)   "
echo "================================================================="

# 0. Garante a base de dados SQLite
echo "[1/6] Verificando base de dados local..."
.venv/bin/python scripts/seed_db.py --target local > /dev/null 2>&1 || true

# 1. Iniciar Laya FP32 Nativo (Apple Silicon GPU)
echo "[2/6] Iniciando Laya FP32 Nativo (Apple Silicon GPU MPS) na porta 8000..."
nohup ./scripts/run_native_laya_mac.sh < /dev/null > "$DIR/.logs/laya.log" 2>&1 &
echo $! > "$DIR/.pids/laya.pid"

# 2. Iniciar User Service
echo "[3/6] Iniciando User Service na porta 8002..."
nohup env PYTHONPATH="$DIR/services/user-service:$DIR/libs/common" .venv/bin/python -m uvicorn src.main:app \
    --app-dir "$DIR/services/user-service" \
    --host 0.0.0.0 --port 8002 < /dev/null > "$DIR/.logs/user-service.log" 2>&1 &
echo $! > "$DIR/.pids/user-service.pid"

# 3. Iniciar Gemini Investigation Agent
echo "[4/6] Iniciando Gemini Investigation Agent na porta 8003..."
nohup env PYTHONPATH="$DIR/agents/gemini-investigation-agent:$DIR/libs/common" .venv/bin/python -m uvicorn src.main:app \
    --app-dir "$DIR/agents/gemini-investigation-agent" \
    --host 0.0.0.0 --port 8003 < /dev/null > "$DIR/.logs/gemini-agent.log" 2>&1 &
echo $! > "$DIR/.pids/gemini-agent.pid"

# 4. Iniciar Pix Gateway Service
echo "[5/6] Iniciando Pix Gateway Service na porta 8001..."
nohup env PYTHONPATH="$DIR/services/pix-gateway-service:$DIR/libs/common" .venv/bin/python -m uvicorn src.main:app \
    --app-dir "$DIR/services/pix-gateway-service" \
    --host 0.0.0.0 --port 8001 < /dev/null > "$DIR/.logs/gateway.log" 2>&1 &
echo $! > "$DIR/.pids/gateway.pid"

# 5. Iniciar Frontend React
echo "[6/6] Iniciando Frontend React (Vite) na porta 3000..."
nohup env CI=true "$DIR/services/frontend-service/node_modules/.bin/vite" --host 0.0.0.0 --port 3000 "$DIR/services/frontend-service" < /dev/null > "$DIR/.logs/frontend.log" 2>&1 &
echo $! > "$DIR/.pids/frontend.pid"

echo ""
echo "Aguardando serviços ficarem prontos..."
for i in {1..20}; do
    if curl -s http://127.0.0.1:8000/health >/dev/null 2>&1 && \
       curl -s http://127.0.0.1:8001/health >/dev/null 2>&1 && \
       curl -s http://127.0.0.1:8002/health >/dev/null 2>&1 && \
       curl -s http://127.0.0.1:8003/health >/dev/null 2>&1 && \
       curl -s http://127.0.0.1:3000 >/dev/null 2>&1; then
        echo ""
        echo "================================================================="
        echo "   ✅ TODOS OS SERVIÇOS ESTÃO ONLINE E OPERACIONAIS!            "
        echo "================================================================="
        echo "   📱 Frontend React:      http://localhost:3000"
        echo "   ⚡ Pix Gateway:          http://localhost:8001/docs"
        echo "   🧠 Laya Nativo (MPS):    http://localhost:8000/health"
        echo "   👤 User Service:         http://localhost:8002/docs"
        echo "   🕵️ Gemini Agent:         http://localhost:8003/docs"
        echo "================================================================="
        echo "Para parar todos os serviços: ./scripts/stop_all_local.sh"
        exit 0
    fi
    sleep 1
    printf "."
done

echo ""
echo "[AVISO] Alguns serviços ainda estão subindo. Verifique os logs em .logs/"
