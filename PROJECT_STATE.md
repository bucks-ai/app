# PROJECT_STATE.md

## Current Phase
**Foundation**

## Current Milestone
Initial app foundation + shared agent handoff system

## Current Working Feature
Landing page — Hero, What We Do, How It Works, Autonomy Boundaries, Early Access CTA

## Last Known Working State
- Next.js 16 app initialized with TypeScript, Tailwind v4, App Router, `src/` directory
- Landing page components created under `/src/components/sections/`
- Root layout and page wired up
- `npm run build` passing (see AI_CHANGELOG.md for latest run result)

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
│   │   ├── ui/            ← shadcn/ui-compatible primitives
│   │   ├── sections/      ← Landing page section components
│   │   └── shared/        ← Navbar, Footer, etc.
│   │
│   ├── lib/               ← Utilities and helpers
│   ├── types/             ← Shared TypeScript types
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
| Supabase | ⏳ Not yet integrated |
| OpenAI API | ⏳ Not yet integrated |
| Vercel AI SDK | ⏳ Not yet integrated |
| LangGraph | ⏳ Not yet integrated |
| Stripe | ⏳ Not yet integrated |
| GitHub App | ⏳ Not yet integrated |
| Vercel Deployment | ⏳ Not yet integrated |
