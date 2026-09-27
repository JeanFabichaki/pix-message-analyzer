import React, { useState, useEffect, useRef } from 'react';
import { Play, Pause, Activity, Server, Shield, Zap, CheckCircle2, ShieldAlert, RotateCcw, ArrowRight, Clock, Gauge, Timer, TrendingUp } from 'lucide-react';
import { generateSyntheticPix } from '../utils/dataGenerator';
import { sendPixTransaction, getThreatIntelStats, getSyncLatencyTelemetry, resetSyncLatencyTelemetry } from '../services/api';

function calculatePercentiles(samples) {
  if (!samples || samples.length === 0) {
    return {
      p50: null,
      p95: null,
      p99: null,
      min: null,
      max: null,
      avg: null,
      count: 0,
      withinSlaPct: 100,
    };
  }
  const sorted = [...samples].sort((a, b) => a - b);
  const n = sorted.length;
  const p50 = sorted[Math.min(Math.floor(n * 0.50), n - 1)];
  const p95 = sorted[Math.min(Math.floor(n * 0.95), n - 1)];
  const p99 = sorted[Math.min(Math.floor(n * 0.99), n - 1)];
  const min = sorted[0];
  const max = sorted[n - 1];
  const avg = sorted.reduce((acc, v) => acc + v, 0) / n;
  const withinSla = sorted.filter((v) => v <= 15.0).length;
  const withinSlaPct = (withinSla / n) * 100;

  return {
    p50: Number(p50.toFixed(2)),
    p95: Number(p95.toFixed(2)),
    p99: Number(p99.toFixed(2)),
    min: Number(min.toFixed(2)),
    max: Number(max.toFixed(2)),
    avg: Number(avg.toFixed(2)),
    count: n,
    withinSlaPct: Number(withinSlaPct.toFixed(1)),
  };
}

export default function Screen2Matrix() {
  const [isRunning, setIsRunning] = useState(false);
  const [targetTps, setTargetTps] = useState(5);
  const [currentTps, setCurrentTps] = useState(0);

  // Contadores
  const [totalProcessed, setTotalProcessed] = useState(0);
  const [totalMasked, setTotalMasked] = useState(0);
  const [totalClean, setTotalClean] = useState(0);
  const [totalBlocked, setTotalBlocked] = useState(0);
  const [intelStats, setIntelStats] = useState({ total_signatures: 0, total_occurrences: 0 });

  // Telemetria de Latência Síncrona (p50, p95, p99)
  const latenciesRef = useRef([]);
  const [latencyStats, setLatencyStats] = useState(() => calculatePercentiles([]));
  const [gatewayTelemetry, setGatewayTelemetry] = useState(null);

  // Histórico de TPS para gráfico de vazão (últimos 24 pontos)
  const [tpsHistory, setTpsHistory] = useState(Array(24).fill(0));

  // Feed recente
  const [recentEvents, setRecentEvents] = useState([]);

  const intervalRef = useRef(null);
  const counterRef = useRef({ processed: 0, masked: 0, clean: 0, blocked: 0 });

  useEffect(() => {
    let isMounted = true;
    const loadIntel = async () => {
      try {
        const [stats, telemetry] = await Promise.all([
          getThreatIntelStats(),
          getSyncLatencyTelemetry(),
        ]);
        if (isMounted) {
          if (stats) {
            setIntelStats({
              total_signatures: stats.total_signatures || 0,
              total_occurrences: stats.total_occurrences || 0,
            });
          }
          if (telemetry && telemetry.total_samples > 0) {
            setGatewayTelemetry(telemetry);
            if (latenciesRef.current.length === 0 && telemetry.recent_samples?.length > 0) {
              latenciesRef.current = [...telemetry.recent_samples];
              setLatencyStats(calculatePercentiles(latenciesRef.current));
            }
          }
        }
      } catch (err) {}
    };
    loadIntel();
    const timer = setInterval(loadIntel, 2500);
    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!isRunning) {
      if (intervalRef.current) clearInterval(intervalRef.current);
      setCurrentTps(0);
      return;
    }

    const intervalMs = Math.max(40, Math.floor(1000 / targetTps));
    let tpsCount = 0;

    const tpsMeterInterval = setInterval(() => {
      setCurrentTps(tpsCount);
      setTpsHistory((prev) => [...prev.slice(1), tpsCount]);
      tpsCount = 0;
    }, 1000);

    intervalRef.current = setInterval(async () => {
      const pix = generateSyntheticPix();
      tpsCount++;
      const tStart = performance.now();

      try {
        const res = await sendPixTransaction({
          transaction_id: pix.transaction_id,
          sender_id: pix.sender_id,
          sender_cpf: pix.sender_cpf,
          receiver_id: pix.receiver_id,
          receiver_cpf: pix.receiver_cpf,
          direction: 'CASH_OUT',
          amount: pix.amount,
          description: pix.description,
        });

        const syncMs = res?.timing?.total_gateway_ms || Number((performance.now() - tStart).toFixed(2));
        latenciesRef.current.push(syncMs);
        if (latenciesRef.current.length > 1000) latenciesRef.current.shift();
        setLatencyStats(calculatePercentiles(latenciesRef.current));

        counterRef.current.processed++;
        const isMasked = res?.original_masked ?? false;
        if (isMasked) {
          counterRef.current.masked++;
        } else {
          counterRef.current.clean++;
        }

        setTotalProcessed(counterRef.current.processed);
        setTotalMasked(counterRef.current.masked);
        setTotalClean(counterRef.current.clean);
        setTotalBlocked(counterRef.current.blocked);

        setRecentEvents((prev) => [
          {
            ...pix,
            description: res?.description || pix.description,
            masked: isMasked,
            status: isMasked ? 'MASKED' : 'APPROVED',
            canonical_message: res?.canonical_message,
            evasion_detected: res?.evasion_detected,
            sync_ms: syncMs,
          },
          ...prev.slice(0, 14),
        ]);
      } catch (err) {
        if (err?.status === 403 || err?.payload?.status === 'REJECTED_BLOCKED') {
          const blockMs = err?.payload?.timing?.total_gateway_ms || 1.2;
          latenciesRef.current.push(blockMs);
          if (latenciesRef.current.length > 1000) latenciesRef.current.shift();
          setLatencyStats(calculatePercentiles(latenciesRef.current));

          counterRef.current.blocked++;
          counterRef.current.processed++;
          setTotalBlocked(counterRef.current.blocked);
          setTotalProcessed(counterRef.current.processed);
          setRecentEvents((prev) => [
            {
              ...pix,
              description: 'CONTA SUSPENSA (5x INFRAÇÕES)',
              masked: true,
              status: 'BLOCKED',
              sync_ms: blockMs,
            },
            ...prev.slice(0, 14),
          ]);
        }
      }
    }, intervalMs);

    return () => {
      clearInterval(intervalRef.current);
      clearInterval(tpsMeterInterval);
    };
  }, [isRunning, targetTps]);

  const toggleRun = () => {
    setIsRunning(!isRunning);
  };

  const handleReset = async () => {
    setIsRunning(false);
    counterRef.current = { processed: 0, masked: 0, clean: 0, blocked: 0 };
    latenciesRef.current = [];
    setLatencyStats(calculatePercentiles([]));
    setGatewayTelemetry(null);
    setTotalProcessed(0);
    setTotalMasked(0);
    setTotalClean(0);
    setTotalBlocked(0);
    setRecentEvents([]);
    setTpsHistory(Array(24).fill(0));
    try {
      await resetSyncLatencyTelemetry();
    } catch (e) {}
  };

  useEffect(() => {
    const handleKeyDown = (e) => {
      const tag = document.activeElement?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      if (e.code === 'Space') {
        e.preventDefault();
        setIsRunning((prev) => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const blockRate = totalProcessed > 0 ? ((totalMasked / totalProcessed) * 100).toFixed(1) : '0.0';

  const activeStats = latencyStats.count > 0 
    ? latencyStats 
    : gatewayTelemetry && gatewayTelemetry.total_samples > 0
    ? {
        p50: gatewayTelemetry.p50_ms,
        p95: gatewayTelemetry.p95_ms,
        p99: gatewayTelemetry.p99_ms,
        min: gatewayTelemetry.min_ms,
        max: gatewayTelemetry.max_ms,
        avg: gatewayTelemetry.avg_ms,
        count: gatewayTelemetry.total_samples,
        withinSlaPct: gatewayTelemetry.within_sla_pct,
      }
    : calculatePercentiles([]);

  return (
    <div className="screen-container">
      {/* 1. WORKFLOW RIBBON: Contextualização do Fluxo de Alta Carga */}
      <section aria-label="Explicação da arquitetura de alta vazão" className="workflow-ribbon">
        <div className="workflow-step">
          <div className="workflow-step-num stage-sync">1</div>
          <div>
            <div className="workflow-step-title">Injeção Transacional</div>
            <div className="workflow-step-desc">Simulação de alto volume com cadência configurável de 1 a 20 ops/s.</div>
          </div>
        </div>

        <div className="workflow-step">
          <div className="workflow-step-num stage-sync">2</div>
          <div>
            <div className="workflow-step-title">Filtro de Baixo Custo (&lt;1ms)</div>
            <div className="workflow-step-desc">Threat Intel Cache intercepta assinaturas conhecidas na hora.</div>
          </div>
        </div>

        <div className="workflow-step">
          <div className="workflow-step-num stage-sync">3</div>
          <div>
            <div className="workflow-step-title">Borda Local (~10ms)</div>
            <div className="workflow-step-desc">Ollaya laya processa mensagens sem consumo de token cloud.</div>
          </div>
        </div>

        <div className="workflow-step">
          <div className="workflow-step-num stage-async">4</div>
          <div>
            <div className="workflow-step-title">Auditoria Imutável</div>
            <div className="workflow-step-desc">Apenas anomalias e ameaças geram despacho ao Gemini em nuvem.</div>
          </div>
        </div>
      </section>

      {/* Header com Controles Operacionais */}
      <section
        aria-labelledby="matrix-page-title"
        style={{ marginBottom: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}
      >
        <div>
          <h2
            id="matrix-page-title"
            style={{ fontSize: '1.35rem', fontWeight: '700', letterSpacing: '-0.02em', color: 'var(--color-ink)' }}
          >
            Telemetria de Alta Vazão & Stress Test do Motor
          </h2>
          <p style={{ color: 'var(--color-ink-muted)', marginTop: '0.2rem', fontSize: '0.85rem' }}>
            Monitore o comportamento da triagem em tempo real sob volume contínuo de transações bancárias.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', flexWrap: 'wrap' }}>
          {/* Seletor de Cadência */}
          <div
            role="radiogroup"
            aria-label="Cadência de injeção"
            style={{ display: 'flex', background: 'var(--color-paper-card)', padding: '0.2rem', borderRadius: 'var(--radius-pill)', border: '1px solid var(--color-rule)', gap: '0.2rem' }}
          >
            {[1, 5, 10, 20].map((rate) => (
              <button
                key={rate}
                type="button"
                role="radio"
                aria-checked={targetTps === rate}
                style={{
                  background: targetTps === rate ? 'var(--color-ink)' : 'transparent',
                  color: targetTps === rate ? '#ffffff' : 'var(--color-ink-muted)',
                  border: 'none',
                  padding: '0.3rem 0.65rem',
                  borderRadius: 'var(--radius-pill)',
                  fontSize: '0.72rem',
                  fontFamily: 'var(--font-mono)',
                  fontWeight: targetTps === rate ? '700' : '500',
                  cursor: 'pointer',
                  transition: 'all var(--dur-fast) var(--ease-snappy)',
                }}
                onClick={() => setTargetTps(rate)}
                aria-label={`${rate} transações por segundo`}
              >
                {rate}/s
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={toggleRun}
            aria-label={isRunning ? 'Pausar simulação de alta vazão' : `Iniciar simulação com ${targetTps} transações por segundo`}
            style={{
              background: isRunning ? 'var(--color-danger)' : 'var(--color-accent)',
              color: '#ffffff',
              fontWeight: '600',
              padding: '0.55rem 1.15rem',
              borderRadius: 'var(--radius-pill)',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              fontSize: '0.82rem',
              transition: 'all var(--dur-fast) var(--ease-snappy)',
              boxShadow: 'var(--shadow-subtle)',
            }}
          >
            {isRunning ? <Pause size={15} aria-hidden="true" /> : <Play size={15} aria-hidden="true" />}
            <span>{isRunning ? 'Pausar (Space)' : `Iniciar ${targetTps} Pix/s`}</span>
          </button>

          <button
            type="button"
            onClick={handleReset}
            aria-label="Zerar contadores e métricas de telemetria"
            style={{
              background: 'var(--color-paper-card)',
              color: 'var(--color-ink-secondary)',
              border: '1px solid var(--color-rule)',
              padding: '0.55rem 0.85rem',
              borderRadius: 'var(--radius-pill)',
              cursor: 'pointer',
              fontWeight: '500',
              fontSize: '0.82rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              transition: 'all var(--dur-fast) var(--ease-snappy)',
            }}
          >
            <RotateCcw size={13} aria-hidden="true" />
            <span>Zerar</span>
          </button>
        </div>
      </section>

      {/* Grid Principal: Métricas e Visualização da Topologia */}
      <div className="matrix-grid">
        {/* LADO ESQUERDO: MÉTRICAS DE VAZÃO & HISTOGRAMA */}
        <section aria-labelledby="telemetry-overview-title" className="glass-panel" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <div>
              <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', color: 'var(--color-ink-muted)', fontFamily: 'var(--font-mono)', fontWeight: '600' }}>
                Vazão de Ingestão & SLA
              </span>
              <h3 id="telemetry-overview-title" style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--color-ink)' }}>
                Atividade Transacional
              </h3>
            </div>
            <div
              role="status"
              className={`badge ${isRunning ? 'badge-active' : 'badge-media'}`}
            >
              <span className="pulsing-dot" style={{ background: isRunning ? 'var(--color-accent)' : 'var(--color-ink-muted)' }} aria-hidden="true"></span>
              <span>{isRunning ? 'PROCESSANDO AO VIVO' : 'EM REPOUSO'}</span>
            </div>
          </div>

          {/* Cards de Métricas */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1.25rem' }}>
            <div style={{ background: 'var(--color-paper-subtle)', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-rule)' }}>
              <span style={{ fontSize: '0.68rem', color: 'var(--color-ink-muted)', textTransform: 'uppercase', fontWeight: '600' }}>Vazão Efetiva</span>
              <div style={{ fontSize: '1.45rem', fontWeight: '700', color: isRunning ? 'var(--color-accent)' : 'var(--color-ink)', marginTop: '0.15rem', fontFamily: 'var(--font-mono)' }}>
                {currentTps} <span style={{ fontSize: '0.75rem', fontWeight: '500', color: 'var(--color-ink-muted)' }}>ops/s</span>
              </div>
              <span style={{ fontSize: '0.68rem', color: 'var(--color-ink-muted)' }}>Meta: {targetTps} ops/s</span>
            </div>

            <div style={{ background: 'var(--color-paper-subtle)', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-rule)' }}>
              <span style={{ fontSize: '0.68rem', color: 'var(--color-ink-muted)', textTransform: 'uppercase', fontWeight: '600' }}>Taxa de Mascaramento</span>
              <div style={{ fontSize: '1.45rem', fontWeight: '700', color: parseFloat(blockRate) > 0 ? 'var(--color-danger)' : 'var(--color-ink)', marginTop: '0.15rem', fontFamily: 'var(--font-mono)' }}>
                {blockRate}%
              </div>
              <span style={{ fontSize: '0.68rem', color: 'var(--color-ink-muted)' }}>{totalMasked} mensagens censuradas</span>
            </div>

            <div style={{ background: 'var(--color-paper-subtle)', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-rule)' }}>
              <span style={{ fontSize: '0.68rem', color: 'var(--color-ink-muted)', textTransform: 'uppercase', fontWeight: '600' }}>Total Ingerido</span>
              <div style={{ fontSize: '1.45rem', fontWeight: '700', color: 'var(--color-ink)', marginTop: '0.15rem', fontFamily: 'var(--font-mono)' }}>
                {totalProcessed.toLocaleString()}
              </div>
              <span style={{ fontSize: '0.68rem', color: 'var(--color-success)', fontWeight: '600' }}>{totalClean.toLocaleString()} limpos</span>
            </div>

            <div style={{ background: 'var(--color-paper-subtle)', padding: '0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-rule)' }}>
              <span style={{ fontSize: '0.68rem', color: 'var(--color-ink-muted)', textTransform: 'uppercase', fontWeight: '600' }}>Cache Threat Intel</span>
              <div style={{ fontSize: '1.45rem', fontWeight: '700', color: 'var(--color-navy)', marginTop: '0.15rem', fontFamily: 'var(--font-mono)' }}>
                {intelStats.total_occurrences}
              </div>
              <span style={{ fontSize: '0.68rem', color: 'var(--color-ink-muted)' }}>Interceptados &lt;1ms</span>
            </div>
          </div>

          {/* BLOCO DE PERCENTIS DE LATÊNCIA SÍNCRONA (BORDA PIX) */}
          <div
            aria-label="Percentis de latência síncrona p50, p95 e p99"
            style={{
              background: 'var(--color-paper-subtle)',
              border: '1px solid var(--color-rule)',
              borderRadius: 'var(--radius-sm)',
              padding: '1rem',
              marginBottom: '1.25rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.85rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Clock size={14} color="var(--color-accent)" aria-hidden="true" />
                  <span style={{ fontSize: '0.68rem', textTransform: 'uppercase', color: 'var(--color-ink-muted)', fontFamily: 'var(--font-mono)', fontWeight: '700' }}>
                    SLA da Borda Síncrona (Caminho Crítico)
                  </span>
                </div>
                <h3 style={{ fontSize: '1.05rem', fontWeight: '700', color: 'var(--color-ink)', marginTop: '0.15rem' }}>
                  Percentis de Latência: p50 / p95 / p99
                </h3>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--color-ink-muted)', background: 'var(--color-paper)', padding: '0.2rem 0.45rem', borderRadius: '4px', border: '1px solid var(--color-rule)' }}>
                  Teto BACEN: &le; 15 ms
                </span>
                <span className={`badge ${activeStats.withinSlaPct >= 95 ? 'badge-active' : 'badge-blocked'}`} style={{ fontSize: '0.68rem', fontWeight: '700' }}>
                  {activeStats.count > 0 ? `${activeStats.withinSlaPct}% no SLA` : 'Aguardando fluxo'}
                </span>
              </div>
            </div>

            {/* Grid dos 3 Percentis Chave */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '0.65rem', marginBottom: '0.85rem' }}>
              {/* CARD P50 */}
              <div style={{ background: 'var(--color-paper-card)', padding: '0.75rem', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-rule)', borderLeft: '3px solid var(--color-success)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--color-ink)' }}>p50 (Mediana)</span>
                  <span style={{ fontSize: '0.62rem', color: 'var(--color-success)', fontWeight: '600' }}>Caso Típico</span>
                </div>
                <div style={{ fontSize: '1.45rem', fontWeight: '700', color: 'var(--color-success)', fontFamily: 'var(--font-mono)', marginTop: '0.2rem' }}>
                  {activeStats.p50 !== null ? `${activeStats.p50} ms` : '—'}
                </div>
                <p style={{ fontSize: '0.66rem', color: 'var(--color-ink-muted)', marginTop: '0.2rem', lineHeight: '1.25' }}>
                  50% das transações respondem abaixo deste tempo.
                </p>
              </div>

              {/* CARD P95 */}
              <div style={{ background: 'var(--color-paper-card)', padding: '0.75rem', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-rule)', borderLeft: '3px solid var(--color-accent)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--color-ink)' }}>p95 (95%)</span>
                  <span style={{ fontSize: '0.62rem', color: 'var(--color-accent)', fontWeight: '600' }}>Carga / Rede</span>
                </div>
                <div style={{ fontSize: '1.45rem', fontWeight: '700', color: 'var(--color-accent)', fontFamily: 'var(--font-mono)', marginTop: '0.2rem' }}>
                  {activeStats.p95 !== null ? `${activeStats.p95} ms` : '—'}
                </div>
                <p style={{ fontSize: '0.66rem', color: 'var(--color-ink-muted)', marginTop: '0.2rem', lineHeight: '1.25' }}>
                  95% das transações dentro da margem de segurança.
                </p>
              </div>

              {/* CARD P99 */}
              <div style={{ background: 'var(--color-paper-card)', padding: '0.75rem', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-rule)', borderLeft: '3px solid var(--color-stage2)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <span style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--color-ink)' }}>p99 (Cauda)</span>
                  <span style={{ fontSize: '0.62rem', color: 'var(--color-stage2)', fontWeight: '600' }}>Pior Caso (1%)</span>
                </div>
                <div style={{ fontSize: '1.45rem', fontWeight: '700', color: activeStats.p99 > 15 ? 'var(--color-warning)' : 'var(--color-stage2)', fontFamily: 'var(--font-mono)', marginTop: '0.2rem' }}>
                  {activeStats.p99 !== null ? `${activeStats.p99} ms` : '—'}
                </div>
                <p style={{ fontSize: '0.66rem', color: 'var(--color-ink-muted)', marginTop: '0.2rem', lineHeight: '1.25' }}>
                  Cauda extrema de latência sob concorrência / IA.
                </p>
              </div>
            </div>

            {/* Barra Visual Comparativa dos Percentis vs Teto BACEN (15ms) */}
            <div style={{ background: 'var(--color-paper-card)', padding: '0.7rem 0.85rem', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-rule)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--color-ink-muted)', marginBottom: '0.35rem', flexWrap: 'wrap', gap: '0.25rem' }}>
                <span>0 ms</span>
                <span style={{ color: 'var(--color-success)', fontWeight: '600' }}>p50: {activeStats.p50 ?? 0}ms</span>
                <span style={{ color: 'var(--color-accent)', fontWeight: '600' }}>p95: {activeStats.p95 ?? 0}ms</span>
                <span style={{ color: 'var(--color-stage2)', fontWeight: '600' }}>p99: {activeStats.p99 ?? 0}ms</span>
                <span style={{ color: 'var(--color-danger)', fontWeight: '700' }}>Teto BACEN: 15 ms</span>
              </div>
              
              <div style={{ height: '8px', background: 'var(--color-paper-inset)', borderRadius: '4px', position: 'relative', overflow: 'hidden' }}>
                {/* Marcador 15ms BACEN (75% da escala de 20ms) */}
                <div style={{ position: 'absolute', left: '75%', top: 0, bottom: 0, width: '2px', background: 'var(--color-danger)', zIndex: 3 }} title="Limite BACEN 15ms" />
                {/* Barra p50 */}
                <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${Math.min(100, ((activeStats.p50 || 0) / 20) * 100)}%`, background: 'var(--color-success)', opacity: 0.9, zIndex: 2, transition: 'width 0.3s ease' }} />
                {/* Barra p95 */}
                <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${Math.min(100, ((activeStats.p95 || 0) / 20) * 100)}%`, background: 'var(--color-accent)', opacity: 0.6, zIndex: 1, transition: 'width 0.3s ease' }} />
                {/* Barra p99 */}
                <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${Math.min(100, ((activeStats.p99 || 0) / 20) * 100)}%`, background: 'var(--color-stage2)', opacity: 0.3, zIndex: 0, transition: 'width 0.3s ease' }} />
              </div>

              {/* Resumo Estatístico Min / Média / Max / Amostras */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.45rem', fontSize: '0.67rem', color: 'var(--color-ink-muted)', flexWrap: 'wrap', gap: '0.35rem' }}>
                <div>
                  <span>Mínimo: <strong>{activeStats.min !== null ? `${activeStats.min} ms` : '—'}</strong></span>
                  <span style={{ margin: '0 0.35rem' }}>•</span>
                  <span>Média: <strong>{activeStats.avg !== null ? `${activeStats.avg} ms` : '—'}</strong></span>
                  <span style={{ margin: '0 0.35rem' }}>•</span>
                  <span>Máximo: <strong>{activeStats.max !== null ? `${activeStats.max} ms` : '—'}</strong></span>
                </div>
                <div>
                  <span>Amostras síncronas avaliadas: <strong>{activeStats.count}</strong></span>
                </div>
              </div>
            </div>

            {/* Sub-tempos da Borda (Decomposição Arquitetural) */}
            {gatewayTelemetry?.breakdown && (
              <div style={{ marginTop: '0.65rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.64rem', color: 'var(--color-ink-muted)', background: 'var(--color-paper-card)', border: '1px solid var(--color-rule)', padding: '0.2rem 0.45rem', borderRadius: '4px' }}>
                  ⚡ Anti-Bypass p50: <strong>{gatewayTelemetry.breakdown.anti_evasion_p50_ms ?? 0.04} ms</strong>
                </span>
                <span style={{ fontSize: '0.64rem', color: 'var(--color-ink-muted)', background: 'var(--color-paper-card)', border: '1px solid var(--color-rule)', padding: '0.2rem 0.45rem', borderRadius: '4px' }}>
                  🛡️ Threat Intel p50: <strong>{gatewayTelemetry.breakdown.threat_intel_p50_ms ?? 0.5} ms</strong>
                </span>
                <span style={{ fontSize: '0.64rem', color: 'var(--color-ink-muted)', background: 'var(--color-paper-card)', border: '1px solid var(--color-rule)', padding: '0.2rem 0.45rem', borderRadius: '4px' }}>
                  ⚡ Ollaya SLM p50: <strong>{gatewayTelemetry.breakdown.ollaya_p50_ms ?? 0.0} ms</strong>
                </span>
              </div>
            )}
          </div>

          {/* Histograma de Vazão dos Últimos 24 segundos */}
          <div style={{ background: 'var(--color-paper-subtle)', padding: '0.9rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--color-rule)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.55rem' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--color-ink-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)', fontWeight: '600' }}>
                Histograma de Vazão (Últimos 24s)
              </span>
              <span style={{ fontSize: '0.7rem', color: 'var(--color-success)', fontWeight: '600', fontFamily: 'var(--font-mono)' }}>
                SLA Médio: &lt; 15ms
              </span>
            </div>

            <div
              role="img"
              aria-label={`Histograma de vazão dos últimos 24 segundos. Vazão atual: ${currentTps} transações por segundo.`}
              style={{ height: '65px', display: 'flex', alignItems: 'flex-end', gap: '4px', padding: '4px 0' }}
            >
              {tpsHistory.map((val, idx) => {
                const scale = targetTps > 0 ? Math.min(1, Math.max(0.08, val / targetTps)) : 0.08;
                return (
                  <div
                    key={idx}
                    style={{
                      flex: 1,
                      height: '100%',
                      transform: `scaleY(${scale})`,
                      transformOrigin: 'bottom',
                      background: val > 0 ? (val >= targetTps * 0.8 ? 'var(--color-accent)' : 'var(--color-navy)') : 'rgba(0, 0, 0, 0.06)',
                      borderRadius: '2px',
                      transition: 'transform 0.2s ease, background 0.2s ease',
                    }}
                    title={`${val} ops/s`}
                  />
                );
              })}
            </div>
          </div>
        </section>

        {/* LADO DIREITO: TOPOLOGIA DE SERVIÇOS & FEED TABULAR */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Topologia dos Nós do Pipeline */}
          <section aria-labelledby="topology-section-title" className="glass-panel" style={{ padding: '1.25rem' }}>
            <h3 id="topology-section-title" style={{ fontSize: '0.7rem', color: 'var(--color-ink-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)', display: 'block', marginBottom: '0.75rem', fontWeight: '600' }}>
              Topologia do Pipeline de Defesa em 5 Nós:
            </h3>
            <div className="pipeline-nodes-grid" role="list">
              <div role="listitem" style={{ background: 'var(--color-paper-subtle)', border: '1px solid var(--color-rule)', borderRadius: 'var(--radius-sm)', padding: '0.65rem', textAlign: 'center' }}>
                <Server size={16} color="var(--color-navy)" style={{ margin: '0 auto 0.25rem' }} aria-hidden="true" />
                <div style={{ fontSize: '0.76rem', fontWeight: '600', color: 'var(--color-ink)' }}>pix-gateway</div>
                <div style={{ fontSize: '0.67rem', color: 'var(--color-ink-muted)', fontFamily: 'var(--font-mono)' }}>Porta 8001</div>
              </div>

              <div role="listitem" style={{ background: 'var(--color-paper-subtle)', border: '1px solid var(--color-rule)', borderRadius: 'var(--radius-sm)', padding: '0.65rem', textAlign: 'center' }}>
                <Shield size={16} color="var(--color-navy)" style={{ margin: '0 auto 0.25rem' }} aria-hidden="true" />
                <div style={{ fontSize: '0.76rem', fontWeight: '600', color: 'var(--color-ink)' }}>Threat Intel</div>
                <div style={{ fontSize: '0.67rem', color: 'var(--color-ink-muted)', fontFamily: 'var(--font-mono)' }}>Cache &lt;1ms</div>
              </div>

              <div role="listitem" style={{ background: 'var(--color-paper-subtle)', border: '1px solid var(--color-rule)', borderRadius: 'var(--radius-sm)', padding: '0.65rem', textAlign: 'center' }}>
                <Zap size={16} color="var(--color-accent)" style={{ margin: '0 auto 0.25rem' }} aria-hidden="true" />
                <div style={{ fontSize: '0.76rem', fontWeight: '600', color: 'var(--color-ink)' }}>Ollaya (laya)</div>
                <div style={{ fontSize: '0.67rem', color: 'var(--color-accent)', fontFamily: 'var(--font-mono)', fontWeight: '600' }}>Decisão ~10ms</div>
              </div>

              <div role="listitem" style={{ background: 'var(--color-paper-subtle)', border: '1px solid var(--color-rule)', borderRadius: 'var(--radius-sm)', padding: '0.65rem', textAlign: 'center' }}>
                <Activity size={16} color="var(--color-stage2)" style={{ margin: '0 auto 0.25rem' }} aria-hidden="true" />
                <div style={{ fontSize: '0.76rem', fontWeight: '600', color: 'var(--color-ink)' }}>Gemini 2.5</div>
                <div style={{ fontSize: '0.67rem', color: 'var(--color-stage2)', fontFamily: 'var(--font-mono)' }}>Async Forense</div>
              </div>

              <div role="listitem" style={{ background: 'var(--color-paper-subtle)', border: '1px solid var(--color-rule)', borderRadius: 'var(--radius-sm)', padding: '0.65rem', textAlign: 'center' }}>
                <ShieldAlert size={16} color="var(--color-navy)" style={{ margin: '0 auto 0.25rem' }} aria-hidden="true" />
                <div style={{ fontSize: '0.76rem', fontWeight: '600', color: 'var(--color-ink)' }}>Governança</div>
                <div style={{ fontSize: '0.67rem', color: 'var(--color-ink-muted)', fontFamily: 'var(--font-mono)' }}>PostgreSQL</div>
              </div>
            </div>
          </section>

          {/* Stream de Transações em Formato Tabular Limpo */}
          <section aria-labelledby="live-feed-title" className="glass-panel" style={{ padding: '1.25rem', flex: 1, minHeight: '380px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <div>
                <span style={{ fontSize: '0.7rem', color: 'var(--color-ink-muted)', textTransform: 'uppercase', fontFamily: 'var(--font-mono)', fontWeight: '600' }}>
                  Feed Contínuo
                </span>
                <h4 id="live-feed-title" style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--color-ink)' }}>
                  Amostragem de Transações ao Vivo
                </h4>
              </div>
              <span style={{ fontSize: '0.72rem', color: 'var(--color-ink-muted)' }}>
                {recentEvents.length} eventos no buffer
              </span>
            </div>

            {recentEvents.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '3.5rem 1rem', color: 'var(--color-ink-muted)', fontSize: '0.82rem' }}>
                Clique em "Iniciar" acima para observar o fluxo contínuo de transações em alta vazão.
              </div>
            ) : (
              <div
                role="log"
                aria-live="polite"
                aria-label="Transações processadas recentemente"
                style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}
              >
                {recentEvents.map((evt, idx) => (
                  <div
                    key={evt.transaction_id || idx}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.55rem 0.8rem',
                      background: 'var(--color-paper-subtle)',
                      border: '1px solid var(--color-rule)',
                      borderRadius: 'var(--radius-xs)',
                      fontSize: '0.78rem',
                      transition: 'background var(--dur-fast) var(--ease-snappy)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', minWidth: 0, flex: 1 }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--color-ink-muted)', whiteSpace: 'nowrap' }}>
                        {new Date(evt.timestamp).toLocaleTimeString()}
                      </span>
                      <span style={{ fontWeight: '600', color: 'var(--color-ink)', whiteSpace: 'nowrap' }}>
                        R$ {evt.amount?.toFixed(2)}
                      </span>
                      <span style={{ color: evt.masked ? 'var(--color-danger)' : 'var(--color-ink-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontStyle: evt.masked ? 'italic' : 'normal', fontWeight: evt.masked ? '600' : 'normal' }}>
                        "{evt.description || '(Sem mensagem)'}"
                      </span>
                    </div>

                    <div style={{ marginLeft: '0.75rem', flexShrink: 0, display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                      {evt.sync_ms !== undefined && (
                        <span style={{ fontSize: '0.67rem', fontFamily: 'var(--font-mono)', color: 'var(--color-ink-muted)', background: 'var(--color-paper-card)', padding: '0.15rem 0.35rem', borderRadius: '3px', border: '1px solid var(--color-rule)' }}>
                          {Number(evt.sync_ms).toFixed(1)} ms
                        </span>
                      )}
                      <span className={`badge ${evt.masked ? 'badge-blocked' : 'badge-active'}`}>
                        {evt.masked ? 'Mascarado' : 'Aprovado'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
