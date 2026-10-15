import React from 'react';
import { motion } from 'motion/react';
import { Lock } from 'lucide-react';
import { spring } from '../../motion/tokens';

/** ●●●○○ — ocorrências de quem enviou. O próximo ponto pulsa enquanto o laudo ainda não chegou. */
export default function DotMeter({ count = 0, limit = 5, blocked = false, pendingNext = false }) {
  const dots = Array.from({ length: limit }, (_, i) => i);
  return (
    <div className="dot-meter" role="img" aria-label={`${count} de ${limit} ocorrências${blocked ? ', conta suspensa' : ''}`}>
      <div className="dot-meter__dots">
        {dots.map((i) => {
          const filled = i < count;
          const isNext = pendingNext && i === count;
          return (
            <motion.span
              key={i}
              className={`dot ${filled ? (blocked ? 'dot--danger' : 'dot--on') : ''} ${isNext ? 'dot--pending' : ''}`}
              initial={false}
              animate={{ scale: filled ? [1, 1.35, 1] : 1 }}
              transition={{ ...spring.pop, delay: filled ? i * 0.06 : 0 }}
            />
          );
        })}
        {blocked && (
          <motion.span
            className="dot-meter__lock"
            initial={{ scale: 0, rotate: -25 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={spring.pop}
          >
            <Lock size={14} strokeWidth={2.6} aria-hidden="true" />
          </motion.span>
        )}
      </div>
      <span className="dot-meter__label num">
        {count} de {limit}
      </span>
    </div>
  );
}
