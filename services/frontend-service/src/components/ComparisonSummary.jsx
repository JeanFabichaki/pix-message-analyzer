import React from 'react';
import { CheckCircle2 } from 'lucide-react';

const MODELS = [{id:'laya',name:'Decision Model original'}, {id:'laya_tuned',name:'Decision Model treinado'}];
const percent = (value) => `${value.toFixed(1).replace('.', ',')}%`;
export function precisionComparison(summary) {
  const values = MODELS.map(({id}) => {
    const item = summary[id];
    const flagged = item.tp + item.fp;
    return flagged > 0 && item.n > 0 ? Math.round(1000 * item.tp / flagged) / 10 : null;
  });
  const comparable = values.every((value) => value !== null);
  const difference = comparable ? Math.round((values[1] - values[0]) * 10) / 10 : null;
  return {values, difference, winner: !comparable || difference === 0 ? null : difference > 0 ? 'laya_tuned' : 'laya'};
}

export default function ComparisonSummary({summary}) {
  const {values, difference, winner} = precisionComparison(summary);
  const best = MODELS.find((item) => item.id === winner);
  return <section className="card cmp-summary" aria-labelledby="cmp-summary-title">
    <header><div><h3 id="cmp-summary-title">Precisão ao reprovar uma mensagem</h3><p>Entre as mensagens reprovadas, quantas eram realmente ameaças?</p></div><span>{summary.laya.n} mensagens comparadas</span></header>
    <div className="cmp-precision-bars">{MODELS.map(({id,name},i) => <div className={`cmp-precision-row ${winner === id ? 'is-best' : ''}`} key={id}>
      <strong>{name}</strong><div className="cmp-precision-track" role="img" aria-label={`${name}: ${values[i] === null ? 'sem mensagens reprovadas' : percent(values[i])} de precisão`}><span style={{width:`${values[i] ?? 0}%`}} className={`cmp-precision-fill cmp-precision-fill--${id}`} /></div>
      <span className="cmp-precision-value">{values[i] === null ? '—' : percent(values[i])}</span>
      {winner === id && <span className="cmp-best-label"><CheckCircle2 size={16} aria-hidden="true" /> Maior precisão neste teste</span>}
    </div>)}</div>
    <p className={`cmp-comparison-verdict ${best ? 'cmp-comparison-verdict--highlight' : ''}`} role="status">{best ? <><strong>{best.name}</strong> teve <strong className="cmp-verdict-gain">{Math.abs(difference).toFixed(1).replace('.', ',')} pontos percentuais</strong> a mais de precisão.</> : difference === 0 ? 'Os dois modelos tiveram a mesma precisão neste teste.' : 'Sem mensagens reprovadas por ambos os modelos, não é possível comparar a precisão.'}</p>
    <div className="cmp-summary-table-wrap"><table className="cmp-summary-table"><caption>Erros e acertos no mesmo conjunto</caption><thead><tr><th scope="col">Resultado</th><th scope="col">Original</th><th scope="col">Treinado</th></tr></thead><tbody>
      <tr><th scope="row">Ameaças detectadas</th>{MODELS.map(({id}) => <td key={id}>{summary[id].tp} de {summary[id].threats_total}</td>)}</tr>
      <tr><th scope="row">Ameaças não detectadas</th>{MODELS.map(({id}) => <td key={id}>{summary[id].fn}</td>)}</tr>
      <tr><th scope="row">Mensagens seguras reprovadas</th>{MODELS.map(({id}) => <td key={id}>{summary[id].fp} de {summary[id].safe_total}</td>)}</tr>
      <tr><th scope="row">Acertos no total</th>{MODELS.map(({id}) => <td key={id}>{percent(summary[id].accuracy)}</td>)}</tr>
    </tbody></table></div>
    <p className="cmp-note">Compare também as ameaças não detectadas. Maior precisão, sozinha, não significa melhor resultado em todas as métricas.</p>
  </section>;
}
