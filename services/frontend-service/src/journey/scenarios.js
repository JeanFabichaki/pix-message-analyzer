export const RECEIVER = {
  id: 'usr_xyz789',
  name: 'Mariana Costa',
  cpf: '98765432100',
};

// Cada caso percorre um caminho diferente pela jornada.
export const SCENARIOS = [
  {
    id: 'normal',
    icon: 'Coffee',
    title: 'Pix normal',
    path: 'Passa em tudo',
    expects: 'A mensagem chega sem alteração.',
    amount: 5,
    message: 'Amigo, quase morri de rir ontem na festa! Segue o valor da vaquinha do churrasco',
    sender: { id: 'usr_amigo_123', name: 'Lucas B.', cpf: '66778899001' },
  },
  {
    id: 'valor_alto',
    icon: 'Banknote',
    title: 'Valor alto',
    path: 'Dispensado na estação 1',
    expects: 'Acima de R$ 10,00 a mensagem não é analisada. É o limite da regra.',
    amount: 50,
    message: 'Vou te achar na saída do trabalho se não me responder',
    sender: { id: 'usr_valor_alto', name: 'Rafael S.', cpf: '33445566778' },
  },
  {
    id: 'direta',
    icon: 'Siren',
    title: 'Ameaça direta',
    path: 'Pega na IA rápida (estação 3)',
    expects: 'Toda mensagem analisada passa pela IA rápida, que reconhece a ameaça e bloqueia o envio do Pix.',
    amount: 1,
    message: 'Se você não fizer o Pix até 18h sei onde seu filho estuda e sua família vai pagar o pato',
    sender: { id: 'usr_extorsao_02', name: 'Carlos M.', cpf: '22334455667' },
  },
  {
    id: 'disfarcada',
    icon: 'Shuffle',
    title: 'Ameaça disfarçada',
    path: 'Disfarce desfeito na estação 2',
    expects: 'Letras trocadas por números e símbolos são decifradas antes de chegar à IA rápida, bloqueando o envio do Pix.',
    amount: 0.5,
    message: 'v.0.u  t_3  p_3_g_4_r  n4  s41d4  d0  tr4b4lh0  s3  n40  m3  p4g4r  h0j3',
    sender: { id: 'usr_evasion_multi', name: 'Infrator Evasivo', cpf: '55667788990' },
  },
  {
    id: 'sutil',
    icon: 'Brain',
    title: 'Ameaça sutil',
    path: 'Só a IA percebe (estação 3)',
    expects: 'Não usa palavras de ameaça óbvias, mas a IA rápida detecta e bloqueia o envio do Pix.',
    amount: 0.5,
    message: 'Sei exatamente que horas você chega em casa. Seria uma pena se algo acontecesse com você',
    sender: { id: 'usr_sutil_01', name: 'Marcos R.', cpf: '11223344556' },
  },
  {
    id: 'reincidente',
    icon: 'Repeat',
    title: 'Reincidente',
    path: 'Múltiplas ameaças bloqueadas (acumula na ficha)',
    expects: 'Cada ameaça bloqueia o Pix e soma na ficha do infrator para auditoria e tomada de decisão manual do analista.',
    amount: 0.05,
    message: 'Último aviso: se não me pagar você vai morrer vagabundo',
    sender: { id: 'usr_repeat_offender', name: 'Infrator Serial', cpf: '99001122334' },
    burst: 5,
  },
  {
    id: 'livre',
    icon: 'PencilLine',
    title: 'Mensagem livre',
    path: 'Você escolhe',
    expects: 'Digite qualquer mensagem e valor e veja por onde ela passa.',
    amount: 1,
    message: '',
    sender: { id: 'usr_livre_01', name: 'Você', cpf: '12312312312' },
    editable: true,
  },
];

export function newTransactionId() {
  return `tx_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
}

export function buildPayload({ scenario, amount, message, transactionId }) {
  return {
    transaction_id: transactionId || newTransactionId(),
    sender_id: scenario.sender.id,
    sender_cpf: scenario.sender.cpf,
    receiver_id: RECEIVER.id,
    receiver_cpf: RECEIVER.cpf,
    direction: 'CASH_OUT',
    amount: Number.isFinite(Number(amount)) && Number(amount) > 0 ? Number(amount) : 1,
    description: message,
  };
}

export function formatBRL(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}
