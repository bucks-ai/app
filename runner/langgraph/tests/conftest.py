"""Test-session guards.

The runner's flight recorder (log_tools.log_event) fans every event out to
Slack via notify_event. When pytest runs in a shell where .env has been
exported (set -a; source .env), SLACK_WEBHOOK_URL is set — so mocked failures
from the test suite ("simulated db error", "connection refused", ...) were
posted to the real team Slack channel on every check run. These fixtures make
the test suite integration-silent.
"""
import os
import pytest

from config import RunnerConfig

_LIVE_VARS = ("SLACK_WEBHOOK_URL", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN")

# Strip live-integration env before any test imports build the cached config.
for _v in _LIVE_VARS:
    os.environ.pop(_v, None)
os.environ["SLACK_NOTIFY"] = "false"


@pytest.fixture(autouse=True)
def _no_live_slack(monkeypatch):
    for v in _LIVE_VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("SLACK_NOTIFY", "false")


@pytest.fixture(autouse=True)
def _restore_has_supabase_property():
    """Some tests monkeypatch ``type(graph.cfg).has_supabase`` (a class-level
    property on the shared RunnerConfig class) to force a fixed value, and
    restore it afterwards with a closure bound to one specific cfg instance
    rather than the true original descriptor. That "restored" version still
    ignores the instance it's called on, so it leaks a wrong-but-plausible
    ``has_supabase`` result into every RunnerConfig built by later tests. This
    safety net guarantees the real class property is back in place after
    every test, regardless of what an individual test's own cleanup does."""
    original = RunnerConfig.has_supabase
    yield
    RunnerConfig.has_supabase = original
