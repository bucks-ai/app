"""Unit tests for the threshold calibration analysis.

Runs standalone (no pytest dependency):

    python tests/test_threshold_calibration.py

Covers ``tools/threshold_calibration.py`` against synthetic event streams, so
the summaries are verified on inputs whose answers are known by construction
rather than against whatever happens to be in the live log.
"""
import json
import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.threshold_calibration import (
    analyze,
    analyze_log,
    count_above,
    iter_events,
    percentile,
    render_measurements,
    summarize,
)


def _event(event_type, payload, timestamp="2026-07-01T00:00:00"):
    return {"event_type": event_type, "timestamp": timestamp, "payload": payload}


def _worker(task_id, elapsed, success=True, timestamp="2026-07-01T00:00:00"):
    return _event("worker_finished", {
        "worker": "claude", "task_id": task_id,
        "elapsed_seconds": elapsed, "success": success,
    }, timestamp)


def _loaded(task_id, task_type, timestamp="2026-07-01T00:00:00"):
    return _event("task_loaded", {"task": {"id": task_id, "type": task_type}}, timestamp)


# ---------------------------------------------------------------------------
# percentile / summarize
# ---------------------------------------------------------------------------

def test_percentile_is_nearest_rank():
    values = list(range(1, 101))  # 1..100
    assert percentile(values, 0.0) == 1
    assert percentile(values, 1.0) == 100
    # Nearest-rank returns an actual observation, never an interpolated value.
    assert percentile(values, 0.95) in values


def test_percentile_of_empty_is_none():
    assert percentile([], 0.95) is None


def test_summarize_reports_sample_count_and_bounds():
    s = summarize([10, 20, 30, 40, 50])
    assert s["n"] == 5
    assert s["min"] == 10
    assert s["max"] == 50
    assert s["median"] == 30


def test_summarize_empty_is_all_none_with_zero_n():
    s = summarize([])
    assert s["n"] == 0
    assert all(s[k] is None for k in ("min", "median", "p90", "p95", "p99", "max"))


def test_summarize_single_sample():
    s = summarize([42.0])
    assert s["n"] == 1
    assert s["median"] == s["p95"] == s["max"] == 42.0


# ---------------------------------------------------------------------------
# Worker duration analysis
# ---------------------------------------------------------------------------

def test_worker_durations_grouped_by_task_type():
    events = [
        _loaded("a", "backend"), _worker("a", 100),
        _loaded("b", "backend"), _worker("b", 300),
        _loaded("c", "frontend"), _worker("c", 50),
    ]
    result = analyze(events)
    assert result["worker_by_type"]["backend"]["n"] == 2
    assert result["worker_by_type"]["frontend"]["n"] == 1
    assert result["worker_overall"]["n"] == 3


def test_worker_without_elapsed_seconds_is_excluded_not_zeroed():
    """Pre-instrumentation events carry no duration; counting them as 0
    would drag every percentile down and understate the real thresholds."""
    events = [
        _loaded("a", "backend"),
        _event("worker_finished", {"worker": "claude", "task_id": "a", "success": True}),
        _worker("b", 600),
    ]
    result = analyze(events)
    assert result["worker_overall"]["n"] == 1
    assert result["worker_overall"]["median"] == 600


def test_duplicate_worker_finished_events_counted_once():
    """The dispatch path logs worker_finished twice for some runs."""
    events = [
        _loaded("a", "backend"),
        _worker("a", 300, timestamp="2026-07-01T00:00:00.111111"),
        _worker("a", 300, timestamp="2026-07-01T00:00:00.999999"),
    ]
    assert analyze(events)["worker_overall"]["n"] == 1


def test_unmapped_task_id_falls_back_to_unknown_type():
    result = analyze([_worker("orphan", 120)])
    assert result["worker_by_type"]["unknown"]["n"] == 1


def test_success_and_failure_are_summarized_separately():
    events = [_worker("a", 100, True), _worker("b", 900, False)]
    result = analyze(events)
    assert result["worker_success"]["n"] == 1
    assert result["worker_failed"]["n"] == 1
    assert result["worker_failed"]["max"] == 900


def test_runs_at_the_cli_ceiling_are_flagged_as_censored():
    """A run that ends at the ceiling was killed by it — the true duration is
    unknown and longer, so it must not be read as an observed maximum."""
    events = [_worker("a", 300), _worker("b", 1800.3), _worker("c", 1795.0)]
    result = analyze(events, censor_at=1800)
    assert result["worker_censored_n"] == 2
    assert result["worker_censored_at"] == 1800


def test_no_censoring_reported_without_a_known_ceiling():
    result = analyze([_worker("a", 1800.3)])
    assert result["worker_censored_n"] == 0


# ---------------------------------------------------------------------------
# PR check analysis
# ---------------------------------------------------------------------------

def test_pr_check_completion_durations():
    events = [
        _event("pr_checks_completed", {"sha": "aaa", "elapsed": 80.0, "polls": 4}),
        _event("pr_checks_completed", {"sha": "bbb", "elapsed": 680.0, "polls": 34}),
    ]
    result = analyze(events)
    assert result["pr_checks_completed"]["n"] == 2
    assert result["pr_checks_completed"]["max"] == 680.0


def test_duplicate_pr_checks_completed_counted_once():
    dup = _event("pr_checks_completed", {"sha": "aaa", "elapsed": 80.0})
    assert analyze([dup, dict(dup)])["pr_checks_completed"]["n"] == 1


def test_pr_check_timeouts_counted_separately_from_completions():
    events = [
        _event("pr_checks_completed", {"sha": "aaa", "elapsed": 80.0}),
        _event("pr_checks_timeout", {"sha": "bbb", "elapsed": 894.0, "timeout": 900}),
    ]
    result = analyze(events)
    assert result["pr_checks_completed"]["n"] == 1
    assert result["pr_checks_timeout_n"] == 1


def test_registration_latency_uses_first_poll_with_a_check_run():
    """PR_CHECKS_EMPTY_GRACE_S must cover the wait until checks appear, so
    only the first non-empty tick per sha counts."""
    events = [
        _event("pr_checks_poll_tick", {"sha": "aaa", "poll": 1, "elapsed": 0.3, "total": 0}),
        _event("pr_checks_poll_tick", {"sha": "aaa", "poll": 2, "elapsed": 20.7, "total": 2}),
        _event("pr_checks_poll_tick", {"sha": "aaa", "poll": 3, "elapsed": 41.0, "total": 2}),
    ]
    result = analyze(events)
    assert result["pr_checks_registration"]["n"] == 1
    assert result["pr_checks_registration"]["max"] == 20.7


def test_sha_that_never_registers_a_check_is_not_a_latency_sample():
    events = [
        _event("pr_checks_poll_tick", {"sha": "aaa", "poll": 1, "elapsed": 0.3, "total": 0}),
        _event("pr_checks_poll_tick", {"sha": "aaa", "poll": 2, "elapsed": 20.5, "total": 0}),
    ]
    assert analyze(events)["pr_checks_registration"]["n"] == 0


# ---------------------------------------------------------------------------
# End-to-end task duration and session spans
# ---------------------------------------------------------------------------

def test_end_to_end_duration_measured_from_load_to_completion():
    events = [
        _loaded("a", "backend", "2026-07-01T00:00:00"),
        _event("task_completed", {"task_id": "a"}, "2026-07-01T00:41:06"),
    ]
    result = analyze(events)
    assert result["task_end_to_end_minutes"]["n"] == 1
    assert result["task_end_to_end_minutes"]["max"] == 41.1


def test_zero_length_task_pairs_are_excluded():
    """Dry-run and skipped tasks complete at their load timestamp and measure
    nothing about real durations."""
    events = [
        _loaded("a", "backend", "2026-07-01T00:00:00"),
        _event("task_completed", {"task_id": "a"}, "2026-07-01T00:00:00"),
    ]
    assert analyze(events)["task_end_to_end_minutes"]["n"] == 0


def test_completion_matched_to_most_recent_prior_load():
    """A requeued task is loaded twice; the duration is from the retry, not
    from the original dispatch an hour earlier."""
    events = [
        _loaded("a", "backend", "2026-07-01T00:00:00"),
        _loaded("a", "backend", "2026-07-01T01:00:00"),
        _event("task_completed", {"task_id": "a"}, "2026-07-01T01:10:00"),
    ]
    assert analyze(events)["task_end_to_end_minutes"]["max"] == 10.0


def test_pair_spanning_a_stopped_loop_is_excluded():
    """A completion logged a day later, after the loop was restarted, is not
    a 31-hour task — unfiltered it was the largest "sample" in the real log."""
    events = [
        _loaded("a", "backend", "2026-07-01T00:00:00"),
        _loaded("b", "backend", "2026-07-01T00:20:00"),
        _event("task_completed", {"task_id": "b"}, "2026-07-01T00:30:00"),
        _event("task_completed", {"task_id": "a"}, "2026-07-02T08:00:00"),
    ]
    result = analyze(events)
    assert result["task_end_to_end_minutes"]["n"] == 1
    assert result["task_end_to_end_minutes"]["max"] == 10.0


def test_long_but_uninterrupted_task_is_kept():
    """A worker emits nothing for 40 minutes; silence inside a window is
    normal and must not disqualify the sample."""
    events = [
        _loaded("a", "test", "2026-07-01T00:00:00"),
        _event("task_completed", {"task_id": "a"}, "2026-07-01T00:41:06"),
    ]
    assert analyze(events)["task_end_to_end_minutes"]["max"] == 41.1


def test_session_spans_split_on_long_silence():
    """Idle time between loop sessions is not runtime MAX_RUNTIME_MINUTES
    needs to cover."""
    events = [_event("noop", {}, f"2026-07-01T00:0{i}:00") for i in range(7)]
    events += [_event("noop", {}, f"2026-07-01T09:0{i}:00") for i in range(7)]
    result = analyze(events)
    assert result["session_span_minutes"]["n"] == 2
    assert result["session_span_minutes"]["max"] == 6.0


def test_short_bursts_are_not_counted_as_sessions():
    """A couple of events is a CLI invocation, not a loop session."""
    events = [_event("noop", {}, "2026-07-01T00:00:00"),
              _event("noop", {}, "2026-07-01T00:01:00")]
    assert analyze(events)["session_span_minutes"]["n"] == 0


# ---------------------------------------------------------------------------
# count_above — the false-timeout rate
# ---------------------------------------------------------------------------

def test_count_above_measures_successful_runs_over_the_threshold():
    events = [_worker("a", 300), _worker("b", 600), _worker("c", 900)]
    assert count_above(events, 570) == (2, 3)


def test_count_above_ignores_failed_runs_by_default():
    """The useful figure is how often the guard mislabels *healthy* work."""
    events = [_worker("a", 900, success=False), _worker("b", 300, success=True)]
    assert count_above(events, 570) == (0, 1)


def test_count_above_can_include_failures():
    events = [_worker("a", 900, success=False), _worker("b", 300, success=True)]
    assert count_above(events, 570, success_only=False) == (1, 2)


# ---------------------------------------------------------------------------
# Log reading and rendering
# ---------------------------------------------------------------------------

def test_iter_events_skips_malformed_lines():
    """The runner appends while this reads; a truncated final line must not
    abort the analysis."""
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
        fh.write(json.dumps(_worker("a", 100)) + "\n")
        fh.write("{not json\n")
        fh.write("\n")
        fh.write(json.dumps(_worker("b", 200)) + "\n")
        path = fh.name
    try:
        assert len(list(iter_events(path))) == 2
        assert analyze_log(path)["worker_overall"]["n"] == 2
    finally:
        os.unlink(path)


def test_missing_log_file_yields_empty_analysis():
    result = analyze_log("/nonexistent/runs.jsonl")
    assert result["worker_overall"]["n"] == 0
    assert result["window"]["events_read"] == 0


def test_render_measurements_includes_sample_counts():
    events = [_loaded("a", "backend"), _worker("a", 300),
              _event("pr_checks_completed", {"sha": "x", "elapsed": 80.0})]
    text = render_measurements(analyze(events, censor_at=1800))
    assert "## Measurements" in text
    assert "backend" in text
    assert "| n |" in text, "every table must expose its sample count"


def test_render_measurements_survives_an_empty_log():
    text = render_measurements(analyze([]))
    assert "## Measurements" in text
    assert "—" in text, "empty summaries render as em dashes, not crashes"


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_percentile_is_nearest_rank,
        test_percentile_of_empty_is_none,
        test_summarize_reports_sample_count_and_bounds,
        test_summarize_empty_is_all_none_with_zero_n,
        test_summarize_single_sample,
        test_worker_durations_grouped_by_task_type,
        test_worker_without_elapsed_seconds_is_excluded_not_zeroed,
        test_duplicate_worker_finished_events_counted_once,
        test_unmapped_task_id_falls_back_to_unknown_type,
        test_success_and_failure_are_summarized_separately,
        test_runs_at_the_cli_ceiling_are_flagged_as_censored,
        test_no_censoring_reported_without_a_known_ceiling,
        test_pr_check_completion_durations,
        test_duplicate_pr_checks_completed_counted_once,
        test_pr_check_timeouts_counted_separately_from_completions,
        test_registration_latency_uses_first_poll_with_a_check_run,
        test_sha_that_never_registers_a_check_is_not_a_latency_sample,
        test_end_to_end_duration_measured_from_load_to_completion,
        test_zero_length_task_pairs_are_excluded,
        test_completion_matched_to_most_recent_prior_load,
        test_pair_spanning_a_stopped_loop_is_excluded,
        test_long_but_uninterrupted_task_is_kept,
        test_session_spans_split_on_long_silence,
        test_short_bursts_are_not_counted_as_sessions,
        test_count_above_measures_successful_runs_over_the_threshold,
        test_count_above_ignores_failed_runs_by_default,
        test_count_above_can_include_failures,
        test_iter_events_skips_malformed_lines,
        test_missing_log_file_yields_empty_analysis,
        test_render_measurements_includes_sample_counts,
        test_render_measurements_survives_an_empty_log,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
