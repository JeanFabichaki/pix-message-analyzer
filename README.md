# Pix Guard — Filtro Neural de Ameaças e Extorsão em Mensagens Pix

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61DAFB.svg)](https://react.dev)
[![Vite](https://img.shields.io/badge/Vite-6.4-646CFF.svg)](https://vitejs.dev)
[![PyTorch MPS](https://img.shields.io/badge/PyTorch-Metal%20MPS-EE4C2C.svg)](https://developer.apple.com/metal/pytorch/)
[![Google Gemini](https://img.shields.io/badge/Google%20GenAI-Gemini%202.5%20Flash-4285F4.svg)](https://ai.google.dev)
[![Tests](https://img.shields.io/badge/Tests-43%20Passed-brightgreen.svg)](tests/)

Sistema completo de detecção em tempo real e bloqueio preventivo de transferências Pix associadas a **ameaças à integridade física**, **violência doméstica e perseguição por ex-cônjuge**, **extorsão e chantagem**, **agiotagem predatória** e **coação psicológica** veiculadas no campo de mensagem aberta do Pix (cash-in e cash-out).

O projeto implementa uma arquitetura em dois estágios: **triagem neural síncrona na borda em menos de 15 ms** via modelo SLM Laya (nativo em GPU Apple Silicon MPS ou C++ ONNX) e **investigação forense semântica assíncrona** com Google Gemini 2.5 Flash, munido de guardrails estruturais, anonimização LGPD e governança humana.

> 📚 **Fine-Tuning do Laya:** O diretório [`finetune/`](finetune/README.md) documenta o pipeline completo de treinamento supervisionado e calibração de temperatura com o novo **dataset de 20.000 amostras** e notebook pronto para Google Colab ([`finetune/Treinar_Laya_Pix_20k.ipynb`](finetune/Treinar_Laya_Pix_20k.ipynb)).

---

## 1. Visão Geral da Arquitetura

O pipeline protege a liquidação financeira sem violar o SLA regulatório do Banco Central ($< 35\text{ ms}$):

```
                                [ Aplicativo Bancário / Cliente Pix ]
                                                 │
                                     POST /pix/transactions
                                                 │
                                                 ▼
                                    [ pix-gateway-service :8001 ]
                                                 │
                      ┌──────────────────────────┴──────────────────────────┐
                      ▼                                                     ▼
           (Valor > R$ 10,00 ou sem texto)                       (Valor <= R$ 10,00 com mensagem)
                      │                                                     │
                      ▼                                                     ▼
           [ Aprova Imediatamente ]                         ┌───────────────────────────────┐
           (Liquidação convencional)                        │ 1. Normalização Anti-Bypass   │ (< 0.05 ms)
                                                            │    (Leetspeak, Unicode, etc.) │
                                                            └───────────────┬───────────────┘
                                                                            │
                                                                            ▼
                                                            ┌───────────────────────────────┐
                                                            │ 2. Triagem Neural Laya        │ (~11ms a 16ms)
                                                            │    (Perguntas Decompostas 3x) │ (GPU MPS / ONNX)
                                                            └───────────────┬───────────────┘
                                                                            │
                                                 ┌──────────────────────────┴──────────────────────────┐
                                                 ▼                                                     ▼
                                      (is_threat == False)                                  (is_threat == True)
                                                 │                                                     │
                                                 ▼                                                     ▼
                                      [ PIX APROVADO ]                              [ PIX BLOQUEADO NO ENVIO ]
                                      (Entrega ao destinatário)                      (Mensagem retida para perícia)
                                                                                               │
                                                                       ┌───────────────────────┴───────────────────────┐
                                                                       │ Chamada Assíncrona (BackgroundTasks)          │
                                                                       ▼                                               ▼
                                                       ┌───────────────────────────────┐               ┌───────────────────────────────┐
                                                       │ 3. Gemini Investigation Agent │               │ 4. Registro & Governança      │
                                                       │    (:8003)                    │               │    user-service (:8002)       │
                                                       │  - Sanitização PII (LGPD)     │               │  - Atualiza ficha cadastral   │
                                                       │  - Isolamento Estrutural XML  │               │  - Histórico de reincidência  │
                                                       │  - Structured JSON Outputs    │               │  - Bloqueio cautelar acionado │
                                                       │  - Telemetria de Custo/Tokens │               │    somente pelo analista      │
                                                       └───────────────────────────────┘               └───────────────────────────────┘
```

### Os Dois Estágios Operacionais:

1. **Estágio Síncrono de Borda (Sub-15ms — Laya Dual MPS Server):**
   - Transações com valor $\le R\$\,10{,}00$ contendo mensagem passam pela normalização anti-bypass e por 3 perguntas semânticas simultâneas no modelo Laya. O gateway usa regex local para mascarar identificadores reconhecidos na entrada do modelo.
   - Detectada a ameaça, o envio do Pix é **imediatamente bloqueado** (`status: "BLOCKED"`), resguardando a vítima e retendo o texto original para perícia criminal.
2. **Estágio Assíncrono de Investigação e Governança (Google ADK + Gemini + User Service):**
   - Disparado em segundo plano (`BackgroundTasks`) sem impactar a latência do cliente.
   - O [workflow do Google ADK](agents/gemini-investigation-agent/src/investigation_workflow.py) consulta o histórico, submete as mensagens ao **Model Armor** para detectar prompt injection e jailbreak e usa o **Sensitive Data Protection (Cloud DLP)** para mascarar CPF, RG, telefone, e-mail, cartão, nomes e endereços detectados. O Gemini recebe a versão mascarada via Google Gen AI SDK. O mascaramento local de chaves Pix e dados bancários complementa o DLP.
   - Em caso de bloqueio ou falha da proteção, a investigação registra `BYPASS` com o motivo e interrompe o envio ao Gemini. O ADK usa uma sessão em memória por investigação e a API retorna os tempos de Model Armor, Cloud DLP e Gemini separadamente.
   - O Gemini pericia até 10 mensagens anteriores do remetente, identificando escalada comportamental, evidências materiais e recomendação para o analista de fraudes.
   - A governança de bloqueio permanente da conta/chave Pix é prerrogativa do analista humano com base no laudo técnico emitido.

---

## 2. Estrutura do Monorepo

```text
pix-message-analyzer/
├── docker-compose.yml                  # Orquestração conteinerizada para Linux / Nuvem
├── Makefile                            # Comandos rápidos de instalação, testes e execução
├── README.md                           # Documentação arquitetural completa
├── requirements.txt                    # Dependências Python unificadas
│
├── scripts/
│   ├── start_all_local.sh              # 🚀 Inicia todos os serviços nativamente no macOS (GPU MPS)
│   ├── stop_all_local.sh               # 🛑 Encerra todos os serviços e libera as portas
│   ├── run_native_laya_mac.sh          # Wrapper com caffeinate para evitar sleep de GPU no Mac
│   ├── serve_laya_direct.py            # Servidor FastAPI Dual-Model (Base + Retreinado) em Metal MPS
│   ├── register_native_laya.py         # Patch de offsets ONNX e registro nativo no container Ollaya
│   └── seed_db.py                      # Carga inicial de usuários e contas no banco
│
├── libs/
│   └── common/                         # Biblioteca compartilhada entre microsserviços
│       ├── setup.py
│       └── common/
│           ├── config/settings.py      # Configurações Pydantic Settings e URLs de ambiente
│           ├── database/               # Async Engine, Base SQLAlchemy e modelos relacionais
│           ├── schemas/                # Contratos DTO de Pix, Threat, User e FinOps
│           └── utils/                  # Guardrails de segurança
│               ├── anonymizer.py       # Anonimização de PII (LGPD e sigilo bancário)
│               └── deobfuscator.py     # Desofuscação anti-bypass (leetspeak, unicode invisível)
│
├── services/
│   ├── frontend-service/               # 📱 Porta 3000: SPA React 18 + Vite + Tailwind + Motion
│   │   ├── src/
│   │   │   ├── App.jsx                 # Casca principal e alternância entre as 3 telas
│   │   │   ├── components/
│   │   │   │   ├── Navbar.jsx          # Barra superior, atalhos de teclado e status de saúde
│   │   │   │   ├── Screen1Journey.jsx  # Tela 1: Jornada interativa e simulação mobile
│   │   │   │   ├── ScreenLive.jsx      # Tela 2: Streaming de transações sintéticas em alta vazão
│   │   │   │   └── ScreenCompare.jsx   # Tela 3: Benchmark em tempo real (Original vs. Retreinado)
│   │   │   ├── journey/
│   │   │   │   ├── PhoneMock.jsx       # Simulador fidedigno de smartphone iOS/Android
│   │   │   │   ├── AfterDelivery.jsx   # Laudo pericial detalhado, evidências e FinOps
│   │   │   │   └── scenarios.js        # Casos de teste pré-configurados (violência, ex, agiotagem)
│   │   │   └── services/api.js         # Cliente de integração com timeout e fallbacks
│   │   └── package.json
│   │
│   ├── pix-gateway-service/            # ⚡ Porta 8001: Gateway de entrada e liquidação Pix
│   │   └── src/
│   │       ├── main.py                 # Rotas /pix/transactions, /pix/engines, /health
│   │       ├── clients/
│   │       │   ├── ollaya_client.py    # Cliente HTTP com pool keep-alive e failover round-robin
│   │       │   ├── investigation.py    # Cliente assíncrono para o agente Gemini
│   │       │   └── user_client.py      # Consulta e atualização de status de usuários
│   │       └── services/
│   │           ├── interceptor.py      # Máquina de estados: 4 estações de triagem
│   │           └── benchmark.py        # Motor de execução paralela do benchmark comparativo
│   │
│   └── user-service/                   # 👤 Porta 8002: Governança cadastral e auditoria
│       └── src/
│           ├── main.py                 # Rotas /users/{id}, /users/{id}/block, /audit/metrics
│           └── services/user_service.py# Regras de negócio e persistência de ocorrências
│
├── agents/
│   └── gemini-investigation-agent/     # 🕵️ Porta 8003: Agente pericial com Google Gemini 2.5 Flash
│       └── src/
│           ├── main.py                 # Rotas /investigate, /threats/user/{id}, /generate-dataset
│           ├── analyzer.py             # Prompt forense, isolamento XML, BLOCK_NONE e FinOps
│           └── rules/threshold.py      # Critérios de reincidência e recomendação ao analista
│
├── finetune/                           # 🧠 Ferramental de Fine-Tuning do Laya (Dataset 20k)
│   ├── build_dataset_20k.py            # Gerador de dataset sintético balanceado de 20.000 amostras
│   ├── train_laya_pix_20k.py           # Script de treino supervisionado + calibração de temperatura
│   ├── Treinar_Laya_Pix_20k.ipynb      # Notebook para execução no Google Colab com GPU T4
│   ├── Modelfile.laya-fp32             # Configuração declarativa para importação FP32 no Ollaya
│   └── data_20k/                       # Datasets gerados (train, val, test e challenge)
│
└── tests/                              # 🧪 Suíte com 43 testes automatizados (pytest)
    ├── test_anti_bypass_evasion.py     # Validação do deobfuscator contra Leetspeak e evasões
    ├── test_api_integration.py         # Teste de integração ponta a ponta dos endpoints
    ├── test_benchmark_gemini.py        # Geração dinâmica de datasets e runner comparativo
    ├── test_gemini_cost_tracking.py    # Verificação das métricas de FinOps (tokens e tarifas USD/BRL)
    ├── test_guardrails_best_practices.py # Anonimização LGPD, tags XML, Safety Settings e FP32
    ├── test_poc_scenarios.py           # Matriz dos 6 cenários regulatórios do Bacen
    └── test_trace_decided_by.py        # Auditoria de rastreabilidade de decisões e estações
```

---

## 3. Como Executar

### 3.1. Execução Nativa no macOS com Apple Silicon GPU / MPS (Recomendada)

Para obter o máximo desempenho de inferência (**~11 ms a 16 ms** de tempo neural puro em GPU Metal) e inicialização em poucos segundos:

1. **Configure o ambiente virtual:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install -e libs/common
   npm --prefix services/frontend-service install
   ```

2. **Crie o `.env` a partir do modelo:**
   ```bash
   cp .env.example .env
   ```
   Para executar a investigação assíncrona, configure `GEMINI_API_KEY`, `GOOGLE_CLOUD_PROJECT` e `MODEL_ARMOR_TEMPLATE_ID`. Model Armor e Cloud DLP usam endpoints regionais de São Paulo por padrão (`southamerica-east1`).

3. **Inicie todos os microsserviços com um único comando:**
   ```bash
   ./scripts/start_all_local.sh
   ```
   O script orquestra em segundo plano:
   - Base de dados local e migrations (`seed_db.py`).
   - **Servidor Dual Laya MPS na porta 8000** (`serve_laya_direct.py` com `caffeinate` ativo).
   - **User Service na porta 8002**.
   - **Gemini Investigation Agent na porta 8003**.
   - **Pix Gateway Service na porta 8001**.
   - **Frontend React (Vite) na porta 3000**.

4. **Para encerrar todos os serviços:**
   ```bash
   ./scripts/stop_all_local.sh
   ```

---

#### Configuração das APIs de proteção

1. Habilite `modelarmor.googleapis.com` e `dlp.googleapis.com` no projeto e crie um template do Model Armor na região configurada. Na POC, o detector de prompt injection e jailbreak usa confiança alta para reduzir falsos positivos em mensagens de ameaça. [Configuração do template](https://docs.cloud.google.com/model-armor/manage-templates)
2. Configure [Application Default Credentials](https://docs.cloud.google.com/docs/authentication/provide-credentials-adc). No Mac, use `gcloud auth application-default login`. Em execução no Google Cloud, use a conta de serviço associada ao agente. A identidade precisa dos papéis `roles/modelarmor.user` e `roles/dlp.user` e da permissão `serviceusage.services.use` no projeto informado.
3. Se executar localmente via Docker, monte as credenciais em modo somente leitura no contêiner do agente e aponte `GOOGLE_APPLICATION_CREDENTIALS` para o caminho montado.

### 3.2. Execução via Docker Compose (Linux, CI ou Servidores)

1. **Inicie o ecossistema com Laya Original:**
   ```bash
   make up
   # ou: docker compose up --build -d
   ```

2. **Inicie com o Laya Retreinado no cluster Ollaya:**
   ```bash
   make up-tuned
   ```

3. **Verifique os logs agregados:**
   ```bash
   make logs
   ```

4. **Para encerrar os containers:**
   ```bash
   make down
   ```

---

## 4. Frontend e Experiência do Analista (SPA com 3 Telas)

Acesse **http://localhost:3000** no navegador. A aplicação foi concebida para oferecer alta densidade de informação, ergonomia visual e acessibilidade total:

As duas interfaces estão disponíveis no mesmo frontend:

- **v1 — interface original:** `http://localhost:3000/?interface=v1` (também é a versão padrão).
- **v2 — apresentação para gerentes:** `http://localhost:3000/?interface=v2`.

Use os links **Experimentar v2** e **Interface v1** no menu superior para alternar. A troca recarrega a interface e limpa o estado local da demonstração. Na v2, a seleção entre **Decision Model original** e **Decision Model treinado** fica na tela principal; o controle de animação fica em **Ajustes**. Clique nas etapas para ver os tempos medidos e os dados retornados pelo backend, sem sair da jornada. A decisão do Pix aparece primeiro; a investigação assíncrona aparece abaixo para os casos bloqueados. O painel aguarda o resultado real da API e permite abrir a análise do operador. Se houver bypass ou falha nas proteções, sinaliza a necessidade de revisão manual.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  🛡️ Pix Guard         [ Jornada (1) ]  [ Ao vivo (2) ]  [ Comparar (3) ]   ● Operacional│
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   📱 SIMULADOR MOBILE                  ESTAÇÕES DO GATEWAY (TEMPO REAL)                │
│  ┌───────────────────────┐             ┌──────────────────────────────────────────┐    │
│  │ Remetente: Marcos     │             │ 1. Regra de Negócio (<= R$ 10)    [0.1ms]│    │
│  │ "se me largar te mato"│  ─────────> ├──────────────────────────────────────────┤    │
│  │ Valor: R$ 0,05        │             │ 2. Guardrail Anti-Bypass          [0.2ms]│    │
│  │ [ ENVIAR PIX ]        │             ├──────────────────────────────────────────┤    │
│  └───────────────────────┘             │ 3. Triagem Neural Laya (MPS)     [14.2ms]│    │
│                                        ├──────────────────────────────────────────┤    │
│                                        │ 4. Decisão: PIX BLOQUEADO        [0.1ms]│    │
│                                        └──────────────────────────────────────────┘    │
│                                                                                        │
│   LAUDO FORENSE ASSÍNCRONO (GEMINI 2.5 FLASH)                                          │
│  ┌────────────────────────────────────────────────────────────────────────────────┐    │
│  │ ⚡ Padrão: Ameaça de violência doméstica e perseguição por ex-cônjuge (0.96)    │    │
│  │ 🔍 Evidências: ["se me largar", "te mato", "vou até sua casa"]                  │    │
│  │ 🛡️ Recomendação: Bloqueio cautelar imediato da chave Pix e notificação BACEN   │    │
│  │ 💰 FinOps: 1.142 tokens consumidos | Custo: $0.00028 (~R$ 0,0016)              │    │
│  └────────────────────────────────────────────────────────────────────────────────┘    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Detalhamento das Telas:

- **1. Jornada (`Screen1Journey`):**
  - **Simulador Mobile (`PhoneMock`):** Representação realista do fluxo do pagador e do recebedor com feedback sonoro e háptico visual.
  - **Cenários Pré-Carregados:** Botões de acesso rápido cobrindo:
    - *Violência Física Explícita* ("vou quebrar sua cara");
    - *Ameaças de Ex-Cônjuge / Marido Inconformado* ("não aceito o término, vou infernizar seus dias");
    - *Extorsão e Agiotagem* ("paga hoje ou mando a cobrança no seu trabalho");
    - *Perseguição Velada / Stalking* ("sei a placa do seu carro novo");
    - *Tentativas de Evasão / Leetspeak* ("v0u t3 p3g4r n4 s41d4");
    - *Transações Cotidianas Benignas* ("almoço de ontem", "vaquinha do churrasco").
  - **Modos de Execução:** Modo automático em câmera lenta ou modo **Passo a Passo** (onde o analista avança estágio por estágio).
  - **Card de Laudo Forense (`AfterDelivery`):** Detalha evidências materiais, linha do tempo histórica com anonimização LGPD e **telemetria FinOps de tokens e custos de API**.

- **2. Ao Vivo (`ScreenLive`):**
  - Streaming contínuo de transações sintéticas processadas pelo gateway real.
  - Indicadores em tempo real: volume por minuto, taxa de ameaças interceptadas, latência p50/p95/p99 e throughput.
  - **Replay Instantâneo:** Clicar em qualquer transação no fluxo ao vivo carrega e reproduz imediatamente toda a sua jornada pericial na Tela 1.

- **3. Comparar (`ScreenCompare`):**
  - Execução simultânea e paralela do conjunto de teste nos dois modelos: **Laya Original (`laya:multilingual`)** vs. **Laya Retreinado (`pix-threats`)**.
  - Apresenta métricas lado a lado: Acurácia, Recall, F1-Score, Falsos Alarmes e Ameaças Perdidas.
  - **Decomposição de Latência:** Exibição clara de `inference_ms` (computação na GPU/CPU) vs. `network_ms` (overhead de rede).
  - **Gerador de Casos Desafiadores via Gemini:** Botão *"Gerar 50 mensagens via Gemini"*, que utiliza prompt estruturado na API do Google para criar 50 casos inéditos de alta complexidade (stalking sutil, leetspeak sofisticado e gírias coloquiais) e submetê-los ao benchmark na hora.

### Atalhos de Teclado e Acessibilidade:
- Teclas **`1`**, **`2`** e **`3`**: Alternam instantaneamente entre as abas.
- Tecla **`R`**: Repete a simulação do Pix atual.
- Tecla **`Espaço`** ou **`→`**: Avança para a próxima estação no modo passo a passo.
- Tecla **`Esc`**: Pula a animação para o laudo final.
- **Botão "Animações":** Alterna entre animações completas e modo reduzido (respeita também a diretiva nativa `prefers-reduced-motion` do sistema operacional).

---

## 5. Servidor Laya Direto Dual-Model em Apple Silicon GPU (`serve_laya_direct.py`)

Para viabilizar inferência sub-15ms em ambiente de desenvolvimento e demonstração no Mac, o script [`scripts/serve_laya_direct.py`](scripts/serve_laya_direct.py) implementa um servidor direto sobre o framework Laya com as seguintes otimizações de baixo nível:

```
┌────────────────────────────────────────────────────────────────────────┐
│   scripts/serve_laya_direct.py (:8000)                                 │
├────────────────────────────────────────────────────────────────────────┤
│  🧠 agent_tuned (pix-threats)    <──> GPU Metal (MPS) Float32 Residente│
│  🧠 agent_base (multilingual)    <──> GPU Metal (MPS) Float32 Residente│
├────────────────────────────────────────────────────────────────────────┤
│  ⚡ 1. Fixed Collate (min_len=64) : Zero recompilação JIT de Shaders   │
│  💓 2. Async Heartbeat (1.5s)     : Previne downclocking térmico do SoC │
│  ☕ 3. Caffeinate Wrapper         : Previne App Nap do macOS            │
│  🚀 4. Zero Lock / ThreadPool     : Sem filas de serialização de Python │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Hospedagem Dual de Modelos:**
   Carrega tanto o modelo retreinado (`pix-threats`) quanto o modelo base original (`convaiinnovations/laya:multilingual`) simultaneamente na memória unificada do Apple Silicon. O roteamento é realizado pelo campo `"model"` recebido na requisição do gateway.
2. **Eliminação de JIT Recompilation de Shaders Metal (`collate_fixed`):**
   No PyTorch com backend MPS, se cada requisição variar ligeiramente no tamanho do tensor (ex.: 28 tokens, depois 34 tokens), o compilador Metal recompila os shaders JIT em tempo de execução, gerando picos esporádicos de 150ms a 300ms. A função `collate_fixed` força dimensões fixas (`min_len=64`), mantendo o grafo compilado estável e executando em **~11 ms**.
3. **Heartbeat Assíncrono e Prevenção de Downclocking:**
   Se o servidor ficar mais de 1,5 segundo sem requisições, uma tarefa de background dispara uma inferência mínima de keep-alive na GPU Metal. Isso impede que o gerenciador de energia do macOS reduza a frequência de clock dos núcleos de GPU.
4. **Resolução de Rede Local (Bind 127.0.0.1):**
   Comunicação inter-serviços padronizada estritamente em `127.0.0.1` (em vez de `localhost`), evitando a penalidade de consulta de resolução mDNS do macOS (que causava picos de 261ms).

---

## 6. Guardrails de Engenharia Antifraude e Boas Práticas

### 6.1. Fase Síncrona (Gateway e Borda)

| Guardrail | Implementação | Motivação Técnica e Regulatória |
|---|---|---|
| **Anti-Bypass / Desofuscação** | [`libs/common/.../deobfuscator.py`](libs/common/common/utils/deobfuscator.py) | Remove leetspeak (`v0u t3 m4t4r`), espaços forçados (`p.a.g.a`), caracteres invisíveis Unicode (`\u200b`) em menos de $0{,}05\text{ ms}$. |
| **Perguntas Decompostas** | [`services/.../ollaya_client.py`](services/pix-gateway-service/src/clients/ollaya_client.py) | Avalia no mesmo forward pass: ameaça de violência física, extorsão/chantagem e cobrança hostil abusiva. Evita diluição de atenção. |
| **Mesmo corte para os dois modelos** | [`services/.../ollaya_client.py`](services/pix-gateway-service/src/clients/ollaya_client.py) | Original e treinado usam corte de 0,40: score ≥ 0,40 reprova a mensagem. `in_gray_zone` continua sinalizando a faixa de 0,45 a menos de 0,65, que já está acima do corte atual. |
| **Precisão Numérica FP32** | [`finetune/Modelfile.laya-fp32`](finetune/Modelfile.laya-fp32) | Evita distorções de arredondamento em ponto flutuante de 16 bits na vizinhança do ponto de corte decisório. |

### 6.2. Fase Assíncrona (Investigação Forense com Gemini)

| Guardrail | Implementação | Motivação Técnica e Jurídica |
|---|---|---|
| **Anonimizador PII (LGPD)** | [`libs/common/.../anonymizer.py`](libs/common/common/utils/anonymizer.py) | Sanitiza CPFs, telefones, e-mails, contas bancárias e chaves Pix localmente antes do envio à API de nuvem. |
| **Isolamento Estrutural XML** | [`agents/.../analyzer.py`](agents/gemini-investigation-agent/src/analyzer.py) | Encapsula as mensagens sob análise dentro de `<mensagens_suspeitas_nao_confiaveis>`, neutralizando tentativas de Indirect Prompt Injection. |
| **Safety Settings `BLOCK_NONE`** | [`agents/.../analyzer.py`](agents/gemini-investigation-agent/src/analyzer.py) | Impede que a API do Gemini aborte por auto-bloqueio (`finish_reason: SAFETY`) ao periciar ameaças de morte reais. |
| **Structured JSON Outputs** | [`libs/common/.../schemas/threat.py`](libs/common/common/schemas/threat.py) | Obriga o retorno no schema Pydantic tipado, garantindo campos de evidências, padrão comportamental e recomendação sem alucinação. |
| **Série Temporal de até 10 Mensagens** | [`agents/.../investigation_workflow.py`](agents/gemini-investigation-agent/src/investigation_workflow.py) | Permite identificar intimidação continuada e perseguição fragmentada em múltiplos micropagamentos de centavos. |
| **FinOps e Monitoramento de Custos** | [`agents/.../analyzer.py`](agents/gemini-investigation-agent/src/analyzer.py) | Rastreia tokens de entrada e saída por chamada, calculando o custo exato em dólares e reais para governança financeira. |

---

## 7. Pipeline de Fine-Tuning do Laya: Dataset de 20.000 Exemplos (`finetune/`)

O diretório [`finetune/`](finetune/README.md) contém a esteira completa para retreinar o Laya com uma base expandida de dados sintéticos e manuscritos:

```
finetune/
├── build_dataset_20k.py            # Script gerador da base de 20.000 amostras
├── train_laya_pix_20k.py           # Treinamento com taxa de aprendizado diferenciada e calibração
├── Treinar_Laya_Pix_20k.ipynb      # Notebook completo para execução direta no Google Colab
├── Modelfile.laya-fp32             # Manifesto OCI para servir no Ollaya C++
└── data_20k/
    ├── train.jsonl                 # 16.000 exemplos de treino balanceados
    ├── val.jsonl                   # 2.000 exemplos de validação para temperatura
    ├── test.jsonl                  # 2.000 exemplos para cálculo de métricas finais
    └── challenge.jsonl             # 50 mensagens desafiadoras escritas à mão
```

### Resultados Comparativos de Assertividade:

| Métrica | Laya Original (`multilingual`) | Laya Retreinado (`pix-threats`) | Diferencial Técnico |
|---|---|---|---|
| **Recall em Ameaças Sintéticas** | 37,5% | **87,5%** | **+50.0 p.p. (+133% de detecção)** |
| **Falsos Alarmes (Falsos Positivos)** | 8,1% | **3,8%** | **Redução de mais da metade dos alarmes falsos** |
| **Recall no Conjunto Desafio (Manuscrito)** | 35,0% | **80,0%** | **Salto de 35% para 80% em linguagem natural real** |
| **F1-Score Geral** | 32,4% | **75,7%** | **Aumento substancial no equilíbrio de precisão/recall** |
| **Latência Média de Inferência** | ~500 ms (CPU base) | **~14 ms (MPS Metal) / ~24 ms (INT8)** | **Até 35x mais rápido** 🚀 |

---

## 8. Endpoints Principais da API

### Pix Gateway Service (`http://localhost:8001`)
- `POST /pix/transactions`: Submete transação para análise e liquidação em tempo real.
- `GET /pix/engines`: Retorna os modelos de IA disponíveis (`laya` e `laya_tuned`) e o motor padrão.
- `GET /pix/benchmark`: Executa o benchmark comparativo em lote no dataset de teste.
- `GET /health`: Estado operacional do gateway e conectividade com os serviços periféricos.

### User Service (`http://localhost:8002`)
- `GET /users/{id}`: Consulta situação cadastral (`ACTIVE` ou `BLOCKED_SUSPICIOUS`).
- `POST /users/{id}/block`: Bloqueio cautelar de conta acionado pelo analista humano.
- `POST /users/{id}/unblock`: Reativação de conta de usuário.
- `GET /audit/metrics`: Consolidação de métricas, ameaças interceptadas e custos acumulados do Gemini.

### Gemini Investigation Agent (`http://localhost:8003`)
- `POST /investigate`: Emite laudo pericial estruturado a partir da mensagem alvo e histórico do remetente.
- `GET /threats/user/{user_id}`: Recupera o histórico forense de ameaças retidas daquele remetente.
- `POST /generate-dataset`: Gera sob demanda novas mensagens sintéticas desafiadoras via Gemini API.

---

## 9. Suíte de Testes Automatizados

O projeto conta com **43 testes automatizados** cobrindo todos os módulos críticos:

```bash
# Execução via ambiente virtual local
source .venv/bin/activate
pytest -v

# Ou via Makefile
make test
```

### Escopo de Cobertura dos Testes:
- **`tests/test_anti_bypass_evasion.py` (6 testes):** Evasão por leetspeak, caracteres invisíveis Unicode e separadores.
- **`tests/test_guardrails_best_practices.py` (11 testes):** Anonimizador LGPD, prompt forense em XML, safety settings `BLOCK_NONE` e precisão FP32.
- **`tests/test_gemini_cost_tracking.py` (5 testes):** Cálculo de tarifas de tokens, agregação de custos e persistência.
- **`tests/test_poc_scenarios.py` (6 testes):** Validação dos cenários regulatórios do Banco Central.
- **`tests/test_benchmark_gemini.py` (2 testes):** Geração dinâmica de dados de teste via Gemini e runner do benchmark.
- **`tests/test_trace_decided_by.py` (11 testes):** Rastreabilidade de cada estação síncrona, failover round-robin e diagnósticos de conectividade.
- **`tests/test_api_integration.py` (2 testes):** Integração ponta a ponta dos endpoints HTTP do Gateway.

---

## 10. Licença e Contexto

Desenvolvido como Prova de Conceito (PoC) para demonstrar a viabilidade técnica de triagem neural em tempo real com SLMs na borda combinados com perícia aprofundada de LLMs para segurança bancária e proteção ao cidadão.
