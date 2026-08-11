# M4c.5 + M4d — the 19 remaining tasks, ranked

**Compiled 2026-08-11**, after M4c reached 11/11 and the runner completed an
unattended overnight run with **zero founder touches**.

Source of the task list: `docs/BABYSITTER-DESIGN-REVIEW.md` §  (the M4c.5 and
M4d tables). Those entries are one-line rows, **not seed-quality descriptions** —
each needs expanding before it can be queued.

**Already landed early** (pulled into M4c.4, so not in the 19): M4c.5-01
failure-context repair (`m4c4-02`), M4c.5-02 crash-safe checkpointing
(`m4c4-01`), M4d-01 plan-then-execute (`m4c4-04`). M4c.5-07 mission briefing is
in flight now as `m4c0-06`.

**The honest frame:** none of these 19 reaches a customer. They harden a
babysitter that already works. Ranked below by what they protect, not by
where they sit in the roadmap.

---

## Tier 1 — Do these three before running unattended while selling

The set that stops the runner quietly hurting itself when nobody is watching.
One evening of work.

### M4c.5-05 — Verification-capture defence
**What:** a constitutional file list (tests, gates, CI config) that workers may
not weaken, plus CI detection of test-weakening — assertion-count drops,
deleted tests, new `skip`/`xfail`, loosened asserts.

**Why it's first:** an agent that can edit its own tests can make any gate pass.
Every other safety mechanism you have — completion evidence, DoD, code review —
assumes the tests are honest. The design review flags this as the highest
severity item in either mission. No incident yet; the failure mode is that you
would not find out.

### M4c.5-10 — Scope enforcement + destructive-op prohibitions
**What:** declared file paths per task, post-work diff check against them,
mandatory stash before branch ops, no force-push to main, no deleting unmerged
branches.

**Why:** already happened. A worker built the Stripe/Resend/Twilio/PostHog
adapters that were explicitly deferred (PR 118) — the scope decision lived in a
doc the worker never reads. Separately, `branch_cleanup_forced` issued `git
branch -D` on a branch git had refused to delete with `-d`, which is the "not
fully merged" signal being overridden.

### M4c.5-03 — External supervisor + auto-revert
**What:** last-known-good SHA, a canary run after any `runner/**` merge, and
automatic revert if the canary fails. The supervisor process sits outside the
loop.

**Why:** the runner modifies itself and merges autonomously. `m4c-06` gave you
the watchdog (restart), but nothing detects "the merge I just made broke me."
`m4c4-07` shipped a half-fix that went unnoticed for days — a canary would have
caught it in one run.

---

## Tier 2 — High value, do during the product phase

### M4c.5-04 — Behavioural fixtures
Replay recorded real incidents (session-limit payload, PR check conclusions,
refusal transcript, merge conflict) and assert correct classification.

**Evidence, this week:** a revoked OAuth token (401) was recorded as `"worker
returned no output"` and scheduled for retry. A monthly-spend-limit 429 was
treated as a resumable cooldown and slept against for ~4 hours. Both are
classification bugs; both are exactly what fixtures catch. `m4c-11` fixed the
routing for these two — fixtures stop the next one.

### M4c.5-06 — Record & replay
Persist worker prompts *and* responses; `main.py replay <task>` re-runs a
failure locally, free.

**Why:** every diagnosis this week cost either a full CI round-trip or a live
worker run. Replay makes debugging free, and it generates the fixtures M4c.5-04
needs.

### M4d-04 — Adversarial reviewer
A review pass that specifically checks for duplicated work, test-weakening,
scope violations and constitutional-file edits, and blocks on those findings.

**Why:** overlaps Tier 1 and catches the same class at a different stage.
Cheaper than 05 + 10 alone are thorough.

### M4d-10 — Log rotation + secret-egress sanitisation
Retention and indexing for `runs.jsonl` (already 9 MB+), plus a single outbound
choke point that sanitises secrets, with realistic-secret tests.

**Why:** worker output flows into `runs.jsonl`, Slack, PR bodies and stop
reports. Outbox approval files are sanitised; the general logging path is not
verified to be. This matters more once real customer credentials exist.

### M4d-07 — Outcome verification
Production SHA, live URL reachability, Sentry signature and M3 funnel events as
a post-deploy gate.

**Why:** becomes important the moment you have users — it is the difference
between "deployed" and "actually working for a human."

---

## Tier 3 — Real value, no urgency

### M4d-06 — `graph.py` refactor
Split it before it crosses 4,000 lines (already past 3,400).

**Note:** this one has a direct cost effect. Cache-read input tokens dominate
every task's bill, and nearly every runner task pulls `graph.py` into context.
Splitting it reduces per-task spend, which matters while you are credit-bound.

### M4c.5-08 — Stop-reason auto-remediation playbooks
Execute the safe remedies automatically: `update-branch`, rebase, requeue
orphan, apply an invariant fix.

**Evidence:** you hand-ran `gh pr update-branch`, `doctor --fix` and task-status
reconciliation repeatedly this week. Each was a founder touch that a playbook
removes.

### M4d-09 — Morning digest + architectural drift audit
One message summarising the night; worst drift offenders become candidate tasks.

**Why it's worth more than it looks:** it replaces the "check on the runner"
round-trip you currently perform manually every morning.

### M4c.5-11 — Model routing + budget projection
Per-task-type model choice; warn *before* the cap, not after. **Partially done**
— `m4c-11` shipped cost/token instrumentation and the spend-without-progress
ceiling.

### M4d-11 — Loop telemetry + LESSONS.md
Per-task-type success rate, cost and duration; curated lessons injected into
every prompt. Partially unblocked by `m4c-11`'s instrumentation.

### M4c.5-12 — External-contract fixtures
Recorded payload shapes for the Claude CLI, Codex, GitHub checks and Vercel,
with a contract test per tool. Closely related to M4c.5-04.

### M4d-05 — Architecture-as-tests
File-size ceilings, duplicate-symbol detection, gate registration checks,
three-place-rule enforcement, assertion-free-test detection.

### M4d-08 — Heartbeat + dashboard tile
Live runner status on the existing Operating Team UI. Also dogfoods the product
surface a customer sees.

---

## Tier 4 — Defer explicitly

### M4c.5-09 — Self-seeding repair tasks
The runner creating its own tasks, with signature dedupe, depth cap, per-session
budget and quarantine.

**Why deferred:** powerful and genuinely risky — an agent that writes its own
backlog. Must come *after* M4c.5-05 and M4c.5-10, never before. Also directly
against the current goal: it generates more runner work at a moment when the
constraint is customers, not throughput.

### M4d-02 — Dependency-graph scheduler
Sequence conflicting tasks, parallelise the rest. Largely covered already by
`m4c4-04`'s conflict detection.

### M4d-03 — Parallel execution
Worktree per worker, serialised merge queue, provider fan-out.

**Why deferred:** parallelism buys wall-clock time, and you are **token-bound,
not time-bound**. Running four workers at once does not create more plan usage;
it exhausts it faster. Revisit if the credit constraint lifts.

---

## Summary

| Tier | Count | When |
|---|---|---|
| 1 — protect the unattended runner | 3 | before selling starts |
| 2 — high value | 5 | during the product phase |
| 3 — real value, no urgency | 8 | opportunistic |
| 4 — defer explicitly | 3 | after Tier 1, or never |

**Recommended:** run Tier 1 (3 tasks, ~1 evening), then point the runner at the
product. Tiers 2–4 are a backlog `m4c-08` can chain into whenever there is spare
capacity — they should never be the reason a customer waits.
