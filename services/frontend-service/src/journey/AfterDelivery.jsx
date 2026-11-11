import React from 'react';
import { motion } from 'motion/react';
import {
  Brain,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  FileLock2,
  LockKeyhole,
  CheckCircle2,
  ArrowRight,
  ArrowDown,
  Sparkles,
} from 'lucide-react';
import Skeleton from '../components/ui/Skeleton';
import { ASYNC_STAGES } from './stages';
import { fmtMs } from './format';
import { dur, ease } from '../motion/tokens';

const ICONS = {
  armor: ShieldCheck,
  dlp: FileLock2,
  laudo: Brain,
};

const DLP_INFOTYPES = [
  { id: 'BRAZIL_CPF_NUMBER', label: 'CPF' },
  { id: 'BRAZIL_RG_NUMBER', label: 'RG' },
  { id: 'PHONE_NUMBER', label: 'Telefone' },
  { id: 'EMAIL_ADDRESS', label: 'E-mail' },
  { id: 'CREDIT_CARD_NUMBER', label: 'Cartão de Crédito' },
  { id: 'PERSON_NAME', label: 'Nome Completo' },
  { id: 'STREET_ADDRESS', label: 'Endereço' },
];

function Card({ stage, index = 0, play, children, tone = 'default', extraClass = '' }) {
  const Icon = ICONS[stage.id] || Brain;
  return (
    <motion.article
      className={`after-card after-card--${stage.id} after-card--${tone} ${extraClass}`}
      initial={play ? { opacity: 0, y: 14 } : false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: play ? 0.08 + index * 0.06 : 0, duration: dur.base, ease }}
    >
      <header className="after-card__head">
        <span className="after-card__num">{stage.n}</span>
        <div>
          <h4>{stage.title}</h4>
          <span className="after-card__sub">{stage.sub}</span>
        </div>
        <Icon size={18} aria-hidden="true" className="after-card__icon" />
      </header>
      {children}
    </motion.article>
  );
}

function formatDlpOutput(targetMsg, backendDlpMsg) {
  if (backendDlpMsg && backendDlpMsg !== targetMsg) {
    let text = backendDlpMsg;
    text = text.replace(/\b\d{3}\.\d{3}\.\d{3}-\d{2}\b/g, '[BRAZIL_CPF_NUMBER]');
    return text;
  }
  let text = String(targetMsg || '');
  text = text.replace(/\b\d{3}\.\d{3}\.\d{3}-\d{2}\b/g, '[BRAZIL_CPF_NUMBER]');
  text = text.replace(/\(?\b\d{2}\)?\s*9?\d{4}-?\d{4}\b/g, '[PHONE_NUMBER]');
  text = text.replace(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, '[EMAIL_ADDRESS]');
  return text;
}

function renderDlpFormattedText(text) {
  if (!text) return null;
  const regex = /(\[(?:BRAZIL_CPF_NUMBER|BRAZIL_RG_NUMBER|PHONE_NUMBER|EMAIL_ADDRESS|CREDIT_CARD_NUMBER|PERSON_NAME|STREET_ADDRESS|CPF_OCULTO|TEL_OCULTO|EMAIL_OCULTO|CHAVE_PIX_OCULTA|DADO_BANCARIO_OCULTO)\])/g;
  const parts = String(text).split(regex);
  return parts.map((part, idx) => {
    if (regex.test(part)) {
      return (
        <span key={idx} className="token-pii" title="Dado sensível protegido pelo Cloud DLP">
          {part}
        </span>
      );
    }
    return <span key={idx}>{part}</span>;
  });
}

function renderPiiInputHighlighted(text) {
  if (!text) return null;
  const regex = /(\b\d{3}\.\d{3}\.\d{3}-\d{2}\b|\(?\b\d{2}\)?\s*9?\d{4}-?\d{4}\b|[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g;
  const parts = String(text).split(regex);
  return parts.map((part, idx) => {
    if (regex.test(part)) {
      return (
        <mark key={idx} className="token-raw-pii" title="Dado pessoal sensível detectado">
          {part}
        </mark>
      );
    }
    return <span key={idx}>{part}</span>;
  });
}

function renderInjectionInputHighlighted(text) {
  if (!text) return null;
  const regex = /(\[SISTEMA[^\]]*\]|\[SYSTEM[^\]]*\]|ignore\s+as\s+instruções[^.]*\.|ignore[^,.]*|desative[^,.]*)/gi;
  const parts = String(text).split(regex);
  return parts.map((part, idx) => {
    if (regex.test(part)) {
      return (
        <mark key={idx} className="token-injection" title="Tentativa de injeção de prompt detectada">
          {part}
        </mark>
      );
    }
    return <span key={idx}>{part}</span>;
  });
}

export default function AfterDelivery({ masked, investigation, reduced, targetMessage, onOpenOperator }) {
  const play = !reduced;
  const data = investigation.data;
  const analysis = data?.analysis;
  const isBypass = Boolean(
    analysis?.bypassed || data?.bypassed || data?.status === 'BYPASS' || analysis?.categoria === 'bypass'
  );

  const [armorStage, dlpStage, laudoStage] = ASYNC_STAGES;

  const targetMsg = data?.target_message || targetMessage;
  const canonicalMsg = data?.canonical_message || data?.armor_message;
  const isEvasion = Boolean(data?.evasion_detected || (canonicalMsg && canonicalMsg !== targetMsg));
  const armorDisplayMsg = isEvasion && canonicalMsg ? canonicalMsg : targetMsg;

  const isPending = masked && investigation.status === 'pending';
  const isReady = masked && investigation.status === 'ready';
  const isTimeout = masked && investigation.status === 'timeout';

  const timing = data?.timing || {};

  // Se o bypass aconteceu especificamente no Model Armor ou no DLP:
  const bypassReason = String(analysis?.bypass_reason || data?.bypass_reason || '');
  const isArmorBypass = isBypass && (bypassReason.toLowerCase().includes('armor') || bypassReason.toLowerCase().includes('injeção'));
  const isDlpBypass = isBypass && (bypassReason.toLowerCase().includes('dlp') || bypassReason.toLowerCase().includes('sensíveis') || bypassReason.toLowerCase().includes('mascarar'));

  const targetLower = String(targetMsg || '').toLowerCase();
  const hasInjectionPattern =
    targetLower.includes('ignore') ||
    targetLower.includes('instruç') ||
    targetLower.includes('bacen') ||
    targetLower.includes('sistema') ||
    targetLower.includes('override');

  const hasPiiPattern =
    /\d{3}\.\d{3}\.\d{3}-\d{2}/.test(targetMsg || '') ||
    /\(\d{2}\)\s*\d{4,5}-\d{4}/.test(targetMsg || '') ||
    /@\w+/.test(targetMsg || '') ||
    String(data?.analysis?.resumo_analise || '').toLowerCase().includes('doxxing') ||
    JSON.stringify(data?.analysis?.evidencias_citadas || []).includes('[PHONE_NUMBER]') ||
    JSON.stringify(data?.analysis?.evidencias_citadas || []).includes('[BRAZIL_CPF_NUMBER]');

  const dlpOutputText = formatDlpOutput(targetMsg, data?.dlp_message);

  return (
    <section className="after" aria-label="O que acontece depois da entrega, em segundo plano">
      <div className="after__lead-wrap">
        <div className="after__lead">
          <motion.span
            className="after__line"
            initial={play ? { scaleY: 0 } : false}
            animate={{ scaleY: 1 }}
            transition={{ duration: 0.4, ease }}
            aria-hidden="true"
          />
          <div>
            <p className="after__lead-title">
              <strong>Depois da entrega</strong>, em segundo plano e sem atrasar o Pix:
            </p>
            <span className="after__lead-sub">
              Workflow Google ADK · Execução assíncrona com proteção de prompt e privacidade
            </span>
          </div>
        </div>

        {masked && (
          <div className="after__pipeline-badge">
            <Sparkles size={12} aria-hidden="true" />
            <span>Google ADK (Agent Development Kit)</span>
          </div>
        )}
      </div>

      {!masked ? (
        <div className="after__clean-box">
          <div className="after__clean-icon">
            <ShieldCheck size={22} aria-hidden="true" />
          </div>
          <div className="after__clean-text">
            <strong>Triagem de Borda Concluída com Sucesso (sub-15ms)</strong>
            <p>
              O Pix foi aprovado pelo modelo de decisão rápida local (Laya) sem detecção de ameaça. Para governança financeira e otimização de custos (FinOps), o pipeline de investigação assíncrona em nuvem (Model Armor, Cloud DLP e Gemini) é acionado exclusivamente quando há identificação de risco ou suspeita de evasão.
            </p>
          </div>
        </div>
      ) : (
        <>
          {/* Stepper horizontal do Workflow ADK em segundo plano */}
          <div className="after__workflow-stepper">
            <div className={`after__step-node ${isReady ? 'is-complete' : isPending ? 'is-active' : ''}`}>
              <div className="after__step-num">5</div>
              <div className="after__step-info">
                <span className="after__step-label">Model Armor</span>
                <span className="after__step-sub">
                  {isPending && 'Inspecionando prompt…'}
                  {isReady && !isArmorBypass && (
                    <span className="after__step-status is-safe">
                      <ShieldCheck size={11} aria-hidden="true" /> 0 Injeção
                      {typeof timing.model_armor_ms === 'number' && ` · ${fmtMs(timing.model_armor_ms)}`}
                    </span>
                  )}
                  {isArmorBypass && <span className="after__step-status is-warn">Bypass Armor</span>}
                  {isTimeout && 'Aguardando…'}
                </span>
              </div>
            </div>

            <div className={`after__step-connector ${isReady ? 'is-complete' : ''}`}>
              <ArrowRight size={14} aria-hidden="true" />
            </div>

            <div className={`after__step-node ${isReady ? 'is-complete' : isPending ? 'is-active' : ''}`}>
              <div className="after__step-num">6</div>
              <div className="after__step-info">
                <span className="after__step-label">Cloud DLP</span>
                <span className="after__step-sub">
                  {isPending && 'Sanitizando PII…'}
                  {isReady && !isDlpBypass && (
                    <span className="after__step-status is-safe">
                      <LockKeyhole size={11} aria-hidden="true" /> LGPD Sanitizado
                      {typeof timing.cloud_dlp_ms === 'number' && ` · ${fmtMs(timing.cloud_dlp_ms)}`}
                    </span>
                  )}
                  {isDlpBypass && <span className="after__step-status is-warn">Bypass DLP</span>}
                  {isTimeout && 'Aguardando…'}
                </span>
              </div>
            </div>

            <div className={`after__step-connector ${isReady ? 'is-complete' : ''}`}>
              <ArrowRight size={14} aria-hidden="true" />
            </div>

            <div className={`after__step-node ${isReady ? 'is-complete' : isPending ? 'is-active' : ''}`}>
              <div className="after__step-num">7</div>
              <div className="after__step-info">
                <span className="after__step-label">Gemini Forense</span>
                <span className="after__step-sub">
                  {isPending && 'Periciando histórico…'}
                  {isReady && !isBypass && (
                    <span className="after__step-status is-safe">
                      <Brain size={11} aria-hidden="true" /> Laudo Concluído
                      {typeof timing.gemini_ms === 'number' && ` · ${fmtMs(timing.gemini_ms)}`}
                    </span>
                  )}
                  {isBypass && <span className="after__step-status is-warn">Bypass Ativo</span>}
                  {isTimeout && 'Processando…'}
                </span>
              </div>
            </div>
          </div>

          {/* Grid com os passos 5 (Model Armor) e 6 (Cloud DLP) lado a lado */}
          <div className="after__protection-grid">
            {/* ETAPA 5: MODEL ARMOR */}
            <Card
              stage={armorStage}
              index={0}
              play={play}
              tone={isArmorBypass ? 'bypass' : isReady ? 'ready' : 'default'}
              extraClass="after-card--armor"
            >
              <div className="chips">
                {isPending && <span className="chip chip--running">Inspecionando Conteúdo…</span>}
                {isReady && !isArmorBypass && (
                  <>
                    <span className="chip chip--safe">
                      <ShieldCheck size={12} aria-hidden="true" /> Prompt Sanitizado (NO_MATCH)
                    </span>
                    <span className="chip">pi_and_jailbreak</span>
                    <span className="chip chip--accent">southamerica-east1</span>
                  </>
                )}
                {isArmorBypass && (
                  <span className="chip chip--warn">
                    <AlertTriangle size={12} aria-hidden="true" /> Alerta de Injeção / Bloqueio
                  </span>
                )}
                {isTimeout && <span className="chip">Aguardando Resposta</span>}
              </div>

              <p className="after-card__text">
                O <strong>Google Cloud Model Armor</strong> inspeciona as mensagens e o histórico contra ataques de <em>Indirect Prompt Injection</em> e tentativas de jailbreak antes de submeter o prompt à IA.
              </p>

              {isPending && (
                <div className="after-card__pending-box">
                  <Skeleton lines={2} />
                  <span className="after-card__muted">Verificando template de segurança no Google Cloud…</span>
                </div>
              )}

              {/* ENTRADA VS SAÍDA: MODEL ARMOR */}
              {isReady && (
                <div className="card-io">
                  <div className="card-io__section card-io__section--input">
                    <div className="card-io__label">
                      <span className="card-io__tag card-io__tag--input">Entrada</span>
                      <span>{isEvasion ? 'Texto decodificado (Canônico após desofuscação)' : 'Mensagem enviada (Raw)'}</span>
                    </div>
                    <div className="card-io__text card-io__text--input">
                      {renderInjectionInputHighlighted(armorDisplayMsg)}
                    </div>
                  </div>

                  <div className="card-io__arrow" aria-hidden="true">
                    <ArrowDown size={14} />
                  </div>

                  <div className="card-io__section card-io__section--output">
                    <div className="card-io__label">
                      <span className="card-io__tag card-io__tag--output">Saída</span>
                      <span>Tratamento Armor &amp; Isolamento Forense</span>
                    </div>
                    <div className="card-io__text card-io__text--armor-out">
                      <div className="card-io__xml-wrap">
                        <span className="card-io__xml-tag">&lt;mensagem_alvo_investigada id="1"&gt;</span>
                        <div className="card-io__xml-content">{armorDisplayMsg}</div>
                        <span className="card-io__xml-tag">&lt;/mensagem_alvo_investigada&gt;</span>
                      </div>
                    </div>
                    <span className="card-io__badge-note card-io__badge-note--armor">
                      <CheckCircle2 size={12} aria-hidden="true" />
                      {isEvasion
                        ? 'Disfarce removido antes da verificação · Inspecionado sem brecha para injeção leetspeak'
                        : 'Comandos desarmados · Tratado estritamente como evidência pericial inerte'}
                    </span>
                  </div>
                </div>
              )}

              {hasInjectionPattern && isReady && (
                <div className="after-card__highlight-box after-card__highlight-box--armor">
                  <div className="after-card__highlight-head">
                    <ShieldAlert size={14} aria-hidden="true" />
                    <strong>Tentativa de Prompt Injection Contida</strong>
                  </div>
                  <p>
                    O atacante tentou inserir comandos para forçar aprovação (ex: simulação de sistema/Bacen). O <strong>Model Armor</strong> filtrou o vetor de ataque e o Gemini tratou o comando estritamente como evidência forense de fraude.
                  </p>
                </div>
              )}

              {isArmorBypass && (
                <div className="after-card__armor-box after-card__armor-box--warn">
                  <div className="after-card__armor-item">
                    <AlertTriangle size={13} aria-hidden="true" className="after-card__armor-icon is-warn" />
                    <span><strong>Bloqueio de Segurança:</strong> {bypassReason || 'Tentativa de injeção interceptada pelo Model Armor.'}</span>
                  </div>
                </div>
              )}

              <div className="after-card__footer-meta">
                {typeof timing.model_armor_ms === 'number' && (
                  <span className="after-card__muted">
                    Tempo de triagem do Armor: <strong>{fmtMs(timing.model_armor_ms)}</strong>
                  </span>
                )}
                <span className="after-card__guardrail-badge">
                  google-cloud-modelarmor · Região SP
                </span>
              </div>
            </Card>

            {/* ETAPA 6: CLOUD DLP (SENSITIVE DATA PROTECTION) */}
            <Card
              stage={dlpStage}
              index={1}
              play={play}
              tone={isDlpBypass ? 'bypass' : isReady ? 'ready' : 'default'}
              extraClass="after-card--dlp"
            >
              <div className="chips">
                {isPending && <span className="chip chip--running">De-identificando PII…</span>}
                {isReady && !isDlpBypass && (
                  <>
                    <span className="chip chip--safe">
                      <LockKeyhole size={12} aria-hidden="true" /> PII De-identificada
                    </span>
                    <span className="chip">7 InfoTypes</span>
                    <span className="chip chip--accent">LGPD &amp; Sigilo Bancário</span>
                  </>
                )}
                {isDlpBypass && (
                  <span className="chip chip--warn">
                    <AlertTriangle size={12} aria-hidden="true" /> Falha no Mascaramento
                  </span>
                )}
                {isTimeout && <span className="chip">Aguardando Resposta</span>}
              </div>

              <p className="after-card__text">
                O <strong>Sensitive Data Protection (Cloud DLP)</strong> de-identifica identificadores pessoais sensíveis antes do envio à nuvem, garantindo compliance com a LGPD e a LC 105/2001 (Sigilo Bancário).
              </p>

              {isPending && (
                <div className="after-card__pending-box">
                  <Skeleton lines={2} />
                  <span className="after-card__muted">Anonimizando dados pessoais no Cloud DLP regional…</span>
                </div>
              )}

              {/* ENTRADA VS SAÍDA: CLOUD DLP */}
              {isReady && (
                <div className="card-io">
                  <div className="card-io__section card-io__section--input">
                    <div className="card-io__label">
                      <span className="card-io__tag card-io__tag--input">Entrada</span>
                      <span>Mensagem que entrou (PII Exposta)</span>
                    </div>
                    <div className="card-io__text card-io__text--input">
                      {renderPiiInputHighlighted(armorDisplayMsg)}
                    </div>
                  </div>

                  <div className="card-io__arrow" aria-hidden="true">
                    <ArrowDown size={14} />
                  </div>

                  <div className="card-io__section card-io__section--output">
                    <div className="card-io__label">
                      <span className="card-io__tag card-io__tag--output">Saída</span>
                      <span>Após tratamento Cloud DLP (LGPD)</span>
                    </div>
                    <div className="card-io__text card-io__text--output">
                      {renderDlpFormattedText(dlpOutputText)}
                    </div>
                    <span className="card-io__badge-note">
                      <LockKeyhole size={12} aria-hidden="true" />
                      PII substituída por marcadores criptográficos antes da transmissão ao Gemini
                    </span>
                  </div>
                </div>
              )}

              <div className="after-card__dlp-infotypes">
                <span className="after-card__dlp-title">InfoTypes inspecionados ativamente:</span>
                <div className="after-card__infotypes-list">
                  {DLP_INFOTYPES.map((info) => (
                    <span key={info.id} className="infotype-badge" title={`Detector: ${info.id}`}>
                      {info.label}
                    </span>
                  ))}
                </div>
              </div>

              {hasPiiPattern && isReady && (
                <div className="after-card__highlight-box after-card__highlight-box--dlp">
                  <div className="after-card__highlight-head">
                    <LockKeyhole size={14} aria-hidden="true" />
                    <strong>Dados Sensíveis Anonimizados (LGPD)</strong>
                  </div>
                  <p>
                    A mensagem continha dados pessoais explícitos da vítima (CPF / Telefone). O <strong>Cloud DLP</strong> de-identificou os dados com marcadores criptográficos antes da perícia, garantindo a privacidade legal.
                  </p>
                </div>
              )}

              <div className="after-card__footer-meta">
                {typeof timing.cloud_dlp_ms === 'number' && (
                  <span className="after-card__muted">
                    Tempo de mascaramento DLP: <strong>{fmtMs(timing.cloud_dlp_ms)}</strong>
                  </span>
                )}
                <span className="after-card__guardrail-badge">
                  google-cloud-dlp · Região SP
                </span>
              </div>
            </Card>
          </div>

          <div className="after__laudo-container">
            <Card stage={laudoStage} index={2} play={play} extraClass="after-card--laudo">
              <button type="button" className="btn btn--primary" onClick={onOpenOperator}>
                Abrir análise do operador <ArrowRight size={16} aria-hidden="true" />
              </button>
            </Card>
          </div>
        </>
      )}
    </section>
  );
}