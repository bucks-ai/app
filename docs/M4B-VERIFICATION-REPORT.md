# M4b Verification Report

Mission: **M4b — Sandbox-per-Business Execution (batch 2)**. This is the
done-when evidence for `m4b-09-verification-report`, the centerpiece of the
M4 pivot proof corpus: the claim under audit is *"our system executes
missions against customer repos under containment."* This pass combines
static/code verification, the full test suite, and live read-only probes
against the real production Supabase project (`SUPABASE_URL` in `.env`) on
2026-07-26. No mutating action was taken against production during this
pass; no business repo, Vercel project, or credential was created.

## Verdict

- **The M4 pivot has not been demonstrated live.** `m4b-08` — the task whose
  entire job was to click Execute and watch a real business repo get built
  and deployed — is **blocked**, not complete. It never got as far as
  creating a mission, cloning a repo, or making a commit. See "m4b-08: what
  was and wasn't demonstrated" below.
- **Headline finding: even once every blocker below is cleared, the pivot
  cannot succeed through the founder-facing UI as currently wired.** The
  per-business sandbox configuration that the founder sets via the Settings
  tab is stored in a different place than the one the runner reads from. See
  "Critical finding" — this is a cross-stack integration gap, not a missing
  credential, and it was not caught by any test because each side's tests
  mock the other side away.
- **m4b-01 (migrations wiring), m4b-02 (Execute CTA/approvals UX), m4b-04
  (sandbox config model), m4b-05 (foreign-repo execution), m4b-06 (business
  Vercel deploy): correctly built, unit-tested, and merged to `main`.** All
  their guarantees are real at the unit-test level; none has been exercised
  against a live business repo or live Vercel project, because no business
  has ever had a sandbox configured (confirmed live, see below).
- **m4b-07 (claim-gate lift): code-complete on its own branch
  (`feature/m4b/claim-gate-lift`, 2 commits) but NOT merged to `main`, and
  its own task status is still `running`, not `complete`.** This alone is a
  hard blocker for `m4b-08` (it's the first item on `m4b-08`'s own resource
  list). All 10 new/changed tests for it pass, and the full suite passes on
  that branch (**1790 passed**).
- **Found and fixed during this pass:** a same-day, already-on-`main` hotfix
  (`0003ad4`, 2026-07-22, unrelated to this task) silently broke 6 of the 31
  tests in `tests/test_foreign_repo_workspace.py` — the node-level tests for
  the wrong-repo-refusal / business-not-found / missing-secret containment
  paths. They were failing for the right reason (a fixture gap, not a logic
  bug) but had apparently not been run to completion since: `python -m
  pytest tests/ -x -q` was silently non-green on `main`. Fixed as part of
  this pass (see "Test regression" below); full suite is now **1780 passed**
  on this branch.

## Critical finding: sandbox config is stored in two places that never sync

Two separate, independently-built storage locations exist for "this
business's sandbox config," and nothing in the codebase copies data between
them:

| Side | Storage | Built by | Reads/writes |
|---|---|---|---|
| **App** (founder Settings tab, API) | `public.business_sandbox` table (`supabase/migrations/0004_business_sandbox.sql`) | m4b-04 | `src/lib/sandbox.ts` (`.from("business_sandbox")`, confirmed at lines 168, 346, 353, 360, 367), `src/app/api/businesses/[id]/sandbox/route.ts` (GET/PATCH), rendered by `src/components/workspace/SandboxStatusPanel.tsx` on the Settings tab |
| **Runner** (execution: foreign-repo clone, Vercel deploy target, claim gate) | `public.businesses.sandbox_config` JSONB column (`supabase/migrations/0004_businesses_sandbox_config.sql` + `0005_business_sandbox_config_vercel_target.sql`) | m4b-05, m4b-06, and the unmerged m4b-07 | `tools/foreign_repo_workspace.py:213` (`sandbox_config = business.get("sandbox_config")`), `tools/vercel_tools.py:311-330` (`resolve_business_vercel_target(sandbox_config)`), `graph.py:250` (`sandbox_config = (business or {}).get("sandbox_config")`), and on the unmerged branch `tools/seeded_mission_queue.py:101` (claim-gate resolver) |

Confirmed by exhaustive grep: **zero** files under `src/app/` or `src/lib/`
ever write to `businesses.sandbox_config` (only a type declaration exists,
`src/types/database.ts:35,224`); **zero** files under `runner/langgraph/`
ever read from or write to the `business_sandbox` table. No SQL trigger,
view, or sync job bridges them (`grep sandbox_config
supabase/migrations/*.sql` shows only the two independent column/table
definitions, no bridging logic).

**Live confirmation, read-only, against production:**
```
GET business_sandbox?select=*                                  -> 200 []   (zero rows, ever)
GET businesses?select=id,idea_name,sandbox_config&id=eq.ebad9506-...
    -> {"id":"ebad9506-...","idea_name":"TestFlow AI","sandbox_config":null}
```
So concretely: **a founder who fully fills in the Settings tab for a
business today would see "configured" in the UI, and the runner would still
never see it** — `prepare_business_repo`, `resolve_business_vercel_target`,
and the (unmerged) claim gate all resolve `sandbox_config` from `businesses`
directly, not from the table the UI writes to. This was not caught by any
existing test because `tests/test_foreign_repo_workspace.py` and
`tests/test_business_vercel_target.py` construct their `business` fixture
dicts with a literal `sandbox_config` key by hand (mocking the runner's own
assumption), and `src/lib/sandbox.test.ts` / the RLS integration test mock
or hit only the `business_sandbox` table — neither suite's mocks match the
other side's actual behavior, so the gap between them is invisible to CI.

This is the actual root blocker of the M4 done-when claim, more fundamental
than any single missing credential: it must be fixed (pick one storage
location — recommend the `business_sandbox` table, since it's RLS-scoped
to the owning user and already has the founder-facing UI built on top of it;
have the runner read from it instead of `businesses.sandbox_config`, or add
an explicit sync step) before any live end-to-end demo, including a re-run
of `m4b-08`, can succeed even with every credential in hand.

## m4b-08: what was and wasn't demonstrated

`m4b-08`'s own resource request (`outbox/m4b-08-execute-end-to-end-demo_resource_request.txt`)
lists, unresolved:
- A merged PR for `feature/m4b/claim-gate-lift` (still open, per above)
- A scoped GitHub token for TestFlow AI's own repo (not in `.env`)
- A scoped Vercel token for TestFlow AI's own Vercel project (not in `.env`)
- A real GitHub repo and Vercel project for TestFlow AI (business_id
  `ebad9506-aaa5-4235-88ab-0ed526e036a2`)
- A populated `business_sandbox` row for it
- `BUSINESS_EXECUTION_ENABLED=true` (blocked on the merge above)
- A human click on Execute in the live UI

**Live confirmation that none of this has happened:** production
`business_sandbox` has zero rows; `businesses.sandbox_config` is `null` for
TestFlow AI; the production `missions` table has **no `runner_target =
"business"` mission ever created for TestFlow AI** — the only
`business`-targeted mission in the entire table (`d49b2a95-...`, created
2026-07-15, `status: queued`) belongs to a different business
(`931f4a57-...`, the M4a-era Execute demo) and has sat queued and unclaimed
for 11 days, which is itself live proof that the claim gate holds closed
correctly under real conditions — exactly the "queued forever" behavior
M4a's report flagged as a pending product decision, still true today.
`AUTO_APPLY_MIGRATIONS`, `BUSINESS_EXECUTION_ENABLED` are both **unset**
(default false) in the live runner `.env`. No screenshots or artifacts exist
under `outbox/` for `m4b-08` beyond its prompt and resource-request files —
it never progressed far enough to produce any.

**Net: the M4 pivot's live done-when has zero real-world executions to
point to.** Everything below this point is unit-test or static-code
verification, not a live demonstration.

## Test regression found and fixed this pass

`tests/test_foreign_repo_workspace.py`'s node-level tests
(`test_node_business_not_found_hard_fails`,
`test_node_success_overrides_repo_path`,
`test_node_forbidden_repo_hard_fails`,
`test_node_missing_secret_blocks_and_writes_resource_request`,
`test_node_missing_secret_fulfilled_retries_successfully`,
`test_node_no_sandbox_config_blocks_as_resource_request`) call
`graph.resolve_business_repo_if_needed` with a hand-built task dict that
never set `runner_target`. `0003ad4` (2026-07-22, already merged to `main`,
unrelated to this task) added an early `if task.get("runner_target", "self")
!= "business": return state` guard to that function — correct behavior for
the real code path (self-targeted dev tasks were being wrongly routed
through business-repo resolution), but it made all 6 tests short-circuit
before ever reaching the logic they claim to test, so they failed once
actually run. Fixed by adding `"runner_target": "business"` to each test's
task dict (`tests/test_foreign_repo_workspace.py`); no production code
changed. Verified: `python -m pytest tests/test_foreign_repo_workspace.py
-q` → 31 passed; full suite `python -m pytest tests/ -x -q` → **1780
passed**.

## Containment guarantees: status matrix

| Guarantee | Task | Test coverage | Live proof | Status |
|---|---|---|---|---|
| **Wrong-repo refusal** (a business mission must never run with `repo_path` == the bucks-ai repo) | m4b-05 | `tests/test_foreign_repo_workspace.py` — 31 tests incl. `test_guard_raises_when_repo_path_equals_bucks_ai_repo`, `test_is_bucks_ai_repo_*`, `test_prepare_business_repo_forbidden_repo`, `test_node_forbidden_repo_hard_fails` | None — no business repo has ever been cloned | **Tested only** |
| **Secret-name-only storage** (business_sandbox / sandbox_config store names, never token values) | m4b-04 | `src/lib/sandbox.test.ts`, `src/lib/supabase/rls.integration.test.ts` (live, 6 passed against real Supabase) | Live schema probe: `business_sandbox` and `businesses.sandbox_config` columns are all TEXT/JSONB name fields; zero rows contain anything resembling a token (table is empty; column is null) | **Verified at the schema level** — but see Critical Finding: this data never reaches the runner regardless |
| **Claim-gate conditions** (`BUSINESS_EXECUTION_ENABLED` + full sandbox + resolvable secrets, all four, before a business mission is claimed) | m4b-07 | `tests/test_seeded_mission_queue.py` on `feature/m4b/claim-gate-lift` — 10 net new tests (57 vs 47 on `main`), incl. every refusal path (`test_claim_refused_when_*` ×6) and the full-config claim path (`test_claim_allowed_when_fully_configured`); full suite 1790 passed on that branch | None — branch not merged, `BUSINESS_EXECUTION_ENABLED` unset in prod, so this code has never run against real data | **Tested only, not merged, not live** |
| **Deploy targeting** (deploys/polling must target the business's own Vercel project+token, never bucks-ai's, and never silently fall back) | m4b-06 | `tests/test_business_vercel_target.py` — 20 tests incl. `test_deploy_if_needed_refuses_fallback_on_partial_sandbox_config`, `test_resolve_business_target_never_returns_bucks_ai_fallback` | None — no business has ever had a `vercel_project_id` configured | **Tested only** |

All four guarantees are real at the unit-test level (mocked git/HTTP/Vercel
API, deterministic). None has fired against a live repo, live deploy, or
live claim, because the Critical Finding above means no business's sandbox
config has ever actually reached the runner's read path, and (independently)
`BUSINESS_EXECUTION_ENABLED` has never been on in production.

## Migrations wiring (m4b-01): founder-applied, not auto-applied

Code (merged, PR #84): `graph.py:350-423`
(`check_pending_migrations_if_needed`), wired between
`check_launch_readiness_if_needed` and `load_next_task`
(`graph.py:2876,2920`). Runs every loop start when `DATABASE_URL` or
`DIRECT_DATABASE_URL` is configured (confirmed set in prod `.env`). Always
logs a loud `migrations_pending` event listing un-applied files, regardless
of the auto-apply flag. Tests: `tests/test_migrations_wiring_node.py` (11
tests) + the migration-specific subset of `tests/test_db_tools.py` (42
tests) — pending-detection, auto-apply happy path, guard-blocked refusal,
non-additive refusal, no-database no-op. All pass.

`AUTO_APPLY_MIGRATIONS` defaults `false` (`config.py:178-180`) and is
**unset in the live `.env`**, so this environment has never taken the
auto-apply branch for real. (Do not confuse with `AUTO_APPLY_SQL`,
`config.py:166-167` — a separate, pre-existing flag for worker-issued ad hoc
SQL, defaulting `true`; unrelated to migration files.)

**Live confirmation of what actually happened:** all 6 migrations
(`0001_runner_migrations` through `0005_business_sandbox_config_vercel_target`)
are present in the production `_runner_migrations` ledger, every row with
identical `applied_at` (`2026-07-22T19:51:44Z`) and `sha256:
"manual-apply-2026-07-22"` — a sentinel value, not a computed hash, matching
the header comment in the (untracked, local-only)
`supabase/APPLY_ALL_PENDING_2026-07-22.sql` combined script found in the
working tree. **This is founder-manual application via the SQL Editor, not
the runner's automated path** — the automated path exists, is unit-tested,
and is correctly gated off by default, but has never fired in production.
Live schema now confirms: `missions.runner_target` exists,
`agent_runs.cost_usd`/`duration_seconds` exist, `business_sandbox` exists
(RLS enabled, 0 rows), `businesses.sandbox_config` exists (JSONB, null for
TestFlow AI) — all of M4a's and M4b's schema gaps are closed at the schema
level.

Also checked, since the local `CHAT_HANDOFF_2026-07-11.md` (uncommitted,
founder's own working notes, not part of this task's scope) records a
2026-07-22 incident requiring transient DB errors to fail open rather than
halt the loop: `check_pending_migrations_if_needed`'s error path
(`graph.py:373-383`) only logs an `"error"` event and returns state without
ever setting `stop_reason` — already matches that doctrine. No gap found
here; noted for completeness, not fixed (nothing needed fixing).

## Execute CTA and approvals UX (m4b-02)

Merged (PR #85, `978102e`). `ExecutePanel` promoted to the primary CTA in
`OverviewTab.tsx`; approvals empty-state disambiguation shipped in
`src/lib/approvals.ts` / `src/app/api/approvals/route.ts` /
`src/components/workspace/tabs/ApprovalsPanel.tsx` — `approvals_schema_missing`
is a distinct, typed state (`src/types/approval-ui.ts`) rendered as an amber
human-required notice, separate from genuine "No approvals pending." Given
this pass's live probe confirms the `approvals` table now exists in
production (`GET approvals?select=id&limit=1` → `200`, one real row) — the
schema-missing branch is currently dormant in prod (a good sign, not a
gap), and the "genuinely empty" / real-approvals-present branches are the
ones live traffic will hit. Unit tests (`ApprovalsPanel.test.ts`,
`route.test.ts`) and the e2e extension in `e2e/business-tabs.spec.ts` all
pass as part of the 370-passed app suite (see below).

## What was verified live in this pass

1. **Full runner suite**, after the fix above: `python -m pytest tests/ -x
   -q` → **1780 passed**, 0 failed.
2. **Full app suite**: `npx vitest run` → **370 passed, 2 skipped**, 0
   failed, including the live RLS integration test for `business_sandbox`
   (`src/lib/supabase/rls.integration.test.ts` → 6 passed, 1 skipped,
   against real Supabase).
3. **`feature/m4b/claim-gate-lift` branch, standalone**: `python -m pytest
   tests/ -x -q` → **1790 passed**, confirming m4b-07's own code is correct
   and ready to merge independent of the sandbox-config-split finding above.
4. **Read-only live probes against production Supabase**
   (`SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` from `.env`, no writes):
   `_runner_migrations` ledger contents, `missions.runner_target` column
   existence and values, `agent_runs.cost_usd`/`duration_seconds` existence,
   `business_sandbox` row count, `businesses.sandbox_config` value for
   TestFlow AI, `approvals` table existence, full `missions` table contents
   (7 rows) cross-referenced by `business_id`/`runner_target`/`status`.
5. **Static verification of every containment guarantee's actual code path**
   (not just its tests): read `tools/foreign_repo_workspace.py`,
   `tools/vercel_tools.py`, `graph.py` (`resolve_business_repo_if_needed`,
   `check_pending_migrations_if_needed`), `src/lib/sandbox.ts`,
   `src/app/api/businesses/[id]/sandbox/route.ts`, and the unmerged
   `tools/seeded_mission_queue.py` claim-gate resolver, line-by-line against
   their own tests to confirm the tests exercise the real logic (this is how
   the Critical Finding and the test regression were both found — neither
   was visible from a green test run alone).
6. **`src/lib/mission-compiler.ts` diff on the unmerged branch**
   (`main...feature/m4b/claim-gate-lift`) read in full: confirms the
   fresh-repo starter-task rewrite (landing page section, analytics stub,
   deploy) matches m4b-07's spec exactly.

## What could not be verified

- **The M4 pivot itself, live**: a business mission created via Execute,
  claimed by the runner, executed against a real foreign repo, deployed to
  a real business Vercel project, smoke-checked, and reflected in the
  Operating Team UI. Not possible in this pass: `m4b-07` isn't merged,
  `BUSINESS_EXECUTION_ENABLED` is off, no business has ever had sandbox
  config populated on the runner's read path, and no credentials for
  TestFlow AI's repo/Vercel project exist in `.env`. Per this task's own
  scope (verification/reporting, not resource provisioning or infra setup),
  none of these were provisioned as part of this pass.
- **Wrong-repo refusal, secret resolution, deploy targeting, and the claim
  gate, live.** All four are unit-tested only, as detailed in the matrix
  above; none has run against a real repo, real Vercel project, or real
  claim attempt.
- **Whether fixing the sandbox-config storage split alone is sufficient**
  for `m4b-08` to succeed once merged/credentialed — this pass did not
  attempt the fix (a cross-stack schema/code decision, not a small patch,
  and outside a verification task's scope), only diagnosed and documented
  it precisely enough to be actionable.

## Recommended M5 business selection criteria, grounded in what the pipeline can build today

`STRATEGY.md` §6.2 already records a founder decision (2026-07-21): the
confirmed first M5 wedge is **the security-hardening sprint service**,
scored clean against all seven §6.1 criteria — including criterion 4,
"buildable by the engine today (fits the M4b pipeline)."

This pass's finding: **criterion 4 is not actually true yet for that
specific product**, independent of the credential/merge blockers above.
Reading the mission-compiler output that will actually run once the pipeline
unblocks (`src/lib/mission-compiler.ts` on `feature/m4b/claim-gate-lift`):
every business mission compiles to exactly three fixed starter tasks — a
landing-page section, an analytics stub, and a deploy — generic Next.js
scaffold work, not a security-hardening deliverable. The real asset that
would make the hardening-sprint wedge buildable (M1's auth/zod/rate-limit/
RLS/security-headers/route-inventory-test playbook) exists and is
battle-tested against the bucks-ai repo itself, but nothing wires it into
`mission-compiler.ts` for foreign business repos — that wiring is
explicitly M4d's scope (per `STRATEGY.md` §8 and the M4c/M4d plan recorded
in `CHAT_HANDOFF_2026-07-11.md`), not yet built.

Recommendation:
1. **Do not select or launch an M5 business against the current pipeline.**
   Treat this report's Critical Finding as a P0 blocker ahead of any M5
   work: fix the sandbox-config storage split (pick one location — recommend
   keeping `business_sandbox`, since RLS and the founder UI are already
   built on it, and pointing the runner's reads there instead).
2. **Merge `feature/m4b/claim-gate-lift`** (m4b-07) — it is complete,
   tested, and blocking `m4b-08` for no remaining code reason.
3. **Re-run `m4b-08` end-to-end** against a real, disposable test repo
   (TestFlow AI or a fresh throwaway) once (1) and (2) land, before
   `BUSINESS_EXECUTION_ENABLED` is ever set `true` against a real customer's
   repo. This is the one thing that would let this report's "what could not
   be verified" section collapse to nothing.
4. **Re-score the security-hardening wedge's criterion 4 specifically**
   once M4d (hardening-by-default in the mission compiler) lands — today
   the pipeline can build a generic SaaS landing page for any business, not
   a hardening sprint for this one. Until then, criterion 4 should read
   "fails" for this wedge, not "clean," on the founder's own rubric.
5. Everything else in `STRATEGY.md` §6.1's scoring algorithm remains sound
   and unaffected by this pass's findings — this is a capability-readiness
   correction, not a doctrine change.

## Known limitations

- This report reflects a single point-in-time, read-only snapshot
  (2026-07-26). No production data was written; the one code change made
  during this pass (the 6-test fixture fix) touches only
  `tests/test_foreign_repo_workspace.py`.
- The Critical Finding's fix is deliberately not attempted here — it's a
  cross-stack schema/code decision (which storage wins, and how existing
  code that reads the other one gets updated) that belongs to its own task,
  not a verification pass.
- `CHAT_HANDOFF_2026-07-11.md` and
  `supabase/APPLY_ALL_PENDING_2026-07-22.sql` are pre-existing, uncommitted
  local files (founder's own working notes and the manual-apply script
  referenced above) — read for context in this pass, left untouched, not
  part of this task's file changes.
- The M4a report's still-open item ("a business mission sits queued forever
  with no UI path out") remains true and is now corroborated by a second,
  independent live example (`d49b2a95-...`, 11 days queued as of this pass)
  — still an open product decision, not addressed by M4b.
- `launch_readiness_scorecard.txt` in `outbox/` (dated 2026-07-26, same
  session) separately reports `credentials_available: 0.80` — "missing:
  Anthropic / Claude" — unrelated to this task's findings, not investigated
  further as out of scope.
