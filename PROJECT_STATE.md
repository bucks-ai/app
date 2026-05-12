# PROJECT_STATE.md

## Current Phase
**Functional Prototype**

## Current Milestone
Idea Intake + Mock Launch Blueprint flow

## Current Working Feature
Landing page CTA to `/intake` plus a frontend-only 4-step Idea Intake wizard with Blueprint Preview

## Last Known Working State
- Next.js 16 app initialized with TypeScript, Tailwind v4, App Router, `src/` directory
- Landing page components created under `/src/components/sections/`
- New `/intake` route added with a client-side multi-step wizard
- Mock business blueprint generator added under `/src/lib/mock-blueprint.ts`
- Blueprint Preview renders business summary, stack, permissions, GTM, analytics, risks, and next autonomous actions
- Root layout and page wired up
- `npm run lint` and `npm run build` passing (see AI_CHANGELOG.md for latest run result)

---

## How to Run Locally

```bash
cd /Users/satvikranga/bucks-ai
npm install        # first time only
npm run dev        # http://localhost:3000
```

## Known Commands

| Command | Purpose |
|---------|---------|
| `npm run dev` | Start dev server |
| `npm run build` | Production build check |
| `npm run lint` | ESLint |
| `npm run start` | Run production build |

---

## Known Blockers

_None at this time._

---

## Important File Map

```
/
├── AGENTS.md              ← Canonical agent instructions (read this first)
├── CLAUDE.md              ← Claude-specific session protocol
├── PROJECT_STATE.md       ← This file
├── TASKS.md               ← Work queue
├── DECISIONS.md           ← Architecture decisions log
├── AI_CHANGELOG.md        ← Per-session change log
├── .env.example           ← Placeholder env vars (committed)
├── .env.local             ← Real secrets (NEVER committed, gitignored)
│
├── src/
│   ├── app/
│   │   ├── layout.tsx     ← Root layout (fonts, metadata)
│   │   ├── page.tsx       ← Landing page (/)
│   │   └── globals.css    ← Global Tailwind imports
│   │
│   ├── components/
│   │   ├── intake/       ← Idea Intake wizard + Blueprint Preview components
│   │   ├── ui/            ← shadcn/ui-compatible primitives
│   │   ├── sections/      ← Landing page section components
│   │   └── shared/        ← Navbar, Footer, etc.
│   │
│   ├── lib/               ← Utilities and helpers, including mock blueprint generation
│   ├── types/             ← Shared TypeScript types, including startup blueprint contracts
│   └── hooks/             ← Custom React hooks
│
└── public/                ← Static assets
```

---

## Integrations Status

| Integration | Status |
|-------------|--------|
| Next.js App Router | ✅ Active |
| TypeScript | ✅ Active |
| Tailwind CSS v4 | ✅ Active |
| Idea Intake Wizard | ✅ Active (frontend-only mock flow) |
| Mock Blueprint Generator | ✅ Active (local TypeScript logic) |
| Supabase | ⏳ Not yet integrated |
| OpenAI API | ⏳ Not yet integrated |
| Vercel AI SDK | ⏳ Not yet integrated |
| LangGraph | ⏳ Not yet integrated |
| Stripe | ⏳ Not yet integrated |
| GitHub App | ⏳ Not yet integrated |
| Vercel Deployment | ⏳ Not yet integrated |
