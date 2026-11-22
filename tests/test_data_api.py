"""Tests for the data endpoints (/health, /filters, /search, /upload), the API-key check,
the upload limits and CORS.

Run from the project root:   python -m pytest tests/test_data_api.py -q
They use stand-in embeddings, so no model is downloaded and they run in a few seconds.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient
from langchain_community.embeddings import FakeEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

KEY = "test-key-123"
HEADERS = {"X-API-Key": KEY}
SAMPLE_PAPER = ROOT / "data" / "aiml_sample_qp_2023.docx"

DOCS = [
    Document(page_content="Supervised learning uses labelled data",
             metadata={"source_type": "notes", "subject": "AIML", "chapter": "Unit 1",
                       "topic": "Types of Machine Learning", "slide": 38, "source_file": "u1.pptx"}),
    Document(page_content="TensorFlow is a framework",
             metadata={"source_type": "notes", "subject": "AIML", "chapter": "Unit 2",
                       "topic": "TensorFlow and PyTorch", "slide": 14, "source_file": "u2.pptx"}),
    Document(page_content="Q6. Linear regression question [5 marks]",
             metadata={"source_type": "question_paper", "subject": "AIML", "chapter": "Unit 3",
                       "topic": "Linear regression", "year": 2023, "question_no": 6, "marks": 5,
                       "difficulty": "medium", "source_file": "qp.docx"}),
    Document(page_content="Chapter text about regression",
             metadata={"source_type": "textbook", "subject": "AIML", "chapter": "Unit 3",
                       "source_file": "tb.docx"}),
]


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("API_KEY", KEY)
    monkeypatch.setenv("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", "dummy-key-for-tests"))
    monkeypatch.chdir(ROOT)  # the loader reads data/*.json relative to the project root

    import api
    import core
    import retrieval

    fake = FakeEmbeddings(size=32)
    store = FAISS.from_documents(DOCS, fake)
    monkeypatch.setattr(retrieval, "get_embeddings", lambda: fake)
    monkeypatch.setattr(retrieval, "get_builtin_store", lambda: store)
    monkeypatch.setattr(retrieval, "UPLOADS", {})
    monkeypatch.setattr(core, "_uploaded_index", None)
    return TestClient(api.app)


def upload(client, name="paper.docx", data=b"x", **fields):
    form = {"source_type": "question_paper", "subject": "AIML", "chapter": "All Units", "year": "2023"}
    form.update(fields)
    return client.post("/upload", headers=HEADERS, data=form,
                       files=[("files", (name, data, "application/octet-stream"))])


# ---------- health and the API key ----------

def test_health_needs_no_key(client):
    assert client.get("/health").json()["status"] == "ok"


@pytest.mark.parametrize("method,path", [("get", "/filters"), ("post", "/search"), ("post", "/upload")])
def test_missing_key_is_rejected(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_wrong_key_is_rejected(client):
    assert client.get("/filters", headers={"X-API-Key": "nope"}).status_code == 401


def test_server_without_api_key_refuses(client, monkeypatch):
    monkeypatch.delenv("API_KEY")
    assert client.get("/filters", headers=HEADERS).status_code == 500


# ---------- /filters ----------

def test_filters_lists_the_index_contents(client):
    body = client.get("/filters", headers=HEADERS).json()
    assert body["subjects"] == ["AIML"]
    assert set(body["source_types"]) == {"notes", "textbook", "question_paper"}
    assert body["years"] == [2023]
    assert "Unit 3" in body["chapters"]


# ---------- /search ----------

def search(client, **body):
    return client.post("/search", headers=HEADERS, json=body)


def test_search_returns_k_results_with_metadata(client):
    results = search(client, question="regression", k=3).json()["results"]
    assert len(results) == 3
    assert {"text", "metadata", "distance"} <= set(results[0])


def test_search_filters_by_source_type(client):
    results = search(client, question="x", k=4, source_types=["question_paper"]).json()["results"]
    assert len(results) == 1
    assert results[0]["metadata"]["difficulty"] == "medium"


def test_search_filters_by_two_source_types(client):
    assert len(search(client, question="x", k=4, source_types=["notes", "textbook"]).json()["results"]) == 3


def test_search_filters_by_chapter_and_topic(client):
    assert len(search(client, question="x", chapter="Unit 3").json()["results"]) == 2
    assert len(search(client, question="x", topic="Linear regression").json()["results"]) == 1


def test_search_with_no_match_returns_an_empty_list(client):
    response = search(client, question="x", chapter="Nope")
    assert response.status_code == 200 and response.json()["results"] == []


@pytest.mark.parametrize("body", [
    {"question": ""},
    {"question": "     "},
    {"question": "a" * 1001},
    {"question": "ok", "k": 0},
    {"question": "ok", "k": 11},
    {},
])
def test_search_rejects_bad_input(client, body):
    assert search(client, **body).status_code == 422


def test_search_strips_spaces_around_the_question(client):
    assert search(client, question="  linear regression  ").json()["question"] == "linear regression"


def test_search_unknown_index_id_is_404(client):
    assert search(client, question="x", index_id="zzz").status_code == 404


# ---------- /upload ----------

def test_upload_indexes_the_file_and_gives_it_to_the_agent(client):
    import core

    response = upload(client, "aiml_sample_qp_2023.docx", SAMPLE_PAPER.read_bytes())
    assert response.status_code == 200
    body = response.json()
    assert body["chunks"] == 7 and len(body["index_id"]) == 8
    assert core._uploaded_index is not None  # /ask can now see the uploaded file

    found = search(client, question="x", k=10, use_builtin=False, index_id=body["index_id"],
                   topic="Linear regression").json()["results"]
    assert len(found) == 1
    assert found[0]["metadata"]["question_no"] == 6
    assert found[0]["metadata"]["chapter"].startswith("Unit 3")  # tagged from data/question_tags.json


def test_upload_accepts_year_zero_from_the_docs_page(client):
    assert upload(client, "aiml_sample_qp_2023.docx", SAMPLE_PAPER.read_bytes(), year="0").status_code == 200


def test_upload_rejects_other_file_types(client):
    response = upload(client, "notes.txt", b"hello")
    assert response.status_code == 400 and "PDF, DOCX and PPTX" in response.json()["detail"]


def test_upload_rejects_an_empty_file(client):
    assert upload(client, "empty.docx", b"").status_code == 400


def test_upload_rejects_an_unknown_source_type(client):
    assert upload(client, "a.docx", SAMPLE_PAPER.read_bytes(), source_type="banana").status_code == 400


def test_upload_rejects_a_year_out_of_range(client):
    assert upload(client, "a.docx", SAMPLE_PAPER.read_bytes(), year="1800").status_code == 400


def test_upload_rejects_a_long_subject(client):
    assert upload(client, "a.docx", SAMPLE_PAPER.read_bytes(), subject="x" * 101).status_code == 422


def test_upload_rejects_a_file_that_is_too_large(client, monkeypatch):
    import api

    monkeypatch.setattr(api, "MAX_FILE_BYTES", 10)
    assert upload(client, "big.docx", b"x" * 11).status_code == 413


def test_upload_rejects_too_many_files(client):
    files = [("files", (f"f{i}.docx", b"x", "application/octet-stream")) for i in range(11)]
    response = client.post("/upload", headers=HEADERS, files=files, data={"source_type": "notes"})
    assert response.status_code == 400


# ---------- CORS ----------

def preflight(client, origin):
    return client.options("/search", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-api-key,content-type",
    })


def test_cors_allows_the_frontend(client):
    response = preflight(client, "http://localhost:5173")
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "x-api-key" in response.headers["access-control-allow-headers"].lower()


def test_cors_blocks_other_sites(client):
    assert "access-control-allow-origin" not in preflight(client, "http://evil.example").headers
