"""Product Evaluation Harness for post-deploy HTTP-based product assertions.

Pure helpers (load_evals_from_file, evaluate_eval_results, format_eval_report,
build_default_evals) are side-effect free and fully unit-testable. HTTP execution
(run_eval, run_product_eval_suite) requires network access to the deployed URL.

Eval definition format (product_evals.json):
    [
        {
            "name": "homepage returns 200",
            "path": "/",
            "checks": [
                {"type": "status", "value": 200},
                {"type": "body_contains", "value": "Welcome"}
            ]
        },
        {
            "name": "api health endpoint",
            "path": "/api/health",
            "checks": [
                {"type": "status", "value": 200},
                {"type": "json_key", "key": "status", "value": "ok"}
            ]
        }
    ]

Supported check types:
    status           — HTTP response status code equals value (int)
    body_contains    — response body contains text value (str)
    header_contains  — response header named `key` contains value (str)
    json_key         — parsed JSON body has field `key` equal to value
    json_key_exists  — parsed JSON body has field `key` (any value)
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from tools.http_retry import retry_request


def build_default_evals(base_url: str) -> list[dict]:  # noqa: ARG001
    """Return an empty default eval list.

    No evals run by default — they must be defined in a product_evals.json config
    file (PRODUCT_EVAL_CONFIG_PATH) or passed directly to run_product_eval_suite.
    """
    return []


def load_evals_from_file(path: str) -> list[dict]:
    """Load eval definitions from a JSON file at path.

    Returns an empty list when the file is missing, unreadable, or contains
    invalid JSON. The top-level JSON value must be a list; a JSON object
    returns an empty list.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, list):
            return data
        return []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def evaluate_eval_results(results: list[dict]) -> dict:
    """Aggregate eval results into a summary dict.

    Each result dict must have: name (str), passed (bool), error (Optional[str]).

    Returns:
        passed       — True when every eval passed (True when no evals ran)
        total        — total eval count
        passed_count — number of passing evals
        failed       — list of names of failing evals
    """
    if not results:
        return {"passed": True, "total": 0, "passed_count": 0, "failed": []}

    failed = [r["name"] for r in results if not r.get("passed")]
    return {
        "passed": len(failed) == 0,
        "total": len(results),
        "passed_count": len(results) - len(failed),
        "failed": failed,
    }


def format_eval_report(results: list[dict], base_url: str) -> str:
    """Build a human-readable product evaluation report string."""
    evaluation = evaluate_eval_results(results)
    overall = "PASSED" if evaluation["passed"] else "FAILED"
    header = (
        f"Product Eval Report — {base_url}\n"
        f"Status: {overall}  "
        f"({evaluation['passed_count']}/{evaluation['total']} evals passed)\n"
    )
    lines = [header]
    for r in results:
        icon = "+" if r.get("passed") else "-"
        checks_run = r.get("checks_run", 0)
        line = f"  [{icon}] {r['name']}  ({checks_run} check(s))"
        if not r.get("passed") and r.get("error"):
            line += f"  — {r['error']}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def _run_check(check: dict, status: int, body: str, headers: dict) -> Optional[str]:
    """Run a single check against an HTTP response.

    Returns an error message string on failure, or None on success.
    """
    check_type = check.get("type", "")
    value = check.get("value")
    key = check.get("key", "")

    try:
        if check_type == "status":
            expected = int(value)
            if status != expected:
                return f"expected status {expected}, got {status}"
        elif check_type == "body_contains":
            if str(value) not in body:
                return f"body does not contain {value!r}"
        elif check_type == "header_contains":
            header_val = headers.get(key.lower(), "")
            if str(value) not in header_val:
                return f"header {key!r} value {header_val!r} does not contain {value!r}"
        elif check_type == "json_key":
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return "response body is not valid JSON"
            if key not in data:
                return f"JSON key {key!r} not found"
            if str(data[key]) != str(value):
                return f"JSON key {key!r} = {data[key]!r}, expected {value!r}"
        elif check_type == "json_key_exists":
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                return "response body is not valid JSON"
            if key not in data:
                return f"JSON key {key!r} not found"
        else:
            return f"unknown check type {check_type!r}"
    except Exception as exc:
        return f"check {check_type!r} raised: {exc}"

    return None


def _fetch_url(url: str, timeout_s: float) -> tuple:
    """Fetch ``url`` and return ``(status, body, headers)``.

    Non-transient HTTP errors (4xx other than 429) are returned as a normal
    result so the eval can inspect the status code. Transient errors (5xx, 429,
    network failures) are re-raised so ``retry_request`` can retry them.
    """
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            return (
                resp.status,
                resp.read().decode("utf-8", errors="replace"),
                {k.lower(): v for k, v in resp.headers.items()},
            )
    except urllib.error.HTTPError as exc:
        if exc.code >= 500 or exc.code == 429:
            raise  # transient — let retry_request handle
        return (
            exc.code,
            exc.read().decode("utf-8", errors="replace") if exc.fp else "",
            {k.lower(): v for k, v in (exc.headers or {}).items()},
        )


def run_eval(base_url: str, eval_def: dict, timeout_s: float = 15.0) -> dict:
    """Execute a single product eval (one HTTP request + N checks).

    Args:
        base_url  — root URL (e.g. "https://my-app.vercel.app")
        eval_def  — eval dict with ``name``, ``path``, and ``checks``
        timeout_s — per-request timeout in seconds

    Returns:
        {"name": str, "passed": bool, "error": Optional[str], "checks_run": int}
    """
    name = eval_def.get("name", "unnamed")
    path = eval_def.get("path", "/")
    checks = eval_def.get("checks", [])

    url = path if path.startswith("http") else base_url.rstrip("/") + path

    try:
        status, body, headers = retry_request(_fetch_url, url, timeout_s)
    except Exception as exc:
        return {
            "name": name,
            "passed": False,
            "error": f"request failed: {exc}",
            "checks_run": 0,
        }

    for i, check in enumerate(checks):
        error = _run_check(check, status, body, headers)
        if error:
            return {
                "name": name,
                "passed": False,
                "error": f"check {i + 1} ({check.get('type', '?')}): {error}",
                "checks_run": i + 1,
            }

    return {"name": name, "passed": True, "error": None, "checks_run": len(checks)}


def run_product_eval_suite(
    base_url: str,
    evals: Optional[list[dict]] = None,
    timeout_ms: int = 15000,
) -> dict:
    """Run all product evals against base_url.

    Args:
        base_url   — root URL to evaluate (e.g. "https://my-app.vercel.app")
        evals      — list of eval dicts; defaults to build_default_evals (empty)
        timeout_ms — per-request timeout in milliseconds

    Returns:
        success  — True when all evals passed (or no evals were defined)
        results  — list of per-eval result dicts
        report   — human-readable string report
        error    — fatal error message on unexpected failure, else None
    """
    if evals is None:
        evals = build_default_evals(base_url)

    if not evals:
        return {
            "success": True,
            "results": [],
            "report": format_eval_report([], base_url),
            "error": None,
        }

    timeout_s = timeout_ms / 1000.0
    results: list[dict] = []
    error_msg: Optional[str] = None

    try:
        for eval_def in evals:
            result = run_eval(base_url, eval_def, timeout_s=timeout_s)
            results.append(result)
    except Exception as exc:
        error_msg = str(exc)

    evaluation = evaluate_eval_results(results)
    report = format_eval_report(results, base_url)

    return {
        "success": evaluation["passed"] and error_msg is None,
        "results": results,
        "report": report,
        "error": error_msg,
    }
