# Pix Guard: roteiro de cinco minutos

Dez slides visíveis. Os 23 slides originais permanecem ocultos como apoio no mesmo arquivo. A apresentação normal pula o apoio. Use as falas sugeridas e não leia todas as células das tabelas. Os tempos somam 5:00 e devem ser ensaiados no seu ritmo.

## 1. Proteção contra mensagens abusivas no Pix (0:00–0:35)

O banco precisa transmitir segurança, mas ameaças pelo Pix podem comprometer essa percepção. Mesmo com o contato bloqueado em outro aplicativo, alguém pode enviar centavos e uma ameaça no campo de mensagem. A reportagem sobre o Pix mostra esse desvio de uso. A notícia sobre feminicídios contextualiza a gravidade da violência, sem estabelecer causalidade com o Pix. O Pix Guard propõe identificar essas mensagens no banco de quem envia, antes de concluir a transferência.

## 2. Escopo do projeto (0:35–0:45)

O app do BV recebe e envia Pix. A POC se limita ao CashOut: analisa mensagens em envios de até dez reais.

## 3. Volume de triagem e tempo disponível (0:45–1:20)

Estimamos cerca de 277 mil CashOut por dia, dos quais 12 mil entram na triagem, ou 4,34% dos envios. A análise precisa dividir tempo com antifraude, validação de saldo e preparação da ordem. Para ilustrar a iniciação no BV antes do envio ao SPI, usamos valores fictícios: 0,7 segundo no p50 e 1,2 segundo no p95.

## 4. Desenho da solução na visão funcional (1:20–1:35)

O cliente confirma o Pix e o banco verifica antifraude e saldo. O Pix Guard avalia a mensagem antes da ordem. Se detectar risco, bloqueia o envio e pode abrir uma investigação. Os demais seguem ao SPI.

## 5. Desenho da solução técnica da POC (1:35–1:50)

Medimos o CashOut na POC rodando no M5. Em sessenta chamadas com triagem, a resposta HTTP teve p50 de 45,9 milissegundos e p95 de 50,1. A inferência teve mediana de 28,8 milissegundos.

## 6. Porque usamos o Decision Model Laya (1:50–2:10)

Testamos um LLM via API e o Laya local. O Gemini levou 839 milissegundos na mediana, contra 65 do Laya nesse teste. Escolhemos o modelo local para a triagem. A investigação com Gemini fica em segundo plano.

## 7. Como o Laya identifica mensagens de risco (2:10–2:55)

As três perguntas separam violência, extorsão e coerção. Elas entram juntas no mesmo processamento. A regra usa o maior escore, sem pesos manuais ou média, para não diluir um sinal forte de ameaça. O corte operacional é 0,65 no original e 0,40 no retreinado. O treino documentado usa três mil mensagens, com mil e duzentas ameaças. Ajustamos encoder e cabeça de decisão por cinco épocas, depois calibramos na validação e avaliamos em teste separado. Existe uma expansão de vinte mil mensagens preparada, mas não atribuímos os resultados a ela sem um relatório final.

## 8. Qualidade após o retreino (2:55–3:40)

Para comparar o retreino de forma justa, usamos a mesma pergunta e o mesmo corte nos dois modelos. No conjunto sintético, o recall passou de 14,7% para 90,7%, e as ameaças não detectadas caíram de 64 para sete. No desafio manual, detectamos dezesseis das vinte ameaças, com recall de 80% e F1 de 76,2%. Há uma limitação importante: os falsos bloqueios manuais subiram de cinco para seis. A tela ao lado é uma captura real do simulador. Esses resultados sustentam uma melhoria da POC, mas ainda não demonstram qualidade em dados reais do banco.

## 9. Latência: Laya local e Gemini via API (3:40–4:30)

Também chamamos o Laya retreinado e o Gemini real para três textos: ameaça, chantagem e conversa normal. Foram dez repetições de cada texto por motor, após aquecimento, e os dois repetiram as decisões esperadas sem erros. Na chamada completa, o Laya teve p50 de 64,7 milissegundos e p95 de 157,4. O Gemini teve p50 de 838,7 e p95 de 1.028,9 milissegundos: treze vezes a mediana local. Ele ficou abaixo de 1,5 segundo em todas as chamadas, mas sua mediana sozinha equivale a 93% da referência de 0,9 segundo. Os outros tempos abaixo vêm de ensaios diferentes e não podem ser misturados.

## 10. Custo mensal da solução no GCP (4:30–5:00)

Para a implantação proposta, usamos a calculadora do GCP com duas réplicas com GPU em São Paulo, banco regional com failover e rede. A base é de 1.665 dólares por mês, incluindo cerca de 112 dólares de Gemini global para investigar dez por cento dos casos. Com reserva de vinte por cento, o orçamento fica próximo de dois mil dólares. Esse dimensionamento ainda precisa de teste de carga no GCP e de avaliação com dados reais.

## Consulta após a apresentação

As versões alternativas dos slides 3 e 6 ficam ocultas logo após os originais. O apoio ocupa os slides 13 a 35. As páginas preservam o número da versão completa. Selecione um slide oculto no modo de edição para consultar.
