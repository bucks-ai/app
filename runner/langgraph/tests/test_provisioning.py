"""Tests for tools/provisioning.py — parent-child self-provisioning."""
import pytest
from unittest.mock import MagicMock, patch

from tools.provisioning import (
    create_github_repo,
    add_github_deploy_key,
    create_vercel_project,
    set_vercel_env,
    link_vercel_git,
    create_supabase_project,
    get_supabase_api_keys,
    wait_supabase_project_ready,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(status_code: int, json_data: dict = None, raise_for_status_exc=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    if raise_for_status_exc:
        resp.raise_for_status.side_effect = raise_for_status_exc
    else:
        resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# GitHub — create_github_repo
# ---------------------------------------------------------------------------

class TestCreateGithubRepo:
    def test_no_token_returns_unavailable(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._gh_token", lambda: None)
        result = create_github_repo("myorg", "myrepo")
        assert result["available"] is False

    def test_no_org_returns_unavailable(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._gh_token", lambda: "tok")
        result = create_github_repo("", "myrepo")
        assert result["available"] is False

    def test_success(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._gh_token", lambda: "tok")
        resp = _mock_response(201, {"id": 1, "full_name": "myorg/myrepo"})
        with patch("tools.provisioning.retry_request", return_value=resp):
            result = create_github_repo("myorg", "myrepo")
        assert result["available"] is True
        assert result["created"] is True
        assert result["repo"]["full_name"] == "myorg/myrepo"

    def test_already_exists_422(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._gh_token", lambda: "tok")
        resp = _mock_response(422)
        with patch("tools.provisioning.retry_request", return_value=resp):
            result = create_github_repo("myorg", "existing")
        assert result["available"] is True
        assert result["created"] is False
        assert result["reason"] == "already_exists"

    def test_http_error(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._gh_token", lambda: "tok")
        with patch("tools.provisioning.retry_request", side_effect=Exception("500 Server Error")):
            result = create_github_repo("myorg", "myrepo")
        assert result["available"] is True
        assert result["created"] is False
        assert "500" in result.get("error", "")


# ---------------------------------------------------------------------------
# GitHub — add_github_deploy_key
# ---------------------------------------------------------------------------

class TestAddGithubDeployKey:
    def test_no_token_returns_unavailable(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._gh_token", lambda: None)
        result = add_github_deploy_key("org/repo", "CI key", "ssh-rsa AAAA...")
        assert result["available"] is False

    def test_success(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._gh_token", lambda: "tok")
        resp = _mock_response(201, {"id": 42})
        with patch("tools.provisioning.retry_request", return_value=resp):
            result = add_github_deploy_key("org/repo", "CI key", "ssh-rsa AAAA...")
        assert result["available"] is True
        assert result["created"] is True
        assert result["key_id"] == 42

    def test_error(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._gh_token", lambda: "tok")
        with patch("tools.provisioning.retry_request", side_effect=Exception("403")):
            result = add_github_deploy_key("org/repo", "key", "ssh-rsa AAAA...")
        assert result["created"] is False


# ---------------------------------------------------------------------------
# Vercel — create_vercel_project
# ---------------------------------------------------------------------------

class TestCreateVercelProject:
    def test_no_token_returns_unavailable(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._vercel_token", lambda: None)
        result = create_vercel_project("my-app")
        assert result["available"] is False

    def test_success(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._vercel_token", lambda: "vtok")
        monkeypatch.setattr("tools.provisioning._vercel_team_id", lambda: None)
        resp = _mock_response(200, {"id": "prj_abc", "name": "my-app"})
        with patch("tools.provisioning.retry_request", return_value=resp):
            result = create_vercel_project("my-app")
        assert result["available"] is True
        assert result["created"] is True
        assert result["project"]["id"] == "prj_abc"

    def test_already_exists_409(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._vercel_token", lambda: "vtok")
        monkeypatch.setattr("tools.provisioning._vercel_team_id", lambda: None)
        resp = _mock_response(409)
        with patch("tools.provisioning.retry_request", return_value=resp):
            result = create_vercel_project("my-app")
        assert result["created"] is False
        assert result["reason"] == "already_exists"

    def test_includes_team_id_when_configured(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._vercel_token", lambda: "vtok")
        monkeypatch.setattr("tools.provisioning._vercel_team_id", lambda: "team_123")
        resp = _mock_response(200, {"id": "prj_abc"})
        with patch("tools.provisioning.retry_request", return_value=resp) as mock_req:
            create_vercel_project("my-app")
        params = mock_req.call_args[1].get("params") or {}
        assert params.get("teamId") == "team_123"


# ---------------------------------------------------------------------------
# Vercel — set_vercel_env
# ---------------------------------------------------------------------------

class TestSetVercelEnv:
    def test_no_token(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._vercel_token", lambda: None)
        result = set_vercel_env("prj_abc", "KEY", "val")
        assert result["available"] is False

    def test_success(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._vercel_token", lambda: "vtok")
        monkeypatch.setattr("tools.provisioning._vercel_team_id", lambda: None)
        resp = _mock_response(200, {"id": "env_1"})
        with patch("tools.provisioning.retry_request", return_value=resp):
            result = set_vercel_env("prj_abc", "MY_KEY", "secret_val")
        assert result["available"] is True
        assert result["created"] is True

    def test_value_not_in_log(self, monkeypatch, capsys):
        """The secret value must never appear in log output."""
        monkeypatch.setattr("tools.provisioning._vercel_token", lambda: "vtok")
        monkeypatch.setattr("tools.provisioning._vercel_team_id", lambda: None)
        with patch("tools.provisioning.retry_request", side_effect=Exception("err")):
            set_vercel_env("prj_abc", "MY_KEY", "SUPER_SECRET_VALUE_XYZ")
        captured = capsys.readouterr()
        assert "SUPER_SECRET_VALUE_XYZ" not in captured.out
        assert "SUPER_SECRET_VALUE_XYZ" not in captured.err


# ---------------------------------------------------------------------------
# Vercel — link_vercel_git
# ---------------------------------------------------------------------------

class TestLinkVercelGit:
    def test_no_token(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._vercel_token", lambda: None)
        result = link_vercel_git("prj_abc", "myorg/myrepo")
        assert result["available"] is False

    def test_success(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._vercel_token", lambda: "vtok")
        monkeypatch.setattr("tools.provisioning._vercel_team_id", lambda: None)
        resp = _mock_response(200, {"id": "prj_abc"})
        with patch("tools.provisioning.retry_request", return_value=resp):
            result = link_vercel_git("prj_abc", "myorg/myrepo")
        assert result["linked"] is True

    def test_repo_parsed_correctly(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._vercel_token", lambda: "vtok")
        monkeypatch.setattr("tools.provisioning._vercel_team_id", lambda: None)
        resp = _mock_response(200, {})
        with patch("tools.provisioning.retry_request", return_value=resp) as mock_req:
            link_vercel_git("prj_abc", "myorg/myrepo")
        body = mock_req.call_args[1]["json"]
        assert body["link"]["org"] == "myorg"
        assert body["link"]["repo"] == "myrepo"


# ---------------------------------------------------------------------------
# Supabase — create_supabase_project
# ---------------------------------------------------------------------------

class TestCreateSupabaseProject:
    def test_no_management_key(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._supabase_management_key", lambda: None)
        monkeypatch.setattr("tools.provisioning._supabase_org_id", lambda: "org_1")
        result = create_supabase_project("test-app", "db_password_here")
        assert result["available"] is False
        assert "SUPABASE_MANAGEMENT_API_KEY" in result.get("reason", "")

    def test_no_org_id(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._supabase_management_key", lambda: "mkey")
        monkeypatch.setattr("tools.provisioning._supabase_org_id", lambda: None)
        result = create_supabase_project("test-app", "db_password_here")
        assert result["available"] is False
        assert "ORG_ID" in result.get("reason", "")

    def test_success(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._supabase_management_key", lambda: "mkey")
        monkeypatch.setattr("tools.provisioning._supabase_org_id", lambda: "org_1")
        resp = _mock_response(201, {"id": "proj_abc", "status": "COMING_UP"})
        with patch("tools.provisioning.retry_request", return_value=resp):
            result = create_supabase_project("test-app", "db_password_here")
        assert result["available"] is True
        assert result["created"] is True

    def test_db_password_not_in_log(self, monkeypatch, capsys):
        monkeypatch.setattr("tools.provisioning._supabase_management_key", lambda: "mkey")
        monkeypatch.setattr("tools.provisioning._supabase_org_id", lambda: "org_1")
        with patch("tools.provisioning.retry_request", side_effect=Exception("err")):
            create_supabase_project("test-app", "MY_SECRET_DB_PASSWORD")
        captured = capsys.readouterr()
        assert "MY_SECRET_DB_PASSWORD" not in captured.out
        assert "MY_SECRET_DB_PASSWORD" not in captured.err


# ---------------------------------------------------------------------------
# Supabase — get_supabase_api_keys
# ---------------------------------------------------------------------------

class TestGetSupabaseApiKeys:
    def test_no_management_key(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._supabase_management_key", lambda: None)
        result = get_supabase_api_keys("proj_abc")
        assert result["available"] is False

    def test_success(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._supabase_management_key", lambda: "mkey")
        keys = [{"name": "anon", "api_key": "anon_key"}, {"name": "service_role", "api_key": "svc_key"}]
        resp = _mock_response(200, keys)
        resp.json.return_value = keys
        with patch("tools.provisioning.retry_request", return_value=resp):
            result = get_supabase_api_keys("proj_abc")
        assert result["available"] is True
        assert len(result["keys"]) == 2


# ---------------------------------------------------------------------------
# Supabase — wait_supabase_project_ready
# ---------------------------------------------------------------------------

class TestWaitSupabaseProjectReady:
    def test_no_management_key(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._supabase_management_key", lambda: None)
        result = wait_supabase_project_ready("proj_abc")
        assert result["available"] is False

    def test_ready_on_first_poll(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._supabase_management_key", lambda: "mkey")
        resp = _mock_response(200, {"status": "ACTIVE_HEALTHY"})
        with patch("tools.provisioning.retry_request", return_value=resp):
            result = wait_supabase_project_ready("proj_abc")
        assert result["ready"] is True
        assert result["status"] == "ACTIVE_HEALTHY"

    def test_timeout(self, monkeypatch):
        monkeypatch.setattr("tools.provisioning._supabase_management_key", lambda: "mkey")
        resp = _mock_response(200, {"status": "COMING_UP"})
        with patch("tools.provisioning.retry_request", return_value=resp):
            with patch("tools.provisioning.time.monotonic", side_effect=[0, 0, 1000]):
                with patch("tools.provisioning.time.sleep"):
                    result = wait_supabase_project_ready("proj_abc", timeout_s=1)
        assert result["ready"] is False
        assert result["status"] == "timeout"
