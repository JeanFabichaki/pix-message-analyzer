import React, { useEffect, useState } from 'react';
import { Cpu } from 'lucide-react';
import { getActiveEngine, getEngines, setActiveEngine } from '../services/api';

const FALLBACK = [
  { id: 'laya_tuned', label: 'Decision Model treinado', available: true },
  { id: 'laya', label: 'Decision Model original', available: true },
];
const MODEL_LABELS = Object.fromEntries(FALLBACK.map(({ id, label }) => [id, label]));

/** Alterna o Decision Model original ou treinado, preservando os identificadores da API. */
export default function EngineSwitch({ disabled: busy = false }) {
  const [engine, setEngine] = useState(getActiveEngine());
  const [engines, setEngines] = useState(FALLBACK);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const data = await getEngines();
      if (!cancelled && data?.engines) setEngines(data.engines);
    };
    load();
    const id = setInterval(load, 15000);
    const onChange = (e) => setEngine(e.detail);
    window.addEventListener('pix-engine-changed', onChange);
    return () => {
      cancelled = true;
      clearInterval(id);
      window.removeEventListener('pix-engine-changed', onChange);
    };
  }, []);

  return (
    <div className="engine-switch" role="radiogroup" aria-label="Modelo de triagem das mensagens">
      <Cpu size={14} aria-hidden="true" className="engine-switch__icon" />
      {engines.map((e) => {
        const selected = engine === e.id;
        const disabled = busy || (!e.available && !selected);
        const label = MODEL_LABELS[e.id] || String(e.label).replace(/\b(?:ollaya|laya)\b/gi, 'Decision Model');
        return (
          <button
            key={e.id}
            type="button"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            className={`engine-switch__opt ${selected ? 'is-active' : ''} ${!e.available ? 'is-offline' : ''}`}
            onClick={() => setActiveEngine(e.id)}
            title={
              e.available
                ? (e.description || label).replace(/\b(?:ollaya|laya)\b/gi, 'Decision Model')
                : `${label} está fora do ar.`
            }
          >
            {label}
            {!e.available && <span className="engine-switch__off"> · offline</span>}
          </button>
        );
      })}
    </div>
  );
}
