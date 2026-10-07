"""Gemini answer generation that knows which file each chunk came from.
Reuses the client and model list from llm.py, so llm.py does not need to change."""
import time

from google.genai import types

from llm import MODELS_TO_TRY, client


def describe_source(doc) -> str:
    meta = doc.metadata or {}
    name = meta.get("source", "unknown source")
    name = str(name).replace("\\", "/").split("/")[-1]
    label = f"{name} ({meta['source_type']})" if meta.get("source_type") else name
    if meta.get("slide") is not None:
        label += f", slide {meta['slide']}"
    elif isinstance(meta.get("page"), int):
        label += f", page {meta['page'] + 1}"  # PDF pages are counted from 0
    return label


def build_prompt(question: str, docs) -> str:
    if docs:
        context = "\n\n---\n\n".join(
            f"[{i}] Source: {describe_source(d)}\n{d.page_content}" for i, d in enumerate(docs, 1)
        )
    else:
        context = "No context provided."
    return f"""
You are an expert AI Academic Assistant & Subject Guide.
Answer the student's question using ONLY the numbered reference materials below.
Cite the sources you use inline like [1] or [2]. If the materials do not cover something, say so.

### Reference Materials:
{context}

### Student Question:
{question}

### Formatting Guidelines:
- Use short headings and bullet points.
- Keep the answer under 300 words.
- Include one short example only if it helps.
"""


def generate_answer(question: str, docs):
    """Yield the answer piece by piece (use with st.write_stream)."""
    prompt = build_prompt(question, docs)
    config = types.GenerateContentConfig(temperature=0.3, max_output_tokens=1000)
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
