import React, { useEffect, useRef, useState } from 'react';
import { animate } from 'motion/react';
import { ease } from '../../motion/tokens';
import { useMotionPrefs } from '../../motion/MotionProvider';

/** Número que sobe contando até o valor real. Largura estável (tabular-nums) para não "tremer". */
export default function CountUp({ value, decimals = 0, duration = 0.6, prefix = '', suffix = '', className = '', locale = 'pt-BR' }) {
  const { reduced } = useMotionPrefs();
  const [shown, setShown] = useState(Number.isFinite(value) ? value : 0);
  const fromRef = useRef(Number.isFinite(value) ? value : 0);

  useEffect(() => {
    if (!Number.isFinite(value)) return undefined;
    if (reduced) {
      setShown(value);
      fromRef.current = value;
      return undefined;
    }
    const controls = animate(fromRef.current, value, {
      duration,
      ease,
      onUpdate: (v) => {
        fromRef.current = v;
        setShown(v);
      },
    });
    return () => controls.stop();
  }, [value, duration, reduced]);

  if (!Number.isFinite(value)) return <span className={`num ${className}`}>—</span>;

  const text = shown.toLocaleString(locale, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return (
    <span className={`num ${className}`}>
      {prefix}
      {text}
      {suffix}
    </span>
  );
}
