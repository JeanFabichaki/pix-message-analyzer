# Laya retreinado × Gemini via API

Execução: 2026-11-04T07:55:03.242942-03:00

Triagem de ameaça, chantagem e coerção no texto. Não identifica fraude transacional.

| Motor | Chamadas válidas | Erros | p50 (ms) | p95 (ms) | Máximo (ms) |
|---|---:|---:|---:|---:|---:|
| laya | 30 | 0 | 64.66 | 157.38 | 194.04 |
| gemini | 30 | 0 | 838.72 | 1028.93 | 1071.54 |

## Mensagens sintéticas

- **M1 (Ameaça física):** Se você me bloquear, vou te esperar na saída e te matar.
- **M2 (Chantagem):** Pague R$ 500 até hoje ou vou divulgar suas fotos íntimas.
- **M3 (Conversa normal):** Valeu pelo café! Quase morri de rir das suas histórias.

## Condições e limites

- Três textos sintéticos selecionados manualmente. Repetições medem variação de tempo, não ampliam a diversidade.
- Percentis exploratórios desta execução, sem validade de SLA, teste de carga ou acurácia generalizável.
- Laya local e Gemini remoto: o resultado compara alternativas de implantação e inclui rede no Gemini.
- Tempo de classificação apenas. Não inclui antifraude, saldo, gateway completo nem processamento BACEN/SPI.
- Gemini retorna somente is_threat em JSON, com thinking configurado. Não gera o laudo forense usado no agente.
- Aquecimento dos três textos de ambos os motores fica separado. Chamadas sequenciais com ordem alternada e seed fixa.
- Os rótulos esperados são definições manuais destes exemplos. Uma mensagem normal não prova que o Pix é legítimo.
- Não há cache explícito nem retries. Tokens de cache implícito retornados pela API são preservados em usage.

Configuração, decisões de cada chamada, aquecimento, tokens e versões constam em report.json.
Não há retry automático. Erros não entram nos percentis nem são convertidos em mensagens seguras.
