import React, { useRef } from 'react';
import { ShieldCheck, Smartphone, Activity, FileText } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab }) {
  const tabsRef = useRef({});

  const handleKeyDown = (e, currentTab) => {
    const tabs = ['simulator', 'matrix', 'audit'];
    const currentIndex = tabs.indexOf(currentTab);

    let nextIndex = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      nextIndex = (currentIndex + 1) % tabs.length;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextIndex = 0;
    } else if (e.key === 'End') {
      e.preventDefault();
      nextIndex = tabs.length - 1;
    }

    if (nextIndex !== null) {
      const nextTab = tabs[nextIndex];
      setActiveTab(nextTab);
      tabsRef.current[nextTab]?.focus();
    }
  };

  return (
    <>
      <a href="#main-content" className="skip-link">
        Pular para o conteúdo principal
      </a>
      <div className="navbar-shell">
        <header className="navbar-container" role="banner">
          <div className="brand-badge">
            <div className="brand-icon-wrapper" aria-hidden="true">
              <ShieldCheck size={20} color="var(--color-accent)" strokeWidth={2.4} />
            </div>
            <div>
              <h1 className="brand-title">Pix Guard</h1>
              <p className="brand-subtitle">Triagem Híbrida Ollaya (&lt;15ms) + Gemini 2.5 Flash</p>
            </div>
          </div>

          <nav aria-label="Painel de navegação de telas">
            <div className="nav-tabs" role="tablist" aria-label="Etapas do fluxo do sistema">
              <button
                ref={(el) => (tabsRef.current['simulator'] = el)}
                id="tab-simulator"
                role="tab"
                aria-selected={activeTab === 'simulator'}
                aria-controls="panel-simulator"
                tabIndex={activeTab === 'simulator' ? 0 : -1}
                className={`nav-tab-btn ${activeTab === 'simulator' ? 'active' : ''}`}
                onClick={() => setActiveTab('simulator')}
                onKeyDown={(e) => handleKeyDown(e, 'simulator')}
              >
                <Smartphone size={15} aria-hidden="true" />
                <span>1. Simulador & Pipeline</span>
              </button>

              <button
                ref={(el) => (tabsRef.current['matrix'] = el)}
                id="tab-matrix"
                role="tab"
                aria-selected={activeTab === 'matrix'}
                aria-controls="panel-matrix"
                tabIndex={activeTab === 'matrix' ? 0 : -1}
                className={`nav-tab-btn ${activeTab === 'matrix' ? 'active' : ''}`}
                onClick={() => setActiveTab('matrix')}
                onKeyDown={(e) => handleKeyDown(e, 'matrix')}
              >
                <Activity size={15} aria-hidden="true" />
                <span>2. Telemetria de Vazão</span>
              </button>

              <button
                ref={(el) => (tabsRef.current['audit'] = el)}
                id="tab-audit"
                role="tab"
                aria-selected={activeTab === 'audit'}
                aria-controls="panel-audit"
                tabIndex={activeTab === 'audit' ? 0 : -1}
                className={`nav-tab-btn ${activeTab === 'audit' ? 'active' : ''}`}
                onClick={() => setActiveTab('audit')}
                onKeyDown={(e) => handleKeyDown(e, 'audit')}
              >
                <FileText size={15} aria-hidden="true" />
                <span>3. Auditoria & Risco</span>
              </button>
            </div>
          </nav>

          <div
            className="status-indicator"
            role="status"
            aria-live="polite"
            aria-label="Status do motor de defesa: Defesa Ativa em Borda e Nuvem"
          >
            <span className="pulsing-dot" aria-hidden="true"></span>
            <span>Defesa Ativa</span>
          </div>
        </header>
      </div>
    </>
  );
}
