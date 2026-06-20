# Runner subproject — agent instructions

You are working inside the bucks.ai autonomous development runner (`runner/langgraph/`). This is a LangGraph-based loop that dispatches Claude Code and Codex as workers, then commits, deploys, and tracks the results.

## Before you write any code

1. Read `README.md` in this directory for architecture context and node descriptions.
2. Read `state.py` to understand `RunnerState` — every graph node receives and returns it.
3. Read `config.py` to understand which env variables are available.
4. Check the relevant tool file in `tools/` and its test in `tests/` before extending either.

## Hard rules

- **Never commit directly to `main`.** All changes must be on a `feature/runner-*` branch.
- **Never bypass `./scripts/check.sh`** — run `python -m pytest tests/ -x -q` from this directory before finishing any Python task.
- **Never use `--no-verify`** on any git command.
- **Never print secret values** — credential names only, never values, in any log, file, or summary.
- **Never read or log** the contents of `inbox/*_resources_provided.txt` — treat it as an opaque existence signal.
- **Never modify `.runtime/` files** in a commit — they are gitignored, local-only loop state.

## Architecture invariants

- All graph nodes have the signature `(state: RunnerState) -> RunnerState`.
- Always return `_persist(state, "<node_name>")` at the end of every node — this saves state to disk.
- Log operational events via `log_event(event_type, payload)` in `tools/log_tools.py`, not `print()`.
- New tools go in `tools/<name>.py` with a matching `tests/test_<name>.py`.
- New config variables: add to `config.py`, update the env table in `README.md`, add at least one test.
- New graph nodes: add to `build_graph()` in `graph.py` with both `add_node` and the appropriate edge.

## Test requirements

```bash
# Run from runner/langgraph/
python -m pytest tests/ -x -q
```

All existing tests must pass before any commit. New features must ship with tests. Pure logic functions (guards, validators, formatters) must be unit-tested without mocking the graph or file system.

## Output format

The runner's `parse_worker_summary` reads your structured output. Always include **every field** below, even when the value is `none`:

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

Omitting a field or misspelling a key causes the runner to misparse the summary and may block the loop.
