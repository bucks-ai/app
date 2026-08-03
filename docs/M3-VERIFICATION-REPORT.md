# M3 Verification Report

Mission: **M3 — Analytics + Observation**. This is the done-when evidence for
`m3-10-verification-report`. It records what was actually run and observed
against live PostHog/Sentry data on 2026-07-09, what could not be run and
exactly why, and the founder actions still outstanding.

## Verdict

- **Runner-side analytics tooling: verified live, working.** `posthog_tools`,
  `sentry_tools`, and `python main.py analytics-report` all made real API
  calls against the configured PostHog project (`497758`) and Sentry project
  (`bucksai`/`javascript-nextjs`) and returned real data.
- **Live signup -> deploy funnel walkthrough with `M3_VERIFY=true`: not
  executed.** Both places it could have run are blocked, for different
  reasons — see "What could not be verified" below. This is reported here
  rather than faked or silently skipped, per the task's own instruction.
- **Instrumentation gap found:** 9 of the 11 canonical funnel events have a
  real `capture()` call site; `intake_started` and `intake_submitted` do not
  (see "Event inventory" below). This is independent of the credential gap
  and is real work, not a founder action.

## What was verified live

Run from `runner/langgraph/`, using the real credentials already present in
`runner/langgraph/.env` (`POSTHOG_PERSONAL_API_KEY`, `POSTHOG_PROJECT_ID`,
`SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT` — all present, `has_posthog`
and `has_sentry` both `True`):

1. **`query_funnel` / `query_event_count` (`tools/posthog_tools.py`)** — live
   HogQL/Funnels queries against the PostHog Query API succeeded
   (`available: true`). `$pageview` shows 6 events in the trailing 90 days
   (confirms the project is genuinely receiving capture traffic — likely from
   manual browsing of the production deployment, see below). All 11 canonical
   funnel events (`user_signed_up` ... `deploy_succeeded`) return **0** over
   the same window — the funnel has never fired, in production or otherwise.
2. **`python main.py analytics-report --days 30`** — ran end-to-end, wrote
   `outbox/analytics_report.txt`, logged `analytics_report_ready`. The
   headline "deployed-repo" line **is answerable**: `Users who reached a
   deployed repo this week: 0` (a real zero, not a "not configured" fallback
   — the PostHog section fell back to "no funnel data returned" only because
   there's no data yet, not because the integration is absent).
3. **Sentry reader tools (`tools/sentry_tools.list_new_issues`)** — live call
   returned one real, currently-unresolved issue:
   `[JAVASCRIPT-NEXTJS-1] TypeError: Object [object Object] has no method
   'updateFrom'` (count=1, users=1, first/last seen 2026-07-09T02:54:24Z).
   Sentry is **configured and working** — contrary to the task description's
   example of what might still be missing, the DSN/org/project are all set
   and the reader path is live end-to-end.
4. **`npm run analytics:provision`** — idempotent PostHog dashboard
   provisioning ran live: both insights already existed and were updated in
   place, the dashboard already existed. Confirms the dashboard has been
   provisioned previously and provisioning stays idempotent on re-run (no
   duplicates created).
5. **Test suite** — `tests/test_posthog_tools.py`, `tests/test_analytics_report.py`,
   and `tests/test_sentry_tools.py` (50 tests) pass. Full runner suite:
   1097 passed / 1 failed, unrelated to this task (see Known Limitations).

## What could not be verified

The task asks for one live click-through of the real funnel (signup through
deploy status refresh) with `M3_VERIFY=true` set, so every event from that
run is stamped `verification_run: true` and findable via `posthog_tools`
without polluting real dashboards. Two possible places to run this exist,
and both are blocked:

- **Local dev server.** The repo root has no `.env.local` and its `.env` sets
  only PostHog/Sentry vars. `NEXT_PUBLIC_SUPABASE_URL`,
  `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY` are unset.
  Confirmed by reading `src/app/api/auth/signup/route.ts:24-29`: the route
  checks `hasSupabaseEnv()` first and returns a `503 supabase_not_configured`
  before anything else runs. `GITHUB_PERSONAL_ACCESS_TOKEN` and
  `VERCEL_TOKEN` are also unset (would block `repo_created` and
  `vercel_project_created` even if signup worked), and
  `TEST_USER_EMAIL`/`TEST_USER_PASSWORD` are unset (blocks `npm run
  seed:e2e`). The very first funnel step is unreachable in this sandbox.
- **Production deployment.** The app is already deployed and live at
  `https://bucks-ai-app-archive.vercel.app/` (confirmed reachable: `/` and
  `/signup` both return `200`) — this is almost certainly the source of the
  6 real `$pageview` events seen above. Its Supabase/GitHub/Vercel secrets
  live in Vercel's project settings, outside this sandbox. But `M3_VERIFY`
  is not set there, and setting it means editing production environment
  variables and forcing a redeploy — out of scope for a read-only
  verification pass, and running the funnel there *without* the flag would
  create real, unmarked signup/repo/deploy events indistinguishable from
  genuine user activity, contaminating the funnel dashboard instead of
  safely confirming it.

Given both paths are blocked for concrete, defensible reasons (not simply
"unconfigured and skipped"), no `verification_run: true` events exist yet.
The founder action to unblock this is listed below.

## Event inventory and capture points

Source of truth: `src/lib/analytics/events.ts` (`ANALYTICS_EVENTS`), narrated
in `docs/M3-EVENT-TAXONOMY.md`.

| Event | Stage | `business_id` required | Capture call site | Wired up? |
|---|---|---|---|---|
| `user_signed_up` | signup | no | `src/app/api/auth/signup/route.ts` (server-only, once per real account) | Yes |
| `intake_started` | intake | no | — | **No capture call site found anywhere in the app** |
| `intake_submitted` | intake | no | — | **No capture call site found anywhere in the app** |
| `blueprint_generated` | blueprint | no | `src/app/api/generate-blueprint/route.ts` (real + fake-AI fixture paths) | Yes |
| `blueprint_saved` | saved | yes (created here) | `src/app/api/businesses/save-blueprint/route.ts` | Yes |
| `tool_approval_requested` | tool_approved | yes | `src/app/api/tool-permissions/[id]/route.ts` | Yes |
| `tool_approved` | tool_approved | yes | `src/app/api/tool-permissions/[id]/route.ts` | Yes |
| `repo_created` | repo | yes | `src/app/api/github/create-repo/route.ts` | Yes |
| `scaffold_prepared` | repo | yes | `src/app/api/github/prepare-next-scaffold/route.ts` | Yes |
| `vercel_project_created` | deploy | yes | `src/app/api/vercel/create-project/route.ts` | Yes |
| `deploy_succeeded` | deploy | yes | `src/lib/vercel/deployment-status.ts` | Yes |

All capture points run through `guardCapture()` (`src/lib/analytics/guard.ts`),
which drops E2E/seeded-test traffic, re-enables and stamps
`verification_run: true` under `M3_VERIFY=true`, and never lets PII
(`FORBIDDEN_PROPERTY_KEYS`) into event properties. 9 of 11 events are wired
to a real capture call; `intake_started`/`intake_submitted` are catalogued
but not yet instrumented anywhere in `src/app/intake/` or
`src/components/intake/`.

## Dashboard links

Confirmed live via `npm run analytics:provision` (PostHog project `497758`):

- Dashboard **"bucks.ai core funnel"** (id `1821081`):
  `https://us.posthog.com/project/497758/dashboard/1821081`
- Insight **"Core signup -> deploy funnel"** (id `9946871`):
  `https://us.posthog.com/project/497758/insights/9946871`
- Insight **"Weekly unique users who deployed"** (id `9946872`):
  `https://us.posthog.com/project/497758/insights/9946872`

Sentry issue found during this pass (real permalink returned by the reader
tool, not constructed): `https://bucksai.sentry.io/issues/7601223819/`

## Runner tool status

| Tool | Status |
|---|---|
| `tools/posthog_tools.py` (`query_event_count`, `query_funnel`, `format_analytics_summary`) | Working — live queries succeed against project `497758` |
| `tools/sentry_tools.py` (`list_new_issues`, `issue_summary`) | Working — live query returned a real issue with permalink |
| `tools/analytics_report.py` / `python main.py analytics-report` | Working — writes `outbox/analytics_report.txt`, both sections render, headline line always answerable |
| `scripts/analytics/provision-dashboards.ts` / `npm run analytics:provision` | Working — idempotent, dashboard and both insights already provisioned and confirmed current |

## What remains not configured

Nothing on the runner side — PostHog and Sentry are both fully configured
and confirmed live. The gap is entirely at the **app** level, in this
sandbox only:

- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
  `SUPABASE_SERVICE_ROLE_KEY` — blocks any real signup (and thus the entire
  funnel) in local dev.
- `GITHUB_PERSONAL_ACCESS_TOKEN` — blocks `repo_created`/`scaffold_prepared`.
- `VERCEL_TOKEN` — blocks `vercel_project_created`/`deploy_succeeded`.
- `TEST_USER_EMAIL`, `TEST_USER_PASSWORD` — blocks `npm run seed:e2e` and any
  spec that depends on the seeded E2E user.

## Outstanding founder actions

1. **Decide how the one-off `M3_VERIFY=true` run actually happens.** Either:
   (a) provide a dedicated E2E Supabase project + `GITHUB_PERSONAL_ACCESS_TOKEN`
   + `VERCEL_TOKEN` in this sandbox's `.env.local` so the funnel can run
   locally end-to-end, or (b) temporarily set `M3_VERIFY=true` /
   `NEXT_PUBLIC_M3_VERIFY=true` on the production Vercel deployment for one
   signup-to-deploy click-through, then unset it — a deliberate, human-approved
   production config change this pass won't make unilaterally.
2. **Wire up `intake_started` and `intake_submitted` capture calls** in the
   intake wizard (`src/app/intake/`, `src/components/intake/`) — the taxonomy
   defines them but no code fires them yet, so the funnel's first two stages
   after signup will always show 0 regardless of credentials.
3. Once (1) produces real `verification_run: true` events, re-run
   `python main.py analytics-report` and confirm the funnel section (not just
   the headline) renders real step counts, then this report can be updated
   with the actual event IDs/timestamps as final closeout evidence.

## Known limitations

- `tests/test_pr_merge_flow.py::test_merge_via_pr_config_defaults` fails
  locally because `runner/langgraph/.env` sets `PR_CHECKS_TIMEOUT_S=1800`,
  overriding the test's hardcoded default of `900`. Pre-existing, unrelated
  to M3/analytics, and present on `main` before this task started — not
  fixed here to stay in scope.
- This report reflects a single point-in-time snapshot (2026-07-09). Event
  counts, the Sentry issue, and dashboard state will change as real traffic
  and future runs occur.
