# Runner Babysitter — Design Review & Red Team

**Date:** 2026-08-04 · **Status:** pre-build review · **Read with:** `docs/M4C-MISSION-SPEC.md`, `STRATEGY.md`, `BUCKS_AI_MASTER_ANALYSIS.md` §13

Written before building M4c.5. Purpose: pressure-test the babysitter concept, find
where it is weak or missing, and fix the scope *before* code exists. Every weakness
below is either observed in this repo's logs or a failure mode the current design
provably cannot detect.

---

## 1. What the babysitter actually is (scope correction)

"Babysitter" undersells it and that has caused scope drift. What is being built is
an **autonomous engineering organization** with four roles:

| Role | Responsibility | Current state |
|---|---|---|
| **Dispatcher** | Pick the right task, give the worker what it needs to succeed | Weak — no mission context, flat queue |
| **QA** | Decide whether the work was actually, correctly done | Good — evidence gate (m4c-02), CI, E2E |
| **SRE** | Keep the loop alive, recover from infrastructure failure | Partial — cooldown guard; no supervisor |
| **Release manager** | Get merged code safely into production | Good — PR path, branch protection |

The name matters because "babysitter" implies *watching*. The valuable behaviour is
*deciding* — what to retry, what to repair, what to skip, what to escalate.

### Success criteria (the only ones that count)

1. A full mission executes overnight with **zero founder touches** except genuine
   new-credential requests.
2. When it fails, it fixes itself or files an actionable repair task — it does not
   sit idle waiting to be found.
3. Code quality does not decay across hundreds of unattended tasks.
4. It cannot break itself in a way that ends autonomy silently.

Criterion 4 is the one no current M4c task addresses.

---

## 2. Red team — how this system fails

### 2.1 CRITICAL: the runner modifies the runner

The loop edits `graph.py`, its own guards, and its own tests. Three escalating
failure modes:

**(a) Hard breakage.** A merged change stops the loop starting. Autonomy ends until
a human notices. *Mitigation in plan:* canary + auto-revert. *Gap:* the revert path
is itself Python inside the loop — if the loop cannot start, it cannot revert. **The
revert mechanism must live OUTSIDE the loop** (a shell supervisor that knows the
last-known-good SHA and can `git revert` without importing the runner).

**(b) Silent semantic breakage.** The loop starts, tests pass, but a guard is now
subtly wrong — e.g. cooldown detection stops matching, or the evidence gate accepts
weaker proof. Nothing fails; the system just gets dumber. A canary that checks
"does it start and do tests pass" cannot see this. *Required:* a **behavioural
smoke suite** — replay a set of recorded real incidents (the 2026-07-06 session-limit
payload, the PR #94 advisory-check conclusions, a refusal transcript, a merge
conflict) and assert the system still classifies each correctly. These are
regression fixtures for judgement, not for code paths.

**(c) Verification capture — the highest-severity class.** A worker that cannot make
a test pass can instead **change the test**. This is a documented AI failure mode and
nothing in the current design detects it. The evidence gate checks that work
happened, not that the bar stayed where it was.

*Required, two parts:*
- **Constitutional files.** A protected list — `tools/completion_evidence.py`,
  `tools/gate_authority.py`, the guard modules, `.github/workflows/*`, and the
  behavioural fixtures. Changes to these require either founder approval or a
  dedicated review pass that cannot be self-approved by the task that wants them.
- **Test-weakening detection.** A CI check that fails when a diff reduces total
  assertion count, deletes test files, adds `skip`/`xfail`, or loosens an assertion
  (`assertEqual` → `assertTrue`, exact → regex), unless the commit message carries
  an explicit justification token the founder must add.

### 2.2 Self-repair recursion

If the babysitter seeds repair tasks for its own failures, and those repairs fail,
seeding more — the queue explodes and the limit budget burns on flailing.

*Required:* dedupe repair tasks on a normalised error signature; a depth cap
(a repair of a repair of a repair is a human escalation, not a fourth attempt); a
per-session self-repair budget; and a quarantine list so the same failing task
cannot be reseeded indefinitely.

### 2.3 Single point of failure: the host

Everything runs in WSL on one laptop. A Windows update, a reboot, a sleep event, or
a WSL crash ends the run. "Runs continuously until limits are exhausted" is not
achievable on this host. Observed already: closing the laptop suspended the loop
mid-cooldown.

*Required eventually:* a VPS or always-on box with the loop as a systemd service.
*Acceptable now:* systemd-user unit inside WSL + `WSL` keep-alive + power settings,
with the honest caveat that host death is unrecoverable without a human.

### 2.4 Brittle coupling to external contracts

The cooldown guard parses **English prose** from the Claude CLI. It has already
broken once (2026-07-06, "You've hit your session limit" matched no marker) and cost
a full night. The same brittleness exists for Codex JSONL, GitHub check-run shapes,
and Vercel deployment payloads.

*Required:* prefer machine-readable signals over prose everywhere (`api_error_status:
429` over message text — already partially done); keep recorded fixtures of every
external payload shape the system parses; a contract test per external tool that
fails loudly when a shape changes.

### 2.5 Scope escape

A worker touching files outside its task's declared scope has already destroyed
uncommitted founder work once (M4b). m4c-04 states the rule but nothing enforces it.

*Required:* declare expected paths per task; a post-work diff check that flags
out-of-scope modifications; mandatory `git stash` before any checkout; and an
absolute prohibition on `push --force` to `main` and on deleting unmerged branches.

### 2.6 Outcome blindness

The loop's definition of success is *its own tests*. A change that passes CI, merges,
deploys, and silently breaks the product funnel is invisible. M3 built the analytics
to see this; nothing consumes it as a gate.

*Required:* post-deploy outcome check — production SHA matches main, the deployed URL
answers, Sentry shows no new error signature attributable to this deploy, and (where
applicable) the M3 funnel events still fire. A deploy that regresses those is a
failure even with green tests.

### 2.7 Unbounded growth

`runs.jsonl` is 20k+ lines; `outbox/` holds 131 files. Both grow forever. Log parsing
already feeds diagnostics and calibration, so this becomes a performance and
correctness issue, not just tidiness.

*Required:* rotation with retention, and an index/summary file so analysis does not
require reading the whole history.

### 2.8 Blind spot while away — and the answer

There is no way to answer "what is it doing right now" without being at the machine.
For an unattended overnight system this is a real usability gap.

**Monitoring and intervention are different problems and need different answers.**

**Monitoring — push, not pull. Do this first.** The runner already syncs task state
to Supabase (`seeded_mission_task_synced`) and M4a already built agent-run streaming
and the Operating Team UI. Add a heartbeat row — current task, step, elapsed, queue
depth, session cost, last stop reason, last-known-good SHA — written every loop tick,
and render it on the existing dashboard. Zero new infrastructure, visible from any
phone browser, and it dogfoods the product: this is the same "watch your business
build itself" surface a customer gets. Push beats pull for monitoring; you should not
need a terminal to answer "is it alive".

**Intervention — SSH via Tailscale.** For the times you must actually *do* something
(attach to tmux, run `doctor --fix`, restart), SSH is the right tool, but do NOT port
-forward from Windows to the public internet. Use Tailscale: install on the Windows
host, install `openssh-server` inside WSL, and the machine joins a private network
reachable from your phone with no open ports and no exposed credentials.

```bash
# inside WSL, once
sudo apt update && sudo apt install -y openssh-server
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo service ssh start
# add your public key to ~/.ssh/authorized_keys

# Windows host: install Tailscale, sign in, enable WSL networking.
# Then from a phone SSH client on the same tailnet:
#   ssh arnav@<tailscale-hostname>
#   tmux attach -t bucks
```

Note WSL does not start services on boot by default — enable systemd in
`/etc/wsl.conf` (`[boot] systemd=true`) so `ssh` and the loop's own service survive a
restart. This is also the prerequisite for §2.3's supervisor.

*Required:* heartbeat artifact + dashboard tile (monitoring), Tailscale + SSH +
systemd (intervention). Ship monitoring first — it removes 90% of the need to log in.

### 2.9 Secret egress

Worker output flows into `runs.jsonl`, Slack, PR bodies, and stop reports. Outbox
approval files are sanitised; the general logging path is not verified to be.

*Required:* a single sanitisation choke point on every outbound path, with tests
using realistic secret shapes (`sk-`, `xoxb-`, `ghp_`, connection strings, JWTs).

### 2.10 Cost blowup

Opus on every task exhausted the monthly spend cap mid-run (2026-08-04 00:13),
stalling for two hours. Model choice is currently global.

*Required:* per-task-type model routing (Opus for runner-internal and architectural
work, Sonnet for mechanical edits, Codex for UI), and a mission-level budget with a
projection warning before the cap is hit rather than after.

---

## 3. Structural weaknesses in the current plan

### 3.1 Retry is the wrong primitive (highest-value fix)

Evidence from this repo: retries have **never** succeeded for a deterministic cause.
Timeouts and cooldowns recover; test failures, merge conflicts, and gate blocks never
do — every one was ultimately fixed by hand.

Retry re-runs identical input expecting a different output. The fix is not more
retries: **failures must be repaired with new information**. `auto_repair_loop` and
`build_auto_repair_prompt` already exist but fire only on local `check.sh` failures.
Extending them to CI failures, merge conflicts, gate blocks, and evidence-gate blocks
— with the actual error text, failing test name, and diff attached — converts the
entire deterministic-failure class from hopeless to solvable.

### 3.2 The queue is flat; the work is not

Five tasks editing `config.py`/`graph.py` ran as parallel branches off one base and
produced a conflict cascade. Tasks need declared file scopes and a dependency graph so
conflicting work is sequenced and independent work can eventually parallelise.

### 3.3 Quality is judgement, and judgement does not scale

`graph.py` is 3,400+ lines and grows every mission. No task refactors it. The strong
fix is to **encode architecture as tests**: file-size ceilings, duplicate-symbol
detection, every gate registered in the shared authority module (would have caught all
three guard-interaction bugs at PR time), config three-place-rule enforcement, tests
that assert nothing. Once required, decay cannot merge.

### 3.4 Workers are context-starved

Fresh `claude --print` per task, ~1,900-char prompt, no knowledge of the mission, what
already shipped, or what comes next. Directly produced: duplicate implementations,
refusals ("do you want me to…"), scope creep. Fix designed (mission briefing +
already-satisfied precheck); not yet built.

---

## 4. What is genuinely sound

Worth stating so the review is not all critique:

- **PR + branch protection as the merge authority.** Nothing broken has reached main
  since M0.8b. This is the load-bearing safety property and it holds.
- **Evidence-based completion (m4c-02).** The right foundation — it makes lying
  structurally hard rather than discouraged.
- **File-based gates with Slack/inbox fulfilment.** Simple, inspectable, recoverable
  by hand. Resisted the temptation to build a stateful approval service.
- **The credential boundary.** The runner uses granted access and never grants itself
  more. Correct, and non-negotiable while it ingests foreign repos.
- **Stop diagnostics (m4c0-05).** Turned a multi-hour grep into a one-minute read on
  its first real use.
- **Statelessness per task.** Deliberate and right; the fix is better inputs, not
  shared memory.

---

## 5. Honest limits — what no amount of building fixes

- **Product judgement.** Which business to build, whether an abstraction is wrong
  rather than ugly, when to kill an idea. Market Radar converts *idea sourcing* to
  evidence and the validation ladder converts *idea testing* to measurement — but
  choosing among ranked candidates and setting kill thresholds stays human.
- **Novel architectural design.** The loop executes well-specified work; it does not
  decide that the system needs a different shape.
- **Host death.** On a laptop, a reboot ends the run. Only different hardware fixes it.
- **Mission authoring quality.** Machine-authored missions will be materially weaker
  than ones written from real incident analysis. Plan for founder-authored missions
  at strategic boundaries indefinitely.

---

## 6. Recommended mission structure

**M4c.4 — Force Multipliers (4 tasks) — RUN THESE FIRST.**
Small, independent, and each one raises the first-attempt success rate of every task
that follows. Running them before the other 29 tasks is the highest-leverage
sequencing decision available; running them last wastes their compounding entirely.

| # | Task | Why first |
|---|---|---|
| 01 | **Crash-safe checkpointing** | m4c-03's 1,552 lines sat uncommitted for days. Until this exists, every halt risks losing work — including the work of the tasks below. Cheapest task in the whole plan. |
| 02 | **Failure-context repair loop** | Deterministic failures currently have a 0% recovery rate. Every subsequent mission inherits that. Fixing it first means the remaining 29 tasks get repaired instead of exhausted. |
| 03 | **Mission briefing + already-satisfied precheck** | Already queued as `m4c0-06`. Every task after it is better-informed; every task before it is not. |
| 04 | **Plan-then-execute pass** | M4c.5 is 12 tasks nearly all touching `graph.py`/`config.py` — precisely the pattern that produced a day of merge conflicts. This detects the collisions *before* the code is written, and produces the file scopes M4c.5-10 needs. |

**M4c (finish, 6 tasks left)** — the floor: stops dying.
environment ownership · watchdog · auto-approval/skip-and-continue · roadmap-as-data ·
self-provisioning + ntfy · verification report.

**M4c.5 — Self-Repair & Integrity (12 tasks)** — the mission that makes it good.
Ordered so each task's dependencies land before it, and so nothing that increases
blast radius ships before the safety net:

| # | Task | Covers |
|---|---|---|
| 01 | **Failure-context repair loop** — route CI failures, merge conflicts, gate blocks and evidence blocks into `auto_repair_loop` with the failing test name, error text and diff attached | §3.1 |
| 02 | **Crash-safe checkpointing** — signal/atexit handlers commit WIP to the task branch on every exit path | §2.1, m4c-03 incident |
| 03 | **External supervisor + auto-revert** — shell/systemd wrapper outside the loop; last-known-good SHA; canary run after any `runner/` merge; revert on failure | §2.1a, §2.3 |
| 04 | **Behavioural fixtures** — replay recorded real incidents (session-limit payload, PR #94 conclusions, refusal transcript, conflict) and assert correct classification | §2.1b |
| 05 | **Verification-capture defence** — constitutional file list + test-weakening detection in CI (assertion counts, deletions, skip/xfail, loosened asserts) | §2.1c — highest severity |
| 06 | **Record & replay** — persist worker prompts *and* responses; `main.py replay <task>` reruns a failure locally and free | §7.4 (also generates 04's fixtures) |
| 07 | **Mission briefing + already-satisfied precheck** | §3.4 |
| 08 | **Stop-reason auto-remediation playbooks** — execute the safe remedies (update-branch, rebase, requeue orphan, apply invariant fix) | §2 generally |
| 09 | **Self-seeding repair tasks** — with error-signature dedupe, depth cap, per-session budget, quarantine | §2.2 |
| 10 | **Scope enforcement + destructive-op prohibitions** — declared paths, post-work diff check, mandatory stash, no force-push to main, no deleting unmerged branches | §2.5 |
| 11 | **Model routing + budget projection** — per-task-type model choice; warn before the cap, not after | §2.10 |
| 12 | **External-contract fixtures** — recorded payload shapes for Claude CLI, Codex, GitHub checks, Vercel; contract test per tool | §2.4 |

**M4d — Scheduling, Quality & Observability (11 tasks)**

| # | Task | Covers |
|---|---|---|
| 01 | **Plan-then-execute pass** — per-task implementation plans, file scopes, conflict + duplicate detection before any code | §7.1 (feeds 02, 03, and M4c.5-10) |
| 02 | **Dependency-graph scheduler** — sequence conflicting tasks, parallelise the rest | §3.2 |
| 03 | **Parallel execution** — worktree per worker, serialised merge queue, provider fan-out | §7.2 |
| 04 | **Adversarial reviewer** — duplicate / test-weakening / scope / constitutional checklist, blocking on those specific findings | §7.3 |
| 05 | **Architecture-as-tests** — file-size ceilings, duplicate symbols, gate registration, three-place rule, assertion-free tests | §3.3 |
| 06 | **`graph.py` refactor** — split before it crosses 4,000 lines | §3.3 |
| 07 | **Outcome verification** — production SHA, live URL, Sentry signature, M3 funnel events as a post-deploy gate | §2.6 |
| 08 | **Heartbeat + dashboard tile** — live status on the existing Operating Team UI | §2.8 |
| 09 | **Morning digest + architectural drift audit** — one message; worst offenders become candidate tasks | §2.8, §3.3 |
| 10 | **Log rotation + secret-egress sanitisation** — retention, index, single outbound choke point with realistic-secret tests | §2.7, §2.9 |
| 11 | **Loop telemetry + LESSONS.md** — per-task-type success/cost/duration; curated lessons injected into every prompt | §7.6, §7.7 |

**Founder-side, outside the missions:** Tailscale + `openssh-server` + `systemd=true`
in `/etc/wsl.conf` (§2.8), and raising or routing around the Opus spend cap (§2.10).

Net sequence: **M4c.4 (4) → M4c (6) → M4c.5 (12) → M4d (11)** = 33 tasks. M4c.5-01,
02 and M4d-01 move into M4c.4, so those missions shrink accordingly.

---

## 9. Known holes — deferred, accepted, or small

Tracked explicitly so nothing here is forgotten by omission.

**Deferred by decision (revisit at the stated trigger):**
- **Parallel execution** — until the Claude plan is upgraded (Max 20x) *and* the
  error rate is consistently low. Multiplying blast radius before then is negative
  value. Trigger: M4c.5 complete + a clean unattended overnight run.
- **VPS migration** — SUPERSEDED for now by the founder's host plan (2026-08-04):
  power settings keep the machine awake with the lid shut on AC, which removes the
  sleep failure mode entirely. Windows restarts/updates are accepted as rare. The
  residual risk is therefore not "the machine sleeps" but "the runner is dead and
  nobody knows", which is solved by auto-restart + a dead-man's switch (§9.1) rather
  than by new hardware. Revisit a VPS only if restart frequency proves higher than
  expected, or when concurrency demands a bigger box. The wrinkle to budget for when
  that day comes: subscription auth on a headless box needs `claude setup-token` or
  API mode.
- **Market Radar / product judgement** — post-M5, after one manual pass through
  §6.1 proves the rubric ranks sanely.

**Accepted limits (no fix planned):**
- Machine-authored missions will stay materially weaker than founder-authored ones
  written from real incident analysis. Plan for founder-written specs at strategic
  boundaries indefinitely.
- Taste — whether an abstraction is wrong rather than ugly — stays human.

### 9.1 Host death — auto-restart plus a dead-man's switch

A dead runner cannot tell you it is dead. Any notifier living on the same machine
dies with it, so this needs two independent pieces:

**Self-recovery (handles most cases).** A Windows Task Scheduler job triggered
"at log on" / "at startup" that runs
`wsl.exe -d Ubuntu -- bash -lc "cd ~/bucks-ai/runner/langgraph && ./scripts/start-loop.sh"`,
where the script is the §2.1a supervisor. After a Windows update reboot, the loop
comes back by itself and you are told it restarted rather than asked to restart it.

**External dead-man's switch (catches when self-recovery fails).** The loop pings a
third-party check-in URL (Healthchecks.io free tier, or Cronitor) every N minutes; if
the ping stops for longer than the grace period, *their* servers notify your phone.
This must be external — an internal watchdog cannot detect its own host being off.
Five minutes to set up, no code beyond one HTTP call in the heartbeat path.

An in-house variant is possible later — the runner already writes to Supabase, so a
Vercel cron route could compare heartbeat age and fire ntfy — and it dogfoods the
product. Prefer the external service first: it has no shared failure mode with the
stack it is watching.

**Small, unscheduled, should be picked up opportunistically:**
- `doctor --fix` detects Supabase divergence but cannot repair it (11 rows currently
  diverged; fixed by hand SQL today). **Root cause and real fix (§9.2):** Supabase
  writes are fire-and-forget — a failed sync is logged and dropped. Declare the local
  queue the source of truth for execution and Supabase a *projection* of it, then give
  the sync a durable outbox: failed writes queue locally and replay on the next tick,
  and `doctor --fix` replays the projection for any `status_mismatch`. This matters
  more than it looks: `check_mission_completion` derives mission status from
  `mission_tasks` rows, so unsynced completions leave a mission permanently
  `in_progress` — and m4c-08's auto-chaining reads exactly that field to decide what
  runs next. Left unfixed, the autonomy story stalls on a bookkeeping bug. Schedule
  in M4c.5.
- `datetime.utcnow()` deprecation across ~15 call sites — becomes a hard error in a
  future Python, and the runner does real time arithmetic on those values (cooldown
  resume, stale windows, retry backoff). Also 700+ lines of warning noise per test
  run, which hides genuine warnings.
- The `E2E (Playwright, Vercel preview) [informational]` job fails on essentially
  every PR. Now correctly ignored, but a permanently-red check trains everyone to
  ignore checks. Fix it or delete it.
- `graph.py` past 3,400 lines — scheduled in M4d-06, but the longer it waits the more
  conflict-prone every mission becomes.
- No timeline/ETA model. M4d-09's digest gives progress; nothing projects a finish
  date or flags drift against a plan.

---

## 7. Exponential improvements — beyond fixing what is broken

Sections 2–3 remove failure. These change the ceiling. Ranked by leverage per unit of
build effort.

### 7.1 Plan-then-execute (two-pass missions) — highest leverage

Before any code is written, run a cheap planning pass over the whole mission: for each
task, a Sonnet-class worker reads the relevant code and emits a short implementation
plan — files it expects to touch, the approach, whether the deliverable already
exists, and which other tasks in the mission touch the same files. Costs a fraction of
an execution pass and produces, before the first line of code:

- the **file-scope declarations** §2.5 and §3.2 both need, derived rather than guessed
- **conflict detection** — the exact failure that cost a full day (five tasks editing
  `config.py` on parallel branches)
- **duplicate detection** — "this already exists at X" before building it again
- **right-sizing signal** — a task whose plan lists 14 files is too big; split it

This single mechanism feeds three other fixes. Build it early.

### 7.2 Parallel execution — the throughput multiplier

With file scopes from 7.1, non-conflicting tasks can run concurrently. Combined with
provider routing (Claude + Codex simultaneously), this is the difference between ~15
tasks a night and ~40. Requires: a scheduler honouring the dependency graph, one
worktree per concurrent worker (never one shared checkout — that is how uncommitted
work gets destroyed), and a serialised merge queue so two green PRs cannot race.

Do not attempt before §2.1 (self-modification safety) and crash-safe checkpointing
are solid; parallelism multiplies the blast radius of every unfixed bug.

### 7.3 Adversarial reviewer — one mechanism, three holes

A second worker reviews each diff before merge against a fixed checklist: does this
duplicate something already on main? does it weaken or delete tests? does it touch
files outside the declared scope? does it change a constitutional file? A different
model reviewing another's work catches things self-review structurally cannot. This
covers §2.1c, §2.5 and the semantic-duplicate gap in one component. The
`INDEPENDENT_CODE_REVIEW_ENABLED` gate already exists in warn-only mode — give it this
checklist and promote *these specific checks* to blocking while leaving stylistic
findings advisory.

### 7.4 Record and replay

Persist every worker prompt **and response** (prompts already land in `outbox/`).
Then any failure can be replayed locally, free, deterministically — including against
a modified runner, to prove a fix works before shipping it. This is the difference
between debugging the runner from log archaeology and debugging it like normal
software. It also generates the behavioural fixtures §2.1b needs, for free, from real
incidents.

### 7.5 Nightly self-test canary

A tiny always-queued mission — one trivial task exercising the full chain: dispatch →
edit → check → commit → PR → CI → merge → deploy → verify. Runs before real work each
session. If the chain is broken, you learn it from a canary in three minutes rather
than from a real mission failing at 3am. Cheap, and it catches exactly the class of
breakage §2.1b describes.

### 7.6 LESSONS.md — memory without shared state

A single append-only file of durable, repo-specific lessons ("`cfg.repo_path` defaults
to a developer home dir — pin it in tests", "advisory checks are non-blocking",
"config changes need three places"), injected into every worker prompt. Preserves
statelessness — it is an *input*, not a session — while ending the repetition of
lessons already learned. The cheap 80% of M8's memory, available now. Entries are
written by the verification pass at each mission's end, so the file stays curated
rather than sprawling.

### 7.7 Telemetry on the loop itself

Per task type: first-attempt success rate, repair-attempt success rate, mean duration,
mean cost, most common failure class. This is what turns model routing, task sizing,
and threshold tuning into data-driven decisions instead of guesses — and it is the
only way to answer "is the babysitter actually getting better" with evidence.

---

## 7.8 Noted for later — self-direction (founder, 2026-08-04)

Two ideas that follow directly from auto-restart + dead-man's switch, deliberately
**not** scoped now:

**Approve-from-phone.** Once the loop can start itself, a mission approval becomes a
push notification with Approve / Decline. Approve → the runner starts itself and
begins the mission. This is a natural extension of the existing ntfy path (m4c-09)
plus the file-based gate convention: the notification action writes the same
fulfilment file a Slack button does. Small once both halves exist. **Belongs in M4c-08
(roadmap-as-data) as a follow-on, or M4d.**

**Self-directed mission authoring.** The system proposing its own direction — not just
executing an approved roadmap, but deciding what the roadmap should contain. This IS
already in the plan: `BUCKS_AI_MASTER_ANALYSIS.md` §8 specifies "weekly review
PROPOSES candidate missions from observed data; founder approves", and M8 (business
memory + evaluation) is where it lands, fed by M3 analytics and the experiment log.
M4c-08's roadmap-as-data is the storage substrate it will write into.

**When M8 is scoped, carry these forward:** proposals must arrive with the evidence
that motivated them (which metric, which failure class, which log signature), the
founder approves at the plan level only, and the same incident-mining that produced
the M4c spec is the mechanism most likely to make machine-authored missions good.

## 8. The one-line test

If M4c.5 and M4d ship and the founder is still hand-running `gh pr merge`, editing
runtime JSON, or discovering a dead loop the next morning, they failed — regardless
of what their tests say.
