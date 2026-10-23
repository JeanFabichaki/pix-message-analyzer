#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/config.env"

PROJECT_ID=${1:-"$(gcloud config get-value project)"}

if [ -z "$PROJECT_ID" ]; then
    echo "[ERRO] Nenhum PROJECT_ID definido."
    exit 1
fi

AR_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO_NAME}"
CONNECTION_NAME=$(gcloud sql instances describe "$DB_INSTANCE_NAME" --project="$PROJECT_ID" --format="value(connectionName)" 2>/dev/null || true)

echo "================================================================="
echo "   Pix Guard - 04: Deploy dos Serviços no Google Cloud Run"
echo "   Projeto       : $PROJECT_ID"
echo "   Região        : $REGION"
echo "   Min Instances : $MIN_INSTANCES (Zero Cold Start)"
echo "   GPU           : $GPU_COUNT x $GPU_TYPE"
echo "================================================================="

if [ -z "$CONNECTION_NAME" ]; then
    echo "[ERRO] Instância Cloud SQL '$DB_INSTANCE_NAME' não encontrada. Execute ./02-setup-db.sh primeiro."
    exit 1
fi

# 1. Deploy Laya Model Server no Cloud Run
echo ""
echo ">>> [1/5] Implantando pix-ollaya-gpu (Zero Cold Start)..."
gcloud run deploy pix-ollaya-gpu \
    --image="${AR_BASE}/pix-ollaya-gpu:latest" \
    --region="$REGION" \
    --cpu=4 \
    --memory=8Gi \
    --min-instances="$MIN_INSTANCES" \
    --max-instances=3 \
    --execution-environment=gen2 \
    --no-cpu-throttling \
    --port=8000 \
    --allow-unauthenticated \
    --project="$PROJECT_ID" \
    --quiet

OLLAYA_URL=$(gcloud run services describe pix-ollaya-gpu --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")
echo "[OK] Laya GPU online em: $OLLAYA_URL"

# 2. Deploy User Service
echo ""
echo ">>> [2/5] Implantando user-service..."
gcloud run deploy user-service \
    --image="${AR_BASE}/user-service:latest" \
    --region="$REGION" \
    --cpu=1 \
    --memory=512Mi \
    --min-instances="$MIN_INSTANCES" \
    --set-secrets="DATABASE_URL=DATABASE_URL:latest" \
    --add-cloudsql-instances="$CONNECTION_NAME" \
    --port=8002 \
    --allow-unauthenticated \
    --project="$PROJECT_ID" \
    --quiet

USER_SERVICE_URL=$(gcloud run services describe user-service --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")
echo "[OK] User Service online em: $USER_SERVICE_URL"

# 3. Deploy Gemini Investigation Agent
echo ""
echo ">>> [3/5] Implantando gemini-investigation-agent..."
gcloud run deploy gemini-investigation-agent \
    --image="${AR_BASE}/gemini-investigation-agent:latest" \
    --region="$REGION" \
    --cpu=1 \
    --memory=512Mi \
    --min-instances="$MIN_INSTANCES" \
    --set-secrets="DATABASE_URL=DATABASE_URL:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest" \
    --set-env-vars="USER_SERVICE_URL=$USER_SERVICE_URL,GEMINI_MODEL=$GEMINI_MODEL" \
    --add-cloudsql-instances="$CONNECTION_NAME" \
    --port=8003 \
    --allow-unauthenticated \
    --project="$PROJECT_ID" \
    --quiet

GEMINI_AGENT_URL=$(gcloud run services describe gemini-investigation-agent --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")
echo "[OK] Gemini Agent online em: $GEMINI_AGENT_URL"

# 4. Deploy Pix Gateway Service
echo ""
echo ">>> [4/5] Implantando pix-gateway-service..."
gcloud run deploy pix-gateway-service \
    --image="${AR_BASE}/pix-gateway-service:latest" \
    --region="$REGION" \
    --cpu=1 \
    --memory=512Mi \
    --min-instances="$MIN_INSTANCES" \
    --set-env-vars="USER_SERVICE_URL=$USER_SERVICE_URL,GEMINI_AGENT_URL=$GEMINI_AGENT_URL,OLLAYA_BASE_URL=$OLLAYA_URL,LAYA_TUNED_BASE_URL=$OLLAYA_URL,LAYA_TUNED_MODEL=laya:pix-threats,OLLAYA_TIMEOUT_SECONDS=25.0" \
    --port=8001 \
    --allow-unauthenticated \
    --project="$PROJECT_ID" \
    --quiet

GATEWAY_URL=$(gcloud run services describe pix-gateway-service --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")
echo "[OK] Pix Gateway online em: $GATEWAY_URL"

# 5. Deploy Frontend Service (Nginx)
echo ""
echo ">>> [5/5] Implantando pix-frontend..."
gcloud run deploy pix-frontend \
    --image="${AR_BASE}/pix-frontend:latest" \
    --region="$REGION" \
    --cpu=1 \
    --memory=512Mi \
    --min-instances="$MIN_INSTANCES" \
    --set-env-vars="GATEWAY_URL=$GATEWAY_URL,USER_SERVICE_URL=$USER_SERVICE_URL,GEMINI_AGENT_URL=$GEMINI_AGENT_URL" \
    --port=8080 \
    --allow-unauthenticated \
    --project="$PROJECT_ID" \
    --quiet

FRONTEND_URL=$(gcloud run services describe pix-frontend --region="$REGION" --project="$PROJECT_ID" --format="value(status.url)")

echo ""
echo "================================================================="
echo "   🎉 DEPLOY COMPLETO NO GOOGLE CLOUD!"
echo "================================================================="
echo "   Interface Web (Frontend) : $FRONTEND_URL"
echo "   Pix Gateway API          : $GATEWAY_URL"
echo "   User Service API         : $USER_SERVICE_URL"
echo "   Gemini Agent API         : $GEMINI_AGENT_URL"
echo "   Laya GPU Model Server    : $OLLAYA_URL"
echo "================================================================="
