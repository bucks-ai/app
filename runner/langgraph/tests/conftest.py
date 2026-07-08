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
