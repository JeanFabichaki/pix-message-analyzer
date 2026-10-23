#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/config.env"

PROJECT_ID=${1:-""}

if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID="pix-guard-$(date +%s | cut -c 6-10)"
    echo "Nenhum PROJECT_ID fornecido. Gerando ID único: $PROJECT_ID"
fi

echo "================================================================="
echo "   Pix Guard - 00: Inicialização de Projeto no Google Cloud"
echo "   Projeto: $PROJECT_ID"
echo "   Região : $REGION"
echo "   Billing: $BILLING_ACCOUNT_ID"
echo "================================================================="

# 1. Verifica autenticação gcloud
CURRENT_USER=$(gcloud config get-value account 2>/dev/null || true)
if [ -z "$CURRENT_USER" ]; then
    echo "[ERRO] gcloud CLI não autenticado. Execute 'gcloud auth login' antes de continuar."
    exit 1
fi
echo "[OK] Autenticado como: $CURRENT_USER"

# 2. Cria o projeto se não existir
if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
    echo "[INFO] Projeto $PROJECT_ID já existe. Continuando..."
else
    echo "[INFO] Criando novo projeto $PROJECT_ID..."
    gcloud projects create "$PROJECT_ID" --name="Pix Guard Cloud"
    echo "[OK] Projeto criado com sucesso!"
fi

# 3. Vincula faturamento (Billing Account)
echo "[INFO] Vinculando projeto à conta de faturamento $BILLING_ACCOUNT_ID..."
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT_ID"
echo "[OK] Faturamento ativado com sucesso!"

# 4. Configura projeto no gcloud local
gcloud config set project "$PROJECT_ID"

# 5. Habilita as APIs necessárias
echo "[INFO] Habilitando APIs essenciais do Google Cloud..."
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    firestore.googleapis.com \
    generativelanguage.googleapis.com \
    compute.googleapis.com \
    iam.googleapis.com \
    --project="$PROJECT_ID"

echo "[OK] APIs habilitadas com sucesso!"

# 6. Cria repositório no Artifact Registry se não existir
echo "[INFO] Verificando repositório Artifact Registry '$AR_REPO_NAME' em $REGION..."
if gcloud artifacts repositories describe "$AR_REPO_NAME" --location="$REGION" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "[INFO] Repositório '$AR_REPO_NAME' já existe."
else
    echo "[INFO] Criando repositório Docker '$AR_REPO_NAME'..."
    gcloud artifacts repositories create "$AR_REPO_NAME" \
        --repository-format=docker \
        --location="$REGION" \
        --description="Repositório de contêineres do Pix Guard" \
        --project="$PROJECT_ID"
    echo "[OK] Repositório Artifact Registry criado!"
fi

# 7. Configura credencial local do Docker para push
echo "[INFO] Configurando autenticação Docker para $REGION-docker.pkg.dev..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "================================================================="
echo "   [SUCESSO] Projeto $PROJECT_ID configurado e pronto!"
echo "   Próximo passo: ./01-setup-secrets.sh $PROJECT_ID"
echo "================================================================="
