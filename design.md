# Design — Pix Guard

A locked design system for this app. Every screen redesign reads this file before emitting code.

## Genre
`modern-minimal` (Fintech Security / Observability / High-Speed Banking Protection)

## Macrostructure family
- **App Workbench (`05-workbench`)**: Visual flow-first architecture. The interface makes the two-stage defense tangible at a glance:
  - **Stage 1 (Synchronous &lt;15ms)**: Local Edge Gate (Ollaya `laya:multilingual` + Threat Intel cache) with immediate string masking without withholding funds.
  - **Stage 2 (Asynchronous Deep AI Forensic)**: Background Gemini 2.5 Flash semantic classification and legal categorization without impacting Pix settlement SLA.
  - **Stage 3 (Continuous Governance)**: Anti-evasion canonical normalization + 5x incident escalation circuit breaker.

## Theme Tokens (OKLCH + Clean Semantic Tokens)
- `--color-paper`: `oklch(98.5% 0.003 247)` (clean, calm titanium canvas)
- `--color-paper-card`: `oklch(100% 0 0)` (crisp white card surfaces)
- `--color-paper-subtle`: `oklch(96.5% 0.005 247)` (tactile inset backgrounds)
- `--color-ink`: `oklch(22% 0.02 255)` (deep slate high-contrast typography)
- `--color-ink-muted`: `oklch(48% 0.02 255)` (clear secondary and metadata text)
- `--color-rule`: `oklch(90% 0.008 255)` (hairline structural dividers)
- `--color-accent`: `oklch(64% 0.19 38)` (energetic terracotta coral for primary interactive actions and alerts)
- `--color-accent-ink`: `oklch(100% 0 0)` (pure white text on accent)
- `--color-stage1`: `oklch(58% 0.18 42)` (stage 1 sync fast-path terracotta/amber)
- `--color-stage2`: `oklch(55% 0.22 290)` (stage 2 async deep intelligence violet)
- `--color-success`: `oklch(52% 0.15 155)` (verified safe emerald green)
- `--color-danger`: `oklch(55% 0.22 25)` (retained/blocked crimson red)
- `--color-focus`: `oklch(64% 0.19 38)` (crisp 2px offset focus ring)

## Typography
- **Display & UI**: `Outfit`, -apple-system, sans-serif (Tight letter spacing `-0.02em`, weights 500, 600, 700). Roman only (no italic headers).
- **Body**: `Outfit`, sans-serif (Weight 400, line-height 1.5).
- **Mono / Latency Metrics**: `JetBrains Mono`, `Fira Code`, monospace (Weights 500, 700).
- **Type Scale**:
  - Display: `clamp(1.5rem, 2.5vw, 1.85rem)`
  - Subtitle: `0.88rem`
  - Body: `0.84rem`
  - Meta/Mono: `0.72rem` to `0.78rem`

## Spacing & Geometry
- Base: 4-point rhythmic scale (`--space-2xs`: 4px, `--space-xs`: 8px, `--space-sm`: 12px, `--space-md`: 16px, `--space-lg`: 24px, `--space-xl`: 32px).
- Radii:
  - Small pills & chips: `6px`
  - Cards: `12px`
  - Floating Nav & Mockup: `20px` to `24px`

## Motion & Microinteractions
- Easings: `cubic-bezier(0.16, 1, 0.3, 1)` (snappy entry, zero overshoot).
- Duration: 150ms to 200ms maximum.
- Respects `prefers-reduced-motion: reduce`.
- No decorative bouncing; motion only indicates live transaction state and stage transitions.

## Flow Clarity Principles (Facilidade de Entendimento do Fluxo)
1. **Interactive Workflow Ribbon**: Every screen anchors the user in the 4-phase mental model (1. Ingestion → 2. Sync Edge Gate <15ms → 3. Async LLM Forensic → 4. Governance Circuit Breaker).
2. **Instant Visual Diffs**: In evasion and threat scenarios, the UI explicitly contrasts `Entrada Bruta (Ofuscada)` ➔ `Normalização Anti-Bypass` ➔ `Mensagem Entregue ao Favorecido`.
3. **Dual-Speed Latency Indicator**: Differentiate visually between milliseconds spent in the synchronous banking path (&lt;15ms) versus asynchronous forensic enrichment (background ~800ms).
4. **Actionable State**: Clear status indicators without ambiguity, high accessibility contrast, and direct feedback.
