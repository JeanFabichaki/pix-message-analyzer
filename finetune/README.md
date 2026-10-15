# Tutorial: fine-tuning do Laya para detectar ameaças e extorsão em mensagens de Pix

Este diretório mostra, de ponta a ponta, como o Laya foi especializado em um problema novo: dizer se a mensagem
de um Pix contém **ameaça, extorsão ou intimidação**. O caminho é reaproveitável em outros projetos: troque o
problema, os dados e a pergunta, e o resto vale igual.

Resumo do caminho:

1. Entender o que o Laya é (e que o fine-tuning não é LoRA).
2. Montar um dataset sintético sem vazamento entre treino e teste.
3. Medir o modelo **antes** de treinar (linha de base).
4. Treinar no Google Colab (GPU T4, cerca de 3 minutos).
5. Calibrar, salvar e medir de novo.
6. Servir o checkpoint em Docker e escolher o modelo no frontend.
7. Comparar os dois modelos pela tela **Comparar**.

## Resultado em uma tabela

Limiar de decisão 0,40, o mesmo do gateway.

| modelo / conjunto | acurácia | precisão | recall | F1 | falsos alarmes | ameaças perdidas |
|---|---|---|---|---|---|---|
| original / teste sintético (1000) | 0,899 | 0,229 | 0,147 | 0,179 | 37 | 64 |
| **retreinado** / teste sintético | **0,971** | **0,756** | **0,907** | **0,824** | 22 | 7 |
| original / escritas à mão (50) | 0,600 | 0,500 | 0,250 | 0,333 | 5 | 15 |
| **retreinado** / escritas à mão | **0,800** | **0,727** | **0,800** | **0,762** | 6 | 4 |

Leitura rápida: o original pegava 11 de 75 ameaças no teste sintético; o retreinado pega 68. Nas 50 mensagens
escritas à mão, que é o teste mais honesto, o original pega 5 de 20 ameaças e o retreinado 16. Os arquivos
completos estão em [`results/report.md`](results/report.md) e [`results/metrics.json`](results/metrics.json).

---

## 1. O que é o Laya (leia antes de treinar)

- **Não é um LLM.** É um *encoder* com uma cabeça de decisão tipada. Para português usamos o checkpoint
  `multilingual/` do repositório `convaiinnovations/laya` no Hugging Face, baseado no `mmBERT-base` (322M parâmetros).
- Ele responde **perguntas tipadas** sobre um texto. Aqui a pergunta é do tipo `choice` (escolha uma opção):
  ```json
  {"threat": {"type": "choice",
              "instructions": "A mensagem de Pix contém ameaça, extorsão ou intimidação?",
              "criteria": {"threat": "ameaça", "safe": "agradecimento ou conversa normal"}}}
  ```
- **O fine-tuning não é LoRA.** O notebook oficial do Laya usa **RLCD**: gradiente de política com *proper
  scoring rules* (SPH + RPS) mais entropia cruzada suave, seguido de **calibração de temperatura**. Todos os
  pesos são treinados (o encoder com taxa de aprendizado menor que a cabeça).
- O campo `instructions` é **obrigatório** em `laya.Agent`. Sem ele a chamada falha com
  `ValueError: no 'instructions'`. Esse foi o primeiro erro que apareceu neste projeto.
- O framework "It's Fine" do vídeo de referência (Sandeco, https://www.youtube.com/watch?v=YGuLBJ6af_o) é do
  autor do vídeo e **não é usado** aqui. Aproveitamos o roteiro (dataset sintético, linha de base, treino no
  Colab, comparação antes/depois), mas o treino em si usa a API do pacote `laya`.

## 2. Arquivos deste diretório

| arquivo | para quê |
|---|---|
| `build_dataset.py` | gera `train/val/test.jsonl` sintéticos em PT-BR |
| `train_laya_pix.py` | linha de base, treino (GPU única), calibração, avaliação e salvamento |
| `data/{train,val,test}.jsonl` | 3000 / 554 / 1000 mensagens |
| `data/challenge.jsonl` | 50 mensagens escritas à mão, fora do gerador |
| `results/` | `metrics.json` e `report.md` do treino real |
| `serve/Dockerfile` | servidor `laya-serve`, com o mesmo contrato `/v1/systemone` do Ollaya |
| `models/pix-threats/` | checkpoint retreinado (~650 MB, **não versionado**, está no `.gitignore`) |

## 3. Passo 1: definir o problema e a pergunta

Antes de qualquer código, responda três coisas:

1. **O que é "positivo"?** Aqui, `threat` (ameaça, extorsão, intimidação) contra `safe` (qualquer outra coisa).
2. **Qual custo pesa mais?** Deixar uma ameaça passar (falso negativo) ou travar uma mensagem normal (falso
   positivo)? Isso define o limiar. O gateway usa `THREAT_THRESHOLD = 0,40`: prefere avisar a mais.
3. **Qual é a pergunta exata?** O texto de `instructions` e os `criteria` entram no treino. **A mesma pergunta
   tem de ser enviada em produção**, palavra por palavra. Neste repositório ela existe em dois lugares:
   - `train_laya_pix.py` (constante `QUESTIONS`)
   - `services/pix-gateway-service/src/clients/ollaya_client.py` (`TUNED_INSTRUCTIONS`)

   Se mudar o texto, mude nos dois e retreine.

## 4. Passo 2: gerar o dataset (`build_dataset.py`)

Não havia dados reais de ameaças em Pix, então o dataset é **sintético**: frases montadas a partir de pools
de fragmentos.

**Pools de ameaça** (rótulo `threat`): violência (`vou te pegar na saída do trabalho`), exigência de dinheiro
(`paga {valor} agora`), chantagem (`senão eu mando suas fotos`), consequência (`ou você se arrepende`) e
cobrança agressiva. Elas são combinadas em frases como "exigência + chantagem + consequência".

**Pools de mensagens normais** (rótulo `safe`), e aqui está o ponto mais importante do dataset:

- pagamentos e agradecimentos comuns (`Pagamento do almoço, obrigado!`);
- cobranças educadas (`Pode me mandar o aluguel até o dia 10?`);
- mensagens neutras;
- **negativos difíceis** (`idioma_violento`): gírias e expressões que *parecem* ameaça mas não são
  (`vou te matar de rir`, `esse bolo é um crime`). Sem eles o modelo aprende só "palavra feia = ameaça".

**Anti-vazamento.** Se a mesma frase aparecer no treino e no teste, a nota do teste não vale nada. Por isso
cada pool de fragmentos é embaralhado com seed fixa (`SEED = 20261014`) e **particionado**: 60% dos
fragmentos vão para o treino, 15% para a validação e 25% para o teste. Um fragmento do teste nunca aparece
no treino.

| conjunto | mensagens | ameaças | uso |
|---|---|---|---|
| `train` | 3000 | 1200 | treinar |
| `val` | 554 | 140 | **só** calibrar a temperatura |
| `test` | 1000 | 75 (7,5%) | nota final; proporção parecida com a vida real |
| `challenge` | 50 | 20 | escritas à mão, fora do gerador |

O teste tem poucas ameaças de propósito: na vida real a maioria das mensagens é normal, e a acurácia sozinha
engana (um modelo que nunca avisa nada já acerta 92,5%).

Cada linha tem este formato:
```json
{"id": "...", "split": "test", "text": "Sei onde você mora...", "label": "threat", "category": "violencia"}
```
Categorias: `violencia`, `chantagem`, `cobranca_agressiva`, `extorsao_violenta`, `pagamento`,
`idioma_violento`, `cobranca_educada`, `neutra` (e `manual` no `challenge`).

```bash
python build_dataset.py data      # regenera train/val/test.jsonl (o challenge é escrito à mão)
```

**O conjunto `challenge` existe para desconfiar do resto.** O dataset sintético vem do mesmo gerador que o
treino, então a nota nele tende a ser otimista. As 50 frases escritas à mão usam palavras que o gerador nunca
produziu e mostram como o modelo se comporta fora do "sotaque" do dataset.

## 5. Passo 3: medir antes de treinar (linha de base)

`train_laya_pix.py` começa avaliando o Laya **sem treino** no teste e no desafio. Sem isso você não sabe se o
fine-tuning ajudou. O resultado aqui foi ruim, e isso é informativo:

- teste sintético: recall 0,147 (pegou 11 de 75 ameaças), F1 0,179;
- escritas à mão: recall 0,250, F1 0,333.

O Laya genérico não tinha a menor ideia do que é "ameaça em Pix" para esta pergunta.

## 6. Passo 4: treinar no Google Colab

### 6.1 Preparar o ambiente

1. Abra https://colab.research.google.com e crie um notebook novo.
2. **Ambiente de execução > Alterar o tipo de ambiente de execução > GPU T4** (a gratuita basta).
3. Primeira célula:
   ```python
   !pip -q install "laya>=0.1.6" "transformers>=4.48.0" datasets accelerate tabulate
   ```
4. Suba `build_dataset.py`, `train_laya_pix.py` e `data/challenge.jsonl` (painel de arquivos à esquerda), ou
   suba a pasta `data/` inteira e pule o `build_dataset.py`.
5. Se o Colab pedir para aceitar os termos de uso, aceite na conta que vai usar.

### 6.2 Rodar

```python
!python build_dataset.py data           # opcional: regenera os dados
!python train_laya_pix.py data /content/out 5
```

O script faz, nesta ordem:

1. Baixa `convaiinnovations/laya/multilingual` (`snapshot_download`) e corrige a configuração do tokenizer.
2. **Linha de base** no teste e no desafio.
3. Converte as linhas em itens do Laya (`items_from_rows`) com o *gold* no formato
   `{"threat": {"label": ..., "probabilities": {"threat": p, "safe": 1-p}}}`. Aplica *label smoothing* de 0,02
   (alvo 0,98 em vez de 1,00).
4. **Treina 5 épocas** com RLCD (`rlcd_loss`).
5. **Calibra** a temperatura na validação (`fit_temperature_map`).
6. **Salva** o checkpoint (`save_checkpoint`) e **avalia** no teste, no desafio e na validação.

### 6.3 Hiperparâmetros usados

| parâmetro | valor | observação |
|---|---|---|
| épocas | 5 | a perda estabiliza na 3ª; ver `train_history` em `metrics.json` |
| micro-batch / acumulação | 16 / 2 | batch efetivo 32; cabe numa T4 |
| `GROUP_SIZE` | 4 | amostras do gradiente de política por item |
| LR do encoder / da cabeça | 2,5e-5 / 1e-4 | encoder mais devagar para não esquecer o que já sabe |
| otimizador | AdamW, weight decay 0,01 | LR com decaimento cosseno até 1e-6 |
| sigma (ruído da política) | 0,4 → 0,1 | cai ao longo das épocas (`sigma_at`) |
| pesos da perda | `w_sph=0.75`, `w_rps=1.0` | |
| precisão | fp16 com `GradScaler` | |
| *clipping* de gradiente | 1,0 | |
| *label smoothing* | 0,02 | |
| seed | 7 | |

Tempo real: **174 segundos** de treino (33 s por época) na T4, mais o download do modelo base.

### 6.4 O que observar durante o treino

- A `avg_loss` por época aparece como `=== epoch {...}`. Neste projeto: -0,07, -0,38, -0,40, -0,41, -0,32.
  A perda do RLCD é negativa por construção (é uma recompensa); o que importa é que ela desça e estabilize.
- No fim, a linha `temperaturas: [...]` mostra a calibração. Valores perto de 1,0 indicam que o modelo já
  saiu razoavelmente calibrado.
- As linhas `TUNED test`, `TUNED challenge` e `TUNED val` trazem as métricas. **A validação deu 1,000**, o que é
  esperado: foi o conjunto usado para calibrar. Não use esse número como resultado.

### 6.5 Trazer o checkpoint do Colab para o projeto

O checkpoint tem ~650 MB (`model.safetensors` com 643.835.524 bytes). Opções, da mais simples à mais
trabalhosa:

1. **Google Drive:** `from google.colab import drive; drive.mount('/content/drive')` e copie `/content/out/model`
   para lá. É o caminho mais confiável.
2. **Download direto** da pasta zipada (`!cd /content/out && zip -r model.zip model`, depois baixe pelo painel de
   arquivos).
3. **Download em partes.** Neste projeto o download único de 599 MB travou. Dividir em pedaços resolveu:
   `!split -b 50M model.zip part_` e remonte com `cat part_* > model.zip`.

Coloque o conteúdo em `finetune/models/pix-threats/`. A pasta precisa conter:

```
finetune/models/pix-threats/
  model.safetensors
  rl_agent_config.json
  encoder/config.json
  tokenizer/
```

> O `rl_agent_config.json` ainda traz um bloco `training` herdado do modelo base (`hours: 4.97` etc.). Ele
> **não descreve este treino**; ignore.

## 7. Passo 5: ler os resultados com cuidado

Limiar 0,40 (matriz completa em `results/metrics.json`):

| | tp | fp | fn | tn |
|---|---|---|---|---|
| original / teste | 11 | 37 | 64 | 888 |
| retreinado / teste | 68 | 22 | 7 | 903 |
| original / escritas à mão | 5 | 5 | 15 | 25 |
| retreinado / escritas à mão | 16 | 6 | 4 | 24 |

**Onde o retreinado ainda erra** (ver `challenge_errors` em `metrics.json`). Esta é a parte mais útil para o
próximo ciclo:

- **Ameaças implícitas ou veladas que passam:** `Pix de 1000 e teu segredo morre comigo` (p=0,02),
  `Eu sei com quem você anda e onde seu filho estuda` (0,03), `Quem mexe comigo acaba no hospital` (0,02). O
  gerador quase não produz esse estilo.
- **Mensagens normais que disparam alarme:** `Vou te dar uma surra no truco sábado` (0,97),
  `Se você não vier amanhã, vou sentir sua falta` (0,97), `Cuidado com a chuva hoje, a estrada tá perigosa` (0,97),
  `Pode me mandar o valor do aluguel até o dia 10, por favor?` (0,81). Faltam negativos difíceis desse tipo.

**Como melhorar** (nesta ordem de retorno esperado):

1. Adicionar ao gerador ameaças veladas e mais negativos difíceis (`Vou aí buscar você`, esportes, jogos,
   cuidado/aviso legítimo, cobrança educada com prazo).
2. Reescrever com outras palavras uma parte do treino (parafraseamento) para reduzir o "sotaque" do gerador.
3. Se houver mensagens reais, anonimizá-las e usá-las **só** no teste e no desafio, nunca no treino sem revisão.
4. Reavaliar o limiar (`th_0.3`, `th_0.4`, `th_0.5`, `th_0.7` estão em `metrics.json`).

## 8. Passo 6: servir o modelo (Docker)

O `serve/Dockerfile` usa `python:3.11-slim`, instala PyTorch CPU e `laya[serve]>=0.4.7` e roda `laya-serve`, que
expõe o mesmo contrato `/v1/systemone` do Ollaya. Por isso o gateway usa **o mesmo cliente** para os dois
modelos; muda só a URL, o nome do modelo e a pergunta.

Variáveis do `laya-serve` usadas (no `docker-compose.yml`, serviço `laya-tuned`):

| variável | valor | para quê |
|---|---|---|
| `LAYA_EXTRA_MODELS` | `{"pix-threats":"/models/pix-threats"}` | registra o checkpoint com um nome |
| `LAYA_MODELS` | `pix-threats` | quais modelos carregar |
| `LAYA_PRELOAD` | `1` | carrega no início, não na primeira chamada |
| `LAYA_DEVICE` | `cpu` | sem GPU no container |

O container é opcional: fica no *profile* `tuned` do Compose, então `make up` continua subindo só o Laya
original. A porta do modelo retreinado é 11436 e a pasta `./finetune/models` entra como volume somente leitura.

```bash
make up-tuned   # confere se o checkpoint existe e sobe tudo com o profile 'tuned'
make up         # só o Laya original
make down       # derruba tudo, incluindo o profile 'tuned'
```

### 8.1. Alternativa de Alta Performance: Empacotar nativo no Ollaya (~50 ms)

Se você precisa de latência ultrabaixa em C++ sem o overhead do interpretador Python e sem a trava sequencial de 1 worker do `laya-serve`:

Basta executar o script automatizado:
```bash
make register-native-laya
```

> **Atenção Técnica Crítica:** O Ollaya executa grafos compilados pelo ONNX Runtime. Dentro do arquivo `.onnx`, cada um dos 168 tensores possui apontamento relativo (`location`) e **deslocamentos absolutos em bytes (`offset`)** para o blob de pesos. Apenas alterar o manifesto OCI faz o modelo continuar lendo os pesos antigos ou com offsets desalinhados (queda de detecção para 2/16). O comando `make register-native-laya` resolve isso extraindo os grafos base, recalculando os offsets a partir do cabeçalho do `model.safetensors` e gerando novos grafos FP32 e FP16 no Ollaya (subindo a detecção para 14/16 e ~502 ms em lote).

## 9. Passo 7: escolher o modelo no projeto


- **Frontend:** na barra superior, o seletor **Laya original / Laya retreinado**. A opção offline fica
  desabilitada. A escolha fica salva no navegador.
- **API:** `POST /pix/transactions` aceita `"engine": "laya"` (padrão) ou `"laya_tuned"`;
  `GET /pix/engines` informa quais estão disponíveis. Se o retreinado estiver fora do ar, o gateway cai no
  caminho de contingência já existente.
- **Configuração:** `LAYA_TUNED_BASE_URL` e `LAYA_TUNED_MODEL` (ver `.env.example`).

> Latência: no Colab o modelo respondeu em ~230 a 480 ms por mensagem na CPU. A meta de 15 ms exibida na tela
> **Ao vivo** provavelmente não será cumprida pelo retreinado em CPU. Em GPU, ~2 ms por mensagem em lote.

## 10. Passo 8: tela "Comparar"

A aba **Comparar** (tecla 4) roda `data/test.jsonl` (200 mensagens ou todas) ou `data/challenge.jsonl` pelos
**dois** modelos e mostra, de forma visual: ameaças detectadas, falsos alarmes, placar geral, acertos por
categoria e exemplos em que só um dos modelos acertou.

- Exige os dois modelos online (`make up-tuned`). Se um estiver fora, a tela explica o motivo.
- Endpoints do gateway: `GET /pix/benchmark/datasets`, `POST /pix/benchmark` (devolve `job_id`),
  `GET /pix/benchmark/{job_id}` (progresso e relatório).
- Código: `services/pix-gateway-service/src/services/benchmark.py` (só biblioteca padrão; os clientes são
  injetados, o que permite testar com dublês) e `services/frontend-service/src/components/ScreenCompare.jsx`.
- O compose monta `./finetune/data` em `/data` no gateway.

## 11. Armadilhas encontradas (para você não repetir)

| problema | causa | solução |
|---|---|---|
| `ValueError: no 'instructions'` | `laya.Agent` exige `instructions` na pergunta | pôr o texto no treino **e** no cliente de produção |
| Download de 599 MB travando no Colab | transferência única grande | dividir com `split` ou usar o Drive |
| Nota "perfeita" na validação | a validação calibrou o modelo | reportar só teste e desafio |
| Nota alta no teste e pior na prática | teste vem do mesmo gerador do treino | manter um conjunto escrito à mão |
| Resultado não bate no Docker | pergunta diferente entre treino e produção | `QUESTIONS` e `TUNED_INSTRUCTIONS` idênticos |
| Modelo grita "ameaça" para gírias | faltavam negativos difíceis | pool `idioma_violento` e mais exemplos |
| Modelo retreinado no Ollaya detecta menos que o original (2/16) | Grafo ONNX contém `location` e `offset` de bytes dos tensores antigos hardcoded | Executar `make register-native-laya` para patchar os grafos ONNX e calibrar critérios |

## 12. Receita para reaproveitar em outro projeto

1. Escreva a **pergunta tipada** (tipo, instrução, critérios) e fixe o texto.
2. Gere ou colete dados. Particione **por fragmento/fonte**, não por linha, e congele o teste.
3. Inclua **negativos difíceis**: o que parece o positivo mas não é.
4. Separe um **desafio** pequeno, escrito à mão, que não passe pelo gerador.
5. Meça a **linha de base** antes de treinar.
6. Copie `train_laya_pix.py`, troque `QUESTIONS`, `THRESHOLD` e os caminhos; treine na T4.
7. Calibre na validação e **nunca** reporte a nota da validação.
8. Olhe os erros (`challenge_errors`), ajuste o gerador e repita.
9. Sirva com `laya-serve`, mantendo a mesma pergunta em produção.

## 13. O que não foi verificado

- O container `laya-tuned` e o `docker compose` **não foram executados** no ambiente de desenvolvimento
  (sem Docker lá). O contrato HTTP foi validado no Colab, com a mesma requisição do gateway: mensagem
  "Pagamento do almoço, obrigado!" classificada `safe` (0,98), extorsão `threat` (0,98),
  "vou te matar de rir..." `safe` (0,98) e "Sei onde você mora..." `threat` (0,98).
- O frontend (seletor e tela Comparar) teve a sintaxe validada, mas não foi aberto em um navegador com os
  dois modelos no ar.
- Os testes do projeto não foram executados.

Rode `make up-tuned` e abra a aba **Comparar** para confirmar tudo de ponta a ponta.
