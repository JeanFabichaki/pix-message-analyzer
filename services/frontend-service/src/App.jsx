import React, { useCallback, useEffect, useState } from 'react';
import { motion } from 'motion/react';
import Navbar, { TABS } from './components/Navbar';
import Screen1Journey from './components/Screen1Journey';
import ScreenLive from './components/ScreenLive';
import ScreenCompare from './components/ScreenCompare';
import ScreenOperator from './components/ScreenOperator';
import { dur, ease } from './motion/tokens';
import './presentation.css';

export default function App() {
  const presentation = new URLSearchParams(window.location.search).get('interface') === 'v2';
  const [tab, setTab] = useState('journey');
  const [replay, setReplay] = useState(null);
  const [operatorCase, setOperatorCase] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [simulatedBlocks, setSimulatedBlocks] = useState({});

  const recordTransaction = useCallback((payload, source) => {
    setTransactions((previous) => [
      ...previous.filter((item) => item.transaction_id !== payload.transaction_id),
      { ...payload, blocked: Boolean(source.blocked || source.original_masked || source.was_masked || source.status === 'BLOCKED'), created_at: new Date().toISOString() },
    ]);
  }, []);

  const openOperator = useCallback((context) => {
    setOperatorCase(context);
    setTab('operator');
    window.scrollTo({ top: 0 });
    requestAnimationFrame(() => document.getElementById('operator-title')?.focus());
  }, []);

  const changeSimulatedBlock = useCallback((senderId, decision) => {
    setSimulatedBlocks((previous) => ({ ...previous, [senderId]: decision }));
  }, []);

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

  // Um Pix escolhido no Ao vivo é reproduzido na Jornada.
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
    <div className={`app ${presentation ? 'app--presentation' : ''}`}>
      <Navbar activeTab={tab} onChange={setTab} presentation={presentation} />
      <main id="main-content" tabIndex={-1} className="app__main">
        {panel('journey', <Screen1Journey presentation={presentation} replay={replay} onReplayConsumed={() => setReplay(null)} active={tab === 'journey'} onOpenOperator={openOperator} onTransaction={recordTransaction} />)}
        {panel('live', <ScreenLive active={tab === 'live'} onInspect={handleInspect} />)}
        {panel('compare', <ScreenCompare active={tab === 'compare'} />)}
        {panel('operator', <ScreenOperator key={operatorCase?.run.txId || 'empty'} context={operatorCase} active={tab === 'operator'} transactions={transactions} simulatedBlock={simulatedBlocks[operatorCase?.sender.id]} onSimulateBlock={changeSimulatedBlock} onBack={() => setTab('journey')} />)}
      </main>
      {tab !== 'operator' && <footer className="app__footer" role="contentinfo">
        <span>
          Prova de conceito · Regra de análise: mensagens de Pix de até R$ 10,00 · Teclas 1 a 4 trocam de
          tela
        </span>
      </footer>}
    </div>
  );
}
