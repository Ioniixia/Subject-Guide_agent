"""Gemini answer generation that knows which file each chunk came from.
Reuses the client and model list from llm.py, so llm.py does not need to change."""
import time

from google.genai import types

from llm import MODELS_TO_TRY, client
from prompts import MARKS_GUIDE, MODES, PRACTICE_ANSWERS_INSTRUCTIONS


def describe_source(doc) -> str:
    meta = doc.metadata or {}
    name = meta.get("source", "unknown source")
    name = str(name).replace("\\", "/").split("/")[-1]
    label = f"{name} ({meta['source_type']})" if meta.get("source_type") else name
    if meta.get("chapter"):
        label += f", chapter: {meta['chapter']}"
    if meta.get("slide") is not None:
        label += f", slide {meta['slide']}"
    elif isinstance(meta.get("page"), int):
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
    if mode == "solve" and marks in MARKS_GUIDE:
        instructions += "\n" + MARKS_GUIDE[marks] + "\n"
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
