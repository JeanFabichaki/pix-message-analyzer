import { useCallback, useEffect, useRef, useState } from 'react';
import { TEMPO, TEMPO_REDUCED } from '../motion/tokens';
import { SYNC_STAGES } from './stages';

const LAST = SYNC_STAGES.length - 1;

function initialState() {
  return {
    phase: 'idle', // idle | running | waiting | done
    states: SYNC_STAGES.map(() => 'pending'),
    cursor: -1, // estação onde a bolha está (-1 = ainda no celular de quem envia)
    jumpFrom: -1, // estação de onde a bolha saiu (para desenhar o arco)
    focus: -1, // estação exibida no cartão de detalhe
    delivered: false,
  };
}

// Uma estação "skip" é visitada só quando é a própria regra de valor (a que dispensa a análise).
function isVisited(station) {
  return station.status !== 'skip' || station.id === 'amount_rule';
}

function finalStateOf(stations) {
  let cursor = LAST;
  for (let i = LAST; i >= 0; i--) {
    if (stations[i].status !== 'void' && isVisited(stations[i])) {
      cursor = i;
      break;
    }
  }
  return {
    phase: 'done',
    states: stations.map((s) => s.status),
    cursor,
    jumpFrom: -1,
    focus: LAST,
    delivered: stations[LAST].status !== 'void',
  };
}

/**
 * Sequencia a jornada: a bolha percorre as estações, cada uma "analisa" e revela o veredito real.
 * Aceita cancelamento (reset/trocar de caso), pular e modo passo a passo.
 */
export function useJourneyTimeline({ reduced }) {
  const [state, setState] = useState(initialState);
  const runRef = useRef(0);
  const skipRef = useRef(false);
  const pendingRef = useRef(new Set());
  const nextResolverRef = useRef(null);

  const flush = useCallback(() => {
    pendingRef.current.forEach((p) => {
      clearTimeout(p.timer);
      p.resolve();
    });
    pendingRef.current.clear();
    if (nextResolverRef.current) {
      nextResolverRef.current();
      nextResolverRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    runRef.current += 1;
    skipRef.current = false;
    flush();
    setState(initialState());
  }, [flush]);

  useEffect(
    () => () => {
      runRef.current += 1;
      flush();
    },
    [flush]
  );

  const sleep = useCallback((ms) => {
    return new Promise((resolve) => {
      if (skipRef.current || ms <= 0) {
        resolve();
        return;
      }
      const entry = { resolve };
      entry.timer = setTimeout(() => {
        pendingRef.current.delete(entry);
        resolve();
      }, ms);
      pendingRef.current.add(entry);
    });
  }, []);

  const play = useCallback(
    async (stations, { stepMode = false, speed = 1 } = {}) => {
      runRef.current += 1;
      const runId = runRef.current;
      skipRef.current = false;
      flush();
      const alive = () => runRef.current === runId;
      const tempo = reduced ? TEMPO_REDUCED : TEMPO;
      const d = (ms) => ms / (speed || 1);

      setState({ ...initialState(), phase: 'running' });
      await sleep(d(tempo.send));
      if (!alive()) return;

      let prev = -1;
      for (let i = 0; i <= LAST; i++) {
        const station = stations[i];
        if (station.status === 'void') continue;
        if (!isVisited(station)) continue;

        // Estações dispensadas entre a anterior e esta são reveladas na saída da bolha (arco por cima).
        const skippedBetween = [];
        for (let k = prev + 1; k < i; k++) {
          if (stations[k].status === 'skip') skippedBetween.push(k);
        }
        setState((s) => {
          const states = [...s.states];
          skippedBetween.forEach((k) => {
            states[k] = 'skip';
          });
          return { ...s, states, cursor: i, jumpFrom: prev, focus: i };
        });
        await sleep(d(tempo.travel));
        if (!alive()) return;

        setState((s) => {
          const states = [...s.states];
          states[i] = 'running';
          return { ...s, states, focus: i };
        });

        if (stepMode && !skipRef.current) {
          setState((s) => ({ ...s, phase: 'waiting' }));
          await new Promise((resolve) => {
            nextResolverRef.current = resolve;
          });
          if (!alive()) return;
          setState((s) => ({ ...s, phase: 'running' }));
        }

        const hasEffect = station.status === 'detect' || station.id === 'delivery';
        await sleep(d(tempo.analyze + (hasEffect ? tempo.effect : 0)));
        if (!alive()) return;

        setState((s) => {
          const states = [...s.states];
          states[i] = station.status;
          return { ...s, states };
        });
        await sleep(d(tempo.verdict));
        if (!alive()) return;

        prev = i;
      }

      await sleep(d(tempo.deliver));
      if (!alive()) return;
      setState(finalStateOf(stations));
    },
    [flush, reduced, sleep]
  );

  // Esc / "Pular animação": vai direto ao estado final.
  const skipTo = useCallback(
    (stations) => {
      skipRef.current = true;
      runRef.current += 1;
      flush();
      setState(finalStateOf(stations));
    },
    [flush]
  );

  // → / espaço no modo passo a passo.
  const next = useCallback(() => {
    if (nextResolverRef.current) {
      nextResolverRef.current();
      nextResolverRef.current = null;
    }
  }, []);

  const showFinal = useCallback((stations) => setState(finalStateOf(stations)), []);
  const setFocus = useCallback((focus) => setState((s) => ({ ...s, focus })), []);

  return { state, play, reset, skipTo, next, showFinal, setFocus };
}
