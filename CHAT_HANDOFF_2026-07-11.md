# bucks.ai — Session Handoff (Fable 5 → Opus 4.8)

**Date:** 2026-07-11
**Purpose:** Complete, self-contained handoff so a fresh chat (Opus 4.8) continues with zero context loss. Covers everything done in the Fable 5 working sessions: runner debugging, missions M2→M4b, all operational incidents and their fixes, the strategy conversation, and the full forward roadmap including far-future vision.
**Read alongside:** `BUCKS_AI_MASTER_ANALYSIS.md` (the canonical July-5 analysis + §13 completion log — the single source of truth for plan progress) and this file. Where they disagree, this file is newer.

**Founder:** Arnav (satvikranga60@gmail.com / arnav144193@gmail.com). Repo: github.com/bucks-ai/app. Local: `~/bucks-ai` (WSL Ubuntu). Runner: `~/bucks-ai/runner/langgraph`.

---

## 0. HOW TO WORK WITH THIS FOUNDER (read first)

- Arnav runs the terminal; the assistant reads/writes files in `~/bucks-ai` directly (WSL UNC path `\\wsl.localhost\ubuntu\home\arnav\bucks-ai`) and hands Arnav exact copy-paste commands. He is not a deep engineer — give **complete, literal commands**, one logical block at a time, and never leave a `<placeholder>` in a command (he will paste it literally and it will error — this happened with `<N>`).
- He edits `.env` via `nano`. Secrets live in `runner/langgraph/.env` (runner) and `~/bucks-ai/.env` (app; there is **no** `.env.local` on this machine — the app reads `.env`). Never print secret values.
- Preference: concise, direct, honest. Push back when he's wrong — he explicitly wants disagreement, not flattery. He responds well to "strongest idea / kill this / reframe that" verdicts.
- The runner executes **whatever git branch is checked out** when `run-loop` launches. Always `git checkout main && git pull` before launching. This caused a full wasted day early on (runner ran unfixed code from stale task branches).

---

## 1. WHAT bucks.ai IS (one paragraph)

A self-driving startup operator for AI/software businesses. Two layers: **(a) the app** (`src/`, Next.js 16 / TS / Tailwind4 / Supabase / Vercel / PostHog / Sentry) — intake → AI blueprint → tool permissions → repo → deploy → Execution Command Center; **(b) the LangGraph runner** (`runner/langgraph/`, Python) — an autonomous dev loop: ChatGPT planner + Claude Code / Codex CLI workers + ~50 flag-gated safety/quality tools, that writes code, runs checks, opens PRs, merges through CI, deploys, and validates. The runner has been building bucks.ai itself. **The M4 pivot (in progress) turns the runner into bucks.ai's production execution engine** so it can build *customer* businesses in per-business sandboxes, not just itself. Endgame: founder supplies goal + approvals; bucks.ai authors, executes, verifies, and learns — for itself and every business it runs.

**Goals & clock:** YC (target Winter batch, ~Nov 2026 deadline, ~4 months out), path to ~$25k MRR / $300k-yr, Stanford admission pillared on the first two. **The entire strategy compresses to: produce verifiable proof the system launches real revenue businesses.** YC odds: idea-only 1–3%, working demo 5–8%, one launched revenue business 10–15%, multiple repeatable launches 20%+.

**Business model (planned):** Phase 1 paid launch sprints ($1k–2.5k) → Phase 2 monthly operator subscription ($99–799/mo) → Phase 3 usage credits → Phase 4 (careful) revenue share. **First ICP:** AI automation agency owners + serious solo/indie AI-SaaS founders (18–35, some money, hate execution grunt work). Explicitly NOT: nontechnical idea people, broke students, enterprises, regulated industries.

---

## 2. MISSION PROGRESS — COMPLETE PICTURE

Operating rule (never violate): **seed ONE mission → runner executes in batches → verify done-when criteria → founder ~1hr review → seed next.** Never pre-queue multiple missions; each mission's verification informs the next seed. This rule has repeatedly caught compounding problems.

Missions are seeded via SQL into the Supabase `missions` + `mission_tasks` tables (the runner's seeded-mission queue polls them). Seed files live in `supabase/mNN-seed-mission.sql`. To seed: `git show <branch>:supabase/<file>.sql | clip.exe` → paste into Supabase SQL editor → Run. Launch: from `main`, `cd runner/langgraph && source .venv/bin/activate && set -a; source .env; set +a && python approvals_daemon.py & && python -u main.py run-loop 2>&1 | tee -a logs/runloop.out`.

### DONE (verified, in §13 of master analysis):
- **M0 — Runner hardening:** CI workflows, cooldown fixes, DB tooling, cost accounting, Slack interactive approvals, PR-based merge flow. (Pre-dates these sessions; see master analysis.)
- **M1 — Production Trust Layer (25 tasks):** auth on every route + route-inventory guard test, zod on all request bodies AND AI outputs, Upstash rate limiting (in-memory fallback), Sentry wiring (code only, DSN added later), RLS audit + fix migration + live verification, error envelope, security headers.
- **M2 — Verification Engine (20 tasks):** E2E seed script + dedicated E2E Supabase project, full Playwright suite (auth/intake/dashboard/business-tabs/tools), fake-AI fixture mode with production guard, blocking `E2E (Playwright)` CI job + informational Vercel-preview job, runner UI-flow config, screenshot artifacts, flaky quarantine, DoD file-claim verification, seeded-queue strict-stop fix, runbook + verification report. The E2E gate caught **six real bugs** before going green (Node20 WebSocket, MX record, mailer rate-limit, confirm-email flow, fake-AI prod guard, tools locator).
- **M3 — Analytics + Observation (10 tasks):** 11-event canonical taxonomy, server+client PostHog capture, test-traffic guard, dashboards-as-code, runner-side `posthog_tools`/`sentry_tools`, `python main.py analytics-report` CLI. Done-when verified live: report answers "Users who reached a deployed repo this week: 0" and Sentry caught the first real prod bug (`JAVASCRIPT-NEXTJS-1` TypeError).
- **M4a — Runner-App Integration batch 1 (10 tasks):** intake instrumentation, Sentry bug fix, `poll_pr_checks` hardening, session-local attempt counts, funnel walkthrough, agent-runs streaming, Operating Team UI on real runs, in-app approval queue (file-compatible with Slack daemon), **Execute button + `runner_target` safety gate**, verification report. Founder clicked Execute live → mission created, status `queued`, safety gate holding. See §3 for the critical finding.

### IN PROGRESS (running as of this handoff):
- **M4b — Sandbox-per-Business Execution batch 2 (9 tasks)** — seed file `supabase/m4b-seed-mission.sql`, PR #83 (`feature/m4b-seed`). SQL already applied to Supabase; loop launched. Tasks:
  1. `m4b-01-migrations-wiring` — un-applied migrations become impossible to miss (loud `migrations_pending` event + optional `AUTO_APPLY_MIGRATIONS`). **Fixes the root cause of the M4a critical finding.**
  2. `m4b-02-execute-cta-and-approvals-state` — promote Execute to a **primary CTA** (founder couldn't find the 10px chip); disambiguate approvals empty state.
  3. `m4b-03-live-self-mission-demo` — `create-self-mission` CLI + prove claim→agent_runs→UI live.
  4. `m4b-04-business-sandbox-config` — `business_sandbox` table (**stores secret NAMES only, never values**), Settings-tab UI, API route. Migration `0004_business_sandbox.sql`.
  5. `m4b-05-runner-foreign-repo-execution` — runner clones/works in isolated per-business workspace with scoped token; **hard refusal to ever run a business mission against the bucks-ai repo.**
  6. `m4b-06-business-vercel-deploy` — deploy/poll target the business's Vercel project + token, smoke check on live business URL.
  7. `m4b-07-claim-gate-lift` — lift the `runner_target=self`-only gate ONLY when `BUSINESS_EXECUTION_ENABLED=true` AND full sandbox config exists AND named secrets resolve.
  8. `m4b-08-execute-end-to-end-demo` — **the M4 done-when**: click Execute on a real business, runner builds+deploys ITS repo. **Needs founder mid-run** to provide scoped GitHub/Vercel tokens (surfaced via resource gate, which auto-resumes after fulfillment).
  9. `m4b-09-verification-report` — M4 mission report + recommended M5 business-selection criteria.
- Expect during M4b: a Slack SQL-approval for `0004_business_sandbox.sql` (read then approve), and m4b-08's resource-gate ping for sandbox tokens.

### NEXT (post-M4b — REVISED sequence after the 2026-07-11 strategy session; now written into `STRATEGY.md`):

**`STRATEGY.md` is now WRITTEN** (repo root, 2026-07-11). It is the doctrine doc: convenience thesis, "external containment enables convenience," parent-child provisioning + A/B/C tool table, the canonical Phase 1-5 target user experience, the Spotify-not-Lovable free/paid tiering, market selection, and the IN/REJECTED ideas ledger. Every mission below should build toward it.

*(Sequence revised again 2026-07-21: babysitter pulled forward into its own small mission M4c per founder decision — "right now I am the one planning it mission to mission and we need to fix that." The old omnibus M4c is split; broker/UI/tiering move to their proper post-M5 slots per `STRATEGY.md` §7.)*

1. **M4c — Loop Babysitter & Continuous Operation (~6-7 tasks, seed immediately after M4b closes):** the loop stops needing the founder. **Approval model (founder decision 2026-07-21): sign-off happens ONCE, at the PLAN level — the founder approves the whole mission roadmap upfront and never seeds individual missions or tasks again.** Per-mission seeding was an unnecessary gate: if the plan is approved, re-approving each piece of it kills convenience for nothing. The only human gates that remain are the ones that carry NEW risk: SQL approvals, resource/credential gates, budget caps, and any mission NOT in the approved plan.
   - **Roadmap-as-data:** the approved mission plan (M4d→M9 and beyond) lives as structured data (a `mission_backlog` table or checked-in specs), each entry pre-written to full seed quality with an `approved` flag set once by the founder. This replaces hand-pasted seed SQL entirely.
   - **Auto-seeding + mission auto-chaining:** when the current mission completes clean, the babysitter seeds and claims the next approved backlog entry automatically. The machine never idles while approved work exists.
   - **Watchdog wrapper:** auto-restart the loop on any exit that isn't a hard human gate (approval pending, resource gate); Slack ping either way. Fresh-session-per-invocation already shipped, so restart is safe.
   - **Limits-aware pause/resume:** on rate-limit/budget/API-quota exhaustion, compute the reset window, sleep it out, resume — never die on exhaustion. (Founder's spec verbatim: "constantly running, only stops when limits are exhausted, then starts up right after.")
   - **Heartbeat + stall detection:** periodic `babysitter_heartbeat` event; if the loop is silent past a threshold, restart it and log loudly. (The VPS move is a founder-infra task, tracked separately — laptop-closed still stops the company until then.)
   - **Doctrine ingestion:** the planner reads `STRATEGY.md` as context on every planning call, so mission plans are doctrine-shaped by construction. This is the first of the three code paths that make the strategy doc executable (see `STRATEGY.md` §6.1 preamble; the other two are M4d and M7.5).
   - *Product mirror:* this same approve-the-plan-once model IS the user experience — a customer approves their business blueprint once and the machine runs every mission under it without coming back. M4c is bucks.ai dogfooding its own convenience doctrine.
2. **M4d — Hardened-by-Default Scaffold (~3-4 tasks, SMALL):** every business bucks.ai builds ships secure. The mission compiler applies the M1 hardening playbook (auth, zod validation, rate limits, RLS, security headers, route-inventory test) to every scaffolded business by default, with a hardening-report artifact per build. This is both a differentiator ("hardened by default") and the internal dogfood of the M5 service.
3. **M5 — Launch ONE real business:** selection now gated by the **Market Selection Algorithm (`STRATEGY.md` §6.1** — demand-evidence sourcing, 7-criteria scoring, validation ladder, kill gates; run manually by the founder this first time). **CONFIRMED first test business: the security-hardening sprint service** (urgent event-triggered painkiller, buyers self-identify when breached, existing spend proven, demos the engine on a foreign repo = M4b, M1 already built the playbook). Must still pass the §6.1 validation ladder (landing page test → buyer conversations → pre-sold paid pilot) before full build. Run intake→blueprint→M4 execution→deployed MVP on a real domain; **document every run — this corpus IS the YC application.**
4. **M6 — Customer discovery + outreach** (research tools, leads table, compliant sequences, CRM). AFTER M5 needs users. Fold in TikTok/IG-video→build as an intake modality + marketing engine here (strong, low cost).
5. **M7 — Revenue loop** (Stripe test→live via Connect per the provisioning doctrine, revenue dashboard).
6. **M7.5 — Market Radar (NEW 2026-07-21):** automate `STRATEGY.md` §6.1 — pain-mining collectors (Reddit/IH/HN/G2 reviews via API within ToS), the 7-criteria scoring rubric encoded, ranked opportunity briefs with evidence links, founder approves/rejects each. This is the "bucks.ai proposes, human approves" endgame's first real piece; deliberately AFTER one manual M5 pass proves the rubric on a real launch.
7. **M8 — Business memory + evaluation** (`runner_lessons`, experiment log, kill/continue engine) — the compounding moat + cross-user learning (consent/anonymization guardrail per `STRATEGY.md` §6). Kill-gate outcomes from §6.1 feed this directly.
8. **M9 — Enterprise hardening** (orgs/RBAC, multi-tenant isolation, audit log, secrets vault, background jobs) — only when paying users exist.

**Deferred to post-M5 (unchanged in substance, moved out of the old omnibus M4c):** Provisioning & Credential Broker (parent-child + OAuth "Connect all" + secret-name vault), node-graph operator UI, free/paid tiering scaffolding — all per `STRATEGY.md` §7 sequencing.

---

## 3. OPERATIONAL PLAYBOOK — every incident hit this session and its fix

These recurred; a new session WILL hit them again. This is the troubleshooting bible.

1. **Stale session state killed restarts.** `run-loop` used to resume `stop_reason`/`loop_count`/`consecutive_failures`/`started_at` from `.runtime/state.local.json` → instant stop on restart. **Fixed** (main.py `start_fresh_session`): every run-loop invocation is a fresh session. No `reset-state` needed anymore.
2. **Approved resource requests never requeued the blocked task.** Slack Approve writes the inbox file but nothing flipped the task `blocked→queued`. **Fixed:** `load_next_task` auto-requeues blocked tasks whose `inbox/{task_id}_resources_provided.txt` exists.
3. **pytest spammed real Slack** with mocked errors ("simulated db error" etc.) because `log_event` fans out to Slack and `.env` was sourced. **Fixed:** guard in `log_tools._maybe_notify_slack` skips fan-out under `PYTEST_CURRENT_TEST` (stub-aware, so tests asserting fan-out still pass) + `tests/conftest.py` strips Slack env.
4. **`chatgpt_no_task` stop while tasks were retry-backoff-queued.** Loop fell through to planner instead of waiting. **Fixed:** `next_retry_eta` + backoff-wait in `load_next_task` (sleeps out the shortest backoff, ≤30min).
   - All four above shipped in PR #52 (`feature/runner-fixes-v2`). Applier script pattern: a `runner_fixes_vN.py` at repo root, idempotent, aborts loudly if an anchor is missing.
5. **`CLAUDE_CLI_TIMEOUT_S` default 1800 killed the full-E2E verification task.** Set `CLAUDE_CLI_TIMEOUT_S=3600` in `.env` (must be in `.env`, not `export`, to survive new shells).
6. **`PR_CHECKS_TIMEOUT_S` default 900 too short** for 2am queued GitHub runners. Raised to 1800 in `.env`.
7. **THE BIG RECURRING ONE — "no checks reported" / PR checks never scheduled.** Multiple root causes, all present this session:
   - **GitHub event drop:** a push that didn't trigger a workflow stays checkless forever; GitHub doesn't retro-schedule. Fix: force a fresh `synchronize` event — `git merge origin/main` on the branch + push, OR `gh api -X PUT repos/bucks-ai/app/pulls/N/update-branch`, OR close/reopen the PR.
   - **Conflicted PR (`mergeable:CONFLICTING`/`DIRTY`):** no merge ref exists → no checks ever. `update-branch` returns 422. Fix: `git checkout <branch> && git merge origin/main`, resolve conflicts by hand, push. Conflicts this session were all **additive keep-both** (two tasks touched config.py/README/events.ts). One case (`m4a-01`) was **two workers implementing the same task twice** (retry on a stale base) — kept main's version, deleted the branch's parallel files.
   - m4a-03 (`poll_pr_checks` hardening) now handles the event-drop case automatically: grace window → auto update-branch on dirty/behind → distinct `pr_checks_no_runs` fail-fast instead of a 30-min burn.
8. **Circuit breakers that stop the loop:** `consecutive_failures` (3), `repeated_task` attempt count (persisted across sessions until m4a-04 made it session-local — clear `task_attempt_counts` in `state.local.json` when requeuing after an externally-caused failure), `stale_run` watchdog (60-min hard stop). When a batch stops on one of these, the cause is usually upstream (a checkless PR), not the task itself.
9. **Standard requeue-and-relaunch snippet** (after fixing whatever blocked a batch):
   ```python
   import json, pathlib
   p = pathlib.Path(".runtime/tasks.local.json"); tasks = json.loads(p.read_text())
   for t in tasks:
       if t["id"].startswith("mNN-") and t["status"] in ("failed","queued"):
           t["status"]="queued"; t["error"]=None
           t.pop("retry_not_before",None); t.pop("retry_count",None)
   p.write_text(json.dumps(tasks, indent=2))
   s = pathlib.Path(".runtime/state.local.json"); st = json.loads(s.read_text())
   st["task_attempt_counts"] = {}; s.write_text(json.dumps(st, indent=2))
   ```
10. **PR merge order tax:** branch protection requires PRs be up-to-date with main; merging PR A invalidates PR B's base. Sequence: update-branch → checks → merge, per PR. `gh` version here predates `gh pr update-branch` — use `git merge origin/main` + push, or `gh api -X PUT .../update-branch`.
11. **gh version quirks:** no `gh pr update-branch` subcommand (use the API call). `--log-failed` sometimes returns empty right after a run — fall back to `gh run view <id>` (inline annotations) or the browser.

---

## 4. STRATEGY CONVERSATION — 8 founder ideas + verdicts (Fable 5's take, for the new session to continue)

Founder brought 8 ideas. Verdicts given (new session should treat these as a starting position, not gospel — but the reasoning is sound):

1. **Mass side-hustle spray for cash flow** — REFRAME. As revenue it's negative-cashflow lottery thinking (fixed costs per business, "one pops off" ignores that winners need distribution). As **live-fire pipeline testing + failure-data generation + proof artifacts**: keep 3–5 capped micro-launches as M4b/M5 shakedown.
2. **Build-to-app-store service** — thesis (sell convenience not novelty) is CORRECT and already bucks.ai's positioning. Specific idea blocked by Apple/Google human identity+review (Type-C, see below). Future SKU, not now.
3. **Codified strategy/doctrine** — **BEST IDEA. Pull forward to now** (was M8-ish). A written doctrine the planner reads before generating: target markets, selection criteria, kill criteria, building playbooks. Prerequisite for the "bucks.ai proposes, human approves" endgame. → `STRATEGY.md` (see §5).
4. **Learn from failures across all users** — VALIDATED, this is M8 + the long-term moat. M3 analytics is its data substrate. Flag: cross-user learning needs consent in terms + anonymization/aggregation from day one.
5. **Auto-file patents** — KILL. Regulated legal practice, software patents rarely worth it for ICP, per-filing cost. Not even backlog.
6. **TikTok/IG video → built app** — it's a FEATURE (intake modality), not a product. Cheap to add post-M5 (video→transcript→blueprint). Best value is marketing content ("built from this viral video, here's the log").
7. **Automated security for vibe-coded startups** — STRONG, and **M1 already built the playbook** (auth/zod/rate-limits/RLS/headers/route-inventory test). Two forms: (a) built into every bucks.ai launch as a differentiator (~free, it's a template); (b) **standalone hardening-sprint offer — top M5 wedge candidate** (painkiller, urgent, buyers post publicly when breached, demos the engine on someone else's repo = literally M4b). Cautions: written permission before scanning; never market "unhackable," sell "hardened against common killers."
8. **The wizard / max-convenience credential setup** — the founder's favorite; see §4a. North star right, staging needs correction.

### 4a. THE WIZARD / PROVISIONING & CREDENTIAL BROKER (deep dive — founder's priority)

Founder wants: paste a command → wizard asks for broad trust → it sets up all accounts/auth/env, even invents the startup idea → button-press convenience. He accepts high-risk/high-reward and the trust barrier.

**Fable 5's reframe (the key architectural insight):** split "account setup" into three types, each a different solution:
- **Type A — official provisioning/management API exists.** Vercel, Supabase (Management API creates projects), GitHub, Stripe Connect, Cloudflare, Resend. bucks.ai calls the API with the founder's **one master token** and provisions **scoped child resources per business.** Fully legitimate, no CAPTCHA, no password storage. **This is the clean path.**
- **Type B — signup exists but no account-creation API (e.g. PostHog).** Solution: create the **parent org once by hand**, then bucks.ai creates a **project + project-key per business via API under that parent.** Never hand-create another. (Browser automation is a last-resort ToS-gray fallback — avoid as core infra.)
- **Type C — genuinely human-only** (domain over budget, Stripe identity/bank, Apple/Google identity, entity filing, ToS acceptance). Cannot be automated by anyone — legal, not technical. Convenience play: **reduce to one tap** — bucks.ai pre-fills everything, founder taps a single approval/deep-link. Surface via the in-app approval queue (built in M4a).

**Trust solved by design, not by taking passwords:** OAuth + scoped tokens + a real vault (Infisical/Doppler; storing secret **names** not values — M4b's sandbox already does this). This is *why the founder trusts Claude* — scoped grants, revocable, not passwords. **Correction to founder's "high risk" framing:** OAuth/scoped design delivers ~90% of the convenience at LOW risk; the password-vault version buys ~5% more for company-ending breach exposure. Take the 90%.

**Where else it applies — "the entire pipeline":** once the 3-tier broker exists, every "Arnav go set up X" collapses — .env provisioning (the PostHog/Sentry annoyance), SQL migrations (m4b-01), domain purchase under a cap (Type-A API), deploys/repos/analytics projects (already Type-A). Unifying principle for `STRATEGY.md`: **"external containment enables convenience" — the more rigorously scoped/sandboxed each grant, the more you can safely automate on top.** The wizard is that contract at the *setup* layer; the loop babysitter is the same contract at the *execution* layer.

**Sequencing:** spec as a "Provisioning & Credential Broker" mission AFTER one revenue business exists (its value is only proven against a real launch flow; YC funds proof-of-launches not proof-of-setup). BUT do the **A/B/C provider classification immediately** — it informs M4b's sandbox tasks running now.

### 4b. The n8n-style node UI (founder uploaded an n8n reference image)
ENDORSE. Missions/tasks are already graph-shaped; render as a live node canvas with the failing step highlighted — better operator console AND best demo visual. Founder's vision: click a block to buy domain, next block is bucks.ai processing, errors highlight the exact failing step. M5-era UI task.

### 4c. The loop babysitter (founder's final idea)
Small now that fresh-session shipped: (1) watchdog wrapper auto-restarts unless hard-blocked on a human gate (Slack ping either way); (2) mission auto-chaining (claim next queued mission instead of stopping; strategic gate remains the human checkpoint); (3) move runner to a VPS — the real babysitter, since a closed laptop currently stops the company. First two are one task each in the next batch.

---

## 5. `STRATEGY.md` — TO BE WRITTEN (spec for the new session)

Draft immediately after M4b closes. Contents:
- **Positioning:** sell convenience/completeness, not novelty ("everything already has a tool; win on simplicity + convenience of the whole pipeline").
- **Market selection doctrine:** B2B micro-SaaS painkillers, reachable buyers, small scope, a convenience wedge; the security-hardening service as a live candidate.
- **Kill criteria:** when to abandon a business (data-driven, feeds M8).
- **Building playbooks:** the M1 hardening template, the standard scaffold, analytics-by-default.
- **Core principle:** "external containment enables convenience" (see §4a).
- **Endgame doctrine:** bucks.ai generates the idea via its specialized strategy; human approves. The doctrine IS the proposal engine.
- **Cross-user learning ethics:** consent + anonymization from first customer.

---

## 6. FAR-FUTURE VISION & ROAD TO SUCCESS (the overall arc)

- **Near (now–1mo):** finish M4b → the machine can build businesses that aren't itself. Write `STRATEGY.md`. Pick M5.
- **Mid (1–3mo):** launch ONE real business (M5), start founder sales conversations immediately (manual outreach + system-generated drafts, don't wait for M6 tooling), publish build-in-public proof content from the run corpus. Add outreach engine (M6) + Stripe (M7) on the live business. Aim: first paying users, $10–50k traction.
- **YC application (~mo 4):** written around verifiable numbers — "our system created N repos, deployed N apps, configured N tools, sent N compliant emails, booked N demos, closed $X, shipped N improvements, humans only for legal/payment/calls."
- **Post-proof (portfolio era):** M8 memory → cross-business playbooks; the Provisioning Broker + wizard for true button-press convenience; the node-graph UI; N concurrent businesses; Marketing Brain (content/SEO/ads with hard external budget caps); self-serve bucks.ai product.
- **Honest ceiling (from master analysis §8):** the machine makes attempts cheap and compounding; whether any attempt reaches $1M/yr depends on problem selection, distribution, and market — no amount of code fixes those, but volume + memory improve the odds. **Statistically the most likely million-dollar business bucks.ai produces is bucks.ai itself** — a system with public proof it launches businesses is what founders pay for and YC funds.
- **The one metric to obsess over:** time from "click Execute / customer says yes" to deployed product. Everything that shortens it raises both capacity and the story.

---

## 7. IMMEDIATE NEXT ACTIONS FOR THE NEW SESSION

1. Check the M4b batch: `.runtime/tasks.local.json` (m4b-* statuses) + `.runtime/state.local.json` (`stop_reason`). Expect `seeded_queue_exhausted` at 9/9, or a stop needing the §3 playbook.
2. Watch for the `0004_business_sandbox.sql` Slack approval and m4b-08's resource-gate token request.
3. When M4b closes: read `docs/M4B-VERIFICATION-REPORT.md`, append `MISSION M4B COMPLETE` to master analysis §13, do the founder review (click Execute on a sandboxed business, watch it build a real repo).
4. Then write `STRATEGY.md` (§5), and pick M5 through it — evaluate the security-hardening sprint service head-to-head against other candidates.
5. Also open: **PR #82** `codex/remove-workspace-sticky-header` — a Codex-generated PR the founder didn't fully account for; review and merge-or-close so it doesn't cause stale-base conflicts.

## 8. KEY FILE INDEX
- Progress truth: `BUCKS_AI_MASTER_ANALYSIS.md` §13 completion log (append-only). This handoff supplements it.
- Verification reports: `docs/M2-VERIFICATION-REPORT.md`, `docs/M3-VERIFICATION-REPORT.md`, `docs/M4A-VERIFICATION-REPORT.md` (M4B pending).
- Seed files: `supabase/m3-seed-mission.sql`, `supabase/m4a-seed-mission.sql`, `supabase/m4b-seed-mission.sql`.
- Runner: `main.py` (CLI), `config.py` (~100 flags, three-place rule: config.py + README table + a test), `state.py`, `graph.py` (loop), `tools/` (~50), `workers/`.
- Env: `runner/langgraph/.env` (runner secrets incl. `CLAUDE_CLI_TIMEOUT_S=3600`, `PR_CHECKS_TIMEOUT_S=1800`, PostHog/Sentry runner keys) and `~/bucks-ai/.env` (app: PostHog `phc_`/personal `phx_`/project id, Sentry DSN/org/project). Vercel env has the 4 runtime keys.
- Agent rules: `AGENTS.md` (feature branches only; `./scripts/check.sh` before commit; never `--no-verify`; never force-push; secrets by name only; structured end-of-task summary format).
