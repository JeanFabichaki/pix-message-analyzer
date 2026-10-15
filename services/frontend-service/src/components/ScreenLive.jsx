import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Pause, Play, RotateCcw } from 'lucide-react';
import CountUp from './ui/CountUp';
import { generateSyntheticPix } from '../utils/dataGenerator';
import { getSyncLatencyTelemetry, resetSyncLatencyTelemetry, sendPixSafe } from '../services/api';
import { buildStations, totalMsOf } from '../journey/buildTrace';
import { MASK_FALLBACK } from '../journey/buildTrace';
import { SYNC_STAGES, STATUS_LABEL } from '../journey/stages';
import { formatBRL } from '../journey/scenarios';
import { fmtMs } from '../journey/format';
import { useMotionPrefs } from '../motion/MotionProvider';
import { dur, ease, spring } from '../motion/tokens';

const RATES = [1, 5, 10, 20];
const MAX_ROWS = 12;
const MAX_INFLIGHT = 12;
const FLUSH_MS = 250;
const SERIES_LEN = 48;

const OUTCOME = {
  clean: { label: 'Aprovado', cls: 'chip--safe' },
  skipped: { label: 'Não analisado', cls: 'chip--skip' },
  blocked: { label: 'Pix bloqueado', cls: 'chip--detect' },
  fallback: { label: 'Aprovado (IA fora)', cls: 'chip--error' },
};

function outcomeOf(ev) {
  if (ev.blocked || ev.masked) return 'blocked';
  if (ev.decidedBy === 'skipped') return 'skipped';
  if (ev.decidedBy === 'ollaya_fallback') return 'fallback';
  return 'clean';
}

function MiniTrail({ stations, animate }) {
  return (
    <span className="mini-trail" aria-label="Resultado em cada estação">
      {stations.map((s, i) => (
        <motion.span
          key={s.id}
          className={`mini-dot mini-dot--${s.status}`}
          title={`${SYNC_STAGES[i].title}: ${STATUS_LABEL[s.status] || s.status}`}
          initial={animate ? { scale: 0 } : false}
          animate={{ scale: 1 }}
          transition={{ ...spring.pop, delay: animate ? i * 0.04 : 0 }}
        />
      ))}
    </span>
  );
}

function Sparkline({ values, limit }) {
  const w = 240;
  const h = 56;
  if (values.length < 2) {
    return <div className="spark spark--empty">Aguardando amostras…</div>;
  }
  const max = Math.max(limit * 1.2, ...values);
  const pts = values.map((v, i) => {
    const x = (i / (SERIES_LEN - 1)) * w;
    const y = h - (Math.min(v, max) / max) * (h - 6) - 3;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const limitY = h - (limit / max) * (h - 6) - 3;
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Tempo real de cada Pix recente em milissegundos">
      <line x1="0" x2={w} y1={limitY} y2={limitY} className="spark__limit" />
      <polyline points={pts.join(' ')} className="spark__line" fill="none" />
    </svg>
  );
}

export default function ScreenLive({ active, onInspect }) {
  const { reduced } = useMotionPrefs();
  const [running, setRunning] = useState(false);
  const [rate, setRate] = useState(5);
  const [counters, setCounters] = useState({ processed: 0, retained: 0 });
  const [events, setEvents] = useState([]);
  const [series, setSeries] = useState([]);
  const [telemetry, setTelemetry] = useState(null);

  const countersRef = useRef({ processed: 0, retained: 0 });
  const bufferRef = useRef([]);
  const seriesRef = useRef([]);
  const inflightRef = useRef(0);
  const dirtyRef = useRef(false);

  // A tela escondida não gera tráfego.
  useEffect(() => {
    if (!active) setRunning(false);
  }, [active]);

  const sendOne = useCallback(async () => {
    if (inflightRef.current >= MAX_INFLIGHT) return;
    inflightRef.current += 1;
    const synthetic = generateSyntheticPix();
    const payload = {
      transaction_id: synthetic.transaction_id,
      sender_id: synthetic.sender_id,
      sender_cpf: synthetic.sender_cpf,
      receiver_id: synthetic.receiver_id,
      receiver_cpf: synthetic.receiver_cpf,
      direction: synthetic.direction,
      amount: synthetic.amount,
      description: synthetic.description,
    };
    try {
      const result = await sendPixSafe(payload);
      if (result.network) return;
      const source = result.source;
      const stations = buildStations(source);
      const blocked = result.ok && (Boolean(source.blocked) || source.status === 'BLOCKED');
      const masked = result.ok && Boolean(source.original_masked ?? source.was_masked);
      const isThreat = blocked || masked;
      const ms = totalMsOf(source);
      const ev = {
        id: payload.transaction_id,
        time: new Date().toLocaleTimeString('pt-BR'),
        sender: synthetic.sender_name || synthetic.sender_id,
        amount: payload.amount,
        message: payload.description,
        ok: result.ok,
        blocked,
        masked: isThreat,
        decidedBy: source.decided_by,
        stations,
        realMs: ms,
        finalMessage: result.ok ? source.description : null,
        senderId: payload.sender_id,
      };
      const c = countersRef.current;
      c.processed += 1;
      if (isThreat) c.retained += 1;
      if (typeof ms === 'number') {
        seriesRef.current = [...seriesRef.current, ms].slice(-SERIES_LEN);
      }
      bufferRef.current.push(ev);
      dirtyRef.current = true;
    } finally {
      inflightRef.current -= 1;
    }
  }, []);

  useEffect(() => {
    if (!running) return undefined;
    const id = setInterval(sendOne, Math.max(40, Math.floor(1000 / rate)));
    return () => clearInterval(id);
  }, [running, rate, sendOne]);

  // Agrupa as atualizações para manter a tela fluida em taxas altas.
  useEffect(() => {
    const id = setInterval(() => {
      if (!dirtyRef.current) return;
      dirtyRef.current = false;
      const incoming = bufferRef.current.splice(0).reverse();
      setEvents((prev) => [...incoming, ...prev].slice(0, MAX_ROWS));
      setCounters({ ...countersRef.current });
      setSeries([...seriesRef.current]);
    }, FLUSH_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!active) return undefined;
    let cancelled = false;
    const load = async () => {
      const t = await getSyncLatencyTelemetry();
      if (!cancelled) setTelemetry(t);
    };
    load();
    const id = setInterval(load, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [active]);

  const handleReset = async () => {
    setRunning(false);
    countersRef.current = { processed: 0, retained: 0 };
    bufferRef.current = [];
    seriesRef.current = [];
    setCounters({ processed: 0, retained: 0 });
    setEvents([]);
    setSeries([]);
    await resetSyncLatencyTelemetry();
    setTelemetry(await getSyncLatencyTelemetry());
  };

  const slaMs = telemetry?.sla_target_ms ?? 15;
  const animateTrail = rate <= 5 && !reduced;

  return (
    <div className="page live">
      <div className="page__head">
        <div>
          <h2 className="page__title">Pix chegando ao vivo</h2>
          <p className="page__lead">
            Cada linha é um Pix real passando pelo gateway com mensagem e valor dentro do limite (≤ R$ 10,00), garantindo 100% de passagem pelo Laya para aferição precisa de latência e vazão.
          </p>
        </div>
        <div className="live__controls">
          <div className="segmented" role="radiogroup" aria-label="Pix por segundo">
            {RATES.map((r) => (
              <button
                key={r}
                type="button"
                role="radio"
                aria-checked={rate === r}
                className={rate === r ? 'is-active' : ''}
                onClick={() => setRate(r)}
              >
                {r}/s
              </button>
            ))}
          </div>
          <motion.button
            type="button"
            className={`btn ${running ? 'btn--secondary' : 'btn--primary'}`}
            onClick={() => setRunning((v) => !v)}
            whileTap={{ scale: 0.97 }}
          >
            {running ? <Pause size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
            {running ? 'Pausar' : 'Iniciar'}
          </motion.button>
          <button type="button" className="btn btn--ghost" onClick={handleReset}>
            <RotateCcw size={16} aria-hidden="true" /> Zerar
          </button>
        </div>
      </div>

      <div className="kpis kpis--3">
        <div className="kpi kpi--lavender">
          <span className="kpi__label">Pix analisados</span>
          <CountUp value={counters.processed} className="kpi__value" />
          <span className="kpi__sub">100% com mensagem e triagem na IA</span>
        </div>
        <div className="kpi kpi--lime">
          <span className="kpi__label">Pix bloqueados</span>
          <motion.span
            key={counters.retained}
            initial={reduced ? false : { scale: 1.12 }}
            animate={{ scale: 1 }}
            transition={spring.pop}
            style={{ display: 'inline-block', transformOrigin: 'left center' }}
          >
            <CountUp value={counters.retained} className="kpi__value" duration={0.3} />
          </motion.span>
          <span className="kpi__sub">envio bloqueado por conter ameaça</span>
        </div>
        <div className="kpi kpi--mint">
          <span className="kpi__label">Tempo da análise (p50 / p95)</span>
          <span className="kpi__value num">
            {telemetry?.p50_ms != null ? fmtMs(telemetry.p50_ms) : '—'}
            <small> / {telemetry?.p95_ms != null ? fmtMs(telemetry.p95_ms) : '—'}</small>
          </span>
          <span className="kpi__sub">
            {telemetry?.total_samples
              ? `${telemetry.within_sla_pct}% dentro da meta de ${slaMs} ms (${telemetry.total_samples} amostras)`
              : `Meta de ${slaMs} ms por Pix`}
          </span>
        </div>
      </div>

      <div className="card live__panel">
        <div className="live__panel-head">
          <h3>Últimos Pix</h3>
          <div className="live__spark">
            <span className="live__spark-label">Tempo real de cada Pix (linha tracejada = meta {slaMs} ms)</span>
            <Sparkline values={series} limit={slaMs} />
          </div>
        </div>

        {events.length === 0 ? (
          <div className="empty">
            <p>
              <strong>{running ? 'Aguardando os primeiros Pix…' : 'Nenhum Pix ainda.'}</strong>
            </p>
            <p>Clique em Iniciar para gerar Pix sintéticos contra o gateway real.</p>
          </div>
        ) : (
          <ul className="feed">
            <AnimatePresence initial={false} mode="popLayout">
              {events.map((ev) => {
                const kind = outcomeOf(ev);
                const o = OUTCOME[kind];
                return (
                  <motion.li
                    key={ev.id}
                    layout={!reduced}
                    className={`feed__row feed__row--${kind}`}
                    initial={{ opacity: 0, y: -14 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    transition={{ duration: dur.base, ease }}
                  >
                    <button
                      type="button"
                      className="feed__btn"
                      onClick={() =>
                        onInspect({
                          token: `${ev.id}-${Date.now()}`,
                          txId: ev.id,
                          senderId: ev.senderId,
                          senderName: ev.sender,
                          amount: ev.amount,
                          message: ev.message,
                          stations: ev.stations,
                          masked: ev.masked,
                          finalMessage: ev.finalMessage ?? (ev.masked ? MASK_FALLBACK : ev.message),
                          decidedBy: ev.decidedBy,
                          realMs: ev.realMs,
                        })
                      }
                      aria-label={`Ver a jornada do Pix de ${ev.sender}, ${formatBRL(ev.amount)}`}
                    >
                      <span className="feed__time num">{ev.time}</span>
                      <span className="feed__who">{ev.sender}</span>
                      <span className="feed__amount num">{formatBRL(ev.amount)}</span>
                      <span className="feed__msg">{ev.message ? `“${ev.message}”` : <em>sem mensagem</em>}</span>
                      <MiniTrail stations={ev.stations} animate={animateTrail} />
                      <span className={`chip ${o.cls}`}>{o.label}</span>
                      <span className="feed__ms num">{ev.realMs != null ? fmtMs(ev.realMs) : ''}</span>
                    </button>
                  </motion.li>
                );
              })}
            </AnimatePresence>
          </ul>
        )}

        <div className="legend" aria-label="Legenda dos pontos">
          {['pass', 'skip', 'detect', 'error'].map((s) => (
            <span key={s} className="legend__item">
              <span className={`mini-dot mini-dot--${s}`} /> {STATUS_LABEL[s]}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
