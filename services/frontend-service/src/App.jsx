import React, { useCallback, useEffect, useState } from 'react';
import { motion } from 'motion/react';
import Navbar, { TABS } from './components/Navbar';
import Screen1Journey from './components/Screen1Journey';
import ScreenLive from './components/ScreenLive';
import ScreenHistory from './components/ScreenHistory';
import ScreenCompare from './components/ScreenCompare';
import { dur, ease } from './motion/tokens';

export default function App() {
  const [tab, setTab] = useState('journey');
  const [replay, setReplay] = useState(null);

  useEffect(() => {
    const onKey = (e) => {
      const tag = document.activeElement?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const idx = Number(e.key) - 1;
      if (Number.isInteger(idx) && TABS[idx]) setTab(TABS[idx].id);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Um Pix escolhido no Ao vivo ou no Histórico é reproduzido na Jornada.
  const handleInspect = useCallback((payload) => {
    setReplay(payload);
    setTab('journey');
  }, []);

  const panel = (id, node) => (
    <motion.div
      key={id}
      id={`panel-${id}`}
      role="tabpanel"
      aria-labelledby={`tab-${id}`}
      hidden={tab !== id}
      initial={false}
      animate={tab === id ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
      transition={{ duration: dur.base, ease }}
    >
      {node}
    </motion.div>
  );

  return (
    <div className="app">
      <Navbar activeTab={tab} onChange={setTab} />
      <main id="main-content" tabIndex={-1} className="app__main">
        {panel('journey', <Screen1Journey replay={replay} onReplayConsumed={() => setReplay(null)} active={tab === 'journey'} />)}
        {panel('live', <ScreenLive active={tab === 'live'} onInspect={handleInspect} />)}
        {panel('history', <ScreenHistory active={tab === 'history'} onInspect={handleInspect} />)}
        {panel('compare', <ScreenCompare active={tab === 'compare'} />)}
      </main>
      <footer className="app__footer" role="contentinfo">
        <span>
          Pix Guard · prova de conceito · Regra de análise: mensagens de Pix de até R$ 10,00 · Teclas 1 a 4 trocam de
          tela
        </span>
      </footer>
    </div>
  );
}
