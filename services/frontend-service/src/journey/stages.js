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
    title: 'Desofuscação',
    short: 'Desofuscação',
    running: 'Procurando letras trocadas, símbolos e separadores no texto…',
    tech: 'common.utils.deobfuscator · deobfuscate_text',
  },
  {
    id: 'ollaya',
    n: 3,
    title: 'Decision Model',
    short: 'Decision Model',
    running: 'O Decision Model está analisando a mensagem…',
    tech: 'ollaya-client · POST /v1/systemone',
  },
  {
    id: 'delivery',
    n: 4,
    title: 'Avaliação da mensagem',
    short: 'Avaliação',
    running: 'Decidindo se a mensagem é aprovada ou reprovada…',
    tech: 'interceptor · Bloqueio se ameaça ou aprovação imediata',
  },
];

export const STAGE_INDEX = Object.fromEntries(SYNC_STAGES.map((s, i) => [s.id, i]));

// Estações que rodam em segundo plano após a triagem síncrona.
export const ASYNC_STAGES = [
  {
    id: 'armor',
    n: 5,
    title: 'Model Armor',
    short: 'Armor',
    sub: 'Filtro Anti-Prompt Injection & Jailbreak (Google Cloud)',
    tech: 'google-cloud-modelarmor · sanitize_user_prompt (southamerica-east1)',
  },
  {
    id: 'dlp',
    n: 6,
    title: 'Cloud DLP',
    short: 'DLP',
    sub: 'Sensitive Data Protection & Mascaramento PII (LGPD)',
    tech: 'google-cloud-dlp · deidentify_content (southamerica-east1)',
  },
  {
    id: 'laudo',
    n: 7,
    title: 'Laudo Forense',
    short: 'Gemini',
    sub: 'Perícia em Série Temporal & Governança (Google ADK + Gemini)',
    tech: 'gemini-investigation-agent · Workflow ADK + Google Gen AI SDK',
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
  delivery: { pass: 'Aprovada', detect: 'Reprovada' },
};

export function verdictLabel(stageId, status) {
  return VERDICT_LABEL[stageId]?.[status] || STATUS_LABEL[status] || '';
}

export const DECIDED_BY_LABEL = {
  none: 'Nenhuma estação identificou ameaça na mensagem.',
  skipped: 'A regra de valor dispensou a análise desta mensagem.',
  ollaya: 'O Decision Model identificou a ameaça e reprovou a mensagem (estação 3).',
  ollaya_fallback: 'O Decision Model estava fora do ar; a mensagem ficou sem análise.',
};
