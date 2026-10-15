# Laya multilíngue x Laya retreinado (Pix: ameaças e extorsão)

Limiar: 0.4 (o THREAT_THRESHOLD do gateway). Treino: 3000 mensagens (1200 ameaças), 5 épocas, T4 do Colab, ~3 min.

| modelo / conjunto | acurácia | precisão | recall | F1 | falsos+ | falsos− |
|---|---|---|---|---|---|---|
| sem treino / test | 0.899 | 0.229 | 0.147 | 0.179 | 37 | 64 |
| sem treino / challenge | 0.600 | 0.500 | 0.250 | 0.333 | 5 | 15 |
| retreinado / test | 0.971 | 0.756 | 0.907 | 0.824 | 22 | 7 |
| retreinado / challenge | 0.800 | 0.727 | 0.800 | 0.762 | 6 | 4 |

Teste = 1000 mensagens sintéticas (75 ameaças + 925 normais), com fragmentos separados do treino (ver build_dataset.py).
Desafio = 50 mensagens escritas à mão (20 ameaças + 30 normais). O desafio é a leitura mais honesta; o teste sintético tende a ser otimista.
Validação (usada só na calibração de temperatura, temperaturas ~1.0): acurácia 1.000.
Latência no Colab/T4: ~2 ms por mensagem em lote.
