"""bucks.ai Autonomous Development Runner — CLI entry point.

Usage:
  python main.py setup
  python main.py status
  python main.py next-task
  python main.py run-once
  python main.py run-loop
  python main.py sync-github-issues [repo]
  python main.py analytics-report [--days N]
  python main.py scan-sql path/to/file.sql
  python main.py logs [--tail N]
  python main.py reset-state [--hard]
"""
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

# Add runner/langgraph to path so tools/workers can import each other cleanly
sys.path.insert(0, str(Path(__file__).parent))


def cmd_setup(args):
    from config import get_config
    from tools.task_tools import _ensure_tasks_file
    from tools.log_tools import _ensure_dirs

    cfg = get_config()
    _ensure_dirs()
    _ensure_tasks_file()

    for d in ("outbox", "inbox", "logs"):
        p = Path(__file__).parent / d
        p.mkdir(exist_ok=True)
        (p / ".gitkeep").touch()

    (Path(__file__).parent / ".runtime").mkdir(exist_ok=True)

    print("=== bucks.ai Autonomous Development Runner — Setup ===")
    report = cfg.report()
    for key, val in report.items():
        status = "✓" if val else "✗"
        if isinstance(val, str):
            print(f"  {key}: {val}")
        elif isinstance(val, bool):
            mark = "✓" if val else "–"
            print(f"  {key}: {mark}")
        else:
            print(f"  {key}: {val}")
    print()

    missing = []
    if not cfg.has_openai:
        missing.append("OPENAI_API_KEY (ChatGPT planner will use outbox/manual mode)")
    if not cfg.has_claude:
        missing.append("ANTHROPIC_API_KEY or CLAUDE_AUTH_MODE=subscription (Claude not available, will use CLI or outbox)")
    if not cfg.has_github:
        missing.append("GITHUB_TOKEN (GitHub tools degraded, tasks.json only)")
    if not cfg.has_supabase:
        missing.append("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY (SQL needs manual execution)")
    if not cfg.has_vercel:
        missing.append("VERCEL_TOKEN (deploy status unavailable)")
    if not cfg.has_slack:
        missing.append("SLACK_WEBHOOK_URL (Slack notifications disabled)")

    if missing:
        print("Missing (degraded mode):")
        for m in missing:
            print(f"  – {m}")
    else:
        print("All integrations configured. Full automatic mode available.")
    print("\nSetup complete.")


def cmd_status(args):
    from tools.log_tools import read_state
    state = read_state()
    if not state:
        print("No state found. Run: python main.py setup")
        return
    print(json.dumps(state, indent=2))


def cmd_next_task(args):
    from tools.task_tools import get_next_queued_task
    task = get_next_queued_task()
    if task:
        print(json.dumps(task, indent=2))
    else:
        print("No queued tasks.")


def cmd_sync_github_issues(args):
    from config import get_config
    from tools.github_tools import sync_open_issues_to_tasks

    cfg = get_config()
    repo = getattr(args, "repo", None) or cfg.github_repo
    if not repo:
        print("No GitHub repo configured. Set GITHUB_REPO=owner/name or pass repo.")
        return
    result = sync_open_issues_to_tasks(repo)
    print(json.dumps({
        "repo": result.get("repo"),
        "synced": result.get("synced", 0),
        "task_ids": [task.get("id") for task in result.get("tasks", [])],
    }, indent=2))


def cmd_run_once(args):
    from graph import graph
    from state import RunnerState
    from tools.log_tools import read_state, update_state
    from datetime import datetime

    saved = read_state()
    init = RunnerState(**{k: v for k, v in saved.items() if k in RunnerState.model_fields})
    if not init.started_at:
        init.started_at = datetime.utcnow().isoformat()
        init.status = "running"

    print("Running one LangGraph cycle...")
    result = graph.invoke(init)
    # LangGraph may return a dict or RunnerState
    if isinstance(result, dict):
        print(f"Completed step: {result.get('last_completed_step')}")
        print(f"Status: {result.get('status')}")
        if result.get("stop_reason"):
            print(f"Stop reason: {result.get('stop_reason')}")
    else:
        print(f"Completed step: {result.last_completed_step}")
        print(f"Status: {result.status}")
        if result.stop_reason:
            print(f"Stop reason: {result.stop_reason}")


def start_fresh_session(init):
    """Reset per-session fields so a restarted loop starts clean.

    Every run-loop invocation is a fresh session. A stop_reason, loop_count,
    failure streak, or started_at left over from a previous run would
    otherwise stop this run on its first cycle (instant "awaiting_resources"
    / "max_loop_tasks" / "max_runtime" stops after a restart). Likewise,
    task_attempt_counts carried over from .runtime/state.local.json would let
    the repeated-task guard insta-block a task on the new session's very
    first attempt, even though that task only exhausted its attempts in a
    previous, unrelated failure cascade — the guard is meant to measure
    attempts within one session, not across restarts.
    """
    init.stop_reason = None
    init.loop_count = 0
    init.consecutive_failures = 0
    init.started_at = datetime.utcnow().isoformat()
    init.status = "running"
    init.task_attempt_counts = {}
    return init


def cmd_run_loop(args):
    from graph import graph
    from state import RunnerState
    from tools.log_tools import read_state, update_state

    saved = read_state()
    init = RunnerState(**{k: v for k, v in saved.items() if k in RunnerState.model_fields})
    init = start_fresh_session(init)

    print("Starting autonomous loop (Ctrl+C to stop)...")
    def _get(s, key, default=None):
        return s.get(key, default) if isinstance(s, dict) else getattr(s, key, default)

    try:
        state = init
        while _get(state, "status") != "stopped":
            state = graph.invoke(state)
            lc = _get(state, "loop_count", 0)
            step = _get(state, "last_completed_step")
            st = _get(state, "status")
            print(f"  Loop {lc}: {step} — {st}")
            if _get(state, "stop_reason"):
                print(f"Loop stopped: {_get(state, 'stop_reason')}")
                break
    except KeyboardInterrupt:
        print("\nLoop interrupted by user.")


def cmd_reset_state(args):
    from tools.log_tools import update_state, log_event, _logs_path

    fresh = {
        "status": "idle",
        "current_task_id": None,
        "current_worker": None,
        "current_branch": None,
        "last_completed_step": None,
        "last_commit": None,
        "loop_count": 0,
        "started_at": None,
        "error": None,
        "current_task": None,
        "worker_result": None,
        "worker_summary": None,
        "worker_summary_digest": None,
        "context_compression": None,
        "check_passed": None,
        "sql_scan": None,
        "sql_approval_status": None,
        "messages": [],
        "stop_reason": None,
    }
    update_state(fresh)
    log_event("state_reset", {"hard": getattr(args, "hard", False)})
    print("State reset to idle.")

    if getattr(args, "hard", False):
        if _logs_path.exists():
            _logs_path.write_text("")
            print("Log file cleared.")
        else:
            print("No log file to clear.")


def cmd_soak(args):
    from tools.soak_harness import run_soak, format_soak_report, SoakConfig

    n = getattr(args, "tasks", 100) or 100
    seed = getattr(args, "seed", None)
    failure_rate = getattr(args, "failure_rate", 0.15)
    timeout_rate = getattr(args, "timeout_rate", 0.05)

    cfg = SoakConfig(
        worker_failure_rate=failure_rate,
        timeout_rate=timeout_rate,
        seed=seed,
    )
    print(f"Running soak harness: {n} tasks, failure_rate={failure_rate}, seed={seed}")
    result = run_soak(n, cfg)
    print(format_soak_report(result))
    if not result["completed"]:
        sys.exit(1)


def cmd_dry_run(args):
    """Run the LangGraph graph in dry-run mode using synthetic soak tasks.

    Workers, git operations, and deploys are all skipped.  The graph's full
    node traversal (guards, gates, reviews) runs normally so the topology can
    be validated without any real side effects.
    """
    import os
    import json
    import shutil
    import tempfile

    n = getattr(args, "tasks", 3) or 3
    seed = getattr(args, "seed", 42)

    # Must be set before importing graph/config (config singleton reads env at init time).
    os.environ["RUNNER_DRY_RUN"] = "true"
    os.environ["MAX_LOOP_TASKS"] = str(n)
    # Disable optional integrations so the dry run needs no credentials.
    os.environ.setdefault("LAUNCH_READINESS_SCORECARD_ENABLED", "false")
    os.environ.setdefault("STRATEGIC_GATE", "false")
    os.environ.setdefault("CLAUDE_HOOKS_SAFETY_PACK_ENABLED", "false")
    os.environ.setdefault("INDEPENDENT_CODE_REVIEW_ENABLED", "false")
    os.environ.setdefault("HIGH_RISK_CLAUDE_REVIEW_ENABLED", "false")
    os.environ.setdefault("CODEX_TO_CLAUDE_ESCALATION_ENABLED", "false")
    os.environ.setdefault("AUTO_REPAIR_LOOP_ENABLED", "false")

    from tools.soak_harness import generate_soak_tasks
    from tools.task_tools import _tasks_path, _ensure_tasks_file

    # Build synthetic task dicts in the format task_tools expects.
    soak_tasks = generate_soak_tasks(n, seed=seed)
    task_queue = [
        {
            "id": t["id"],
            "title": t["title"],
            "type": t["type"],
            "branch": t["branch"],
            "status": "queued",
            "retry_count": 0,
            "preferred_worker": t.get("preferred_worker"),
            "dry_run": True,
        }
        for t in soak_tasks
    ]

    _ensure_tasks_file()
    # Back up existing task queue and replace with synthetic tasks.
    original_content = _tasks_path.read_text() if _tasks_path.exists() else "[]"
    _tasks_path.write_text(json.dumps(task_queue, indent=2))

    print(f"Dry-run: {n} synthetic tasks, seed={seed}")
    print("(Workers, git, SQL, and deploy are all skipped)")

    try:
        from graph import graph
        from state import RunnerState
        from tools.log_tools import read_state, update_state

        saved = read_state()
        init = RunnerState(**{k: v for k, v in saved.items() if k in RunnerState.model_fields})
        init.status = "running"
        init.started_at = datetime.utcnow().isoformat()

        def _get(s, key, default=None):
            return s.get(key, default) if isinstance(s, dict) else getattr(s, key, default)

        state = init
        loops_run = 0
        stopped = False
        while _get(state, "status") != "stopped" and loops_run < n:
            state = graph.invoke(state)
            loops_run += 1
            lc = _get(state, "loop_count", 0)
            step = _get(state, "last_completed_step")
            st = _get(state, "status")
            task_id = _get(state, "current_task_id") or "-"
            print(f"  Loop {lc} [{task_id}]: {step} — {st}")
            stop_reason = _get(state, "stop_reason")
            if stop_reason:
                _expected = {"no_more_tasks", "no_queued_tasks", "max_loop_tasks"}
                if stop_reason in _expected:
                    print(f"Dry-run complete: {lc} task cycle(s) processed ({stop_reason}).")
                else:
                    print(f"Dry-run stopped unexpectedly: {stop_reason}")
                stopped = True
                break

        if not stopped:
            print(f"Dry-run complete: {loops_run} invocation(s) processed without errors.")
    finally:
        # Always restore the original task queue.
        _tasks_path.write_text(original_content)
        print("Task queue restored.")


def cmd_analytics_report(args):
    from tools.analytics_report import generate_analytics_report

    days = getattr(args, "days", 7) or 7
    result = generate_analytics_report(days=days)
    print(result["text"])
    print(f"Written to {result['report_path']}")


def cmd_scan_sql(args):
    from tools.sql_guard import scan_sql_file
    path = args.path
    result = scan_sql_file(path)
    print(json.dumps(result, indent=2))
    if result["ok"]:
        print("\n✓ SQL scan passed")
    else:
        print(f"\n✗ SQL scan BLOCKED: {result['blocked_terms']}")
        sys.exit(1)


def cmd_logs(args):
    from tools.log_tools import read_logs
    tail = getattr(args, "tail", 50) or 50
    events = read_logs(tail=tail)
    if not events:
        print("No log events found.")
        return
    for event in events:
        ts = event.get("timestamp", "")[:19]
        et = event.get("event_type", "unknown")
        tid = event.get("task_id") or ""
        tid_str = f" [{tid}]" if tid else ""
        print(f"{ts}{tid_str}  {et}")


def main():
    parser = argparse.ArgumentParser(
        description="bucks.ai Autonomous Development Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("setup", help="Validate config and create required folders")
    sub.add_parser("status", help="Print current state.json")
    sub.add_parser("next-task", help="Print next queued task")
    sub.add_parser("run-once", help="Run one LangGraph cycle")
    sub.add_parser("run-loop", help="Run continuous autonomous loop")

    p_soak = sub.add_parser("soak", help="Run the 100-task in-memory soak harness")
    p_soak.add_argument("--tasks", type=int, default=100, help="Number of tasks to simulate (default 100)")
    p_soak.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    p_soak.add_argument("--failure-rate", type=float, default=0.15, dest="failure_rate",
                        help="Worker failure injection rate 0.0–1.0 (default 0.15)")
    p_soak.add_argument("--timeout-rate", type=float, default=0.05, dest="timeout_rate",
                        help="Worker timeout injection rate 0.0–1.0 (default 0.05)")

    p_dry = sub.add_parser("dry-run", help="Run the graph in dry-run mode with synthetic tasks (no workers, git, or deploy)")
    p_dry.add_argument("--tasks", type=int, default=3, help="Number of synthetic tasks to run (default 3)")
    p_dry.add_argument("--seed", type=int, default=42, help="Random seed for task generation (default 42)")

    p_sync = sub.add_parser("sync-github-issues", help="Import open GitHub issues into the local task queue")
    p_sync.add_argument("repo", nargs="?", help="GitHub repo in owner/name form")

    p_analytics = sub.add_parser("analytics-report", help="Build the weekly analytics report (funnel + new Sentry issues)")
    p_analytics.add_argument("--days", type=int, default=7, help="Trailing window in days (default 7)")

    p_sql = sub.add_parser("scan-sql", help="Scan a SQL file for dangerous statements")
    p_sql.add_argument("path", help="Path to .sql file")

    p_logs = sub.add_parser("logs", help="Print recent log events")
    p_logs.add_argument("--tail", type=int, default=50, help="Number of events to show")

    p_reset = sub.add_parser("reset-state", help="Reset runner state to idle defaults")
    p_reset.add_argument(
        "--hard",
        action="store_true",
        help="Also truncate the log file (runs.jsonl)",
    )

    args = parser.parse_args()

    dispatch = {
        "setup": cmd_setup,
        "status": cmd_status,
        "next-task": cmd_next_task,
        "sync-github-issues": cmd_sync_github_issues,
        "run-once": cmd_run_once,
        "run-loop": cmd_run_loop,
        "analytics-report": cmd_analytics_report,
        "scan-sql": cmd_scan_sql,
        "logs": cmd_logs,
        "reset-state": cmd_reset_state,
        "soak": cmd_soak,
        "dry-run": cmd_dry_run,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
