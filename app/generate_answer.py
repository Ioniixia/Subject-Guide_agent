"""Gemini answer generation that knows which file each chunk came from.
Reuses the client and model list from llm.py, so llm.py does not need to change."""
import json
import re
import time

from google.genai import types

from llm import MODELS_TO_TRY, client
from prompts import MARKS_GUIDE, MODES, PRACTICE_ANSWERS_INSTRUCTIONS, QUIZ_INSTRUCTIONS


def _digits(value) -> str:
    """'Q3', 3 and '3' all become '3'."""
    return re.sub(r"\D", "", str(value)) if value is not None else ""


def describe_source(doc) -> str:
    meta = doc.metadata or {}
    name = meta.get("source", "unknown source")
    name = str(name).replace("\\", "/").split("/")[-1]
    label = f"{name} ({meta['source_type']})" if meta.get("source_type") else name
    if meta.get("chapter"):
        label += f", chapter: {meta['chapter']}"

    question_no = _digits(meta.get("question_no"))
    if meta.get("source_type") == "question_paper" or question_no:
        parts = []
        if meta.get("year"):
            parts.append(str(meta["year"]))
        if question_no:
            parts.append(f"Q{question_no}")
        if _digits(meta.get("marks")):
            parts.append(f"{_digits(meta['marks'])} marks")
        if parts:
            label += ", " + ", ".join(parts)

    if meta.get("slide") is not None:
        label += f", slide {meta['slide']}"
    elif isinstance(meta.get("page"), int) and not question_no:
        label += f", page {meta['page'] + 1}"  # PDF pages are counted from 0
    return label


def _format_context(docs) -> str:
    if not docs:
        return "No context provided."
    return "\n\n---\n\n".join(
        f"[{i}] Source: {describe_source(d)}\n{d.page_content}" for i, d in enumerate(docs, 1)
    )


def build_prompt(question: str, docs, mode: str = "qa", marks: str | None = None) -> str:
    instructions = MODES[mode]["instructions"]
    if mode == "solve" and marks:
        if marks in MARKS_GUIDE:
            instructions += "\n" + MARKS_GUIDE[marks] + "\n"
        elif marks.isdigit():
            instructions += f"\nThe problem is worth {marks} marks: size the answer to match.\n"
    label = {"qa": "Student Question", "solve": "Problem to Solve", "learn": "Topic to Teach"}[mode]
    return f"""
You are an expert AI Academic Assistant & Subject Guide.
{instructions}
### Reference Materials:
{_format_context(docs)}

### {label}:
{question}
"""


def _stream(prompt: str, max_tokens: int):
    config = types.GenerateContentConfig(temperature=0.3, max_output_tokens=max_tokens)
    last_error = None

    for model_name in MODELS_TO_TRY:
        for _ in range(2):
            started = False
            try:
                for piece in client.models.generate_content_stream(
                    model=model_name, contents=prompt, config=config
                ):
                    if piece.text:
                        started = True
                        yield piece.text
                return
            except Exception as e:
                if started:
                    raise
                last_error = e
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    time.sleep(2)
                    continue
                break

    raise Exception(f"All Gemini models failed. Last error: {last_error}")


def generate_answer(question: str, docs, mode: str = "qa", marks: str | None = None):
    """Yield the answer piece by piece (use with st.write_stream)."""
    return _stream(build_prompt(question, docs, mode, marks), MODES[mode]["max_tokens"])


def generate_practice_answers(topic: str, docs, lesson_text: str):
    """Yield answers to the practice questions at the end of a lesson."""
    prompt = f"""
You are an expert AI Academic Assistant & Subject Guide.
{PRACTICE_ANSWERS_INSTRUCTIONS}
### Reference Materials:
{_format_context(docs)}

### Topic:
{topic}

### Lesson:
{lesson_text}
"""
    return _stream(prompt, 1000)


def _complete(prompt: str, max_tokens: int, as_json: bool = False) -> str:
    """Ask Gemini for a full (non-streamed) reply, with the same retry and fallback logic."""
    extra = {"response_mime_type": "application/json"} if as_json else {}
    config = types.GenerateContentConfig(temperature=0.3, max_output_tokens=max_tokens, **extra)
    last_error = None

    for model_name in MODELS_TO_TRY:
        for _ in range(2):
            try:
                response = client.models.generate_content(model=model_name, contents=prompt, config=config)
                if response.text:
                    return response.text
                last_error = Exception("empty reply")
                break
            except Exception as e:
                last_error = e
                if "503" in str(e) or "UNAVAILABLE" in str(e):
                    time.sleep(2)
                    continue
                break

    raise Exception(f"All Gemini models failed. Last error: {last_error}")


def parse_quiz(text: str) -> list[dict]:
    """Turn Gemini's JSON reply into a checked list of quiz questions."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    data = json.loads(text)
    if isinstance(data, dict):
        data = data.get("questions", [])
    quiz = []
    for item in data:
        options = [str(o) for o in item.get("options", [])]
        answer = item.get("answer_index")
        if len(options) != 4 or not isinstance(answer, int) or not 0 <= answer <= 3:
            continue
        quiz.append({
            "question": str(item.get("question", "")).strip(),
            "options": options,
            "answer_index": answer,
            "explanation": str(item.get("explanation", "")).strip(),
        })
    if not quiz:
        raise ValueError("The quiz came back in an unexpected format.")
    return quiz


def generate_quiz(topic: str, docs, lesson_text: str, n: int = 3) -> list[dict]:
    """Return n multiple-choice questions about the lesson."""
    prompt = f"""
You are an expert AI Academic Assistant & Subject Guide.
{QUIZ_INSTRUCTIONS.format(n=n)}
### Reference Materials:
{_format_context(docs)}

### Topic:
{topic}

### Lesson:
{lesson_text}
"""
    return parse_quiz(_complete(prompt, 1500, as_json=True))
