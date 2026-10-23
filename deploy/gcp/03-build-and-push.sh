#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$DIR/../.." && pwd)"
source "$DIR/config.env"

PROJECT_ID=${1:-"$(gcloud config get-value project)"}

if [ -z "$PROJECT_ID" ]; then
    echo "[ERRO] Nenhum PROJECT_ID definido."
    exit 1
fi

AR_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO_NAME}"

echo "================================================================="
echo "   Pix Guard - 03: Build e Push de Imagens para o Artifact Registry"
echo "   Projeto : $PROJECT_ID"
echo "   Destino : $AR_BASE"
echo "================================================================="

cd "$ROOT_DIR"

# Função para build e push
build_and_push() {
    local SERVICE_NAME=$1
    local DOCKERFILE=$2
    local TAG="${AR_BASE}/${SERVICE_NAME}:latest"

    echo ""
    echo "-----------------------------------------------------------------"
    echo ">>> Construindo $SERVICE_NAME ($TAG)..."
    echo "-----------------------------------------------------------------"

    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        echo "[INFO] Usando Docker daemon local..."
        docker build -t "$TAG" -f "$DOCKERFILE" .
        docker push "$TAG"
    else
        echo "[INFO] Docker daemon local não detectado. Usando Google Cloud Build..."
        gcloud builds submit \
            --tag="$TAG" \
            --config=<(cat <<EOF
steps:
- name: 'gcr.io/cloud-builders/docker'
  args: ['build', '-t', '$TAG', '-f', '$DOCKERFILE', '.']
images:
- '$TAG'
EOF
) . --project="$PROJECT_ID"
    fi
    echo "[OK] $SERVICE_NAME publicado com sucesso!"
}

# 1. User Service
build_and_push "user-service" "services/user-service/Dockerfile"

# 2. Gemini Investigation Agent
build_and_push "gemini-investigation-agent" "agents/gemini-investigation-agent/Dockerfile"

# 3. Pix Gateway Service
build_and_push "pix-gateway-service" "services/pix-gateway-service/Dockerfile"

# 4. Frontend Service (Nginx Prod)
build_and_push "pix-frontend" "deploy/docker/Dockerfile.frontend.prod"

# 5. Laya GPU Service
if [ -f "deploy/docker/Dockerfile.ollaya.gpu" ]; then
    build_and_push "pix-ollaya-gpu" "deploy/docker/Dockerfile.ollaya.gpu"
fi

echo ""
echo "================================================================="
echo "   [SUCESSO] Todas as imagens foram publicadas no Artifact Registry!"
echo "   Próximo passo: ./04-deploy-cloudrun.sh $PROJECT_ID"
echo "================================================================="
