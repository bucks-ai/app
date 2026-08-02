-- =============================================================================
-- Seed: M4c — Loop Babysitter & Continuous Operation (10 tasks)
--
-- Run ONCE in the Supabase SQL editor (the app project the runner polls).
-- The runner seeded-mission queue picks up status='queued' missions and
-- executes tasks in position order.
--
-- Full spec with rationale: docs/M4C-MISSION-SPEC.md
--
-- WHY THIS MISSION: M4b took ~6 hours of founder debugging in one session and
-- ZERO of those hours were the AI failing to write code. Every task below is
-- derived from a specific failure the founder personally absorbed. This is not
-- a speculative feature list.
--
-- BUILD ORDER IS LOAD-BEARING: tasks 01-03 make the runner HONEST (correct
-- dispatch, evidence-based completion, self-healing state). Only then do 04-07
-- give it POWERS, and 08-09 make it CONTINUOUS. Building auto-approval on top
-- of a system that scores refusals as successes just automates lying.
--
-- FOUNDER PREREQUISITES (do before launching the loop):
--   1. Apply supabase/migrations/0006_deprecate_businesses_sandbox_config.sql
--      (comment-only; silences the pending-migration warning on every run)
--   2. ntfy.sh topic created + app installed on phone; topic name added to
--      runner/langgraph/.env as NTFY_TOPIC (needed by m4c-09)
--   3. CLAUDE_MODEL / ANTHROPIC_MODEL set to Opus 5 or Fable 5 in
--      runner/langgraph/.env — founder decision 2026-07-27, this mission is
--      too high-leverage and too subtle for Sonnet 5 workers
--   4. Windows power settings: lid-close-when-plugged-in = "Do nothing",
--      sleep = "Never" (so overnight runs survive a closed laptop)
-- =============================================================================

WITH src AS (
  SELECT business_id, user_id
  FROM public.missions
  WHERE id = 'ad272c08-6fc6-4a3e-91b5-27380d224d8e'  -- M4b batch 2
),
m AS (
  INSERT INTO public.missions (business_id, user_id, name, goal, status, task_count, runner_target)
  SELECT
    business_id,
    user_id,
    'M4c — Loop Babysitter & Continuous Operation',
    'The loop stops needing the founder. Done when the runner executes a full mission end to end, unattended, overnight — surviving usage limits, transient network failures, PR checks, merges and deploys — and the founder phone stays silent unless a human genuinely must create an account. If M4c ships and the founder is still hand-running gh pr merge or editing runtime JSON, M4c has failed regardless of what its tests say.',
    'queued',
    10,
    'self'
  FROM src
  RETURNING id, business_id, user_id
)
INSERT INTO public.mission_tasks
  (mission_id, business_id, user_id, task_id, title, description, type, branch, position, status)
SELECT m.id, m.business_id, m.user_id,
       t.task_id, t.title, t.description, t.type, t.branch, t.position, 'queued'
FROM m,
(VALUES
  ('m4c-01-worker-dispatch-fix',
   'M4c: fix business-task worker dispatch (BLOCKS ALL UNATTENDED BUSINESS EXECUTION)',
   'The M4b deploy task failed THREE times and never once because the AI could not deploy. Root cause confirmed from two independent worker transcripts: the runner writes outbox/<task>_prompt.txt and launches the worker such that the prompt arrives as an ATTACHED FILE REFERENCE rather than as the instruction itself, with cwd left in the bucks-ai tree instead of the business workspace. Both workers therefore saw "a file describing a deploy to someone elses Vercel project", correctly judged that consequential and irreversible, and asked for clarification instead of acting. The workers behaved CORRECTLY; the dispatch is broken. Required: (a) pass the task prompt as the actual instruction, not a file @-mention; (b) for runner_target=business tasks set worker cwd to the resolved business workspace path; (c) before any work, assert git remote get-url origin matches the business repo_full_name and hard-fail on mismatch; (d) refuse to start the loop at all from a non-main branch or a dirty working tree (the founder hit this — the loop ran from fix/sandbox-config-edit with uncommitted changes, which is what confused the workers). Tests: business task receives correct cwd; wrong-remote aborts; dirty-tree and non-main both refuse to start. Until this lands, no business mission can execute unattended, which is the entire point of M4.',
   'backend', 'feature/m4c/worker-dispatch-fix', 1),

  ('m4c-02-completion-integrity',
   'M4c: evidence-based completion — never score a refusal as success',
   'ai-infra-03 was marked complete TWICE while the worker had refused the task and deployed nothing: deploy_result was null, zero files created or modified, and the worker final output was a QUESTION ("do you want me to: 1. Execute it... 2. Just summarize..."). The runner marks complete on worker exit-success, not on evidence of work. Silent false success is worse than a crash — every other M4b failure was loud; this one looked like a win and left the mission marked done with the core deliverable missing. Required: completion requires POSITIVE evidence appropriate to task type — a commit sha that actually exists in the expected remote, a deployment id/URL that responds to a real request, a file that exists on disk. Detect refusal/no-op/question patterns ("I am not going to", "do you want me to", "Commit Result: skipped", "no new commit", zero created AND zero modified) and mark blocked, NEVER complete. A worker whose output is a question is blocked by definition. Tests: each refusal pattern; each evidence type; a genuine completion still passes.',
   'backend', 'feature/m4c/completion-integrity', 2),

  ('m4c-03-state-self-healing',
   'M4c: self-healing task state — orphans, duplicate seeding, transient vs terminal',
   'Three distinct state bugs, ALL hand-fixed by the founder editing runtime JSON during M4b. (1) ORPHANED RUNNING TASKS, hit four separate times (m4b-07/08/09/10): an interrupted run leaves the in-flight task at status=running forever; the existing requeue logic only handles blocked tasks, so on restart the loop sees zero queued work and exits seeded_queue_exhausted — appearing done when it actually stalled. Fix: on startup, requeue any task stuck at running with no live worker/session owning it, mirroring requeue_fulfilled_blocked_tasks. (2) DUPLICATE SEEDING, hit 3x: the Execute: AI Infra mission was seeded three times because nothing checks whether a mission tasks are already present locally before seeding, producing 15 tasks with COLLIDING ids (ai-infra-1..5 x3); status writes key off id so a completion could mark the wrong row, and the sets even disagreed on content. Fix: check for existing local tasks for a seeded_mission_id before seeding, enforce globally-unique task ids, reconcile against Supabase mission_tasks as source of truth rather than blindly appending. Also prune stray placeholder tasks such as rls-fixture-task. (3) TRANSIENT ERRORS MARKED TERMINAL: a degraded network broke a Supabase lookup and the task was marked failed with "business not found"; failed is terminal so every relaunch exhausted in 30s until hand-edited. Fix: classify errors as TRANSIENT (network/DNS/timeout/rate-limit/5xx — retry with backoff then requeue, never terminal) vs GENUINE (the work itself is wrong — may be terminal, after one retry). A partial mitigation shipped 2026-07-31 in fetch_business_by_id (3 attempts, linear backoff, distinct business_lookup_unreachable event); generalize it.',
   'backend', 'feature/m4c/state-self-healing', 3),

  ('m4c-04-git-pr-autonomy',
   'M4c: full git and PR autonomy — create, check, rebase, merge, without the founder',
   'During M4b the founder personally ran gh pr create then gh pr checks then gh pr merge for every single PR, resolved a main divergence by hand-choosing rebase vs reset, resolved six identical-formatting merge conflicts, and recovered from a stale origin/main no-op merge. Required: open PRs, poll checks, merge on green — end to end with no founder involvement. Handle the recurring "no checks reported" state by rebasing on latest main to wake the checks. Handle divergence: prefer pull --rebase, and detect when a local commit is already upstream so it can be dropped cleanly (git reports "patch contents already upstream"). Auto-resolve TRIVIAL conflicts only — whitespace and formatting-only differences with identical semantics, like the six in test_foreign_repo_workspace.py where one side wrapped a call across three lines and the other kept it on one; escalate anything semantic. CRITICAL SAFETY: never silently discard founder work — a worker routine branch operation reverted uncommitted local doc edits during M4b. Rule: commit-or-stash before any checkout, and never touch files outside the task declared scope.',
   'backend', 'feature/m4c/git-pr-autonomy', 4),

  ('m4c-05-environment-deploy-ownership',
   'M4c: own the environment — migrations, deploys, config pre-validation',
   'FRAMING: the runner already HAS the access it needs. .env already holds VERCEL_TOKEN, POSTHOG_PERSONAL_API_KEY, GITHUB_TOKEN, SUPABASE_SERVICE_ROLE_KEY, SENTRY_AUTH_TOKEN and the Slack tokens. During M4b the runner held a valid Vercel token the entire time and still never deployed, never noticed production was serving stale code, never wired the git integration, never applied pending migrations. The gap is AGENCY, not credentials. Required: (a) PROACTIVELY USE EXISTING ACCESS — deploy via the Vercel API, query PostHog to verify analytics actually fire, apply migrations via Supabase, check Sentry for new errors post-deploy, as normal parts of finishing a task and never as something the founder triggers. (b) MIGRATIONS: detect pending migrations and auto-apply additive/guarded ones instead of halting or warning forever (M4b: 6 pending migrations silently blocked startup; 0006 then warned on every single subsequent run). (c) DEPLOYED-SHA VERIFICATION: assert the deployed production SHA matches main before trusting the UI, and trigger a deploy if not — during M4b the Vercel project was not git-connected so main merged for hours while production served stale code, and the founder debugged a "missing feature" that had existed in the repo the whole time. (d) CONFIG PRE-VALIDATION AT CLAIM TIME: verify the configured repo and Vercel project actually exist and are reachable (GET /repos/{owner}/{repo}, Vercel project probe) BEFORE claiming, instead of discovering it 40 minutes in via a clone failure — a wrong repo name (testflow vs testflow-demo) burned a full run and a resource gate. (e) PUSH-DESTINATION VERIFICATION: business commits must land in the business repo; assert the remote matches repo_full_name before and after push and hard-fail otherwise. (f) FAIL-OPEN ON INFRA ERRORS: transient infra failures degrade to a loud Slack warning and the loop CONTINUES; they must never escalate to awaiting_resources or halt the loop.',
   'infra', 'feature/m4c/environment-ownership', 5),

  ('m4c-06-continuous-operation',
   'M4c: watchdog, limits-aware pause/resume, heartbeat',
   'Founder spec verbatim: "constantly running, only stops when limits are exhausted, then starts up right after." Required: (a) WATCHDOG WRAPPER — auto-restart the loop on any exit that is not a hard human gate; Slack ping either way. Fresh-session-per-invocation already shipped so restart is safe. (b) LIMITS-AWARE PAUSE/RESUME — on rate-limit, budget or API-quota exhaustion, compute the reset window, sleep it out, then resume. Never die on exhaustion. Note the existing CLAUDE_USAGE_LIMIT_AUTO_RESUME and CLAUDE_SUBSCRIPTION_COOLDOWN_* config as the starting point; during M4b runs were repeatedly cut short by cooldowns and never resumed on their own. (c) HEARTBEAT AND STALL DETECTION — emit a periodic babysitter_heartbeat event; if the loop goes silent past a threshold, restart it and log loudly.',
   'backend', 'feature/m4c/continuous-operation', 6),

  ('m4c-07-auto-approval-policy',
   'M4c: auto-approval — the founder approves everything, so stop asking',
   'Founder decision, verbatim: "I approve everything, dont wait for me." AUTO-APPROVE by writing the same inbox fulfillment file a human approve-click would (so the file-based graph gates stay untouched): merges that already passed CI, additive migrations that pass the existing sql_guard scan, and any action inside the approved roadmap. NEVER AUTO-APPROVE two classes: (a) genuinely destructive, irreversible or over-budget actions — non-additive SQL containing DROP, spend past a cap, anything the guard flags; (b) resource/credential gates that need a human to create an account, because auto-clicking approve cannot conjure a token into existence. IMPORTANT DISTINCTION the founder surfaced 2026-07-31: an APPROVAL is a DECISION (merge this, apply this) and the runner should make those itself; a CREDENTIAL GATE is a THING THAT DOES NOT EXIST YET (there is no Resend account anywhere) and is a request for materials, not permission. So the value of this item is not the gate — it is SKIP-AND-CONTINUE: today a single missing credential halts the entire loop (observed repeatedly across M4b); afterwards the runner sets that one task aside, keeps working everything else, and auto-requeues it the instant the credential appears. Net effect: routine approvals disappear entirely and the founder is touched only for new credentials and truly irreversible calls.',
   'backend', 'feature/m4c/auto-approval', 7),

  ('m4c-08-roadmap-as-data',
   'M4c: roadmap-as-data plus auto-seeding and mission chaining',
   'Founder decision 2026-07-21: sign-off happens ONCE, at the PLAN level. The founder approves the whole mission roadmap upfront and never seeds individual missions or tasks again — per-mission seeding was an unnecessary gate, because if the plan is approved then re-approving each piece of it kills convenience for nothing. Required: (a) the approved mission plan (M4d through M9 and beyond) lives as structured data — a mission_backlog table or checked-in specs — with each entry pre-written to full seed quality and an approved flag set once by the founder. This replaces hand-pasted seed SQL entirely, including the file you are reading. (b) AUTO-SEEDING AND CHAINING: when the current mission completes clean, seed and claim the next approved backlog entry automatically; the machine never idles while approved work exists. (c) DOCTRINE INGESTION: the planner reads STRATEGY.md as context on every planning call so mission plans are doctrine-shaped by construction — this is the first of three code paths that make the strategy doc executable (the others are M4d and M7.5). PRODUCT MIRROR: this approve-the-plan-once model IS the customer experience — a customer approves their business blueprint once and the machine runs every mission under it without coming back. M4c is bucks.ai dogfooding its own convenience doctrine.',
   'backend', 'feature/m4c/roadmap-as-data', 8),

  ('m4c-09-self-provisioning-and-notify',
   'M4c: parent-child self-provisioning, dependency batch-ahead, phone push',
   'PARENT-CHILD PROVISIONING (the self-provisioning engine; STRATEGY.md section 3 and the 2026-07-29 doctrine): the human creates ONE parent account per vendor, once, ever; the agent then creates UNLIMITED scoped children under it via API, forever, unattended. Coverage is near-total — GitHub (repos, deploy keys, scoped tokens), Vercel (projects, env vars, domains, git connections), Supabase (projects and keys via Management API), Stripe (Connect sub-accounts, purpose-built for exactly this), AWS (Organizations sub-accounts, IAM roles), Resend (domains, verification, scoped sending keys), Twilio (subaccounts), PostHog (projects). EXPLICITLY OUT OF SCOPE: autonomous signup for brand-new vendor accounts — ToS acceptance is a binding legal act, provider terms prohibit automated signup, agent-completed signup flows are a recognised fraud vector vendors actively detect and terminate, and an unattended agent that ingests foreign repo contents by design (M4b) must never hold account-creation or spending powers. See STRATEGY.md section 6.3. THE 30-SECOND SETUP HANDOFF (founder decision 2026-07-31 — the founder makes all purchases and completes all signups personally; the job is to make that take 30 seconds not 30 minutes): every credential request must arrive FULLY PREPARED — exact signup URL deep-linked as far into the flow as possible, precisely which plan/tier to pick and whether the free tier suffices, every field value pre-computed and copy-pasteable, the exact .env variable NAME to paste the key into and where that file lives, which mission/task is blocked in one line, and a single done action to unblock. ANTI-GOAL: a bare "Resource needed: an ESP" like the M4b requests, which forces the founder to do research the agent should have done. DEPENDENCY BATCH-AHEAD: on startup parse the ENTIRE approved roadmap, extract every external dependency, and issue ONE consolidated credential request up front — one 30-minute founder session for the whole roadmap instead of N ambushes over weeks. The list must be GENEROUS not minimal; never cut corners to avoid asking, tool acquisition is pre-approved. PHONE PUSH: exactly ONE alert class reaches the founder phone — credential/account requests. Everything else (approvals, merges, errors, migrations, stranded tasks, deploy failures) is the babysitter job, silently. Use ntfy.sh via NTFY_TOPIC (three-place rule), NOT Slack, because Slack only notifies with the app open which is why credential requests sat unseen for hours during M4b. Slack remains the full activity log. SUCCESS CRITERION: across a full unattended night the phone buzzes zero times unless a human genuinely must create an account.',
   'backend', 'feature/m4c/self-provisioning', 9),

  ('m4c-10-verification-report',
   'M4c: verification pass and mission report',
   'Write docs/M4C-VERIFICATION-REPORT.md. The acceptance test is NOT unit coverage — it is an UNATTENDED OVERNIGHT RUN of a real mission, reporting exactly how many times the founder was touched and why. Target: zero touches except genuine new-credential requests. Map every one of the thirteen M4b-derived failure modes (see CHAT_HANDOFF_2026-07-11.md M4c items 1-13) to the test or live evidence that it can no longer happen: orphaned running tasks, duplicate seeding, transient-marked-terminal, false completion, worker dispatch, stale deploys, unapplied migrations, config typos caught late, discarded founder work, wrong push destination, silent no-ops, escalation-instead-of-diagnosis. State everything unverified explicitly. FINAL STANDARD, founder verbatim: "it genuinely needs to be powerful" — if M4c ships and the founder is still hand-running gh pr merge or editing runtime JSON, M4c has FAILED regardless of what its tests say. Say so plainly in the report if that is the case.',
   'test', 'feature/m4c/verification', 10)
) AS t(task_id, title, description, type, branch, position);
