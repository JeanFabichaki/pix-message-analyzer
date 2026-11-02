import React from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Lock, Send, ShieldCheck, Smartphone, BellRing, History, RotateCcw } from 'lucide-react';
import CountUp from '../components/ui/CountUp';
import DotMeter from '../components/ui/DotMeter';
import { dur, ease, spring } from '../motion/tokens';
import { SCENARIOS, RECEIVER, formatBRL } from './scenarios';
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
          <div className="phone__scenario-picker">
            <div className="scenarios scenarios--phone" role="radiogroup" aria-label="Casos prontos">
              {SCENARIOS.map((sc) => {
                const Icon = SCENARIO_ICONS[sc.icon];
                const active = scenario.id === sc.id;
                return (
                  <button
                    key={sc.id}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    className={`scenario scenario--phone ${active ? 'is-active' : ''}`}
                    onClick={() => onPickScenario(sc)}
                    disabled={busy && !active}
                  >
                    {active && (
                      <motion.span
                        layoutId="scenario-pill-phone"
                        className="scenario__pill"
                        transition={spring.soft}
                      />
                    )}
                    <span className="scenario__content">
                      {Icon && <Icon size={13} aria-hidden="true" />}
                      <span>{sc.title}</span>
                    </span>
                  </button>
                );
              })}
              {replayActive && (
                <span className="scenario scenario--phone is-active scenario--replay">
                  <span className="scenario__content">
                    <History size={13} aria-hidden="true" />
                    <span>Reprodução</span>
                  </span>
                </span>
              )}
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
              <strong>{scenario.sender.name}</strong>
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
                <span className="notif__title">Envio Bloqueado</span>
                <span className="notif__sub">Transação retida pelo sistema</span>
              </motion.div>

              <motion.div
                className="receiver-amount"
                variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { delay: 0.15 } } }}
              >
                <span className="phone__label">Valor transferido</span>
                <span className="receiver-amount__value" style={{ color: 'var(--color-danger, #ef4444)' }}>
                  R$ 0,00
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
                  <Lock size={12} aria-hidden="true" /> Pix não transferido
                </span>
                <p>O Pix continha ameaça ou intimidação e foi bloqueado preventivamente.</p>
              </motion.div>

              {typeof realMs === 'number' && (
                <motion.div
                  className="real-time-seal"
                  variants={{
                    hidden: { opacity: 0, scale: 0.8 },
                    show: { opacity: 1, scale: 1, transition: { ...spring.pop, delay: 0.7 } },
                  }}
                >
                  Tempo até bloqueio: <strong className="num">{realMs.toFixed(1).replace('.', ',')} ms</strong>
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
                <span className="notif__title">Você recebeu um Pix</span>
                <span className="notif__sub">de {senderName}</span>
              </motion.div>

              <motion.div
                className="receiver-amount"
                variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { delay: 0.15 } } }}
              >
                <span className="phone__label">Valor recebido</span>
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
