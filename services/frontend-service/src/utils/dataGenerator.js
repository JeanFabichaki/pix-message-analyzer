// Gerador de dados transacionais sintéticos para simulação e teste de vazão da API real do Pix Guard

const BENIGN_MESSAGES = [
  'Pagamento do cafe com a equipe',
  'Almoco de sexta-feira',
  'Gasolina do fim de semana',
  'Divida da pizza de ontem',
  'Presente de aniversario da Carol',
  'Rachando o churrasco',
  'Assinatura do streaming compartilhado',
  'Compra de pao de queijo na padaria',
  'Farmacia - remedios',
  'Supermercado mensal parte 1',
  'Manutencao da bike',
  'Ingresso do cinema',
  'Doacao para campanha do agasalho',
  'Ajuste da corrida do app',
  'Compra de livro usado',
  '',
];

const THREAT_MESSAGES = [
  'Vou te pegar na saida do trabalho se nao me responder',
  'Me paga hoje ou voce vai ver o que acontece',
  'Sei onde voce mora e onde seus filhos estudam',
  'Vou te quebrar inteiro se nao transferir agora',
  'Nao adianta fugir, estou na sua porta te vigiando',
  'Transfere ou vai sofrer as consequencias vagabundo',
  'Vou te achar nem que seja no fim do mundo caloteiro',
  'Seu tempo acabou, se nao me pagar voce vai morrer',
  'Vou espancar voce quando te encontrar na rua',
  'Ultimo aviso: me devolve o dinheiro ou vai dar ruim pra voce',
];

const SENDERS = [
  { id: 'usr_abc123', name: 'Alice Sender', cpf: '12345678901' },
  { id: 'usr_repeat_01', name: 'Carlos Infrator', cpf: '11122233344' },
  { id: 'usr_repeat_02', name: 'Marcos Cobrador', cpf: '55566677788' },
  { id: 'usr_client_03', name: 'Juliana Costa', cpf: '44433322211' },
  { id: 'usr_client_04', name: 'Rafael Souza', cpf: '99887766554' },
  { id: 'usr_client_05', name: 'Beatriz Lima', cpf: '77665544332' },
];

const RECEIVERS = [
  { id: 'usr_xyz789', name: 'Bob Receiver', cpf: '98765432100' },
  { id: 'usr_rec_02', name: 'Mercado Central LTDA', cpf: '12345678000199' },
  { id: 'usr_rec_03', name: 'Cafe & Cia', cpf: '98765432000188' },
  { id: 'usr_rec_04', name: 'Dona Maria Doces', cpf: '33221144000155' },
];

export function generateSyntheticPix() {
  const isThreatCandidate = Math.random() < 0.22;
  const sender = SENDERS[Math.floor(Math.random() * SENDERS.length)];
  const receiver = RECEIVERS[Math.floor(Math.random() * RECEIVERS.length)];

  let amount;
  let description;

  if (isThreatCandidate) {
    // 80% das ameaças são micro-pix (< R$ 10) para testar a triagem em tempo real, 20% acima
    const isMicro = Math.random() < 0.8;
    amount = isMicro ? parseFloat((Math.random() * 9.9 + 0.05).toFixed(2)) : parseFloat((Math.random() * 250 + 15).toFixed(2));
    description = THREAT_MESSAGES[Math.floor(Math.random() * THREAT_MESSAGES.length)];
  } else {
    // Transações normais
    amount = parseFloat((Math.random() * 450 + 1.5).toFixed(2));
    description = BENIGN_MESSAGES[Math.floor(Math.random() * BENIGN_MESSAGES.length)];
  }

  const txId = `tx_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 6)}`;

  return {
    transaction_id: txId,
    sender_id: sender.id,
    sender_name: sender.name,
    sender_cpf: sender.cpf,
    receiver_id: receiver.id,
    receiver_name: receiver.name,
    receiver_cpf: receiver.cpf,
    direction: 'CASH_OUT',
    amount,
    description,
    timestamp: new Date().toLocaleTimeString(),
  };
}
