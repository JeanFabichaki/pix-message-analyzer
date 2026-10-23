#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/config.env"

PROJECT_ID=${1:-"$(gcloud config get-value project)"}

if [ -z "$PROJECT_ID" ]; then
    echo "[ERRO] Nenhum PROJECT_ID especificado."
    exit 1
fi

echo "================================================================="
echo "   ⚡ PIX GUARD - REATIVAR RECURSOS (ZERO COLD START)"
echo "   Projeto: $PROJECT_ID"
echo "================================================================="

# 1. Reativar instâncias no Cloud Run com min-instances=1
echo "[INFO] Restaurando min-instances=1 no Cloud Run..."
SERVICES=("pix-ollaya-gpu" "pix-gateway-service" "user-service" "gemini-investigation-agent" "pix-frontend")

for SVC in "${SERVICES[@]}"; do
    if gcloud run services describe "$SVC" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
        echo " -> Reativando serviço $SVC (min-instances=1)..."
        gcloud run services update "$SVC" --min-instances=1 --region="$REGION" --project="$PROJECT_ID" --quiet
    fi
done

FRONTEND_URL=$(gcloud run services describe pix-frontend --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)" 2>/dev/null || echo "")

echo ""
echo "================================================================="
echo "   ✅ TODOS OS SERVIÇOS ESTÃO ATIVOS E PRONTOS PARA TESTES!"
if [ -n "$FRONTEND_URL" ]; then
    echo "   Acesse o sistema em: $FRONTEND_URL"
fi
echo "================================================================="
