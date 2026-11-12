const VALID = new Set(['not_run', 'checked', 'blocked', 'history_filtered', 'masked', 'error']);
export const PROTECTION_LABELS = {
  not_run: 'Não acionado neste caso', checked: 'Verificação concluída', blocked: 'Conteúdo bloqueado',
  history_filtered: 'Histórico filtrado', masked: 'Dados pessoais mascarados', error: 'Falha na proteção',
};
export const protectionNeedsAttention = (state) => ['blocked', 'history_filtered', 'masked', 'error'].includes(state);

// Relatórios antigos não têm ações explícitas: usa somente os resultados disponíveis.
export function protectionStates(data) {
  const actions = data?.protection_actions || {};
  const reason = String(data?.bypass_reason || data?.analysis?.bypass_reason || '').toLowerCase();
  const armor = VALID.has(actions.model_armor) ? actions.model_armor : reason.includes('armor')
    ? reason.includes('bloqueou') ? 'blocked' : 'error'
    : data?.timing?.model_armor_ms > 0 ? 'checked' : 'not_run';
  let dlp = actions.cloud_dlp;
  const targetInput = data?.armor_message ?? data?.canonical_message ?? data?.target_message;
  const targetComparable = typeof data?.dlp_message === 'string' && typeof targetInput === 'string';
  // Inclusive em relatórios antigos, mascarar só o histórico não deixa o DLP amarelo.
  if (dlp === 'error' || reason.includes('dlp') || reason.includes('mascarar')) dlp = 'error';
  else if (dlp !== 'not_run' && targetComparable && (VALID.has(dlp) || data?.timing?.cloud_dlp_ms > 0 || data.dlp_message !== targetInput)) dlp = data.dlp_message !== targetInput ? 'masked' : 'checked';
  else if (dlp === 'masked') dlp = 'checked';
  else if (!VALID.has(dlp)) dlp = data?.timing?.cloud_dlp_ms > 0 ? 'checked' : 'not_run';
  return {armor, dlp};
}
