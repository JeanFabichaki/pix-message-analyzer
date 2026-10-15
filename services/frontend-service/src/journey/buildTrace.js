import { SYNC_STAGES } from './stages';

const MASK_FALLBACK = 'Mensagem retida por conter conteúdo inadequado sob análise de segurança.';

/**
 * Converte a resposta do gateway em 4 estações na ordem da jornada.
 * Estações que não foram alcançadas (ex.: depois de um bloqueio) ficam com status "void".
 */
export function buildStations(source) {
  const trace = Array.isArray(source?.trace) && source.trace.length ? source.trace : deduceTrace(source);
  const byId = Object.fromEntries(trace.map((t) => [t.step, t]));
  return SYNC_STAGES.map((stage) => {
    const t = byId[stage.id];
    if (!t) return { id: stage.id, status: 'void', ms: null, detail: null, data: null };
    return {
      id: stage.id,
      status: t.status,
      ms: typeof t.ms === 'number' ? t.ms : null,
      detail: t.detail || null,
      data: t.data || null,
    };
  });
}

// Compatibilidade com respostas antigas, sem `trace`. Deduz o caminho pelo que o gateway devolveu.
function deduceTrace(res) {
  if (!res) return [];
  const t = res.timing || {};
  const masked = Boolean(res.original_masked ?? res.was_masked);
  const evaded = Boolean(res.evasion_detected);
  const out = [];
  out.push({ step: 'amount_rule', status: 'pass', ms: 0.01 });
  out.push({ step: 'anti_evasion', status: evaded ? 'detect' : 'pass', ms: t.step2_anti_evasion_ms });
  out.push({
    step: 'ollaya',
    status: masked ? 'detect' : 'pass',
    ms: t.step2_ollaya_ms,
  });
  out.push({ step: 'delivery', status: masked ? 'detect' : 'pass', ms: t.step3_masking_ms });
  return out;
}

export function totalMsOf(source) {
  const t = source?.timing;
  if (!t) return null;
  return typeof t.total_gateway_ms === 'number' ? t.total_gateway_ms : null;
}

/** Reconstrói uma jornada aproximada a partir de um registro da auditoria (que não guarda o trace). */
export function stationsFromAuditLog(log) {
  const rationale = log?.gemini_rationale || '';
  const evaded = rationale.startsWith('[Anti-Bypass');
  const score = typeof log?.ollaya_score === 'number' ? log.ollaya_score : null;
  const trace = [
    { step: 'amount_rule', status: 'pass', detail: 'Valor dentro do limite e com mensagem.' },
    {
      step: 'anti_evasion',
      status: evaded ? 'detect' : 'pass',
      detail: evaded ? 'Disfarce detectado e desfeito.' : 'Nenhum disfarce encontrado.',
    },
    {
      step: 'ollaya',
      status: 'detect',
      detail: 'A IA rápida identificou a ameaça.',
      data: { score, category: log?.ollaya_category },
    },
    { step: 'delivery', status: 'detect', detail: 'Mensagem substituída pelo aviso padrão.' },
  ];
  return buildStations({ trace });
}

export { MASK_FALLBACK };
