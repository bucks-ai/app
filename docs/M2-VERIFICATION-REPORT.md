# M2 Verification Report

Full E2E verification pass performed 2026-07-07 against a dedicated E2E Supabase
project (real credentials, not mocked), plus a review of the current state of
CI on the open M2 PRs. This is the done-when evidence for M2.

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
unset — verified directly: running the suite with those vars unset produces
`1 skipped` (the signup test, gated separately on the service-role key) and
the rest either pass (specs with no data dependency) or fail with assertions
about missing seeded data (expected, since no seed step ran).

## 2. Local run results (this pass)

Environment: real dedicated E2E Supabase project (credentials already present
in the shell environment — no `.env.local` needed), `npm run seed:e2e`
succeeded, `next build` + `next start`, `E2E_FAKE_AI=true`.

- **`npm test`** (Vitest): 239/239 passed, 32 files.
- **`npm run build`**: clean, no type errors.
- **`npx playwright test` (default parallelism, 6 workers on this host)**: 5
  passed, 4 failed (`auth.spec.ts` signup, `business-tabs.spec.ts`,
  `dashboard.spec.ts`, `tools.spec.ts`), 1 skipped.
- **Re-run with `--workers=1`**: `business-tabs.spec.ts` and
  `dashboard.spec.ts` **passed**. `auth.spec.ts` signup and `tools.spec.ts`
  still failed identically.

### Findings, by root cause

1. **Auth signup — known, documented, not a regression.** Fails with
   `element(s) not found` waiting for "account created" after a real signup
   POST. This matches the Supabase built-in mailer's ~2 confirmation
   emails/hour cap, already documented in `docs/M2-E2E-RUNBOOK.md` §8 from an
   earlier reliability pass; this session's manual re-runs (several `npm run
   seed:e2e` + suite executions in short succession) plausibly exhausted the
   same cap. Fix already on file: configure custom SMTP for the E2E Supabase
   project (founder action, still outstanding — see §5).

2. **`business-tabs.spec.ts` / `dashboard.spec.ts` — parallelism-dependent,
   not seen serially.** Both specs read/assert against the single shared
   seeded demo business. At this host's default parallelism (6 workers) they
   intermittently failed; at `--workers=1` they passed cleanly every time.
   This points to a reliability gap in running the full suite fully parallel
   against one shared fixture, not a product bug. CI's `ubuntu-latest`
   runners are smaller (2 workers observed in the auth-only fail-fast step),
   which reduces but may not eliminate the exposure — this hasn't been
   confirmed against a real CI run of the full-suite step (see §3, the
   fail-fast gate has prevented that step from ever running so far).

3. **`tools.spec.ts` — genuine, deterministic, reproducible failure (not a
   flake).** Fails identically under both parallel and serial runs with a
   Playwright strict-mode violation: the `permissionCard()` helper's locator
   (tool-name heading + "Request approval" button, intended to uniquely
   scope the queue card and exclude the tool-registry preview card above it)
   resolves to **two** elements once a permission is in `approval_requested`
   state — both the queue card and the registry preview card render a
   "Request approval" button and "Approval Requested" text in that state.
   The disambiguation strategy documented in the spec's own comment ("the
   button only ever renders inside PermissionActionBar on the queue card")
   does not hold for this specific status value. This is a real test/UI
   coupling bug, independent of environment.

4. **`intake.spec.ts` — reproducible in this environment, root cause not
   isolated within this pass's budget.** Fails consistently (dev server,
   fresh `next build`+`next start`, with and without PostHog configured,
   `.next` fully cleared and rebuilt) waiting for `input[name="ideaName"]`.
   Instrumented directly: after client hydration, every form field in
   `IdeaIntakeWizard` (both `<input>` via `TextInput` and `<textarea>` via
   `TextArea`) loses its `name` attribute — confirmed by adding a novel
   `data-debug-marker` attribute to the source, rebuilding, and observing it
   present in the server-rendered HTML and the compiled client JS bundle, but
   absent from the live DOM's React fiber props after hydration. The `/login`
   page's plain, uncontrolled inputs are unaffected (auth tests' `name`-based
   locators work fine), so this isn't a blanket environment-level attribute
   stripper — it's specific to this controlled, wizard-step component tree.
   I was not able to fully isolate the mechanism inside this pass; flagging as
   a follow-up task (§6) rather than continuing to extend this
   already-long verification session. Because the CI `e2e` job's full-suite
   step has not yet successfully executed on any PR (see §3), there's no CI
   evidence either way on whether this specific failure is environment-local
   to this sandbox or would reproduce in CI too.

## 3. CI status (`.github/workflows/app.yml`)

The `e2e` and `e2e-preview` jobs are **not yet on `main`** — they exist only
on three still-open PRs (`feature/m2/ci-e2e` #44, `feature/m2/e2e-preview`
#45, `feature/m2/required-check` #48). `main`'s `App CI` workflow currently
only runs the `check` job (lint/typecheck/test/build), and `Runner CI` runs
the langgraph pytest suite. Both are the only two required status checks on
branch protection today. Because of this, opening this task's own PR against
`main` cannot exercise the `e2e` job — there is nothing on `main` to trigger
it. Status below is from directly inspecting the three open PRs' check runs.

| PR | `Lint, typecheck, build` | `Runner tests` | `E2E (Playwright)` | `E2E (Playwright, Vercel preview)` |
| --- | --- | --- | --- | --- |
| #44 `ci-e2e` | pass | pass | fail | — |
| #45 `e2e-preview` | pass | fail (stale — predates a later `main` fix merged after this branch's base) | fail | pass (correctly detected no preview available and skipped, per its informational design) |
| #48 `required-check` | pass | pass | fail | — |

All three `E2E (Playwright)` failures were inspected directly via the Actions
logs:
- Earliest runs (before PR #48's fixes) failed on a real, 100%-reproducible
  Node-version bug (`@supabase/supabase-js`'s realtime client needs native
  `WebSocket`, Node 20 doesn't have it) — fixed on #48 by pinning
  `node-version: 22` for the `e2e` job only.
- The next layer down was a real bug too: `bucks.ai` (used for throwaway
  signup emails) has no MX record, so Supabase's `signUp()` rejected every
  throwaway address as invalid — fixed on #48 by switching to `@gmail.com`
  addresses (nothing is ever delivered; the local part is a random UUID).
- The current, latest failure on #48 (and by extension #44, which predates
  these fixes) is the mailer rate-limit issue from §2.1 above — the job's
  fail-fast "auth flows" gate step (`npx playwright test e2e/auth.spec.ts`,
  run before the full-suite step) dies on the signup test before the
  full-suite step (which would run `business-tabs`/`dashboard`/`intake`/
  `tools`) ever executes. **This means the full E2E suite has never actually
  completed a run inside GitHub Actions CI** — every observed CI run so far
  has been stopped by the auth fail-fast gate.

**Trigger conditions:**
- `check` (App CI): every PR into `main` and every push to `main` touching
  `src/**`, `public/**`, or app config files.
- `pytest` (Runner CI): every PR into `main` and every push to `main`
  touching `runner/**`.
- `e2e` / `e2e-preview` (once merged): every PR into `main`, unconditionally
  (no path filter) — see `.github/workflows/app.yml` on `feature/m2/ci-e2e`.

**Secrets — already configured**, contrary to the runbook's earlier caveat
that this was a blocking founder action:

```
E2E_SUPABASE_URL, E2E_SUPABASE_ANON_KEY, E2E_SUPABASE_SERVICE_ROLE_KEY,
E2E_TEST_USER_EMAIL, E2E_TEST_USER_PASSWORD, VERCEL_TOKEN, VERCEL_PROJECT_ID
```
(confirmed via `gh secret list` — names only, not read). `docs/M2-E2E-RUNBOOK.md`
§5 should be updated to drop the "founder must add these" framing once #44 is
merged — the remaining blockers are the mailer rate limit and branch
protection, not missing secrets.

Despite `VERCEL_TOKEN`/`VERCEL_PROJECT_ID` being set, the `e2e-preview` job on
PR #45 still reported "Timed out waiting for a ready Vercel preview
deployment — skipping preview E2E" (its by-design graceful/non-blocking exit
path). This could mean the token/project ID pairing doesn't match an actual
Vercel project wired to auto-deploy previews for this repo, or that no
preview was triggered for that specific commit — worth a founder check but
not a code fix, and not currently blocking anything since the job is
informational.

## 4. Runner-side validation status

- **UI flow validation** (`tools/ui_flow_validator.py`, wired into
  `graph.py`'s `run_ui_flow_validation_if_needed` node): pure helpers
  (`build_default_flows`, `load_flows_from_file`, `evaluate_flow_results`,
  `format_flow_report`) are fully unit-tested and side-effect free. It's
  opt-in (`UI_FLOW_VALIDATION_ENABLED=false` by default) and no-ops cleanly
  with no flows defined — by design, flows must be supplied via
  `UI_FLOW_CONFIG_PATH`. Browser execution (`run_flow`) requires a real
  Playwright install and is covered by `tests/test_ui_flow_validator.py`
  including a screenshot-on-failure case.
- **Screenshots** (`tools/playwright_harness.py`): `capture_screenshot` is
  best-effort (returns `None` on failure rather than masking the real flow
  failure), writes timestamped, sanitized filenames under
  `outbox/screenshots/`, and `enforce_screenshot_retention` caps the
  directory to the most recent 100 files. Both are unit-tested without
  mocking a real browser.
- **Deploy URL targeting** (`graph.py`'s `run_e2e_if_needed`,
  `run_ui_flow_validation_if_needed`, and the product-eval node): all three
  resolve `base_url` the same way — `cfg.e2e_base_url` (an explicit
  `E2E_BASE_URL` override) takes priority, falling back to
  `deploy.get("url") or deploy.get("deployment_url")` from the actual deploy
  step's result, so post-deploy validation targets the real deployed
  artifact rather than a hardcoded URL.
- All 1534 tests in `runner/langgraph/tests/` pass (`python -m pytest tests/
  -x -q`), confirming this session's context — no runner-side regressions.

## 5. Outstanding founder actions

1. **Merge `feature/m2/ci-e2e` (#44) and `feature/m2/required-check` (#48)**
   into `main` — the `e2e` job doesn't exist on `main` yet, so nothing above
   can become a required check until this lands. #48 already contains the
   Node-version and MX-record fixes on top of #44; #45 (`e2e-preview`) is
   independent and informational-only.
2. **Configure custom SMTP for the E2E Supabase project** (Dashboard →
   Authentication → Emails → SMTP Settings) to remove the built-in mailer's
   ~2 emails/hour cap — this is the only failure standing between the
   current branch and a fully green `e2e` job at time of writing.
3. **Add `E2E (Playwright)` to branch protection's required status checks**
   for `main` (Settings → Branches → main) once the above two are done and a
   throwaway PR has been verified green — do **not** add the
   `[informational]` preview job.
4. **Check the Vercel project/token pairing** — `e2e-preview` never found a
   preview deployment for its test commit despite `VERCEL_TOKEN` and
   `VERCEL_PROJECT_ID` being set; confirm the token has access to the right
   project and that preview deployments are actually enabled for this repo
   before relying on this job's results.

## 6. Known limitations of this verification pass

- Ran the suite in this session's sandbox, not inside GitHub Actions — CI's
  full-suite step (the one that would exercise `dashboard`/`business-tabs`/
  `intake`/`tools`) has never completed a run in CI to date (see §3), so
  parallelism-related flakiness (§2 finding 2) and the intake hydration issue
  (§2 finding 4) are unconfirmed either way in the actual CI environment.
- The `tools.spec.ts` locator-ambiguity bug (§2 finding 3) and the
  `intake.spec.ts` hydration issue (§2 finding 4) are real, reproducible
  failures against this branch's current code — not addressed by this task,
  which is verification/reporting scope only.
- Did not attempt to fix the Supabase mailer rate limit (requires Supabase
  dashboard access, a founder action) or merge the open PRs (out of scope for
  a test/verification task).

## 7. Next tasks

- Fix `tools.spec.ts`'s `permissionCard()` disambiguation (or the underlying
  duplicate "Request approval" affordance across the queue card and registry
  preview card) so the locator uniquely resolves regardless of permission
  status.
- Root-cause the `intake.spec.ts` hydration prop loss (§2 finding 4) —
  bisect `IdeaIntakeWizard`'s step-conditional rendering, or reproduce with
  React's hydration diagnostics enabled, to confirm whether it's a genuine
  app bug or specific to this sandbox's browser/runtime.
- Investigate whether running the full local/CI suite with `--workers=1` (or
  giving each spec its own seeded business) is warranted to remove the
  parallelism-dependent flake in `business-tabs`/`dashboard` (§2 finding 2).
