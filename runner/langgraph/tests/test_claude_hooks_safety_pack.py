"""Tests for tools/claude_hooks_safety_pack.py."""
import json
import re
import pytest
from pathlib import Path

from tools.claude_hooks_safety_pack import (
    BLOCKED_BASH_PATTERNS,
    build_settings_payload,
    check_command,
    validate_hooks,
    write_hooks,
    _BASH_HOOK_CMD,
)


# ---------------------------------------------------------------------------
# BLOCKED_BASH_PATTERNS sanity checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", [
    "git push origin --force",
    "git push --force-with-lease",
    "git push origin main --force",
    "git push origin HEAD:main",
    "git push origin HEAD:master",
    "git push origin HEAD:production",
    "git push origin HEAD:release",
    "git reset --hard HEAD~1",
    "git reset --hard",
    "git commit --no-verify -m 'message'",
    "git commit -a --no-verify -m 'msg'",
    "git checkout -- .",
    "git checkout --  .",
    "git clean -f",
    "git clean -fd",
    "git clean -xfd",
    "git branch -D my-feature",
    "--gpg-sign=false",
    "git commit -c commit.gpgsign=false",
])
def test_dangerous_commands_are_blocked(cmd):
    matches = check_command(cmd)
    assert matches, f"Expected '{cmd}' to be blocked but no pattern matched"


@pytest.mark.parametrize("cmd", [
    "git push origin feature/my-task",
    "git push --set-upstream origin feature/my-task",
    "git reset HEAD file.py",
    "git reset --soft HEAD~1",
    "git commit -m 'add feature'",
    "git checkout -b feature/new-task",
    "git branch -d feature/old",
    "git clean -n",
    "git clean -i",
    "echo hello world",
    "npm test",
    "python -m pytest tests/ -x -q",
    "./scripts/check.sh",
])
def test_safe_commands_are_not_blocked(cmd):
    matches = check_command(cmd)
    assert not matches, f"Expected '{cmd}' to be allowed but pattern(s) matched: {matches}"


# ---------------------------------------------------------------------------
# build_settings_payload
# ---------------------------------------------------------------------------

def test_payload_has_hooks_key():
    p = build_settings_payload()
    assert "hooks" in p


def test_payload_has_pre_tool_use():
    hooks = build_settings_payload()["hooks"]
    assert "PreToolUse" in hooks
    assert isinstance(hooks["PreToolUse"], list)
    assert len(hooks["PreToolUse"]) >= 1


def test_payload_bash_matcher():
    entry = build_settings_payload()["hooks"]["PreToolUse"][0]
    assert entry.get("matcher") == "Bash"


def test_payload_command_type():
    entry = build_settings_payload()["hooks"]["PreToolUse"][0]
    hook = entry["hooks"][0]
    assert hook.get("type") == "command"
    assert "command" in hook
    assert hook["command"]


def test_payload_is_json_serialisable():
    payload = build_settings_payload()
    serialised = json.dumps(payload)
    assert json.loads(serialised) == payload


# ---------------------------------------------------------------------------
# Hook command: regex patterns survive the escaping chain
# ---------------------------------------------------------------------------

def test_hook_cmd_contains_force_pattern():
    assert "force" in _BASH_HOOK_CMD


def test_hook_cmd_contains_no_verify_pattern():
    assert "no-verify" in _BASH_HOOK_CMD


def test_hook_cmd_contains_reset_hard_pattern():
    assert "reset" in _BASH_HOOK_CMD


def test_hook_cmd_is_python3_invocation():
    assert _BASH_HOOK_CMD.strip().startswith("python3 -c")


def test_hook_cmd_exits_2_on_block():
    assert "sys.exit(2 if found else 0)" in _BASH_HOOK_CMD


def test_hook_cmd_reads_stdin():
    assert "sys.stdin" in _BASH_HOOK_CMD


# ---------------------------------------------------------------------------
# write_hooks
# ---------------------------------------------------------------------------

def test_write_hooks_creates_settings_file(tmp_path):
    result = write_hooks(tmp_path)
    assert result["wrote"] is True
    assert result["merged"] is True
    path = Path(result["path"])
    assert path.exists()


def test_write_hooks_valid_json(tmp_path):
    write_hooks(tmp_path)
    content = (tmp_path / ".claude" / "settings.json").read_text()
    data = json.loads(content)
    assert "hooks" in data
    assert "PreToolUse" in data["hooks"]


def test_write_hooks_idempotent(tmp_path):
    write_hooks(tmp_path)
    result2 = write_hooks(tmp_path)
    assert result2["wrote"] is False
    assert result2["merged"] is False


def test_write_hooks_preserves_existing_keys(tmp_path):
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    existing = {"permissions": {"allow": ["Read"]}, "hooks": {}}
    (settings_dir / "settings.json").write_text(json.dumps(existing))

    write_hooks(tmp_path)

    data = json.loads((settings_dir / "settings.json").read_text())
    assert data["permissions"] == {"allow": ["Read"]}


def test_write_hooks_appends_to_existing_pre_tool_use(tmp_path):
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    existing = {
        "hooks": {
            "PreToolUse": [
                {"matcher": "Write", "hooks": [{"type": "command", "command": "echo write"}]}
            ]
        }
    }
    (settings_dir / "settings.json").write_text(json.dumps(existing))

    write_hooks(tmp_path)

    data = json.loads((settings_dir / "settings.json").read_text())
    entries = data["hooks"]["PreToolUse"]
    matchers = [e.get("matcher") for e in entries]
    assert "Write" in matchers
    assert "Bash" in matchers


def test_write_hooks_handles_invalid_json(tmp_path):
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    (settings_dir / "settings.json").write_text("NOT JSON {{{")

    result = write_hooks(tmp_path)
    assert result["wrote"] is True


# ---------------------------------------------------------------------------
# validate_hooks
# ---------------------------------------------------------------------------

def test_validate_hooks_false_when_no_file(tmp_path):
    result = validate_hooks(tmp_path)
    assert result["valid"] is False
    assert "not found" in result["reason"]


def test_validate_hooks_true_after_write(tmp_path):
    write_hooks(tmp_path)
    result = validate_hooks(tmp_path)
    assert result["valid"] is True
    assert result["reason"] is None


def test_validate_hooks_false_when_hook_missing(tmp_path):
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    data = {"hooks": {"PreToolUse": []}}
    (settings_dir / "settings.json").write_text(json.dumps(data))

    result = validate_hooks(tmp_path)
    assert result["valid"] is False


def test_validate_hooks_false_on_invalid_json(tmp_path):
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    (settings_dir / "settings.json").write_text("{bad json")

    result = validate_hooks(tmp_path)
    assert result["valid"] is False
    assert "valid JSON" in result["reason"]


def test_validate_hooks_path_in_result(tmp_path):
    result = validate_hooks(tmp_path)
    assert "settings.json" in result["path"]
