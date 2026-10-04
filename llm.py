import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Models are tried in order. All of these appear in your list_models.py output.
# gemini-flash-latest is an alias Google keeps pointing at a current Flash model.
MODELS_TO_TRY = [
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
]


def generate_academic_answer(query: str, context_chunks: list[str]) -> str:
    """Send the student's question plus retrieved context to Gemini
    and return the generated explanation as text."""

    # Format the retrieved chunks (from the retriever or PLACEHOLDER_CHUNKS)
    if not context_chunks:
        formatted_context = "No context provided."
    else:
        formatted_context = "\n\n---\n\n".join(
            [f"Chunk {i + 1}:\n{chunk}" for i, chunk in enumerate(context_chunks)]
        )

    prompt = f"""
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
- Structure your response clearly with headings, bullet points, and step-by-step reasoning.
- Provide a comprehensive explanation, including theoretical concepts and practical examples.
"""

    last_error = None

    for model_name in MODELS_TO_TRY:
        for attempt in range(2):  # retry the same model once if it is busy
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.3),
                )
                return response.text
            except Exception as e:
                last_error = e
                msg = str(e)
                if "503" in msg or "UNAVAILABLE" in msg:
                    time.sleep(2)  # server busy: wait, retry, then move on
                    continue
                break  # 404, 429 or other error: skip to the next model

    raise Exception(f"All Gemini models failed. Last error: {last_error}")