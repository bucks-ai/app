# bucks.ai design system — Black Card + Mission Console

Generated with the installed `ui-ux-pro-max` design-system workflow for:
`AI startup operator SaaS dashboard execution workspace dark glass bento`
(variance 7 / motion 6 / density 8), then adapted to the product and the
project's existing Next.js + Tailwind stack.

## Direction

**Style:** near-black mission-console interface with mature glass panels,
instrument-grade cards, and restrained 3D depth. The interface should feel like
an operating system for startup execution: precise, technical, confident, and
premium. Glass is concentrated in the hero console, agent registry, checkpoints,
and tool mesh; ordinary narrative blocks stay dark and quiet.

**Product fit:** bucks.ai turns a one-sentence idea into a managed MVP
workspace, so the design centers on state, agent work, tool permissions,
deployment checkpoints, and the next operator decision. The UI borrows the
confidence of Linear/Vercel/Attio and the data clarity of a mission-control
dashboard without using generic AI imagery.

## Palette

Dark surfaces sit in the `#050506` / `#080808` range. **One teal family** owns
command, focus, telemetry, and CTAs — nothing else may introduce a second
brand hue. Cyan/green are system-state colors, not decoration. Amber and rose
indicate checkpoints and risk. `--accent-blue`, `--accent-violet`, and
`--accent-gold` are *data* hues: charts and category encoding only, never
backgrounds, glows, CTAs, links, or focus rings.

| Token | Dark value | Role |
| --- | --- | --- |
| `--background` | `#050506` | page base |
| `--surface` | `#08080a` | stable panel fallback |
| `--surface-elevated` | `#101014` | elevated glass fallback |
| `--surface-glass` | `rgba(12, 12, 17, 0.72)` | frosted cards/nav |
| `--foreground` | `#f4f7fb` | primary text |
| `--text-secondary` | `#aeb4c4` | body/supporting text |
| `--text-muted` | `#747b8d` | metadata |
| `--accent` | `#14a08f` | CTA/focus/telemetry |
| `--accent-hover` | `#17b8a4` | active CTA |
| `--accent-bright` | `#4fd1bd` | glow/line accent |
| `--accent-deep` | `#0b5f57` | gradient shadow stop |

Status tokens: `done #38e8a7`, `running #22d3ee`, `queued #8b97aa`,
`blocked #fb7185`, `pending #fbbf24`. `running` is deliberately cyan so the
live state cannot be confused with the teal accent.

Light mode is not a tint of dark mode — it carries its own elevation ramp
(`--background #f2f4f1` → `--surface #fafbf9` → `--surface-elevated #ffffff`),
with pure white reserved for the most elevated surface. Every status and body
token is re-declared for light; none may be left to inherit, or a dark-mode
value lands on paper.

## The page field

One atmosphere per route, rendered once by `<PageField />` at the top of the
tree. It is `position: fixed`, so content scrolls *through* the light. Sections
must not paint their own background, aurora, or `border-y` — that banding is
what makes a long page read as choppy. Sections separate by whitespace and
type weight; where a division is genuinely needed, use `.flow-divider`.

Risk tokens: `low #34d399`, `medium #fbbf24`, `high #fb923c`,
`critical #fb7185`.

## Typography

Four families, each with one job:

| Family | Token | Role |
| --- | --- | --- |
| `EB Garamond` | `--font-serif` | display: h1/h2, section openers, workspace titles |
| `Space Grotesk` | `--font-display` / `--font-heading` | wordmark, h3-h6, compact UI headings |
| `DM Sans` | `--font-sans` | UI and body copy |
| `JetBrains Mono` | `--font-mono` | status labels, IDs, metrics, operational metadata |

The serif carries the headline moments so the product reads considered rather
than instrument-panel technical; the geometric sans keeps dense UI compact.
Helper classes `.display-xl`, `.display-lg`, and `.display-serif` set the
optical sizing, and `.display-accent` sets the serif italic used for the one
emphasised phrase in a headline.

Type rules:
- Body starts at 16px where text is paragraph-like; compact labels may be
  11-12px only when uppercase mono metadata.
- Long text wraps before truncating. Truncation is reserved for secondary
  activity lines and never for primary actions.
- Letter spacing is negative **only** at display sizes (`-0.012em` to
  `-0.02em`), where a large serif otherwise reads as a book page. Everything
  below display scale stays non-negative, and mono labels keep positive
  tracking for scanability.

## Layout

Homepage:
- Hero headline is direct: "Your startup, operating itself."
- Mission Console shows active agent state, current run, execution log, tool
  permissions, deployment state, and a human checkpoint.
- Live Execution section turns a startup idea into Strategy, Research,
  Validation, Build, and Deploy states.
- Agent Registry, Autonomy Layer, Human Checkpoints, Tool Mesh, and Build Log
  sections prove the product is execution infrastructure, not a chatbot.

Dashboard:
- Top strip is a bento KPI row: projects, approvals, active deploys, blockers.
- Project cards prioritize next action, stage, progress, approvals, blockers,
  and last activity.
- Signed-out and missing-env states show a polished preview with clear sample
  labeling.

## Motion Spec

All motion respects `prefers-reduced-motion`.

| Element | Trigger | Timing | Meaning | Reduced-motion fallback |
| --- | --- | --- | --- | --- |
| Nav condensation | scroll past 18px | 200ms ease | page has entered working mode | static nav |
| Section reveal | enters viewport | 450-650ms stagger | establish reading order | visible immediately |
| Hero pipeline flow | page load / live state | 1.2s loop | Deploy is running | static solid connector |
| Status pulse | running state | 1.8-2s loop | work is active | static dot |
| Progress ring/bar | card paint | 650ms ease-out | project maturity | final value |
| KPI count-up | dashboard paint | 700ms ease-out | live metrics resolving | final value |
| Tile hover lift | pointer hover/focus | 180-250ms | reveal secondary detail | no transform |
| Execution loop step | step crosses viewport midline | instant state + 280ms crossfade | scroll position drives loop stage | instant swap, no transforms |
| Loop stage map | active step change | dash flow 1.2s loop on active segment | which handoff is live | static solid segments |
| Field breathe | page load | 14s ease loop, scale only | atmosphere, no contrast shift | static gradient |
| Field parallax | scroll | 0.12x offset, capped 220px | the light lags the page | static gradient |
| CTA press | pointer down | 0.98 scale, 200ms | tactile confirmation | allowed (discrete, user-initiated) |

## Component Contract

Surface rules:
- At most **two** bordered levels in any one view. Depth comes from shadow and
  the near-invisible `--edge` token, not from outlining every group.
- `.flow-card` is the default content surface (no outline, panel radius,
  two-stage shadow). `.flow-well` is a tonal grouping *inside* a card — use it
  instead of nesting another bordered box.
- Radii: `rounded-sm` / `rounded-card` / `rounded-panel`. One name, one value —
  do not re-declare a radius token in both `:root` and `@theme inline`.
- `backdrop-filter` on `.glass-surface` is declared unconditionally with the
  `-webkit-` form first. Wrapping it in `@supports` caused Lightning CSS to
  drop the property from the build entirely.

Shared primitives:
- `PageField`: the one full-bleed atmosphere for a route.
- `GlassCard`: frosted panel with solid fallback and optional hover lift.
- `GlassPanel`: black-card glass wrapper for the mission-console system.
- `BentoGrid`: responsive, stable grid tracks for dense tiles.
- `StatusChip`: `done / running / queued / blocked / pending`.
- `StatusPill`: text-first system/status label.
- `RiskBadge`: `low / medium / high / critical`.
- `ProgressRing`: accessible SVG progress with animation.
- `KpiStat`: count-up metric tile with optional mini sparkline.
- `NextActionBlock`: the AI recommendation as the focal action surface.
- `AnimatedPipeline`: reusable pipeline with flowing connector states.
- `MissionConsole`, `ExecutionLog`, `AgentCard`, `ToolTile`, and
  `AnimatedProgressRail`: landing-specific product proof primitives.
- `ExecutionLoop`: scroll-driven loop story — IntersectionObserver picks the
  active step; a sticky `LoopConsole` re-renders stage map, artifact,
  permissions, and log line per step.
- `ApprovalCheckpoint`: a human gate rendered honestly — state, risk label,
  verbatim permission prompt, and rollback path. No fake approve buttons.
- `CTAButton`: the one CTA (primary/secondary) with press feedback.
- `BackgroundAtmosphere`: shared aurora + grid + noise, pointer-transparent.
- `Navbar` and `Footer`: shared glass shell.

## Accessibility & Performance

Three rules exist because breaking them produced real, measured failures:

- **On-tint text needs its own token.** A chip is `bg-X/12 text-X`: the same
  hue lightens the background and colours the text, which caps the ratio near
  4:1 however the tint is tuned. Use `--accent-on-tint`, `--running-on-tint`,
  and `--risk-*-on-tint` for chip *text*; the raw hues stay for fills, dots,
  and rules, which only need 3:1.
- **Never de-emphasise with wrapper opacity.** `opacity` multiplies every
  descendant's contrast at once — an `opacity-60` container took body copy to
  2.8:1. De-emphasise with a text colour that still clears 4.5:1, and carry
  state with surface and rule treatment instead.
- **Form borders use `--input-border`, never `--edge`.** `--edge` sits near
  1.25:1 by design; a control boundary is load-bearing and needs 3:1 (1.4.11).

- Body contrast targets WCAG AA over glass and fallback surfaces.
- Every status/body token is declared in BOTH theme blocks. A token left to
  inherit lands a dark-mode value on paper.
- The reduced-motion block must also park Tailwind's own `animate-*`
  utilities, and must reset `filter` as well as opacity and transform.
- Status and risk never rely on color alone.
- Interactive targets stay at least 44px tall.
- Focus rings remain visible globally.
- `backdrop-filter` is wrapped in a capability fallback through `.glass-surface`.
- Expensive motion is transform/opacity/SVG stroke based; width/height layout
  animation is avoided.
- Mobile breakpoints are first-class: bento grids collapse to single-column
  cards and the pipeline becomes vertical.
