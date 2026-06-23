"""Worker health probe.

Performs a lightweight pre-dispatch check before a worker is invoked to
detect obvious unavailability early — missing credentials, absent CLI
binaries — without making any LLM API calls.  Catching these conditions
before dispatching avoids burning a full task slot on a certain failure and
lets the runner log a clear diagnostic rather than a generic worker error.

Static probe: cheap filesystem + env-var lookups only, adds negligible
latency to each loop iteration.

Optional live ping (``live_ping_enabled=True``): runs the worker CLI with
``--version`` in a subprocess to confirm the binary actually starts.  Off by
default because it adds ~100–500 ms per dispatch; enable via
``WORKER_HEALTH_LIVE_PING=true`` when diagnosing flaky worker startups.

Design: pure helper ``probe_worker_health()`` returns a plain dict so it is
unit-testable without patching graph or file-system state, following the same
pure-helper + thin-node pattern used by ``tools/failure_guard.py``.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from typing import Optional

WORKER_HEALTH_STOP = "worker_health_probe_failed"

_CLAUDE_BINARIES = ("claude",)
_CODEX_BINARIES = ("codex",)

_DEFAULT_LIVE_PING_TIMEOUT_S = 10.0


def _binary_available(candidates: tuple[str, ...]) -> Optional[str]:
    """Return the first binary name found on PATH, or None."""
    for name in candidates:
        if shutil.which(name):
            return name
    return None


def _live_ping_binary(binary: str, timeout_s: float = _DEFAULT_LIVE_PING_TIMEOUT_S) -> dict:
    """Run ``binary --version`` in a subprocess to confirm it starts correctly.

    Returns a dict with:
        - ``alive``      — True when the process exited with code 0.
        - ``latency_ms`` — Wall-clock milliseconds the subprocess took.
        - ``reason``     — Human-readable failure description, or None on success.
    """
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            [binary, "--version"],
            timeout=timeout_s,
            capture_output=True,
        )
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        if proc.returncode == 0:
            return {"alive": True, "latency_ms": latency_ms, "reason": None}
        stderr = proc.stderr.decode(errors="replace").strip()
        return {
            "alive": False,
            "latency_ms": latency_ms,
            "reason": (
                f"{binary} --version exited with code {proc.returncode}"
                + (f": {stderr}" if stderr else "")
            ),
        }
    except subprocess.TimeoutExpired:
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        return {
            "alive": False,
            "latency_ms": latency_ms,
            "reason": f"{binary} --version timed out after {timeout_s}s",
        }
    except FileNotFoundError:
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        return {
            "alive": False,
            "latency_ms": latency_ms,
            "reason": f"{binary} binary not found when attempting live ping",
        }


def probe_worker_health(
    worker_type: str,
    claude_auth_mode: str,
    has_anthropic: bool,
    has_openai: bool,
    health_probe_enabled: bool = True,
    live_ping_enabled: bool = False,
    live_ping_timeout_s: float = _DEFAULT_LIVE_PING_TIMEOUT_S,
) -> dict:
    """Check whether the chosen worker appears ready to accept work.

    Args:
        worker_type:          ``"claude"`` or ``"codex"`` (other values pass).
        claude_auth_mode:     ``"api_key"`` or ``"subscription"``.
        has_anthropic:        True when ``ANTHROPIC_API_KEY`` is set.
        has_openai:           True when ``OPENAI_API_KEY`` is set.
        health_probe_enabled: When False the function is a no-op that always
                              returns ``available=True``.
        live_ping_enabled:    When True, run the worker CLI with ``--version``
                              via subprocess after the static checks pass.
                              Adds latency; default off.
        live_ping_timeout_s:  Seconds before the live-ping subprocess is
                              killed (default 10.0).

    Returns a dict with:
        - ``available``        — True when the worker appears ready.
        - ``worker``           — Echo of ``worker_type``.
        - ``reason``           — Human-readable explanation when not available.
        - ``blocked``          — True when the runner should halt.
        - ``stop_reason``      — ``WORKER_HEALTH_STOP`` when blocked, else None.
        - ``live_ping_latency_ms`` — Milliseconds the live ping took, or None.
    """
    if not health_probe_enabled:
        return {
            "available": True,
            "worker": worker_type,
            "reason": None,
            "blocked": False,
            "stop_reason": None,
            "live_ping_latency_ms": None,
        }

    available = True
    reason: Optional[str] = None
    live_ping_binary_name: Optional[str] = None

    if worker_type == "claude":
        cli_found = _binary_available(_CLAUDE_BINARIES)
        creds_ok = claude_auth_mode == "subscription" or has_anthropic
        if not cli_found:
            available = False
            reason = "claude CLI binary not found on PATH"
        elif not creds_ok:
            available = False
            reason = (
                "Claude requires ANTHROPIC_API_KEY (api_key mode) "
                "or CLAUDE_AUTH_MODE=subscription"
            )
        else:
            live_ping_binary_name = cli_found
    elif worker_type == "codex":
        cli_found = _binary_available(_CODEX_BINARIES)
        if not cli_found:
            available = False
            reason = "codex CLI binary not found on PATH"
        elif not has_openai:
            available = False
            reason = "Codex requires OPENAI_API_KEY"
        else:
            live_ping_binary_name = cli_found

    live_ping_latency_ms: Optional[float] = None
    if available and live_ping_enabled and live_ping_binary_name:
        ping = _live_ping_binary(live_ping_binary_name, timeout_s=live_ping_timeout_s)
        live_ping_latency_ms = ping["latency_ms"]
        if not ping["alive"]:
            available = False
            reason = ping["reason"]

    blocked = not available
    return {
        "available": available,
        "worker": worker_type,
        "reason": reason,
        "blocked": blocked,
        "stop_reason": WORKER_HEALTH_STOP if blocked else None,
        "live_ping_latency_ms": live_ping_latency_ms,
    }
