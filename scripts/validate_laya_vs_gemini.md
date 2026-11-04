# Validação de tempo: Laya retreinado e Gemini via API

Execute na raiz do projeto, com o Laya retreinado ativo:

```bash
.venv/bin/python scripts/validate_laya_vs_gemini.py --repetitions 10
```

O script lê `GEMINI_API_KEY`, `GEMINI_MODEL`, `LAYA_TUNED_BASE_URL` e
`LAYA_TUNED_MODEL` do ambiente ou do `.env`, sem registrar a chave. Os parâmetros
`--gemini-model`, `--laya-url` e `--laya-model` substituem essas configurações.
Use `--help` para consultar os demais parâmetros. Se necessário, instale
`httpx` e `python-dotenv` no ambiente Python.

São três textos sintéticos: ameaça física, chantagem e conversa normal com
expressão figurada. Os rótulos esperados são manuais. A tarefa é detectar risco
no **texto**, sem afirmar se o Pix é uma fraude financeira. Nenhuma mensagem de
cliente é usada. O Laya recebe as três perguntas lidas diretamente do gateway,
com agregação pelo maior escore e corte padrão de 0,40. O Gemini recebe os
mesmos critérios e retorna apenas `{"is_threat": true/false}`, sem laudo.

Cada motor recebe três chamadas de aquecimento, excluídas dos percentis, e
30 chamadas medidas (10 para cada texto). Há uma única chamada ativa por vez.
A ordem dos textos é embaralhada com seed 42 e a ordem dos motores alterna em
cada par. O cronômetro cobre o POST HTTP até a validação do JSON. As conexões
são reutilizadas. O Gemini usa `thinkingLevel=MINIMAL`, temperatura zero e
limite de 256 tokens de saída. O parâmetro `--thinking-level default` permite
comparar a configuração padrão do modelo em uma nova execução, identificada
separadamente. Modelos que não aceitam `thinkingLevel` precisam desse modo ou
de uma configuração compatível. Não há fallback nem retry automático.

Cada execução cria uma pasta em `validation_results/laya_vs_gemini/` com:

- `report.json`: configuração, prompts, ambiente, decisões, tokens, versões,
  erros, aquecimento e estatísticas gerais e por mensagem.
- `measurements.csv`: uma linha por chamada, inclusive aquecimento e erros.
- `report.md`: resumo legível.

Erros não são decisões seguras e ficam fora dos percentis de respostas válidas.
Os percentis usam interpolação linear R7. O programa retorna código diferente
de zero em falhas de preparação, aquecimento ou chamadas medidas. O relatório
é atualizado durante a execução, para preservar os resultados já obtidos.

## Execução usada na apresentação

Relatório: `validation_results/laya_vs_gemini/20261104T075503240800/report.json`.
Em 04/11/2026, Apple M5 com Laya em MPS, modelo remoto `gemini-3.5-flash-lite`:

| Métrica da chamada completa | Laya retreinado | Gemini API |
|---|---:|---:|
| p50 | 64,66 ms | 838,72 ms |
| p95 | 157,38 ms | 1.028,93 ms |
| Máximo | 194,04 ms | 1.071,54 ms |
| Erros | 0/30 | 0/30 |

Ambos retornaram os rótulos esperados nas 30 chamadas medidas. São apenas três
textos distintos, o que não permite estimar acurácia geral. A mediana da API do
Gemini foi aproximadamente 13 vezes a do Laya local neste ensaio. Todas as
chamadas válidas ficaram abaixo de 1,5 s. A mediana do Gemini equivale a cerca
de 93% da referência bancária de 0,9 s, mas esses tempos não incluem antifraude,
saldo ou envio ao BACEN. Não some percentis de etapas nem trate a comparação
como comprovação de cumprimento ou violação do prazo de um Pix completo.

O resultado compara duas alternativas de implantação, incluindo a rede externa
do Gemini. Não isola o custo matemático dos modelos, não mede carga e não é SLA.
O ensaio anterior de 18,6 ms da apresentação mede inferência de **uma pergunta**,
em outra execução. Este ensaio mede HTTP completo com **três perguntas** no
Laya e não substitui aquele resultado.

Referências oficiais de configuração:
[saída estruturada](https://ai.google.dev/gemini-api/docs/structured-output) e
[thinking](https://ai.google.dev/gemini-api/docs/thinking).

Verificações locais, sem uso de API:

```bash
.venv/bin/python -m unittest discover -s tests -p test_validate_laya_vs_gemini.py
```
