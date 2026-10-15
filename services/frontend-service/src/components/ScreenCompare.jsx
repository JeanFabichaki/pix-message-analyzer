import React, { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'motion/react';
import { FlaskConical, Play, ShieldAlert, ShieldCheck, Target, Siren, Sparkles, ChevronDown, ChevronUp, Timer } from 'lucide-react';
import { getBenchmark, getBenchmarkDatasets, startBenchmark, generateGeminiBenchmarkMessages } from '../services/api';
import { dur, ease } from '../motion/tokens';


const ENGINES = [
  { id: 'laya', name: 'Laya original', cls: 'base' },
  { id: 'laya_tuned', name: 'Laya retreinado', cls: 'tuned' },
];
const SIZES = [
  { id: 200, label: 'Rápido (200 mensagens)' },
  { id: 0, label: 'Completo' },
];
const TABS = [
  { id: 'wins_tuned', label: 'Só o retreinado acertou' },
  { id: 'wins_base', label: 'Só o original acertou' },
  { id: 'both_wrong', label: 'Os dois erraram' },
];

const pct = (v) => `${Number(v).toFixed(1).replace('.', ',')}%`;

const fmtMs = (ms) => {
  if (ms == null || Number.isNaN(Number(ms))) return '—';
  const n = Number(ms);
  return `${n < 10 ? n.toFixed(1).replace('.', ',') : Math.round(n)} ms`;
};

const fmtDuration = (ms) => {
  if (ms == null || Number.isNaN(Number(ms))) return '—';
  const n = Number(ms);
  if (n < 1000) return `${Math.round(n)} ms`;
  const sec = n / 1000;
  return `${sec < 10 ? sec.toFixed(1).replace('.', ',') : Math.round(sec)} s`;
};

const calcDelta = (base, tuned, lowerIsBetter = true) => {
  if (base == null || tuned == null || Number.isNaN(Number(base)) || Number.isNaN(Number(tuned))) return null;
  const b = Number(base);
  const t = Number(tuned);
  if (b <= 0) return null;
  const diffPct = ((t - b) / b) * 100;
  if (Math.abs(diffPct) < 0.5) return { text: '=', type: 'neutral' };
  const isBetter = lowerIsBetter ? diffPct < 0 : diffPct > 0;
  const sign = diffPct > 0 ? '+' : '';
  return {
    text: `${sign}${Math.round(diffPct)}%`,
    type: isBetter ? 'good' : 'bad',
  };
};

function TimingTile({ label, baseVal, tunedVal, delta, hint }) {
  return (
    <div className="cmp-timing-tile" title={hint}>
      <div className="cmp-timing-tile__header">
        <span className="cmp-timing-tile__label">{label}</span>
        {delta && (
          <span className={`cmp-timing-tile__delta cmp-timing-tile__delta--${delta.type}`}>
            {delta.text}
          </span>
        )}
      </div>
      <div className="cmp-timing-tile__rows">
        <div className="cmp-timing-tile__line">
          <span className="cmp-timing-tag cmp-timing-tag--base">Orig</span>
          <span className="cmp-timing-val num">{baseVal}</span>
        </div>
        <div className="cmp-timing-tile__line">
          <span className="cmp-timing-tag cmp-timing-tag--tuned">Retr</span>
          <span className="cmp-timing-val cmp-timing-val--tuned num">{tunedVal}</span>
        </div>
      </div>
    </div>
  );
}

function Bar({ value, cls, label }) {
  return (
    <div className="cmp-bar" title={label}>
      <motion.div
        className={`cmp-bar__fill cmp-bar__fill--${cls}`}
        initial={{ width: 0 }}
        animate={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        transition={{ duration: 0.8, ease }}
      />
      <span className="cmp-bar__val num">{pct(value)}</span>
    </div>
  );
}

function MetricRow({ title, hint, a, b }) {
  return (
    <div className="cmp-metric">
      <div className="cmp-metric__title">
        <strong>{title}</strong>
        <span>{hint}</span>
      </div>
      <Bar value={a} cls="base" label={`Original: ${pct(a)}`} />
      <Bar value={b} cls="tuned" label={`Retreinado: ${pct(b)}`} />
    </div>
  );
}

function Split({ ok, bad, okLabel, badLabel, okCls }) {
  const total = ok + bad || 1;
  return (
    <div className="cmp-split">
      <div className="cmp-split__bar">
        <motion.div className={`cmp-split__ok cmp-split__ok--${okCls}`} initial={{ width: 0 }} animate={{ width: `${(100 * ok) / total}%` }} transition={{ duration: 0.8, ease }} />
        <motion.div className="cmp-split__bad" initial={{ width: 0 }} animate={{ width: `${(100 * bad) / total}%` }} transition={{ duration: 0.8, ease }} />
      </div>
      <div className="cmp-split__legend">
        <span><b className="num">{ok}</b> {okLabel}</span>
        <span><b className="num">{bad}</b> {badLabel}</span>
      </div>
    </div>
  );
}

function Verdict({ pred, label }) {
  const right = pred === (label === 'threat');
  return <span className={`chip ${right ? 'chip--safe' : 'chip--danger'}`}>{pred ? 'Ameaça' : 'Normal'} {right ? '✓' : '✗'}</span>;
}

export default function ScreenCompare({ active }) {
  const [datasets, setDatasets] = useState([]);
  const [dataset, setDataset] = useState('test');
  const [size, setSize] = useState(200);
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('wins_tuned');
  const [generatingGemini, setGeneratingGemini] = useState(false);
  const [geminiResult, setGeminiResult] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    if (active && datasets.length === 0) getBenchmarkDatasets().then(setDatasets);
  }, [active, datasets.length]);
  useEffect(() => () => clearTimeout(timer.current), []);

  const handleGenerateGemini = async () => {
    setGeneratingGemini(true);
    setError(null);
    try {
      const res = await generateGeminiBenchmarkMessages(50);
      setGeminiResult(res);
      const updated = await getBenchmarkDatasets();
      setDatasets(updated);
      setDataset('gemini');
    } catch (e) {
      setError(`Falha ao gerar mensagens com Gemini: ${e.message}`);
    } finally {
      setGeneratingGemini(false);
    }
  };

  const poll = useCallback(async (id) => {
    try {
      const j = await getBenchmark(id);
      setJob(j);
      if (j.status === 'running') timer.current = setTimeout(() => poll(id), 600);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  const run = async () => {
    clearTimeout(timer.current);
    setError(null);
    setJob({ status: 'running', total: 0, done: { laya: 0, laya_tuned: 0 } });
    try {
      const id = await startBenchmark(dataset, dataset === 'test' && size ? size : null);
      poll(id);
    } catch (e) {
      setJob(null);
      setError(e.message);
    }
  };

  const running = job?.status === 'running';
  const rep = job?.status === 'done' ? job.report : null;
  const cur = datasets.find((d) => d.id === dataset);
  const S = rep?.summary;

  return (
    <div className="page compare">
      <div className="page__head">
        <div>
          <h2 className="page__title">Comparar: Laya original × retreinado</h2>
          <p className="page__lead">
            As mesmas mensagens passam pelos dois modelos e você vê quem acerta mais. As mensagens de teste não foram
            usadas no treino.
          </p>
        </div>
      </div>

      <div className="card cmp-setup">
        <div className="cmp-setup__group">
          <div className="cmp-setup__head-row">
            <span className="cmp-setup__label">1. Escolha as mensagens</span>
            <motion.button
              type="button"
              className="btn btn--gemini"
              onClick={handleGenerateGemini}
              disabled={generatingGemini || running}
              whileTap={{ scale: 0.97 }}
              title="Chama a API do Google Gemini com um prompt estruturado para formular 50 novos casos desafiadores de teste"
            >
              <Sparkles size={15} className={generatingGemini ? 'cmp-spin' : ''} aria-hidden="true" />
              {generatingGemini
                ? 'Gerando 50 mensagens no Gemini…'
                : geminiResult
                ? 'Gerar novas 50 mensagens com Gemini'
                : 'Gerar 50 mensagens via Gemini'}
            </motion.button>
          </div>

          <div className="cmp-choices" role="radiogroup" aria-label="Conjunto de mensagens">
            {(datasets.length ? datasets : [{ id: 'test', label: 'Teste sintético', available: true }, { id: 'challenge', label: 'Escritas à mão', available: true }]).map((d) => (
              <button key={d.id} type="button" role="radio" aria-checked={dataset === d.id} disabled={running || d.available === false}
                className={`cmp-choice ${dataset === d.id ? 'is-on' : ''} ${d.id === 'gemini' ? 'cmp-choice--gemini' : ''}`}
                onClick={() => setDataset(d.id)}>
                {d.id === 'gemini' && <Sparkles size={13} style={{ marginRight: 6, display: 'inline', verticalAlign: 'middle' }} />}
                {d.label}{d.size ? ` · ${d.size}` : ''}
              </button>
            ))}
          </div>

          {generatingGemini && (
            <div className="cmp-gemini-loading">
              <span className="cmp-spinner" />
              <span>O Google Gemini está formulando 50 mensagens de teste com casos de perseguição, coação e gírias coloquiais…</span>
            </div>
          )}

          {geminiResult && dataset === 'gemini' && (
            <div className="cmp-gemini-info">
              <div className="cmp-gemini-info__header">
                <div>
                  <strong>✨ 50 Mensagens geradas via Gemini ({geminiResult.model || 'Gemini 3.5 Flash'}):</strong>
                  <span> {geminiResult.threats_count} ameaças e {geminiResult.safe_count} benignas prontas para o benchmark.</span>
                </div>
                <button
                  type="button"
                  className="btn btn--subtle btn--sm"
                  onClick={() => setShowPreview(!showPreview)}
                >
                  {showPreview ? 'Ocultar mensagens' : `Ver as ${geminiResult.count} mensagens`}
                  {showPreview ? <ChevronUp size={14} style={{ marginLeft: 4 }} /> : <ChevronDown size={14} style={{ marginLeft: 4 }} />}
                </button>
              </div>

              {showPreview && (
                <div className="cmp-gemini-preview">
                  <div className="cmp-gemini-preview__list">
                    {geminiResult.messages.map((m, idx) => (
                      <div key={m.id || idx} className={`cmp-gemini-card cmp-gemini-card--${m.label}`}>
                        <div className="cmp-gemini-card__head">
                          <span className={`chip ${m.label === 'threat' ? 'chip--danger' : 'chip--safe'}`}>
                            {m.label === 'threat' ? 'Ameaça' : 'Normal'}
                          </span>
                          <span className="cmp-gemini-card__cat">{m.category}</span>
                          {m.explanation && <span className="cmp-gemini-card__exp">{m.explanation}</span>}
                        </div>
                        <p className="cmp-gemini-card__text">“{m.text}”</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {cur?.note && <p className="cmp-setup__note">{cur.note}</p>}
        </div>
        {dataset === 'test' && (
          <div className="cmp-setup__group">
            <span className="cmp-setup__label">2. Quantas?</span>
            <div className="cmp-choices" role="radiogroup" aria-label="Quantidade">
              {SIZES.map((s) => (
                <button key={s.id} type="button" role="radio" aria-checked={size === s.id} disabled={running}
                  className={`cmp-choice ${size === s.id ? 'is-on' : ''}`} onClick={() => setSize(s.id)}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        )}
        <motion.button type="button" className="btn btn--primary cmp-run" onClick={run} disabled={running} whileTap={{ scale: 0.97 }}>
          <Play size={16} aria-hidden="true" /> {running ? 'Comparando…' : rep ? 'Rodar de novo' : 'Rodar comparação'}
        </motion.button>
      </div>


      {error && <div className="card cmp-alert" role="alert"><strong>Não deu para comparar.</strong> {error}</div>}

      {running && (
        <div className="card cmp-progress" aria-live="polite">
          <h3>Lendo as mensagens…</h3>
          {ENGINES.map((e) => {
            const done = job.done?.[e.id] || 0;
            const p = job.total ? (100 * done) / job.total : 0;
            return (
              <div key={e.id} className="cmp-progress__row">
                <span>{e.name}</span>
                <div className="cmp-bar"><div className={`cmp-bar__fill cmp-bar__fill--${e.cls}`} style={{ width: `${p}%`, transition: 'width .3s' }} /></div>
                <span className="num">{done}/{job.total || '…'}</span>
              </div>
            );
          })}
        </div>
      )}

      {job?.status === 'error' && <div className="card cmp-alert" role="alert">A comparação falhou: {job.error}</div>}

      {rep && S && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: dur.base, ease }}>
          {(rep.errors.laya > 0 || rep.errors.laya_tuned > 0) && (
            <div className="card cmp-alert" role="alert">
              {rep.errors.laya + rep.errors.laya_tuned} chamadas falharam e ficaram fora da conta. {rep.first_error}
            </div>
          )}

          <div className="cmp-heroes">
            {ENGINES.map((e) => (
              <div key={e.id} className={`cmp-hero cmp-hero--${e.cls}`}>
                <span className="cmp-hero__name">{e.name}</span>
                <span className="cmp-hero__big num">{S[e.id].tp}<small> de {S[e.id].threats_total}</small></span>
                <span className="cmp-hero__sub">ameaças detectadas</span>
                <span className="cmp-hero__alarm"><Siren size={14} aria-hidden="true" /> {S[e.id].fp} falsos alarmes em {S[e.id].safe_total} mensagens normais</span>
              </div>
            ))}
          </div>

          <div className="card cmp-timing">
            <div className="cmp-timing__head">
              <div className="cmp-timing__title">
                <Timer size={16} aria-hidden="true" />
                <span>Tempo de execução da bateria & Latência</span>
              </div>
              <div className="cmp-legend">
                <span><i className="dot dot--base" /> Original</span>
                <span><i className="dot dot--tuned" /> Retreinado</span>
              </div>
            </div>

            <div className="cmp-timing__grid">
              <TimingTile
                label="Bateria total"
                baseVal={fmtDuration(S.laya.wall_ms)}
                tunedVal={fmtDuration(S.laya_tuned.wall_ms)}
                delta={calcDelta(S.laya.wall_ms, S.laya_tuned.wall_ms, true)}
                hint="Duração total para processar todas as mensagens deste modelo"
              />
              <TimingTile
                label="Tempo médio"
                baseVal={fmtMs(S.laya.avg_ms)}
                tunedVal={fmtMs(S.laya_tuned.avg_ms)}
                delta={calcDelta(S.laya.avg_ms, S.laya_tuned.avg_ms, true)}
                hint="Latência média por inferência"
              />
              <TimingTile
                label="Mediana"
                baseVal={fmtMs(S.laya.median_ms)}
                tunedVal={fmtMs(S.laya_tuned.median_ms)}
                delta={calcDelta(S.laya.median_ms, S.laya_tuned.median_ms, true)}
                hint="Mediana do tempo de resposta"
              />
              <TimingTile
                label="p50"
                baseVal={fmtMs(S.laya.p50_ms ?? S.laya.median_ms)}
                tunedVal={fmtMs(S.laya_tuned.p50_ms ?? S.laya_tuned.median_ms)}
                delta={calcDelta(S.laya.p50_ms ?? S.laya.median_ms, S.laya_tuned.p50_ms ?? S.laya_tuned.median_ms, true)}
                hint="Percentil 50 (50% das mensagens responderam até este tempo)"
              />
              <TimingTile
                label="p95"
                baseVal={fmtMs(S.laya.p95_ms)}
                tunedVal={fmtMs(S.laya_tuned.p95_ms)}
                delta={calcDelta(S.laya.p95_ms, S.laya_tuned.p95_ms, true)}
                hint="Percentil 95 (95% das mensagens responderam até este tempo)"
              />
              <TimingTile
                label="p99"
                baseVal={fmtMs(S.laya.p99_ms)}
                tunedVal={fmtMs(S.laya_tuned.p99_ms)}
                delta={calcDelta(S.laya.p99_ms, S.laya_tuned.p99_ms, true)}
                hint="Percentil 99 (99% das mensagens responderam até este tempo)"
              />
              <TimingTile
                label="Mín / Máx"
                baseVal={`${fmtMs(S.laya.min_ms)} / ${fmtMs(S.laya.max_ms)}`}
                tunedVal={`${fmtMs(S.laya_tuned.min_ms)} / ${fmtMs(S.laya_tuned.max_ms)}`}
                delta={null}
                hint="Latência mínima e máxima observadas"
              />
              <TimingTile
                label="Vazão"
                baseVal={S.laya.throughput_rps != null ? `${S.laya.throughput_rps} msg/s` : '—'}
                tunedVal={S.laya_tuned.throughput_rps != null ? `${S.laya_tuned.throughput_rps} msg/s` : '—'}
                delta={calcDelta(S.laya.throughput_rps, S.laya_tuned.throughput_rps, false)}
                hint="Vazão de inferência em mensagens por segundo"
              />
            </div>
          </div>

          <div className="card cmp-section">
            <h3><Target size={18} aria-hidden="true" /> Placar geral</h3>
            <div className="cmp-legend"><span><i className="dot dot--base" /> Original</span><span><i className="dot dot--tuned" /> Retreinado</span></div>
            <MetricRow title="Acertos no total" hint="mensagens classificadas corretamente" a={S.laya.accuracy} b={S.laya_tuned.accuracy} />
            <MetricRow title="Ameaças que ele pegou" hint="de todas as ameaças, quantas foram detectadas (recall)" a={S.laya.recall} b={S.laya_tuned.recall} />
            <MetricRow title="Alertas que eram ameaça de verdade" hint="quando ele avisa, com que frequência está certo (precisão)" a={S.laya.precision} b={S.laya_tuned.precision} />
            <MetricRow title="Nota combinada" hint="equilíbrio entre pegar ameaças e não alarmar à toa (F1)" a={S.laya.f1} b={S.laya_tuned.f1} />
            <p className="cmp-note">
              Sobre a acurácia: como quase tudo é mensagem normal, um modelo que nunca avisasse nada já acertaria
              muito. Por isso o que mais importa é <strong>quantas ameaças ele pegou</strong>.
            </p>
          </div>

          <div className="card cmp-section">
            <h3><ShieldAlert size={18} aria-hidden="true" /> Onde cada um acertou e errou</h3>
            <div className="cmp-two">
              {ENGINES.map((e) => (
                <div key={e.id} className="cmp-box">
                  <strong>{e.name}</strong>
                  <span className="cmp-box__title">Ameaças reais</span>
                  <Split ok={S[e.id].tp} bad={S[e.id].fn} okLabel="detectadas" badLabel="passaram batido" okCls={e.cls} />
                  <span className="cmp-box__title">Mensagens normais</span>
                  <Split ok={S[e.id].tn} bad={S[e.id].fp} okLabel="liberadas" badLabel="bloqueadas sem motivo" okCls={e.cls} />
                  <div className="cmp-box__lat">
                    <div className="cmp-box__lat-main">
                      <Timer size={13} aria-hidden="true" />
                      <span>Bateria: <strong className="num">{fmtDuration(S[e.id].wall_ms)}</strong> {S[e.id].throughput_rps ? `(${S[e.id].throughput_rps} msg/s)` : ''}</span>
                    </div>
                    <div className="cmp-box__lat-pills">
                      <span title="Tempo médio por mensagem">Média: <b className="num">{fmtMs(S[e.id].avg_ms)}</b></span>
                      <span title="Mediana">Mediana: <b className="num">{fmtMs(S[e.id].median_ms)}</b></span>
                      <span title="p50">p50: <b className="num">{fmtMs(S[e.id].p50_ms ?? S[e.id].median_ms)}</b></span>
                      <span title="Percentil 95">p95: <b className="num">{fmtMs(S[e.id].p95_ms)}</b></span>
                      <span title="Percentil 99">p99: <b className="num">{fmtMs(S[e.id].p99_ms)}</b></span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card cmp-section">
            <h3><ShieldCheck size={18} aria-hidden="true" /> Acertos por tipo de mensagem</h3>
            <div className="cmp-legend"><span><i className="dot dot--base" /> Original</span><span><i className="dot dot--tuned" /> Retreinado</span></div>
            {rep.by_category.map((c) => (
              <div key={c.category} className="cmp-cat">
                <div className="cmp-cat__head">
                  <strong>{c.label}</strong>
                  <span className={`chip ${c.kind === 'threat' ? 'chip--danger' : 'chip--safe'}`}>{c.kind === 'threat' ? 'ameaça' : 'normal'}</span>
                  <span className="cmp-cat__n num">{c.n} msgs</span>
                </div>
                <Bar value={(100 * c.laya) / c.n} cls="base" label="Original" />
                <Bar value={(100 * c.laya_tuned) / c.n} cls="tuned" label="Retreinado" />
              </div>
            ))}
          </div>

          <div className="card cmp-section">
            <h3><FlaskConical size={18} aria-hidden="true" /> Mensagens de exemplo</h3>
            <div className="cmp-tabs" role="tablist">
              {TABS.map((t) => (
                <button key={t.id} type="button" role="tab" aria-selected={tab === t.id} className={`cmp-tab ${tab === t.id ? 'is-on' : ''}`} onClick={() => setTab(t.id)}>
                  {t.label} <span className="num">({rep.counts[t.id]})</span>
                </button>
              ))}
            </div>
            {rep.examples[tab].length === 0 ? (
              <p className="cmp-note">Nenhum caso nesta lista.</p>
            ) : (
              <ul className="cmp-examples">
                {rep.examples[tab].map((x, i) => (
                  <li key={i} className="cmp-ex">
                    <p className="cmp-ex__text">“{x.text}”</p>
                    <div className="cmp-ex__meta">
                      <span className="cmp-ex__cat">{x.category} · era {x.label === 'threat' ? 'ameaça' : 'normal'}</span>
                      <span>Original <Verdict pred={x.laya.pred} label={x.label} /></span>
                      <span>Retreinado <Verdict pred={x.laya_tuned.pred} label={x.label} /></span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <p className="cmp-note cmp-note--foot">
            {rep.dataset === 'test'
              ? 'O teste sintético usa frases do mesmo gerador do treino (com trechos separados), então tende a ser otimista. As mensagens escritas à mão são o teste mais honesto.'
              : 'Poucas mensagens: um erro a mais ou a menos muda bastante a porcentagem.'}{' '}
            Bateria concluída em {job.elapsed_s}s (Original: {fmtDuration(S.laya.wall_ms)}, Retreinado: {fmtDuration(S.laya_tuned.wall_ms)}).
          </p>
        </motion.div>
      )}
    </div>
  );
}
