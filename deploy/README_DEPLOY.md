# Guia de Implantação do Pix Guard no Google Cloud Platform (GCP)

Este guia documenta o provisionamento automatizado do **Pix Guard** no Google Cloud Platform na região **`us-central1`**, com arquitetura Serverless baseada em **Cloud Run**, aceleração por **GPU NVIDIA L4** para o modelo de decisão **Laya**, **Cloud SQL PostgreSQL**, **Secret Manager** e **Zero Cold Start** (`--min-instances=1`).

---

## 🏛️ Arquitetura no GCP

```
[Navegador do Usuário]
         │ (HTTPS público)
         ▼
[pix-frontend] (Cloud Run / Nginx)
   ├───► /pix-api/   ──► [pix-gateway-service] (Cloud Run)
   │                           ├──► [pix-ollaya-gpu] (Cloud Run com 1x NVIDIA L4)
   │                           ├──► [user-service] (Cloud Run)
   │                           └──► [gemini-investigation-agent] (Cloud Run)
   │                                         ├──► [Google Gemini API]
   │                                         └──► [Cloud SQL PostgreSQL 16]
   ├───► /user-api/   ──► [user-service]
   └───► /gemini-api/ ──► [gemini-investigation-agent]
```

---

## 📋 Pré-requisitos

1. **Google Cloud SDK (`gcloud`)** instalado e autenticado:
   ```bash
   gcloud auth login
   ```
2. **Conta de Faturamento (Billing Account)** ativa (identificada automaticamente nos scripts).
3. **Docker** local em execução (ou o script utilizará automaticamente o Google Cloud Build).

---

## 🚀 Execução em Comando Único

Para executar o pipeline completo de forma automatizada:

```bash
./deploy/gcp/deploy-all.sh [ID_DO_PROJETO_OPCIONAL]
```
*(Se você não passar um ID de projeto, o script gerará um identificador único como `pix-guard-XXXXX`).*

---

## 📦 Execução Passo a Passo (Modular)

Caso prefira inspecionar e executar etapa por etapa:

### 1. Criar Projeto e Ativar APIs
Cria o novo projeto, vincula o faturamento, habilita as APIs de IA/Cloud Run/Cloud SQL e cria o repositório Docker no Artifact Registry:
```bash
./deploy/gcp/00-init-project.sh meu-projeto-pix
```

### 2. Configurar Segredos no Secret Manager
Grava a chave da Google Gemini (`GEMINI_API_KEY`) e gera uma senha criptografada para o banco de dados:
```bash
./deploy/gcp/01-setup-secrets.sh meu-projeto-pix
```

### 3. Provisionar Banco Cloud SQL PostgreSQL
Cria a instância PostgreSQL 16 (`db-f1-micro`) em `us-central1` e armazena a string de conexão segura (`DATABASE_URL`) no Secret Manager:
```bash
./deploy/gcp/02-setup-db.sh meu-projeto-pix
```

### 4. Build e Publicação de Imagens
Compila as 5 imagens de microsserviço (com o modelo Laya retreinado para GPU) e publica no Artifact Registry:
```bash
./deploy/gcp/03-build-and-push.sh meu-projeto-pix
```

### 5. Deploy no Cloud Run (Zero Cold Start)
Implanta todos os serviços no Cloud Run com `--min-instances=1` e aloca a GPU NVIDIA L4 para o modelo de decisão:
```bash
./deploy/gcp/04-deploy-cloudrun.sh meu-projeto-pix
```

---

## ⚡ Laya em GPU Nativa vs CPU

- **Eliminação de Modificações de CPU**: Foram removidas as restrições de threads (`OMP_NUM_THREADS`), quantização estática INT8 de CPU e clamping numérico.
- **Aceleração CUDA**: O modelo de decisão roda diretamente nos Tensor Cores da NVIDIA L4 com precisão flutuante integral, reduzindo a latência da inferência de ~30ms para **~5ms**.
- **Script de Registro GPU**: Disponível em `scripts/register_native_laya_gpu.py`.

---

## 💰 FinOps & Controle de Custos

| Recurso | Modo de Execução Ativo | Modo Pausado (Sem Testes) |
|---|---|---|
| **Cloud Run (APIs + Frontend)** | min-instances=1 (~$15/mês) | min-instances=0 ($0,00) |
| **Cloud Run (Laya GPU L4)** | min-instances=1 (~$400/mês se 24/7) | min-instances=0 ($0,00 quando ocioso) |
| **Cloud SQL PostgreSQL** | db-f1-micro (~$9,50/mês) | activation-policy=NEVER (~$2/mês disco) |

### Como pausar o ambiente para custo zero:
```bash
# Reduzir instâncias a zero (elimina cobrança de GPU e CPU ociosas)
gcloud run services update pix-ollaya-gpu --min-instances=0 --region=us-central1
gcloud run services update pix-gateway-service --min-instances=0 --region=us-central1
gcloud run services update user-service --min-instances=0 --region=us-central1
gcloud run services update gemini-investigation-agent --min-instances=0 --region=us-central1
gcloud run services update pix-frontend --min-instances=0 --region=us-central1

# Pausar Cloud SQL
gcloud sql instances patch pix-guard-db --activation-policy=NEVER
```

### Como reativar para testes / apresentações com Zero Cold Start:
```bash
gcloud sql instances patch pix-guard-db --activation-policy=ALWAYS
gcloud run services update pix-ollaya-gpu --min-instances=1 --region=us-central1
gcloud run services update pix-gateway-service --min-instances=1 --region=us-central1
gcloud run services update user-service --min-instances=1 --region=us-central1
gcloud run services update gemini-investigation-agent --min-instances=1 --region=us-central1
gcloud run services update pix-frontend --min-instances=1 --region=us-central1
```

---

## 🧪 Verificação e Validação

Após a execução, acesse a URL HTTPS exibida no final do script `04-deploy-cloudrun.sh`:
1. **Envio Normal**: Transfira R$ 5,00 com mensagem comum -> Aprovação instantânea via GPU L4 (<10ms).
2. **Envio Suspeito**: Transfira R$ 50,00 com mensagem "passa logo senão eu te pego na saída" ->
   - Interceptação imediata pelo Laya.
   - Perícia pelo Gemini Agent com cálculo de tokens e custo FinOps em tempo real.
   - Histórico e métricas persistidos com sucesso no Cloud SQL.
