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
  python main.py doctor [--fix] [--json] [--no-supabase]
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

    # M4c.0: setup is the command an operator runs to find out whether this
    # config will work, so it must surface a broken timeout ordering here
    # rather than letting run-loop discover it overnight.
    from tools.config_invariants import format_violations
    violations = cfg.threshold_violations()
    if violations:
        print()
        print(format_violations(violations))
        sys.exit(1)

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

    threshold_invariants_or_exit("run-once")

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


def preflight_or_exit(command: str):
    """M4c: refuse to start an unattended loop from an unclean starting point.

    Workers operate on the runner's own working tree. Starting from a feature
    branch with uncommitted changes (observed 2026-08-02: the loop was launched
    from ``fix/sandbox-config-edit`` mid-edit) hands them a tree where intended
    state and in-flight work are indistinguishable — which is exactly what
    caused three M4b workers to stop and ask for clarification instead of
    executing. Exits the process rather than raising: this is an operator
    error to fix before starting, not a task failure to record.
    """
    from config import get_config
    from tools.dispatch_preflight import evaluate_loop_start
    from tools.log_tools import log_event

    cfg = get_config()
    if not cfg.loop_start_preflight_enabled:
        return

    verdict = evaluate_loop_start(cfg.repo_path)
    if verdict["ok"]:
        return

    log_event("loop_start_refused", {
        "command": command,
        "reason": verdict["reason"],
        "branch": verdict["branch"],
        "dirty": verdict["dirty"],
        "repo_path": cfg.repo_path,
    })
    print(f"✗ {verdict['message']}")
    print("  (override for local experiments only: LOOP_START_PREFLIGHT=false)")
    sys.exit(1)


def threshold_invariants_or_exit(command: str):
    """M4c.0: refuse to start when the timeout windows are not properly nested.

    The runner's timeouts are nested windows, not independent knobs, and an
    inverted pair does not error — it mis-behaves hours later somewhere that
    points nowhere near the cause. Two such inversions shipped in the defaults
    (a worker guard below the observed p90, a watchdog below the observed max
    task duration), and both surfaced as "the loop died overnight". Exits
    rather than raising: this is an operator error to fix in `.env` before
    starting, not a task failure to record.
    """
    from config import get_config
    from tools.config_invariants import format_violations
    from tools.log_tools import log_event

    cfg = get_config()
    violations = cfg.threshold_violations()
    if not violations:
        return

    log_event("config_invariant_violated", {
        "command": command,
        "violations": [
            {"invariant": v["invariant"], "values": v["values"]} for v in violations
        ],
    })
    print(format_violations(violations))
    sys.exit(1)


def install_wip_checkpoint_handlers(state_ref: dict):
    """M4c.4: make every exit path from the run loop commit the tree first.

    Work that exists only in the working tree is work that can vanish — m4c-03's
    1,552 finished lines sat uncommitted for days after a guard halted the loop
    before its commit step, and survived only because the founder happened to
    run `git status`. Ctrl+C, a watchdog's SIGTERM, an unhandled exception and a
    plain return all land here first.

    ``state_ref`` is the mutable holder the loop updates each iteration, so the
    handlers read the task in flight at the moment of the exit rather than
    whatever was current when they were installed.
    """
    from config import get_config
    from tools.wip_checkpoint import CheckpointContext, install_checkpoint_handlers

    cfg = get_config()
    if not cfg.wip_checkpoint_enabled:
        return None

    def _context():
        # Prefer the persisted state: every graph node writes it, so it names
        # the task in flight even when a signal arrives mid-cycle, hours before
        # graph.invoke() returns and updates state_ref. Fall back to the
        # in-memory holder when the state file is unreadable.
        from tools.log_tools import read_state

        try:
            state = read_state() or state_ref.get("state")
        except Exception:
            state = state_ref.get("state")

        task = _state_get(state, "current_task") or {}
        return CheckpointContext(
            repo_path=task.get("repo_path") or cfg.repo_path,
            task_id=_state_get(state, "current_task_id"),
            stop_reason=_state_get(state, "stop_reason"),
        )

    return install_checkpoint_handlers(_context, push=cfg.wip_checkpoint_push)


def _state_get(state, key, default=None):
    """Read a field from loop state that LangGraph may hand back as either a
    dict or a RunnerState."""
    if state is None:
        return default
    return state.get(key, default) if isinstance(state, dict) else getattr(state, key, default)


def cmd_run_loop(args):
    from graph import graph
    from state import RunnerState
    from tools.log_tools import read_state, update_state

    threshold_invariants_or_exit("run-loop")
    preflight_or_exit("run-loop")

    saved = read_state()
    init = RunnerState(**{k: v for k, v in saved.items() if k in RunnerState.model_fields})
    init = start_fresh_session(init)

    # Installed before the first invoke so even a crash inside the first cycle
    # exits through a checkpoint.
    state_ref = {"state": init}
    install_wip_checkpoint_handlers(state_ref)

    print("Starting autonomous loop (Ctrl+C to stop)...")
    _get = _state_get

    try:
        state = init
        while _get(state, "status") != "stopped":
            state = graph.invoke(state)
            state_ref["state"] = state
            lc = _get(state, "loop_count", 0)
            step = _get(state, "last_completed_step")
            st = _get(state, "status")
            print(f"  Loop {lc}: {step} — {st}")
            if _get(state, "stop_reason"):
                print(f"Loop stopped: {_get(state, 'stop_reason')}")
                break
    except KeyboardInterrupt:
        print("\nLoop interrupted by user.")


def cmd_watchdog(args):
    """M4c: babysitter wrapper — auto-restart run-loop on any non-human-gate exit.

    Runs ``python main.py run-loop`` as a subprocess and monitors it:
    - A background thread emits ``babysitter_heartbeat`` every
      WATCHDOG_HEARTBEAT_INTERVAL_S seconds so operators can confirm the
      wrapper is alive.
    - If the inner process has not updated its state file for more than
      WATCHDOG_STALL_THRESHOLD_S seconds, the thread kills the subprocess and
      the main loop restarts it (``watchdog_stall_detected``).
    - On subprocess exit, reads .runtime/state.local.json to get the
      stop_reason, then evaluates the restart decision:
        · Hard human gates (awaiting_resources, merge_approval_required, etc.)
          log ``watchdog_stopped`` and exit — a human must act first.
        · Everything else (rate limits, quota exhaustion, max_loop_tasks, …)
          logs ``watchdog_restart``, sleeps the appropriate wait, and restarts.
    - Ctrl+C propagates a clean stop.

    Slack pings are sent on start, each restart, and on permanent stop, using
    the existing ``notify_event`` machinery (degrades gracefully when the
    webhook is not configured).
    """
    import subprocess
    import threading
    import time
    from pathlib import Path

    from config import get_config
    from tools.log_tools import log_event, read_state
    from tools.loop_watchdog import evaluate_restart_decision

    cfg = get_config()
    heartbeat_interval_s = cfg.watchdog_heartbeat_interval_s
    stall_threshold_s = cfg.watchdog_stall_threshold_s
    max_restarts = cfg.watchdog_max_restarts
    restart_delay_s = cfg.watchdog_restart_delay_s
    # CLI flag overrides the env var
    if getattr(args, "max_restarts", None) is not None:
        max_restarts = args.max_restarts

    base_dir = Path(__file__).parent
    state_file = base_dir / ".runtime" / "state.local.json"
    python_bin = sys.executable
    run_loop_cmd = [python_bin, str(base_dir / "main.py"), "run-loop"]

    def _slack(event_type, payload):
        try:
            from tools.slack_tools import notify_event
            notify_event(event_type, payload)
        except Exception:
            pass  # Never interrupt the watchdog for a Slack error

    restart_count = 0
    log_event("watchdog_started", {
        "heartbeat_interval_s": heartbeat_interval_s,
        "stall_threshold_s": stall_threshold_s,
        "max_restarts": max_restarts,
    })
    _slack("watchdog_started", {
        "heartbeat_interval_s": heartbeat_interval_s,
        "stall_threshold_s": stall_threshold_s,
        "max_restarts": max_restarts,
    })
    print(
        f"Watchdog starting (heartbeat={heartbeat_interval_s}s "
        f"stall={stall_threshold_s}s max_restarts={max_restarts or 'unlimited'})"
    )

    while True:
        log_event("watchdog_loop_starting", {"restart_count": restart_count})

        try:
            proc = subprocess.Popen(run_loop_cmd, cwd=str(base_dir))
        except Exception as exc:
            log_event("watchdog_spawn_failed", {
                "error": str(exc),
                "restart_count": restart_count,
            })
            time.sleep(restart_delay_s)
            restart_count += 1
            continue

        stop_monitor = threading.Event()
        stall_triggered = threading.Event()

        def _monitor(proc=proc, stop=stop_monitor, stall=stall_triggered):
            last_heartbeat = time.time()
            last_mtime = state_file.stat().st_mtime if state_file.exists() else None

            while not stop.is_set() and proc.poll() is None:
                time.sleep(10)
                now = time.time()

                if now - last_heartbeat >= heartbeat_interval_s:
                    log_event("babysitter_heartbeat", {
                        "restart_count": restart_count,
                        "pid": proc.pid,
                    })
                    last_heartbeat = now

                if stall_threshold_s > 0 and state_file.exists():
                    try:
                        mtime = state_file.stat().st_mtime
                        if mtime != last_mtime:
                            last_mtime = mtime
                        else:
                            stale_age = now - (last_mtime or now)
                            if stale_age > stall_threshold_s:
                                log_event("watchdog_stall_detected", {
                                    "stale_seconds": round(stale_age),
                                    "pid": proc.pid,
                                    "restart_count": restart_count,
                                })
                                _slack("watchdog_stall_detected", {
                                    "stale_seconds": round(stale_age),
                                    "restart_count": restart_count,
                                })
                                stall.set()
                                proc.kill()
                                break
                    except OSError:
                        pass

        monitor = threading.Thread(target=_monitor, daemon=True, name="watchdog-monitor")
        monitor.start()

        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            stop_monitor.set()
            log_event("watchdog_stopped", {"reason": "keyboard_interrupt"})
            _slack("watchdog_stopped", {"reason": "keyboard_interrupt"})
            print("\nWatchdog stopped by user.")
            return
        finally:
            stop_monitor.set()

        monitor.join(timeout=5)

        state = read_state() or {}
        stop_reason = state.get("stop_reason")

        if stall_triggered.is_set():
            restart_count += 1
            log_event("watchdog_restart", {
                "reason": "stall detected — inner loop was silent",
                "restart_count": restart_count,
                "stop_reason": stop_reason,
            })
            _slack("watchdog_restart", {
                "reason": "stall detected — inner loop was silent",
                "restart_count": restart_count,
            })
            print(f"  Watchdog restarting after stall (restart #{restart_count})")
            time.sleep(restart_delay_s)
            continue

        decision = evaluate_restart_decision(
            stop_reason,
            state,
            max_restarts=max_restarts,
            restart_count=restart_count,
            default_delay_s=restart_delay_s,
            network_retry_delay_s=cfg.network_retry_delay_s,
            network_max_patience_s=cfg.network_max_patience_minutes * 60,
        )

        if not decision["should_restart"]:
            log_event("watchdog_stopped", {
                "reason": decision["reason"],
                "stop_reason": stop_reason,
                "restart_count": restart_count,
            })
            _slack("watchdog_stopped", {
                "reason": decision["reason"],
                "stop_reason": stop_reason,
                "restart_count": restart_count,
            })
            print(f"Watchdog stopping: {decision['reason']}")
            return

        wait = decision["wait_seconds"]
        restart_count += 1
        log_event("watchdog_restart", {
            "reason": decision["reason"],
            "restart_count": restart_count,
            "wait_seconds": round(wait),
            "stop_reason": stop_reason,
        })
        _slack("watchdog_restart", {
            "reason": decision["reason"],
            "restart_count": restart_count,
            "wait_seconds": round(wait),
            "stop_reason": stop_reason,
        })
        print(f"  Watchdog restarting in {round(wait)}s: {decision['reason']}")
        if wait > 0:
            time.sleep(wait)


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


def cmd_doctor(args):
    """Report task-queue health; with --fix, repair what can be repaired.

    Exits non-zero when the queue is unhealthy and nothing was fixed, so this
    is usable as a pre-flight check in a script and not just by eye.
    """
    from tools.queue_doctor import run_doctor

    result = run_doctor(
        fix=getattr(args, "fix", False),
        check_supabase=not getattr(args, "no_supabase", False),
    )
    if getattr(args, "json", False):
        print(json.dumps({"report": result["report"], "repairs": result["repairs"]}, indent=2))
    else:
        print(result["text"])

    if not result["report"]["healthy"]:
        sys.exit(1)


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

    p_watchdog = sub.add_parser(
        "watchdog",
        help=(
            "M4c babysitter: run run-loop as a subprocess and auto-restart on "
            "any non-human-gate exit (rate limits, session endings, crashes)"
        ),
    )
    p_watchdog.add_argument(
        "--max-restarts",
        type=int,
        default=None,
        dest="max_restarts",
        help="Override WATCHDOG_MAX_RESTARTS (0 = unlimited)",
    )

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

    p_doctor = sub.add_parser(
        "doctor",
        help="Report task-queue health (orphans, duplicates, invariant violations, Supabase divergence)",
    )
    p_doctor.add_argument("--fix", action="store_true", help="Apply the automatic repairs")
    p_doctor.add_argument("--json", action="store_true", help="Print the raw report as JSON")
    p_doctor.add_argument(
        "--no-supabase",
        action="store_true",
        dest="no_supabase",
        help="Skip the Supabase mission_tasks divergence check (offline / faster)",
    )

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
        "watchdog": cmd_watchdog,
        "analytics-report": cmd_analytics_report,
        "scan-sql": cmd_scan_sql,
        "logs": cmd_logs,
        "doctor": cmd_doctor,
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
