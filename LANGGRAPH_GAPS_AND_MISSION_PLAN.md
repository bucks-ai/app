# LangGraph Gap Analysis + bucks.ai MVP→Enterprise Mission Plan

Audited against actual repo state (runner/langgraph: 48 tools, 5 workers, config.py, overnight.env; app: 215 src files). Everything below is a **delta** — things you do NOT already have.

---

# PART 1 — Missing runner capabilities

Ranked by leverage. "Runner tool" = code in `runner/langgraph/tools/` + config flags + tests, matching your existing pattern.

## Tier 1 — blockers for long unattended runs

### 1.1 Cooldown auto-resume fixes (you asked for this; it's built but broken for real Pro cooldowns)
- `_parse_wait_seconds` only parses relative durations ("in 2 hours"). Claude Code emits absolute times ("Your limit will reset at 6pm"). Add absolute-time parsing (parse clock time + timezone, compute delta).
- Default `CLAUDE_SUBSCRIPTION_COOLDOWN_MAX_WAITS=3` + 1h fallback wait = loop halts before a 5h Pro window resets. Set `0` (unlimited, code already supports) in a subscription profile.
- Cooldown wait time counts against `MAX_RUNTIME_MINUTES` — exclude it, or overnight runs die sleeping.
- Ship `profiles/overnight-subscription.env` (`CLAUDE_AUTH_MODE=subscription`, no ANTHROPIC_API_KEY, `MAX_WAITS=0`, `WAIT_S=1800`).

### 1.2 External CI gate (GitHub Actions)
Every gate you have runs *inside* the runner. Nothing on GitHub enforces anything — auto-merge to main with `MERGE_APPROVAL_POLICY=auto` overnight has zero external check. One bad merge poisons every subsequent task's baseline.
- `.github/workflows/app.yml`: `npm ci`, lint, `tsc --noEmit`, `next build` (path-filtered to app).
- `.github/workflows/runner.yml`: `pytest tests/ -x -q` (path-filtered to runner/).
- Branch protection on main requiring green checks. Runner merges via PR + checks API instead of raw merge.

### 1.3 Real database/migration tooling
`supabase_tools.py` is 2.5KB — thin. Config has no `DATABASE_URL` / `DIRECT_DATABASE_URL`. LangGraph cannot actually inspect schema, apply migrations, or roll back.
- Add `DATABASE_URL` (pooler) + `DIRECT_DATABASE_URL` (migrations) to config.
- New tool `db_tools.py`: schema inspect, migration apply (respecting sql_environment_gate), migration rollback, seed data, RLS policy listing.
- Migration files in `supabase/migrations/` in-repo so schema state is versioned (right now SQL apparently flows through outbox/inbox approval files only).

### 1.4 Real cost/token accounting
`COST_BUDGET_GUARD` exists but defaults rely on `ESTIMATED_COST_PER_TASK_DOLLARS=0.0` — the guard is effectively blind. Claude Code and Codex CLIs emit actual token/cost telemetry in JSON output mode; parse it per task, accumulate per session, feed the existing guard. Without this, "run 600 prompts" has no true budget brake.

## Tier 2 — the two missing items from your own 28-prompt list

### 2.1 (#21) Learning / experiment memory — **the single biggest missing capability**
Nothing persists across runs except git history and logs. The runner cannot answer "have I tried this before, and did it work?"
- Supabase tables: `runner_task_outcomes` (task_id, worker, attempts, failure_classes, resolution, duration, cost), `runner_lessons` (pattern → guidance).
- Write path: `update_logs_and_state` inserts an outcome row per task.
- Read path: planner/mission-compiler pulls top-K relevant lessons into context before generating tasks.
- Start dumb (keyword match), upgrade to embeddings later. This is what makes run #10 better than run #1 — nothing else on this list compounds like this.

### 2.2 (#20) Analytics/observability connector layer
The improvement loop ("observe → diagnose → ship") is blind — the runner can deploy but cannot see production.
- `posthog_tools.py`: query funnels, event counts, top drop-off (PostHog REST API; app is already instrumented with posthog-js).
- `sentry_tools.py`: list new/regressed issues since last deploy (add Sentry to the app first — Part 2, M1).
- `vercel_tools.py` extension: runtime logs + error rate for latest deployment.
- These feed the planner: "landing conversion is X, top error is Y → generate fix tasks."

## Tier 3 — capability expansion

### 3.1 Web research tool
No tool in `tools/` can touch the web (beyond GitHub/Vercel APIs). The planner cannot do market research, competitor checks, or read docs. Add one: Tavily (simplest API) or Firecrawl (crawl+extract). `research_tools.py`: search(query), fetch(url→markdown). Gate behind `RESEARCH_TOOLS_ENABLED`.

### 3.2 Slack interactive approvals (approve from your phone)
Approvals currently require placing files in `inbox/` on your machine — you are the bottleneck at 2am. Upgrade Slack from webhook → bot token + Socket Mode: approval requests post as messages with Approve/Reject buttons; handler writes the inbox file. Your existing gates (SQL, merge, strategic, resource) all keep working — the button just automates the file drop. This single tool multiplies practical autonomy more than any new gate.

### 3.3 Artifact/evidence storage
Playwright screenshots, validation reports, eval outputs currently live in `.runtime/` (local, gitignored, lost). Add `artifact_tools.py` → upload to Supabase Storage, link in Slack notifications + run records. Needed for "document the hell out of it" proof later.

### 3.4 Parallel workers via git worktrees
Workers dispatch serially. For 100+ task missions, add worktree isolation (one branch = one worktree = one worker) and run 2–3 workers concurrently on non-conflicting tasks (mission compiler already produces dependencies — use them for scheduling). Do this only AFTER 1.2 CI exists; parallel merging without external checks is how you destroy main twice as fast.

### 3.5 Runner → app visibility
The app has `agent_runs` API + Operating Team UI, but the Python runner doesn't report into it (supabase_tools too thin). Add run/task reporting into the app's `agent_runs` tables so bucks.ai's own dashboard shows real runner activity. This is also the first step of the endgame: the runner becoming bucks.ai's production execution engine, not a dev-side tool.

### 3.6 Secrets broker
`.env` files only. Fine solo; not fine when the runner manages per-business credentials for launched startups. Adopt Infisical or Doppler; runner fetches at start; `resource_gate` requests missing secrets by NAME (never value — your AGENTS.md rule already says this). Do at M8, not now.

## Explicitly NOT recommended as runner tools now
Stripe/email/CRM/ad-platform tooling belongs to the **product** (bucks.ai features, built as missions below), not the runner. The runner needs to *build and verify* those integrations, not own them. Ads APIs (Meta/Google/TikTok): skip entirely until a launched business has organic traction — burn rate with no learning otherwise.

---

# PART 2 — Mission plan: bucks.ai MVP → enterprise

Format matches your seeded mission queue: each mission compiles to 15–60 tasks with acceptance criteria. **Order matters** — each mission's verification depends on the previous one. Human-required setup is listed per mission (things LangGraph cannot do: account creation, terms, payment onboarding).

## M0 — Runner hardening (mostly manual/you, ~1 week)
Everything in Tier 1 above: cooldown fixes, CI + branch protection, db_tools + DATABASE_URL, real cost accounting. Plus Slack interactive approvals (3.2) if you want overnight runs to not stall.
**Done when:** a 25-task overnight subscription-mode run completes with ≥1 real cooldown survived, all merges gated by green CI.
**Human setup:** GitHub Actions enabled; branch protection; DATABASE_URL/DIRECT_DATABASE_URL from Supabase dashboard; Slack app with bot token.

## M1 — Production trust layer (~30 tasks)
The app is a functional prototype; make it safe to put real users and money on.
- Auth check on EVERY API route (`/api/generate-blueprint` currently unauthenticated — anyone can burn your OpenAI credits).
- Zod schemas for all request bodies AND all AI outputs (blueprint JSON is currently `JSON.parse(...) as BusinessBlueprint` — a cast, not validation). Model name → env var.
- Rate limiting (Upstash Ratelimit) on AI + mutation endpoints.
- Startup env validation (zod env schema) — fail fast, not silently degrade.
- Sentry integration (client + server) with source maps.
- Supabase RLS audit: verify every table with user data has policies; write pgTAP or SQL tests for them.
- Central error envelope + logging convention for API routes.
**Done when:** no unauthenticated mutating/AI route; malformed AI output cannot reach UI; Sentry captures a thrown test error in production.
**Human setup:** Sentry account + DSN; Upstash account.

## M2 — Verification engine (~20 tasks)
Turn the built-but-dormant E2E capability on, so every later mission is machine-verifiable.
- Dedicated Supabase test user + seeded test business.
- `E2E_ENABLED=true`; Playwright suite: signup→login, intake→blueprint, dashboard load, tool-permission queue, business detail tabs.
- E2E in CI on preview deployments (Vercel preview URL per PR).
- UI flow config (`UI_FLOW_CONFIG_PATH`) covering the golden path; screenshots uploaded as artifacts (3.3).
**Done when:** a PR that breaks login cannot merge; runner validates deployed preview, not just `npm run build`.
**Human setup:** test user credentials in env.

## M3 — Analytics + observation loop (~15 tasks)
Finish your Phase 8 properly, both sides.
- PostHog event taxonomy: signup, intake_started, blueprint_generated, business_saved, tool_approved, repo_created, deploy_created — the activation funnel.
- Server-side capture for API events (posthog-node), not just client.
- Funnel + retention dashboards defined as code/docs.
- Runner-side `posthog_tools.py` + `sentry_tools.py` (Tier 2.2) so the loop can read what it shipped.
**Done when:** you can answer "how many users reached a deployed repo this week" from PostHog, and the runner can fetch that number.
**Human setup:** PostHog project API key (read), Sentry auth token.

## M4 — bucks.ai runs its own runner (the architectural pivot, ~40 tasks)
Today: runner builds bucks.ai. Enterprise: runner IS bucks.ai's engine. Bridge them.
- Job contract: bucks.ai writes a mission row (Supabase `missions` table: business_id, goal, constraints, status); runner polls/claims, executes, streams task status back into the app's existing `agent_runs` tables.
- Operating Team UI shows live runner activity (already scaffolded — wire real data).
- Approval surfaces in-app: human_required_actions queue backed by the same inbox/outbox protocol (and Slack buttons).
- Sandbox-per-business: runner profile that targets a business's OWN repo (created by the app's create-repo flow) instead of bucks-ai/app — your external-containment model, formalized: scoped GitHub token per business repo, separate Vercel project, capped keys.
**Done when:** clicking "Execute" on a saved business in the dashboard causes the runner to scaffold, build, and deploy that business's repo with status visible in the UI.
**Human setup:** none new (reuses GitHub/Vercel tokens; per-business fine-grained tokens recommended).

## M5 — Launch one real business through the system (~30 tasks + your sales time)
Not infrastructure — the proof. Pick ONE idea (B2B micro-SaaS, painkiller, reachable buyers).
- Feed it through intake → blueprint → M4 execution → deployed MVP on its own domain.
- Landing page, waitlist, PostHog funnel on the launched product.
- Document every run: prompts in, tasks executed, evidence artifacts. This corpus is the YC application.
**Done when:** a real product is live at a real domain, built ≥80% by the system, with logs proving it.
**Human setup:** domain purchase, any product-specific accounts. You do sales calls.

## M6 — Customer discovery + outreach engine (~40 tasks)
Build only once M5's business needs users (real requirements beat imagined ones).
- Research: `research_tools` (Tavily/Firecrawl) → ICP briefs, competitor maps stored per business.
- Leads: Apollo (or manual CSV import first) → `leads` table, enrichment, scoring.
- Outreach: compliant sequence generator (CAN-SPAM: identity, address, opt-out), Gmail/Resend integration, **drafts by default, sends require approval**, daily send caps as autonomy rules.
- CRM: pipeline view in-app (leads → contacted → replied → demo → paying), reply ingestion, follow-up scheduler.
**Done when:** system produces a 100-lead scored list + personalized drafts for the M5 business, and tracks replies after you approve sends.
**Human setup:** Apollo/Tavily API keys, sending domain + warmup, Google OAuth or Resend.

## M7 — Revenue loop (~30 tasks)
- Stripe test mode: products/prices, Checkout, Customer Portal, webhook handler + event ledger table, subscription state in Supabase, plan gating in-app.
- Revenue dashboard (MRR, churn, failed payments) for each launched business.
- Live mode only after test-mode E2E passes (Stripe test clocks in the Playwright suite).
**Done when:** a test card can subscribe to the M5 business end-to-end and state survives webhook replay.
**Human setup:** Stripe onboarding (identity/bank — legally yours), webhook secret.

## M8 — Business memory + evaluation (~25 tasks)
Your moat layer — now it has real data to remember.
- Experiment log: hypothesis → action → metric → outcome per business.
- Idea scorecard + kill/continue engine using PostHog + Stripe + CRM data.
- Runner lessons memory (Tier 2.1) if not done in M0.
- Weekly auto-generated business review posted to Slack.
**Done when:** the system can argue, with data, whether to iterate or kill the M5 business.

## M9 — Enterprise hardening (~50 tasks; only when there are paying users)
- Orgs/teams/RBAC; multi-tenant isolation audit.
- Audit log table for every autonomous action (agent, why, tool, diff, cost, risk) surfaced in-app.
- Secrets vault (Infisical/Doppler) for per-business credentials.
- Background jobs (Inngest/Trigger.dev) replacing anything long-running in API routes.
- Admin/operator console; usage metering + quotas; parallel workers (Tier 3.4); status page + uptime monitoring.
**Done when:** two unrelated users can each launch a business with zero data or credential overlap, and every autonomous action is auditable.

---

## Human-only checklist (LangGraph can never do these — schedule yourself)
Stripe identity/bank onboarding · domain purchases beyond budget rules · Google OAuth consent screens · Slack app installation · accepting ToS for any new service · business entity filing · sending first outreach batches (approve) · sales calls.

## Sequencing logic (why this order)
M0–M2 make the machine trustworthy → M3 gives it eyes → M4 makes the product and the machine the same thing → M5 produces proof → M6–M7 produce revenue → M8 produces compounding → M9 produces "enterprise." Skipping ahead (e.g., M9 infra before M5 proof) builds power nothing uses — that's where the previous plan was drifting.
