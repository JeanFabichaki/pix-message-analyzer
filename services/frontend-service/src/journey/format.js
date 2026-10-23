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

export function formatCostUSD(val) {
  if (val === null || val === undefined) return '$0.00';
  const n = Number(val);
  if (n === 0) return '$0.00';
  if (n < 0.0001) return `$${n.toFixed(6)}`;
  return `$${n.toFixed(4)}`;
}

export function formatCostBRL(val) {
  if (val === null || val === undefined) return 'R$ 0,00';
  const n = Number(val);
  if (n === 0) return 'R$ 0,00';
  if (n < 0.01) return `R$ ${n.toFixed(5).replace('.', ',')}`;
  return `R$ ${n.toFixed(2).replace('.', ',')}`;
}

export function formatTokens(count) {
  if (count === null || count === undefined) return '0 tokens';
  const n = Number(count);
  return `${n.toLocaleString('pt-BR')} tokens`;
}

export function formatCostSummary(cost) {
  if (!cost) return null;
  const usd = formatCostUSD(cost.cost_usd);
  const brl = formatCostBRL(cost.cost_brl);
  return `${usd} (~${brl})`;
}

