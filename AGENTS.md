<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

## Standard command workflow

- After editing code, run `./scripts/check.sh`
- To finish a feature branch, run `./scripts/finish-feature.sh "message"`
- To merge into main, run `./scripts/merge-feature.sh feature/name`
- Never commit `.env.local`
- Never print secrets
- Never run `npm audit fix --force`
- Never use `git push --force`
- Prefer `git merge --no-edit` to avoid vim merge screens
- If conflicts appear, stop and report them

## Branch safety (non-negotiable)

- **Every task must operate on a feature branch** — never on a protected branch.
- Branch naming: always `feature/<task-id>` (e.g. `feature/operating-team-ui`).
- Never set `branch: main`, `branch: master`, `branch: production`, or any other protected name in a task dict.
- Never use `git push --force` or `git push origin HEAD:main`.
- Never use `git reset --hard` without explicit human instruction.
- Never use `--no-verify` when committing — hooks exist for a reason.
- If you find yourself on `main`, stop and report — do not commit or push.

## Safety gate rules

- Never bypass `./scripts/check.sh` — it must pass before any commit.
- Never disable, remove, skip, or comment out a safety gate or guard (acceptance criteria gate, definition of done gate, scope guard, failure guard, resource gate, etc.).
- Never write tasks that contain force-push operations, hard resets, direct production deploys, or destructive database commands.
- Never add `--no-verify`, `commit.gpgsign=false`, or any other flag that bypasses commit hooks or signing.

## Secret and credential hygiene

- Never print, log, or commit secret values, API keys, tokens, or passwords — report *names only*.
- Never commit `.env`, `.env.local`, `.env.production`, or any file containing real credentials.
- Never read or log the contents of `inbox/<task_id>_resources_provided.txt` — it is a human-only fulfillment signal; treat it as opaque.
- When a task requires a missing credential, list the *name* only under "Credentials Needed" in the summary — never the value.

## Structured output format

Every task response must end with this exact structured summary so the runner can parse it:

```
- Files Created: (bullet list or "none")
- Files Modified: (bullet list or "none")
- Check Result: pass/fail
- Commit Result: (sha or skipped)
- Push Result: (done or skipped)
- SQL Required: yes/no
- SQL File Path: (path or N/A)
- Credentials Needed: (names only, or "none")
- Resources Needed: (names only, or "none")
- Known Limitations: (bullet list or "none")
- Next Task: (suggestions or "none")
```

Missing or misspelled keys cause the runner to misparse the summary — include all fields even when the value is "none" or "N/A".

## Runner subproject (runner/langgraph)

When working inside `runner/langgraph/`:

- Run `python -m pytest tests/ -x -q` after any Python change — all tests must pass before committing.
- Never change the `RunnerState` field names or types without updating all graph nodes that read those fields.
- Every new tool in `tools/` must be covered by a corresponding test file in `tests/`.
- New config variables require updates in three places: `config.py`, the env table in `README.md`, and any relevant tests.
- Log events via `log_event(...)` — never use `print()` for operational output.
- `.runtime/` files are gitignored and local-only; never commit them.
- `outbox/` and `inbox/` files are gitignored and transient; never commit them.
