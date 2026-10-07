import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Lite models first: they answer faster. Falls back to the next one if a model
# is busy (503) or unavailable (404).
MODELS_TO_TRY = [
    "gemini-2.5-flash-lite",   # fastest: does not spend time "thinking"
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
    "gemini-3.5-flash",
]


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
