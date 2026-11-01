import re
import sys
import time

sys.path.insert(0, "app")  # reuse the Gemini client from app/llm.py

from google.genai import types
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from llm import MODELS_TO_TRY, client

# Fill these in from Google's pricing page: (USD per 1M input tokens, USD per 1M output tokens).
# Leave a model as None if you are on the free tier or don't know the price.
PRICES = {
    "gemini-2.5-flash-lite": None,
    "gemini-3.1-flash-lite": None,
    "gemini-flash-latest": None,
    "gemini-3.5-flash": None,
}

# Each question comes with words that a correct answer from your slides should contain.
QUESTIONS = [
    ("What is the difference between weak AI and strong AI?", ["narrow", "general", "human"]),
    ("What is TensorFlow used for?", ["open source", "machine learning", "deep learning"]),
    ("What is a decision tree?", ["supervised", "root", "leaf"]),
    ("Explain supervised learning with an example.", ["label", "train", "predict"]),
    ("What is linear regression?", ["supervised", "slope", "intercept"]),
]


def normalize(text):
    return text.lower().replace("-", " ")


def keyword_score(answer, keywords):
    text = normalize(answer)
    return sum(1 for k in keywords if normalize(k) in text) / len(keywords)


def build_prompt(question, docs):
    context = "\n\n---\n\n".join(f"[{i}] {d.page_content}" for i, d in enumerate(docs, 1))
    return f"""Answer the student's question using ONLY the numbered reference materials below.
Cite sources inline like [1]. Keep the answer under 150 words.

### Reference Materials:
{context}

### Question:
{question}
"""


def main():
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
    retrieved = {
        q: store.similarity_search(q, k=3, filter={"source_type": "notes"})
        for q, _ in QUESTIONS
    }
    config = types.GenerateContentConfig(temperature=0.3, max_output_tokens=1000)

    summary = []
    for model in MODELS_TO_TRY:
        print(f"\nTesting {model} ...")
        rows, errors = [], 0
        for question, keywords in QUESTIONS:
            prompt = build_prompt(question, retrieved[question])
            start = time.perf_counter()
            try:
                resp = client.models.generate_content(model=model, contents=prompt, config=config)
                seconds = time.perf_counter() - start
                answer = resp.text or ""
                usage = resp.usage_metadata
                rows.append({
                    "seconds": seconds,
                    "score": keyword_score(answer, keywords),
                    "cited": bool(re.search(r"\[\d+\]", answer)),
                    "in": getattr(usage, "prompt_token_count", 0) or 0,
                    "out": getattr(usage, "candidates_token_count", 0) or 0,
                })
                print(f"  ok  {seconds:5.1f}s  keywords={rows[-1]['score']:.0%}  {question[:45]}")
            except Exception as e:
                errors += 1
                print(f"  ERROR {str(e)[:90]}")
            time.sleep(1)

        if rows:
            n = len(rows)
            avg = lambda key: sum(r[key] for r in rows) / n
            price = PRICES.get(model)
            if price:
                cost = (avg("in") * price[0] + avg("out") * price[1]) / 1_000_000 * 1000
                cost_text = f"${cost:.2f}"
            else:
                cost_text = "free tier / fill in"
            summary.append(
                f"| {model} | {avg('seconds'):.1f} | {avg('score'):.0%} | "
                f"{sum(r['cited'] for r in rows)}/{n} | {avg('in'):.0f} / {avg('out'):.0f} | "
                f"{cost_text} | {errors} |"
            )
        else:
            summary.append(f"| {model} | failed | - | - | - | - | {errors} |")

    table = (
        "| Model | Avg response time (s) | Keyword accuracy | Answers with citations | "
        "Avg tokens (in / out) | Est. cost per 1000 questions | Errors |\n"
        "|---|---|---|---|---|---|---|\n" + "\n".join(summary)
    )
    print("\n" + table)
    with open("model_comparison.md", "w", encoding="utf-8") as f:
        f.write(table + "\n")
    print("\nSaved to model_comparison.md")


if __name__ == "__main__":
    main()