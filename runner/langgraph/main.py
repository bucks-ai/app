"""bucks.ai Autonomous Development Runner — CLI entry point.

Usage:
  python main.py setup
  python main.py status
  python main.py next-task
  python main.py run-once
  python main.py run-loop
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
    if not cfg.has_anthropic:
        missing.append("ANTHROPIC_API_KEY (Claude API not available, will use CLI or outbox)")
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


def cmd_run_loop(args):
    from graph import graph
    from state import RunnerState
    from tools.log_tools import read_state, update_state
    from datetime import datetime

    saved = read_state()
    init = RunnerState(**{k: v for k, v in saved.items() if k in RunnerState.model_fields})
    if not init.started_at:
        init.started_at = datetime.utcnow().isoformat()
    init.status = "running"

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
        "run-once": cmd_run_once,
        "run-loop": cmd_run_loop,
        "scan-sql": cmd_scan_sql,
        "logs": cmd_logs,
        "reset-state": cmd_reset_state,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
