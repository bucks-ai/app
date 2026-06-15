"""Deterministic context compression helpers for runner state messages."""
from typing import Any

try:
    import tiktoken
except Exception:  # pragma: no cover - fallback is covered by behavior tests
    tiktoken = None


_FALLBACK_CHARS_PER_TOKEN = 4
_DEFAULT_ENCODING = "cl100k_base"


def _encoding():
    if tiktoken is None:
        return None
    try:
        return tiktoken.get_encoding(_DEFAULT_ENCODING)
    except Exception:
        return None


def estimate_tokens(text: Any) -> int:
    """Estimate token count for text, using tiktoken when available."""
    value = "" if text is None else str(text)
    if not value:
        return 0

    enc = _encoding()
    if enc is not None:
        return len(enc.encode(value))

    return max(1, (len(value) + _FALLBACK_CHARS_PER_TOKEN - 1) // _FALLBACK_CHARS_PER_TOKEN)


def message_token_count(message: dict) -> int:
    """Estimate tokens for a chat-style message, including role overhead."""
    role = message.get("role", "")
    content = message.get("content", "")
    return estimate_tokens(role) + estimate_tokens(content) + 4


def messages_token_count(messages: list[dict]) -> int:
    return sum(message_token_count(message) for message in messages)


def _clean_content(value: Any, max_chars: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _compression_notice(
    *,
    dropped_messages: int,
    dropped_tokens: int,
    summary_digest: str | None,
    max_summary_chars: int,
) -> dict:
    lines = [
        "Runner context compressed.",
        f"Omitted earlier messages: {dropped_messages}.",
        f"Approximate omitted tokens: {dropped_tokens}.",
    ]
    if summary_digest:
        lines.extend(["Latest run summary:", _clean_content(summary_digest, max_summary_chars)])
    return {"role": "system", "content": "\n".join(lines)}


def compress_messages(
    messages: list[dict],
    *,
    max_tokens: int,
    keep_recent: int = 4,
    summary_digest: str | None = None,
    max_summary_chars: int = 1200,
) -> dict:
    """Return messages compacted under a soft token ceiling.

    Compression is deterministic and local: older messages are replaced by one
    synthetic system notice while the most recent messages stay verbatim. If the
    preserved tail alone exceeds ``max_tokens``, the function still preserves it
    because truncating the active worker exchange can change behavior.
    """
    if not messages:
        return {
            "messages": [],
            "compressed": False,
            "tokens_before": 0,
            "tokens_after": 0,
            "messages_before": 0,
            "messages_after": 0,
            "dropped_messages": 0,
        }

    tokens_before = messages_token_count(messages)
    if max_tokens <= 0 or tokens_before <= max_tokens:
        return {
            "messages": list(messages),
            "compressed": False,
            "tokens_before": tokens_before,
            "tokens_after": tokens_before,
            "messages_before": len(messages),
            "messages_after": len(messages),
            "dropped_messages": 0,
        }

    keep_count = max(0, min(keep_recent, len(messages)))
    kept_tail = messages[-keep_count:] if keep_count else []
    dropped = messages[: len(messages) - keep_count] if keep_count else messages
    dropped_tokens = messages_token_count(dropped)
    notice = _compression_notice(
        dropped_messages=len(dropped),
        dropped_tokens=dropped_tokens,
        summary_digest=summary_digest,
        max_summary_chars=max_summary_chars,
    )
    compressed = [notice] + list(kept_tail)

    return {
        "messages": compressed,
        "compressed": True,
        "tokens_before": tokens_before,
        "tokens_after": messages_token_count(compressed),
        "messages_before": len(messages),
        "messages_after": len(compressed),
        "dropped_messages": len(dropped),
    }
