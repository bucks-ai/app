# Auto-Merge Claude Smoke Note

**Date:** 2026-06-07
**Branch:** feature/runner-auto-merge-claude-smoke
**Worker:** claude (outbox mode)

## Summary

This note confirms that the bucks.ai runner's auto-merge flow works correctly when
a Claude worker task completes successfully. After `commit_push_merge_if_needed`
commits and pushes the feature branch, it calls `merge_feature_branch` automatically
when `AUTO_MERGE=true`.

## Auto-Merge Flow

The `commit_push_merge_if_needed` node (graph.py:196) executes this sequence:

1. Guard: reject protected branches (`main`, `master`, `dev`, etc.)
2. Create/switch to the feature branch
3. Run `commit_all` — stage and commit all changes
4. Run `push_branch` — push to origin
5. If `cfg.auto_merge` is `True`: run `merge_feature_branch` then `fetch_pull_main`

`AUTO_MERGE` defaults to `"true"` in `config.py:36`. Set `AUTO_MERGE=false` in
`.env` to disable automatic merging and leave the feature branch open for review.

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `AUTO_MERGE` | `true` | Merge feature branch into main after push |
| `AUTO_DEPLOY` | `true` | Trigger Vercel deploy after merge |
| `AUTO_APPLY_SQL` | `true` | Apply SQL migrations after merge |
| `REQUIRE_SQL_APPROVAL` | `false` | Gate SQL apply on human approval |

## Branch Safety

Protected branches (`main`, `master`, `dev`, `develop`, `production`, `release`)
are blocked at two points:

- **Early guard** (`load_next_task`): rewrites the task branch to `feature/<task-id>`
- **Late guard** (`commit_push_merge_if_needed`): emits an `error` event and returns
  early if the branch is still protected at commit time

## Check Result

`./scripts/check.sh` — pass

## Known Limitations

- `deploy` remote is not configured; `push_branch` to `deploy` always fails (non-blocker).
- `fetch_pull_main` after merge requires a clean working tree; state files
  (`state.json`, `tasks.json`) should be stashed or excluded before merge.
- True parallel multi-worker dispatch is not yet implemented.
