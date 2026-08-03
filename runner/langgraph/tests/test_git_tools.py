"""tools/git_tools.py::run_check — skips gracefully in repos with no scripts/check.sh
(business/foreign repos never have this bucks-ai-only convention)."""
import os
import stat

from tools.git_tools import run_check


def test_run_check_skips_when_no_check_script(tmp_path):
    result = run_check(str(tmp_path))
    assert result["success"] is True
    assert "skipped" in result["output"]


def test_run_check_runs_existing_script(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    check_sh = scripts_dir / "check.sh"
    check_sh.write_text("#!/bin/bash\necho ok\nexit 0\n")
    check_sh.chmod(check_sh.stat().st_mode | stat.S_IEXEC)

    result = run_check(str(tmp_path))
    assert result["success"] is True
    assert "ok" in result["output"]


def test_run_check_reports_failure_of_existing_script(tmp_path):
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    check_sh = scripts_dir / "check.sh"
    check_sh.write_text("#!/bin/bash\necho boom\nexit 1\n")
    check_sh.chmod(check_sh.stat().st_mode | stat.S_IEXEC)

    result = run_check(str(tmp_path))
    assert result["success"] is False
    assert "boom" in result["output"]
