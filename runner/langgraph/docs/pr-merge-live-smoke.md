# Live PR-Merge Smoke Test (Smoke Test 2)

**Date:** 2026-07-05
**Branch:** feature/smoke-pr-merge-2
**Worker:** claude (outbox mode)

## Purpose

Smoke Test 1 (`docs/two-worker-claude-smoke.md` / `smoke-pr-merge`) exercised the
runner's PR-based merge path (`_merge_via_pull_request` in `graph.py`) added in
M0.8b. This test goes one step further: it drives the *actual* GitHub flow by
hand — open a real PR against `origin/main`, let the required status checks
(`Lint, typecheck, build` and `Runner tests`) run to completion, and merge only
once both are green — to confirm the live path the runner depends on actually
works end-to-end against this repo's branch protection rules.

## Branch protection observed

`gh api repos/bucks-ai/app/branches/main/protection` on 2026-07-05 shows:

- `required_status_checks.strict`: `true`
- `required_status_checks.contexts`: `["Lint, typecheck, build", "Runner tests"]`
- `allow_force_pushes`: `false`
- `allow_deletions`: `false`

This matches what `_merge_via_pull_request` assumes: a direct `git push origin main`
or local `git merge` + push (the old `merge_feature_branch` path) would be
rejected by GitHub, since `main` requires a PR with passing checks.

## Procedure

1. Create `feature/smoke-pr-merge-2` off `main`.
2. Commit this doc, push the branch.
3. Open a PR via `gh pr create` (mirrors `create_pull_request` in `tools/github_tools.py`).
4. Poll `gh pr checks` / the commit status API until both required contexts
   reach a terminal state (mirrors `poll_pr_checks`).
5. Merge via `gh pr merge --squash` (mirrors `merge_pull_request`) only if both
   checks are green.
6. Confirm `main` fast-forwards/updates and the local repo can `fetch`/`pull` it.

## Results

_Filled in after the PR's checks complete — see below._
