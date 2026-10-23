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
echo "   🛑 PIX GUARD - PAUSAR TODOS OS RECURSOS COM CUSTO"
echo "   Projeto: $PROJECT_ID"
echo "================================================================="

# 1. Reduzir instâncias do Cloud Run para 0 (Desliga GPU L4 e CPUs ociosas)
echo "[INFO] Reduzindo instâncias do Cloud Run para ZERO..."
SERVICES=("pix-ollaya-gpu" "pix-gateway-service" "user-service" "gemini-investigation-agent" "pix-frontend")

for SVC in "${SERVICES[@]}"; do
    if gcloud run services describe "$SVC" --region="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
        echo " -> Pausando serviço $SVC (min-instances=0)..."
        gcloud run services update "$SVC" --min-instances=0 --region="$REGION" --project="$PROJECT_ID" --quiet
    fi
done

# 2. Pausar a instância Cloud SQL PostgreSQL
echo "[INFO] Pausando instância Cloud SQL '$DB_INSTANCE_NAME'..."
if gcloud sql instances describe "$DB_INSTANCE_NAME" --project="$PROJECT_ID" >/dev/null 2>&1; then
    gcloud sql instances patch "$DB_INSTANCE_NAME" --activation-policy=NEVER --project="$PROJECT_ID" --quiet
    echo "[OK] Instância Cloud SQL pausada (cobrança de computação suspensa)!"
fi

echo ""
echo "================================================================="
echo "   ✅ TODOS OS RECURSOS COM CUSTO FORAM PAUSADOS!"
echo "   Custo ativo de GPU e Computação: R$ 0,00"
echo "   Para reativar quando for apresentar: ./deploy/gcp/resume-all.sh $PROJECT_ID"
echo "================================================================="
