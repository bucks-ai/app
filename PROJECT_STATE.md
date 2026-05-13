# PROJECT_STATE.md

## Current Phase
**Functional Prototype**

## Current Milestone
Surface Unification — Intake and Tools Operator Console Aesthetic

## Current Working Feature
Vercel deployment execution UI on saved business detail pages.

## Last Known Working State
- Next.js 16 app initialized with TypeScript, Tailwind v4, App Router, `src/` directory
- Homepage fully redesigned with 10 landing components under `src/components/landing/`
- `/intake` visually unified as a launch-sequence wizard and Mission Control blueprint output
- `/tools` visually unified as a permission-layer/control-room registry
- Design system: `#080808` background, `#4F46E5` accent, amber human-required states, red blocked/risk states, minimal green success treatment, no emoji, no fake social proof
- All routes (`/`, `/intake`, `/tools`, `/api/generate-blueprint`) building successfully
- `npm run lint` — clean
- `npm run build` — passing (see AI_CHANGELOG.md for latest run result)

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
│   │   ├── landing/       ← Homepage redesign (10 components, current)
│   │   ├── ui/            ← shadcn/ui-compatible primitives
│   │   ├── sections/      ← Legacy landing components (superseded by landing/)
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
| OpenAI API | ⚠️ Route scaffold active; requires `OPENAI_API_KEY` in `.env.local` |
| Vercel AI SDK | ⏳ Not yet integrated |
| LangGraph | ⏳ Not yet integrated |
| Stripe | ⏳ Not yet integrated |
| GitHub App | ⏳ Not yet integrated |
| Vercel Deployment | ⚠️ Frontend UI ready; backend routes expected from separate branch |
