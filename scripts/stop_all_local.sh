#!/usr/bin/env bash
# ==============================================================================
# Para todos os serviços iniciados por start_all_local.sh
# ==============================================================================
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "================================================================="
echo "   🛑 ENCERRANDO SERVIÇOS DO PIX GUARD                           "
echo "================================================================="

if [ -d "$DIR/.pids" ]; then
    for PID_FILE in "$DIR"/.pids/*.pid; do
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            NAME=$(basename "$PID_FILE" .pid)
            if kill -0 "$PID" 2>/dev/null; then
                echo " -> Encerrando $NAME (PID $PID)..."
                kill "$PID" 2>/dev/null || true
            fi
            rm -f "$PID_FILE"
        fi
    done
fi

# Mata eventuais processos remanescentes nas portas padrão
for PORT in 8000 8001 8002 8003 3000; do
    PIDS=$(lsof -ti :$PORT 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo " -> Liberando porta $PORT (PID $PIDS)..."
        kill -9 $PIDS 2>/dev/null || true
    fi
done

echo "✅ Todos os serviços foram encerrados."
