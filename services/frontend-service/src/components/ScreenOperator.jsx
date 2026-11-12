import React, { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, CheckCircle2, FileSearch, LockKeyhole, RefreshCw, Search, ShieldAlert, Undo2 } from 'lucide-react';
import { getUser, getUserThreatLogs } from '../services/api';
import { useInvestigation } from '../journey/useInvestigation';
import { categoryLabel, CRITICALITY_LABEL } from '../journey/format';
import { formatBRL, RECEIVER } from '../journey/scenarios';

function timestamp(value) {
  if (!value) return 0;
  // O banco pode serializar datas UTC sem o sufixo de fuso.
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`;
  return Date.parse(normalized) || 0;
}

function formatDate(value) {
  const time = timestamp(value);
  return time ? new Date(time).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' }) : 'Horário não informado';
}

function maskCpf(value) {
  const digits = String(value || '').replace(/\D/g, '');
  return digits.length === 11 ? `***.${digits.slice(3, 6)}.${digits.slice(6, 9)}-**` : 'Não informado';
}

export default function ScreenOperator({ context, active, transactions, simulatedBlock, onSimulateBlock, onBack }) {
  const [records, setRecords] = useState({ status: 'idle', user: null, logs: [], error: '' });
  const [refresh, setRefresh] = useState(0);
  const [query, setQuery] = useState('');
  const [onlyThreats, setOnlyThreats] = useState(false);
  const [reason, setReason] = useState('');
  const [showAllHistory, setShowAllHistory] = useState(false);
  const senderId = context?.sender.id;
  const run = context?.run;
  const investigation = useInvestigation(run?.txId, active && Boolean(run?.masked), refresh);
  const data = investigation.data || context?.investigation.data;
  const analysis = data?.analysis;
  const bypassed = Boolean(data?.bypassed || analysis?.bypassed || data?.status === 'BYPASS' || analysis?.categoria === 'bypass');
  const accountBlocked = records.user?.status === 'BLOCKED_SUSPICIOUS';

  useEffect(() => {
    if (!senderId || !active) return undefined;
    let cancelled = false;
    setRecords((previous) => ({ ...previous, status: 'loading', error: '' }));
    Promise.allSettled([getUser(senderId), getUserThreatLogs(senderId, { throwOnError: true })]).then(([user, logs]) => {
      if (cancelled) return;
      const userData = user.status === 'fulfilled' ? user.value : null;
      const validLogs = logs.status === 'fulfilled' && Array.isArray(logs.value);
      setRecords({ status: 'ready', user: userData, logs: validLogs ? logs.value : [],
        error: [!userData && 'Dados da conta indisponíveis.', !validLogs && 'Histórico de ocorrências indisponível.'].filter(Boolean).join(' '),
      });
    });
    return () => { cancelled = true; };
  }, [senderId, active, refresh, investigation.status]);

  const messages = useMemo(() => {
    if (!context) return [];
    const merged = new Map();
    transactions.filter((item) => item.sender_id === senderId).forEach((item) => {
      merged.set(item.transaction_id, { ...item, message: item.description, source: 'Pix enviado nesta sessão' });
    });
    records.logs.forEach((item) => {
      const previous = merged.get(item.transaction_id);
      merged.set(item.transaction_id, { ...previous, ...item, message: item.original_message,
        blocked: previous?.blocked ?? null, flagged: true, source: 'Ocorrência registrada' });
    });
    const current = merged.get(run.txId);
    merged.set(run.txId, { ...current, transaction_id: run.txId,
      message: current?.message || run.payload.description || data?.target_message,
      amount: run.payload.amount, blocked: Boolean(run.blocked || run.masked), flagged: Boolean(run.masked),
      source: 'Pix selecionado na Jornada', current: true });
    // Preserva envios repetidos, sem duplicar mensagens já presentes no histórico.
    const counts = new Map();
    [...merged.values()].filter((item) => !item.current).forEach((item) => {
      counts.set(item.message, (counts.get(item.message) || 0) + 1);
    });
    (data?.history_analyzed || []).forEach((message, index) => {
      if (counts.get(message) > 0) { counts.set(message, counts.get(message) - 1); return; }
      merged.set(`context-${index}`, { transaction_id: `context-${index}`, message, flagged: true, source: 'Histórico considerado no laudo' });
    });
    return [...merged.values()].sort((a, b) => Number(Boolean(b.current)) - Number(Boolean(a.current)) || timestamp(b.created_at) - timestamp(a.created_at));
  }, [context, senderId, run, data, transactions, records.logs]);

  const flaggedCount = messages.filter((item) => item.flagged || item.blocked).length;
  const canBlock = reason.trim().length > 0 && !simulatedBlock && !accountBlocked;

  if (!context) {
    return (
      <section className="page operator operator--empty" aria-labelledby="operator-title">
        <FileSearch size={32} aria-hidden="true" />
        <h2 id="operator-title" className="page__title" tabIndex={-1}>Análise do operador</h2>
        <p>Envie uma mensagem na Jornada e abra a análise do operador na investigação.</p>
        <button className="btn btn--primary" type="button" onClick={onBack}><ArrowLeft size={16} aria-hidden="true" /> Ir para a Jornada</button>
      </section>
    );
  }

  const currentMessage = messages.find((item) => item.current);
  const history = messages.filter((item) => !item.current);
  const matchingHistory = history.filter((item) => (!onlyThreats || item.flagged || item.blocked) && String(item.message || '').toLocaleLowerCase('pt-BR').includes(query.toLocaleLowerCase('pt-BR')));
  const displayedHistory = showAllHistory ? matchingHistory : matchingHistory.slice(0, 3);

  return (
    <section className="page operator operator--simplified" aria-labelledby="operator-title">
      <button type="button" className="btn btn--ghost btn--sm operator__back" onClick={onBack}><ArrowLeft size={15} aria-hidden="true" /> Voltar à Jornada</button>
      <header className="page__head"><div><h2 id="operator-title" className="page__title" tabIndex={-1}>Análise do operador</h2><p className="page__lead">Entenda a mensagem, consulte o contexto e registre sua decisão.</p></div></header>

      <div className="operator-case-summary">
        <div><span className="operator__muted">Remetente</span><strong>{records.user?.name || context.sender.name || senderId}</strong></div>
        <span className={`chip ${simulatedBlock || accountBlocked ? 'chip--danger' : records.user ? 'chip--safe' : ''}`}>{simulatedBlock ? 'Conta bloqueada' : accountBlocked ? 'Conta bloqueada' : records.user ? 'Conta ativa' : 'Status não disponível'}</span>
        {analysis && !bypassed ? <span className={`chip chip--crit-${analysis.criticidade}`}>Gravidade {CRITICALITY_LABEL[analysis.criticidade] || 'não informada'}</span> : <span className="operator__muted">{bypassed ? 'Revisão manual necessária' : 'Investigação pendente'}</span>}
        <details className="operator-account-details"><summary>Detalhes do remetente</summary><dl className="operator__facts"><div><dt>Identificador</dt><dd>{senderId}</dd></div><div><dt>CPF protegido</dt><dd>{maskCpf(records.user?.cpf_cnpj || context.sender.cpf)}</dd></div><div><dt>Mensagens disponíveis</dt><dd>{messages.length}</dd></div><div><dt>Mensagens sinalizadas</dt><dd>{flaggedCount}</dd></div></dl></details>
      </div>

      <div className="operator__layout">
        <div className="operator__main">
          <section className="operator__section operator-current" aria-labelledby="current-message-title">
            <div className="operator__section-head"><h3 id="current-message-title">Mensagem em análise</h3><span className={`chip ${currentMessage?.blocked ? 'chip--danger' : currentMessage?.flagged ? 'chip--warn' : 'chip--safe'}`}>{currentMessage?.blocked ? 'Mensagem reprovada' : currentMessage?.flagged ? 'Sinalizada para análise' : 'Mensagem aprovada'}</span></div>
            <blockquote>{currentMessage?.message || 'Sem mensagem'}</blockquote>
            <div className="operator__message-meta">{currentMessage?.amount != null && <strong>{formatBRL(currentMessage.amount)}</strong>}<span>{formatDate(currentMessage?.created_at)}</span></div>
            <details className="operator-disclosure"><summary>Detalhes da mensagem</summary><dl className="operator__facts"><div><dt>Transação de origem</dt><dd>{run.txId}</dd></div>{currentMessage?.receiver_id && <div><dt>Destinatário</dt><dd>{currentMessage.receiver_id === RECEIVER.id ? RECEIVER.name : currentMessage.receiver_id}</dd></div>}</dl></details>
          </section>

          <section className="operator__section" aria-labelledby="forensic-title">
            <div className="operator__section-head"><h3 id="forensic-title"><FileSearch size={18} aria-hidden="true" /> Resumo da investigação</h3></div>
            {bypassed ? <div className="operator__notice" role="status"><strong>A investigação requer revisão manual.</strong><p>{analysis?.bypass_reason || data?.bypass_reason || 'A proteção interrompeu a investigação. Revise as mensagens e evidências disponíveis.'}</p></div> : analysis ? <>
              <div className="chips"><span className="chip">{categoryLabel(analysis.categoria)}</span>{analysis.acao_imediata_recomendada && <span className="chip chip--danger">Intervenção prioritária recomendada</span>}</div>
              <p className="operator-investigation-brief">{analysis.resumo_analise || 'A investigação não contém um resumo.'}</p>
              {analysis.recomendacao_analista && <div className="operator-recommendation"><strong>Recomendação da IA</strong><p>{analysis.recomendacao_analista}</p></div>}
              <details className="operator-disclosure"><summary>Ver investigação completa e evidências</summary><p className="operator__summary">{analysis.resumo_analise}</p><dl className="operator__analysis">
                {analysis.padrao_identificado && <div><dt>Padrão identificado</dt><dd>{analysis.padrao_identificado}</dd></div>}
                {analysis.evidencias_citadas?.length > 0 && <div><dt>Evidências citadas</dt><dd>{analysis.evidencias_citadas.map((text, i) => <blockquote key={i}>{text}</blockquote>)}</dd></div>}
                {analysis.recomendacao_analista && <div><dt>Recomendação completa</dt><dd>{analysis.recomendacao_analista}</dd></div>}
              </dl><details className="operator-disclosure"><summary>Dados técnicos: tempos e custo</summary><pre>{JSON.stringify({timing:data?.timing,cost:data?.cost || analysis.cost},null,2)}</pre></details></details>
              <p className="operator__muted operator-ai-note">A IA apoia a análise. A decisão é do operador.</p>
            </> : <div className="operator__notice" role="status"><strong>{investigation.status === 'timeout' ? 'A investigação ainda não está disponível.' : 'Aguardando a investigação…'}</strong><p>Você já pode revisar a mensagem e o histórico disponível.</p></div>}
          </section>

          <section className="operator__section" aria-labelledby="messages-title">
            <div className="operator__section-head"><h3 id="messages-title">Histórico de mensagens <span className="operator__count">{history.length}</span></h3><button type="button" className="btn btn--ghost btn--xs" onClick={() => setRefresh((value) => value + 1)} disabled={records.status === 'loading'}><RefreshCw size={14} aria-hidden="true" /> {records.status === 'loading' ? 'Carregando…' : 'Atualizar'}</button></div>
            <p className="operator__muted">Outras mensagens disponíveis. O histórico pode ser parcial.</p>
            {records.error && <p className="operator__notice" role="alert">{records.error} Exibindo os dados disponíveis.</p>}
            <details className="operator-disclosure"><summary>Buscar e filtrar mensagens</summary><div className="operator__filters"><label className="operator__search"><Search size={16} aria-hidden="true" /><span className="sr-only">Buscar nas mensagens</span><input type="search" placeholder="Buscar nas mensagens" value={query} onChange={(e) => {setQuery(e.target.value);setShowAllHistory(false);}} /></label><label className="operator__checkbox"><input type="checkbox" checked={onlyThreats} onChange={(e) => {setOnlyThreats(e.target.checked);setShowAllHistory(false);}} /> Somente sinalizadas</label></div></details>
            <ol className="operator__messages">{displayedHistory.map((item) => <li key={item.transaction_id} className="operator__message operator-history-item">
              <div className="operator__message-head"><time>{formatDate(item.created_at)}</time><span className={`chip ${item.blocked ? 'chip--danger' : item.flagged ? 'chip--warn' : 'chip--safe'}`}>{item.blocked ? 'Mensagem reprovada' : item.flagged ? 'Sinalizada' : 'Mensagem aprovada'}</span></div>
              <blockquote>{item.message || 'Sem mensagem'}</blockquote>
              <details className="operator-disclosure"><summary>Ver detalhes</summary><div className="operator__message-meta">{item.amount != null && <span>{formatBRL(item.amount)}</span>}<span>{item.source}</span></div>{item.gemini_rationale && <p className="operator__rationale">{item.gemini_rationale}</p>}<small className="operator__transaction">{item.transaction_id.startsWith('context-') ? 'ID não informado no contexto da investigação' : item.transaction_id}</small></details>
            </li>)}</ol>
            {matchingHistory.length > 3 && <button type="button" className="btn btn--ghost btn--sm operator-history-toggle" aria-expanded={showAllHistory} onClick={() => setShowAllHistory((value) => !value)}>{showAllHistory ? 'Mostrar somente 3 mensagens' : `Ver histórico completo (${matchingHistory.length})`}</button>}
            {displayedHistory.length === 0 && <p className="operator__no-results" role="status">{query || onlyThreats ? 'Nenhuma mensagem encontrada com estes filtros.' : 'Nenhuma mensagem anterior disponível.'}</p>}
          </section>
        </div>

        <aside className="operator__sidebar" aria-label="Decisão manual">
          <section className="operator__section" aria-labelledby="decision-title"><div className="operator__section-head"><h3 id="decision-title"><ShieldAlert size={18} aria-hidden="true" /> Decisão do operador</h3></div>
            {simulatedBlock ? <div className="operator__decision-result" role="status"><CheckCircle2 size={23} aria-hidden="true" /><strong>Conta bloqueada</strong><p>{simulatedBlock.reason}</p><span>{formatDate(simulatedBlock.createdAt)}</span><button type="button" className="btn btn--ghost btn--sm" onClick={() => onSimulateBlock(senderId,null)}><Undo2 size={15} aria-hidden="true" /> Desfazer bloqueio</button></div> : <form className="operator__decision-form" onSubmit={(event) => {event.preventDefault();if(canBlock)onSimulateBlock(senderId,{reason:reason.trim(),createdAt:new Date().toISOString(),transactionId:run.txId});}}>
              <label htmlFor="block-reason">Justificativa da decisão</label><textarea id="block-reason" required maxLength={1000} rows={4} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Descreva as evidências que fundamentam sua decisão…" disabled={accountBlocked} aria-describedby="block-help" /><p id="block-help" className="operator__muted">{accountBlocked ? 'A conta já consta como bloqueada no cadastro.' : 'Registre uma justificativa para habilitar o bloqueio.'}</p><button className="btn btn--danger" type="submit" disabled={!canBlock}><LockKeyhole size={16} aria-hidden="true" /> Bloquear conta</button>
            </form>}
          </section>
        </aside>
      </div>
    </section>
  );
}
