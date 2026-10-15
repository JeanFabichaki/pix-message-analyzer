import { useEffect, useState } from 'react';
import { getTransactionInvestigation } from '../services/api';

const INTERVAL_MS = 700;
const MAX_TRIES = 22; // ~15s

/** Consulta o laudo do Gemini até ele existir (a investigação roda em segundo plano). */
export function useInvestigation(transactionId, enabled) {
  const [state, setState] = useState({ status: 'idle', data: null });

  useEffect(() => {
    if (!transactionId || !enabled) {
      setState({ status: 'idle', data: null });
      return undefined;
    }
    let cancelled = false;
    let tries = 0;
    let timer;
    setState({ status: 'pending', data: null });

    const tick = async () => {
      tries += 1;
      const data = await getTransactionInvestigation(transactionId);
      if (cancelled) return;
      if (data) {
        setState({ status: 'ready', data });
        return;
      }
      if (tries >= MAX_TRIES) {
        setState({ status: 'timeout', data: null });
        return;
      }
      timer = setTimeout(tick, INTERVAL_MS);
    };
    timer = setTimeout(tick, 400);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [transactionId, enabled]);

  return state;
}

/** Versão promessa, usada pelo envio em sequência (reincidente). */
export async function waitForInvestigation(transactionId, { tries = 14, intervalMs = 600 } = {}) {
  for (let i = 0; i < tries; i++) {
    const data = await getTransactionInvestigation(transactionId);
    if (data) return data;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  return null;
}
