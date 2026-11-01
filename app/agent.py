"""Router agent, run logging and small helpers for the study assistant.
Nothing here depends on Streamlit, so it can be reused by a backend later."""
import json
import logging
import os
import re
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

from google.genai import types

from llm import MODELS_TO_TRY, client

LOG_DIR = os.getenv("AGENT_LOG_DIR", "logs")
LOG_FILE = os.path.join(LOG_DIR, "agent_runs.jsonl")

logger = logging.getLogger("study_agent")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# The tools the router can choose from. "mode" is how the app runs each tool.
TOOLS = {
    "answer_question": {
        "mode": "qa",
        "description": "a direct question about a concept or definition",
    },
    "solve_problem": {
        "mode": "solve",
        "description": "the student wants a step-by-step solution, or refers to an exam question such as Q3 from 2023",
    },
    "teach_topic": {
        "mode": "learn",
        "description": "the student wants to learn a topic: a lesson with theory, an example and practice",
    },
    "make_quiz": {
        "mode": "quiz",
        "description": "the student wants a quiz, MCQs, or to be tested on a topic",
    },
    "find_past_questions": {
        "mode": "past",
        "description": "the student wants past or previous-year paper questions on a topic",
    },
}

ROUTER_PROMPT = """
You are the router agent of a study assistant. Choose exactly ONE tool for the student's message.

Tools:
{tools}

Return ONLY JSON like {{"tool": "<tool name>", "reason": "<one short sentence>"}}.

Student message:
{message}
"""

SOLVE_WORDS = ("solve", "calculate", "compute", "derive", "how do i", "step by step", "step-by-step", "normalize")
PAST_WORDS = ("past question", "previous year", "past paper", "previous paper", "question paper", "pyq", "old paper")
QUIZ_WORDS = ("quiz", "test me", "mcq", "multiple choice", "question me", "test my")
TEACH_WORDS = ("teach me", "lesson", "learn about", "learn ", "from scratch", "in detail", "walk me through")


def extract_marks(message: str):
    """Pick up '5 marks' style hints. Returns '2', '5', '10' or None."""
    match = re.search(r"\b(\d{1,2})\s*[- ]?marks?\b", message.lower())
    return match.group(1) if match and match.group(1) in ("2", "5", "10") else None


def route_by_rules(message: str) -> dict:
    """Simple keyword router, used when Gemini is unavailable or switched off."""
    text = message.lower()
    solving = any(w in text for w in SOLVE_WORDS) or re.search(r"\bq\s?\d+\b", text)
    if any(w in text for w in PAST_WORDS) and not solving:
        tool, reason = "find_past_questions", "The message asks for past paper questions."
    elif any(w in text for w in QUIZ_WORDS):
        tool, reason = "make_quiz", "The message asks to be tested."
    elif solving:
        tool, reason = "solve_problem", "The message asks to solve a problem."
    elif any(w in text for w in TEACH_WORDS):
        tool, reason = "teach_topic", "The message asks to learn a topic."
    else:
        tool, reason = "answer_question", "Default: a direct question."
    return {"tool": tool, "reason": reason, "marks": extract_marks(message) if tool == "solve_problem" else None}


def _call_router(prompt: str) -> str:
    """One short Gemini call that returns JSON. Tries each model once."""
    config = types.GenerateContentConfig(temperature=0, max_output_tokens=200, response_mime_type="application/json")
    last_error = None
    for model_name in MODELS_TO_TRY:
        try:
            response = client.models.generate_content(model=model_name, contents=prompt, config=config)
            if response.text:
                return response.text
        except Exception as e:  # try the next model
            last_error = e
    raise Exception(f"Router could not reach Gemini: {last_error}")


def route(message: str, use_llm: bool = True) -> dict:
    """Decide which tool should handle the message.
    Returns {"tool", "reason", "marks", "source"}; source is 'llm' or 'rules'."""
    if use_llm:
        try:
            tools = "\n".join(f"- {name}: {info['description']}" for name, info in TOOLS.items())
            raw = _call_router(ROUTER_PROMPT.format(tools=tools, message=message))
            data = json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip()))
            tool = data.get("tool")
            if tool not in TOOLS:
                raise ValueError(f"unknown tool {tool!r}")
            return {
                "tool": tool,
                "reason": str(data.get("reason", "")).strip(),
                "marks": extract_marks(message) if tool == "solve_problem" else None,
                "source": "llm",
            }
        except Exception as e:
            logger.warning("Router fell back to rules: %s", e)
    result = route_by_rules(message)
    result["source"] = "rules"
    return result


class AgentRun:
    """Records every step of one request, and writes a log line when it finishes."""

    def __init__(self, message: str, ui_mode: str):
        self.id = uuid.uuid4().hex[:8]
        self.message = message
        self.ui_mode = ui_mode
        self.tool = None
        self.steps = []
        self.status = "ok"
        self.error = None
        self._start = time.time()

    @contextmanager
    def step(self, agent: str, action: str, detail: str = ""):
        record = {"agent": agent, "action": action, "detail": detail, "status": "ok", "ms": 0}
        started = time.time()
        try:
            yield record
        except Exception as e:
            record["status"] = "error"
            record["detail"] = f"{type(e).__name__}: {e}"
            self.status, self.error = "error", record["detail"]
            raise
        finally:
            record["ms"] = int((time.time() - started) * 1000)
            self.steps.append(record)

    def track_stream(self, agent: str, action: str, stream, detail: str = ""):
        """Wrap a streamed answer so its timing and any error are recorded when it ends."""
        record = {"agent": agent, "action": action, "detail": detail, "status": "ok", "ms": 0}
        started = time.time()

        def wrapped():
            try:
                for piece in stream:
                    yield piece
            except Exception as e:
                record["status"] = "error"
                record["detail"] = f"{type(e).__name__}: {e}"
                self.status, self.error = "error", record["detail"]
                raise
            finally:
                record["ms"] = int((time.time() - started) * 1000)
                self.steps.append(record)

        return wrapped()

    def finish(self):
        entry = {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "run_id": self.id,
            "ui_mode": self.ui_mode,
            "tool": self.tool,
            "message": self.message[:300],
            "status": self.status,
            "error": self.error,
            "total_ms": int((time.time() - self._start) * 1000),
            "steps": self.steps,
        }
        logger.info("run %s tool=%s status=%s total_ms=%s", self.id, self.tool, self.status, entry["total_ms"])
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning("Could not write the run log: %s", e)
        return entry


def check_citations(answer: str, n_sources: int):
    """Light reviewer: do the [n] citations point at real sources? Returns (ok, message)."""
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", answer or "")}
    if not cited:
        return False, "No citations found in the answer."
    bad = sorted(n for n in cited if n < 1 or n > n_sources)
    if bad:
        return False, f"Cites sources that do not exist: {bad}."
    return True, f"Cites {len(cited)} of {n_sources} sources."


def friendly_error(error: Exception) -> str:
    """Turn a raw API error into a message a student can act on."""
    text = str(error)
    if "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower():
        return "Gemini is rate-limited right now. Please wait a minute and try again."
    if "503" in text or "UNAVAILABLE" in text:
        return "Gemini is busy at the moment. Please try again in a few seconds."
    if "API key" in text or "API_KEY" in text or "401" in text or "403" in text:
        return "The Gemini API key is missing or not accepted. Check GEMINI_API_KEY in .env or the app secrets."
    return f"Something went wrong while generating the answer: {text[:200]}"
