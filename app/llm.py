import contextvars
import functools
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# A request that takes longer than this gives up, and the next model in MODELS_TO_TRY is tried.
TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000),  # the SDK counts in milliseconds
)

# Fastest first. Falls back to the next one if a model is busy (503), unavailable (404) or too slow.
MODELS_TO_TRY = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
    "gemini-flash-latest",
]

# The model used by the latest Gemini call, so the Agent steps panel can show which one answered.
LAST_MODEL = contextvars.ContextVar("last_model", default=None)


def _remember_model(method):
    """Wrap a client call so it records the model it was asked to use."""

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        LAST_MODEL.set(kwargs.get("model"))
        return method(*args, **kwargs)

    return wrapper


client.models.generate_content = _remember_model(client.models.generate_content)
client.models.generate_content_stream = _remember_model(client.models.generate_content_stream)


def _build_prompt(query: str, context_chunks: list[str]) -> str:
    if not context_chunks:
        formatted_context = "No context provided."
    else:
        formatted_context = "\n\n---\n\n".join(
            [f"Chunk {i + 1}:\n{chunk}" for i, chunk in enumerate(context_chunks)]
        )

    return f"""
You are an expert AI Academic Assistant & Subject Guide.
Answer the student's question accurately using ONLY the provided reference materials below.
If the context is insufficient, state clearly what is missing, but synthesize what you can.

---
### Reference Materials / Context:
{formatted_context}

---
### Student Question:
{query}

---
### Formatting Guidelines:
- Keep the answer under 250 words.
- Use short headings and bullet points.
- Include one short practical example only if it helps.
- After key points, cite the supporting chunk number, like (Chunk 2).
"""


def generate_academic_answer_stream(query: str, context_chunks: list[str]):
    """Yield the answer in pieces as Gemini writes it, so text appears right away."""
    prompt = _build_prompt(query, context_chunks)
    config = types.GenerateContentConfig(temperature=0.3, max_output_tokens=800)
    last_error = None

    for model_name in MODELS_TO_TRY:
        for attempt in range(2):  # retry the same model once if it is busy
            started = False
            try:
                for chunk in client.models.generate_content_stream(
                    model=model_name, contents=prompt, config=config
                ):
                    if chunk.text:
                        started = True
                        yield chunk.text
                return
            except Exception as e:
                if started:
                    raise  # failed midway: don't restart with another model
                last_error = e
                msg = str(e)
                if "503" in msg or "UNAVAILABLE" in msg:
                    time.sleep(2)
                    continue
                break  # 404, 429 or other error: try the next model

    raise Exception(f"All Gemini models failed. Last error: {last_error}")


def generate_academic_answer(query: str, context_chunks: list[str]) -> str:
    """Non-streaming version (kept so older code still works)."""
    return "".join(generate_academic_answer_stream(query, context_chunks))
