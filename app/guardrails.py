"""Guardrails: input validation, prompt-injection checks, rate limiting and a fallback answer.
Plain Python with no Streamlit or FastAPI imports, so the app, the API and the tests share it."""
import os
import re
import time
from collections import defaultdict, deque

MAX_MESSAGE_LENGTH = 2000

# Phrases that try to change the assistant's instructions instead of asking a study question.
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+)?(the\s+)?(previous|above|prior|earlier)\s+(instructions?|prompts?|rules?)",
    r"disregard\s+(all\s+|any\s+)?(the\s+)?(previous|above|prior|earlier)",
    r"forget\s+(everything|all)\s+(you|i)\s+(were|was|have been)\s+told",
    r"(reveal|show|print|repeat|tell\s+me)\s+(me\s+)?(your|the)\s+(system|hidden|initial|secret)\s+(prompt|instructions?)",
    r"you\s+are\s+now\s+(in\s+)?(dan|developer\s+mode|an?\s+unrestricted)",
    r"act\s+as\s+(an?\s+)?(unrestricted|jailbroken|uncensored)",
    r"(override|bypass)\s+(your|the)\s+(safety|rules|guardrails|instructions)",
]
_INJECTION = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class GuardrailError(ValueError):
    """The message is rejected. The text is safe to show to the student."""


def looks_like_injection(text: str) -> bool:
    return any(p.search(text) for p in _INJECTION)


def clean_text(text: str) -> str:
    """Remove control characters and collapse long runs of blank lines."""
    text = _CONTROL_CHARS.sub("", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text.strip()


def check_message(message) -> str:
    """Validate and clean a student's message. Returns the cleaned text or raises GuardrailError."""
    if not isinstance(message, str) or not message.strip():
        raise GuardrailError("Please enter a question or topic first.")
    cleaned = clean_text(message)
    if not cleaned:
        raise GuardrailError("Please enter a question or topic first.")
    if len(cleaned) > MAX_MESSAGE_LENGTH:
        raise GuardrailError(f"That message is too long. Please keep it under {MAX_MESSAGE_LENGTH} characters.")
    if looks_like_injection(cleaned):
        raise GuardrailError("That looks like an attempt to change my instructions. Please ask a study question instead.")
    return cleaned


def filter_context(docs):
    """Drop retrieved chunks that contain instruction-like text (an uploaded file could hide one).
    Returns (safe_docs, number_skipped)."""
    safe = [d for d in docs if not looks_like_injection(d.page_content)]
    return safe, len(docs) - len(safe)


class RateLimiter:
    """Allow at most max_calls per key in any window of per_seconds (kept in memory)."""

    def __init__(self, max_calls=None, per_seconds=60):
        self.max_calls = max_calls or int(os.getenv("RATE_LIMIT_PER_MIN", "30"))
        self.per_seconds = per_seconds
        self._calls = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        calls = self._calls[key]
        while calls and now - calls[0] > self.per_seconds:
            calls.popleft()
        if len(calls) >= self.max_calls:
            return False
        calls.append(now)
        return True


def fallback_answer(docs, label_for, reason="The AI model is unavailable right now.") -> str:
    """What to show when Gemini fails: the most relevant passages from the student's own material."""
    if not docs:
        return f"{reason} Please try again in a moment."
    lines = [f"{reason} Here are the most relevant passages from your material instead:", ""]
    for i, doc in enumerate(docs[:4], 1):
        text = " ".join(doc.page_content.split())
        excerpt = text[:350] + ("..." if len(text) > 350 else "")
        lines.append(f"**[{i}] {label_for(doc)}**")
        lines.append(f"> {excerpt}")
        lines.append("")
    return "\n".join(lines).strip()
