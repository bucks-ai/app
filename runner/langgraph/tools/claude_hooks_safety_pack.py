"""Claude Code hooks safety pack.

Generates and manages .claude/settings.json PreToolUse hooks that block
dangerous shell commands (destructive git operations, credential exposure)
when Claude workers are dispatched by the runner.

All pure-logic helpers are I/O-free; only write_hooks() touches the filesystem.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Blocked patterns
# Each entry is a regex (case-insensitive) matched against the full Bash command.
# ---------------------------------------------------------------------------

BLOCKED_BASH_PATTERNS: list[str] = [
    r"git\s+push\s+.*--force",
    r"git\s+push\s+[^\s]+\s+[^\s]+:(main|master|production|release)",
    r"git\s+reset\s+--hard",
    r"git\s+commit\s+.*--no-verify",
    r"git\s+checkout\s+--\s*\.",
    r"git\s+clean\s+-\S*f",
    r"git\s+branch\s+-D",
    r"--gpg-sign=false",
    r"commit\.gpgsign=false",
]

# ---------------------------------------------------------------------------
# Hook command
# Inline Python one-liner executed by Claude Code as a PreToolUse hook.
# Receives JSON on stdin: {"tool_name": "Bash", "tool_input": {"command": "..."}}.
# Exits 2 to block the tool call; 0 to allow it.
# Raw string so backslash-s sequences survive json.dumps → json.loads → shell → Python.
# ---------------------------------------------------------------------------

_BASH_HOOK_CMD: str = (
    r"""python3 -c "import json,sys,re;"""
    r"""d=json.load(sys.stdin);"""
    r"""cmd=d.get('tool_input',{}).get('command','');"""
    r"""BLOCKED=["""
    r"""r'git\s+push\s+.*--force',"""
    r"""r'git\s+push\s+[^\s]+\s+[^\s]+:(main|master|production|release)',"""
    r"""r'git\s+reset\s+--hard',"""
    r"""r'git\s+commit\s+.*--no-verify',"""
    r"""r'git\s+checkout\s+--\s*\.',"""
    r"""r'git\s+clean\s+-\S*f',"""
    r"""r'git\s+branch\s+-D',"""
    r"""r'--gpg-sign=false',"""
    r"""r'commit\.gpgsign=false',"""
    r"""];"""
    r"""found=[p for p in BLOCKED if re.search(p,cmd)];"""
    r"""[print('[runner-safety] BLOCKED: '+p,file=sys.stderr) for p in found];"""
    r"""sys.exit(2 if found else 0)" """
)


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------

def build_settings_payload() -> dict:
    """Return the dict representing the runner-safety hooks block.

    Merge this into the existing .claude/settings.json rather than replacing it.
    """
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": _BASH_HOOK_CMD.strip(),
                        }
                    ],
                }
            ]
        }
    }


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

def write_hooks(repo_path: str | Path) -> dict:
    """Merge runner-safety PreToolUse hook into <repo_path>/.claude/settings.json.

    Existing content is preserved.  If the runner-safety hook is already present
    (matched by command string equality) the file is left unchanged.

    Returns:
        dict with keys: wrote (bool), path (str), merged (bool — True if hook was added).
    """
    settings_path = Path(repo_path) / ".claude" / "settings.json"

    existing: dict = {}
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            existing = {}

    runner_cmd = build_settings_payload()["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    existing_pre_tool: list = (
        existing.get("hooks", {}).get("PreToolUse", [])
    )

    already_present = any(
        isinstance(entry, dict)
        and entry.get("hooks", [{}])[0].get("command") == runner_cmd
        for entry in existing_pre_tool
    )

    if already_present:
        return {"wrote": False, "path": str(settings_path), "merged": False}

    merged_pre_tool = existing_pre_tool + build_settings_payload()["hooks"]["PreToolUse"]

    result = dict(existing)
    result["hooks"] = dict(existing.get("hooks", {}))
    result["hooks"]["PreToolUse"] = merged_pre_tool

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(result, indent=2) + "\n")

    return {"wrote": True, "path": str(settings_path), "merged": True}


def validate_hooks(repo_path: str | Path) -> dict:
    """Check whether the runner-safety PreToolUse hook is installed.

    Returns:
        dict with keys: valid (bool), path (str), reason (str | None).
    """
    settings_path = Path(repo_path) / ".claude" / "settings.json"

    if not settings_path.exists():
        return {
            "valid": False,
            "path": str(settings_path),
            "reason": "settings.json not found",
        }

    try:
        data = json.loads(settings_path.read_text())
    except json.JSONDecodeError:
        return {
            "valid": False,
            "path": str(settings_path),
            "reason": "settings.json is not valid JSON",
        }

    runner_cmd = build_settings_payload()["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    pre_tool = data.get("hooks", {}).get("PreToolUse", [])
    found = any(
        isinstance(entry, dict)
        and entry.get("hooks", [{}])[0].get("command") == runner_cmd
        for entry in pre_tool
    )

    if found:
        return {"valid": True, "path": str(settings_path), "reason": None}
    return {
        "valid": False,
        "path": str(settings_path),
        "reason": "runner-safety PreToolUse Bash hook not found",
    }


# ---------------------------------------------------------------------------
# Testing helper
# ---------------------------------------------------------------------------

def check_command(cmd: str) -> list[str]:
    """Return the subset of BLOCKED_BASH_PATTERNS that match *cmd*.

    Case-sensitive: git flags are case-sensitive (-d vs -D).
    Used in tests; not called at runtime.
    """
    return [p for p in BLOCKED_BASH_PATTERNS if re.search(p, cmd)]
