import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'motion/react';
import { Banknote, ShieldCheck } from 'lucide-react';
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

/** O texto se desfaz em fragmentos e é trocado pelo aviso padrão; o dinheiro segue direto. */
export function MessageSwap({ original, masked, amount, play }) {
  const words = useMemo(() => String(original || '').split(/\s+/).filter(Boolean), [original]);
  return (
    <div className="swap">
      <div className="swap__box">
        <span className="decode__label">O que foi digitado</span>
        <p className="swap__original">
          {words.map((w, i) => (
            <motion.span
              key={`${w}-${i}`}
              className="swap__word"
              initial={false}
              animate={
                play
                  ? { opacity: 0.18, y: (i % 3) * -3 - 2, filter: 'blur(3px)' }
                  : { opacity: 0.35, filter: 'blur(2px)' }
              }
              transition={{ delay: play ? 0.15 + i * 0.03 : 0, duration: 0.45, ease }}
            >
              {w}{' '}
            </motion.span>
          ))}
        </p>
      </div>
      <div className="swap__box swap__box--after">
        <span className="decode__label">O que chega a quem recebe</span>
        <motion.p
          className="swap__masked"
          initial={play ? { opacity: 0, y: 8 } : false}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: play ? 0.75 : 0, duration: dur.base, ease }}
        >
          <ShieldCheck size={16} aria-hidden="true" /> {masked}
        </motion.p>
      </div>
      <motion.div
        className="swap__money"
        initial={play ? { opacity: 0, x: -10 } : false}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: play ? 0.9 : 0, ...spring.soft }}
      >
        <Banknote size={16} aria-hidden="true" />{' '}
        {amount === null || amount === undefined ? 'O dinheiro' : formatBRL(amount)} segue direto para quem recebe, sem atraso.
      </motion.div>
    </div>
  );
}
