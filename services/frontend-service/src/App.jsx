import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar';
import Screen1Simulator from './components/Screen1Simulator';
import Screen2Matrix from './components/Screen2Matrix';
import Screen3Audit from './components/Screen3Audit';

export default function App() {
  const [activeTab, setActiveTab] = useState('simulator');
  const [announcement, setAnnouncement] = useState('');

  const tabTitles = {
    simulator: 'Tela 1: Simulador de Transferência & Pipeline de Análise carregada',
    matrix: 'Tela 2: Telemetria de Alta Vazão carregada',
    audit: 'Tela 3: Painel de Auditoria & Governança carregada',
  };

  const handleTabChange = (newTab) => {
    setActiveTab(newTab);
    setAnnouncement(tabTitles[newTab] || '');
  };

  useEffect(() => {
    const handleKeyDown = (e) => {
      const tag = document.activeElement?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      if (e.key === '1') handleTabChange('simulator');
      else if (e.key === '2') handleTabChange('matrix');
      else if (e.key === '3') handleTabChange('audit');
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Live Region for Screen Reader Announcements */}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement}
      </div>

      <Navbar activeTab={activeTab} setActiveTab={handleTabChange} />

      <main
        id="main-content"
        tabIndex={-1}
        style={{ flex: 1, paddingBottom: '3rem', outline: 'none' }}
      >
        <div
          id="panel-simulator"
          role="tabpanel"
          aria-labelledby="tab-simulator"
          hidden={activeTab !== 'simulator'}
        >
          {activeTab === 'simulator' && <Screen1Simulator />}
        </div>

        <div
          id="panel-matrix"
          role="tabpanel"
          aria-labelledby="tab-matrix"
          hidden={activeTab !== 'matrix'}
        >
          {activeTab === 'matrix' && <Screen2Matrix />}
        </div>

        <div
          id="panel-audit"
          role="tabpanel"
          aria-labelledby="tab-audit"
          hidden={activeTab !== 'audit'}
        >
          {activeTab === 'audit' && <Screen3Audit />}
        </div>
      </main>

      <footer
        role="contentinfo"
        style={{
          borderTop: '1px solid var(--border-subtle)',
          padding: '1rem 2rem',
          textAlign: 'center',
          fontSize: '0.75rem',
          color: 'var(--text-muted)',
          background: 'var(--bg-primary)',
          fontFamily: 'var(--font-mono)',
        }}
      >
        <span>Pix Guard • Defesa Híbrida: Ollaya (laya &lt;15ms) + Google Gemini 2.5 Flash Structured Outputs</span>
      </footer>
    </div>
  );
}
