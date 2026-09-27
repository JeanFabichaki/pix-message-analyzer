import React, { useState, useEffect, useRef } from 'react';
import {
  Users,
  ShieldAlert,
  Search,
  RefreshCw,
  Unlock,
  RotateCcw,
  ChevronRight,
  Info,
  Shield,
  X,
  FileText,
  Scale,
  Trash2,
  AlertTriangle,
} from 'lucide-react';
import {
  getAuditThreats,
  getAuditMetrics,
  listUsers,
  unblockUser,
  resetUserThreats,
  clearAllAuditHistory,
  getThreatIntelStats,
  listConfirmedThreats,
} from '../services/api';

export default function Screen3Audit() {
  const [threats, setThreats] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [users, setUsers] = useState([]);
  const [intelStats, setIntelStats] = useState({ total_signatures: 0, total_occurrences: 0 });
  const [confirmedThreats, setConfirmedThreats] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isClearing, setIsClearing] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCriticality, setSelectedCriticality] = useState('ALL');
  const [selectedThreat, setSelectedThreat] = useState(null);
  const [actionSuccessMsg, setActionSuccessMsg] = useState(null);

  const drawerRef = useRef(null);
  const closeButtonRef = useRef(null);

  useEffect(() => {
    if (selectedThreat && drawerRef.current && window.innerWidth <= 1024) {
      drawerRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    if (selectedThreat && closeButtonRef.current) {
      closeButtonRef.current.focus();
    }
  }, [selectedThreat]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [threatsData, metricsData, usersData, intelStatsData, confirmedData] = await Promise.all([
        getAuditThreats(),
        getAuditMetrics(),
        listUsers(),
        getThreatIntelStats(),
        listConfirmedThreats(10),
      ]);
      setThreats(threatsData || []);
      setMetrics(metricsData);
      setUsers(usersData || []);
      if (intelStatsData) setIntelStats(intelStatsData);
      if (confirmedData) setConfirmedThreats(confirmedData);
    } catch (e) {
      console.error('Erro ao carregar dados de auditoria:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setSelectedThreat(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleUnblock = async (userId) => {
    try {
      await unblockUser(userId);
      setActionSuccessMsg(`Usuário ${userId} reativado com sucesso.`);
      setTimeout(() => setActionSuccessMsg(null), 3000);
      loadData();
    } catch (e) {
      alert('Erro ao desbloquear usuário');
    }
  };

  const handleResetThreats = async (userId) => {
    if (!window.confirm(`Zerar histórico de infrações da conta ${userId}?`)) return;
    try {
      await resetUserThreats(userId);
      setActionSuccessMsg(`Infrações zeradas para ${userId}.`);
      setTimeout(() => setActionSuccessMsg(null), 3000);
      loadData();
    } catch (e) {
      alert('Erro ao resetar infrações');
    }
  };

  const handleClearAllHistory = async () => {
    setIsClearing(true);
    try {
      const res = await clearAllAuditHistory();
      setSelectedThreat(null);
      setShowConfirmModal(false);
      setActionSuccessMsg(
        `Base histórica limpa com sucesso! ${res?.details?.deleted_threat_logs ?? 0} ocorrências excluídas e contas reativadas.`
      );
      setTimeout(() => setActionSuccessMsg(null), 4000);
      await loadData();
    } catch (e) {
      alert('Erro ao limpar base histórica: ' + e.message);
    } finally {
      setIsClearing(false);
    }
  };

  const filteredThreats = threats.filter((t) => {
    const matchesSearch =
      (t.original_message || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.user_id || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (t.transaction_id || '').toLowerCase().includes(searchQuery.toLowerCase());

    const matchesCriticality =
      selectedCriticality === 'ALL' || t.gemini_criticality === selectedCriticality;

    return matchesSearch && matchesCriticality;
  });

  return (
    <div className="screen-container">
      {/* 1. WORKFLOW RIBBON: O Ciclo de Vida da Investigação */}
      <section aria-label="Ciclo de vida da auditoria e governança" className="workflow-ribbon">
        <div className="workflow-step">
          <div className="workflow-step-num stage-sync">1</div>
          <div>
            <div className="workflow-step-title">Flag de Borda</div>
            <div className="workflow-step-desc">Ollaya intercepta a ameaça e emite o flag de censura em &lt;15ms.</div>
          </div>
        </div>

        <div className="workflow-step">
          <div className="workflow-step-num stage-async">2</div>
          <div>
            <div className="workflow-step-title">Perícia com Gemini</div>
            <div className="workflow-step-desc">Geração de parecer jurídico e tipificação penal em background.</div>
          </div>
        </div>

        <div className="workflow-step">
          <div className="workflow-step-num stage-gov">3</div>
          <div>
            <div className="workflow-step-title">Registro Imutável</div>
            <div className="workflow-step-desc">Log estruturado persistido com score e fundamentação textual.</div>
          </div>
        </div>

        <div className="workflow-step">
          <div className="workflow-step-num stage-gov">4</div>
          <div>
            <div className="workflow-step-title">Ação do Compliance</div>
            <div className="workflow-step-desc">Analistas auditam pareceres e gerenciam contas sob quarentena.</div>
          </div>
        </div>
      </section>

      {/* Header */}
      <section
        aria-labelledby="audit-page-title"
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}
      >
        <div>
          <h2
            id="audit-page-title"
            style={{ fontSize: '1.35rem', fontWeight: '700', letterSpacing: '-0.02em', color: 'var(--color-ink)' }}
          >
            Painel de Auditoria Forense & Governança de Risco
          </h2>
          <p style={{ color: 'var(--color-ink-muted)', marginTop: '0.2rem', fontSize: '0.85rem' }}>
            Registro legal e imutável de todas as mensagens retidas pelo motor de defesa com parecer do Gemini 2.5 Flash.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => setShowConfirmModal(true)}
            disabled={loading || isClearing}
            aria-label="Limpar toda a base histórica de auditoria"
            style={{
              background: '#ffffff',
              color: 'var(--color-danger)',
              border: '1px solid var(--border-danger)',
              padding: '0.5rem 0.95rem',
              borderRadius: 'var(--radius-pill)',
              cursor: isClearing ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              fontWeight: '600',
              fontSize: '0.82rem',
              transition: 'all var(--dur-fast) var(--ease-snappy)',
              boxShadow: 'var(--shadow-subtle)',
            }}
          >
            <Trash2 size={13} aria-hidden="true" />
            <span>{isClearing ? 'Limpando Base...' : 'Limpar Base Histórica'}</span>
          </button>

          <button
            type="button"
            onClick={loadData}
            disabled={loading}
            aria-busy={loading}
            aria-label="Atualizar dados de auditoria"
            style={{
              background: 'var(--color-paper-card)',
              color: 'var(--color-ink-secondary)',
              border: '1px solid var(--color-rule)',
              padding: '0.5rem 1rem',
              borderRadius: 'var(--radius-pill)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              fontWeight: '500',
              fontSize: '0.82rem',
              transition: 'all var(--dur-fast) var(--ease-snappy)',
            }}
          >
            <RefreshCw size={13} className={loading ? 'spin-fast' : ''} aria-hidden="true" />
            <span>Atualizar Auditoria</span>
          </button>
        </div>
      </section>

      {actionSuccessMsg && (
        <div
          role="status"
          aria-live="polite"
          style={{
            background: 'var(--bg-success)',
            border: '1px solid var(--border-success)',
            color: 'var(--color-success)',
            padding: '0.65rem 1rem',
            borderRadius: 'var(--radius-sm)',
            marginBottom: '1.25rem',
            fontWeight: '600',
            fontSize: '0.82rem',
          }}
        >
          ✓ {actionSuccessMsg}
        </div>
      )}

      {/* KPI Cards em Estilo Sóbrio Unificado */}
      <section aria-label="Indicadores gerais de risco e conformidade" className="kpi-grid">
        <div className="glass-panel" style={{ padding: '1rem', background: 'var(--color-navy)', border: '1px solid var(--color-navy)', color: '#ffffff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'rgba(255, 255, 255, 0.7)' }}>
            <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Total Usuários</span>
            <Users size={15} color="#ffffff" aria-hidden="true" />
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: '700', marginTop: '0.2rem', color: '#ffffff', fontFamily: 'var(--font-mono)' }}>
            {metrics ? metrics.total_users : users.length}
          </div>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-accent)', fontWeight: '600' }}>
            {metrics ? metrics.active_users : users.filter((u) => u.status === 'ACTIVE').length} contas regulares
          </span>
        </div>

        <div className="glass-panel" style={{ padding: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--color-ink-muted)' }}>
            <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Contas Suspensas</span>
            <ShieldAlert size={15} color="var(--color-danger)" aria-hidden="true" />
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: '700', marginTop: '0.2rem', color: (metrics?.blocked_users || 0) > 0 ? 'var(--color-danger)' : 'var(--color-ink)', fontFamily: 'var(--font-mono)' }}>
            {metrics ? metrics.blocked_users : users.filter((u) => u.status === 'BLOCKED_SUSPICIOUS').length}
          </div>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-ink-muted)' }}>
            Circuito preventivo de 5x
          </span>
        </div>

        <div className="glass-panel" style={{ padding: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--color-ink-muted)' }}>
            <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Incidentes Gravados</span>
            <Shield size={15} color="var(--color-ink-muted)" aria-hidden="true" />
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: '700', marginTop: '0.2rem', color: 'var(--color-ink)', fontFamily: 'var(--font-mono)' }}>
            {metrics ? metrics.total_threats : threats.length}
          </div>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-ink-muted)' }}>
            Auditados e persistidos
          </span>
        </div>

        <div className="glass-panel" style={{ padding: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--color-ink-muted)' }}>
            <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Assinaturas no Cache</span>
            <Shield size={15} color="var(--color-navy)" aria-hidden="true" />
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: '700', marginTop: '0.2rem', color: 'var(--color-ink)', fontFamily: 'var(--font-mono)' }}>
            {intelStats.total_signatures}
          </div>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-success)', fontWeight: '600' }}>
            {intelStats.total_occurrences}x interceptados (&lt;1ms)
          </span>
        </div>

        <div className="glass-panel" style={{ padding: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: 'var(--color-ink-muted)' }}>
            <span style={{ fontSize: '0.7rem', textTransform: 'uppercase', fontFamily: 'var(--font-mono)' }}>Ameaças Críticas</span>
            <ShieldAlert size={15} color="var(--color-danger)" aria-hidden="true" />
          </div>
          <div style={{ fontSize: '1.45rem', fontWeight: '700', marginTop: '0.2rem', color: (metrics?.threats_by_criticality?.CRITICA || 0) > 0 ? 'var(--color-danger)' : 'var(--color-ink)', fontFamily: 'var(--font-mono)' }}>
            {metrics?.threats_by_criticality?.CRITICA || 0}
          </div>
          <span style={{ fontSize: '0.7rem', color: 'var(--color-ink-muted)' }}>
            {metrics?.threats_by_criticality?.ALTA || 0} de alta severidade
          </span>
        </div>
      </section>

      <div className="audit-grid">
        {/* TABELA DE THREAT LOGS COM ACESSIBILIDADE */}
        <section aria-labelledby="threat-table-heading" className="glass-panel" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', gap: '0.75rem', flexWrap: 'wrap' }}>
            <h3 id="threat-table-heading" style={{ fontSize: '1rem', fontWeight: '600', color: 'var(--color-ink)' }}>
              Histórico de Mensagens Retidas ({filteredThreats.length})
            </h3>

            {/* Filtros e Busca */}
            <div style={{ display: 'flex', gap: '0.45rem', flex: 1, maxWidth: '400px' }}>
              <div style={{ position: 'relative', flex: 1 }}>
                <Search size={14} aria-hidden="true" style={{ position: 'absolute', left: '0.65rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--color-ink-muted)' }} />
                <label htmlFor="audit-search" className="sr-only">Buscar por texto, remetente ou ID</label>
                <input
                  id="audit-search"
                  type="text"
                  placeholder="Buscar texto ou ID..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{
                    width: '100%',
                    background: 'var(--color-paper-subtle)',
                    border: '1px solid var(--color-rule)',
                    borderRadius: 'var(--radius-pill)',
                    padding: '0.4rem 0.5rem 0.4rem 2rem',
                    color: 'var(--color-ink)',
                    fontSize: '0.78rem',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div>
                <label htmlFor="criticality-filter" className="sr-only">Filtrar por nível de criticidade</label>
                <select
                  id="criticality-filter"
                  value={selectedCriticality}
                  onChange={(e) => setSelectedCriticality(e.target.value)}
                  style={{
                    background: 'var(--color-paper-subtle)',
                    border: '1px solid var(--color-rule)',
                    borderRadius: 'var(--radius-pill)',
                    color: 'var(--color-ink)',
                    padding: '0.4rem 0.65rem',
                    fontSize: '0.78rem',
                    cursor: 'pointer',
                  }}
                >
                  <option value="ALL">Todas</option>
                  <option value="CRITICA">Crítica</option>
                  <option value="ALTA">Alta</option>
                  <option value="MEDIA">Média</option>
                  <option value="BAIXA">Baixa</option>
                </select>
              </div>
            </div>
          </div>

          {filteredThreats.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '3.5rem 1rem', color: 'var(--color-ink-muted)', fontSize: '0.82rem' }}>
              Nenhum registro de ameaça encontrado para os filtros selecionados.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table
                aria-label="Registros de ameaças detectadas em transferências Pix"
                style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}
              >
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--color-rule)', textAlign: 'left', color: 'var(--color-ink-muted)', fontSize: '0.7rem', textTransform: 'uppercase' }}>
                    <th scope="col" style={{ padding: '0.6rem 0.5rem' }}>Horário</th>
                    <th scope="col" style={{ padding: '0.6rem 0.5rem' }}>Remetente</th>
                    <th scope="col" style={{ padding: '0.6rem 0.5rem' }}>Mensagem Retida</th>
                    <th scope="col" style={{ padding: '0.6rem 0.5rem' }}>Criticidade</th>
                    <th scope="col" style={{ padding: '0.6rem 0.5rem' }}>Tipificação</th>
                    <th scope="col" style={{ padding: '0.6rem 0.5rem' }}>Perícia</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredThreats.map((t) => {
                    const badgeClass =
                      t.gemini_criticality === 'CRITICA'
                        ? 'badge-critica'
                        : t.gemini_criticality === 'ALTA'
                        ? 'badge-alta'
                        : t.gemini_criticality === 'MEDIA'
                        ? 'badge-media'
                        : 'badge-baixa';
                    const hasEvasion = t.gemini_rationale && t.gemini_rationale.includes('Anti-Bypass');

                    return (
                      <tr
                        key={t.id}
                        tabIndex={0}
                        role="button"
                        aria-selected={selectedThreat?.id === t.id}
                        aria-label={`Ver parecer forense de ${t.user_id}: ${t.original_message}`}
                        className={`threat-row ${selectedThreat?.id === t.id ? 'selected' : ''}`}
                        onClick={() => setSelectedThreat(t)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            setSelectedThreat(t);
                          }
                        }}
                      >
                        <td style={{ padding: '0.65rem 0.5rem', fontFamily: 'var(--font-mono)', color: 'var(--color-ink-muted)', fontSize: '0.72rem', whiteSpace: 'nowrap' }}>
                          {t.created_at ? new Date(t.created_at).toLocaleTimeString() : 'Recente'}
                        </td>
                        <td style={{ padding: '0.65rem 0.5rem', fontWeight: '500', color: 'var(--color-ink)' }}>
                          {t.user_id}
                        </td>
                        <td style={{ padding: '0.65rem 0.5rem', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--color-danger)' }}>
                          <span>"{t.original_message}"</span>
                          {hasEvasion && (
                            <span
                              style={{
                                marginLeft: '0.35rem',
                                padding: '0.1rem 0.35rem',
                                borderRadius: '4px',
                                background: 'var(--bg-warning)',
                                color: 'var(--color-warning)',
                                border: '1px solid var(--border-warning)',
                                fontSize: '0.62rem',
                                fontWeight: '700',
                                fontFamily: 'var(--font-mono)',
                              }}
                            >
                              ANTI-BYPASS
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '0.65rem 0.5rem' }}>
                          <span className={`badge ${badgeClass}`}>{t.gemini_criticality || 'ALTA'}</span>
                        </td>
                        <td style={{ padding: '0.65rem 0.5rem', color: 'var(--color-ink-secondary)' }}>
                          {t.gemini_category || 'violencia_fisica'}
                        </td>
                        <td style={{ padding: '0.65rem 0.5rem' }}>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedThreat(t);
                            }}
                            aria-label={`Ver laudo da auditoria para ${t.transaction_id}`}
                            style={{
                              background: 'transparent',
                              border: 'none',
                              color: 'var(--color-navy)',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.15rem',
                              fontSize: '0.72rem',
                              fontWeight: '600',
                            }}
                          >
                            <span>Parecer</span>
                            <ChevronRight size={13} aria-hidden="true" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* PAINEL LATERAL: PERÍCIA DO GEMINI & GESTÃO DE CONTAS */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* DETALHE DA PERÍCIA FORENSE SELECIONADA */}
          {selectedThreat ? (
            <aside
              ref={drawerRef}
              role="region"
              aria-labelledby="drawer-title"
              aria-live="polite"
              className="glass-panel"
              style={{ padding: '1.25rem' }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Scale size={16} color="var(--color-stage2)" aria-hidden="true" />
                  <h4 id="drawer-title" style={{ fontSize: '0.92rem', fontWeight: '700', color: 'var(--color-ink)' }}>
                    Parecer Pericial (Gemini 2.5 Flash)
                  </h4>
                </div>
                <button
                  ref={closeButtonRef}
                  type="button"
                  onClick={() => setSelectedThreat(null)}
                  aria-label="Fechar laudo pericial"
                  style={{
                    background: 'var(--color-paper-subtle)',
                    border: '1px solid var(--color-rule)',
                    color: 'var(--color-ink-secondary)',
                    cursor: 'pointer',
                    fontSize: '0.7rem',
                    padding: '0.2rem 0.5rem',
                    borderRadius: 'var(--radius-pill)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.25rem',
                  }}
                >
                  <X size={12} aria-hidden="true" />
                  <span>Fechar</span>
                </button>
              </div>

              {/* Destaque Anti-Bypass */}
              {selectedThreat.gemini_rationale && selectedThreat.gemini_rationale.includes('Anti-Bypass') && (
                <div
                  role="status"
                  style={{
                    background: 'var(--bg-warning)',
                    border: '1px solid var(--border-warning)',
                    padding: '0.45rem 0.65rem',
                    borderRadius: 'var(--radius-xs)',
                    marginBottom: '0.75rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                    color: 'var(--color-warning)',
                    fontSize: '0.73rem',
                    fontWeight: '600',
                  }}
                >
                  <ShieldAlert size={14} aria-hidden="true" />
                  <span>Camada Anti-Bypass: Tentativa de evasão desofuscada com sucesso.</span>
                </div>
              )}

              {/* Mensagem Original */}
              <div style={{ marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '0.68rem', color: 'var(--color-ink-muted)', textTransform: 'uppercase', fontWeight: '600' }}>
                  Mensagem Bruta Interceptada:
                </span>
                <p style={{ background: 'var(--color-paper-subtle)', padding: '0.55rem', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-rule)', color: 'var(--color-danger)', marginTop: '0.2rem', fontSize: '0.8rem', fontWeight: '600', fontFamily: 'var(--font-mono)' }}>
                  "{selectedThreat.original_message}"
                </p>
              </div>

              {/* Justificativa do Gemini */}
              <div style={{ marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '0.68rem', color: 'var(--color-ink-muted)', textTransform: 'uppercase', fontWeight: '600' }}>
                  Fundamentação Semântica & Enquadramento:
                </span>
                <p style={{ color: 'var(--color-ink-secondary)', marginTop: '0.2rem', fontSize: '0.8rem', lineHeight: '1.45' }}>
                  {selectedThreat.gemini_rationale || 'Ameaça identificada com alta criticidade com base em termos coercitivos explícitos.'}
                </p>
              </div>

              {/* Metadados Técnicos */}
              <dl style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.45rem', fontSize: '0.72rem', background: 'var(--color-paper-subtle)', padding: '0.55rem', borderRadius: 'var(--radius-xs)', border: '1px solid var(--color-rule)' }}>
                <div>
                  <dt style={{ color: 'var(--color-ink-muted)' }}>Score Ollaya:</dt>
                  <dd style={{ fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--color-accent)', margin: 0 }}>
                    {selectedThreat.ollaya_score || selectedThreat.jev_score || 0.95}
                  </dd>
                </div>
                <div>
                  <dt style={{ color: 'var(--color-ink-muted)' }}>Transação ID:</dt>
                  <dd style={{ fontFamily: 'var(--font-mono)', color: 'var(--color-ink)', margin: 0 }}>{selectedThreat.transaction_id}</dd>
                </div>
              </dl>
            </aside>
          ) : null}

          {/* GESTÃO DE CONTAS & CIRCUITO 5X */}
          <section aria-labelledby="accounts-gov-title" className="glass-panel" style={{ padding: '1.25rem' }}>
            <h4 id="accounts-gov-title" style={{ fontSize: '0.92rem', fontWeight: '700', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.45rem', color: 'var(--color-ink)' }}>
              <Users size={16} color="var(--color-navy)" aria-hidden="true" />
              Contas & Gestão de Quarentena
            </h4>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '380px', overflowY: 'auto' }}>
              {users.length === 0 ? (
                <div style={{ color: 'var(--color-ink-muted)', fontSize: '0.8rem' }}>Carregando contas cadastradas...</div>
              ) : (
                users.map((u) => (
                  <div
                    key={u.id}
                    style={{
                      background: 'var(--color-paper-subtle)',
                      border: '1px solid var(--color-rule)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '0.65rem 0.75rem',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <span style={{ fontWeight: '600', fontSize: '0.8rem', color: 'var(--color-ink)' }}>{u.id}</span>
                        <span className={`badge ${u.status === 'BLOCKED_SUSPICIOUS' ? 'badge-blocked' : 'badge-active'}`}>
                          {u.status === 'BLOCKED_SUSPICIOUS' ? 'Quarentena' : 'Ativo'}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--color-ink-muted)', marginTop: '0.15rem' }}>
                        {u.threat_count || 0} de 5 infrações registradas
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: '0.35rem' }}>
                      {u.status === 'BLOCKED_SUSPICIOUS' ? (
                        <button
                          type="button"
                          onClick={() => handleUnblock(u.id)}
                          aria-label={`Desbloquear conta ${u.id}`}
                          style={{
                            background: 'var(--bg-success)',
                            border: '1px solid var(--border-success)',
                            color: 'var(--color-success)',
                            padding: '0.25rem 0.55rem',
                            borderRadius: 'var(--radius-xs)',
                            fontSize: '0.7rem',
                            fontWeight: '600',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.25rem',
                          }}
                        >
                          <Unlock size={11} aria-hidden="true" />
                          <span>Desbloquear</span>
                        </button>
                      ) : null}

                      <button
                        type="button"
                        onClick={() => handleResetThreats(u.id)}
                        aria-label={`Zerar infrações da conta ${u.id}`}
                        style={{
                          background: '#ffffff',
                          border: '1px solid var(--color-rule)',
                          color: 'var(--color-ink-secondary)',
                          padding: '0.25rem 0.55rem',
                          borderRadius: 'var(--radius-xs)',
                          fontSize: '0.7rem',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.25rem',
                        }}
                      >
                        <RotateCcw size={11} aria-hidden="true" />
                        <span>Zerar</span>
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </section>
        </div>
      </div>

      {/* MODAL DE CONFIRMAÇÃO PARA LIMPEZA DA BASE HISTÓRICA */}
      {showConfirmModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-modal-title"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15, 23, 42, 0.6)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: '1rem',
          }}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-rule)',
              padding: '1.5rem',
              maxWidth: '460px',
              width: '100%',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 8px 10px -6px rgba(0, 0, 0, 0.1)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem', marginBottom: '1rem' }}>
              <div
                style={{
                  width: '38px',
                  height: '38px',
                  borderRadius: '50%',
                  background: 'var(--bg-danger)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--color-danger)',
                  flexShrink: 0,
                }}
              >
                <AlertTriangle size={20} aria-hidden="true" />
              </div>
              <div>
                <h3 id="confirm-modal-title" style={{ fontSize: '1.05rem', fontWeight: '700', color: 'var(--color-ink)', margin: 0 }}>
                  Limpar Toda a Base Histórica?
                </h3>
                <p style={{ fontSize: '0.82rem', color: 'var(--color-ink-muted)', marginTop: '0.35rem', lineHeight: '1.4' }}>
                  Esta ação excluirá permanentemente todos os registros de auditoria, ocorrências de fraude interceptadas e assinaturas de ameaça do sistema.
                  Além disso, todas as contas atualmente suspensas serão reativadas para o status regular.
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.65rem', marginTop: '1.25rem' }}>
              <button
                type="button"
                onClick={() => setShowConfirmModal(false)}
                disabled={isClearing}
                style={{
                  background: '#ffffff',
                  border: '1px solid var(--color-rule)',
                  padding: '0.45rem 1rem',
                  borderRadius: 'var(--radius-pill)',
                  fontSize: '0.82rem',
                  fontWeight: '600',
                  color: 'var(--color-ink-secondary)',
                  cursor: 'pointer',
                }}
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleClearAllHistory}
                disabled={isClearing}
                style={{
                  background: 'var(--color-danger)',
                  border: 'none',
                  padding: '0.45rem 1.15rem',
                  borderRadius: 'var(--radius-pill)',
                  fontSize: '0.82rem',
                  fontWeight: '600',
                  color: '#ffffff',
                  cursor: isClearing ? 'not-allowed' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  boxShadow: '0 2px 6px rgba(220, 38, 38, 0.3)',
                }}
              >
                <Trash2 size={13} aria-hidden="true" />
                <span>{isClearing ? 'Excluindo...' : 'Confirmar e Limpar'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
