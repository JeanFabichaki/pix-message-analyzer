#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/config.env"

PROJECT_ID=${1:-"$(gcloud config get-value project)"}

if [ -z "$PROJECT_ID" ]; then
    echo "[ERRO] Nenhum PROJECT_ID definido. Passe como argumento ou configure no gcloud."
    exit 1
fi

echo "================================================================="
echo "   Pix Guard - 01: Configuração do Secret Manager"
echo "   Projeto: $PROJECT_ID"
echo "================================================================="

# Extrai GEMINI_API_KEY do .env local se existir
ENV_FILE="$DIR/../../.env"
GEMINI_KEY=""
if [ -f "$ENV_FILE" ]; then
    GEMINI_KEY=$(grep -E '^GEMINI_API_KEY=' "$ENV_FILE" | cut -d '=' -f2- | tr -d '"' | tr -d "'" || true)
fi

if [ -z "$GEMINI_KEY" ]; then
    echo -n "Informe sua chave da API Google Gemini (GEMINI_API_KEY): "
    read -r -s GEMINI_KEY
    echo ""
fi

if [ -z "$GEMINI_KEY" ]; then
    echo "[AVISO] Nenhuma GEMINI_API_KEY fornecida. O agente usará MOCK_GEMINI=true ou modo BYPASS."
    GEMINI_KEY="mock-placeholder-key"
fi

# Cria ou atualiza o segredo GEMINI_API_KEY
echo "[INFO] Gravando GEMINI_API_KEY no Secret Manager..."
if gcloud secrets describe GEMINI_API_KEY --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo -n "$GEMINI_KEY" | gcloud secrets versions add GEMINI_API_KEY --data-file=- --project="$PROJECT_ID"
else
    echo -n "$GEMINI_KEY" | gcloud secrets create GEMINI_API_KEY --data-file=- --replication-policy="automatic" --project="$PROJECT_ID"
fi
echo "[OK] Segredo GEMINI_API_KEY configurado!"

# Concede permissão de leitura de segredos e acesso ao Firestore para a Service Account padrão do Cloud Run
PROJECT_NUM=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUM}-compute@developer.gserviceaccount.com"

echo "[INFO] Concedendo permissões secretmanager.secretAccessor e datastore.user para $COMPUTE_SA..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --condition=None --quiet >/dev/null

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/datastore.user" \
    --condition=None --quiet >/dev/null

echo "================================================================="
echo "   [SUCESSO] Segredos e permissões configurados!"
echo "   Próximo passo: ./02-setup-firestore.sh $PROJECT_ID"
echo "================================================================="
