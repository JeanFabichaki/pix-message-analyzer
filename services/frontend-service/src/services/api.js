// Cliente HTTP para os serviços de backend com fallback inteligente
const GATEWAY_BASE = import.meta.env.VITE_GATEWAY_URL || '/pix-api';
const USER_BASE = import.meta.env.VITE_USER_SERVICE_URL || '/user-api';
const AGENT_BASE = import.meta.env.VITE_GEMINI_AGENT_URL || '/gemini-api';

// Fallback direto caso o proxy do Vite não seja usado
const DIRECT_GATEWAY = 'http://localhost:8001';
const DIRECT_USER = 'http://localhost:8002';
const DIRECT_AGENT = 'http://localhost:8003';

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
    body: JSON.stringify(txData),
  });

  const data = await res.json();
  if (!res.ok) {
    const errorMsg = data?.detail?.message || data?.detail || 'Erro ao processar transação Pix';
    const err = new Error(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
    err.status = res.status;
    err.payload = data;
    throw err;
  }
  return data;
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

const INTEL_BASE = import.meta.env.VITE_THREAT_INTEL_URL || '/threat-intel-api';
const DIRECT_INTEL = 'http://localhost:8004';

export async function getThreatIntelStats() {
  const primary = `${INTEL_BASE}/threats/stats`;
  const fallback = `${DIRECT_INTEL}/threats/stats`;
  try {
    const res = await safeFetch(primary, fallback);
    if (!res.ok) return { total_signatures: 0, total_occurrences: 0 };
    return await res.json();
  } catch (e) {
    return { total_signatures: 0, total_occurrences: 0 };
  }
}

export async function listConfirmedThreats(limit = 20) {
  const primary = `${INTEL_BASE}/threats?limit=${limit}`;
  const fallback = `${DIRECT_INTEL}/threats?limit=${limit}`;
  try {
    const res = await safeFetch(primary, fallback);
    if (!res.ok) return [];
    return await res.json();
  } catch (e) {
    return [];
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

