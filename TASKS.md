# TASKS.md

> Update this file after every agent session. Move tasks between buckets as work progresses.

---

## Now

- [x] Initialize Next.js app with TypeScript, Tailwind, App Router, src-dir
- [x] Create agent handoff system (AGENTS.md, CLAUDE.md, PROJECT_STATE.md, TASKS.md, DECISIONS.md, AI_CHANGELOG.md)
- [x] Create .env.example with all placeholder env vars
- [x] Build initial landing page (Hero, What We Do, How It Works, Autonomy Boundaries, CTA)

---

## Next

- [ ] Build **Idea Intake form** — multi-step form: name, idea, goal, budget, timeline, constraints
- [ ] Build **mock Blueprint Preview** — static UI showing what a generated business blueprint looks like
- [ ] Build **Mission Control dashboard shell** — authenticated layout with sidebar nav and placeholder panels
- [ ] Add **Navbar** and **Footer** components to shared/
- [ ] Wire up **Early Access CTA** to a waitlist form (email capture, no backend yet — can use a form service)

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
