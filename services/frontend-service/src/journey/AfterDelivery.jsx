import React, { useState } from 'react';
import { motion } from 'motion/react';
import {
  Brain,
  ClipboardList,
  Lock,
  AlertTriangle,
  ShieldCheck,
  History,
  Activity,
  SearchCheck,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  MessageSquare,
  Quote,
} from 'lucide-react';
import DotMeter from '../components/ui/DotMeter';
import Skeleton from '../components/ui/Skeleton';
import { ASYNC_STAGES } from './stages';
import { CRITICALITY_LABEL, categoryLabel, fmtMs } from './format';
import { dur, ease, spring } from '../motion/tokens';

const ICONS = { laudo: Brain, ficha: ClipboardList };

function TypeReveal({ text, play }) {
  const words = String(text || '').split(/\s+/).filter(Boolean);
  const step = Math.min(0.05, 1.2 / Math.max(words.length, 1));
  return (
    <p className="after-card__text">
      {words.map((w, i) => (
        <motion.span
          key={`${w}-${i}`}
          initial={play ? { opacity: 0 } : false}
          animate={{ opacity: 1 }}
          transition={{ delay: i * step, duration: 0.15 }}
        >
          {w}{' '}
        </motion.span>
      ))}
    </p>
  );
}

function Card({ stage, index, play, children, tone = 'default' }) {
  const Icon = ICONS[stage.id];
  return (
    <motion.article
      className={`after-card after-card--${tone}`}
      initial={play ? { opacity: 0, y: 14 } : false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: play ? 0.12 + index * 0.08 : 0, duration: dur.base, ease }}
    >
      <header className="after-card__head">
        <span className="after-card__num">{stage.n}</span>
        <div>
          <h4>{stage.title}</h4>
          <span className="after-card__sub">{stage.sub}</span>
        </div>
        <Icon size={18} aria-hidden="true" className="after-card__icon" />
      </header>
      {children}
    </motion.article>
  );
}

export default function AfterDelivery({ masked, investigation, ficha, reduced, targetMessage }) {
  const play = !reduced;
  const [showHistory, setShowHistory] = useState(false);
  const data = investigation.data;
  const analysis = data?.analysis;
  const isBypass = Boolean(
    analysis?.bypassed || data?.bypassed || data?.status === 'BYPASS' || analysis?.categoria === 'bypass'
  );
  const [laudo, fichaStage] = ASYNC_STAGES;

  const historyAnalyzed = data?.history_analyzed || [];
  const targetMsg = data?.target_message || targetMessage;
  const historyCount = historyAnalyzed.length;
  const totalAnalyzed = historyCount + (targetMsg ? 1 : 0);

  const cardTone = isBypass ? 'bypass' : masked && analysis ? 'ready' : 'default';

  return (
    <section className="after" aria-label="O que acontece depois da entrega, em segundo plano">
      <div className="after__lead">
        <motion.span
          className="after__line"
          initial={play ? { scaleY: 0 } : false}
          animate={{ scaleY: 1 }}
          transition={{ duration: 0.4, ease }}
          aria-hidden="true"
        />
        <p>
          <strong>Depois da entrega</strong>, em segundo plano e sem atrasar o Pix:
        </p>
      </div>

      <div className="after__grid">
        <Card stage={laudo} index={0} play={play} tone={cardTone}>
          {!masked && <p className="after-card__muted">Nenhuma ameaça encontrada, então não há laudo a gerar.</p>}
          {masked && investigation.status === 'pending' && (
            <>
              <Skeleton lines={3} />
              <p className="after-card__muted">A IA de investigação está periciando a série de mensagens…</p>
            </>
          )}
          {masked && investigation.status === 'timeout' && (
            <p className="after-card__muted">O laudo ainda está em processamento. Consulte o Histórico em instantes.</p>
          )}
          {masked && analysis && !isBypass && (
            <>
              <div className="chips">
                <motion.span
                  className={`chip chip--crit-${analysis.criticidade}`}
                  initial={play ? { scale: 0.6, opacity: 0 } : false}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={spring.pop}
                >
                  Gravidade {CRITICALITY_LABEL[analysis.criticidade] || analysis.criticidade}
                </motion.span>
                <span className="chip">{categoryLabel(analysis.categoria)}</span>
                <span className="chip chip--accent" title="Total de mensagens avaliadas pelo Gemini nesta investigação">
                  <History size={12} aria-hidden="true" />
                  {historyCount > 0 ? `Série Temporal: ${totalAnalyzed} mensagens periciadas` : '1ª ocorrência investigada'}
                </span>
                {analysis.acao_imediata_recomendada && (
                  <span className="chip chip--danger">
                    <ShieldAlert size={12} aria-hidden="true" />
                    Intervenção Prioritária
                  </span>
                )}
              </div>

              <TypeReveal text={analysis.resumo_analise} play={play} />

              {/* Padrão Comportamental Identificado na Série Temporal */}
              {analysis.padrao_identificado && (
                <div className="after-card__pattern-box">
                  <div className="after-card__box-header">
                    <Activity size={13} aria-hidden="true" className="after-card__box-icon" />
                    <strong>Padrão Identificado na Série (até 10 mensagens):</strong>
                  </div>
                  <p className="after-card__box-text">{analysis.padrao_identificado}</p>
                </div>
              )}

              {/* Evidências Materiais Citadas pelo Modelo */}
              {Array.isArray(analysis.evidencias_citadas) && analysis.evidencias_citadas.length > 0 && (
                <div className="after-card__evidences-box">
                  <div className="after-card__box-header">
                    <SearchCheck size={13} aria-hidden="true" className="after-card__box-icon" />
                    <strong>Evidências Materiais Citadas no Laudo:</strong>
                  </div>
                  <div className="after-card__quote-list">
                    {analysis.evidencias_citadas.map((ev, i) => (
                      <span key={i} className="after-card__quote-badge">
                        <Quote size={10} aria-hidden="true" /> “{ev}”
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Recomendação Acionável para o Analista Humano */}
              {analysis.recomendacao_analista && (
                <div className="after-card__rec-box">
                  <div className="after-card__box-header">
                    <ShieldCheck size={13} aria-hidden="true" className="after-card__box-icon" />
                    <strong>Recomendação para o Analista de Fraudes:</strong>
                  </div>
                  <p className="after-card__box-text">{analysis.recomendacao_analista}</p>
                </div>
              )}

              {/* Acordeão Interativo para Inspecionar as Mensagens Avaliadas */}
              <div className="after-card__history-section">
                <button
                  type="button"
                  className="after-card__history-btn"
                  onClick={() => setShowHistory((prev) => !prev)}
                  aria-expanded={showHistory}
                >
                  <div className="after-card__history-btn-label">
                    <MessageSquare size={13} aria-hidden="true" />
                    <span>
                      <strong>Inspecionar mensagens periciadas</strong> ({totalAnalyzed} no contexto forense)
                    </span>
                  </div>
                  {showHistory ? <ChevronUp size={15} aria-hidden="true" /> : <ChevronDown size={15} aria-hidden="true" />}
                </button>

                {showHistory && (
                  <div className="after-card__history-list">
                    <div className="after-card__history-info">
                      <ShieldCheck size={12} aria-hidden="true" />
                      <span>Mensagens isoladas em tags XML com anonimização prévia de PII (LGPD).</span>
                    </div>

                    {historyAnalyzed.map((msg, idx) => (
                      <div key={idx} className="after-card__msg-row">
                        <span className="after-card__msg-tag">#{idx + 1} Histórico</span>
                        <span className="after-card__msg-content">{msg}</span>
                      </div>
                    ))}

                    {targetMsg && (
                      <div className="after-card__msg-row after-card__msg-row--target">
                        <span className="after-card__msg-tag after-card__msg-tag--target">
                          #{historyCount + 1} Atual (Alvo)
                        </span>
                        <span className="after-card__msg-content">{targetMsg}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="after-card__footer-meta">
                {typeof data?.timing?.gemini_ms === 'number' && (
                  <span className="after-card__muted">
                    Laudo pericial gerado em <strong>{fmtMs(data.timing.gemini_ms)}</strong>.
                  </span>
                )}
                <span className="after-card__guardrail-badge">
                  Guardrails: Tags XML &amp; Sanitização PII
                </span>
              </div>
            </>
          )}

          {masked && isBypass && (
            <div className="after-card__bypass-box">
              <div className="chips">
                <motion.span
                  className="chip chip--warn"
                  initial={play ? { scale: 0.8, opacity: 0 } : false}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={spring.pop}
                >
                  <AlertTriangle size={13} aria-hidden="true" />
                  Investigação em Bypass
                </motion.span>
                <span className="chip chip--bypass">API Gemini Indisponível</span>
              </div>

              <p className="after-card__text after-card__text--bypass">
                A chamada semântica à API do Google Gemini não pôde ser autenticada ou conectada. O sistema{' '}
                <strong>não utilizou aproximações nem fallback heurístico</strong>, operando em modo{' '}
                <strong>BYPASS transparente</strong>.
              </p>

              {(analysis?.bypass_reason || data?.bypass_reason) && (
                <p className="after-card__muted after-card__bypass-reason">
                  <strong>Motivo:</strong> {analysis?.bypass_reason || data?.bypass_reason}
                </p>
              )}

              <div className="after-card__bypass-shield">
                <ShieldCheck size={14} aria-hidden="true" />
                <span>
                  <strong>Proteção na borda garantida:</strong> O envio do Pix com ameaça foi bloqueado pelo Ollaya em menos de
                  15ms.
                </span>
              </div>
            </div>
          )}
        </Card>

        <Card stage={fichaStage} index={1} play={play} tone={ficha.blocked ? 'danger' : 'default'}>
          <DotMeter
            count={ficha.count}
            limit={ficha.limit}
            blocked={ficha.blocked}
            pendingNext={masked && investigation.status === 'pending'}
          />
          {ficha.blocked ? (
            <p className="after-card__text after-card__text--danger">
              <Lock size={14} aria-hidden="true" /> Conta com bloqueio cautelar aplicado pelo analista de fraudes.
            </p>
          ) : (
            <p className="after-card__muted">
              {ficha.count} ocorrência(s) acumulada(s). O bloqueio de conta é decisão do analista humano com base no laudo pericial.
            </p>
          )}
        </Card>
      </div>
    </section>
  );
}
