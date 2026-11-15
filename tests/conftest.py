"""Test setup: dummy key, temporary database and log folder, and the app/ folder on the path."""
import json
import os
import sys
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ["APP_DB"] = os.path.join(_tmp, "test.db")
os.environ["AGENT_LOG_DIR"] = os.path.join(_tmp, "logs")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

import pytest  # noqa: E402
from langchain_community.embeddings import FakeEmbeddings  # noqa: E402
from langchain_community.vectorstores import FAISS  # noqa: E402
from langchain_core.documents import Document  # noqa: E402


def make_doc(text, source_type, chapter, subject="AIML", **meta):
    return Document(page_content=text, metadata={
        "source": f"{source_type}.pdf", "source_type": source_type, "subject": subject, "chapter": chapter, **meta})


@pytest.fixture(autouse=True)
def no_builtin_index(monkeypatch):
    """Tests use their own small index. Without this, a real faiss_index/ in the repo would be loaded
    (slow, and it changes the results), so a test would pass on one machine and fail on another."""
    import core

    monkeypatch.setattr(core, "load_builtin_index", lambda: None)


@pytest.fixture(scope="session")
def store():
    docs = [
        make_doc("Backpropagation updates weights.", "notes", "Neural Networks"),
        make_doc("Neural networks textbook chapter.", "textbook", "Neural Networks"),
        make_doc("Lab: train a small network.", "lab_manual", "Neural Networks"),
        make_doc("Search algorithms explore states.", "notes", "Search"),
        make_doc("Q3: Explain backpropagation.", "question_paper", "All Units", question_no="Q3", year=2023, marks=5),
        make_doc("Q1: Define a perceptron.", "question_paper", "All Units", question_no=1, year=2022, marks=2),
    ]
    return FAISS.from_documents(docs, FakeEmbeddings(size=32))


@pytest.fixture
def fake_llm(monkeypatch):
    """Replace every Gemini call with a fake. Returns a dict to steer it from a test."""
    import agent
    import agent_routes
    import agent_service
    import generate_answer

    state = {"tool": "answer_question", "fail": None, "calls": []}

    def answer(question, docs, mode="qa", marks=None):
        state["calls"].append((mode, marks))
        if state["fail"]:
            raise Exception(state["fail"])
        yield "Supervised learning uses labelled data [1] and [2]."

    quiz = lambda topic, docs, lesson, n=3: [  # noqa: E731
        {"question": f"Q{i}?", "options": ["a", "b", "c", "d"], "answer_index": 1, "explanation": "because"} for i in range(3)]

    monkeypatch.setattr(agent_service, "generate_answer", answer)
    monkeypatch.setattr(generate_answer, "generate_answer", answer)
    for module in (agent_service, agent_routes, generate_answer):
        monkeypatch.setattr(module, "generate_quiz", quiz)
    for module in (agent_routes, generate_answer):
        monkeypatch.setattr(module, "generate_practice_answers", lambda t, d, text: iter(["1. A", "2. B"]))
    monkeypatch.setattr(agent, "_call_router", lambda prompt: json.dumps({"tool": state["tool"], "reason": "test"}))
    return state


@pytest.fixture
def client(store, fake_llm):
    import agent_routes
    import core
    from fastapi.testclient import TestClient
    from api_test import app

    core.set_uploaded_index(store)
    agent_routes.limiter = agent_routes.RateLimiter(max_calls=1000)
    yield TestClient(app)
    core.set_uploaded_index(None)
