"""Strategic decision gate.

After completing a configurable batch of tasks, the runner pauses and writes a
human-readable summary to ``outbox/`` for strategic review.  The loop only
resumes once the operator creates an approval file in ``inbox/``.

This gives human operators periodic checkpoints to redirect or halt autonomous
work before the runner commits to too large a body of changes — especially
useful for long-running multi-task sessions where scope creep or strategic
drift is a concern.

Setting ``strategic_pause_interval`` to 0 (the default) disables the gate
entirely.  Setting it to N pauses after every N completed task loops.

The decision logic is pure (no I/O, no state mutation) so it is unit-testable
in isolation; the graph node in ``graph.run_strategic_gate`` handles file I/O
and state mutation around these helpers.
"""

STRATEGIC_GATE_STOP = "awaiting_strategic_review"


def evaluate_strategic_gate(
    tasks_since_gate: int,
    strategic_pause_interval: int,
) -> dict:
    """Decide whether the strategic gate should fire.

    Args:
        tasks_since_gate:         Number of task loops completed since the last
                                  gate (or since the session started).
        strategic_pause_interval: How many tasks between each gate pause.
                                  ``<= 0`` disables the gate.

    Returns a dict with:
        - ``tasks_since_gate``  — Updated counter (reset to 0 when triggered,
                                  otherwise incremented by 1).
        - ``triggered``         — True when the interval was just reached.
        - ``blocked``           — True when the loop should pause.
        - ``stop_reason``       — ``STRATEGIC_GATE_STOP`` when blocked, else None.
    """
    if strategic_pause_interval <= 0:
        return {
            "tasks_since_gate": tasks_since_gate + 1,
            "triggered": False,
            "blocked": False,
            "stop_reason": None,
        }

    new_count = tasks_since_gate + 1
    triggered = new_count >= strategic_pause_interval

    return {
        "tasks_since_gate": 0 if triggered else new_count,
        "triggered": triggered,
        "blocked": triggered,
        "stop_reason": STRATEGIC_GATE_STOP if triggered else None,
    }


def format_review_file(
    loop_count: int,
    tasks_since_gate: int,
    summary_digest: str,
    inbox_filename: str,
) -> str:
    """Build the human-readable strategic review request written to ``outbox/``."""
    lines = [
        f"# Strategic Review Required — loop: {loop_count}",
        "",
        f"The runner has completed {tasks_since_gate} task(s) since the last strategic review.",
        "Please review the recent work and decide whether to continue.",
        "",
        "To resume the runner, create this file (any content):",
        "",
        f"    inbox/{inbox_filename}",
        "",
    ]
    if summary_digest:
        lines += [
            "## Last task summary",
            "",
            summary_digest,
            "",
        ]
    lines += [
        "## How to resume",
        "",
        f"Once you have reviewed, create inbox/{inbox_filename}.",
        "The runner will resume from the next queued task.",
        "",
        "To halt the runner instead, simply do not create the file.",
        "The runner will remain stopped until manually restarted.",
    ]
    return "\n".join(lines) + "\n"
