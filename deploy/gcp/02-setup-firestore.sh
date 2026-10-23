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
echo "   Pix Guard - 02: Configuração do Google Cloud Firestore"
echo "   Projeto : $PROJECT_ID"
echo "   Região  : $REGION"
echo "   Tipo    : FIRESTORE_NATIVE (Serverless)"
echo "================================================================="

# Habilita API do Firestore
gcloud services enable firestore.googleapis.com --project="$PROJECT_ID" --quiet

# Verifica se o database padrão já existe
if gcloud firestore databases describe --database="(default)" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "[INFO] Firestore database '(default)' já existe."
else
    echo "[INFO] Criando Firestore Native database em $REGION..."
    gcloud firestore databases create \
        --location="$REGION" \
        --type=firestore-native \
        --database="(default)" \
        --project="$PROJECT_ID" \
        --quiet
fi

echo "[OK] Firestore configurado com sucesso e pronto para uso!"
