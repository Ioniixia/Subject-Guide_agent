"""Deployment helpers: serving the frontend, the benchmark summary and the version pinning.
Run from the repo root with:  python -m pytest tests -q"""
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import benchmark  # noqa: E402
import pin_versions  # noqa: E402
from web import mount_frontend  # noqa: E402


# ---------- serving the frontend ----------
def make_app():
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


def test_frontend_is_not_mounted_when_it_was_not_built(tmp_path):
    app = make_app()
    assert mount_frontend(app, tmp_path / "missing") is False
    assert TestClient(app).get("/").status_code == 404


def test_frontend_is_served_and_the_api_still_works(tmp_path):
    (tmp_path / "index.html").write_text("<html><div id='root'>study guide</div></html>")
    (tmp_path / "app.js").write_text("console.log('hi')")
    app = make_app()
    assert mount_frontend(app, tmp_path) is True
    client = TestClient(app)
    assert "study guide" in client.get("/").text
    assert client.get("/app.js").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}  # API routes are not hidden by the frontend
    assert client.get("/docs").status_code == 200
    assert client.get("/nothing-here.js").status_code == 404


# ---------- benchmark ----------
def result(seconds, **data):
    base = {"tool": "answer_question", "answer": "text", "citations_ok": True, "fallback": False,
            "steps": [{"agent": "Tutor", "ms": 1000}]}
    return {"ok": True, "seconds": seconds, "data": {**base, **data}}


def test_benchmark_summary_counts_failures_fallbacks_and_citations():
    stats = benchmark.summarize([
        result(2.0), result(4.0), result(6.0, citations_ok=False), result(3.0, fallback=True),
        {"ok": False, "seconds": 1.0, "error": "HTTP 502"},
    ])
    assert stats["questions"] == 5 and stats["succeeded"] == 4
    assert stats["median_s"] == 3.5 and stats["citations_ok"] == 3 and stats["fallbacks"] == 1
    assert stats["avg_step_ms"] == {"Tutor": 1000}
    assert "| Questions asked | 5 |" in benchmark.to_markdown(stats)


def test_benchmark_summary_handles_no_successful_requests():
    stats = benchmark.summarize([{"ok": False, "seconds": 1.0, "error": "URLError"}])
    assert stats["succeeded"] == 0 and stats["median_s"] is None
    assert "None s" in benchmark.to_markdown(stats)


# ---------- pinning versions ----------
def test_package_names_ignore_comments_versions_and_extras():
    lines = ["pypdf", "langchain>=0.2  # chat", "", "# a comment", "uvicorn[standard]==0.30", "-r other.txt", "faiss-cpu"]
    assert pin_versions.package_names(lines) == ["pypdf", "langchain", "uvicorn", "faiss-cpu"]


def test_pinned_reports_installed_versions_and_missing_packages():
    lines, missing = pin_versions.pinned(["pytest", "definitely-not-installed-xyz"])
    assert lines[0].startswith("pytest==") and missing == ["definitely-not-installed-xyz"]
