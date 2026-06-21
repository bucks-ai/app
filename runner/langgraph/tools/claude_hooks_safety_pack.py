"""Claude Code hooks safety pack.

Generates and manages .claude/settings.json PreToolUse hooks that block
dangerous shell commands (destructive git operations, credential exposure)
and file writes to .env* paths when Claude workers are dispatched by the runner.

All pure-logic helpers are I/O-free; only write_hooks() touches the filesystem.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Blocked patterns
# Each entry is a regex matched against the full Bash command or file path.
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

# Matches any path whose final component starts with ".env" (.env, .env.local, .envrc, …)
BLOCKED_FILE_PATTERNS: list[str] = [
    r"(^|/)\.env",
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

# Inline Python one-liner for Write and Edit tools.
# Receives JSON on stdin: {"tool_name": "Write"|"Edit", "tool_input": {"file_path": "..."}}.
# Exits 2 to block the tool call when file_path matches .env* pattern.
_FILE_HOOK_CMD: str = (
    r"""python3 -c "import json,sys,re;"""
    r"""d=json.load(sys.stdin);"""
    r"""fp=d.get('tool_input',{}).get('file_path','');"""
    r"""blocked=bool(re.search(r'(^|/)\.env',fp));"""
    r"""print('[runner-safety] BLOCKED .env write: '+fp,file=sys.stderr) if blocked else None;"""
    r"""sys.exit(2 if blocked else 0)" """
)


# ---------------------------------------------------------------------------
# Payload builder
# ---------------------------------------------------------------------------

def build_settings_payload() -> dict:
    """Return the dict representing the runner-safety hooks block.

    Merge this into the existing .claude/settings.json rather than replacing it.
    """
    file_hook = {"type": "command", "command": _FILE_HOOK_CMD.strip()}
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
                },
                {
                    "matcher": "Write",
                    "hooks": [file_hook],
                },
                {
                    "matcher": "Edit",
                    "hooks": [file_hook],
                },
            ]
        }
    }


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

def write_hooks(repo_path: str | Path) -> dict:
    """Merge runner-safety PreToolUse hooks into <repo_path>/.claude/settings.json.

    Existing content is preserved.  Each new hook entry is checked individually
    by command string equality; only missing entries are appended.

    Returns:
        dict with keys: wrote (bool), path (str), merged (bool — True if any hook was added).
    """
    settings_path = Path(repo_path) / ".claude" / "settings.json"

    existing: dict = {}
    if settings_path.exists():
        try:
            existing = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            existing = {}

    new_entries = build_settings_payload()["hooks"]["PreToolUse"]
    existing_pre_tool: list = existing.get("hooks", {}).get("PreToolUse", [])

    # Collect all commands already installed to enable per-entry idempotency.
    installed_cmds: set[str] = set()
    for entry in existing_pre_tool:
        if isinstance(entry, dict):
            for hook in entry.get("hooks", []):
                cmd = hook.get("command")
                if cmd:
                    installed_cmds.add(cmd)

    to_add = [
        entry for entry in new_entries
        if entry.get("hooks", [{}])[0].get("command") not in installed_cmds
    ]

    if not to_add:
        return {"wrote": False, "path": str(settings_path), "merged": False}

    merged_pre_tool = existing_pre_tool + to_add

    result = dict(existing)
    result["hooks"] = dict(existing.get("hooks", {}))
    result["hooks"]["PreToolUse"] = merged_pre_tool

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(result, indent=2) + "\n")

    return {"wrote": True, "path": str(settings_path), "merged": True}


def validate_hooks(repo_path: str | Path) -> dict:
    """Check whether all runner-safety PreToolUse hooks are installed.

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

    required_cmds = {
        entry.get("hooks", [{}])[0].get("command")
        for entry in build_settings_payload()["hooks"]["PreToolUse"]
    }

    pre_tool = data.get("hooks", {}).get("PreToolUse", [])
    installed_cmds: set[str] = set()
    for entry in pre_tool:
        if isinstance(entry, dict):
            for hook in entry.get("hooks", []):
                cmd = hook.get("command")
                if cmd:
                    installed_cmds.add(cmd)

    missing = required_cmds - installed_cmds
    if not missing:
        return {"valid": True, "path": str(settings_path), "reason": None}
    return {
        "valid": False,
        "path": str(settings_path),
        "reason": f"missing {len(missing)} required runner-safety hook(s)",
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


def check_file_path(fp: str) -> list[str]:
    """Return the subset of BLOCKED_FILE_PATTERNS that match *fp*.

    Used in tests; not called at runtime.
    """
    return [p for p in BLOCKED_FILE_PATTERNS if re.search(p, fp)]
