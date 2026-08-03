# M2 Verification Report

Full E2E verification pass performed 2026-07-08 against a dedicated E2E Supabase
project (real credentials, not mocked), plus a review of the current state of
CI on `main`. This is the done-when evidence for M2. Supersedes the
2026-07-07 pass (`8c5eb79`, PR #51) — most findings from that pass are now
resolved; see §2 and §5 for what changed.

## 1. Spec inventory

`e2e/*.spec.ts`, run with Playwright against a production build (`next build`
+ `next start`), `E2E_FAKE_AI=true`:

| Spec | Covers | Needs seeded user? |
| --- | --- | --- |
| `home.spec.ts` | Landing page renders the hero heading and primary CTA. | No |
| `auth.spec.ts` | Signup (real form → email-confirm via admin API → login), login with the seeded user, wrong-password error path, logout clears the session. | Yes (signup additionally needs `SUPABASE_SERVICE_ROLE_KEY` to confirm the throwaway account) |
| `dashboard.spec.ts` | Seeded demo business renders as a card and opens its detail page; a brand-new user (created/cleaned up via admin API) sees the empty state. | Yes, plus service-role key |
| `business-tabs.spec.ts` | Research / validation / execution / operating-team tabs on the business detail page each render seeded data or their designed empty state, never an error boundary. Addresses tabs via `?tab=` query param to avoid sidebar/mobile-nav ambiguity. | Yes |
| `intake.spec.ts` | Founder intake wizard → `E2E_FAKE_AI` blueprint generation → save → shows up on the dashboard. The one spec gated on `E2E_FAKE_AI=true` in addition to the seeded user. | Yes |
| `tools.spec.ts` | Tools page permission queue renders the two seeded pending (`approval_requested`) rows, approve/reject both work against the real `/api/tool-permissions` backend, and persist across reload. | Yes |

All specs that need the seeded user/business `test.skip()` themselves cleanly
with an explanatory message when `TEST_USER_EMAIL`/`TEST_USER_PASSWORD` are
unset. `intake.spec.ts` additionally `test.skip()`s if `E2E_FAKE_AI` is not
`"true"` **in the process running `playwright test` itself** — exporting it
only for the app server (as CI's `env:` block does at the job level, but an
ad hoc local run easily misses) silently skips this spec instead of failing.
Flagging because this pass initially hit exactly that: the first two local
runs below reported "1 skipped" with `intake.spec.ts` never actually
executing until `E2E_FAKE_AI=true` was exported to the test runner too.

## 2. Local run results (this pass)

Environment: real dedicated E2E Supabase project (credentials already present
in the shell environment — no `.env.local` needed), `npm run seed:e2e`
succeeded, `next build` + `next start`, `E2E_FAKE_AI=true` exported to both
the server and the `playwright test` process.

- **`npm test`** (Vitest): 241/241 passed, 32 files.
- **`npm run build`**: clean, no type errors.
- **`python -m pytest tests/ -x -q`** (runner, `runner/langgraph/`): 1578
  passed.
- **Environment gotcha found and worked around**: this sandbox's shell had a
  stray `PLAYWRIGHT_BASE_URL` pointed at an old, unrelated Vercel deployment
  (`bucks-ai-app-archive.vercel.app`), left over from earlier session state.
  `playwright.config.ts` honors that override before falling back to
  `localhost:3000`, so the first attempt at this pass silently ran the entire
  suite against a stale external site instead of the local build — producing
  confusing failures (page content that didn't match any commit in this
  repo's history). Unsetting it in the same shell invocation as each
  `playwright test` call fixed it. Not a code bug, but worth calling out:
  anyone re-running this suite locally should `echo $PLAYWRIGHT_BASE_URL`
  first and unset it unless deliberately targeting a preview.
- **`npx playwright test --grep-invert "@flaky"` at `--workers=1` (clean
  reseed beforehand): 10/10 passed**, 0 skipped. This is a full green run of
  every spec, including `intake.spec.ts` and `tools.spec.ts`, both of which
  had genuine, reproducible failures in the 2026-07-07 pass (see §5 — both
  now fixed on `main`).
- **Re-run at this host's default parallelism (6 workers), fresh reseed**:
  3 of 10 failed — `business-tabs.spec.ts`, `dashboard.spec.ts` (`lists the
  seeded demo business...`), and `tools.spec.ts`. All three read/mutate the
  single shared seeded demo business/tool-permission rows; at high local
  parallelism they intermittently collide. This is the same root cause
  documented in the 2026-07-07 pass (then only 2 of the 3 specs were
  observed racing — `tools.spec.ts` now joins them, plausibly because it
  didn't reliably execute in that pass at all, see §1). CI's `ubuntu-latest`
  runners default to fewer parallel workers, which reduces but does not
  eliminate this exposure — see §3 for what CI itself has now shown.
- Re-running any of the three failing specs alone after a fresh
  `npm run seed:e2e` passes reliably — this confirms the failures are a
  shared-fixture race under parallelism, not a product bug.

## 3. CI status (`.github/workflows/app.yml`)

Unlike the 2026-07-07 pass, the `e2e` and `e2e-preview` jobs are **now on
`main`** (merged via PR #48 and #53) and have completed real runs:

- **Latest push to `main`** (PR #56 merge, run `28976755090`,
  2026-07-08T21:24Z): `E2E (Playwright)` — **pass** (1m45s). Its own log shows
  a `business-tabs.spec.ts` failure on the first attempt that succeeded on
  CI's built-in retry (`retries: 2` when `CI` is set) — the exact
  parallelism-dependent race from §2, now directly observed inside GitHub
  Actions, not just locally. `Lint, typecheck, build` — pass (1m12s).
  `E2E (Playwright, Vercel preview) [informational]` — skipped (0s): its
  `if: github.event_name == 'pull_request'` guard correctly no-ops on a
  direct push to `main`.
- **PR #56 itself** (`gh pr checks 56`): `E2E (Playwright)` pass (1m49s),
  `E2E (Playwright, Vercel preview) [informational]` **pass (10m59s)** — this
  is a real change from the 2026-07-07 pass, which found `e2e-preview`
  always reporting "no preview found" despite the Vercel secrets being set.
  It's now successfully resolving the PR's Vercel preview deployment and
  running the full suite against it. `Lint, typecheck, build` pass,
  `Runner tests` pass.
- Checked the four most recent `E2E (Playwright)` job logs on `main`/PRs for
  the Supabase mailer rate-limit failure documented in the 2026-07-07 pass
  (`docs/M2-E2E-RUNBOOK.md` §8) — **none hit it**. This isn't proof the
  underlying ~2-emails/hour cap was lifted (no direct access to the Supabase
  dashboard to confirm custom SMTP was configured), only that recent CI
  traffic hasn't been dense enough to exhaust it. Still worth confirming
  directly (§5).

**Trigger conditions** (unchanged from the runbook):
- `check` (App CI): every PR into `main` and every push to `main` touching
  `src/**`, `public/**`, or app config files.
- `pytest` (Runner CI): every PR into `main` and every push to `main`
  touching `runner/**`.
- `e2e`: every PR into `main`, unconditionally (no path filter), plus every
  push to `main`, plus `workflow_dispatch`.
- `e2e-preview`: every PR into `main` only (`if: github.event_name ==
  'pull_request'`) — never runs on a direct push.

**Secrets — confirmed configured** (`gh secret list`, names only):
```
E2E_SUPABASE_URL, E2E_SUPABASE_ANON_KEY, E2E_SUPABASE_SERVICE_ROLE_KEY,
E2E_TEST_USER_EMAIL, E2E_TEST_USER_PASSWORD, VERCEL_TOKEN, VERCEL_PROJECT_ID
```

**Branch protection — configured, but still missing `E2E (Playwright)`.**
`gh api repos/bucks-ai/app/branches/main/protection` (the repo is
`bucks-ai/app`, not `bucks-ai/bucks-ai`) shows a protection rule exists, with
`required_status_checks.contexts` currently `["Lint, typecheck, build",
"Runner tests"]`. `E2E (Playwright)` is not in that list, so it runs on every
PR/push but does not yet block a merge if red. This is unchanged from the
2026-07-07 pass and is the one founder action still fully outstanding.

## 4. Runner-side validation status

- **UI flow validation** (`tools/ui_flow_validator.py`, wired into
  `graph.py`'s `run_ui_flow_validation_if_needed` node): pure helpers
  (`build_default_flows`, `load_flows_from_file`, `evaluate_flow_results`,
  `format_flow_report`) are fully unit-tested and side-effect free. It's
  opt-in (`UI_FLOW_VALIDATION_ENABLED=false` by default). `build_default_flows`
  now covers the five core flows (added in PR #54) rather than requiring
  `UI_FLOW_CONFIG_PATH` for any coverage at all.
- **Deploy URL targeting**: `tools/deploy_target.py`'s `resolve_target_url`
  (added in PR #55) is now the single shared, unit-tested source of truth for
  the E2E-override-vs-deploy-result priority (`E2E_BASE_URL` always wins,
  else `deploy_result["url"]`/`deployment_url`). `run_e2e_if_needed` and
  `run_ui_flow_validation_if_needed` (`graph.py`) both call it.
  `run_product_eval_if_needed` still inlines the same two-line fallback
  logic rather than calling the shared helper — behaviorally identical today,
  but worth consolidating so the priority only lives in one place (see §6
  Next tasks).
- **Screenshots** (`tools/playwright_harness.py`): `capture_screenshot` is
  best-effort (returns `None` on failure rather than masking the real flow
  failure), writes timestamped, sanitized filenames under
  `outbox/screenshots/`, and `enforce_screenshot_retention` caps the
  directory to the most recent 100 files. Both are unit-tested without
  mocking a real browser.
- **Flaky-test policy** (added PR #56, `docs/M2-E2E-RUNBOOK.md` §7): the
  `@flaky` tag convention and non-blocking quarantine CI step now exist. The
  parallelism race documented in §2/§3 of this report is a strong candidate
  for this policy if the root cause (shared single seeded fixture across
  specs) isn't fixed directly first — see §6.
- All 1578 tests in `runner/langgraph/tests/` pass (`python -m pytest tests/
  -x -q`), confirming no runner-side regressions from this session.

## 5. What changed since the 2026-07-07 pass

The prior pass (PR #51) found four issues. Status now:

1. **Auth signup mailer rate limit** — not re-triggered in this pass's local
   or CI runs (§2, §3), but not independently confirmed fixed either
   (no Supabase dashboard access). Treat as unresolved until confirmed.
2. **`business-tabs.spec.ts` / `dashboard.spec.ts` parallelism race** — still
   present, and now also affects `tools.spec.ts` under high local
   parallelism (§2). Directly observed once inside real CI too (§3), where
   it was silently absorbed by `retries: 2`. Not fixed, but no longer purely
   theoretical — there's now a real CI data point.
3. **`tools.spec.ts` locator ambiguity (`permissionCard()` matching two
   elements)** — **fixed** (commit `240df6d`, "leaf-section tool card
   locator", merged via PR #48). Confirmed passing serially in this pass.
4. **`intake.spec.ts` hydration prop loss (`name` attribute stripped)** —
   **not reproducible in this pass**; the spec passed cleanly every time it
   was actually executed (§1's `E2E_FAKE_AI` scoping gotcha meant the prior
   pass may not have exercised this reliably either — worth treating the
   2026-07-07 finding with that caveat rather than as confirmed-then-fixed).

Additionally, both blockers §3 of the 2026-07-07 report called out as
structural (jobs not on `main`; `e2e-preview` never finding a deployment) are
resolved — see §3 above.

## 6. Outstanding founder actions

1. **Add `E2E (Playwright)` to branch protection's required status checks**
   for `main` (Settings → Branches → main, repo `bucks-ai/app`) — the rule
   already requires `Lint, typecheck, build` and `Runner tests` but not yet
   `E2E (Playwright)` (confirmed via the GitHub API in §3), so this is the
   only fully-outstanding item from the prior pass. Do not add the
   `[informational]` preview job as required — it's designed to be
   skippable.
2. **Confirm custom SMTP is configured for the E2E Supabase project**
   (Dashboard → Authentication → Emails → SMTP Settings), or confirm the
   built-in mailer's cap has otherwise been raised — this pass found no
   evidence of the rate-limit failure recurring, but also couldn't directly
   verify the dashboard setting (§5.1).

## 7. Known limitations of this verification pass

- The parallelism-dependent race (§2, §5.2) was reproduced but not
  root-caused or fixed — this task's scope is verification/reporting.
- Did not have Supabase dashboard access to directly confirm SMTP
  configuration (§6.2).
- The sandbox's stray `PLAYWRIGHT_BASE_URL` (§2) is local shell state, not a
  repo issue — noted here in case it affects a future session in the same
  sandbox.

## 8. Next tasks

- Fix the shared-fixture parallelism race (`business-tabs.spec.ts`,
  `dashboard.spec.ts`, `tools.spec.ts` all read/mutate the single seeded demo
  business) — either give each spec its own seeded business/tool-permission
  rows, or serialize them via Playwright's `test.describe.serial` /
  per-file project dependencies. Until fixed, consider tagging the affected
  tests `@flaky` per the PR #56 policy so CI's retry-driven passes are
  visible as quarantined rather than silently absorbed.
- Consolidate `run_product_eval_if_needed`'s inline base-URL fallback
  (`graph.py`) to call `tools/deploy_target.py`'s `resolve_target_url`, like
  the other two post-deploy nodes already do (§4) — purely a duplication
  cleanup, not a behavior change.
- Once branch protection is configured (§6.1), do a throwaway PR to confirm
  `E2E (Playwright)` actually blocks a merge when red, not just that it runs.
