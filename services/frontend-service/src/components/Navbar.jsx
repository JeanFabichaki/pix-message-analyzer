import React, { useEffect, useState } from 'react';
import { motion } from 'motion/react';
import { Activity, GitCompare, History, Route, ShieldCheck, Sparkles, TriangleAlert } from 'lucide-react';
import { getGatewayHealth } from '../services/api';
import EngineSwitch from './EngineSwitch';
import { useMotionPrefs } from '../motion/MotionProvider';
import { spring } from '../motion/tokens';

export const TABS = [
  { id: 'journey', label: 'Jornada', Icon: Route },
  { id: 'live', label: 'Ao vivo', Icon: Activity },
  { id: 'history', label: 'Histórico', Icon: History },
  { id: 'compare', label: 'Comparar', Icon: GitCompare },
];

export default function Navbar({ activeTab, onChange }) {
  const { reduced, manualReduced, toggle } = useMotionPrefs();
  const [health, setHealth] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const check = async () => {
      const h = await getGatewayHealth();
      if (!cancelled) setHealth(h);
    };
    check();
    const id = setInterval(check, 10000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const online = health === null ? null : health.reachable;
  const aiDown = Boolean(health?.reachable && health.ollaya?.status === 'degraded');
  const pill = online === null ? ['', 'Verificando…'] : !online ? ['status--off', 'Gateway fora do ar'] : aiDown ? ['status--warn', 'IA rápida fora do ar'] : ['status--on', 'Gateway online'];

  return (
    <>
      <a href="#main-content" className="skip-link">
        Pular para o conteúdo principal
      </a>
      <div className="navbar-shell">
        <header className="navbar" role="banner">
          <div className="brand">
            <span className="brand__icon" aria-hidden="true">
              <ShieldCheck size={20} strokeWidth={2.4} />
            </span>
            <div>
              <h1 className="brand__title">Pix Guard</h1>
              <p className="brand__sub">Como uma mensagem de Pix é verificada antes de chegar</p>
            </div>
          </div>

          <nav aria-label="Telas">
            <div className="tabs" role="tablist">
              {TABS.map(({ id, label, Icon }, i) => {
                const active = activeTab === id;
                return (
                  <button
                    key={id}
                    id={`tab-${id}`}
                    role="tab"
                    type="button"
                    aria-selected={active}
                    aria-controls={`panel-${id}`}
                    className={`tab ${active ? 'is-active' : ''}`}
                    onClick={() => onChange(id)}
                  >
                    {active && <motion.span layoutId="tab-pill" className="tab__pill" transition={spring.soft} />}
                    <span className="tab__content">
                      <Icon size={16} aria-hidden="true" />
                      <span>{label}</span>
                      <kbd className="tab__key" aria-hidden="true">
                        {i + 1}
                      </kbd>
                    </span>
                  </button>
                );
              })}
            </div>
          </nav>

          <div className="navbar__right">
            <EngineSwitch />
            <button
              type="button"
              className="btn btn--ghost btn--xs"
              onClick={toggle}
              aria-pressed={manualReduced}
              title="Reduz as animações, útil em projetores e para quem prefere menos movimento"
            >
              <Sparkles size={14} aria-hidden="true" /> Animações: {reduced ? 'reduzidas' : 'ligadas'}
            </button>
            <span className={`status ${pill[0]}`} role="status">
              <span className="status__dot" aria-hidden="true" />
              {pill[1]}
            </span>
          </div>
        </header>
      </div>
      {aiDown && (
        <div className="alert-banner" role="alert">
          <TriangleAlert size={18} aria-hidden="true" />
          <div>
            <strong>A IA rápida (Ollaya) não está respondendo.</strong> Os Pix estão sendo aprovados <u>sem análise</u>{' '}
            até ela voltar.
            {health.ollaya.last_error && <span className="alert-banner__detail"> Detalhe: {health.ollaya.last_error}</span>}
            {/MODEL_NOT_FOUND|not found/i.test(health.ollaya.last_error || '') && (
              <span className="alert-banner__detail"> Rode <code>make pull-model</code> para baixar o modelo.</span>
            )}
          </div>
        </div>
      )}
    </>
  );
}
