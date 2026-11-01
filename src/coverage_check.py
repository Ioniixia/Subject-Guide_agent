import json
from collections import Counter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


def coverage_report(index_path="faiss_index", syllabus_path="data/syllabus.json"):
    """For every syllabus topic, count its note chunks and its exam questions."""
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    store = FAISS.load_local(index_path, embeddings, allow_dangerous_deserialization=True)
    with open(syllabus_path, encoding="utf-8") as f:
        syllabus = json.load(f)

    notes = Counter()
    questions = Counter()
    for doc in store.docstore._dict.values():
        topic = doc.metadata.get("topic")
        if not topic:
            continue
        if doc.metadata.get("source_type") == "question_paper":
            questions[topic] += 1
        elif doc.metadata.get("source_type") == "notes":
            notes[topic] += 1

    rows = []
    for unit in syllabus["units"]:
        for topic in unit["topics"]:
            n, q = notes[topic], questions[topic]
            gaps = []
            if n == 0:
                gaps.append("NO STUDY MATERIAL")
            if q == 0:
                gaps.append("NO QUESTIONS")
            rows.append({"chapter": unit["chapter"], "topic": topic,
                         "notes": n, "questions": q, "gaps": gaps})
    return rows


if __name__ == "__main__":
    current = None
    for r in coverage_report():
        if r["chapter"] != current:
            current = r["chapter"]
            print(f"\n{current}")
        status = ", ".join(r["gaps"]) if r["gaps"] else "ok"
        print(f"  {r['topic']:<46} notes={r['notes']:<3} questions={r['questions']:<2} {status}")