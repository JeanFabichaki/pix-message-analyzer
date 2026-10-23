import React, { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Code2 } from 'lucide-react';
import { SYNC_STAGES, STATUS_LABEL, verdictLabel } from './stages';
import StageIcon from './StageIcon';
import StatusIcon from '../components/ui/StatusIcon';
import { AmountRuler, DecodeText, MessageSwap, ScoreGauge } from './effects';
import { fmtMs } from './format';
import { dur, ease } from '../motion/tokens';

const FINAL = new Set(['pass', 'skip', 'detect', 'error']);

function Effect({ stage, station, stations, context, play }) {
  const data = station?.data || {};
  const status = station?.status;

  switch (stage.id) {
    case 'amount_rule':
      return <AmountRuler amount={context.amount} limit={data.limit ?? 10} play={play} />;
    case 'anti_evasion': {
      if (status !== 'detect') return null;
      return <DecodeText from={data.original ?? context.message} to={data.canonical ?? ''} play={play} />;
    }
    case 'ollaya': {
      if (status === 'skip' || status === 'error' || typeof data.score !== 'number') return null;
      return <ScoreGauge score={data.score} play={play} />;
    }
    case 'delivery': {
      if (status !== 'detect') return null;
      return <MessageSwap original={context.message} masked={context.maskedMessage} amount={context.amount} play={play} />;
    }
    default:
      return null;
  }
}

export default function StageDetail({ index, stations, states, context, reduced, idleText, arriving }) {
  const [showTech, setShowTech] = useState(false);
  const stage = SYNC_STAGES[index];

  if (!stage) {
    return (
      <div className="detail detail--empty">
        <p>{idleText || 'Envie o Pix. Cada estação mostra aqui o que foi verificado, com os tempos reais.'}</p>
      </div>
    );
  }

  const station = stations[index];
  const state = states[index];
  const isFinal = FINAL.has(state);
  const text =
    state === 'running'
      ? stage.running
      : state === 'pending'
        ? arriving
          ? 'A mensagem está chegando a esta estação…'
          : 'A mensagem ainda não chegou a esta estação.'
        : state === 'void'
          ? 'A mensagem foi barrada antes de chegar aqui.'
          : station?.detail || '';

  return (
    <div className={`detail detail--${state}`}>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={stage.id}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4, transition: { duration: dur.instant } }}
          transition={{ duration: dur.fast, ease }}
        >
          <div className="detail__head">
            <span className="detail__icon">
              {isFinal ? <StatusIcon status={state} size={20} /> : <StageIcon id={stage.id} size={20} />}
            </span>
            <div className="detail__titles">
              <span className="detail__kicker">Etapa {stage.n} de {SYNC_STAGES.length}</span>
              <h3>{stage.title}</h3>
            </div>
            <span className={`chip chip--${state}`}>
              {isFinal ? verdictLabel(stage.id, state) : STATUS_LABEL[state]}
            </span>
          </div>

          <p className="detail__text">{text}</p>

          {isFinal && (
            <Effect stage={stage} station={station} stations={stations} context={context} play={!reduced} />
          )}

          {stage.id === 'ollaya' && isFinal && (
            <div className="latency-breakdown">
              <div className="latency-item">
                <div className="latency-item__header">
                  <span className="latency-item__title">⚡ inference_ms (CPU)</span>
                  <strong className="latency-item__value">
                    {fmtMs(station?.data?.pure_inference_ms ?? station?.data?.inference_ms ?? Math.round((station?.ms || 200) * 0.9))}
                  </strong>
                </div>
                <p className="latency-item__desc">Tempo em que a CPU processou a rede neural.</p>
              </div>
              <div className="latency-item">
                <div className="latency-item__header">
                  <span className="latency-item__title">🌐 network_ms (Cloud Run)</span>
                  <strong className="latency-item__value">
                    {fmtMs(station?.data?.network_ms ?? Math.max(0, Math.round((station?.ms || 200) * 0.1)))}
                  </strong>
                </div>
                <p className="latency-item__desc">Latência de transporte e proxy Cloud Run.</p>
              </div>
            </div>
          )}

          <div className="detail__foot">
            {isFinal && station?.ms != null && (
              <span className="detail__ms">
                Tempo real nesta etapa: <strong className="num">{fmtMs(station.ms)}</strong>
              </span>
            )}
            <button
              type="button"
              className="btn btn--ghost btn--xs"
              onClick={() => setShowTech((v) => !v)}
              aria-expanded={showTech}
            >
              <Code2 size={14} aria-hidden="true" /> {showTech ? 'Ocultar detalhes técnicos' : 'Detalhes técnicos'}
            </button>
          </div>

          {showTech && (
            <pre className="detail__tech">
              {stage.tech}
              {station?.data ? `\n${JSON.stringify(station.data, null, 2)}` : ''}
            </pre>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
