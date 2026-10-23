#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DIR/config.env"

PROJECT_ID=${1:-""}

if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID="pix-guard-$(date +%s | cut -c 6-10)"
fi

echo "================================================================="
echo "   🚀 PIX GUARD - DEPLOY AUTOMATIZADO COMPLETO NO GOOGLE CLOUD"
echo "   Projeto       : $PROJECT_ID"
echo "   Região        : $REGION"
echo "   Min Instances : $MIN_INSTANCES (Zero Cold Start)"
echo "   Acelerador    : $GPU_COUNT x $GPU_TYPE"
echo "================================================================="

# Etapa 0: Projeto e APIs
"$DIR/00-init-project.sh" "$PROJECT_ID"

# Etapa 1: Segredos e Chaves
"$DIR/01-setup-secrets.sh" "$PROJECT_ID"

# Etapa 2: Banco de Dados Serverless (Google Cloud Firestore)
"$DIR/02-setup-firestore.sh" "$PROJECT_ID"

# Etapa 3: Build e Push das Imagens
"$DIR/03-build-and-push.sh" "$PROJECT_ID"

# Etapa 4: Deploy no Cloud Run
"$DIR/04-deploy-cloudrun.sh" "$PROJECT_ID"

echo ""
echo "================================================================="
echo "   ✅ DEPLOY CONCLUÍDO COM SUCESSO!"
echo "================================================================="
