export function fmtMs(ms) {
  if (ms === null || ms === undefined || Number.isNaN(Number(ms))) return '';
  const n = Number(ms);
  const digits = n < 1 ? 2 : n < 100 ? 1 : 0;
  return `${n.toFixed(digits).replace('.', ',')} ms`;
}

export const CATEGORY_LABEL = {
  extorsao: 'Extorsão',
  violencia_fisica: 'Violência física',
  stalking_perseguicao: 'Perseguição',
  injuria_difamacao: 'Injúria ou difamação',
  outros: 'Outros',
  ameaca_explicita_perseguicao: 'Perseguição ou coação',
  ameaca_ou_extorsao: 'Ameaça ou extorsão',
  benigno: 'Sem risco',
  bypass: 'Bypass (Sem análise)',
};

export function categoryLabel(value) {
  if (!value) return '—';
  return CATEGORY_LABEL[value] || String(value).replace(/_/g, ' ');
}

export const CRITICALITY_LABEL = {
  BAIXA: 'Baixa',
  MEDIA: 'Média',
  ALTA: 'Alta',
  CRITICA: 'Crítica',
  BYPASS: 'Bypass',
};
