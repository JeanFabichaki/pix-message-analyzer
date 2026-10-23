#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/config.env"

PROJECT_ID=${1:-"$(gcloud config get-value project)"}

if [ -z "$PROJECT_ID" ]; then
    echo "[ERRO] Nenhum PROJECT_ID definido."
    exit 1
fi

echo "================================================================="
echo "   Pix Guard - 02: Provisionamento do Cloud SQL PostgreSQL"
echo "   Projeto: $PROJECT_ID"
echo "   Região : $REGION"
echo "   Tier   : $DB_TIER (baixo custo)"
echo "================================================================="

# Recupera senha do banco do Secret Manager
DB_PASS=$(gcloud secrets versions access latest --secret=DB_PASSWORD --project="$PROJECT_ID")

# 1. Cria a instância Cloud SQL se não existir
echo "[INFO] Verificando instância Cloud SQL '$DB_INSTANCE_NAME'..."
if gcloud sql instances describe "$DB_INSTANCE_NAME" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "[INFO] Instância Cloud SQL '$DB_INSTANCE_NAME' já existe."
else
    echo "[INFO] Criando instância Cloud SQL PostgreSQL 16 '$DB_INSTANCE_NAME' (pode levar 4 a 6 minutos)..."
    gcloud sql instances create "$DB_INSTANCE_NAME" \
        --database-version=POSTGRES_16 \
        --tier="$DB_TIER" \
        --region="$REGION" \
        --root-password="$DB_PASS" \
        --storage-type=SSD \
        --storage-size=10GB \
        --storage-auto-increase \
        --project="$PROJECT_ID"
    echo "[OK] Instância Cloud SQL criada com sucesso!"
fi

# 2. Cria o banco de dados pix_guard_db se não existir
echo "[INFO] Verificando banco de dados '$DB_NAME'..."
if gcloud sql databases describe "$DB_NAME" --instance="$DB_INSTANCE_NAME" --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "[INFO] Banco de dados '$DB_NAME' já existe."
else
    echo "[INFO] Criando banco de dados '$DB_NAME'..."
    gcloud sql databases create "$DB_NAME" --instance="$DB_INSTANCE_NAME" --project="$PROJECT_ID"
    echo "[OK] Banco de dados criado!"
fi

# 3. Obtém o Connection Name da instância Cloud SQL
CONNECTION_NAME=$(gcloud sql instances describe "$DB_INSTANCE_NAME" --project="$PROJECT_ID" --format="value(connectionName)")
echo "[INFO] Cloud SQL Connection Name: $CONNECTION_NAME"

# 4. Salva a DATABASE_URL para conexão no Cloud Run via Unix Socket
DB_URL="postgresql+asyncpg://postgres:${DB_PASS}@/${DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"
echo "[INFO] Atualizando segredo DATABASE_URL no Secret Manager..."
if gcloud secrets describe DATABASE_URL --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo -n "$DB_URL" | gcloud secrets versions add DATABASE_URL --data-file=- --project="$PROJECT_ID"
else
    echo -n "$DB_URL" | gcloud secrets create DATABASE_URL --data-file=- --replication-policy="automatic" --project="$PROJECT_ID"
fi

# 5. Concede permissão de Cloud SQL Client para a Service Account do Cloud Run
PROJECT_NUM=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUM}-compute@developer.gserviceaccount.com"
echo "[INFO] Concedendo permissão cloudsql.client para $COMPUTE_SA..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/cloudsql.client" \
    --condition=None --quiet >/dev/null

echo "================================================================="
echo "   [SUCESSO] Cloud SQL provisionado e integrado!"
echo "   Connection Name: $CONNECTION_NAME"
echo "   Próximo passo: ./03-build-and-push.sh $PROJECT_ID"
echo "================================================================="
