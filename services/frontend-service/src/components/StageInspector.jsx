import React from 'react';
import { X, Clock3 } from 'lucide-react';
import { fmtMs } from '../journey/format';

function JsonPayload({ value }) {
  const json = JSON.stringify(value, null, 2);
  const tokens = /("(?:\\.|[^"\\])*")(\s*:)?|\b(?:true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;
  const parts = [];
  let cursor = 0;
  for (const match of json.matchAll(tokens)) {
    if (match.index > cursor) parts.push(json.slice(cursor, match.index));
    const kind = match[2] ? 'key' : match[1] ? 'string' : match[0] === 'null' ? 'null' : /^(true|false)$/.test(match[0]) ? 'boolean' : 'number';
    parts.push(<span key={match.index} className={`json-token--${kind}`}>{match[0]}</span>);
    cursor = match.index + match[0].length;
  }
  if (cursor < json.length) parts.push(json.slice(cursor));
  return <code>{parts}</code>;
}

export default function StageInspector({ id, title, description, metrics = [], payload, onClose, emphasizePayload = false, score, scoreStatus }) {
  const measured = metrics.filter((item) => typeof item.value === 'number' && Number.isFinite(item.value));
  const hasScore = typeof score === 'number' && Number.isFinite(score) && score >= 0 && score <= 1;
  const scoreText = hasScore ? score.toLocaleString('pt-BR', {style: 'percent', maximumFractionDigits: 1}) : '';
  const scoreTone = scoreStatus === 'detect' ? 'threat' : scoreStatus === 'pass' ? 'safe' : 'neutral';
  return (
    <section id={id} className={`presentation-inspector ${emphasizePayload ? 'presentation-inspector--split' : ''}`} aria-label={`Detalhes: ${title}`}>
      <header><h4>{title}</h4><button type="button" onClick={onClose} aria-label="Fechar detalhes da etapa"><X size={18} aria-hidden="true" /></button></header>
      {hasScore && <div className={`presentation-score presentation-score--${scoreTone}`}>
        <div className="presentation-score__head"><span>Score do Decision Model</span><strong>{scoreText}</strong></div>
        <div className="presentation-score__track" role="meter" aria-label="Score do Decision Model" aria-valuemin={0} aria-valuemax={1} aria-valuenow={score} aria-valuetext={scoreText}>
          <div className="presentation-score__fill" style={{width:`${score * 100}%`}} />
        </div>
        <div className="presentation-score__legend"><span>0%</span><span>100%</span></div>
      </div>}
      <div className="presentation-inspector__body">
        <div className="presentation-inspector__facts">
          <p>{description}</p>
          {measured.length > 0 && <dl>{measured.map(({ label, value }) => <div key={label}><dt><Clock3 size={14} aria-hidden="true" />{label}</dt><dd>{fmtMs(value)}</dd></div>)}</dl>}
        </div>
        {payload != null ? <details className="presentation-inspector__payload" open={emphasizePayload || undefined}><summary>Dados retornados pelo backend</summary><pre tabIndex={0} aria-label={`Payload de ${title}`}><JsonPayload value={payload} /></pre></details> : <small>Os dados desta etapa aparecerão após o envio.</small>}
      </div>
    </section>
  );
}
