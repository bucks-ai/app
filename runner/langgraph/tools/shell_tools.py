"""Shell command execution helper."""
import subprocess
from state import ToolResult
from tools.log_tools import log_event


def run_command(cmd: str | list, cwd: str = None, timeout: int = 120, stdin_data: str = None) -> ToolResult:
    shell = isinstance(cmd, str)
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=stdin_data,
        )
        success = result.returncode == 0
        output = (result.stdout or "") + (result.stderr or "")
        if not success:
            log_event("error", {"cmd": cmd, "returncode": result.returncode, "output": output[:500]})
        return ToolResult(tool="shell", success=success, output=output.strip())
    except subprocess.TimeoutExpired:
        log_event("error", {"cmd": cmd, "error": "timeout"})
        return ToolResult(tool="shell", success=False, error=f"Command timed out after {timeout}s")
    except Exception as e:
        log_event("error", {"cmd": cmd, "error": str(e)})
        return ToolResult(tool="shell", success=False, error=str(e))
