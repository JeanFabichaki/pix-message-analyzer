# Pix Guard - PoC Filtro de Ameaças Pix (JEV e Gemini)

Prova de Conceito (PoC) para detecção em tempo real, mascaramento e punição/bloqueio preventivo de comportamentos abusivos, intimidação, extorsão e ameaças veiculadas através de mensagens de transferências Pix (cash-in e cash-out).

---

## 1. Visão Geral da Arquitetura

O pipeline implementa uma defesa de dois estágios:

```
                         [ Cliente / Endpoint Pix ]
                                     │
                         POST /pix/transactions
                                     │
                                     ▼
                        [ pix-gateway-service ]
                                     │
                (Valor <= PIX_THRESHOLD_AMOUNT_BRL?)
                       ├── Não ──> [ Processa Normalmente ]
                       └── Sim
                                │
                     (Mensagem preenchida?)
                       ├── Não ──> [ Processa Normalmente ]
                       └── Sim
                                │
                                ▼
                    [ jev-client (API Corporativa) ]
                                │
                       (is_threat == True?)
                       ├── Não ──> [ Processa Normalmente ]
                       └── Sim
                                │
               ┌────────────────┴────────────────┐
               │                                 │
     (Substitui mensagem pelo              (Dispara evento/chamada
      PIX_MASKED_MESSAGE)                   assíncrona de auditoria)
               │                                 │
               ▼                                 ▼
    [ Retorna Pix Mascarado ]      [ gemini-investigation-agent ]
                                                 │
                                        [ Gemini 2.5 Flash API ]
                                       (Structured JSON Outputs)
                                                 │
                                                 ▼
                                     [ Persiste em threat_logs ]
                                                 │
                                      (Total de ameaças >= 5?)
                                        ├── Não ──> [ Apenas Registra ]
                                        └── Sim ──> [ user-service /block ]
```

1. **Triagem Rápida e Decisão em Tempo Real (JEV API):**
   - Transações com valor $\le R\$\,10{,}00$ que possuam mensagem de texto passam por validação de latência ultra-baixa com a API corporativa do JEV.
   - Caso seja detectada ameaça, a mensagem original é substituída imediatamente pela mensagem padrão do sistema (`PIX_MASKED_MESSAGE`), sem reter o fluxo financeiro.
2. **Investigação Semântica Assíncrona e Governança (Gemini API + PostgreSQL):**
   - O gateway envia a mensagem em segundo plano (`BackgroundTasks`) para o agente Gemini.
   - O agente analisa criticidade e categoria via **Google Gemini (Structured Outputs)** e grava em `threat_logs`.
   - Se o remetente acumular **5 ameaças**, o agente dispara o bloqueio preventivo no `user-service` (status `BLOCKED_SUSPICIOUS`).
   - Futuras tentativas de transação Pix de usuários bloqueados são rejeitadas com HTTP 403 (`REJECTED_BLOCKED`).

---

## 2. Estrutura do Monorepo

```text
pix-message-analyzer/
├── docker-compose.yml
├── .env.example
├── .env
├── Makefile
├── README.md
├── requirements.txt
│
├── libs/
│   └── common/                         # Código compartilhado entre serviços
│       ├── setup.py
│       └── common/
│           ├── config/settings.py      # Configurações Pydantic Settings
│           ├── database/               # SQLAlchemy Async Engine, Base, Models
│           └── schemas/                # DTOs de Pix, Threat e User
│
├── services/
│   ├── frontend-service/               # Porta 3000: SPA React + Vite com 3 Telas
│   │   ├── Dockerfile
│   │   ├── package.json
│   │   ├── vite.config.js
│   │   └── src/
│   │       ├── App.jsx
│   │       ├── components/             # Telas 1 (Simulador), 2 (Matrix), 3 (Auditoria)
│   │       └── services/api.js
│   │
│   ├── pix-gateway-service/            # Porta 8001: Gateway de entrada Pix
│   │   ├── Dockerfile
│   │   └── src/
│   │       ├── main.py                 # Rotas /pix/transactions, /pix/cashin, /pix/cashout
│   │       ├── clients/                # JEV client, Investigation dispatcher, User client
│   │       └── services/interceptor.py # Triagem rápida e mascaramento
│   │
│   └── user-service/                   # Porta 8002: Governança de usuários e bloqueios
│       ├── Dockerfile
│       └── src/
│           ├── main.py                 # Rotas /users/{id}, /users/{id}/block, /users/ensure, /audit
│           └── services/user_service.py# Persistência e regras de bloqueio
│
├── agents/
    └── gemini-investigation-agent/     # Porta 8003: Agente com Gemini 2.5 Flash
        ├── Dockerfile
        └── src/
            ├── main.py                 # POST /investigate
            ├── analyzer.py             # Integração Google GenAI (Structured Outputs)
            └── rules/threshold.py      # Gatilho de reincidência (>= 5 infrações)
```

---

## 3. Como Executar

### 3.1. Usando Docker Compose (Recomendado)

1. Crie o arquivo `.env`:
   ```bash
   cp .env.example .env
   ```
2. (Opcional) Insira sua chave real da Gemini API no `.env`:
   ```ini
   GEMINI_API_KEY=sua_chave_aqui
   ```
   *Nota: Caso não possua a chave no momento, o sistema opera automaticamente em modo mock heurístico para testes e demonstrações.*

3. Inicie os serviços e o banco PostgreSQL:
   ```bash
   make up
   # ou: docker compose up --build -d
   ```

4. Acesse o **Frontend Web**:
   - URL: **http://localhost:3000**
   - **Tela 1**: App Pix mobile simulado na esquerda + animações do pipeline de análise na direita (presets rápidos de 1-clique).
   - **Tela 2**: Cyber-stream tipo Matrix a 100 Pix/segundo com telemetria ativa do fluxo entre Gateway, JEV, Gemini e User-Service.
   - **Tela 3**: Painel de Auditoria e Governança com KPI cards, tabela de ameaças, justificativa semântica do Gemini e botões de desbloqueio/reset de usuários.

5. Verifique os logs:
   ```bash
   make logs
   ```

6. Para parar a infraestrutura:
   ```bash
   make down
   ```

---

### 3.2. Execução Local com Python Virtualenv

1. Crie e ative seu ambiente virtual:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Instale as dependências:
   ```bash
   make install
   ```
3. Execute a suíte de testes:
   ```bash
   make test
   ```

---

## 4. Endpoints Principais

### Gateway Pix (`http://localhost:8001`)

- `POST /pix/transactions`
  - **Payload:**
    ```json
    {
      "transaction_id": "tx_pix_99182312",
      "sender_id": "usr_abc123",
      "sender_cpf": "12345678901",
      "receiver_id": "usr_xyz789",
      "receiver_cpf": "98765432100",
      "direction": "CASH_OUT",
      "amount": 1.50,
      "description": "Vou te pegar na saida do trabalho se nao me responder"
    }
    ```
  - **Resposta com Mascaramento:**
    ```json
    {
      "transaction_id": "tx_pix_99182312",
      "status": "APPROVED",
      "amount": 1.50,
      "description": "Mensagem retida por conter conteúdo inadequado sob análise de segurança.",
      "original_masked": true
    }
    ```

### User Service (`http://localhost:8002`)

- `GET /users/{id}`: Detalhes cadastrais e status (`ACTIVE` ou `BLOCKED_SUSPICIOUS`).
- `POST /users/{id}/block`: Bloqueio manual ou automático por exceder limite de ameaças.
- `GET /users`: Listagem de todos os usuários cadastrados.

### Gemini Investigation Agent (`http://localhost:8003`)

- `POST /investigate`: Endpoint interno disparado pelo Gateway para análise semântica e auditoria.
- `GET /threats/user/{user_id}`: Histórico completo de mensagens de ameaça interceptadas do usuário.

---

## 5. Validação da PoC (Matriz de Cenários)

| Cenário de Teste | Entrada (Payload) | Resposta Esperada | Comportamento Interno |
| :--- | :--- | :--- | :--- |
| **1. Valor Acima do Limite** | `amount: 50.00`, texto ameaçador | `APPROVED`, mensagem preservada | Não aciona JEV nem Gemini (ignorado por threshold). |
| **2. Mensagem em Branco** | `amount: 1.00`, texto vazio `""` | `APPROVED`, mensagem vazia | Não aciona JEV nem Gemini. |
| **3. Mensagem Benigna** | `amount: 5.00`, `"Pagamento do cafe"` | `APPROVED`, mensagem preservada | JEV retorna `is_threat=False`; processa normalmente. |
| **4. Ameaça Detectada (< 5x)** | `amount: 0.05`, `"Vou te achar"` | `APPROVED`, mensagem padrão substituída | JEV detecta; Gemini avalia; registra ocorrência `N` ($N < 5$). Usuário segue `ACTIVE`. |
| **5. Gatilho de Bloqueio (= 5x)** | 5ª mensagem ameaçadora do mesmo `sender_id` | `APPROVED`, mensagem padrão substituída | Gemini avalia; 5ª ocorrência registrada; `user-service` chamado e status do cliente migra para `BLOCKED_SUSPICIOUS`. |
| **6. Governança Preventiva** | Nova transação do usuário bloqueado | HTTP 403 `REJECTED_BLOCKED` | Gateway bloqueia transação na origem. |