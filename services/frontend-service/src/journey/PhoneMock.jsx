import React from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Lock, Send, ShieldCheck, Smartphone, BellRing } from 'lucide-react';
import CountUp from '../components/ui/CountUp';
import DotMeter from '../components/ui/DotMeter';
import { dur, ease, spring } from '../motion/tokens';
import { RECEIVER, formatBRL } from './scenarios';

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
}) {
  const editable = Boolean(scenario.editable);
  const isReplay = scenario.id === 'replay';
  const sendDisabled = busy || isReplay || !amount || Number(amount) <= 0 || (editable && !String(message).trim());

  return (
    <section className={`phone ${suspended ? 'phone--suspended' : ''}`} aria-label="Celular de quem envia">
      <header className="phone__bar">
        <span className="phone__bar-title">
          <Smartphone size={15} aria-hidden="true" /> Quem envia
        </span>
        <span className={`chip ${suspended ? 'chip--danger' : 'chip--safe'}`}>
          {suspended ? (
            <>
              <Lock size={12} aria-hidden="true" /> Conta suspensa
            </>
          ) : (
            'Conta ativa'
          )}
        </span>
      </header>

      <div className="phone__body">
        <div className="phone__party">
          <span className="phone__label">De</span>
          <strong>{scenario.sender.name}</strong>
          <span className="phone__label">Para</span>
          <strong>{RECEIVER.name}</strong>
        </div>

        <label className="phone__amount">
          <span className="phone__label">Valor do Pix</span>
          {editable ? (
            <span className="phone__amount-input">
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
            <span className="phone__amount-value num">{formatBRL(amount)}</span>
          )}
        </label>

        <div className="phone__message">
          <span className="phone__label">Mensagem</span>
          {editable ? (
            <textarea
              value={message}
              onChange={(e) => onMessageChange(e.target.value)}
              placeholder="Digite a mensagem do Pix…"
              rows={4}
              aria-label="Mensagem do Pix"
            />
          ) : (
            <p className="phone__message-text">“{message}”</p>
          )}
        </div>

        <motion.button
          type="button"
          className="btn btn--primary btn--block"
          onClick={onSend}
          disabled={sendDisabled}
          whileTap={{ scale: 0.97 }}
          transition={spring.pop}
        >
          {busy ? (
            <span>{burstProgress ? `Enviando ${burstProgress.done} de ${burstProgress.total}…` : 'Em análise…'}</span>
          ) : (
            <>
              <span>Enviar Pix</span>
              <Send size={16} aria-hidden="true" />
            </>
          )}
        </motion.button>
        {onBurst && (
          <button type="button" className="btn btn--secondary btn--block" onClick={onBurst} disabled={busy}>
            Enviar {burstTotal}× em sequência
          </button>
        )}
        {isReplay && <p className="phone__hint phone__hint--muted">Reprodução de um Pix já processado.</p>}

        {ficha && (
          <div className="phone__ficha">
            <span className="phone__label">Ocorrências de quem envia</span>
            <DotMeter count={ficha.count} limit={ficha.limit} blocked={ficha.blocked} />
            {(ficha.count > 0 || suspended) && onReactivate && (
              <button type="button" className="btn btn--ghost btn--xs" onClick={onReactivate} disabled={busy}>
                Zerar contagem (demonstração)
              </button>
            )}
          </div>
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
