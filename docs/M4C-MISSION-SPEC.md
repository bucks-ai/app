# M4c — Loop Babysitter & Continuous Operation

**Status:** ready to seed (written 2026-07-31, immediately after M4b closed)
**Build with:** Opus 5 or Fable 5 workers — NOT Sonnet 5 (founder decision 2026-07-27)
**Why this mission exists:** M4b took ~6 hours of founder debugging in a single session, and
**zero of those hours were the AI failing to write code.** Every task below is derived from a
specific failure the founder personally absorbed. This is not a speculative feature list.

**The one-line goal:** the loop stops needing the founder.

**Definition of done for the whole mission:** the runner executes a full mission end-to-end,
unattended, overnight — surviving usage limits, transient network failures, PR checks, merges
and deploys — and the founder's phone stays silent unless a human genuinely must create an
account.

---

## Build order (sequencing matters — do not reorder)

The critical rule: **trustworthy completion and state come BEFORE autonomy.** Building
auto-approval or auto-chaining on top of a system that scores refusals as successes just
automates lying. Tasks 01–03 make the runner honest; 04–07 make it capable; 08–09 make it
continuous; 10 verifies.

---

### m4c-01 — Fix business-task worker dispatch ★ FIRST, BLOCKS EVERYTHING
**Type:** backend

The deploy task in M4b failed three separate times and never once because the AI couldn't
deploy. Root cause confirmed from two independent worker transcripts: the runner writes
`outbox/<task>_prompt.txt` and launches the worker such that the prompt arrives as an
**attached file reference rather than as the instruction itself**, with cwd left in the
bucks-ai tree instead of the business workspace. Both workers saw "a file describing a deploy
to someone else's Vercel project," correctly judged that consequential and irreversible, and
asked for clarification. Verbatim: *"do you want me to: 1. Execute it... 2. Just summarize...
3. Investigate the runner?"* **The workers behaved correctly. The dispatch is broken.**

Required:
- Pass the task prompt as the actual instruction, not a file `@`-mention.
- For `runner_target: "business"` tasks, set worker cwd to the resolved business workspace.
- Before any work, assert `git remote get-url origin` matches the business's
  `repo_full_name`; hard-fail on mismatch.
- Refuse to start the loop at all from a non-`main` branch or a dirty working tree (the
  founder hit this: the loop ran from `fix/sandbox-config-edit` with uncommitted changes,
  which is what confused the workers in the first place).
- Tests: business task gets correct cwd; wrong-remote aborts; dirty-tree/non-main refuses to start.

Until this lands, **no business mission can execute unattended** — which is the entire point of M4.

---

### m4c-02 — Completion integrity (evidence-based completion)
**Type:** backend

`ai-infra-03` was marked `complete` TWICE while the worker had refused the task and deployed
nothing. `deploy_result` was `null`, zero files created or modified, and the worker's final
output was a question. The runner marks `complete` on worker exit-success, not on evidence
of work. **Silent false success is worse than a crash — every other failure was loud; this one
looked like a win and left the mission marked done with the core deliverable missing.**

Required:
- Completion requires POSITIVE evidence appropriate to task type: a commit sha that actually
  exists in the expected remote; a deployment id/URL that responds; a file that exists.
- Detect refusal/no-op/question patterns ("I'm not going to", "do you want me to",
  "Commit Result: skipped", "no new commit", zero created AND zero modified) → mark
  `blocked`, never `complete`.
- A worker whose output is a QUESTION is `blocked` by definition.
- Tests: each refusal pattern; each evidence type; a genuine completion still passes.

---

### m4c-03 — State self-healing
**Type:** backend

Three distinct state bugs, all hand-fixed by editing runtime JSON during M4b:
1. **Orphaned `running` tasks** (hit FOUR times: m4b-07/08/09/10). An interrupted run leaves
   the in-flight task at `running` forever; existing requeue logic only handles `blocked`. On
   restart the loop sees zero `queued` work and exits `seeded_queue_exhausted` — appearing
   done when it actually stalled.
2. **Duplicate seeding** (hit 3×). "Execute: AI Infra" was seeded three times, producing 15
   tasks with COLLIDING ids (`ai-infra-1..5` ×3). Status writes key off id, so a completion
   could mark the wrong row. Sets even disagreed on content (pre- vs post-m4b-07 compiler).
   Required a hand-written dedupe script.
3. **Transient errors marked terminal.** A degraded network broke a Supabase lookup; the task
   was marked `failed` with "business not found." `failed` is terminal, so every relaunch
   exhausted in 30s until the founder hand-edited the JSON.

Required:
- On startup, requeue any task stuck at `running` with no live worker/session owning it.
- Idempotent seeding: check for existing local tasks for a `seeded_mission_id` before seeding;
  enforce globally-unique task ids; reconcile against Supabase `mission_tasks` as source of truth.
- Error classification: **transient** (network/DNS/timeout/rate-limit/5xx) → retry with
  backoff, then requeue, NEVER terminal. **Genuine** (the work is wrong) → may be terminal,
  after one retry.
- Prune stray placeholder tasks (e.g. `rls-fixture-task`).

---

### m4c-04 — Git/PR autonomy
**Type:** backend

During M4b the founder personally ran `gh pr create` → `gh pr checks` → `gh pr merge` for
every PR, plus resolved a `main` divergence (hand-choosing rebase vs reset), plus resolved six
identical-formatting merge conflicts, plus recovered from a stale `origin/main` no-op merge.

Required:
- Open PRs, poll checks, merge on green — end to end, no founder involvement.
- Handle "no checks reported" (rebase on latest main to wake checks).
- Handle divergence: prefer `pull --rebase`; detect when a local commit is already upstream
  and drop it cleanly.
- Auto-resolve *trivial* conflicts (whitespace/formatting-only, identical semantics); escalate
  anything semantic.
- **Never silently discard founder work.** A worker's routine branch operation reverted
  uncommitted local doc edits during M4b. Rule: commit-or-stash before any checkout; never
  touch files outside the task's declared scope.

---

### m4c-05 — Environment & deploy ownership
**Type:** infra

Required:
- **Migrations:** detect pending migrations and apply additive/guarded ones automatically
  (`AUTO_APPLY_MIGRATIONS`) instead of halting or warning on every run forever. (M4b: 6
  pending migrations silently blocked startup; `0006` then warned on every subsequent run.)
- **Deployed-SHA verification:** before trusting the UI, assert the deployed production SHA
  matches `main`; trigger a deploy if not. (M4b: the Vercel project wasn't git-connected, so
  `main` merged for hours while production served stale code — the founder debugged a
  "missing feature" that had existed in the repo the whole time.)
- **Config pre-validation at claim time:** verify the configured repo and Vercel project
  actually exist and are reachable (`GET /repos/{owner}/{repo}`, Vercel project probe) BEFORE
  claiming — instead of discovering it 40 minutes in via a clone failure. (M4b: `testflow` vs
  `testflow-demo` burned a full run and a resource gate.)
- **Push-destination verification:** business commits must land in the business repo. Assert
  the remote matches `repo_full_name` before and after push; hard-fail otherwise.
- **Fail-open on infra errors:** transient infra failures degrade to a loud Slack warning and
  the loop CONTINUES; they must never escalate to `awaiting_resources` or halt.

---

### m4c-06 — Continuous operation: watchdog, limits-aware resume, heartbeat
**Type:** backend

Founder's spec verbatim: *"constantly running, only stops when limits are exhausted, then
starts up right after."*

Required:
- Watchdog wrapper: auto-restart on any exit that isn't a hard human gate; Slack ping either way.
- Limits-aware pause/resume: on rate-limit/budget/quota exhaustion, compute the reset window,
  sleep it out, resume. Never die on exhaustion.
- Heartbeat + stall detection: periodic `babysitter_heartbeat`; if silent past a threshold,
  restart and log loudly.

---

### m4c-07 — Auto-approval policy
**Type:** backend

Founder: *"I approve everything, don't wait for me."*

- **Auto-approve** (write the same inbox fulfillment file a human click would, so the
  file-based gates stay untouched): merges that already passed CI, additive migrations passing
  `sql_guard`, any action inside the approved roadmap.
- **Never auto-approve:** (a) destructive/irreversible or over-budget actions (non-additive SQL
  with DROP, spend past a cap, anything the guard flags); (b) resource/credential gates needing
  a human to create an account — auto-clicking can't conjure a token, so **skip that task, keep
  working everything else, auto-requeue the moment the credential lands.** Never block the whole
  loop on one gate.

---

### m4c-08 — Roadmap-as-data + auto-seeding/chaining
**Type:** backend

Founder decision: sign-off happens ONCE, at the PLAN level. No per-mission or per-task seeding, ever.

- Approved mission plan (M4d→M9+) lives as structured data (`mission_backlog` table or checked-in
  specs), each entry pre-written to full seed quality with an `approved` flag set once.
- When the current mission completes clean, seed and claim the next approved entry automatically.
  The machine never idles while approved work exists.
- **Doctrine ingestion:** the planner reads `STRATEGY.md` on every planning call, so plans are
  doctrine-shaped by construction.
- *Product mirror:* this approve-the-plan-once model IS the customer experience. M4c is bucks.ai
  dogfooding its own convenience doctrine.

---

### m4c-09 — Self-provisioning + dependency batch-ahead + phone push
**Type:** backend

**Parent-child provisioning** (see `STRATEGY.md` §3 and the 2026-07-29 doctrine): the human
creates ONE parent account per vendor, once. The agent creates unlimited scoped children under
it via API, forever. Covers GitHub (repos, tokens), Vercel (projects, env vars, domains, git
links), Supabase (projects/keys), Stripe (Connect sub-accounts), AWS (Organizations, IAM),
Resend (domains, sending keys), Twilio (subaccounts), PostHog (projects).
**Explicitly NOT in scope: autonomous signup for brand-new vendor accounts** — ToS acceptance is
a binding legal act, provider terms prohibit automated signup, and an unattended agent that
ingests foreign repo contents (M4b) must not hold account-creation or spending powers. See
`STRATEGY.md` §6.3.

**Dependency batch-ahead:** on startup, parse the ENTIRE approved roadmap, extract every external
dependency, and issue ONE consolidated credential request up front. One ~30-minute founder
session for the whole roadmap instead of N ambushes. **The list must be GENEROUS, not minimal** —
never cut corners to avoid asking; tool acquisition is pre-approved.

**Phone push:** exactly ONE alert class reaches the founder's phone — credential/account requests.
Everything else (approvals, merges, errors, migrations, stranded tasks, deploy failures) is the
babysitter's job, silently. Use ntfy.sh or Pushover, not Slack (Slack only notifies with the app
open — that's why credential requests sat unseen during M4b). Slack remains the full activity log.
**Success criterion: across a full unattended night, the phone buzzes zero times unless a human
genuinely must create an account.**

---

### m4c-10 — Verification pass + M4c report
**Type:** test

Write `docs/M4C-VERIFICATION-REPORT.md`. The acceptance test is not unit coverage — it is:
**run a real mission overnight, unattended, and report exactly how many times the founder was
touched and why.** Target: zero touches except genuine new-credential requests.

State everything unverified explicitly. If M4c ships and the founder is still hand-running
`gh pr merge` or editing runtime JSON, **M4c has failed regardless of what its tests say.**

---

## Companion infra task (not a runner task — founder action)

**Always-on host.** The babysitter keeps the *loop* alive, but closing the laptop lid sleeps the
*machine* and kills WSL + the runner regardless. (1) Immediate: Windows power settings —
lid-close-when-plugged-in = "Do nothing", sleep = "Never". (2) Durable: migrate the runner + its
`.env` to a cheap always-on VPS ($5–10/mo Hetzner/DO) so autonomy no longer depends on the
founder's personal machine being open and charged. **Always-on host + babysitter = actual 24/7.**
Also eliminates the stale-shell-export class of bug that bit three times during M4b
(`DIRECT_DATABASE_URL`, `VERCEL_TOKEN`, and env drift generally).
