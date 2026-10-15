# Pix Guard - PoC Filtro de Ameaças Pix (Ollaya e Gemini)

Prova de Conceito (PoC) para detecção em tempo real, mascaramento e punição/bloqueio preventivo de comportamentos abusivos, intimidação, extorsão e ameaças veiculadas através de mensagens de transferências Pix (cash-in e cash-out).

> **Quer treinar o seu próprio modelo?** O diretório [`finetune/`](finetune/README.md) é um tutorial completo de fine-tuning do Laya (dataset, Colab, calibração, Docker e comparação), reaproveitável em outros projetos.

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
                    [ ollaya-client (API Corporativa) ]
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

1. **Triagem Rápida e Decisão em Tempo Real (Ollaya API):**
   - Transações com valor $\le R\$\,10{,}00$ que possuam mensagem de texto passam por validação de latência ultra-baixa com o modelo de decisão Ollaya.
   - Caso seja detectada ameaça, a mensagem original é substituída imediatamente pela mensagem padrão do sistema (`PIX_MASKED_MESSAGE`), sem reter o fluxo financeiro.
2. **Investigação Semântica Assíncrona e Governança (Gemini API + PostgreSQL):**
   - O gateway envia a mensagem em segundo plano (`BackgroundTasks`) para o agente Gemini.
   - O agente analisa criticidade e categoria via **Google Gemini (Structured Outputs)** e grava em `threat_logs`.
   - Se o remetente acumular **5 ameaças**, o agente dispara o bloqueio preventivo no `user-service` (status `BLOCKED_SUSPICIOUS`).
   - O gateway **não consulta** o status da conta ao receber um Pix: usuários marcados como `BLOCKED_SUSPICIOUS` continuam sendo processados normalmente.

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
│   │       ├── clients/                # Ollaya client, Investigation dispatcher, User client
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
   *Nota: Caso a chave não esteja configurada ou seja inválida, a investigação do Gemini opera automaticamente em modo transparente de BYPASS, sem forjar análises heurísticas e sinalizando na UI.*

3. Inicie os serviços e o banco PostgreSQL:
   ```bash
   make up
   # ou: docker compose up --build -d
   ```

4. Acesse o **Frontend Web**:
   - URL: **http://localhost:3000**
   - **Jornada** (tela principal): escolha um caso pronto (ou digite uma mensagem), envie o Pix e acompanhe a mensagem do celular de quem envia até o de quem recebe, passando por 4 estações síncronas (valor, disfarces, IA rápida, entrega) e 2 etapas em segundo plano (laudo do Gemini, ficha N de 5). Os tempos exibidos são os medidos pelo gateway; a animação é uma câmera lenta. Modo "Passo a passo" (→ ou espaço avança, Esc pula, R repete).
   - **Ao vivo**: Pix sintéticos passando pelo gateway real, com mini-trilha de 4 pontos por linha e latência p50/p95 real. Clicar numa linha reproduz a jornada daquele Pix.
   - **Histórico**: mensagens retidas com laudo da IA, contas com ocorrências e ações de reativar/zerar. "Ver a jornada" reconstrói o caminho a partir do registro.
   - Teclas **1 a 4** trocam de tela. A aba **Comparar** (Tela 4) roda os dados de teste nos dois modelos (Laya original x retreinado) e mostra a diferença de assertividade. Conta com o botão **"Gerar 50 mensagens via Gemini"**, que aciona a API do Google Gemini com um prompt estruturado para gerar 50 novos casos desafiadores de teste (25 ameaças complexas como stalking e chantagem, e 25 benignas) e os compara em tempo real. O botão "Animações" reduz o movimento (também respeita `prefers-reduced-motion`).

   > O frontend passou a depender de `motion`. Com Docker, reconstrua a imagem (`make up`) para instalar a dependência.

4.1. **Laya original ou retreinado.** Com o checkpoint em `finetune/models/pix-threats` (passo a passo em `finetune/README.md`),
   rode `make up-tuned`. O Laya retreinado nativo (`laya:pix-threats`) é registrado no cluster Ollaya e configurado como motor padrão (`"engine": "laya_tuned"`).
   O seletor **Laya original / Laya retreinado** fica na barra superior do frontend; pela API, envie `"engine": "laya_tuned"` (padrão) ou `"laya"` em `POST /pix/transactions`; `GET /pix/engines` mostra a disponibilidade.

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
| **1. Valor Acima do Limite** | `amount: 50.00`, texto ameaçador | `APPROVED`, mensagem preservada | Não aciona Ollaya nem Gemini (ignorado por threshold). |
| **2. Mensagem em Branco** | `amount: 1.00`, texto vazio `""` | `APPROVED`, mensagem vazia | Não aciona Ollaya nem Gemini. |
| **3. Mensagem Benigna** | `amount: 5.00`, `"Pagamento do cafe"` | `APPROVED`, mensagem preservada | Ollaya retorna `is_threat=False`; processa normalmente. |
| **4. Ameaça Detectada (< 5x)** | `amount: 0.05`, `"Vou te achar"` | `APPROVED`, mensagem padrão substituída | Ollaya detecta; Gemini avalia; registra ocorrência `N` ($N < 5$). Usuário segue `ACTIVE`. |
| **5. Gatilho de Bloqueio (= 5x)** | 5ª mensagem ameaçadora do mesmo `sender_id` | `APPROVED`, mensagem padrão substituída | Gemini avalia; 5ª ocorrência registrada; `user-service` chamado e status do cliente migra para `BLOCKED_SUSPICIOUS`. |
| **6. Governança Preventiva** | Nova transação do usuário bloqueado | HTTP 403 `REJECTED_BLOCKED` | Gateway bloqueia transação na origem. |

---

## 6. Estudo de Calibração e Tuning de Prompts do Ollaya (SLM Laya)

### 6.1. Motivação e Desafio de Engenharia de Prompts em SLMs
O **Ollaya** (`laya:multilingual`) é um *Small Language Model* (SLM) baseado no encoder **mmBERT-base**, operando localmente na borda para atender ao requisito de latência ultrabaixa estipulado para liquidações Pix ($< 35\text{ ms}$).

Diferente de LLMs massivos de centenas de bilhões de parâmetros (como Gemini ou GPT-4) que possuem janelas de contexto gigantes e lidam bem com instruções extensas, SLMs possuem janela de contexto limitada (~1024 tokens) e vetor de atenção focado. Em modelos desse porte, a redação do contrato TypeSafe (`/v1/systemone`) tem impacto crítico:
1. **Prompts excessivamente longos:** diluem o foco de atenção do encoder, aumentam o número de tokens desnecessariamente, triplicam a latência e causam degradação severa de recall (falsos negativos).
2. **Prompts excessivamente curtos:** reduzem a amplitude semântica do modelo; palavras isoladas (como apenas `"ameaça"`) ignoram coações veladas, chantagens financeiras e perseguição (*stalking*).

---

### 6.2. Comparativo das Abordagens Testadas

Durante o desenvolvimento do gateway, três formulações foram submetidas a testes empíricos rigorosos:

#### Abordagem 1: Prompt Descritivo Longo (Versão Inicial)
```json
{
  "model": "laya:multilingual",
  "state": "<mensagem>",
  "questions": {
    "threat": {
      "type": "choice",
      "instructions": "Analise em português do Brasil se a mensagem de Pix contém ameaça, agressão física iminente, perseguição (stalking), caçada, emboscada, coação, intimidação ou cobrança hostil. Atenção: expressões como \"vou te achar\", \"no fim do mundo\", \"vou te pegar\", \"esperar na saída\", \"caloteiro\" configuram coação e ameaça grave.",
      "criteria": {
        "threat": "Ameaça física, perseguição, caçada no fim do mundo, emboscada, cobrança violenta, coação ou intimidação",
        "safe": "Comunicação respeitosa, amigável, romântica consentida, familiar legítima ou comercial normal"
      }
    }
  }
}
```
* **Comprimento:** ~175 tokens de entrada.
* **Latência:** ~135 ms por inferência.
* **Diagnóstico:** O excesso de exemplos circunstanciais e redundâncias desviou os pesos de atenção. Em benchmark de 8 mensagens-chave, acertou apenas 50% dos casos, deixando passar até mesmo violência direta (`prob=0.1355`).

#### Abordagem 2: Prompt Minimalista / Sem Instrução
```json
{
  "model": "laya:multilingual",
  "state": "<mensagem>",
  "questions": {
    "threat": {
      "type": "choice",
      "criteria": {
        "threat": "ameaça",
        "safe": "agradecimento ou conversa normal"
      }
    }
  }
}
```
* **Comprimento:** ~25 tokens de entrada.
* **Latência:** ~30 ms por inferência.
* **Diagnóstico:** Excelente velocidade e alta precisão para violência direta (`prob=0.9970`), porém estrito demais. Mensagens com perseguição contextualizada (*stalking*) registraram apenas `prob=0.2300`, caindo abaixo do limiar de 0.40 e sendo liberadas indevidamente.

#### Abordagem 3: O Meio-Termo Calibrado (Adotado em Produção)
```json
{
  "model": "laya:multilingual",
  "state": "<mensagem>",
  "questions": {
    "threat": {
      "type": "choice",
      "instructions": "A mensagem de Pix contém ameaça, chantagem ou perseguição?",
      "criteria": {
        "threat": "ameaça, chantagem ou perseguição",
        "safe": "conversa normal ou amigável"
      }
    }
  }
}
```
* **Comprimento:** ~55 a 65 tokens de entrada.
* **Latência:** ~35 ms por inferência (compatível com a meta de SLA do BACEN).
* **Diagnóstico:** O equilíbrio ideal. A instrução única de 1 linha ativou os cabeçalhos semânticos essenciais de perseguição e extorsão sem poluir o contexto. Subiu a detecção de *stalking* para `prob=0.6179` (acima do limiar de 0.40) com **zero falso alarme** em conversas com gírias ou cobranças pacíficas.

---

### 6.3. Matriz de Resultados do Benchmark no Container Real

Os testes a seguir foram executados diretamente contra o serviço real do Ollaya (`ghcr.io/ollaya-dev/ollaya:latest`, modelo `laya:multilingual`), com limiar de decisão fixado em $\ge 0{,}40$:

| Mensagem Testada | Categoria Real | Longo (175 tok) | Curto (25 tok) | **Meio-Termo (55 tok)** | Decisão Final |
| :--- | :--- | :---: | :---: | :---: | :---: |
| *"Vi você saindo da academia com seu carro prata, vou te achar nem que seja no fim do mundo"* | **Perseguição (Stalking)** | 0.34% *(safe)* ✗ | 23.00% *(safe)* ✗ | **61.79% (threat)** ✓ | **RETIDA (MASKED)** |
| *"vou te pegar na saida do trabalho se nao me pagar hoje"* (canônico pós anti-bypass) | **Coação / Extorsão** | 9.30% *(safe)* ✗ | 76.64% *(threat)* ✓ | **86.14% (threat)** ✓ | **RETIDA (MASKED)** |
| *"Me paga hoje ou vou quebrar sua cara"* | **Violência Física Direta** | 13.55% *(safe)* ✗ | 99.70% *(threat)* ✓ | **73.01% (threat)** ✓ | **RETIDA (MASKED)** |
| *"Amigo, quase morri de rir ontem na festa! Segue o valor da vaquinha do churrasco"* | **Gíria Coloquial (Benigno)** | 0.15% *(safe)* ✓ | 0.20% *(safe)* ✓ | **6.23% (safe)** ✓ | **LIBERADA (CLEAN)** |
| *"Pagamento do almoço de ontem, valeu amigo!"* | **Transação Cotidiana (Benigno)** | 0.04% *(safe)* ✓ | 0.22% *(safe)* ✓ | **0.40% (safe)** ✓ | **LIBERADA (CLEAN)** |
| *"Pode me transferir o valor do aluguel até o dia 10, por favor?"* | **Cobrança Educada com Prazo** | 0.02% *(safe)* ✓ | 0.20% *(safe)* ✓ | **0.01% (safe)** ✓ | **LIBERADA (CLEAN)** |
| *"Compra de 2 ingressos para o cinema"* | **Transação Comercial (Benigno)** | 0.05% *(safe)* ✓ | 0.37% *(safe)* ✓ | **0.18% (safe)** ✓ | **LIBERADA (CLEAN)** |
| **Acurácia Global no Benchmark** | — | **50.0%** (4/8) | **75.0%** (6/8) | **87.5%** (7/8) | — |

---

### 6.4. Lição de Arquitetura: Preservação de Capitalização e Pontuação
Um dos aprendizados mais importantes do estudo envolveu o estágio anterior de **Anti-Bypass / Desofuscação**:
* O encoder do modelo `laya:multilingual` (baseado em mmBERT) foi pré-treinado em textos que contêm letras maiúsculas, vírgulas e acentos.
* Quando a mensagem original **não continha disfarces** (`evasion_detected == False`), forçar a forma canônica pré-processada (em minúsculas e sem pontuação: `"vi voce saindo da academia..."`) derrubava o score de *stalking* para $2{,}56\%$.
* **Solução arquitetural adotada no Gateway ([`interceptor.py`](services/pix-gateway-service/src/services/interceptor.py)):**
  - Se for detectada evasão / leetspeak $\rightarrow$ alimenta o Ollaya com o texto normalizado (`canonical_text`) para desarmar a ofuscação.
  - Se não houver evasão $\rightarrow$ alimenta o Ollaya com o texto original em linguagem natural (`tx.description`), preservando o contexto sintático e de pontuação original.


---

## 7. Empacotamento do Modelo Retreinado para Performance Nativa no Ollaya (~50 ms)

### 7.1. Diagnóstico de Performance: Python/PyTorch vs. Binário Nativo C++

Ao comparar o **Laya Original** com o **Laya Retreinado**, observou-se uma diferença acentuada de latência:
- **Laya Original (`pix-ollaya`):** ~53 ms por inferência.
- **Laya Retreinado no container de protótipo (`pix-laya-tuned`):** ~110 ms em chamadas isoladas e ~854 ms em testes de concorrência em lote (como na Tela 4).

Inspecionando o código-fonte interno do servidor de protótipo (`laya.serve`), identificou-se que ele utiliza um **`ThreadPoolExecutor(max_workers=1)`** e um **`asyncio.Lock()` global (`async with gate:`)**. Sob rajadas simultâneas (o benchmark dispara 6 requisições concorrentes), as mensagens formam uma fila estrita de espera de 1 por 1 em Python, inflando o tempo médio percebido.

Para alcançar a **mesma performance nativa (~50 ms)** do modelo original e processamento paralelo real nos núcleos da CPU, o modelo retreinado pode ser empacotado diretamente no runtime do **Ollaya** em C++.

---

### 7.2. Como o Ollaya Organiza os Modelos (Arquitetura OCI)

O container do Ollaya (`ghcr.io/ollaya-dev/ollaya`) opera de forma similar ao Docker / Ollama:
1. **Camadas de Blobs (`/home/ollaya/.ollaya/models/blobs/sha256-...`):**
   - **Grafo ONNX (`application/vnd.ollaya.graph.onnx`):** Grafo computacional compilado para ModernBERT/mmBERT com kernels otimizados em C++ (ONNX Runtime).
   - **Pesos (`application/vnd.ollaya.weights`):** Arquivo bruto de tensores `model.safetensors` (~643 MB).
   - **Tokenizador (`application/vnd.ollaya.tokenizer`):** `tokenizer.json` de alta velocidade em Rust.
   - **Metadados:** Arquitetura, calibração de temperatura e decisões tipadas.
2. **Manifesto (`/home/ollaya/.ollaya/models/manifests/...`):** Arquivo JSON declarativo que aponta para os digests dos blobs.

Como o script de fine-tuning (`train_laya_pix.py`) produz um `model.safetensors` com os novos pesos ajustados (onde o tamanho do cabeçalho JSON e a ordem das chaves mudam ligeiramente), **o grafo ONNX precisa ser adaptado para apontar para o novo blob e seus offsets exatos de bytes**:
- Os tensores externos no ONNX Runtime utilizam o campo `location` com o nome do arquivo relativo (ex.: `sha256-<hash>`) e `offset`/`length` em bytes.
- O script automatizado [`scripts/register_native_laya.py`](scripts/register_native_laya.py) extrai os grafos originais do Ollaya, recalcula os offsets de cada um dos 168 tensores a partir do cabeçalho do `model.safetensors` retreinado, gera novos grafos FP32 e FP16 vinculados aos novos pesos e cria o manifesto `laya:pix-threats`.

---

### 7.3. Automação do Empacotamento Nativo

Para empacotar o modelo retreinado nativamente no Ollaya com todos os grafos ONNX ajustados:

```bash
make register-native-laya
```

O comando executa:
1. Leitura do cabeçalho de `finetune/models/pix-threats/model.safetensors` e cálculo do SHA-256.
2. Extração dos grafos ONNX base (FP32 e FP16) do container `pix-ollaya`.
3. Patching automático de todos os tensores externos com os novos offsets de bytes e nome do blob.
4. Geração do blob de calibração de temperatura (`application/vnd.ollaya.calibration`) calibrado na validação.
5. Injeção de todos os novos blobs no volume do Ollaya e criação do manifesto `laya:pix-threats`.
6. Reinicialização a quente do runner no Ollaya (`ollaya stop laya:pix-threats`).

---

### 7.4. Comparativo de Performance e Acurácia Real

Testado no benchmark sintético completo de 200 mensagens (16 ameaças e 184 mensagens legítimas):

| Métrica | Laya Original (`laya:multilingual`) | Laya Retreinado Nativo (`laya:pix-threats`) | Ganho / Impacto |
| :--- | :---: | :---: | :---: |
| **Ameaças Detectadas (Recall)** | **6 de 16 (37.5%)** | **14 de 16 (87.5%)** | **+50.0 p.p. (+133% de recall)** |
| **Falsos Alarmes (FP)** | 15 em 184 (8.1%) | **7 em 184 (3.8%)** | **-53% de falsos alarmes** |
| **F1-Score** | 32.4% | **75.7%** | **+43.3 p.p.** |
| **Acurácia Global** | 87.5% | **95.5%** | **+8.0 p.p.** |
| **Latência Média em Lote (Tela 4)** | ~537 ms | **~502 ms** | Performance nativa C++ idêntica |
| **Consumo de Memória Extra** | Base Ollaya | **Zero container extra** | Economia de ~1.5 GB de RAM |

---

### 7.5. Histórico e Diagnóstico: Por Que a Assertividade Inicial no Ollaya Caiu (2/16) e Como Foi Resolvida

Durante a primeira tentativa de migração do modelo retreinado para o runtime nativo do Ollaya, observou-se uma anomalia severa no benchmark da Tela 4:
- O Laya original detectou **6 de 16 ameaças** (15 falsos alarmes).
- O Laya retreinado nativo detectou apenas **2 de 16 ameaças** (11 falsos alarmes).
- A velocidade estava excelente (~50 ms), mas a assertividade do modelo retreinado estava significativamente pior que o modelo original sem treino.

#### 1. A Causa Raiz Técnica (Engenharia Reversa do Ollaya e ONNX Runtime)
Através da inspeção do binário `/usr/bin/ollaya` e dos processos em `/proc/` dentro do container, identificamos como o Ollaya realmente opera:
1. **O Ollaya não consome `.safetensors` diretamente em C++:** Diferente do Python/PyTorch (que usa `safetensors.torch.load_file` para carregar tensores por nomes de chaves), o Ollaya instancia um runner em Rust/C++ com a biblioteca **ONNX Runtime** (`ort-2.0.0-rc.13`).
2. **Tensores Externos e Deslocamento em Bytes (`data_location: 1`):** Os grafos `graph_fp32.onnx` e `graph_fp16.onnx` utilizam armazenamento externo de tensores. Dentro do protobuf do `.onnx`, cada um dos 168 inicializadores externos armazena três campos:
   - `location`: Nome relativo do blob de pesos (estava hardcoded como `"sha256-9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204"`).
   - `offset`: Deslocamento absoluto em bytes a partir do início do arquivo.
   - `length`: Comprimento exato em bytes do tensor.
3. **Mudança no Cabeçalho do Safetensors:** No fine-tuning, o cabeçalho JSON do novo `model.safetensors` aumentou em 16 bytes (passando de 17.504 para 17.520 bytes) e a ordem dos tensores foi reorganizada.
4. **O Efeito Colateral do Manifesto OCI:** Quando apenas trocamos o hash no manifesto OCI do modelo (`pix-threats`), o ONNX Runtime continuou abrindo o arquivo `sha256-9d628fd9...` (o modelo base original), porque o caminho do arquivo estava embutido **dentro do arquivo binário `.onnx`**, e não no manifesto.
5. **Divergência de Prompt:** Como ambos os modelos estavam executando secretamente os mesmos pesos base, a instrução diferente enviada pelo gateway para o modelo retreinado (`"extorsão ou intimidação"`) fez o modelo base pontuar ainda mais baixo para as ameaças de perseguição e violência direta, caindo de 6 para 2 detecções.

#### 2. A Solução Implementada
1. **Script Automatizado de Patching ONNX ([`scripts/register_native_laya.py`](scripts/register_native_laya.py)):**
   - Extrai os grafos `graph_fp32.onnx` e `graph_fp16.onnx` do container.
   - Analisa o cabeçalho do novo `model.safetensors` e calcula os novos offsets exatos de bytes para cada um dos 168 tensores.
   - Reescreve o campo `location` para o hash do blob retreinado (`sha256-b716580f...`).
   - Salva e publica os novos grafos ONNX compilados e o blob de calibração de temperatura no Ollaya.
2. **Calibração de Critérios no Gateway ([`ollaya_client.py`](services/pix-gateway-service/src/clients/ollaya_client.py)):**
   - O `OllayaClient` passou a aceitar `criteria` customizado.
   - O cliente do Laya retreinado (`ollaya_tuned_client`) foi calibrado para enviar exatamente as instruções e critérios com os quais foi treinado:
     - Instrução: `"A mensagem de Pix contém ameaça, extorsão ou intimidação?"`
     - `threat`: `"ameaça"`
     - `safe`: `"agradecimento ou conversa normal"`

#### 3. Tabela Evolutiva do Benchmark (200 Mensagens Sintéticas)

| Fase da Implementação | Ameaças Detectadas | Falsos Alarmes | Recall | F1-Score | Latência Média | Observações |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **1. Laya Original (Base)** | 6 de 16 | 15 em 184 | 37.5% | 32.4% | ~537 ms | Modelo multilíngue padrão |
| **2. Laya Retreinado no `laya-serve` (Python)** | 14 de 16 | 7 em 184 | 87.5% | 75.7% | ~854 ms | Boa assertividade, mas lento por lock de 1 worker |
| **3. Laya Nativo (Tentativa 1 - sem patch ONNX)** | 2 de 16 | 11 em 184 | 12.5% | 16.7% | ~500 ms | **Bug:** Grafo ONNX continuava lendo o modelo base |
| **4. Laya Nativo (Definitivo - com patch ONNX)** | **14 de 16** | **7 em 184** | **87.5%** | **75.7%** | **~502 ms** | **Resolvido:** Alta assertividade + Alta velocidade |

> **No Conjunto Desafio (50 mensagens escritas à mão):**
> - **Laya Original:** 7 de 20 ameaças detectadas (9 falsos alarmes em 30).
> - **Laya Retreinado Nativo Corrigido:** **16 de 20 ameaças detectadas** (6 falsos alarmes em 30) — um salto de **35% para 80% de recall**.

---

## 8. Cluster de Instâncias do Ollaya para Rajadas de Transações (Opção A)

### 8.1. Motivação e Arquitetura de Escala Horizontal
Em horários de pico comercial do Pix ou em testes de lote em larga escala (ex.: 200 a 1000 mensagens), submeter dezenas de transações simultâneas a um único container do Ollaya gera fila interna de espera (*queue delay* no ONNX Runtime). A primeira mensagem sai em ~50 ms, mas a 50ª mensagem pode demorar mais de 2 segundos esperando sua vez na fila da CPU.

Para solucionar isso sem adicionar proxies intermediários (como Nginx ou Traefik), foi implementada a **Opção A: Client-Side Load Balancing no Gateway**:

```
                       ┌─────────────────────────────────┐
                       │       pix-gateway-service       │
                       │ (OllayaClient c/ Round-Robin)   │
                       └──────────────┬──────────────────┘
                                      │
                   ┌──────────────────┴──────────────────┐
                   ▼                                     ▼
        ┌─────────────────────┐               ┌─────────────────────┐
        │  pix-ollaya (:11435)│               │ pix-ollaya-2 (:11437)│
        │   Runtime C++ ONNX  │               │   Runtime C++ ONNX  │
        └──────────┬──────────┘               └──────────┬──────────┘
                   │                                     │
                   └──────────────────┬──────────────────┘
                                      ▼
                      ┌───────────────────────────────┐
                      │ Named Volume: `ollaya_models` │
                      │  (Pesos e Grafos Compartilhados)
                      └───────────────────────────────┘
```

### 8.2. Componentes da Solução
1. **Múltiplas Réplicas no Docker Compose ([`docker-compose.yml`](docker-compose.yml)):**
   - Instância 1: `pix-ollaya` na porta interna `11435`.
   - Instância 2: `pix-ollaya-2` na porta externa `11437` e rede interna `ollaya-2:11435`.
   - Ambos montam o mesmo volume `ollaya_models` (zero duplicação de disco para os pesos de 680 MB).
2. **Client-Side Round-Robin e Failover no Gateway ([`ollaya_client.py`](services/pix-gateway-service/src/clients/ollaya_client.py)):**
   - Suporte nativo a listas de URLs via `OLLAYA_CLUSTER_URLS` e `LAYA_TUNED_CLUSTER_URLS`.
   - Rotação atômica de requisições entre os nós via Round-Robin.
   - Failover automático: se uma réplica falhar (ex.: timeout ou reinicialização), o cliente tenta automaticamente no próximo nó do cluster antes de falhar.
3. **Warmup Paralelo:**
   - O método `warmup()` aquece todas as réplicas em paralelo via `asyncio.gather`.
4. **Monitoramento e Observabilidade:**
   - O endpoint `GET /health` do gateway reporta `cluster_size`, `cluster_nodes` e a saúde agregada das instâncias.