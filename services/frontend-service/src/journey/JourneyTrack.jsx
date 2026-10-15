import React, { useLayoutEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { MessageCircle, ShieldCheck } from 'lucide-react';
import { SYNC_STAGES, verdictLabel, STATUS_LABEL } from './stages';
import StageIcon from './StageIcon';
import StatusIcon from '../components/ui/StatusIcon';
import { fmtMs } from './format';
import { ease, spring } from '../motion/tokens';

const NODE = 56;
const ARC_SPACE = 44; // altura reservada acima dos nós para os arcos
const CY = ARC_SPACE + NODE / 2;
const FINAL = new Set(['pass', 'skip', 'detect', 'error']);

function arcsOf(states) {
  const arcs = [];
  let i = 0;
  while (i < states.length) {
    const isHopped = states[i] === 'skip' && SYNC_STAGES[i].id !== 'amount_rule';
    if (!isHopped) {
      i += 1;
      continue;
    }
    const start = i;
    while (i < states.length && states[i] === 'skip' && SYNC_STAGES[i].id !== 'amount_rule') i += 1;
    const from = start - 1;
    const to = i;
    if (from >= 0 && to < states.length) arcs.push({ from, to, key: `${from}-${to}` });
  }
  return arcs;
}

export default function JourneyTrack({ stations, timeline, selectedIndex, onSelect, amountLabel, reduced }) {
  const { states, cursor, jumpFrom, phase, delivered } = timeline;
  const ref = useRef(null);
  const [width, setWidth] = useState(0);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return undefined;
    const measure = () => setWidth(el.getBoundingClientRect().width);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const compact = width > 0 && width < 560;
  const col = width / SYNC_STAGES.length;
  const cx = (i) => (i + 0.5) * col;
  const arcs = compact ? [] : arcsOf(states);
  const showBubble = !compact && !reduced && width > 0;

  // Posição da bolha: no celular de quem envia, em uma estação, ou saindo para quem recebe.
  const leaving = phase === 'done' && delivered;
  const bx = leaving ? width + 28 : cursor < 0 ? -6 : cx(cursor);
  const isJump = cursor >= 0 && jumpFrom >= 0 && cursor - jumpFrom > 1 && phase === 'running';
  const bubbleTone = cursor >= 0 && FINAL.has(states[cursor]) ? states[cursor] : 'neutral';

  const progressRatio = cursor < 0 ? 0 : cursor / (SYNC_STAGES.length - 1);
  const railSpan = Math.max(cx(SYNC_STAGES.length - 1) - cx(0), 1);

  return (
    <div className={`track ${compact ? 'track--compact' : ''}`} ref={ref}>
      {!compact && width > 0 && (
        <>
          <div className="track__rail" style={{ left: cx(0), width: railSpan, top: CY - 2 }} aria-hidden="true">
            <motion.div
              className="track__rail-fill"
              initial={false}
              animate={{ scaleX: progressRatio }}
              transition={{ duration: reduced ? 0 : 0.32, ease }}
            />
          </div>

          <svg className="track__arcs" width={width} height={CY + 8} aria-hidden="true">
            <AnimatePresence>
              {arcs.map((a) => {
                const x1 = cx(a.from);
                const x2 = cx(a.to);
                return (
                  <motion.path
                    key={a.key}
                    d={`M ${x1} ${CY - NODE / 2 + 2} C ${x1} 2, ${x2} 2, ${x2} ${CY - NODE / 2 + 2}`}
                    className="track__arc"
                    fill="none"
                    initial={{ pathLength: 0, opacity: 0 }}
                    animate={{ pathLength: 1, opacity: 1 }}
                    transition={{ duration: reduced ? 0 : 0.5, ease }}
                  />
                );
              })}
            </AnimatePresence>
            {arcs.map((a) => {
              const mid = (cx(a.from) + cx(a.to)) / 2;
              return (
                <text key={`t-${a.key}`} x={mid} y={14} textAnchor="middle" className="track__arc-label">
                  atalho: não precisou
                </text>
              );
            })}
          </svg>
        </>
      )}

      {showBubble && (
        <motion.div
          className={`bubble bubble--${bubbleTone}`}
          initial={false}
          animate={{
            x: bx - 20,
            y: isJump ? [0, -40, 0] : 0,
            opacity: leaving ? 0 : phase === 'idle' ? 0.0 : 1,
            scale: leaving ? 0.7 : 1,
          }}
          transition={{
            x: { duration: 0.32, ease },
            y: { duration: 0.32, ease },
            opacity: { duration: 0.25, delay: leaving ? 0.15 : 0 },
            scale: { duration: 0.25 },
          }}
          style={{ top: CY - 20 }}
          aria-hidden="true"
        >
          {bubbleTone === 'detect' ? (
            <ShieldCheck size={18} strokeWidth={2.4} />
          ) : (
            <MessageCircle size={18} strokeWidth={2.4} />
          )}
          {amountLabel && <span className="bubble__tag num">{amountLabel}</span>}
        </motion.div>
      )}

      <ol className="stations" style={!compact ? { paddingTop: ARC_SPACE } : undefined}>
        {SYNC_STAGES.map((stage, i) => {
          const state = states[i];
          const station = stations[i];
          const isFinal = FINAL.has(state);
          const isSelected = selectedIndex === i;
          const label = isFinal ? verdictLabel(stage.id, state) : STATUS_LABEL[state] || '';
          return (
            <li key={stage.id} className="station-cell">
              <button
                type="button"
                className={`station station--${state} ${isSelected ? 'is-selected' : ''}`}
                onClick={() => onSelect(i)}
                aria-current={isSelected ? 'step' : undefined}
                aria-label={`Etapa ${stage.n}: ${stage.title}. ${label}`}
              >
                <span className="station__node">
                  <AnimatePresence mode="popLayout" initial={false}>
                    <motion.span
                      key={`${state}`}
                      className="station__icon"
                      initial={{ scale: 0.4, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 0.6, opacity: 0 }}
                      transition={spring.pop}
                    >
                      {state === 'running' ? (
                        <span className="spinner" />
                      ) : isFinal ? (
                        <StatusIcon status={state} size={24} />
                      ) : (
                        <StageIcon id={stage.id} />
                      )}
                    </motion.span>
                  </AnimatePresence>
                  {state === 'running' && !reduced && <span className="station__pulse" aria-hidden="true" />}
                  <span className="station__num" aria-hidden="true">
                    {stage.n}
                  </span>
                </span>
                <span className="station__title">{stage.title}</span>
                <span className="station__verdict">{label}</span>
                <span className="station__ms num">{isFinal && station?.ms != null ? fmtMs(station.ms) : ' '}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
