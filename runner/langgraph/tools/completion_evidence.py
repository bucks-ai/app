"""Evidence-based completion gate (M4c) — never score a refusal as success.

The runner used to mark a task complete on one signal: the worker process
exited successfully. Nothing checked whether the worker had actually *done*
anything. On 2026-07-30 03:34 and again on 2026-07-31 02:29, ``ai-infra-03``
("Deploy the scaffolded app") was marked complete twice while the worker had
refused the task and deployed nothing:

- ``run_summary_digest`` → ``Files: created none; modified none``
- ``task_definition_of_done_warned`` → "no files created or modified reported
  in worker output" — a *warning*, because the DoD gate is non-strict by
  default, so the loop sailed straight past it
- the worker's final output was a question, not a report: "do you want me to:
  1. Execute it... 2. Just summarize..."
- ``task_completed`` → and ``seeded_mission_task_synced`` pushed that same
  false success back to Supabase, leaving the mission marked done with its
  core deliverable missing

Silent false success is worse than a crash. Every other M4b failure was loud;
this one looked like a win. So this gate inverts the default: **completion must
be earned with positive, independently verified evidence**, and anything short
of that is ``blocked`` — never ``complete``, and never ``failed`` either, since
a refusal is not a failure of the code, it is work that was never attempted.

Two independent tests, both of which ``ai-infra-03`` fails:

1. **Refusal / question / no-op detection** (``detect_refusal``). A worker that
   says it is not going to do the work, or asks the operator a question instead
   of reporting, is blocked by definition — a question means the work is still
   pending a decision, whatever the exit code said.
2. **Positive evidence** (``verify_evidence``), appropriate to the task type
   and *verified against the world rather than the worker's self-report*:
   a file that exists on disk, a commit sha that exists and is reachable from
   the expected remote, a deployment URL that answers a real request.

Evidence beats self-report in both directions: a "no-op" signal such as
``Commit Result: skipped`` does not block a task whose commit is provably in
the remote, and conversely a summary full of confident claims does not complete
a task whose claimed files are not on disk.

Config: ``COMPLETION_EVIDENCE_GATE_ENABLED`` (default true). Deliberately there
is **no warn-only mode**. The DoD gate had one, defaulted to it, and that is
precisely how ``ai-infra-03`` shipped twice — a gate that only warns about a
missing deliverable is not a gate.
"""
import os
import re
from typing import Callable, Optional

from tools.log_tools import log_event

# ── Signal kinds ────────────────────────────────────────────────────────────
REFUSAL = "refusal"    # the worker said it would not do the work
QUESTION = "question"  # the worker asked the operator instead of reporting
NO_OP = "no_op"        # the worker reported having changed nothing

#: Signals that block on their own. A refusal or a question is a statement that
#: the work was not done; no amount of ambient evidence talks us out of it.
HARD_SIGNALS = frozenset({REFUSAL, QUESTION})

# ── Evidence kinds ──────────────────────────────────────────────────────────
EVIDENCE_FILES = "files"
EVIDENCE_COMMIT = "commit"
EVIDENCE_DEPLOYMENT = "deployment"
#: A successfully merged PR whose sha GitHub returned at merge time.
EVIDENCE_MERGED_PR = "merged_pr"
#: Satisfied by *any* of: files-on-disk, a commit-in-remote, or a merged PR
#: — the bar for a task whose deliverable is source changes, however they landed.
EVIDENCE_ARTIFACT = "artifact"

GATE_NAME = "completion_evidence"
EVENT_VERIFIED = "task_completion_evidence_verified"
EVENT_MISSING = "task_completion_evidence_missing"
EVENT_NO_OP_OVERRIDDEN = "task_completion_no_op_overridden_by_evidence"

_EMPTY_VALUES = frozenset({"", "none", "n/a", "na", "(none)", "not applicable", "skipped"})

# ── Detection patterns ──────────────────────────────────────────────────────
# Kept deliberately narrow. A false positive costs one task a `blocked` status
# (recoverable, and visible in outbox/), while a false negative is the bug this
# module exists to kill — but a gate that cries wolf gets turned off, which is
# the same bug by another route.

_REFUSAL_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\bi(?:'m|’m| am)\s+not\s+going\s+to\b", re.I), "I am not going to"),
    (re.compile(r"\bi\s+(?:will|would)\s+not\s+(?:be\s+)?(?:do|run|execute|deploy|creat|writ|mak|proceed)", re.I), "I will not <do the work>"),
    (re.compile(r"\bi(?:'m|’m| am)\s+(?:unable|not\s+able)\s+to\s+(?:complete|do|execute|deploy|proceed)", re.I), "I am unable to complete"),
    (re.compile(r"\bi\s+can(?:not|'t|’t)\s+(?:complete|execute|deploy|proceed|do\s+this)\b", re.I), "I cannot complete"),
    (re.compile(r"\b(?:i\s+)?refus(?:e|ed|ing)\s+to\b", re.I), "refusing to"),
    (re.compile(r"\bi\s+(?:did|have)\s+not\s+(?:actually\s+)?(?:deploy|execute|run|commit|creat|modif|chang)", re.I), "I did not actually <do the work>"),
    (re.compile(r"\bno\s+(?:changes|work|files)\s+were\s+made\b", re.I), "no changes were made"),
)

_QUESTION_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\bdo\s+you\s+want\s+me\s+to\b", re.I), "do you want me to"),
    (re.compile(r"\bwould\s+you\s+like\s+me\s+to\b", re.I), "would you like me to"),
    (re.compile(r"\bshould\s+i\s+(?:proceed|continue|execute|run|deploy|go\s+ahead)\b", re.I), "should I proceed"),
    (re.compile(r"\b(?:please\s+)?let\s+me\s+know\s+(?:if|whether|which|how)\b", re.I), "let me know which"),
    (re.compile(r"\bplease\s+(?:confirm|advise|clarify)\b", re.I), "please confirm/advise"),
    (re.compile(r"\bwhich\s+(?:option|approach|one)\s+(?:do|would|should)\s+you\b", re.I), "which option do you want"),
    (re.compile(r"\bwaiting\s+for\s+(?:your\s+)?(?:confirmation|approval|instructions)\b", re.I), "waiting for your confirmation"),
)

_NO_OP_COMMIT_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\bno\s+new\s+commit\b", re.I), "no new commit"),
    (re.compile(r"\bnothing\s+to\s+commit\b", re.I), "nothing to commit"),
)

_FENCE = re.compile(r"```.*?```", re.S)


def _prose(text: str) -> str:
    """Strip fenced code blocks so a pattern inside a quoted sample or a diff
    doesn't read as the worker's own voice."""
    return _FENCE.sub(" ", text or "")


def _meaningful_items(items) -> list[str]:
    return [str(v).strip() for v in (items or []) if str(v).strip().lower() not in _EMPTY_VALUES]


def _is_empty(value) -> bool:
    return value is None or str(value).strip().lower() in _EMPTY_VALUES


def _last_line(text: str) -> str:
    for line in reversed((text or "").splitlines()):
        if line.strip():
            return line.strip()
    return ""


def _signal(kind: str, pattern: str, detail: str) -> dict:
    return {"kind": kind, "pattern": pattern, "detail": detail}


def detect_refusal(raw_output: str, summary: Optional[dict] = None) -> list[dict]:
    """Find refusal, question, and no-op signals in a worker's output.

    Returns a list of ``{kind, pattern, detail}`` dicts, one per distinct
    pattern matched. ``kind`` is one of :data:`REFUSAL`, :data:`QUESTION`,
    :data:`NO_OP`.

    Refusal and question signals block on their own (see :data:`HARD_SIGNALS`).
    No-op signals describe an *absence* of work, so they are reported but
    deferred to :func:`verify_evidence`, which can prove otherwise.
    """
    summary = summary or {}
    prose = _prose(raw_output or "")
    signals: list[dict] = []

    for pattern, label in _REFUSAL_PATTERNS:
        m = pattern.search(prose)
        if m:
            signals.append(_signal(REFUSAL, label, f"worker output says {m.group(0).strip()!r}"))

    for pattern, label in _QUESTION_PATTERNS:
        m = pattern.search(prose)
        if m:
            signals.append(_signal(QUESTION, label, f"worker output asks {m.group(0).strip()!r}"))

    # A worker whose last word is a question is still waiting on a decision,
    # whatever it exited with.
    tail = _last_line(prose)
    if tail.endswith("?"):
        signals.append(_signal(
            QUESTION, "output ends with a question",
            f"worker's final line is a question: {tail[:120]!r}",
        ))

    # ── No-op signals ───────────────────────────────────────────────────────
    created = _meaningful_items(summary.get("files_created"))
    modified = _meaningful_items(summary.get("files_modified"))
    if not created and not modified:
        signals.append(_signal(
            NO_OP, "zero files created and zero modified",
            "worker reported no files created and no files modified",
        ))

    commit_result = summary.get("commit_result")
    if _is_empty(commit_result):
        reported = str(commit_result).strip() if commit_result is not None else ""
        signals.append(_signal(
            NO_OP, "Commit Result: skipped",
            f"worker reported commit result as {reported or '(absent)'}",
        ))

    for pattern, label in _NO_OP_COMMIT_PATTERNS:
        m = pattern.search(prose)
        if m:
            signals.append(_signal(NO_OP, label, f"worker output says {m.group(0).strip()!r}"))

    return signals


# ── Which evidence a task must produce ──────────────────────────────────────

#: Task types whose deliverable is a live deployment rather than a diff.
_DEPLOY_TASK_TYPES = frozenset({"deploy", "deployment", "release"})

#: Matched against title + description. Deliberately verb-shaped: an "infra"
#: task that merely *mentions* deployment config should not be forced to prove
#: a live deployment, but "Deploy the scaffolded app" must.
#:
#: The trailing guard drops the noun sense of the word — "fix the deploy
#: script", "document the release process" are tasks *about* deployment
#: tooling, whose deliverable is a diff, not a running site.
_DEPLOY_TOOLING_NOUNS = (
    r"script|scripts|config|configs|configuration|pipeline|workflow|workflows|"
    r"step|steps|job|jobs|doc|docs|documentation|guide|note|notes|process|"
    r"checklist|runbook|key|keys|token|tokens|setting|settings"
)
_DEPLOY_INTENT = re.compile(
    r"\b(?:deploy|redeploy|ship|release|roll\s+out)(?:s|ed|ing)?\b(?!\w)"
    rf"(?!\s+(?:{_DEPLOY_TOOLING_NOUNS})\b)",
    re.I,
)


def required_evidence(task: Optional[dict], deploy_available: bool = True) -> list[str]:
    """Return the evidence kinds ``task`` must produce to count as complete.

    A deploy task proves itself with a responding deployment; everything else
    proves itself with an artifact (a file on disk or a commit in the remote).

    ``deploy_available`` is the caller's answer to "could a deployment happen at
    all in this environment?" (``AUTO_DEPLOY`` on, a Vercel token present). When
    it is False the runner never even attempts a deploy, so demanding deployment
    evidence would leave the task permanently blocked with no way to satisfy the
    gate — and an unsatisfiable gate is one somebody switches off, which is this
    bug by another route. The task still owes an artifact, so a refusal that
    produced nothing is caught either way.
    """
    task = task or {}
    task_type = str(task.get("type") or "").strip().lower()
    intent_text = f"{task.get('title') or ''}\n{task.get('description') or ''}"

    is_deploy = task_type in _DEPLOY_TASK_TYPES or bool(_DEPLOY_INTENT.search(intent_text))
    if is_deploy and deploy_available:
        return [EVIDENCE_DEPLOYMENT]
    return [EVIDENCE_ARTIFACT]


# ── Evidence verifiers ──────────────────────────────────────────────────────
# Each returns {"verified": bool, "detail": str}. Every one of them consults
# something outside the worker's summary; that is the whole point.


def _result(verified: bool, detail: str) -> dict:
    return {"verified": verified, "detail": detail}


def verify_files_evidence(summary: Optional[dict], repo_path: str) -> dict:
    """A file the worker claims it wrote must actually exist on disk."""
    summary = summary or {}
    claimed = _meaningful_items(summary.get("files_created")) + _meaningful_items(
        summary.get("files_modified")
    )
    if not claimed:
        return _result(False, "worker claimed no files created or modified")
    if not repo_path:
        return _result(False, "no repo path available to check claimed files against disk")

    found, missing = [], []
    for raw_path in claimed:
        rel = raw_path.lstrip("./")
        (found if os.path.exists(os.path.join(repo_path, rel)) else missing).append(raw_path)

    if not found:
        return _result(False, f"none of the {len(claimed)} claimed file(s) exist on disk: {', '.join(claimed[:5])}")
    detail = f"{len(found)} claimed file(s) exist on disk: {', '.join(found[:5])}"
    if missing:
        detail += f" (but {len(missing)} do not: {', '.join(missing[:5])})"
    return _result(True, detail)


def _default_git_runner(args: list[str], cwd: str) -> tuple[bool, str]:
    from tools.git_tools import _git

    r = _git(args, cwd)
    return bool(r.success), (r.output or "")


def verify_commit_evidence(
    commit: Optional[dict],
    repo_path: str,
    remote: str = "origin",
    *,
    git_runner: Optional[Callable[[list[str], str], tuple[bool, str]]] = None,
) -> dict:
    """A claimed commit must exist as an object *and* be in the expected remote.

    ``commit`` is the dict recorded by ``commit_push_merge_if_needed``
    (``{"sha", "nothing_to_commit", ...}`` from ``git_tools.commit_all``).

    ``nothing_to_commit`` is rejected outright: ``commit_all`` deliberately
    reports a clean tree as "landed" and returns the *existing* HEAD so the
    deploy path isn't skipped, which means that sha predates the task and
    proves nothing about it. That is exactly the sha ``ai-infra-03`` carried
    into its deploy — and the reason its PR create failed 422 with no commits
    between base and head.
    """
    commit = commit or {}
    git_runner = git_runner or _default_git_runner

    if commit.get("nothing_to_commit"):
        return _result(False, "no new commit — the tree was already clean, so HEAD predates this task")

    sha = str(commit.get("sha") or "").strip()
    if not sha:
        return _result(False, "no commit sha recorded")
    if not repo_path:
        return _result(False, f"no repo path available to verify commit {sha[:12]}")

    exists, _ = git_runner(["cat-file", "-e", f"{sha}^{{commit}}"], repo_path)
    if not exists:
        return _result(False, f"commit {sha[:12]} does not exist in {repo_path}")

    ok, output = git_runner(["branch", "-r", "--contains", sha], repo_path)
    branches = [b.strip() for b in (output or "").splitlines() if b.strip()]
    on_remote = [b for b in branches if b.split("/", 1)[0] == remote]
    if not ok or not on_remote:
        return _result(False, f"commit {sha[:12]} exists locally but is on no {remote}/ branch — it was never pushed")

    return _result(True, f"commit {sha[:12]} is in the remote on {', '.join(on_remote[:3])}")


def verify_merged_pr_evidence(merge_result: Optional[dict]) -> dict:
    """A successfully merged PR is artifact evidence in its own right.

    The GitHub merge API returning a sha is stronger proof than files on disk:
    GitHub confirmed the commit landed on main, even if the local working tree
    hasn't been fast-forwarded yet or the branch has already been deleted.
    """
    if not merge_result:
        return _result(False, "no merge result")
    if not merge_result.get("success"):
        return _result(False, f"PR merge was not successful: {merge_result.get('error') or merge_result.get('reason') or 'unknown'}")
    sha = str(merge_result.get("sha") or "").strip()
    if not sha:
        return _result(False, "merge result has no sha")
    pr_number = merge_result.get("pr_number") or merge_result.get("number")
    label = f"PR #{pr_number} " if pr_number else ""
    return _result(True, f"{label}merged with sha {sha[:12]}")


def _default_http_probe(url: str, timeout: float = 15.0) -> tuple[bool, str]:
    import requests

    try:
        resp = requests.get(url, timeout=timeout)
    except Exception as exc:  # network error → the URL did not answer
        return False, f"{type(exc).__name__}: {exc}"
    # A 4xx is still a live application answering; a 5xx is not.
    return resp.status_code < 500, f"HTTP {resp.status_code}"


def verify_deployment_evidence(
    deploy_result: Optional[dict],
    *,
    http_probe: Optional[Callable[[str], tuple[bool, str]]] = None,
) -> dict:
    """A deployment must have an id/URL, be READY, and answer a real request."""
    if not deploy_result:
        return _result(False, "no deploy result — nothing was deployed")

    http_probe = http_probe or _default_http_probe
    poll = deploy_result.get("poll") or {}
    deployment = poll.get("deployment") or {}
    deployment_id = deployment.get("uid") or deployment.get("id") or deploy_result.get("deployment_id")
    url = deploy_result.get("url") or deploy_result.get("deployment_url") or deployment.get("url")

    if not url and not deployment_id:
        return _result(False, "deploy result carries neither a deployment id nor a URL")

    if poll and not poll.get("ready"):
        state = poll.get("state") or "unknown"
        return _result(False, f"deployment {deployment_id or url} did not reach READY (state {state})")

    if not url:
        return _result(False, f"deployment {deployment_id} has no URL to probe")

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    ok, detail = http_probe(url)
    if not ok:
        return _result(False, f"deployment URL {url} did not answer a real request ({detail})")
    return _result(True, f"deployment URL {url} answered a real request ({detail})")


def verify_evidence(
    summary: Optional[dict] = None,
    *,
    repo_path: str = "",
    commit: Optional[dict] = None,
    deploy_result: Optional[dict] = None,
    merge_result: Optional[dict] = None,
    remote: str = "origin",
    git_runner: Optional[Callable[[list[str], str], tuple[bool, str]]] = None,
    http_probe: Optional[Callable[[str], tuple[bool, str]]] = None,
) -> dict:
    """Verify every evidence kind, returning ``{kind: {verified, detail}}``.

    :data:`EVIDENCE_ARTIFACT` is the disjunction of files, commit, and merged
    PR: source work counts however it landed.  A merged PR sha returned by
    GitHub is accepted as artifact evidence even when the working tree is clean
    and the feature branch has already been deleted (M4c.4).
    """
    files = verify_files_evidence(summary, repo_path)
    commit_ev = verify_commit_evidence(commit, repo_path, remote, git_runner=git_runner)
    merged_pr = verify_merged_pr_evidence(merge_result)
    deployment = verify_deployment_evidence(deploy_result, http_probe=http_probe)

    artifact_sources = [e for e in (files, commit_ev, merged_pr) if e["verified"]]
    if artifact_sources:
        artifact = _result(True, "; ".join(e["detail"] for e in artifact_sources))
    else:
        artifact = _result(
            False,
            f"{files['detail']}; {commit_ev['detail']}; {merged_pr['detail']}",
        )

    return {
        EVIDENCE_FILES: files,
        EVIDENCE_COMMIT: commit_ev,
        EVIDENCE_MERGED_PR: merged_pr,
        EVIDENCE_DEPLOYMENT: deployment,
        EVIDENCE_ARTIFACT: artifact,
    }


def evaluate_completion(
    summary: Optional[dict] = None,
    task: Optional[dict] = None,
    raw_output: str = "",
    *,
    repo_path: str = "",
    commit: Optional[dict] = None,
    deploy_result: Optional[dict] = None,
    merge_result: Optional[dict] = None,
    remote: str = "origin",
    deploy_available: bool = True,
    git_runner: Optional[Callable[[list[str], str], tuple[bool, str]]] = None,
    http_probe: Optional[Callable[[str], tuple[bool, str]]] = None,
) -> dict:
    """Decide whether a worker run may be scored complete.

    Returns::

        {
          "complete": bool,     # True only with verified evidence and no refusal
          "blocked":  bool,     # always `not complete` — this gate never fails a task
          "reasons":  list[str],# human-readable, one per blocking finding
          "signals":  list[dict],
          "evidence": dict,     # kind → {verified, detail}
          "required": list[str],
          "satisfied": list[str],
        }

    The verdict is ``blocked``, never ``failed``: a worker that refused or asked
    a question did not break anything, it left work undone, and a human (or a
    re-run with a better prompt) is what unblocks it.
    """
    signals = detect_refusal(raw_output, summary)
    evidence = verify_evidence(
        summary,
        repo_path=repo_path,
        commit=commit,
        deploy_result=deploy_result,
        merge_result=merge_result,
        remote=remote,
        git_runner=git_runner,
        http_probe=http_probe,
    )
    required = required_evidence(task, deploy_available=deploy_available)

    reasons: list[str] = []
    for sig in signals:
        if sig["kind"] in HARD_SIGNALS:
            reasons.append(f"{sig['kind']}: {sig['detail']}")

    satisfied = [kind for kind in required if evidence[kind]["verified"]]
    for kind in required:
        if kind not in satisfied:
            reasons.append(f"missing {kind} evidence: {evidence[kind]['detail']}")

    complete = not reasons
    return {
        "complete": complete,
        "blocked": not complete,
        "reasons": reasons,
        "signals": signals,
        "evidence": evidence,
        "required": required,
        "satisfied": satisfied,
    }


def guard_completion_evidence(
    summary: Optional[dict] = None,
    task: Optional[dict] = None,
    raw_output: str = "",
    context: str = "",
    merge_result: Optional[dict] = None,
    **kwargs,
) -> dict:
    """Run :func:`evaluate_completion` and log the verdict.

    Logs :data:`EVENT_VERIFIED` when the task earned its completion, or
    :data:`EVENT_MISSING` when it did not. A no-op signal that verified
    evidence overruled is logged separately as
    :data:`EVENT_NO_OP_OVERRIDDEN` — worth seeing, since it usually means a
    worker under-reported its own summary.
    """
    decision = evaluate_completion(summary, task, raw_output, merge_result=merge_result, **kwargs)
    task_id = (task or {}).get("id")

    if decision["complete"]:
        overridden = [s for s in decision["signals"] if s["kind"] == NO_OP]
        if overridden:
            log_event(EVENT_NO_OP_OVERRIDDEN, {
                "task_id": task_id,
                "context": context,
                "signals": [s["pattern"] for s in overridden],
                "evidence": [decision["evidence"][k]["detail"] for k in decision["satisfied"]],
                "message": (
                    "Worker's summary reported no work, but the evidence says "
                    "otherwise; completing on the evidence."
                ),
            }, task_id=task_id)
        else:
            log_event(EVENT_VERIFIED, {
                "task_id": task_id,
                "context": context,
                "required": decision["required"],
                "evidence": [decision["evidence"][k]["detail"] for k in decision["satisfied"]],
            }, task_id=task_id)
        return decision

    log_event(EVENT_MISSING, {
        "task_id": task_id,
        "task_title": (task or {}).get("title"),
        "context": context,
        "reasons": decision["reasons"],
        "signals": [{"kind": s["kind"], "pattern": s["pattern"]} for s in decision["signals"]],
        "required": decision["required"],
        "satisfied": decision["satisfied"],
        "message": (
            "Worker exited successfully but produced no verifiable evidence of "
            "the work; marking blocked rather than complete."
        ),
    }, task_id=task_id)
    return decision
