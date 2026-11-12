import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'motion/react';
import { Banknote, ShieldCheck, ShieldAlert, Lock, Ban, FileText } from 'lucide-react';
import CountUp from '../components/ui/CountUp';
import { dur, ease, spring } from '../motion/tokens';
import { formatBRL } from './scenarios';

const GLYPHS = 'abcdefghijklmnopqrstuvwxyz0123456789@$#%&';
const LEET = /([0-9@$!|_.*+€§ª])/;

function scramble(target, settled) {
  let out = '';
  for (let i = 0; i < target.length; i++) {
    const ch = target[i];
    if (i < settled || ch === ' ') out += ch;
    else out += GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
  }
  return out;
}

/** Mostra o texto disfarçado e o resolve, caractere a caractere, até a forma legível. */
export function DecodeText({ from, to, play }) {
  const [shown, setShown] = useState(play ? scramble(to, 0) : to);

  useEffect(() => {
    if (!play) {
      setShown(to);
      return undefined;
    }
    let settled = 0;
    const step = Math.max(1, Math.ceil(to.length / 16));
    const id = setInterval(() => {
      settled += step;
      if (settled >= to.length) {
        setShown(to);
        clearInterval(id);
      } else {
        setShown(scramble(to, settled));
      }
    }, 40);
    return () => clearInterval(id);
  }, [to, play]);

  const parts = useMemo(() => String(from).split(LEET), [from]);

  return (
    <div className="decode">
      <div className="decode__row">
        <span className="decode__label">Como foi enviado</span>
        <p className="decode__text decode__text--before">
          {parts.map((p, i) =>
            LEET.test(p) && p.length === 1 ? (
              <mark key={i} className="decode__leet">
                {p}
              </mark>
            ) : (
              <span key={i}>{p}</span>
            )
          )}
        </p>
      </div>
      <div className="decode__row">
        <span className="decode__label">Depois de desfeito</span>
        <p className="decode__text decode__text--after">{shown}</p>
      </div>
    </div>
  );
}

/** Medidor do quanto a IA considerou a mensagem arriscada. */
export function ScoreGauge({ score, limit = 0.4, play }) {
  const pct = Math.max(0, Math.min(1, Number(score) || 0));
  const over = pct >= limit;
  return (
    <div className="gauge">
      <div className="gauge__head">
        <span className="decode__label">Risco estimado pela IA</span>
        <CountUp value={Math.round(pct * 100)} suffix="%" className="gauge__value" duration={play ? 0.7 : 0} />
      </div>
      <div className="gauge__track">
        <motion.div
          className={`gauge__fill ${over ? 'gauge__fill--over' : ''}`}
          initial={play ? { scaleX: 0 } : false}
          animate={{ scaleX: pct }}
          transition={{ duration: 0.7, ease }}
        />
        <span className="gauge__limit" style={{ left: `${limit * 100}%` }}>
          <span className="gauge__limit-label">limite {Math.round(limit * 100)}%</span>
        </span>
      </div>
    </div>
  );
}

/** Régua do valor contra o limite da regra. */
export function AmountRuler({ amount, limit, play }) {
  const max = Math.max(limit * 1.6, Number(amount) * 1.15 || limit * 1.6);
  const limitPct = (limit / max) * 100;
  const amountPct = Math.min(100, ((Number(amount) || 0) / max) * 100);
  const over = Number(amount) > limit;
  return (
    <div className="ruler">
      <div className="ruler__track">
        <span className="ruler__zone" style={{ width: `${limitPct}%` }} />
        <span className="ruler__limit" style={{ left: `${limitPct}%` }}>
          <span className="ruler__limit-label">limite {formatBRL(limit)}</span>
        </span>
        <motion.span
          className={`ruler__dot ${over ? 'ruler__dot--over' : ''}`}
          initial={play ? { left: '0%' } : false}
          animate={{ left: `${amountPct}%` }}
          transition={{ ...spring.soft }}
        >
          <span className="ruler__dot-label num">{formatBRL(amount)}</span>
        </motion.span>
      </div>
    </div>
  );
}

/** Quando uma mensagem é reprovada, o conteúdo original é preservado para perícia. */
export function MessageSwap({ original, play }) {

  return (
    <div className="blocked-outcome" role="alert" aria-label="Notificação de mensagem reprovada">
      {/* 1. Alerta Principal de Segurança: Alto contraste, sem verde */}
      <motion.div
        className="blocked-outcome__card"
        initial={play ? { opacity: 0, y: 8 } : false}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: play ? 0.2 : 0, duration: dur.base, ease }}
      >
        <div className="blocked-outcome__head">
          <div className="blocked-outcome__icon" aria-hidden="true">
            <ShieldAlert size={24} />
          </div>
          <div className="blocked-outcome__headline">
            <div className="blocked-outcome__title-row">
              <h4 className="blocked-outcome__title">Mensagem reprovada</h4>
              <span className="blocked-outcome__badge">
                <Ban size={12} aria-hidden="true" /> Conteúdo não entregue
              </span>
            </div>
            <p className="blocked-outcome__desc">
              A mensagem foi reprovada pelo sistema de segurança por conter linguagem de intimidação, coação ou ameaça.
            </p>
          </div>
        </div>

        {/* 2. Resumo Claro para o Usuário Comum */}
        <div className="blocked-outcome__grid">
          <div className="blocked-outcome__item blocked-outcome__item--safe">
            <div className="blocked-outcome__item-icon">
              <ShieldCheck size={18} aria-hidden="true" />
            </div>
            <div className="blocked-outcome__item-body">
              <span className="blocked-outcome__item-title">Conteúdo preservado para análise</span>
              <p className="blocked-outcome__item-text">
                O conteúdo original fica disponível para investigação e análise do operador.
              </p>
            </div>
          </div>

          <div className="blocked-outcome__item blocked-outcome__item--not-delivered">
            <div className="blocked-outcome__item-icon">
              <Ban size={18} aria-hidden="true" />
            </div>
            <div className="blocked-outcome__item-body">
              <span className="blocked-outcome__item-title">Mensagem não entregue</span>
              <p className="blocked-outcome__item-text">
                A mensagem agressiva foi descartada da entrega. Nada chegou ao destinatário.
              </p>
            </div>
          </div>
        </div>
      </motion.div>

      {/* 3. Evidência Retida para Perícia e Auditoria */}
      <motion.div
        className="blocked-outcome__evidence"
        initial={play ? { opacity: 0, y: 8 } : false}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: play ? 0.38 : 0, duration: dur.base, ease }}
      >
        <div className="blocked-outcome__evidence-header">
          <div className="blocked-outcome__evidence-label-group">
            <FileText size={14} aria-hidden="true" className="blocked-outcome__evidence-icon" />
            <span className="blocked-outcome__evidence-label">
              Mensagem retida para auditoria pericial e compliance
            </span>
          </div>
          <span className="blocked-outcome__evidence-tag">Ameaça Interceptada</span>
        </div>
        <p className="blocked-outcome__original-text">“{original}”</p>
      </motion.div>
    </div>
  );
}
