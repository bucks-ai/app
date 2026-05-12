# DECISIONS.md — Architecture Decision Log

> Record significant architectural choices here so future agents and contributors understand the WHY, not just the WHAT.

---

## ADR-001: Next.js App Router

**Decision:** Use Next.js 16 with the App Router (`/src/app`)
**Why:** Server Components reduce client-side JS; nested layouts simplify dashboard structure; built-in API routes avoid a separate backend for MVP
**Alternatives considered:** Remix, Vite + React SPA
**Status:** Active

---

## ADR-002: TypeScript Strict Mode

**Decision:** TypeScript with strict mode enabled
**Why:** bucks.ai will have complex agent-generated data types; strict typing prevents runtime surprises, especially across the AI-to-UI boundary
**Status:** Active

---

## ADR-003: Tailwind CSS v4

**Decision:** Tailwind CSS v4 (utility-first, no CSS-in-JS)
**Why:** Fast iteration, consistent design tokens, co-located styles. v4 ships as a PostCSS plugin with improved performance.
**Status:** Active

---

## ADR-004: shadcn/ui-Compatible Component Structure

**Decision:** Follow shadcn/ui conventions (`/src/components/ui/`) without adding shadcn as a dependency yet
**Why:** Keeps the door open for one-command `npx shadcn add <component>` later while avoiding premature dependency lock-in
**How to apply:** Primitive UI components live in `/src/components/ui/`; page sections in `/src/components/sections/`
**Status:** Active

---

## ADR-005: Supabase for Auth and Database (deferred)

**Decision:** Use Supabase when auth/database is needed
**Why:** Postgres + Row Level Security is well-suited for multi-tenant founder data; built-in auth with social providers; good Next.js SDK
**When to integrate:** Once Idea Intake form needs persistence
**Status:** Planned, not yet integrated

---

## ADR-006: OpenAI API + Vercel AI SDK for Blueprint Generation (deferred)

**Decision:** Use OpenAI API (GPT-4o) wrapped by Vercel AI SDK for streaming responses
**Why:** Vercel AI SDK handles streaming/tool-call abstraction well with Next.js; GPT-4o is the best available model for structured business planning
**When to integrate:** Once Blueprint Preview needs real AI output
**Status:** Planned, not yet integrated

---

## ADR-007: Vercel for Deployment (deferred)

**Decision:** Deploy to Vercel
**Why:** Zero-config Next.js deployment; preview URLs per PR; Edge Functions available; bucks.ai will eventually automate Vercel deployments for customer projects
**Status:** Planned, not yet integrated

---

## ADR-008: Repo Files as Source of Truth for Agent Sync

**Decision:** All agents (Claude, Codex, etc.) must read and update AGENTS.md, PROJECT_STATE.md, TASKS.md, DECISIONS.md, and AI_CHANGELOG.md before and after sessions
**Why:** Multiple AI agents will work on this repo; without a shared written context, each agent starts blind and creates drift. Repo files outlive any chat session.
**Status:** Active — this is a hard rule
