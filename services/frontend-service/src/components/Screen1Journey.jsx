import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ChevronRight, FastForward, History, Play, RotateCcw, Send, SkipForward } from 'lucide-react';
import { SCENARIO_ICONS } from '../journey/scenarioIcons';
import { SenderPhone, ReceiverPhone } from '../journey/PhoneMock';
import JourneyTrack from '../journey/JourneyTrack';
import StageDetail from '../journey/StageDetail';
import AfterDelivery from '../journey/AfterDelivery';
import { useJourneyTimeline } from '../journey/useJourneyTimeline';
import { useInvestigation, waitForInvestigation } from '../journey/useInvestigation';
import { buildStations, totalMsOf } from '../journey/buildTrace';
import { DECIDED_BY_LABEL, SYNC_STAGES, verdictLabel } from '../journey/stages';
import { SCENARIOS, buildPayload, formatBRL } from '../journey/scenarios';
import { fmtMs } from '../journey/format';
import { getUser, getUserThreatLogs, resetUserThreats, sendPixSafe } from '../services/api';
import { useMotionPrefs } from '../motion/MotionProvider';
import { useToast } from './ui/Toast';
import { dur, ease, spring } from '../motion/tokens';

const DEFAULT_LIMIT = 5;
const EMPTY_STATIONS = SYNC_STAGES.map((s) => ({ id: s.id, status: 'void', ms: null, detail: null, data: null }));

function isTyping() {
  const tag = document.activeElement?.tagName?.toLowerCase();
  return tag === 'input' || tag === 'textarea' || tag === 'select';
}

function ScenarioPicker({ activeId, onPick, disabled, replayActive }) {
  return (
    <div className="scenarios" role="radiogroup" aria-label="Casos prontos">
      {SCENARIOS.map((sc) => {
        const Icon = SCENARIO_ICONS[sc.icon];
        const active = activeId === sc.id;
        return (
          <button
            key={sc.id}
            type="button"
            role="radio"
            aria-checked={active}
            className={`scenario ${active ? 'is-active' : ''}`}
            onClick={() => onPick(sc)}
            disabled={disabled && !active}
          >
            {active && <motion.span layoutId="scenario-pill" className="scenario__pill" transition={spring.soft} />}
            <span className="scenario__content">
              <Icon size={16} aria-hidden="true" />
              <span>{sc.title}</span>
            </span>
          </button>
        );
      })}
      {replayActive && (
        <span className="scenario is-active scenario--replay">
          <span className="scenario__content">
            <History size={16} aria-hidden="true" />
            <span>Reprodução</span>
          </span>
        </span>
      )}
    </div>
  );
}

export default function Screen1Journey({ replay, onReplayConsumed, active = true }) {
  const { reduced } = useMotionPrefs();
  const { toast } = useToast();
  const timeline = useJourneyTimeline({ reduced });
  const { state: tl } = timeline;

  const [scenario, setScenario] = useState(SCENARIOS[2]);
  const [amount, setAmount] = useState(SCENARIOS[2].amount);
  const [message, setMessage] = useState(SCENARIOS[2].message);
  const [run, setRun] = useState(null);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [burstProgress, setBurstProgress] = useState(null);
  const [stepMode, setStepMode] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [gov, setGov] = useState({ count: 0, blocked: false });
  const [replayActive, setReplayActive] = useState(false);
  const sendIdRef = useRef(0);

  const investigation = useInvestigation(run?.txId, Boolean(run?.masked));
  const inv = investigation.data;

  const refreshGovernance = useCallback(async (senderId) => {
    try {
      const [user, logs] = await Promise.all([getUser(senderId), getUserThreatLogs(senderId)]);
      setGov({
        count: Array.isArray(logs) ? logs.length : 0,
        blocked: user?.status === 'BLOCKED_SUSPICIOUS',
      });
    } catch (e) {
      /* ficha indisponível: mantém o último valor */
    }
  }, []);

  useEffect(() => {
    refreshGovernance(scenario.sender.id);
  }, [scenario, refreshGovernance]);

  useEffect(() => {
    if (investigation.status === 'ready') refreshGovernance(scenario.sender.id);
  }, [investigation.status, scenario, refreshGovernance]);

  const ficha = {
    count: inv?.total_threats ?? gov.count,
    limit: inv?.block_limit ?? DEFAULT_LIMIT,
    blocked: Boolean(inv?.account_blocked) || gov.blocked,
  };

  // ----- Envio -----
  const finishWith = useCallback(
    async (payload, result, { playSpeed = speed } = {}) => {
      const source = result.source;
      const masked = result.ok && Boolean(source.original_masked ?? source.was_masked);
      const stations = buildStations(source);
      setRun({
        payload,
        txId: payload.transaction_id,
        stations,
        ok: result.ok,
        masked,
        decidedBy: source.decided_by,
        realMs: totalMsOf(source),
        finalMessage: result.ok ? source.description : null,
      });
      await timeline.play(stations, { stepMode, speed: playSpeed });
    },
    [speed, stepMode, timeline]
  );

  const handleSend = useCallback(async () => {
    if (busy) return;
    const token = ++sendIdRef.current;
    setBusy(true);
    setSelected(null);
    setRun(null);
    timeline.reset();
    const payload = buildPayload({ scenario, amount, message });
    const result = await sendPixSafe(payload);
    if (token !== sendIdRef.current) return;
    if (result.network) {
      toast('Não consegui falar com o gateway. Confira se os serviços estão no ar.', 'danger');
      setBusy(false);
      return;
    }
    await finishWith(payload, result);
    if (token === sendIdRef.current) {
      setBusy(false);
      refreshGovernance(scenario.sender.id);
    }
  }, [busy, scenario, amount, message, timeline, finishWith, toast, refreshGovernance]);

  const handleBurst = useCallback(async () => {
    if (busy) return;
    const total = scenario.burst || DEFAULT_LIMIT;
    const token = ++sendIdRef.current;
    setBusy(true);
    setSelected(null);
    setRun(null);
    timeline.reset();
    let last = null;
    for (let i = 0; i < total; i++) {
      setBurstProgress({ done: i, total });
      const payload = buildPayload({ scenario, amount, message });
      const result = await sendPixSafe(payload);
      if (token !== sendIdRef.current) return;
      if (result.network) {
        toast('Não consegui falar com o gateway.', 'danger');
        break;
      }
      last = { payload, result };
      if (!result.ok) break;
      if (result.source.original_masked) {
        await waitForInvestigation(payload.transaction_id);
        if (token !== sendIdRef.current) return;
        await refreshGovernance(scenario.sender.id);
      }
    }
    setBurstProgress(null);
    if (last) await finishWith(last.payload, last.result, { playSpeed: 2 });
    if (token === sendIdRef.current) {
      setBusy(false);
      refreshGovernance(scenario.sender.id);
    }
  }, [busy, scenario, amount, message, timeline, finishWith, toast, refreshGovernance]);

  const handlePick = useCallback(
    (sc) => {
      sendIdRef.current += 1;
      setBusy(false);
      setBurstProgress(null);
      setReplayActive(false);
      timeline.reset();
      setRun(null);
      setSelected(null);
      setScenario(sc);
      setAmount(sc.amount);
      setMessage(sc.message);
    },
    [timeline]
  );

  const handleReactivate = useCallback(async () => {
    try {
      await resetUserThreats(scenario.sender.id);
      await refreshGovernance(scenario.sender.id);
      timeline.reset();
      setRun(null);
      toast('Contagem de ocorrências zerada e conta reativada.', 'safe');
    } catch (e) {
      toast('Não foi possível zerar a contagem.', 'danger');
    }
  }, [scenario, refreshGovernance, timeline, toast]);

  // ----- Reprodução vinda das outras abas -----
  useEffect(() => {
    if (!replay) return;
    sendIdRef.current += 1;
    const token = sendIdRef.current;
    const replayScenario = {
      id: 'replay',
      title: 'Reprodução',
      sender: { id: replay.senderId, name: replay.senderName || replay.senderId, cpf: '' },
      amount: replay.amount,
      message: replay.message,
      editable: false,
    };
    setScenario(replayScenario);
    setAmount(replay.amount);
    setMessage(replay.message);
    setReplayActive(true);
    setSelected(null);
    setBusy(true);
    setRun({
      payload: { amount: replay.amount, description: replay.message, transaction_id: replay.txId },
      txId: replay.txId,
      stations: replay.stations,
      ok: true,
      masked: replay.masked,
      decidedBy: replay.decidedBy,
      realMs: replay.realMs ?? null,
      finalMessage: replay.finalMessage,
      replayed: true,
    });
    timeline.play(replay.stations, { stepMode, speed }).then(() => {
      if (token === sendIdRef.current) setBusy(false);
    });
    onReplayConsumed?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [replay?.token]);

  // ----- Controles -----
  const stations = run?.stations || EMPTY_STATIONS;
  const phase = tl.phase;
  const finished = phase === 'done';

  const handleSkip = useCallback(() => {
    if (run) timeline.skipTo(run.stations);
  }, [run, timeline]);

  const handleReplayAnimation = useCallback(async () => {
    if (!run) return;
    setSelected(null);
    setBusy(true);
    const token = ++sendIdRef.current;
    await timeline.play(run.stations, { stepMode, speed });
    if (token === sendIdRef.current) setBusy(false);
  }, [run, timeline, stepMode, speed]);

  useEffect(() => {
    if (!active) return undefined;
    const onKey = (e) => {
      if (isTyping()) return;
      if ((e.key === 'ArrowRight' || e.key === ' ') && phase === 'waiting') {
        e.preventDefault();
        timeline.next();
      } else if (e.key === 'Escape' && (phase === 'running' || phase === 'waiting')) {
        handleSkip();
      } else if ((e.key === 'r' || e.key === 'R') && finished && run) {
        handleReplayAnimation();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [active, phase, finished, run, timeline, handleSkip, handleReplayAnimation]);

  const detailIndex = selected ?? (tl.focus >= 0 ? tl.focus : -1);
  const detailContext = {
    amount: run?.payload?.amount ?? amount,
    message: run?.payload?.description ?? message,
    maskedMessage: run?.finalMessage,
  };

  const liveText = useMemo(() => {
    if (tl.focus < 0) return '';
    const stage = SYNC_STAGES[tl.focus];
    const st = tl.states[tl.focus];
    if (!stage || ['pending', 'running', 'void'].includes(st)) return '';
    return `Etapa ${stage.n}, ${stage.title}: ${verdictLabel(stage.id, st)}. ${stations[tl.focus]?.detail || ''}`;
  }, [tl.focus, tl.states, stations]);

  const senderSuspended = ficha.blocked;
  const amountLabel = formatBRL(run?.payload?.amount ?? amount);

  return (
    <div className="page journey">
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {liveText}
      </div>

      <div className="journey__head">
        <div>
          <h2 className="page__title">A viagem de uma mensagem Pix</h2>
        </div>
      </div>

      <ScenarioPicker activeId={scenario.id} onPick={handlePick} disabled={busy} replayActive={replayActive} />
      {!replayActive && (
        <p className="scenario-note" key={scenario.id}>
          <strong>Caminho:</strong> {scenario.path}. {scenario.expects}
        </p>
      )}

      <div className="journey__stage">
        <SenderPhone
          scenario={scenario}
          amount={amount}
          message={message}
          onAmountChange={setAmount}
          onMessageChange={setMessage}
          onSend={handleSend}
          busy={busy}
          suspended={senderSuspended}
          burstProgress={burstProgress}
          ficha={ficha}
          onBurst={scenario.burst ? handleBurst : null}
          burstTotal={scenario.burst}
          onReactivate={handleReactivate}
        />

        <div className="journey__center">
          <div className="card journey__track-card">
            <div className="controls" role="group" aria-label="Controles da animação">
              <div className="segmented" role="radiogroup" aria-label="Modo de reprodução">
                <button
                  type="button"
                  role="radio"
                  aria-checked={!stepMode}
                  className={!stepMode ? 'is-active' : ''}
                  onClick={() => setStepMode(false)}
                  disabled={busy}
                >
                  <Play size={14} aria-hidden="true" /> Automático
                </button>
                <button
                  type="button"
                  role="radio"
                  aria-checked={stepMode}
                  className={stepMode ? 'is-active' : ''}
                  onClick={() => setStepMode(true)}
                  disabled={busy}
                >
                  <ChevronRight size={14} aria-hidden="true" /> Passo a passo
                </button>
              </div>
              <div className="segmented" role="radiogroup" aria-label="Velocidade">
                {[1, 2].map((v) => (
                  <button
                    key={v}
                    type="button"
                    role="radio"
                    aria-checked={speed === v}
                    className={speed === v ? 'is-active' : ''}
                    onClick={() => setSpeed(v)}
                    disabled={busy}
                  >
                    {v === 2 && <FastForward size={14} aria-hidden="true" />} {v}×
                  </button>
                ))}
              </div>

              <div className="controls__spacer" />

              <AnimatePresence mode="popLayout" initial={false}>
                {phase === 'waiting' && (
                  <motion.button
                    key="next"
                    type="button"
                    className="btn btn--primary btn--sm"
                    onClick={timeline.next}
                    initial={{ opacity: 0, scale: 0.9 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0 }}
                    transition={spring.pop}
                  >
                    Próxima etapa <ChevronRight size={16} aria-hidden="true" />
                  </motion.button>
                )}
                {(phase === 'running' || phase === 'waiting') && (
                  <motion.button
                    key="skip"
                    type="button"
                    className="btn btn--ghost btn--sm"
                    onClick={handleSkip}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    <SkipForward size={14} aria-hidden="true" /> Pular animação
                  </motion.button>
                )}
                {finished && run && !busy && (
                  <motion.div
                    key="again"
                    className="controls__group"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    <button type="button" className="btn btn--ghost btn--sm" onClick={handleReplayAnimation}>
                      <RotateCcw size={14} aria-hidden="true" /> Repetir animação
                    </button>
                    {!run.replayed && (
                      <button type="button" className="btn btn--secondary btn--sm" onClick={handleSend}>
                        <Send size={14} aria-hidden="true" /> Enviar de novo
                      </button>
                    )}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            <JourneyTrack
              stations={stations}
              timeline={tl}
              selectedIndex={detailIndex}
              onSelect={(i) => setSelected(i)}
              amountLabel={amountLabel}
              reduced={reduced}
            />
            <StageDetail
              index={detailIndex}
              stations={stations}
              states={tl.states}
              context={detailContext}
              reduced={reduced}
              idleText={replayActive ? '' : scenario.expects}
              arriving={tl.cursor === detailIndex && tl.states[detailIndex] === 'pending'}
            />
          </div>

          <AnimatePresence>
            {finished && run && (
              <motion.div
                key={run.txId}
                className={`outcome outcome--${run.masked ? 'masked' : 'clean'}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: dur.base, ease }}
              >
                <strong>{DECIDED_BY_LABEL[run.decidedBy] || 'Jornada concluída.'}</strong>
                {typeof run.realMs === 'number' && (
                  <span>
                    Tempo real somado do gateway: <strong className="num">{fmtMs(run.realMs)}</strong>. A animação é
                    propositalmente mais lenta para dar para acompanhar.
                  </span>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <ReceiverPhone
          phase={phase === 'waiting' ? 'running' : phase}
          delivered={tl.delivered}
          amount={run?.payload?.amount ?? amount}
          senderName={scenario.sender.name}
          message={run?.finalMessage ?? ''}
          masked={Boolean(run?.masked)}
          realMs={run?.realMs}
        />
      </div>

      <AnimatePresence>
        {finished && run && run.ok && (
          <AfterDelivery
            key={run.txId}
            masked={run.masked}
            investigation={investigation}
            ficha={ficha}
            reduced={reduced}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
