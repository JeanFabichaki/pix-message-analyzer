import React from 'react';
import { motion } from 'motion/react';
import { Brain, ClipboardList, Lock, AlertTriangle, ShieldCheck } from 'lucide-react';
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

export default function AfterDelivery({ masked, investigation, ficha, reduced }) {
  const play = !reduced;
  const data = investigation.data;
  const analysis = data?.analysis;
  const isBypass = Boolean(
    analysis?.bypassed || data?.bypassed || data?.status === 'BYPASS' || analysis?.categoria === 'bypass'
  );
  const [laudo, fichaStage] = ASYNC_STAGES;

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
              <p className="after-card__muted">A IA de investigação está lendo o caso…</p>
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
              </div>
              <TypeReveal text={analysis.resumo_analise} play={play} />
              {typeof data?.timing?.gemini_ms === 'number' && (
                <span className="after-card__muted">Laudo gerado em {fmtMs(data.timing.gemini_ms)}.</span>
              )}
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
                  <strong>Proteção na borda garantida:</strong> A mensagem ameaçadora foi retida pelo Ollaya em menos de
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
              <Lock size={14} aria-hidden="true" /> Limite atingido: a conta foi marcada como suspensa.
            </p>
          ) : (
            <p className="after-card__muted">
              Ao chegar a {ficha.limit} ocorrências, a conta de quem envia é marcada como suspensa.
            </p>
          )}
        </Card>
      </div>
    </section>
  );
}
