# Design — Pix Guard (Havenmed Edition)

A locked design system for this app. Inspired by the clean, sophisticated Havenmed Hospital Management Dashboard UI/UX architecture. Every screen redesign adheres to this specification.

## Genre
`havenmed-modern-saas` (Ultra-clean, High-Usability Fintech & Observability Dashboard)

## Macrostructure
- **Top Header Bar**: Floating luminous header with Havenmed pill navigation tabs (active item in high-contrast charcoal `#171a1f`), real-time status pill indicator, and quick utility controls.
- **Top Metric Cards Row (Signature Havenmed Pastels)**:
  - **Card 1 (Lavender)**: `bg: #eef0ff`, `accent: #6b73e8`, `text: #1e245a` — Volume de Transações Pix.
  - **Card 2 (Mint)**: `bg: #e1f5f0`, `accent: #19947d`, `text: #0d4036` — Latência Edge Gate Síncrona (<15ms SLA).
  - **Card 3 (Soft Lime / Chartreuse)**: `bg: #f3fc76`, `accent: #b5c70e`, `text: #2c3300` — Ameaças Mitigadas & Sanitizadas.
  - **Card 4 (Slate / Cool Pearl)**: `bg: #f1f3f7`, `accent: #64748b`, `text: #1e293b` — Circuit Breakers & Contas sob Quarentena.
- **Primary Content Panels**: Crisp white elevated cards (`#ffffff`) with generous 22px border radius, subtle shadows, hairline borders, and generous breathing room.

## Theme Tokens
- `--color-canvas`: `#f5f7fa` (warm luminous off-white/pearl background)
- `--color-card-white`: `#ffffff` (crisp white card surfaces)
- `--color-card-subtle`: `#f8fafc` (tactile inner container surfaces)
- `--color-ink`: `#121721` (deep slate/charcoal high-contrast typography)
- `--color-ink-secondary`: `#475467` (balanced secondary body text)
- `--color-ink-muted`: `#94a3b8` (subtle captions and metadata)
- `--color-rule`: `#e9edf2` (hairline structural dividers)

### Havenmed KPI Pastels
- `--kpi-lavender-bg`: #ebedff;
- `--kpi-lavender-accent`: #626bee;
- `--kpi-lavender-text`: #1e245a;
- `--kpi-mint-bg`: #def4ef;
- `--kpi-mint-accent`: #16937c;
- `--kpi-mint-text`: #0d3d34;
- `--kpi-lime-bg`: #f1fc6e;
- `--kpi-lime-accent`: #aebd00;
- `--kpi-lime-text`: #2a3100;
- `--kpi-slate-bg`: #eff2f6;
- `--kpi-slate-accent`: #64748b;
- `--kpi-slate-text`: #1e293b;

### Interactive Charcoal & Accents
- `--color-charcoal`: #171a1f;
- `--color-charcoal-hover`: #272c35;
- `--color-charcoal-ink`: #ffffff;

### Security Status Tokens (Harmonized)
- `--color-safe`: #107e54;
- `--bg-safe`: #e2f7ed;
- `--color-danger`: #c92a2a;
- `--bg-danger`: #fde8e8;
- `--color-warning`: #b45309;
- `--bg-warning`: #fef3c7;

## Typography
- **Primary Font**: `'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- **Code & Latency Metrics**: `'JetBrains Mono', 'Fira Code', monospace`
- **Scale**:
  - Hero KPI: `1.85rem` (Weight 700, letter-spacing `-0.03em`)
  - Section Title: `1.15rem` (Weight 600)
  - Card Title: `0.92rem` (Weight 600)
  - Body: `0.85rem` (Weight 400, line-height 1.5)
  - Micro / Meta: `0.75rem` (Weight 500)

## Geometry & Geometry
- Card Corner Radius: `22px`
- Sub-widget Radius: `14px`
- Pill Radius: `9999px`
- Shadows:
  - Card Elevation: `0 2px 4px rgba(18, 23, 33, 0.02), 0 8px 24px rgba(18, 23, 33, 0.04)`
  - Card Hover: `0 4px 8px rgba(18, 23, 33, 0.04), 0 16px 32px rgba(18, 23, 33, 0.07)`

## Motion & Interactions
- Duration: `180ms`
- Easing: `cubic-bezier(0.16, 1, 0.3, 1)`
- Tactile hover lift on KPI cards (`transform: translateY(-2px)`)
- Smooth SVG spline curves for telemetry and progress arc gauges.

## Jornada da mensagem & movimento
- Tela principal "Jornada": celular de quem envia, trilha de 4 estações, celular de quem recebe e, abaixo, as etapas em segundo plano (laudo e ficha).
- Estados das estações (sempre ícone + texto, nunca só cor): pendente (cinza), analisando (pulso), passou (verde ✓), não precisou (tracejado –), detectou (âmbar ⚠), falhou (lavanda).
- Tokens de movimento em `src/motion/tokens.js`: instant 120ms, fast 180ms, base 320ms, slow 600ms, easing `cubic-bezier(0.16, 1, 0.3, 1)`, spring pop (500/30).
- A animação nunca inventa números: tempos vêm do `trace` do gateway. Anima-se apenas `transform`/`opacity` (exceções pontuais: expansão de linha do Histórico, realce do trecho detectado).
- `prefers-reduced-motion` e o botão "Animações" desligam a bolha viajante e os efeitos; o estado final é sempre completo.
