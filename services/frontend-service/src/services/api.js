// Cliente HTTP para os serviços de backend com fallback inteligente
const GATEWAY_BASE = '/pix-api';
const USER_BASE = '/user-api';
const AGENT_BASE = '/gemini-api';

// Fallback direto caso o proxy do Vite não seja usado (ex: testes fora do Vite)
const DIRECT_GATEWAY = 'http://localhost:8001';
const DIRECT_USER = 'http://localhost:8002';
const DIRECT_AGENT = 'http://localhost:8003';

// ---- Modelo de triagem selecionado: 'laya_tuned' (retreinado para Pix) ou 'laya' (original).
const ENGINE_KEY = 'pixguard.engine';
let activeEngine = 'laya_tuned';
try {
  if (typeof localStorage !== 'undefined') {
    const saved = localStorage.getItem(ENGINE_KEY);
    if (saved === 'laya' || saved === 'laya_tuned') activeEngine = saved;
  }
} catch (e) {
  /* localStorage indisponível: segue com o modelo retreinado */
}

export function getActiveEngine() {
  return activeEngine;
}

export function setActiveEngine(id) {
  activeEngine = id === 'laya_tuned' ? 'laya_tuned' : 'laya';
  try {
    localStorage.setItem(ENGINE_KEY, activeEngine);
  } catch (e) {
    /* ignora */
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('pix-engine-changed', { detail: activeEngine }));
  }
}

export async function getEngines() {
  try {
    const res = await safeFetch(`${GATEWAY_BASE}/pix/engines`, `${DIRECT_GATEWAY}/pix/engines`);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    return null;
  }
}

async function safeFetch(primaryUrl, fallbackUrl, options = {}) {
  try {
    const res = await fetch(primaryUrl, options);
    return res;
  } catch (err) {
    if (fallbackUrl) {
      try {
        return await fetch(fallbackUrl, options);
      } catch (e) {
        throw e;
      }
    }
    throw err;
  }
}

export async function sendPixTransaction(txData) {
  const primary = `${GATEWAY_BASE}/pix/transactions`;
  const fallback = `${DIRECT_GATEWAY}/pix/transactions`;

  const res = await safeFetch(primary, fallback, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ engine: activeEngine, ...txData }),
  });

  const data = await res.json();
  if (!res.ok) {
    const errorMsg = data?.detail?.message || data?.detail || 'Erro ao processar transação Pix';
    const err = new Error(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
    err.status = res.status;
    err.payload = data;
    throw err;
  }

  // Normalização de compatibilidade de campos
  data.was_masked = data.original_masked ?? data.was_masked ?? false;
  data.final_message = data.description ?? data.final_message ?? '';
  return data;
}

/**
 * Envia o Pix sem lançar exceção: devolve { ok, source } com a resposta (200) ou o `detail` de uma resposta de erro,
 * ou { ok: false, network: true } quando o gateway não responde.
 */
export async function sendPixSafe(payload) {
  try {
    const res = await sendPixTransaction(payload);
    return { ok: true, source: res };
  } catch (err) {
    const detail = err?.payload?.detail;
    if (err?.status && detail && typeof detail === 'object') {
      return { ok: false, source: detail, status: err.status };
    }
    return { ok: false, network: true, message: err?.message };
  }
}

/**
 * Saúde do gateway: { reachable, ollaya: { status: ok|degraded|unknown, last_error } }.
 * `degraded` significa que a IA rápida está falhando e os Pix estão sendo aprovados sem análise.
 */
export async function getGatewayHealth() {
  const primary = `${GATEWAY_BASE}/health`;
  const fallback = `${DIRECT_GATEWAY}/health`;
  try {
    const res = await safeFetch(primary, fallback);
    if (!res.ok) return { reachable: false, ollaya: null };
    const data = await res.json();
    return { reachable: true, ollaya: data.ollaya || null };
  } catch (e) {
    return { reachable: false, ollaya: null };
  }
}

export async function getUser(userId) {
  const primary = `${USER_BASE}/users/${userId}`;
  const fallback = `${DIRECT_USER}/users/${userId}`;
  const res = await safeFetch(primary, fallback);
  if (!res.ok) return null;
  return await res.json();
}

export async function listUsers() {
  const primary = `${USER_BASE}/users`;
  const fallback = `${DIRECT_USER}/users`;
  try {
    const res = await safeFetch(primary, fallback);
    if (!res.ok) return [];
    return await res.json();
  } catch (e) {
    return [];
  }
}

export async function unblockUser(userId) {
  const primary = `${USER_BASE}/users/${userId}/unblock`;
  const fallback = `${DIRECT_USER}/users/${userId}/unblock`;
  const res = await safeFetch(primary, fallback, { method: 'POST' });
  if (!res.ok) throw new Error('Falha ao desbloquear usuário');
  return await res.json();
}

export async function resetUserThreats(userId) {
  const primary = `${USER_BASE}/users/${userId}/reset-threats`;
  const fallback = `${DIRECT_USER}/users/${userId}/reset-threats`;
  const res = await safeFetch(primary, fallback, { method: 'POST' });
  if (!res.ok) throw new Error('Falha ao resetar ocorrências');
  return await res.json();
}

export async function getAuditThreats() {
  const primary = `${USER_BASE}/audit/threats`;
  const fallback = `${DIRECT_USER}/audit/threats`;
  try {
    const res = await safeFetch(primary, fallback);
    if (!res.ok) return [];
    return await res.json();
  } catch (e) {
    return [];
  }
}

export async function getAuditMetrics() {
  const primary = `${USER_BASE}/audit/metrics`;
  const fallback = `${DIRECT_USER}/audit/metrics`;
  try {
    const res = await safeFetch(primary, fallback);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    return null;
  }
}

export async function clearAllAuditHistory() {
  const primary = `${USER_BASE}/audit/clear-history`;
  const fallback = `${DIRECT_USER}/audit/clear-history`;
  const res = await safeFetch(primary, fallback, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Falha ao limpar histórico de auditoria');
  const data = await res.json();
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('pix-history-cleared', { detail: data }));
  }
  return data;
}

export async function getUserThreatLogs(userId) {
  const primary = `${AGENT_BASE}/threats/user/${userId}`;
  const fallback = `${DIRECT_AGENT}/threats/user/${userId}`;
  try {
    const res = await safeFetch(primary, fallback);
    if (!res.ok) return [];
    return await res.json();
  } catch (e) {
    return [];
  }
}

export async function getTransactionInvestigation(transactionId) {
  const primary = `${AGENT_BASE}/threats/tx/${transactionId}`;
  const fallback = `${DIRECT_AGENT}/threats/tx/${transactionId}`;
  try {
    const res = await safeFetch(primary, fallback);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    return null;
  }
}

export async function getSyncLatencyTelemetry() {
  const primary = `${GATEWAY_BASE}/pix/telemetry/latency`;
  const fallback = `${DIRECT_GATEWAY}/pix/telemetry/latency`;
  try {
    const res = await safeFetch(primary, fallback);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    return null;
  }
}

export async function resetSyncLatencyTelemetry() {
  const primary = `${GATEWAY_BASE}/pix/telemetry/reset`;
  const fallback = `${DIRECT_GATEWAY}/pix/telemetry/reset`;
  try {
    const res = await safeFetch(primary, fallback, { method: 'POST' });
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    return null;
  }
}


// ---- Comparação Laya original x retreinado (benchmark com os dados de teste do fine-tuning)
export async function getBenchmarkDatasets() {
  try {
    const res = await safeFetch(`${GATEWAY_BASE}/pix/benchmark/datasets`, `${DIRECT_GATEWAY}/pix/benchmark/datasets`);
    if (!res.ok) return [];
    return (await res.json()).datasets || [];
  } catch (e) {
    return [];
  }
}

export async function startBenchmark(dataset, size) {
  const res = await safeFetch(`${GATEWAY_BASE}/pix/benchmark`, `${DIRECT_GATEWAY}/pix/benchmark`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset, size: size || null }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data?.detail?.message || data?.detail || 'Não foi possível iniciar a comparação';
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data.job_id;
}

export async function getBenchmark(jobId) {
  const res = await safeFetch(`${GATEWAY_BASE}/pix/benchmark/${jobId}`, `${DIRECT_GATEWAY}/pix/benchmark/${jobId}`);
  if (!res.ok) throw new Error('Comparação não encontrada');
  return res.json();
}

export async function generateGeminiBenchmarkMessages(count = 50) {
  const primary = `${GATEWAY_BASE}/pix/benchmark/generate-gemini`;
  const fallback = `${DIRECT_GATEWAY}/pix/benchmark/generate-gemini`;
  const res = await safeFetch(primary, fallback, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ count }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data?.detail?.message || data?.detail || 'Erro ao gerar mensagens com Gemini';
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data;
}

