// Fonte única das estações da jornada. Cada uma corresponde a um trecho real do gateway.

export const SYNC_STAGES = [
  {
    id: 'amount_rule',
    n: 1,
    title: 'Precisa analisar?',
    short: 'Valor',
    running: 'Verificando o valor e se há mensagem para analisar…',
    tech: 'interceptor · valor ≤ PIX_THRESHOLD_AMOUNT_BRL e mensagem preenchida',
  },
  {
    id: 'anti_evasion',
    n: 2,
    title: 'Remover disfarces',
    short: 'Disfarce',
    running: 'Procurando letras trocadas, símbolos e separadores no texto…',
    tech: 'common.utils.deobfuscator · deobfuscate_text',
  },
  {
    id: 'ollaya',
    n: 3,
    title: 'IA rápida',
    short: 'IA',
    running: 'A IA rápida (Ollaya) está lendo a mensagem…',
    tech: 'ollaya-client · POST /v1/systemone',
  },
  {
    id: 'delivery',
    n: 4,
    title: 'Desfecho Pix',
    short: 'Desfecho',
    running: 'Decidindo se o Pix é aprovado ou bloqueado…',
    tech: 'interceptor · Bloqueio se ameaça ou aprovação imediata',
  },
];

export const STAGE_INDEX = Object.fromEntries(SYNC_STAGES.map((s, i) => [s.id, i]));

// Estações que rodam em segundo plano após a triagem síncrona.
export const ASYNC_STAGES = [
  {
    id: 'laudo',
    n: 5,
    title: 'Laudo detalhado',
    sub: 'IA de investigação (Gemini)',
    tech: 'gemini-investigation-agent · POST /investigate',
  },
  {
    id: 'ficha',
    n: 6,
    title: 'Ficha de quem enviou',
    sub: 'Governança sob análise do analista',
    tech: 'threat_logs · Histórico para decisão de bloqueio de conta pelo analista',
  },
];

export const STATUS_LABEL = {
  pending: 'Aguardando',
  running: 'Analisando',
  pass: 'Passou',
  skip: 'Não precisou',
  detect: 'Detectou',
  error: 'Falhou',
  void: 'Não chegou aqui',
};

// Rótulos por estação para o veredito curto exibido no nó.
export const VERDICT_LABEL = {
  amount_rule: { pass: 'Analisar', skip: 'Dispensado' },
  anti_evasion: { pass: 'Texto limpo', detect: 'Disfarce' },
  ollaya: { pass: 'Segura', detect: 'Ameaça', skip: 'Não precisou', error: 'Fora do ar' },
  delivery: { pass: 'Aprovado', detect: 'Bloqueado' },
};

export function verdictLabel(stageId, status) {
  return VERDICT_LABEL[stageId]?.[status] || STATUS_LABEL[status] || '';
}

export const DECIDED_BY_LABEL = {
  none: 'Nenhuma estação precisou agir: o Pix foi aprovado normalmente.',
  skipped: 'A regra de valor dispensou a análise desta mensagem.',
  ollaya: 'A IA rápida identificou a ameaça e bloqueou o envio do Pix (estação 3).',
  ollaya_fallback: 'A IA rápida estava fora do ar; o Pix foi aprovado por segurança.',
};
