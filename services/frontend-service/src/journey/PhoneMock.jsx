import React, { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Lock, Send, ShieldCheck, Smartphone, BellRing, History, RotateCcw, ChevronDown, Check } from 'lucide-react';
import CountUp from '../components/ui/CountUp';
import DotMeter from '../components/ui/DotMeter';
import { dur, ease, spring } from '../motion/tokens';
import { SCENARIOS, DEFAULT_SENDER, RECEIVER, formatBRL } from './scenarios';
import { SCENARIO_ICONS } from './scenarioIcons';

export function SenderPhone({
  scenario,
  amount,
  message,
  onAmountChange,
  onMessageChange,
  onSend,
  busy,
  suspended,
  burstProgress,
  ficha,
  onBurst,
  burstTotal,
  onReactivate,
  onPickScenario,
  replayActive,
}) {
  const [comboboxOpen, setComboboxOpen] = useState(false);
  const comboboxRef = useRef(null);

  useEffect(() => {
    if (!comboboxOpen) return;
    const handleClickOutside = (e) => {
      if (comboboxRef.current && !comboboxRef.current.contains(e.target)) {
        setComboboxOpen(false);
      }
    };
    document.addEventListener('pointerdown', handleClickOutside);
    return () => document.removeEventListener('pointerdown', handleClickOutside);
  }, [comboboxOpen]);

  const handleComboboxKeyDown = (e) => {
    if (e.key === 'Escape') {
      setComboboxOpen(false);
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!comboboxOpen) {
        setComboboxOpen(true);
      } else {
        const currentIndex = SCENARIOS.findIndex((s) => s.id === scenario.id);
        const nextIndex =
          e.key === 'ArrowDown'
            ? (currentIndex + 1) % SCENARIOS.length
            : (currentIndex - 1 + SCENARIOS.length) % SCENARIOS.length;
        onPickScenario(SCENARIOS[nextIndex]);
      }
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      setComboboxOpen((prev) => !prev);
    }
  };

  const SelectedIcon = replayActive ? History : SCENARIO_ICONS[scenario?.icon];
  const editable = Boolean(scenario.editable);
  const isReplay = scenario.id === 'replay';
  const sendDisabled = busy || isReplay || (editable && !String(message).trim());

  return (
    <section className={`phone ${suspended ? 'phone--suspended' : ''}`} aria-label="Celular de quem envia">
      <header className="phone__bar">
        <span className="phone__bar-title">
          <Smartphone size={15} aria-hidden="true" /> Quem envia
        </span>
        <div className="phone__bar-meta">
          {ficha && (ficha.count > 0 || suspended) && (
            <div className="phone__threat-meter" title={`${ficha.count} ocorrência(s)`}>
              <DotMeter count={ficha.count} limit={ficha.limit} blocked={ficha.blocked} />
              {onReactivate && (
                <button
                  type="button"
                  className="btn btn--ghost btn--xxs"
                  onClick={onReactivate}
                  disabled={busy}
                  title="Zerar contagem"
                >
                  <RotateCcw size={12} aria-hidden="true" />
                </button>
              )}
            </div>
          )}
          <span className={`chip chip--sm ${suspended ? 'chip--danger' : 'chip--safe'}`}>
            {suspended ? (
              <>
                <Lock size={11} aria-hidden="true" /> Suspensa
              </>
            ) : (
              'Ativa'
            )}
          </span>
        </div>
      </header>

      <div className="phone__body">
        {onPickScenario && (
          <div className="phone__scenario-picker" ref={comboboxRef}>
            <div className="phone__combobox-wrap">
              <span id="scenario-combobox-label" className="phone__label-mini">
                Tipo de envio
              </span>
              <button
                type="button"
                id="scenario-combobox-button"
                role="combobox"
                aria-haspopup="listbox"
                aria-expanded={comboboxOpen}
                aria-controls="scenario-combobox-listbox"
                aria-labelledby="scenario-combobox-label scenario-combobox-button"
                className={`phone__combobox-trigger ${comboboxOpen ? 'is-open' : ''}`}
                onClick={() => !busy && setComboboxOpen((prev) => !prev)}
                onKeyDown={handleComboboxKeyDown}
                disabled={busy}
              >
                <span className="phone__combobox-trigger-content">
                  {SelectedIcon && (
                    <span className="phone__combobox-icon-badge">
                      <SelectedIcon size={14} aria-hidden="true" />
                    </span>
                  )}
                  <span className="phone__combobox-trigger-text">
                    {replayActive ? 'Reprodução' : scenario.title}
                  </span>
                </span>
                <ChevronDown
                  size={16}
                  aria-hidden="true"
                  className={`phone__combobox-chevron ${comboboxOpen ? 'is-open' : ''}`}
                />
              </button>

              <AnimatePresence>
                {comboboxOpen && (
                  <motion.ul
                    id="scenario-combobox-listbox"
                    role="listbox"
                    aria-labelledby="scenario-combobox-label"
                    className="phone__combobox-menu"
                    initial={{ opacity: 0, y: -6, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -6, scale: 0.98 }}
                    transition={{ duration: 0.15, ease: [0.16, 1, 0.3, 1] }}
                  >
                    {replayActive && (
                      <li
                        role="option"
                        aria-selected={true}
                        className="phone__combobox-option is-active phone__combobox-option--replay"
                      >
                        <span className="phone__combobox-option-icon">
                          <History size={14} aria-hidden="true" />
                        </span>
                        <div className="phone__combobox-option-body">
                          <span className="phone__combobox-option-title">Reprodução</span>
                          <span className="phone__combobox-option-sub">Pix histórico reencenado</span>
                        </div>
                        <Check size={15} aria-hidden="true" className="phone__combobox-check" />
                      </li>
                    )}
                    {SCENARIOS.map((sc) => {
                      const Icon = SCENARIO_ICONS[sc.icon];
                      const active = !replayActive && scenario.id === sc.id;
                      return (
                        <li
                          key={sc.id}
                          role="option"
                          aria-selected={active}
                          className={`phone__combobox-option ${active ? 'is-active' : ''}`}
                          onClick={() => {
                            onPickScenario(sc);
                            setComboboxOpen(false);
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              onPickScenario(sc);
                              setComboboxOpen(false);
                            }
                          }}
                          tabIndex={0}
                        >
                          <span className="phone__combobox-option-icon">
                            {Icon && <Icon size={14} aria-hidden="true" />}
                          </span>
                          <div className="phone__combobox-option-body">
                            <span className="phone__combobox-option-title">{sc.title}</span>
                            <span className="phone__combobox-option-sub">{sc.path}</span>
                          </div>
                          {active && <Check size={15} aria-hidden="true" className="phone__combobox-check" />}
                        </li>
                      );
                    })}
                  </motion.ul>
                )}
              </AnimatePresence>
            </div>

            {!replayActive && scenario && (
              <p className="phone__scenario-note">
                <strong>{scenario.path}:</strong> {scenario.expects}
              </p>
            )}
          </div>
        )}

        <div className="phone__tx-strip">
          <div className="phone__tx-parties">
            <span className="phone__party-tag">
              <span className="phone__label-mini">De</span>
              <strong>{scenario?.sender?.name || DEFAULT_SENDER.name}</strong>
            </span>
            <span className="phone__party-arrow">→</span>
            <span className="phone__party-tag">
              <span className="phone__label-mini">Para</span>
              <strong>{RECEIVER.name}</strong>
            </span>
          </div>

          <div className="phone__tx-amount">
            {editable ? (
              <span className="phone__amount-input-compact">
                <span aria-hidden="true">R$</span>
                <input
                  type="number"
                  inputMode="decimal"
                  min="0.01"
                  step="0.01"
                  value={amount}
                  onChange={(e) => onAmountChange(e.target.value)}
                  aria-label="Valor do Pix em reais"
                />
              </span>
            ) : (
              <strong className="phone__amount-tag num">{formatBRL(amount)}</strong>
            )}
          </div>
        </div>

        <div className="phone__message">
          <div className="phone__message-top">
            <span className="phone__label-mini">Mensagem do Pix</span>
            {editable && <span className="phone__hint-mini">Editável</span>}
          </div>
          {editable ? (
            <textarea
              value={message}
              onChange={(e) => onMessageChange(e.target.value)}
              placeholder="Digite a mensagem do Pix…"
              rows={3}
              className="phone__textarea-compact"
              aria-label="Mensagem do Pix"
            />
          ) : (
            <p className="phone__message-text-compact">“{message}”</p>
          )}
        </div>

        <div className="phone__actions-row">
          <motion.button
            type="button"
            className="btn btn--primary btn--compact btn--block"
            onClick={onSend}
            disabled={sendDisabled}
            whileTap={{ scale: 0.97 }}
            transition={spring.pop}
          >
            {busy ? (
              <span>{burstProgress ? `Enviando ${burstProgress.done}/${burstProgress.total}…` : 'Em análise…'}</span>
            ) : (
              <>
                <span>Enviar Pix</span>
                <Send size={15} aria-hidden="true" />
              </>
            )}
          </motion.button>
          {onBurst && (
            <button
              type="button"
              className="btn btn--secondary btn--compact"
              onClick={onBurst}
              disabled={busy}
              title={`Enviar ${burstTotal} transações em rajada para testar reincidência`}
            >
              {burstTotal}× Rajada
            </button>
          )}
        </div>
        {isReplay && <p className="phone__hint phone__hint--muted">Reprodução de um Pix já processado.</p>}
        {suspended && (
          <p className="phone__hint phone__hint--danger">Conta suspensa. Clique no ícone de reset no topo para testar.</p>
        )}
      </div>
    </section>
  );
}

export function ReceiverPhone({ phase, delivered, blocked, amount, senderName, message, masked, realMs }) {
  const showResult = phase === 'done';
  return (
    <section className="phone phone--receiver" aria-label="Celular de quem recebe">
      <header className="phone__bar">
        <span className="phone__bar-title">
          <Smartphone size={15} aria-hidden="true" /> Quem recebe
        </span>
        <span className="phone__label">{RECEIVER.name.split(' ')[0]}</span>
      </header>

      <div className="phone__body phone__body--receiver" aria-live="polite">
        <AnimatePresence mode="wait" initial={false}>
          {!showResult && (
            <motion.div
              key="waiting"
              className="receiver-wait"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: dur.fast }}
            >
              <BellRing size={28} strokeWidth={1.6} aria-hidden="true" />
              <p>{phase === 'idle' ? 'Nenhum Pix ainda.' : 'Aguardando o Pix…'}</p>
            </motion.div>
          )}

          {showResult && blocked && (
            <motion.div key="blocked" className="receiver-ok" initial="hidden" animate="show">
              <motion.div
                className="notif notif--danger"
                variants={{
                  hidden: { opacity: 0, y: -28 },
                  show: { opacity: 1, y: 0, transition: { ...spring.soft } },
                }}
              >
                <span className="notif__title">Mensagem reprovada</span>
                <span className="notif__sub">Conteúdo retido para análise</span>
              </motion.div>

              <motion.div
                className="receiver-amount receiver-amount--blocked"
                variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { delay: 0.15 } } }}
              >
                <span className="phone__label">Avaliação da mensagem</span>
                <span className="receiver-amount__value" style={{ color: 'var(--color-danger, #ef4444)' }}>
                  Reprovada
                </span>
              </motion.div>

              <motion.div
                className="chat-bubble chat-bubble--blocked"
                variants={{
                  hidden: { opacity: 0, y: 12, scale: 0.97 },
                  show: { opacity: 1, y: 0, scale: 1, transition: { ...spring.soft, delay: 0.35 } },
                }}
              >
                <span className="chat-bubble__tag" style={{ color: 'var(--color-danger, #ef4444)' }}>
                  <Lock size={12} aria-hidden="true" /> Mensagem não entregue
                </span>
                <p>A mensagem continha ameaça ou intimidação e foi reprovada.</p>
              </motion.div>

              {typeof realMs === 'number' && (
                <motion.div
                  className="real-time-seal"
                  variants={{
                    hidden: { opacity: 0, scale: 0.8 },
                    show: { opacity: 1, scale: 1, transition: { ...spring.pop, delay: 0.7 } },
                  }}
                >
                  Tempo da avaliação: <strong className="num">{realMs.toFixed(1).replace('.', ',')} ms</strong>
                </motion.div>
              )}
            </motion.div>
          )}

          {showResult && delivered && !blocked && (
            <motion.div key="delivered" className="receiver-ok" initial="hidden" animate="show">
              <motion.div
                className="notif"
                variants={{
                  hidden: { opacity: 0, y: -28 },
                  show: { opacity: 1, y: 0, transition: { ...spring.soft } },
                }}
              >
                <span className="notif__title">Mensagem aprovada</span>
                <span className="notif__sub">de {senderName}</span>
              </motion.div>

              <motion.div
                className="receiver-amount receiver-amount--blocked"
                variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { delay: 0.15 } } }}
              >
                <span className="phone__label">Valor do Pix</span>
                <span className="receiver-amount__value">
                  {amount === null || amount === undefined ? (
                    <small className="receiver-amount__missing">valor não registrado</small>
                  ) : (
                    <>
                      + <CountUp value={Number(amount) || 0} decimals={2} prefix="R$ " duration={0.7} />
                    </>
                  )}
                </span>
              </motion.div>

              <motion.div
                className={`chat-bubble ${masked ? 'chat-bubble--masked' : ''}`}
                variants={{
                  hidden: { opacity: 0, y: 12, scale: 0.97 },
                  show: { opacity: 1, y: 0, scale: 1, transition: { ...spring.soft, delay: 0.35 } },
                }}
              >
                {masked && (
                  <span className="chat-bubble__tag">
                    <ShieldCheck size={12} aria-hidden="true" /> Mensagem protegida
                  </span>
                )}
                <p>{message ? `“${message}”` : 'Sem mensagem.'}</p>
              </motion.div>

              {typeof realMs === 'number' && (
                <motion.div
                  className="real-time-seal"
                  variants={{
                    hidden: { opacity: 0, scale: 0.8 },
                    show: { opacity: 1, scale: 1, transition: { ...spring.pop, delay: 0.7 } },
                  }}
                >
                  Tempo real da análise: <strong className="num">{realMs.toFixed(1).replace('.', ',')} ms</strong>
                </motion.div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </section>
  );
}
