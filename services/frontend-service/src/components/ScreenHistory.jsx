import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { ChevronDown, Lock, LockOpen, Route, Search, Trash2, RefreshCw } from 'lucide-react';
import CountUp from './ui/CountUp';
import DotMeter from './ui/DotMeter';
import Skeleton from './ui/Skeleton';
import { useToast } from './ui/Toast';
import {
  clearAllAuditHistory,
  getAuditMetrics,
  getAuditThreats,
  listUsers,
  resetUserThreats,
  unblockUser,
} from '../services/api';
import { MASK_FALLBACK, stationsFromAuditLog } from '../journey/buildTrace';
import { CRITICALITY_LABEL, categoryLabel } from '../journey/format';
import { friendlyName } from '../journey/people';
import { useMotionPrefs } from '../motion/MotionProvider';
import { dur, ease } from '../motion/tokens';

const BLOCK_LIMIT = 5;

function formatWhen(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export default function ScreenHistory({ active, onInspect }) {
  const { reduced } = useMotionPrefs();
  const { toast } = useToast();
  const [threats, setThreats] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [openId, setOpenId] = useState(null);
  const [confirmClear, setConfirmClear] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, m, u] = await Promise.all([getAuditThreats(), getAuditMetrics(), listUsers()]);
      setThreats(t || []);
      setMetrics(m);
      setUsers(u || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (active) load();
  }, [active, load]);

  const countByUser = useMemo(() => {
    const map = {};
    threats.forEach((t) => {
      map[t.user_id] = (map[t.user_id] || 0) + 1;
    });
    return map;
  }, [threats]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return threats;
    return threats.filter(
      (t) =>
        friendlyName(t.user_id, t.user_name).toLowerCase().includes(q) ||
        (t.original_message || '').toLowerCase().includes(q) ||
        (t.gemini_category || '').toLowerCase().includes(q)
    );
  }, [threats, query]);

  const suspendedUsers = users.filter((u) => u.status === 'BLOCKED_SUSPICIOUS');
  const usersWithThreats = users.filter((u) => (countByUser[u.id] || 0) > 0 || u.status === 'BLOCKED_SUSPICIOUS');

  const act = async (fn, okMessage, errMessage) => {
    try {
      await fn();
      toast(okMessage, 'safe');
      await load();
    } catch (e) {
      toast(errMessage, 'danger');
    }
  };

  const handleClear = async () => {
    setConfirmClear(false);
    await act(clearAllAuditHistory, 'Base de auditoria reiniciada.', 'Não foi possível limpar o histórico.');
    setOpenId(null);
  };

  const viewJourney = (t) => {
    onInspect({
      token: `${t.id}-${Date.now()}`,
      txId: t.transaction_id,
      senderId: t.user_id,
      senderName: friendlyName(t.user_id, t.user_name),
      amount: null,
      message: t.original_message,
      stations: stationsFromAuditLog(t),
      masked: true,
      finalMessage: MASK_FALLBACK,
      decidedBy: 'ollaya',
      realMs: null,
    });
  };

  return (
    <div className="page history">
      <div className="page__head">
        <div>
          <h2 className="page__title">Histórico de ameaças retidas</h2>
          <p className="page__lead">
            Cada registro mostra o que foi digitado, o que o destinatário viu e o laudo da IA de investigação.
          </p>
        </div>
        <div className="live__controls">
          <button type="button" className="btn btn--ghost" onClick={load} disabled={loading}>
            <RefreshCw size={16} aria-hidden="true" /> Atualizar
          </button>
          {confirmClear ? (
            <div className="confirm">
              <span>Apagar todo o histórico?</span>
              <button type="button" className="btn btn--danger btn--sm" onClick={handleClear}>
                Sim, apagar
              </button>
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => setConfirmClear(false)}>
                Cancelar
              </button>
            </div>
          ) : (
            <button type="button" className="btn btn--ghost" onClick={() => setConfirmClear(true)}>
              <Trash2 size={16} aria-hidden="true" /> Reiniciar demonstração
            </button>
          )}
        </div>
      </div>

      <div className="kpis kpis--3">
        <div className="kpi kpi--lavender">
          <span className="kpi__label">Mensagens retidas</span>
          <CountUp value={metrics?.total_threats ?? 0} className="kpi__value" />
          <span className="kpi__sub">ameaças interceptadas</span>
        </div>
        <div className="kpi kpi--slate">
          <span className="kpi__label">Contas suspensas</span>
          <CountUp value={metrics?.blocked_users ?? suspendedUsers.length} className="kpi__value" />
          <span className="kpi__sub">de {metrics?.total_users ?? users.length} contas conhecidas</span>
        </div>
        <div className="kpi kpi--lime">
          <span className="kpi__label">Gravidade crítica ou alta</span>
          <CountUp
            value={(metrics?.threats_by_criticality?.CRITICA || 0) + (metrics?.threats_by_criticality?.ALTA || 0)}
            className="kpi__value"
          />
          <span className="kpi__sub">segundo o laudo da IA</span>
        </div>
      </div>

      <div className="history__grid">
        <section className="card" aria-label="Mensagens retidas">
          <div className="card__head">
            <h3>Mensagens retidas</h3>
            <label className="search">
              <Search size={15} aria-hidden="true" />
              <input
                type="search"
                placeholder="Buscar por nome, texto ou categoria"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                aria-label="Buscar nas mensagens retidas"
              />
            </label>
          </div>

          {loading && threats.length === 0 ? (
            <Skeleton lines={5} className="skeleton--panel" />
          ) : filtered.length === 0 ? (
            <div className="empty">
              <p>
                <strong>{threats.length === 0 ? 'Nenhuma ameaça registrada ainda.' : 'Nada encontrado para a busca.'}</strong>
              </p>
              <p>Envie uma ameaça na aba Jornada e ela aparece aqui.</p>
            </div>
          ) : (
            <ul className="threat-list">
              {filtered.map((t, i) => {
                const isOpen = openId === t.id;
                const crit = t.gemini_criticality;
                const isBypass = t.gemini_category === 'bypass' || !crit || (t.gemini_rationale && t.gemini_rationale.includes('BYPASS'));
                return (
                  <motion.li
                    key={t.id}
                    layout={!reduced}
                    className={`threat ${isOpen ? 'is-open' : ''}`}
                    initial={reduced || i > 9 ? false : { opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: dur.base, ease, delay: i < 10 && !reduced ? i * 0.03 : 0 }}
                  >
                    <button
                      type="button"
                      className="threat__summary"
                      onClick={() => setOpenId(isOpen ? null : t.id)}
                      aria-expanded={isOpen}
                    >
                      <span className="threat__when num">{formatWhen(t.created_at)}</span>
                      <span className="threat__who">{friendlyName(t.user_id, t.user_name)}</span>
                      <span className="threat__msg">“{t.original_message}”</span>
                      {isBypass ? (
                        <>
                          <span className="chip chip--warn">Bypass</span>
                          <span className="chip chip--bypass">Sem laudo Gemini</span>
                        </>
                      ) : (
                        <>
                          <span className={`chip chip--crit-${crit}`}>{CRITICALITY_LABEL[crit] || crit || '—'}</span>
                          <span className="chip">{categoryLabel(t.gemini_category)}</span>
                        </>
                      )}
                      <ChevronDown size={16} className="threat__chev" aria-hidden="true" />
                    </button>

                    <AnimatePresence initial={false}>
                      {isOpen && (
                        <motion.div
                          className="threat__detail"
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: dur.base, ease }}
                        >
                          <div className="threat__cols">
                            <div>
                              <span className="decode__label">O que foi digitado</span>
                              <p className="threat__quote">“{t.original_message}”</p>
                              <span className="decode__label">O que o destinatário viu</span>
                              <p className="threat__quote threat__quote--masked">{MASK_FALLBACK}</p>
                            </div>
                            <div>
                              <span className="decode__label">Laudo da IA de investigação</span>
                              {isBypass ? (
                                <p className="threat__rationale threat__rationale--bypass">
                                  ⚠️ <strong>Investigação ignorada (Bypass):</strong> {t.gemini_rationale || 'Serviço do Google indisponível ou não autenticado.'}
                                </p>
                              ) : (
                                <p className="threat__rationale">{t.gemini_rationale || 'Sem justificativa registrada.'}</p>
                              )}
                              {typeof t.ollaya_score === 'number' && (
                                <span className="chip">IA rápida: risco {Math.round(t.ollaya_score * 100)}%</span>
                              )}
                            </div>
                          </div>
                          <div className="threat__actions">
                            <button type="button" className="btn btn--primary btn--sm" onClick={() => viewJourney(t)}>
                              <Route size={14} aria-hidden="true" /> Ver a jornada desta mensagem
                            </button>
                            <span className="threat__note">
                              A jornada é reconstruída a partir do registro, sem os tempos de cada etapa.
                            </span>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="card" aria-label="Contas com ocorrências">
          <div className="card__head">
            <h3>Contas com ocorrências</h3>
          </div>
          {usersWithThreats.length === 0 ? (
            <div className="empty">
              <p>Nenhuma conta com ocorrências.</p>
            </div>
          ) : (
            <ul className="user-list">
              {usersWithThreats.map((u) => {
                const suspended = u.status === 'BLOCKED_SUSPICIOUS';
                const count = countByUser[u.id] || 0;
                return (
                  <li key={u.id} className={`user ${suspended ? 'user--suspended' : ''}`}>
                    <div className="user__top">
                      <div>
                        <strong>{friendlyName(u.id, u.name)}</strong>
                        <span className="user__id">{u.id}</span>
                      </div>
                      <span className={`chip ${suspended ? 'chip--block' : 'chip--safe'}`}>
                        {suspended ? (
                          <>
                            <Lock size={12} aria-hidden="true" /> Suspensa
                          </>
                        ) : (
                          'Ativa'
                        )}
                      </span>
                    </div>
                    <DotMeter count={Math.min(count, BLOCK_LIMIT)} limit={BLOCK_LIMIT} blocked={suspended} />
                    <div className="user__actions">
                      {suspended && (
                        <button
                          type="button"
                          className="btn btn--secondary btn--xs"
                          onClick={() =>
                            act(() => unblockUser(u.id), `Conta de ${friendlyName(u.id, u.name)} reativada.`, 'Não foi possível reativar a conta.')
                          }
                        >
                          <LockOpen size={13} aria-hidden="true" /> Reativar conta
                        </button>
                      )}
                      <button
                        type="button"
                        className="btn btn--ghost btn--xs"
                        onClick={() =>
                          act(
                            () => resetUserThreats(u.id),
                            `Ocorrências de ${friendlyName(u.id, u.name)} zeradas.`,
                            'Não foi possível zerar as ocorrências.'
                          )
                        }
                      >
                        Zerar ocorrências
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
