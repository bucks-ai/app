# M4b Verification Report

Mission: **M4b — Sandbox-per-Business Execution**. This is the done-when
evidence for `m4b-09-verification-report`, and the centerpiece of the M4
pivot proof corpus. The claim under audit is:

> *"Our system executes missions against customer repos under containment."*

**This report supersedes the 2026-07-26 revision** (PR #90), whose verdict —
"the M4 pivot has not been demonstrated live" — was correct on its date and
was invalidated by events on 2026-07-27 through 2026-07-31. The two
blockers that report identified as fatal (the sandbox-config storage split,
and the unmerged claim gate) were both closed, and `m4b-08` then ran. The
prior text is preserved in git history at `d3387ea` and should be read as
the pre-pivot baseline, not as a current statement of fact.

Verification pass performed **2026-08-03**, combining: the full runner and
app test suites, read-only probes against the production Supabase project,
live execution of the containment guard functions against real production
configuration, forensic inspection of the business repository the runner
built into, and an HTTP probe of the resulting deployment. **No production
data was written during this pass. No mission was claimed, and no business
repo, Vercel project, or credential was created or modified.**

---

## Verdict

**The core claim is demonstrated, with one material qualification.**

The runner autonomously cloned a customer-owned GitHub repository
(`rangasatvik/testflow-demo`, business "AI Infra"), built a working
application into it across **5 commits and ~1,787 insertions**, and pushed
to **9 feature branches on the customer's remote**. The result is live and
serving at **https://testflow-demo.vercel.app** (verified HTTP 200 this
pass, `<title>Testflow Security Assessment</title>`). Containment held:
**zero business content entered the bucks-ai repository**, verified against
the commit log for the execution window.

**The qualification — and it is load-bearing for an outside reader:**

1. **The deploy step was performed manually by the founder**, not by the
   runner. Everything *built* was autonomous; the step that made it *live*
   was not. Root cause is a broken business-task worker dispatch, documented
   below and specified as M4c item 12.
2. **The task-status ledger cannot be used as evidence of what was done.**
   6 of 8 tasks are marked `complete` with summaries reading
   `Files: created none; modified none`. The git history of the customer
   repo — not the ledger — is the only trustworthy record of the work.
3. **Reaching this took ~6 hours of founder debugging in one session.** Per
   the founder's own contemporaneous notes, zero of those hours were the AI
   failing to write code; every blocker was harness plumbing. That failure
   list became the M4c specification.

So the honest one-line claim the proof corpus can support is: **"our system
autonomously builds into customer repositories under verified containment,
and cannot yet ship the result unattended."** The stronger claim —
end-to-end unattended execution — is **not** yet supported.

---

## 1. What `m4b-08` demonstrated live, with artifact paths

Every artifact below was inspected directly during this pass.

### 1.1 The customer repository

| Fact | Value | How verified |
|---|---|---|
| Business | "AI Infra", `business_id` `931f4a57-007c-419f-8209-7957a9f5d8eb` | Live `business_sandbox` row |
| Customer repo | `rangasatvik/testflow-demo` | `git remote get-url origin` in the workspace |
| Local workspace | `runner/langgraph/.workspaces/931f4a57-007c-419f-8209-7957a9f5d8eb` | Present on disk, gitignored (`.gitignore:72`), untracked |
| Commits by the runner | 5 | `git log` in that workspace |
| Remote branches pushed | 9 (`origin/feature/ai-infra/*`) | `git branch -r` |
| Live deployment | https://testflow-demo.vercel.app → **HTTP 200** | `curl` this pass |

**The five commits** (workspace `git log --oneline`):

```
903a244  Build security assessment landing sections          2 files,   +82
8cb6b8c  Build security assessment landing page              2 files,  +129
36c0f15  Instrument analytics capture: visits, demos, opens  7 files,  +260
39050b6  Scaffold infra: Node/Express, Docker, AWS, Postgres 13 files, +1316
1116bdd  Build security assessment MVP (root)                8 files, +2618
```

**Corrected build metrics.** The `CHAT_HANDOFF_2026-07-11.md` closure note
claims "1,819 insertions across 19 files." The precise figures are:

- **1,787 insertions** across the four commits after the root commit.
- The root commit's 2,618 insertions include **1,730 lines of generated
  `package-lock.json`**, which no honest reader should count as authored work.
- **21 tracked files** at HEAD; **1,617 lines excluding the lockfile**.

The handoff figure is approximately right but was never recomputed. An
outside auditor should cite **~1,600 lines of authored application code
across 21 files**, not the headline number.

**What was actually built** (`git ls-files` at HEAD): a React frontend
(`src/App.jsx`, `src/styles.css`, `index.html`), an Express + Postgres
analytics backend (`server/index.js`, `server/analytics.js`, `server/db.js`,
`server/migrations/0001_create_analytics_events.sql`), containerization
(`Dockerfile`, `docker-compose.yml`, `.dockerignore`), AWS ECS deploy config
(`infra/aws/ecs-task-definition.json`, `infra/aws/deploy-aws.yml.example`),
and documentation (`README.md`, `docs/security-best-practices.md`).

### 1.2 Containment, verified

`git log --since=2026-07-29 --until=2026-08-01` on bucks-ai returns six
commits, all founder-authored M4c specification and sandbox-config work.
**No business application code appears in the bucks-ai repository.** The
customer's code exists only in the gitignored workspace and on the
customer's own remote.

### 1.3 What is NOT demonstrated

- **Unattended deploy.** `ai-infra-03` ("Deploy the scaffolded app") was
  marked `complete` with the summary `Files: created none; modified none /
  Check: unknown / SQL: unknown` — it did nothing. The founder deployed by
  hand on 2026-07-31. Prompt artifact:
  `runner/langgraph/outbox/ai-infra-03_prompt.txt`.
- **Root cause** (from the founder's notes, corroborated by the prompt
  artifact): the runner passes the task prompt as an *attached file
  reference* with cwd left in the bucks-ai tree rather than the business
  workspace. Two independent workers therefore saw "a file describing a
  deploy to someone else's Vercel project," correctly judged that
  consequential and irreversible, and **asked for clarification instead of
  acting**. The workers behaved correctly; the dispatch is broken. This is
  M4c item 12.
- **Mission-level completion.** Three business missions for this business
  (`d49b2a95`, `d6802ad8`, `8511bfc9`) are still `running` in production
  despite all 8 tasks being `complete`. Mission status never closes. A
  fourth (`ecdcfb9e`) was queued 2026-08-03.

---

## 2. Containment guarantees: status matrix

All four guarantees were exercised **live against production configuration**
this pass, not merely unit-tested. This is the substantive upgrade over the
2026-07-26 revision.

| Guarantee | Test proof | Live proof (this pass) | Status |
|---|---|---|---|
| **Wrong-repo refusal** | `tests/test_foreign_repo_workspace.py` — **32 passed** | `is_bucks_ai_repo()` correctly rejected `bucks-ai/app` (the configured repo), `bucks-ai/bucks-ai`, and resisted case (`BUCKS-AI/BUCKS-AI`) and whitespace/slash (`' bucks-ai/bucks-ai/ '`) evasion; accepted `rangasatvik/testflow-demo`. `guard_business_repo_path()` raised `ForeignRepoGuardError` on the bucks-ai repo root. | **Verified live** (see caveat 2.1) |
| **Secret-name-only storage** | `tests/test_business_sandbox.py` — **8 passed**; `src/lib/sandbox.test.ts` | The live `business_sandbox` row holds `github_token_secret_name: "TESTFLOW_GITHUB_TOKEN"` and `vercel_token_secret_name: "TESTFLOW_VERCEL_TOKEN"` — **names, no values**. Schema (`0004_business_sandbox.sql`) has *no column capable of holding a token*: only `repo_full_name`, `vercel_project_id`, and two `*_secret_name` TEXT columns. | **Verified live and structurally guaranteed** (see 4.1) |
| **Claim-gate conditions** | `tests/test_seeded_mission_queue.py` — **58 passed** | `evaluate_business_mission_claim()` run against the **real queued mission** `ecdcfb9e`: `{'allowed': True}` — proving all four conditions hold on real data. Negative paths confirmed live: `missing_business_id`, `business_not_found`. | **Verified live** |
| **Deploy targeting** | `tests/test_business_vercel_target.py` — **21 passed** | `resolve_business_vercel_target()` on the live config resolved to the **business's own** project `prj_u463pZOf1N5oDh7Le6KOfR0ToE22` via its own `TESTFLOW_VERCEL_TOKEN`. Partial and empty configs both returned `partial_sandbox_config` — **no bucks-ai fallback**. | **Verified live** |

### 2.1 Caveat: the path guard is an equality check, not a containment check

`guard_business_repo_path` (`tools/foreign_repo_workspace.py:166-180`)
compares `os.path.realpath(repo_path) == os.path.realpath(cfg.repo_path)`.
Verified live: it refuses `/home/arnav/bucks-ai`, but **allows**
`/home/arnav/bucks-ai/runner/langgraph` — a path inside the bucks-ai tree.

This is **not currently exploitable**: `repo_path` is always constructed by
`ensure_workspace` as `.workspaces/<business_id>`, and workspaces live under
the bucks-ai tree by design (so the guard *cannot* simply reject subpaths
without rejecting every legitimate workspace). The code's own docstring is
honest about this, calling itself defense-in-depth. Recorded here because an
auditor will ask, and because it becomes a real gap the moment `repo_path`
is settable from anywhere but `ensure_workspace`.

---

## 3. The 2026-07-26 blockers: both closed

### 3.1 Sandbox-config storage split — FIXED

The prior report's Critical Finding was that the founder-facing Settings tab
wrote to `public.business_sandbox` while every runner path read
`public.businesses.sandbox_config`, with nothing syncing them — so
configuring the UI had no effect on execution.

Closed by **PR #91** (`f0fb877`, 2026-07-27), which added
`tools/business_sandbox.py::fetch_business_sandbox` as the single runner-side
read path and switched all consumers (`prepare_business_repo`,
`evaluate_business_mission_claim`, `resolve_business_vercel_target`,
`graph.py::_resolve_business_deploy_target`) onto it. `businesses.sandbox_config`
is left in place but dead — a business with data only on the legacy column
is treated as **unconfigured, with no silent stale-data fallback**. That
design choice is correct and worth noting: it fails closed, not open.

Verified this pass: `fetch_business_sandbox('931f4a57-…')` returns the live
row, and the claim gate built on it returns `allowed: True`. The fix is real
and is what made `m4b-08` possible.

### 3.2 Claim-gate lift — MERGED

`feature/m4b/claim-gate-lift` merged as PR #89 (`0fe44de`).
`BUSINESS_EXECUTION_ENABLED` is now **`true`** in the live runner `.env`
(previously unset/false). The gate is live and permitting real missions.

---

## 4. Migrations wiring (m4b-01): founder-applied, not auto-applied

**Direct answer to the audit question: `0004` was founder-applied, not
auto-applied. The runner's automated path has never fired in production.**

Live `_runner_migrations` ledger, read this pass:

```
0001_runner_migrations.sql                      2026-07-22T19:51:44Z  manual-apply-2026-07-22
0002_agent_runs_cost_duration.sql               2026-07-22T19:51:44Z  manual-apply-2026-07-22
0003_missions_runner_target.sql                 2026-07-22T19:51:44Z  manual-apply-2026-07-22
0004_business_sandbox.sql                       2026-07-22T19:51:44Z  manual-apply-2026-07-22
0004_businesses_sandbox_config.sql              2026-07-22T19:51:44Z  manual-apply-2026-07-22
0005_business_sandbox_config_vercel_target.sql  2026-07-22T19:51:44Z  manual-apply-2026-07-22
```

All six share an identical `applied_at` and a **sentinel `sha256` of
`manual-apply-2026-07-22`** — a literal string, not a computed hash. This is
the signature of founder application via the Supabase SQL Editor.
`AUTO_APPLY_MIGRATIONS` remains **unset** (defaults false, `config.py:178-180`).

The automated path itself is built and tested — `check_pending_migrations_if_needed`
(`graph.py:350-423`), wired into the loop, with `tests/test_migrations_wiring_node.py`
(**11 passed**). It always logs a loud `migrations_pending` event regardless
of the auto-apply flag. It is correctly gated off by default; it has simply
never run for real. m4b-01 is therefore **code-complete and unproven in
production**.

### 4.1 Two live findings on migrations

1. **`0006` is un-applied in production.** `0006_deprecate_businesses_sandbox_config.sql`
   does not appear in the ledger. Impact is **nil** — its only executable
   statement is a `COMMENT ON COLUMN` marking `businesses.sandbox_config`
   deprecated. No schema or behavior depends on it. But it means the ledger
   and the migrations directory are out of sync, and the un-applied state
   is invisible unless the loop runs and logs `migrations_pending`.
2. **Two migrations share the `0004` prefix** — `0004_business_sandbox.sql`
   and `0004_businesses_sandbox_config.sql`. Both applied, so no live
   breakage, but the numbering scheme no longer guarantees a total order.
   Any future tooling that sorts by prefix will have ambiguous ordering.

---

## 5. Execute CTA and approvals UX (m4b-02)

Both shipped and merged (PR #85), verified present this pass:

- **Execute CTA**: `ExecutePanel` is imported and rendered as the primary
  action in `src/components/workspace/tabs/OverviewTab.tsx:12,173`.
- **Approvals empty-state disambiguation**: `approvals_schema_missing` is a
  distinct typed state (`src/types/approval-ui.ts:4`) threaded through
  `src/lib/approvals.ts:76,95` and `src/app/api/approvals/route.ts:24-29`,
  rendered separately from a genuine "no approvals pending" by
  `ApprovalsPanel.tsx`. Covered by `ApprovalsPanel.test.ts` and
  `route.test.ts`.
- **Sandbox config editing** was added subsequently (PRs #92, #93,
  `38f6b43`/`544a9a6`) after the original UI shipped with no edit affordance
  for already-configured fields — one of the six hours of founder debugging.
  `SandboxStatusPanel.tsx` is the Settings-tab surface.

---

## 6. Test suite status

| Suite | Result |
|---|---|
| Runner — `python -m pytest tests/ -q` | **2282 passed**, 0 failed |
| App — `npx vitest run` | **367 passed, 8 skipped**, 1 file failed (flaky, see below) |

**One flaky test, characterized not dismissed.**
`src/lib/supabase/rls.integration.test.ts` failed in the full run with
`Hook timed out in 10000ms` (suite duration 26.7s), then **passed in
isolation: 6 passed, 1 skipped, 5.5s**. It is a live-network test against
real Supabase with a 10s hook timeout that is insufficient under full-suite
load. This is a genuine flake, not a logic failure — but it means
`npx vitest run` is not reliably green, and the guarantee it covers
(cross-tenant RLS denial on `business_sandbox`) is therefore not
continuously enforced. **Recommended fix:** raise the hook timeout for this
file, or gate it behind an explicit integration-test flag so the default
suite is deterministic. Not changed in this pass — a verification pass
should not alter what it measures.

---

## 7. Security finding: token materialized in plaintext on disk

**Severity: low blast radius, must still be rotated.**

The business workspace's git remote embeds a live GitHub token in cleartext:

```
runner/langgraph/.workspaces/931f4a57-…/.git/config
  → https://x-access-token:ghp_<REDACTED>@github.com/rangasatvik/testflow-demo.git
```

**Blast radius, verified this pass:**
- `.workspaces/` is gitignored (`.gitignore:72`) and **untracked** —
  `git ls-files` returns nothing. The token **never entered git history**.
- No hardcoded `ghp_` values exist in tracked source. The only matches are a
  documentation placeholder, test fakes, and the redaction regex in
  `tools/slack_approvals.py:58`.

**This does not contradict the secret-name-only guarantee**, which is about
the *database* — and there it holds structurally (§2). But an auditor should
understand the distinction precisely: **names-only in Supabase, plaintext on
disk.** The token must materialize somewhere to clone; embedding it in the
remote URL persists it in `.git/config` for the workspace's lifetime, which
is broader than necessary.

The code shows real awareness here — `_run_git` deliberately avoids
`tools.shell_tools.run_command` and redacts the token from all logged output,
precisely because git echoes credentialed URLs on failure
(`tools/foreign_repo_workspace.py:94-104`). The remaining gap is persistence
at rest, not logging.

**Recommended:** rotate the token in `TESTFLOW_GITHUB_TOKEN`; prefer a
credential helper or per-invocation `-c http.extraheader` over an embedded
remote URL.

---

## 8. The false-completion problem

The most audit-relevant defect found. Task states in
`runner/langgraph/.runtime/tasks.local.json`:

| Task | Status | Summary |
|---|---|---|
| ai-infra-01 | complete | *(empty)* |
| ai-infra-02 | complete | `created none; modified none` |
| **ai-infra-03** (deploy) | **complete** | `created none; modified none; Check: unknown` |
| ai-infra-04 | complete | *(GTM summary)* |
| ai-infra-05 | complete | **copy of ai-infra-04's summary — wrong title** |
| ai-infra-06 | complete | `created docs/competitive-risk-mitigation…` |
| ai-infra-07 | complete | *(empty)* |
| ai-infra-08 | complete | `created none; modified none; Check: pass` |

All 8 marked `complete`; only 2 carry any evidence of work; one (`ai-infra-05`)
carries *another task's* summary. Meanwhile the repo holds 5 real commits.

**Both facts are true simultaneously**: real autonomous work happened, *and*
the ledger cannot tell you which task did it or whether a task did anything.
The runner marks `complete` on worker exit-success, not on evidence of work.

**For the proof corpus this means: cite the customer repo's git history,
never the task ledger.** This is M4c item 10(b), and the founder's own note
is the right framing — *"silent false success is worse than a crash; every
other failure was loud, this one looked like a win."*

`ai-infra-03` additionally carries a `dedupe_note` recording that a prior
`failed` state was a transient Supabase lookup failure during degraded
network, requiring hand-editing of runtime JSON to recover (M4c item 11;
partially mitigated by the `fetch_business_by_id` retry, which this pass
confirms is present at `tools/foreign_repo_workspace.py:183`).

---

## 9. Recommended M5 business selection criteria

`STRATEGY.md` §6.2 records the founder decision (2026-07-21) that the first
M5 wedge is the **security-hardening sprint service**, scored clean on all
seven §6.1 criteria — including criterion 4, *"buildable by the engine today."*

**Criterion 4 is still not satisfied, and `m4b-08` did not change this.**

Reading `src/lib/mission-compiler.ts` as it stands, every business mission
compiles to the same fixed generic starter set: `Build landing page section`
(:90), `Wire analytics stub` (:103), `Deploy the scaffolded app` (:119),
`Execute go-to-market` (:135), `Mitigate top risk` (:147). The file's own
header comment (:15-16) states the intent plainly — *"concrete, self-contained
starter work… rather than bucks-ai-specific tasks."*

**A trap for the reader, worth stating explicitly:** the AI Infra demo built
a *security assessment tool* and produced `docs/security-best-practices.md`.
That is the **business idea** being security-themed. It is **not** the engine
applying its own hardening playbook to a customer's repo. Those are different
capabilities, and only the first exists today.

The asset that would make the hardening wedge buildable — M1's
auth/zod/rate-limit/RLS/security-headers/route-inventory playbook — exists
and is battle-tested against bucks-ai itself, but **nothing wires it into
`mission-compiler.ts` for foreign repos**. That wiring is M4d scope.

### Recommendations

1. **Do not launch an M5 business until M4c item 12 (worker dispatch) lands.**
   This is the binding constraint, not business selection. Until a business
   task can execute unattended with cwd in the right workspace, every M5
   engagement requires a founder babysitting session — which does not scale
   to a customer and cannot be sold.
2. **Add "positive completion evidence" (M4c item 10b) as a hard gate.**
   Selling execution against a customer repo while the system can report
   success for work it did not do is the single largest reputational risk in
   the current design.
3. **Re-score criterion 4 for the hardening wedge as `fails`, not `clean`,**
   until M4d ships. This is a capability-readiness correction on the
   founder's own rubric, not a doctrine change.
4. **Revise selection criteria to match demonstrated capability.** What the
   pipeline provably builds today is a *greenfield scaffold into an empty or
   near-empty customer repo*: React frontend, Express/Postgres backend,
   Docker, deploy config, analytics stub. Therefore prefer, for M5:
   - **Greenfield over brownfield.** All five commits landed in a fresh repo.
     The engine has **never** modified a mature codebase with existing
     conventions, and nothing in this corpus supports that claim.
   - **Buyers who accept feature branches.** The engine pushed 9 branches and
     merged none; the repo's `origin/HEAD` points at a feature branch, not
     `main`. There is no demonstrated merge/review path.
   - **Tolerant of a manual deploy step**, until item 12 lands.
   - **Small, well-specified scope** matching the five fixed compiler tasks.
5. **Rotate `TESTFLOW_GITHUB_TOKEN`** (§7) before this repo is shown externally.
6. **Apply `0006`** and resolve the duplicate-`0004` numbering (§4.1).
7. **De-flake the RLS integration test** (§6) so cross-tenant denial is
   continuously enforced rather than intermittently skipped.

---

## 10. What could not be verified

Stated explicitly, per the audit standard for this document:

- **Unattended end-to-end execution.** Never demonstrated. The deploy was
  manual; worker dispatch for business tasks is broken.
- **Wrong-repo refusal on the DB-sourced path.** `prepare_business_repo`
  reads `repo_full_name` from `business_sandbox`, so exercising the
  `forbidden_repo` branch live would require writing a hostile value to
  production. Refused as out of scope for a read-only pass. Covered by unit
  tests and by live verification of both underlying primitives (§2).
- **The runner's auto-apply migration path.** Never fired in production;
  unit-tested only.
- **Which task produced which commit.** Unrecoverable from the ledger (§8).
- **Whether the deployed site is served from the runner's commits.** The
  HTTP 200 and matching title are strong circumstantial evidence, but the
  founder's notes record an earlier incident of a Vercel project not being
  git-connected and serving stale code. Not re-verified at the deployment-SHA
  level this pass.
- **Any claim about repeatability.** `m4b-08` is **n=1**, on one business,
  one repo, with six hours of human intervention. Nothing here supports a
  claim about the success rate of a second attempt.

---

## 11. Known limitations of this report

- Point-in-time snapshot, 2026-08-03, read-only. No production writes.
- Live probes used the service-role key and therefore bypass RLS; RLS
  enforcement itself is evidenced by the integration test (§6), not by these
  probes.
- Task-ledger data is read from local `.runtime/tasks.local.json`, which is
  gitignored, local-only, and has been hand-edited during incident recovery
  (§8) — treat it as narrative, not as an audit record.
- `CHAT_HANDOFF_2026-07-11.md` is the founder's working notes, not a
  verified artifact; where this report cites it (the six-hour debugging
  session, the manual deploy, dispatch root cause) the claims are the
  founder's own and are corroborated where possible by prompt artifacts and
  task state, but the transcripts themselves were not re-read this pass.
- The build-metric correction (§1.1) supersedes the handoff's headline
  numbers; if any external material already cites "1,819 insertions / 19
  files," it should be updated.
