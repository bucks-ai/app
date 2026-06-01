# TASKS.md

> Update this file after every agent session. Move tasks between buckets as work progresses.

---

## Now

- [x] Initialize Next.js app with TypeScript, Tailwind, App Router, src-dir
- [x] Create agent handoff system (AGENTS.md, CLAUDE.md, PROJECT_STATE.md, TASKS.md, DECISIONS.md, AI_CHANGELOG.md)
- [x] Create .env.example with all placeholder env vars
- [x] Build initial landing page (Hero, What We Do, How It Works, Autonomy Boundaries, CTA)
- [x] Homepage redesign — premium operator console aesthetic (feature/homepage-redesign)
- [x] Surface unification — `/intake` and `/tools` match premium operator console aesthetic

---

## Next

- [ ] Resolve Next.js workspace-root warning from multiple lockfiles (`turbopack.root` or workspace cleanup)
- [ ] QA polished business workspace with signed-in business data
- [ ] Verify compact Overview, Actions, Build, Deploy, Tools, Activity, and Settings tabs
- [ ] Verify GitHub and Vercel controls remain reachable from Build/Deploy
- [ ] Verify tool approvals still work from Tools
- [ ] Verify mobile sticky next-action bar and horizontal tab scrolling
- [ ] Verify production deployment for the polished business workspace flow
- [ ] Improve real `/api/generate-blueprint` route — stream OpenAI structured output to BlueprintPreview
- [ ] Build **Mission Control dashboard shell** — authenticated layout with sidebar nav and placeholder panels
- [ ] Wire up **Early Access CTA** to a waitlist form (email capture, no backend yet — can use a form service)
- [ ] Add Supabase persistence

---

## Later

- [ ] Add real AI blueprint generation (OpenAI API + Vercel AI SDK)
- [ ] Add Supabase auth (magic link or GitHub OAuth)
- [ ] Add Supabase database (projects, blueprints, tasks, users)
- [ ] Add tool registry (catalog of integrations bucks.ai can use)
- [ ] Add GitHub App integration (repo creation, commit, PR automation)
- [ ] Add Vercel deployment automation
- [ ] Add analytics (PostHog)
- [ ] Add outreach/CRM pipeline
- [ ] Add Stripe billing

---

## Blocked

_Nothing blocked right now._

---

## Done

- [x] Project scaffold: Next.js 16 + TypeScript + Tailwind v4 + App Router
- [x] Agent handoff files created
- [x] Landing page foundation built
- [x] Build **Idea Intake form** — multi-step form: name, idea, goal, budget, timeline, constraints
- [x] Build **mock Blueprint Preview** — intelligent frontend-only Mission Control dashboard for generated launch blueprints
- [x] Build Vercel deployment execution UI for saved business detail pages
- [x] Build Execution Status / Run History backend layer
- [x] Build Execution Command Center UI for saved business detail pages
- [x] Polish business workspace UX with compact components and dashboard re-entry cards
- [x] Build Operating Team UI for the 21-agent registry and agent run history
