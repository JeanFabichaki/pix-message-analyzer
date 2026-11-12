import React, { useState } from 'react';
import { Database, ShieldCheck, FileLock2, Sparkles, FileText, Check, ArrowRight, LoaderCircle, RotateCcw, ChevronDown, AlertTriangle, MessageSquareX, MessageSquareWarning, MessageSquare } from 'lucide-react';
import { SCENARIOS } from '../journey/scenarios';
import { SYNC_STAGES, STATUS_LABEL, verdictLabel } from '../journey/stages';
import StageIcon from '../journey/StageIcon';
import EngineSwitch from './EngineSwitch';
import StageInspector from './StageInspector';
import { fmtMs } from '../journey/format';
import { SCENARIO_ICONS } from '../journey/scenarioIcons';
import { protectionStates, protectionNeedsAttention, PROTECTION_LABELS } from '../journey/protectionState';

const ASYNC = [
  { label: 'Histórico', Icon: Database, description: 'Contexto do remetente' },
  { label: 'Model Armor', Icon: ShieldCheck, description: 'Proteção contra injeção', timingKey: 'model_armor_ms' },
  { label: 'Cloud DLP', Icon: FileLock2, description: 'Proteção de dados pessoais', timingKey: 'cloud_dlp_ms' },
  { label: 'Gemini', Icon: Sparkles, description: 'Análise do contexto', timingKey: 'gemini_ms' },
  { label: 'Laudo', Icon: FileText, description: 'Apoio ao operador', timingKey: 'governance_ms', timingLabel: 'Registro' },
];

export default function JourneyPresentation({ scenario, amount, message, onPick, onAmountChange, onMessageChange,
  onSend, busy, burstProgress, suspended, onReactivate, run, timeline, finished, investigation,
  onSkip, onReplay, onOpenOperator, onRetry, stations, selected, onSelect }) {
  const [asyncSelection, setAsyncSelection] = useState(null);
  const asyncIndex = asyncSelection?.transactionId === run?.txId ? asyncSelection?.index : null;
  const blocked = Boolean(run?.blocked || run?.masked);
  const failed = run && !run.ok;
  const fallback = run?.decidedBy === 'ollaya_fallback';
  const ready = investigation.status === 'ready';
  const timeout = investigation.status === 'timeout';
  const data = investigation.data;
  const protection = protectionStates(data);
  const bypass = Boolean(data?.bypassed || data?.analysis?.bypassed || data?.status === 'BYPASS');
  const editable = Boolean(scenario.editable);
  const ScenarioIcon = SCENARIO_ICONS[scenario.icon] || FileText;
  const outcomeTitle = failed ? 'Não foi possível avaliar a mensagem' : blocked ? 'Mensagem reprovada' : fallback ? 'Mensagem sem análise' : 'Mensagem aprovada';
  const outcomeText = failed ? 'Tente novamente para obter o resultado da avaliação.' : blocked ? 'A mensagem não chegou ao destinatário.' : fallback ? 'O Decision Model estava indisponível. Consulte a operação.' : 'Não foram identificadas ameaças na mensagem.';
  const OutcomeIcon = failed || fallback ? MessageSquareWarning : blocked ? MessageSquareX : MessageSquare;

  return (
    <section className="presentation-journey" aria-labelledby="presentation-title">
      <header className="presentation-journey__head">
        <h2 id="presentation-title">Jornada do Pix</h2>
        <div className="presentation-model-picker"><span>Modelo de triagem</span><EngineSwitch disabled={busy} /></div>
      </header>
      <div className="presentation-journey__layout">
        <form className="presentation-compose" onSubmit={(e) => { e.preventDefault(); onSend(); }}>
          <label htmlFor="presentation-scenario">Cenário</label>
          <div className="presentation-scenario-picker">
          <ScenarioIcon size={20} className="presentation-scenario-picker__icon" aria-hidden="true" />
          <select id="presentation-scenario" value={scenario.id} disabled={busy || scenario.id === 'replay'} onChange={(e) => onPick(SCENARIOS.find((item) => item.id === e.target.value))}>
            {scenario.id === 'replay' && <option value="replay">Reprodução do Pix</option>}
            {SCENARIOS.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
          </select>
          <ChevronDown size={19} className="presentation-scenario-picker__chevron" aria-hidden="true" />
          </div>
          <label className="presentation-compose__amount-label" htmlFor="presentation-amount">Valor do Pix</label>
          <div className="presentation-compose__amount"><span>R$</span>{editable ? <input id="presentation-amount" type="number" min="0.01" step="0.01" required value={amount} disabled={busy} onChange={(e) => onAmountChange(e.target.value === '' ? '' : Number(e.target.value))} /> : <output id="presentation-amount">{Number(amount).toLocaleString('pt-BR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</output>}</div>
          <label htmlFor="presentation-message">Mensagem</label>
          <textarea id="presentation-message" rows={4} value={message} readOnly={!editable} disabled={busy} required maxLength={1000} onChange={(e) => onMessageChange(e.target.value)} />
          {suspended && <div className="presentation-notice" role="status">O remetente está suspenso. <button type="button" onClick={onReactivate} disabled={busy}>Reativar para demonstração</button></div>}
          {scenario.id === 'replay' ? <button type="button" className="presentation-primary" disabled={busy} onClick={onReplay}><RotateCcw size={18} /> Repetir animação</button> :
            <button type="submit" className="presentation-primary" disabled={busy || suspended || !String(message).trim()}>{busy ? <><LoaderCircle className="presentation-spinner" size={20} /> {burstProgress ? `Enviando ${burstProgress.done + 1} de ${burstProgress.total}` : 'Analisando Pix…'}</> : scenario.burst ? 'Enviar sequência de Pix' : finished ? 'Enviar outro Pix' : 'Enviar Pix'}</button>}
        </form>
        <section className="presentation-decision" aria-label="Análise e decisão do Pix">
          <ol className="presentation-stages">
            {SYNC_STAGES.map((stage, i) => {
              const status = timeline.states[i];
              const final = ['pass', 'skip', 'detect', 'error'].includes(status);
              const success = status === 'pass' || (stage.id === 'anti_evasion' && status === 'detect') || (stage.id === 'amount_rule' && status === 'skip');
              const tone = status === 'error' ? 'warning' : status === 'detect' && i > 1 ? 'danger' : success ? 'complete' : status === 'running' ? 'active' : 'pending';
              return <li key={stage.id} className={`presentation-stage presentation-stage--${tone}`} aria-current={status === 'running' ? 'step' : undefined}>
                <button type="button" className="presentation-stage-button" aria-expanded={selected === i} aria-controls="presentation-sync-detail" onClick={() => { onSelect(selected === i ? null : i); setAsyncSelection(null); }}>
                <span className="presentation-stage__icon"><StageIcon id={stage.id} size={30} />{success && <Check size={15} className="presentation-async-check" aria-label="Etapa concluída com sucesso" />}</span>
                <strong>{i === 3 ? 'Decisão' : stage.title}</strong>
                <span>{status === 'void' && !run ? 'Aguardando' : final ? verdictLabel(stage.id, status) : STATUS_LABEL[status]}</span>
                {final && typeof stations[i]?.ms === 'number' && <small className="presentation-stage-time" aria-label={`Tempo da etapa: ${fmtMs(stations[i].ms)}`}>{fmtMs(stations[i].ms)}</small>}
                </button>
              </li>;
            })}
          </ol>
          {selected != null && <StageInspector
            key={`sync-${selected}-${run?.txId || 'idle'}`}
            id="presentation-sync-detail" title={SYNC_STAGES[selected].title}
            emphasizePayload={SYNC_STAGES[selected].id === 'ollaya'}
            score={SYNC_STAGES[selected].id === 'ollaya' ? stations[selected]?.data?.score : undefined}
            scoreStatus={stations[selected]?.status}
            description={run ? stations[selected]?.detail?.replace(/\bA IA rápida\b/g, 'O Decision Model') || 'Esta etapa não retornou detalhes adicionais.' : 'Envie um Pix para ver o tempo medido e os dados desta etapa.'}
            metrics={[{label:'Tempo da etapa',value:stations[selected]?.ms}, {label:'Inferência',value:stations[selected]?.data?.pure_inference_ms ?? stations[selected]?.data?.inference_ms}, {label:'Transporte HTTP',value:stations[selected]?.data?.network_ms}]}
            payload={run ? SYNC_STAGES[selected].id === 'ollaya' ? stations[selected]?.data : stations[selected] : null} onClose={() => onSelect(null)}
          />}
          <div className={`presentation-outcome ${finished && run ? `presentation-outcome--${failed || fallback ? 'warning' : blocked ? 'blocked' : 'approved'}` : ''}`} role="status" aria-live="polite">
            {finished && run ? <><OutcomeIcon className="presentation-outcome__icon" size={30} strokeWidth={1.7} aria-hidden="true" /><div className="presentation-outcome__copy"><h3>{outcomeTitle}</h3><p>{outcomeText}</p></div></> : <p>{busy ? 'Acompanhe a análise da mensagem.' : 'Envie o Pix para acompanhar a análise.'}</p>}
          </div>
          {timeline.phase === 'running' && <button className="presentation-text-button" type="button" onClick={onSkip}>Pular animação <ArrowRight size={16} /></button>}
          {finished && run && scenario.id !== 'replay' && <button className="presentation-text-button" type="button" onClick={onReplay} disabled={busy}><RotateCcw size={16} /> Repetir animação</button>}
        </section>
      </div>
      {finished && run?.ok && blocked && <section className="presentation-investigation" aria-labelledby="presentation-investigation-title">
        <header><div><h3 id="presentation-investigation-title">Investigação em segundo plano</h3><p>A mensagem já foi reprovada. A investigação continua em segundo plano.</p></div>
          <span className="presentation-investigation__status" role="status">{ready ? bypass ? 'Revisão manual necessária' : 'Concluída' : timeout ? 'Resultado ainda indisponível' : <><LoaderCircle size={17} className="presentation-spinner" /> Processando</>}</span>
        </header>
        <ol className="presentation-async-stages">
          {ASYNC.map(({ label, Icon, description, timingKey, timingLabel }, i) => {
            // A API fornece o resultado final, sem eventos de progresso intermediário.
            const state = i === 1 ? protection.armor : i === 2 ? protection.dlp : null;
            const attention = ready && state && protectionNeedsAttention(state);
            const complete = ready && (state ? state === 'checked' : !bypass);
            return <li key={label} className={ready && state === 'error' ? 'is-protection-error' : attention ? 'is-intervention' : complete ? 'is-complete' : ''}>
              <button type="button" className="presentation-stage-button" aria-expanded={asyncIndex === i} aria-controls="presentation-async-detail" onClick={() => { setAsyncSelection(asyncIndex === i ? null : {transactionId:run.txId,index:i}); onSelect(null); }}>
              <span className="presentation-stage__icon"><Icon size={28} />{attention ? <AlertTriangle size={16} className="presentation-protection-alert" aria-label="A proteção precisou atuar" /> : complete && <Check size={15} className="presentation-async-check" />}</span>
              <strong>{label}</strong><span>{description}</span>
              {ready && <small>{state ? PROTECTION_LABELS[state] : bypass ? 'Consulte o resultado' : 'Concluído'}</small>}
              <small className="presentation-stage-time">{ready ? typeof data?.timing?.[timingKey] === 'number' ? `${timingLabel ? `${timingLabel}: ` : ''}${fmtMs(data.timing[timingKey])}` : 'Tempo não informado' : 'Aguardando tempo'}</small>
              </button>
            </li>;
          })}
        </ol>
        {asyncIndex != null && <StageInspector key={`async-${asyncIndex}-${run.txId}`} id="presentation-async-detail"
          title={ASYNC[asyncIndex].label}
          description={!ready ? 'A investigação ainda não retornou o resultado. Os tempos serão exibidos quando estiverem disponíveis.' : bypass ? data.bypass_reason || data.analysis?.bypass_reason || 'A investigação requer revisão manual.' : ASYNC[asyncIndex].description}
          metrics={[{label:ASYNC[asyncIndex].timingLabel || 'Tempo medido',value:data?.timing?.[ASYNC[asyncIndex].timingKey]}]}
          payload={!ready ? null : [
            {history_count:data.history_count,history_analyzed:data.history_analyzed},
            {armor_message:data.armor_message,evasion_detected:data.evasion_detected,bypassed:data.bypassed,bypass_reason:data.bypass_reason},
            {dlp_message:data.dlp_message,dlp_history:data.dlp_history,bypassed:data.bypassed,bypass_reason:data.bypass_reason},
            {analysis:data.analysis,bypassed:data.bypassed,bypass_reason:data.bypass_reason},
            {status:data.status,analysis:data.analysis,total_threats:data.total_threats,account_blocked:data.account_blocked}
          ][asyncIndex]} onClose={() => setAsyncSelection(null)} />}
        <footer>
          <p>{ready ? bypass ? data?.bypass_reason || data?.analysis?.bypass_reason || 'A proteção interrompeu a investigação. Revise as evidências manualmente.' : data?.analysis?.resumo_analise || 'O laudo está disponível para análise do operador.' : timeout ? 'A avaliação da mensagem permanece válida. Você pode consultar a investigação novamente.' : 'O laudo ficará disponível para análise do operador.'}</p>
          {ready && <button type="button" className="presentation-secondary" onClick={onOpenOperator}>Abrir análise do operador <ArrowRight size={18} /></button>}
          {timeout && <button type="button" className="presentation-secondary" onClick={onRetry}>Consultar novamente</button>}
        </footer>
      </section>}
    </section>
  );
}
