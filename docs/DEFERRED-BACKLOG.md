# Deferred Backlog — work consciously postponed, never dropped

**Purpose:** every item here was deliberately deferred, with a reason and a
**trigger** that says exactly when to pick it back up. Nothing in this file is
cancelled. If an item's trigger fires and it is still sitting here, that is a
process failure.

**Review cadence:** read this file (a) at the start of every new mission phase,
(b) before writing any new mission spec, and (c) as a required step of
`m4c-10` and every future verification task. `m4c-08` (roadmap-as-data) MUST
ingest this file alongside the approved roadmap so deferred work is visible to
the planner, not just to the founder.

**Created:** 2026-08-08, after the M4c.4 scope review.

---

## 1. m4c4-05 — Network pause — ✅ RESOLVED 2026-08-09, SUPERSEDED

**Status:** SUPERSEDED by `m4c4-05b-network-pause-watchdog`, seeded at the
front of the queue (`runner/langgraph/seed_network_pause.py`). The original
`m4c4-05` stays at the back of the queue marked `superseded_by`. **Do not build
both.**

**What changed:** `m4c-06` merged (PR 111, `f10358d`) and
`tools/loop_watchdog.py` now owns the entire sleep-and-restart mechanism the
original spec would have duplicated — hard-gate exclusions, limits-aware
waits, and a 30s default restart delay that IS the poll interval m4c4-05
asked for. The derived task therefore builds only the three genuinely missing
pieces: a connectivity probe, network-error classification that touches no
counters, and a cumulative patience ceiling.

**Founder decision 2026-08-09 — no VPS.** Of everything the VPS would have
solved for this setup, only "losing wifi while driving" mattered, and the
derived task covers it directly. Overnight-run capability is already in place
(see §5, which is now optional rather than recommended).

**Original spec (retained for reference):** `runner/langgraph/seed_m4c4.py`,
TASKS entry `m4c4-05-network-pause`

**What it does:** treats total connectivity loss as an environmental pause
(probe before dispatch, classify network-shaped errors mid-call, touch no
counters while paused, poll every 30s, give up after 90 min).

**Why deferred — two independent overlaps:**
1. `m4c-06` (continuous operation) builds limits-aware pause/resume — the same
   "environmental pause" machinery, for a different trigger. Building both
   separately risks two competing wait mechanisms; the m4c4-05 spec itself says
   "reuse that machinery; do not invent a second waiting mechanism."
2. Its motivating scenario — *the founder's laptop moves between locations with
   no wifi* — is deleted entirely by moving the runner to an always-on VPS
   (see item 5 below). A datacentre box does not drive anywhere.

**Trigger to revisit:** when `m4c-06` lands, check whether its pause/resume
machinery already covers connectivity loss. If yes, close this as absorbed and
record that. If no, build it AS AN EXTENSION of m4c-06's mechanism, not a
parallel one. Also revisit immediately if the always-on-host migration is
abandoned and the runner stays on the founder's laptop.

**Cost of being wrong:** low. A network blip currently burns retry counters and
pollutes failure telemetry — annoying, not destructive, and only while the
runner lives on a mobile machine.

---

## 2. m4c0-06 — Mission-context briefing

**Status:** seeded, moved to back of queue
**Original spec:** seeded separately; referenced as task 03 in `seed_m4c4.py`

**What it does:** gives each worker a briefing on the mission it is working
inside, so tasks are executed with awareness of the surrounding plan.

**Why deferred:** weakest evidence of any M4c.4 item — it was reasoned from
first principles rather than derived from a specific logged failure, unlike its
siblings (each of which traces to an incident). It also works AGAINST the
dominant cost driver: cache-read input tokens already reach ~1.4M per task, and
this adds context to every call.

**Trigger to revisit:** when there is direct evidence a worker failed or
duplicated work *because it lacked mission context* — e.g. `m4c4-04`'s
duplicate-detection flags a task whose deliverable already existed, and the
root cause is the worker not knowing what the mission had already built. At
that point this stops being speculative.

**Also revisit if:** cost-per-task instrumentation (item 4) shows context size
is NOT the dominant cost, which removes the main argument against it.

---

## 3. m4c-09 — Speculative vendor adapters (PARTIAL deferral)

**Status:** m4c-09 REMAINS IN THE ACTIVE SEQUENCE. Only the speculative
adapters below are deferred.
**Original spec:** `docs/M4C-MISSION-SPEC.md` § m4c-09

**IMPORTANT — what is NOT deferred, and why.** Parent-child provisioning is
doctrine (`STRATEGY.md` §3) and is load-bearing for the product itself: a
business that cannot mint its own project, key or domain cannot ship. Building
it is the bridge to running real businesses, not a reward for already running
them. The following ship in the active sequence:
- the provisioning **framework** and adapter pattern,
- adapters for the vendors actually in use today: **GitHub** (repos, tokens),
  **Vercel** (projects, env vars, domains, git links), **Supabase**
  (projects/keys),
- **dependency batch-ahead** (one consolidated credential request up front),
- **phone push** (ntfy.sh/Pushover; the single alert class that reaches the
  founder).

**Deferred:** adapters for **Stripe Connect** (sub-accounts), **AWS**
(Organizations/IAM), **Resend** (domains, sending keys), **Twilio**
(subaccounts), **PostHog** (per-business projects).

**Why:** no business has yet requested any of them, so their usage shape is
unknown — five integrations built to a guess are five integrations likely built
wrong, each with its own auth model and failure modes. With the adapter pattern
in place, adding one later is a small, well-informed change.

**Trigger to revisit — per vendor, not as a batch:** the first time a real
business (customer or dogfood) needs that specific vendor. `m4c-09`'s
dependency batch-ahead will surface the need explicitly, by design. Build that
one adapter then, against a concrete requirement.

**Cost of being wrong:** low, and self-correcting — batch-ahead turns a missing
adapter into one prepared 30-second credential request rather than a blocker.

---

## 4. Runner usage/cost instrumentation

**Status:** NOT SEEDED — exists only here
**Origin:** identified 2026-08-08 while trying to answer "what does a task
actually cost?" and finding the data does not exist.

**The gap:** the runner logs `total_cost_usd` and token usage from the Claude
CLI JSON **only on the failure path**. Successful runs record
`session_cost: 0.0`. So there is no per-task cost or token data for any task
that worked — cost-per-task cannot be computed, and trends cannot be seen.

**What to build:** parse `total_cost_usd` and the `usage` block on the SUCCESS
path too; accumulate into `session_cost`; include cost and token totals in
`run_summary_digest` and in `live_batch_validation_complete` metrics so
cost-per-task is reportable per batch.

**Why deferred:** it was proposed to inform the decision "is $50 of credit
enough?" — that decision is now made (the trimmed active sequence is ~8 tasks
at an estimated $5–8, comfortably inside budget), so the measurement is no
longer decision-relevant. It buys insight, not autonomy, and does not advance
"the loop stops needing the founder."

**Trigger to revisit — this one is close, treat it as near-term:** BEFORE
starting M4c.5 or M4d. Those are 23 tasks with no specs and therefore no size
estimate; committing real money to them without cost-per-task data repeats the
exact blindness that made this gap visible. Also revisit immediately if a
single task's cost ever surprises you again.

---

## 5. Always-on host migration (FOUNDER ACTION — not a runner task)

**Status:** not started
**Original spec:** `docs/M4C-MISSION-SPEC.md` § "Companion infra task"

**What:** (1) immediate — Windows power settings: lid-close-when-plugged-in =
"Do nothing", sleep = "Never". (2) durable — migrate the runner and its `.env`
to a cheap always-on VPS ($5–10/mo, Hetzner/DO).

**DOWNGRADED 2026-08-09 — founder decision: no VPS for now.** The laptop
already has overnight-run capability, and the one problem the VPS uniquely
solved for this setup — losing wifi while driving — is handled directly by
`m4c4-05b-network-pause-watchdog` (§1). The remaining VPS benefits (surviving
Windows updates, reboots, power loss; killing the stale-shell-export env-drift
class) are real but not currently blocking anything. Keep the power settings;
treat the VPS as optional.

**Why it stays in this file:** it is a founder action that no runner task will
ever pick up, which makes it the single most forgettable item here. Revisit if
the runner starts losing overnight runs to machine-level failures (updates,
reboots, sleep) rather than to network or quota — that is the signal the
laptop has become the bottleneck.

**Why it matters:** the babysitter keeps the *loop* alive; it cannot keep the
*machine* alive. Closing the laptop sleeps WSL and kills the runner regardless
of how much continuous-operation work has shipped. Until this is done, every
hour of `m4c-06` is theoretical. Per the spec: **"Always-on host + babysitter =
actual 24/7."** It also eliminates the stale-shell-export bug class that bit
three times during M4b (`DIRECT_DATABASE_URL`, `VERCEL_TOKEN`, env drift), and
deletes the motivating scenario for item 1 above.

**Trigger:** before `m4c-10`'s acceptance test, which is *"run a real mission
overnight, unattended."* That test cannot pass honestly on a laptop that
sleeps. Do the power settings today; do the VPS before m4c-10.

---

## 6. Scope already satisfied — verify, do not rebuild

Not deferred; recorded so nobody builds them twice.

**m4c-07 — the auto-approve-merges half.** `m4c-07`'s stated scope includes
auto-approving merges that already passed CI. This is already working:
`RISK_BASED_MERGE_APPROVAL_ENABLED=true` with `merge_approval_policy=auto`
merged PRs 107, 108 and 109 unattended on 2026-08-08 with no founder input.
**When m4c-07 runs, build only the SKIP-AND-CONTINUE behaviour** — a missing
credential must set that one task aside and let the loop continue, instead of
halting everything (observed repeatedly across M4b). The spec says this
directly: *"the value of this item is not the gate; it is the skip-and-continue
behaviour."* Verify the merge half rather than rewriting it.

---

## 7. Known prerequisite risk — m4c-08 (roadmap-as-data)

Not deferred (founder decision 2026-08-08: keep it in sequence while it is
planned, so it cannot be forgotten). Recorded here as a **dependency warning**.

`m4c-08` ingests "the approved mission plan (M4d→M9+) as structured data, each
entry pre-written to full seed quality with an `approved` flag." **Those specs
do not currently exist** — M4c.5 (12 tasks) and M4d (11 tasks) are not seeded
and have no documents in `docs/`. An ingester with nothing to ingest will
either no-op or invent its own backlog.

**Required before m4c-08 executes:** write M4c.5 and M4d to seed quality, or
explicitly scope m4c-08 to build the *mechanism* (schema, approved flag,
auto-seed-on-clean-completion, `STRATEGY.md` doctrine ingestion, and ingestion
of THIS file) and accept that the backlog is populated later. Decide which,
deliberately, before it is claimed — do not let a worker discover this at
runtime.
