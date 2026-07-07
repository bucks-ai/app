# M2 E2E Runbook

End-to-end tests run with [Playwright](https://playwright.dev) against a real
Next.js server and a dedicated Supabase test project. Specs live in `e2e/*.spec.ts`;
config is `playwright.config.ts`.

## 1. Run the suite locally

**Env vars** (put these in `.env.local`, never commit it — see `.env.example`):

| Var | Purpose |
| --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | Point at a **dedicated E2E Supabase project** — never production. The seed script deletes/recreates the test user's data on every run. |
| `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` | Credentials for the seeded E2E user. Specs `test.skip` themselves cleanly if these are unset. |
| `E2E_FAKE_AI` | Set to `true` so `/api/generate-blueprint` returns a deterministic fixture instead of calling a real AI provider (see §4). |

**Steps:**

```bash
npx playwright install chromium   # once, to install the browser
npm run seed:e2e                  # idempotent: creates/resets the E2E user + demo business
npm run dev                       # in one terminal, serving http://localhost:3000
npm run test:e2e                  # in another terminal
```

`test:e2e` targets `PLAYWRIGHT_BASE_URL` (default `http://localhost:3000`). To run
against another URL (e.g. a Vercel preview), export `PLAYWRIGHT_BASE_URL` before
running.

## 2. Debugging

- **UI mode** (interactive, watch/step through specs): `npm run test:e2e:ui`
- **Traces**: `playwright.config.ts` sets `trace: "on-first-retry"`, plus
  `screenshot: "only-on-failure"` and `video: "retain-on-failure"`. After a failing
  run, view the trace with:
  ```bash
  npx playwright show-trace test-results/<test-name>/trace.zip
  ```
- **HTML report**: `reporter` includes `html`; open it with `npx playwright show-report`
  after a run.
- **CI artifacts**: on failure, CI uploads `playwright-report/` and `test-results/`
  as workflow artifacts (14-day retention) — download them from the failed run's
  Actions summary page instead of trying to reproduce blind.

## 3. Adding a new spec

- One file per flow/page under `e2e/`, e.g. `e2e/business-tabs.spec.ts`.
- Rely only on Playwright's built-in auto-waiting (`toHaveURL`, `toBeVisible`, etc.
  retry until timeout) — no manual `waitForTimeout`/sleeps.
- If the spec needs the seeded user, add the standard skip guard at the top of the
  `describe` block:
  ```ts
  test.skip(
    !TEST_USER_EMAIL || !TEST_USER_PASSWORD,
    "TEST_USER_EMAIL / TEST_USER_PASSWORD not set — run `npm run seed:e2e` and set them first."
  );
  ```
- Reuse fixture data/helpers from `src/lib/seed-e2e.ts` (`DEMO_BUSINESS`,
  `DEMO_PENDING_TOOL_PERMISSIONS`, `findUserIdByEmail`) instead of hardcoding IDs —
  it's the single source of truth for what `seed:e2e` actually creates.
- If the flow calls an AI-backed route, gate the fixture behind `E2E_FAKE_AI` (see §4)
  rather than hitting a real model in CI.

## 4. Fake-AI mode and its production guard

`src/lib/e2e-fake-ai.ts` (`isFakeAiEnabled()`) makes AI-calling routes exercised by
E2E — currently just `/api/generate-blueprint` — skip the real model call and return
a fixture built from `generateMockBlueprint` instead, so the intake-to-blueprint spec
is fast, free, and deterministic.

**Production guard:** the flag only takes effect when `E2E_FAKE_AI=true` **and**
`NODE_ENV !== "production"`. If `E2E_FAKE_AI=true` leaks into a production
environment, `isFakeAiEnabled()` logs a warning and returns `false` — real users can
never be served fixture data.

## 5. CI jobs and secrets

Defined in `.github/workflows/app.yml`, on every PR into `main`:

- **`check`** — lint, `next typegen`, `tsc --noEmit`, `npm test`, `npm run build`.
  No E2E-specific secrets needed.
- **`e2e`** (blocking gate) — builds the app, seeds the E2E user, starts it with
  `npm run start`, waits for `http://localhost:3000` to respond, then runs
  `npm run test:e2e` with `E2E_FAKE_AI=true`.
- **`e2e-preview`** (informational, `continue-on-error: true` — see §6) — resolves
  the PR's Vercel preview URL and runs the same suite against it.

Both E2E jobs need these five repository secrets (Settings → Secrets and variables →
Actions), pointing at the **dedicated E2E Supabase project**, never production:

| Secret | Maps to |
| --- | --- |
| `E2E_SUPABASE_URL` | `NEXT_PUBLIC_SUPABASE_URL` |
| `E2E_SUPABASE_ANON_KEY` | `NEXT_PUBLIC_SUPABASE_ANON_KEY` |
| `E2E_SUPABASE_SERVICE_ROLE_KEY` | `SUPABASE_SERVICE_ROLE_KEY` |
| `E2E_TEST_USER_EMAIL` | `TEST_USER_EMAIL` |
| `E2E_TEST_USER_PASSWORD` | `TEST_USER_PASSWORD` |

`e2e-preview` additionally needs:

| Secret | Purpose |
| --- | --- |
| `VERCEL_TOKEN` | Vercel API token with access to the project |
| `VERCEL_PROJECT_ID` | Vercel project id for this app |

> These CI jobs currently live on `feature/m2/ci-e2e` / `feature/m2/e2e-preview` and
> are not yet merged to `main`. Once merged, the founder must add the secrets above
> before the `e2e` job can pass (it will fail closed, not skip, if they're missing).

## 6. The preview-URL job

`e2e-preview` resolves the PR head commit's Vercel deployment via
`scripts/wait-for-vercel-preview.sh`, which polls the Vercel API
(`GET /v6/deployments?projectId=...&sha=...`) for up to 10 minutes. It writes
`found`/`url` outputs and **never exits non-zero** — a missing token, missing
project id, unmatched deployment, error/canceled/blocked state, or timeout are all
treated as "no preview" and the job posts a `::notice::` and skips its remaining
steps gracefully.

This job is deliberately informational (`continue-on-error: true`): it validates the
real deployed artifact end-to-end, but a Vercel-side hiccup must never block a PR.
The local-build `e2e` job (§5) remains the blocking gate.

## 7. Flaky policy

- `playwright.config.ts` sets `retries: isCI ? 2 : 0` — CI auto-retries a failing
  test up to twice before marking it failed; local runs never retry, so a local
  fail is a real fail.
- `forbidOnly: isCI` — a stray `test.only` fails CI instead of silently skipping
  the rest of the suite.
- If a spec is genuinely flaky (fails intermittently even with retries), don't
  increase retries globally — fix the root cause (usually a missing
  auto-waiting assertion or a race in the seed data) or, as a last resort,
  `test.fixme()` it with a comment linking the follow-up task. Do not delete or
  silently disable a failing spec.
- The `e2e-preview` job is exempt from this policy by design (§6) — it's
  informational and expected to occasionally skip on Vercel-side timing.

## 8. Founder step: making `e2e` a required check

Once `feature/m2/ci-e2e` (and the secrets in §5) are merged/configured, the `e2e`
job needs to be added to branch protection so it actually blocks merges, matching
how `Lint, typecheck, build` and `Runner tests` are already required:

1. GitHub repo → **Settings → Branches → Branch protection rules** → edit the rule
   for `main`.
2. Under **Require status checks to pass before merging**, add **`E2E (Playwright)`**
   (the `e2e` job's `name:`) to the required list.
3. Do **not** add `E2E (Playwright, Vercel preview) [informational]` — it's designed
   to be advisory and would otherwise block merges on Vercel flakiness.
4. Confirm the five `E2E_*` secrets from §5 are set, then open a throwaway PR to
   verify the check appears and passes before relying on it.
