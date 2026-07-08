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

Dark surfaces sit in the `#050506` / `#080808` range. Electric indigo/violet
owns command, focus, telemetry, and CTAs. Cyan/green are system-state colors,
not decoration. Amber and rose indicate checkpoints and risk.

| Token | Dark value | Role |
| --- | --- | --- |
| `--background` | `#050506` | page base |
| `--surface` | `#08080a` | stable panel fallback |
| `--surface-elevated` | `#101014` | elevated glass fallback |
| `--surface-glass` | `rgba(12, 12, 17, 0.72)` | frosted cards/nav |
| `--foreground` | `#f4f7fb` | primary text |
| `--text-secondary` | `#aeb4c4` | body/supporting text |
| `--text-muted` | `#747b8d` | metadata |
| `--accent` | `#6d5dfc` | CTA/focus/telemetry |
| `--accent-hover` | `#8378ff` | active CTA |
| `--accent-bright` | `#a6b4ff` | glow/line accent |

Status tokens: `done #38e8a7`, `running #22d3ee`, `queued #8b97aa`,
`blocked #fb7185`, `pending #fbbf24`.

Risk tokens: `low #34d399`, `medium #fbbf24`, `high #fb923c`,
`critical #fb7185`.

## Typography

`Space Grotesk` for display/headlines, `DM Sans` for UI/body copy, and
`JetBrains Mono` for status labels, IDs, metrics, and operational metadata.
The pairing reads technical and modern without becoming sterile.

Type rules:
- Body starts at 16px where text is paragraph-like; compact labels may be
  11-12px only when uppercase mono metadata.
- Long text wraps before truncating. Truncation is reserved for secondary
  activity lines and never for primary actions.
- Letter spacing remains non-negative. Mono labels use positive tracking for
  scanability.

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

## Component Contract

Shared primitives:
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
- `Navbar` and `Footer`: shared glass shell.

## Accessibility & Performance

- Body contrast targets WCAG AA over glass and fallback surfaces.
- Status and risk never rely on color alone.
- Interactive targets stay at least 44px tall.
- Focus rings remain visible globally.
- `backdrop-filter` is wrapped in a capability fallback through `.glass-surface`.
- Expensive motion is transform/opacity/SVG stroke based; width/height layout
  animation is avoided.
- Mobile breakpoints are first-class: bento grids collapse to single-column
  cards and the pipeline becomes vertical.
