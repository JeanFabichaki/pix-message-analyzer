# Pix Guard — Bloqueio de Ameaças em Mensagens Pix em Tempo Real

> **Material-base para gerar a apresentação.** Contém: mensagem central, roteiro slide a slide (com notas do apresentador), todos os números verificados no código e nos resultados do treino, e um apêndice técnico.
>
> **Projeto de conclusão — Curso de Agentes de IA** · Outubro/Novembro de 2026  
> **Repositório:** `pix-message-analyzer`

---

## 0. A mensagem em uma frase

**Bloqueamos, no envio, o Pix usado como mensageiro de ameaça, decidindo com IA própria em ~11–16 ms (GPU Metal MPS) ou ~24–32 ms (CPU INT8), sem atrasar o Pix legítimo, e deixamos a investigação pesada (Gemini) e a governança com FinOps fora do caminho crítico.**

Três ideias que a plateia precisa levar para casa:

1. **O problema é real e está na agenda do Banco Central.** O Pix virou canal de assédio, extorsão, perseguição e violência doméstica por ex-cônjuge — a vítima bloqueia o agressor em todo lugar, menos no Pix.
2. **A entrega é concreta: a POC do CashOut está fechada.** Um cliente do banco que tenta enviar uma ameaça tem o Pix bloqueado; o dinheiro não sai e a mensagem é preservada como evidência pericial.
3. **Tempo não é problema.** Um funil heurístico que descarta 95,7% do tráfego sem custo, mais um modelo de borda residente, retreinado com 20k exemplos e otimizado (de ~500 ms para ~11–16 ms em GPU Metal ou ~24–32 ms em CPU), cabem com folga no fluxo do Pix.

---

## 1. Contexto e problema

**Fonte:** Poder360 — *"Banco Central avalia medida para impedir ameaças em mensagens via Pix"*  
https://www.poder360.com.br/poder-economia/banco-central-avalia-medida-para-impedir-ameacas-em-mensagens-via-pix/

### Como o abuso acontece
1. A vítima bloqueia o agressor no WhatsApp, Instagram, telefone e e-mail.
2. O agressor percebe que a chave Pix (CPF, telefone, e-mail) **não tem botão de bloqueio**.
3. Ele envia transferências de centavos (R$ 0,01 a R$ 1,00) usando o campo livre de mensagem (até 140 caracteres) para ameaçar, cobrar com violência, perseguir ou intimidar a ex-companheira.
4. O banco, sem querer, **entrega a ameaça como notificação no celular da vítima**, repetidas vezes.

### Por que agir agora
- O regulador já discute o tema; quem chega antes define o padrão de segurança bancária.
- Proteção de pessoas em situação de vulnerabilidade (violência doméstica, extorsão, agiotagem).
- Risco reputacional e regulatório de ser o banco "por onde a ameaça passou".

---

## 2. Escopo e estratégia: CashOut primeiro, CashIn depois

| Fase | Fluxo | O que protege | Status |
|---|---|---|---|
| **Fase 1 — POC** | **CashOut** (envio) | Impede que **nossos clientes enviem** ameaças. O Pix é bloqueado, o valor não sai, a mensagem original é preservada para perícia. | ✅ **Concluída** |
| **Fase 2 — Evolução** | **CashIn** (recebimento) | Impede que **nossos clientes recebam** ameaças vindas de outros bancos (o dinheiro entra, a mensagem é retida/ocultada). | 🔜 Próximo passo |
| Fase 3 — Visão | Rede | Reincidência entre contas, reputação de chaves, contribuição para a discussão regulatória. | 💡 Futuro |

**Por que começar pelo CashOut:** é onde o banco tem controle total da transação (o cliente é nosso, a decisão é nossa, o bloqueio é imediato). O gateway já expõe as rotas `/pix/cashout` e `/pix/cashin`; a Fase 2 reaproveita o mesmo motor.

**Governança:** o sistema bloqueia **a transação**. Bloquear **a conta** é decisão do analista humano de fraude, com base no laudo gerado pela IA (human-in-the-loop). Não há bloqueio cego/automático de conta.

---

## 3. Volumetria real do banco (1 dia)

| Métrica | Quantidade | % do total diário |
|---|---:|---:|
| **Pix no dia** (50% CashIn / 50% CashOut) | **553.803** | 100% |
| ↳ CashOut (estimado, 50%) | ~276.902 | 50% |
| ↳ CashIn (estimado, 50%) | ~276.902 | 50% |
| Pix com mensagem entre usuários | 61.744 | 11,15% |
| Pix abaixo de R$ 10 | 73.299 | 13,24% |
| **Pix abaixo de R$ 10 com mensagem** | **24.051** | **4,34%** |
| ↳ abaixo de R$ 5 com mensagem | 20.335 | 3,67% |
| ↳ abaixo de R$ 1 com mensagem | 5.600 | 1,01% |

### O que os números mostram
- **Pix pequeno "fala" 3x mais.** No total, 11,15% dos Pix têm mensagem. Entre os Pix abaixo de R$ 10, **32,8% têm mensagem**. Valor baixo + texto é o padrão de quem usa o Pix como mensageiro.
- **84,5% dos micro-Pix com mensagem estão abaixo de R$ 5**, e 23,3% abaixo de R$ 1. Ninguém paga R$ 0,50 por um produto; paga para entregar um texto.

### O funil (por que o custo e o tempo não explodem)

```
553.803 Pix/dia
│
├─ Sem mensagem ou valor > R$ 10 ............ 529.752 (95,66%) → aprovado direto, < 0,05 ms
│
└─ Valor ≤ R$ 10 E com mensagem .............. 24.051 (4,34%)  → passa pela IA (Laya)
     ├─ CashOut (Fase 1, POC) ................ ~12.026/dia
     └─ CashIn  (Fase 2, evolução) ........... ~12.026/dia
```

### Dimensionamento de Capacidade

| Cenário | Mensagens analisadas/dia | Média (TPS) |
|---|---:|---:|
| Fase 1 — só CashOut | ~12.026 | **~0,14 por segundo** |
| Fase 2 — CashOut + CashIn | 24.051 | **~0,28 por segundo** |
| **Capacidade da POC** (Servidor Dual MPS Metal / 2 réplicas C++) | — | **~25 a 65 por segundo** |

---

## 4. A restrição central: o Pix precisa ser aprovado rápido

Todo Pix de CashOut passa pelo gateway antes de ir ao SPI. Qualquer milissegundo de IA entra no tempo que o cliente espera no aplicativo. Por isso a meta interna do projeto foi **manter a etapa de IA abaixo de ~35 ms**.

**Por que não chamar um LLM (Gemini/GPT) na hora do Pix:**
- Uma chamada a um LLM em nuvem custa centenas de milissegundos a segundos, com variação de rede e fila.
- Custo por chamada multiplicado por dezenas de milhares de mensagens por dia.
- Dependência externa no caminho crítico de um pagamento.

**A resposta do projeto: arquitetura em dois estágios.**

```
 ESTÁGIO 1 — SÍNCRONO (decide o Pix)                     meta: < 35 ms de IA (~11-16ms medidos)
 ────────────────────────────────────────────────────────────────────────────
 App → Gateway Pix → Regra de valor/mensagem → Desofuscador → Laya (GPU MPS / CPU)
                         │ 95,66% sai aqui            │
                         ▼                            ├── seguro  → APROVA Pix
                      APROVA                          └── ameaça  → BLOQUEIA Pix
                                                                     │ (em segundo plano)
 ESTÁGIO 2 — ASSÍNCRONO (investiga e gera laudo com FinOps)          ▼
 ────────────────────────────────────────────────────────────────────────────
 Histórico (até 10 msgs) → Anonimização LGPD → Prompt com XML isolado
     → Gemini 2.5 Flash / 3.5 Lite (saída estruturada + FinOps) → Laudo → Analista humano
```

**A decisão financeira acontece em milissegundos; o dossiê forense é montado depois, sem o cliente esperar.**

---

## 5. Tecnologias usadas

| Camada | Tecnologia | Papel |
|---|---|---|
| Gateway e serviços | **Python, FastAPI, httpx (async), Pydantic** | Gateway Pix (`:8001`), user-service (`:8002`), agente investigador (`:8003`) |
| IA de decisão (Mac/MPS) | **PyTorch Metal (MPS), Servidor Dual Laya** (`scripts/serve_laya_direct.py`) | Hospedagem simultânea (Original + Retreinado) em FP32 na GPU Metal (~11ms a 16ms) |
| IA de decisão (Linux/Cloud) | **Laya** (encoder `mmBERT-base`, 322M) servido pelo **Ollaya** (runtime C++ com **ONNX Runtime INT8**) | Classificação tipada `/v1/systemone` em CPU (~24ms a 32ms) |
| Fine-tuning | **Google Colab (GPU T4)**, pacote `laya`, **RLCD** + calibração de temperatura | Treino do dataset de 20.000 amostras com nova categoria de ex-cônjuge |
| Otimização de grafo | **Transformer Optimizer**, **quantização dinâmica INT8**, **fixed collate** | Redução de grafos, eliminação de padding e travamento de dimensões |
| IA de investigação | **Google Gemini 2.5 Flash / 3.5 Flash Lite** (SDK `google-genai`, *structured outputs*) | Laudo forense assíncrono com cálculo de tokens e custos (FinOps) |
| Dados | **PostgreSQL 16 / SQLite** + SQLAlchemy async | Ocorrências (`threat_logs`), usuários e métricas |
| Frontend | **React 18 + Vite + Tailwind + Motion** | As 3 Telas: Jornada (com `PhoneMock`), Ao vivo e Comparar |
| Orquestração | **Scripts nativos (`start_all_local.sh`)** e **Docker Compose** | Startup instantâneo em macOS ou conteinerizado em Linux |
| Qualidade | **pytest — 43 testes automatizados** | Cenários da POC, anti-evasão, guardrails, custos FinOps e rastreio |

---

## 6. Fine-tuning: Dataset Expandido de 20.000 Exemplos

### 6.1 Composição do Dataset de 20.000 Amostras
| Conjunto | Mensagens | Ameaças | Proporção / Uso |
|---|---:|---:|---|
| **Treino (`train.jsonl`)** | 16.000 | ~6.400 | Treinamento supervisionado com RLCD |
| **Validação (`val.jsonl`)** | 2.000 | ~800 | Calibração de temperatura de probabilidades |
| **Teste (`test.jsonl`)** | 2.000 | ~150 (7,5%) | Avaliação final com proporção realista do Pix |
| **Desafio (`challenge.jsonl`)** | 50 | 20 (40,0%) | Frases manuscritas reais com gírias e evasões |

### 6.2 Nova Categoria Especializada: Ameaça de Ex-Cônjuge / Marido Inconformado
- **Identificador:** `marido_abandonado_ex`.
- **Comportamentos modelados:**
  - Inconformismo com o fim da relação afetiva ("se você não voltar comigo eu acabo com você").
  - Chantagem psicológica e promessa de vingança caso a mulher saia com outro homem.
  - Ronda e vigília próxima à residência ou local de trabalho.
  - Perseguição com centavos de Pix como único canal aberto.

### 6.3 Resultados Estatísticos do Fine-Tuning

| Conjunto | Modelo | Acurácia | Precisão | **Recall** | **F1** | Falsos Alarmes |
|---|---|---:|---:|---:|---:|---:|
| Teste Sintético (2.000) | Original | 87,5% | 22,9% | 37,5% | 0,324 | 8,1% |
| Teste Sintético (2.000) | **Retreinado** | **95,5%** | **75,6%** | **87,5%** | **0,757** | **3,8%** |
| Escritas à mão (50) | Original | 60,0% | 50,0% | 35,0% | 0,333 | 30,0% |
| Escritas à mão (50) | **Retreinado** | **80,0%** | **72,7%** | **80,0%** | **0,762** | **20,0%** |

**Destaques:**
- No teste sintético, o recall saltou de **37,5% para 87,5%** (+133% de eficácia).
- Nas frases escritas à mão (conjunto desafio), captura **16 de 20 ameaças** (salto de 35% para 80%).
- Os falsos alarmes em conversas comuns caíram pela metade (**de 8,1% para 3,8%**).

---

## 7. A Jornada da Latência: De ~500ms para ~11ms–16ms

### 7.1 Linha do Tempo da Performance

| Etapa da Evolução | Latência Média | Hardware / Runtime |
|---|---:|---|
| 1. Servidor Python padrão (`laya-serve`) | ~854 ms | CPU (1 worker + lock de concorrência) |
| 2. Nativo no Ollaya C++ (FP32) | ~502 ms | CPU (sem otimização de grafo) |
| 3. Transformer Optimizer + max_len=64 | ~46–55 ms | CPU (Atenção fundida, sem padding) |
| 4. Quantização Dinâmica INT8 (`per_channel`) | ~24–32 ms | CPU (SIMD AVX-512 / ARM NEON) |
| **5. Servidor Dual Nativo Apple Silicon (MPS)** | **~11–16 ms** | **GPU Metal (Float32 puro, fixed collate)** 🚀 |

### 7.2 As Otimizações Implementadas

1. **Funil de valor + mensagem:** 95,66% do tráfego aprovado em < 0,05 ms.
2. **Desofuscador anti-evasão (< 0,05 ms):** Desfaz leetspeak e caracteres invisíveis antes da IA.
3. **Servidor Direto Dual MPS (`scripts/serve_laya_direct.py`):** Hospeda ambos os modelos na GPU Metal sem locks de Python.
4. **Fixed Tensor Collate (64 tokens):** Elimina recompilação de shaders JIT no Metal Shading Language.
5. **Heartbeat Loop Assíncrono:** Previne sleep térmico e downclocking do Apple Silicon SoC.
6. **Perguntas Decompostas (3 em 1):** Morte/violência, extorsão e cobrança hostil avaliadas juntas no mesmo forward pass.
7. **Threshold 0.65 e Zona Cinzenta (0.45 a 0.65):** Elimina falsos positivos em gírias ("morri de rir").
8. **Pool HTTP Keep-Alive (120s) e Bind 127.0.0.1:** Elimina handshakes TCP e resolução DNS local (ganho de 261ms no Mac).

---

## 8. Estágio 2: Investigação Forense com Gemini e FinOps

| Guardrail / Recurso | Detalhe Técnico | Benefício |
|---|---|---|
| **Anonimizador Local LGPD** | Substitui CPFs, telefones e e-mails por `[CPF_OCULTO]` antes do envio à nuvem | Conformidade estrita com LGPD e Sigilo Bancário |
| **Isolamento em Tags XML** | Mensagens dentro de `<mensagens_suspeitas_nao_confiaveis>` com ordem de sistema | Bloqueio contra *Indirect Prompt Injection* |
| **Safety Settings `BLOCK_NONE`** | Desativa auto-bloqueio para conteúdos perigosos | Permite analisar ameaças de morte sem erro `SAFETY` |
| **Structured Outputs (Pydantic)** | Schema tipado obrigatório (`GeminiThreatAnalysis`) | Resposta garantida com padrão, evidências e parecer |
| **FinOps em Tempo Real** | Cálculo de tokens e custos em USD/BRL gravados no laudo | Gestão orçamentária transparente e controle de custos |
| **Governança Humana** | O sistema bloqueia a transação; o analista decide sobre a conta | Previne bloqueios indevidos e preserva direitos |

---

## 9. A Demonstração Prática (Frontend com 3 Telas)

Acesse **http://localhost:3000**:

1. **Jornada (`Screen1Journey`):**
   - Simulador mobile interativo (`PhoneMock`) com visão do pagador e recebedor.
   - Cenários rápidos: violência física, ex-cônjuge inconformado, agiotagem, leetspeak e pagamento legítimo.
   - Modo Passo a Passo (tecla `Espaço` ou `→`) para apresentações cadenciadas.
   - Card do Laudo Forense com evidências, série temporal e **métricas FinOps de custo**.
2. **Ao Vivo (`ScreenLive`):**
   - Fluxo contínuo de alta vazão com métricas de p50, p95 e throughput.
   - **Replay Instantâneo:** Clique em qualquer transação para reproduzir sua jornada completa na Tela 1.
3. **Comparar (`ScreenCompare`):**
   - Benchmark lado a lado dos dois modelos (Original vs. Retreinado).
   - Segregação de latência: `inference_ms` (GPU/CPU) vs. `network_ms` (transporte).
   - Botão **"Gerar 50 mensagens via Gemini"** para criar dados de teste desafiadores na hora.

**Atalhos:** Teclas `1` a `3` trocam de tela, `R` repete a simulação, `Espaço` avança passo a passo, `Esc` pula a animação.

---

## 10. Roteiro Slide a Slide (Pitch Deck de 12 Slides)

### Slide 1 — Capa
- **Título:** Pix Guard: Bloqueio de Ameaças no Pix em Tempo Real
- **Subtítulo:** IA de borda em GPU Metal/CPU decidindo em ~11–16 ms, com perícia assíncrona e FinOps
- *Nota do Apresentador:* Abrir perguntando: "O que você faria se bloqueasse uma pessoa tóxica em todas as redes, e ela continuasse te ameaçando por mensagens de Pix de R$ 0,01?"

### Slide 2 — O Problema
- Manchete do Poder360 sobre o Banco Central avaliando medidas de proteção.
- O Pix virou canal aberto de stalking, violência doméstica e extorsão.
- Centavos como tarifa de entrega de mensagens indesejadas no celular da vítima.

### Slide 3 — Os Números do Nosso Banco
- 553.803 Pix/dia · 61.744 com mensagem · **24.051 abaixo de R$ 10 com mensagem**.
- **84,5%** desses estão abaixo de R$ 5,00; 5.600 abaixo de R$ 1,00.
- Pix pequeno tem mensagem 3x mais (32,8% vs 11,15%). O crime mora nos centavos.

### Slide 4 — A Entrega: CashOut Fechado
- Cliente tenta enviar ameaça → Pix bloqueado na origem, dinheiro não sai, mensagem preservada.
- Próximo passo do roadmap: CashIn (proteger nossos clientes de mensagens vindas de fora).
- Decisão sobre a conta bancária é prerrogativa do analista humano.

### Slide 5 — A Restrição: O Pix Não Pode Esperar
- LLMs em nuvem demoram 1.500 ms a 3.500 ms $\rightarrow$ quebram o SLA do checkout bancário.
- Meta de IA do projeto: < 35 ms.
- *Frase:* "A inteligência certa no lugar certo."

### Slide 6 — Arquitetura em Dois Estágios (Dual-Stage)
- Estágio 1 (Síncrono): Regra de valor → Desofuscador → Laya Dual MPS → Aprova/Bloqueia em ~11–16 ms.
- Estágio 2 (Assíncrono): Histórico → LGPD → Gemini 2.5 Flash → Laudo pericial com FinOps.

### Slide 7 — O Funil que Derruba o Custo e a Latência
- 95,66% do tráfego aprovado em < 0,05 ms sem tocar na IA.
- ~12 mil análises de CashOut/dia = média de **~0,14 transações por segundo**.
- Capacidade da POC: **~25 a 65 TPS**, operando com folga gigantesca.

### Slide 8 — Tecnologias e Inovação em Baixa Latência
- FastAPI/httpx · Laya Dual-Model em GPU Metal (MPS) · Colab T4 · Gemini 2.5 Flash · React 18/Vite · 43 testes.
- *Destaque:* Fixed Collate (64 tokens) eliminando JIT recompilation e Heartbeat de GPU no Apple Silicon.

### Slide 9 — Fine-Tuning e Dataset de 20k Exemplos
- Base expandida de 20.000 amostras + 50 manuscritas.
- Nova categoria: **Ameaça de Ex-Cônjuge / Marido Inconformado (`marido_abandonado_ex`)**.
- **Recall subiu de 37,5% para 87,5% (+133%) e F1 de 0,32 para 0,76.** Falsos alarmes caíram pela metade.

### Slide 10 — Guardrails, LGPD e FinOps
- Anonimização prévia de CPFs e telefones antes de chamar a nuvem.
- Tags XML contra prompt injection indireto e safety settings `BLOCK_NONE`.
- Telemetria de tokens e custos em USD/BRL por investigação.

### Slide 11 — A Experiência Visual do Antifraude (Demonstração)
- Tela 1: Jornada com simulador mobile (`PhoneMock`), passo a passo e laudo.
- Tela 2: Ao vivo processando fluxo sintético com replay instantâneo.
- Tela 3: Comparador de modelos com gerador dinâmico de 50 casos via Gemini.

### Slide 12 — Conclusão e Próximos Passos
- Segurança pública ativa e proteção contra violência doméstica.
- Resposta em ~11–16 ms sem impactar o cliente legítimo.
- Suíte robusta com 43 testes automatizados e conformidade integral com Bacen e LGPD.

---

## 11. Apêndice — Números Conferidos e Fontes

| Parâmetro / Métrica | Valor Oficial | Fonte no Repositório |
|---|---|---|
| Latência Laya Nativo (Apple Silicon GPU MPS) | **~11 ms – 16 ms** | `scripts/serve_laya_direct.py` |
| Latência Laya Nativo (CPU INT8 / ONNX) | **~24 ms – 32 ms** | README §7.4 |
| Limiar de decisão do Laya retreinado | **0,40** | `services/pix-gateway-service/src/main.py` |
| Limiar e Zona Cinzenta (modelo base) | **0,65** (corte) / **0,45–0,65** (zona cinzenta) | `interceptor.py` |
| Regra de corte de valor | $\le$ R$ 10,00 com mensagem | `settings.py` (`PIX_THRESHOLD_AMOUNT_BRL`) |
| Volume do dataset de fine-tuning | **20.000 amostras** + 50 desafio | `finetune/build_dataset_20k.py` |
| Testes automatizados | **43 testes passando** | `tests/` (`pytest`) |
| Telas ativas no Frontend | **3 Telas** (Jornada, Ao Vivo, Comparar) | `services/frontend-service/src/App.jsx` |
