# bucks.ai design system — Mission Control Glass

Generated with the installed `ui-ux-pro-max` design-system workflow for:
`AI startup operator SaaS dashboard execution workspace dark glass bento`
(variance 7 / motion 6 / density 8), then adapted to the product and the
project's existing Next.js + Tailwind stack.

## Direction

**Style:** dark-first refined glassmorphism with dense bento composition. The
interface should feel like an operator console for founders: calm, premium,
instrumented, and decisive. Glass is used for nav, cards, overlays, and major
dashboard tiles; it is never so transparent that content competes with the
background.

**Product fit:** bucks.ai turns a one-sentence idea into a managed MVP
workspace, so the design centers on state, pipeline movement, and the next
recommended action. The UI borrows the confidence of Linear/Vercel/Attio and
the data clarity of a mission-control dashboard.

## Palette

Dark surfaces avoid pure black to reduce OLED smear and make frosted panels
legible. Teal/cyan owns "live action" and CTAs. Green, amber, rose, and slate
are semantic status colors only.

| Token | Dark value | Role |
| --- | --- | --- |
| `--background` | `#07090f` | page base |
| `--surface` | `#0b1018` | stable panel fallback |
| `--surface-elevated` | `#111827` | elevated glass fallback |
| `--surface-glass` | `rgba(10, 16, 26, 0.68)` | frosted cards/nav |
| `--foreground` | `#f4f7fb` | primary text |
| `--text-secondary` | `#a8b3c7` | body/supporting text |
| `--text-muted` | `#6f7a90` | metadata |
| `--accent` | `#2dd4bf` | primary CTA/live flow |
| `--accent-hover` | `#5eead4` | active CTA |
| `--accent-bright` | `#67e8f9` | glow/line accent |

Status tokens: `done #34d399`, `running #2dd4bf`, `queued #8b97aa`,
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
- Hero centers the live execution workspace, not a decorative illustration.
- "How it works" is a connected 01-04 bento rail.
- The six-part system uses asymmetrical tiles with hover reveal.
- Agent cards are phase-tinted and motion-light.

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
- `BentoGrid`: responsive, stable grid tracks for dense tiles.
- `StatusChip`: `done / running / queued / blocked / pending`.
- `RiskBadge`: `low / medium / high / critical`.
- `ProgressRing`: accessible SVG progress with animation.
- `KpiStat`: count-up metric tile with optional mini sparkline.
- `NextActionBlock`: the AI recommendation as the focal action surface.
- `AnimatedPipeline`: reusable pipeline with flowing connector states.
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
