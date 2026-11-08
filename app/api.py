"""FastAPI backend for the Subject Guide agent.

Run from the project root:   python -m uvicorn app.api:app
Interactive docs:            http://127.0.0.1:8000/docs
"""
import os
import secrets
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

load_dotenv()

from fastapi import Depends, FastAPI, File, Form, HTTPException, Security, UploadFile
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

import retrieval

MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB per uploaded file

app = FastAPI(title="Subject Guide API", version="1.0")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Security(api_key_header)):
    """Simple authentication: the X-API-Key header must match the API_KEY setting."""
    expected = os.getenv("API_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="API_KEY is not set on the server")
    if not key or not secrets.compare_digest(key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    k: int = Field(4, ge=1, le=10)
    subject: str | None = None
    chapter: str | None = None
    source_types: list[str] | None = None
    topic: str | None = None
    index_id: str | None = None  # id returned by POST /upload
    use_builtin: bool = True


@app.get("/health")
def health():
    """Open endpoint: checks that the server is running."""
    return {"status": "ok", "uploaded_indexes": len(retrieval.UPLOADS)}


@app.get("/filters", dependencies=[Depends(require_api_key)])
def filters():
    """Subjects, chapters, source types, topics and years in the built-in index."""
    return retrieval.list_filters()


@app.post("/search", dependencies=[Depends(require_api_key)])
def search(request: SearchRequest):
    """Question plus filters in, closest chunks (with source metadata) out."""
    try:
        results = retrieval.search(
            request.question, request.k, request.subject, request.chapter,
            request.source_types, request.topic, request.index_id, request.use_builtin,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown index_id. Upload the files again.")
    return {
        "question": request.question,
        "results": [retrieval.doc_to_dict(doc, distance) for doc, distance in results],
    }


@app.post("/upload", dependencies=[Depends(require_api_key)])
def upload(
    files: list[UploadFile] = File(...),
    source_type: str = Form("notes"),
    subject: str = Form("AIML"),
    chapter: str = Form("General"),
    year: int | None = Form(None),
):
    """Upload PDF, DOCX or PPTX files, tag them, and index them. Returns an index_id for /search."""
    contents = []
    for f in files:
        data = f.file.read()
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail=f"{f.filename} is larger than 25 MB")
        contents.append((f.filename, data))
    try:
        index_id, chunks = retrieval.index_uploads(contents, source_type, subject, chapter, year)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"index_id": index_id, "files": [name for name, _ in contents], "chunks": chunks}


def _fix_file_fields(node):
    """Newer FastAPI marks file fields as contentMediaType, which the /docs page shows as a text
    box. Rewrite them as format: binary so /docs shows a Choose File button."""
    if isinstance(node, dict):
        if node.get("contentMediaType") == "application/octet-stream":
            node.pop("contentMediaType")
            node["format"] = "binary"
        for value in node.values():
            _fix_file_fields(value)
    elif isinstance(node, list):
        for value in node:
            _fix_file_fields(value)


_original_openapi = app.openapi


def _custom_openapi():
    schema = _original_openapi()
    _fix_file_fields(schema)
    return schema


app.openapi = _custom_openapi


# Yitong's endpoints: app/agent_routes.py must define `router = APIRouter()`
try:
    from agent_routes import router as agent_router

    app.include_router(agent_router, dependencies=[Depends(require_api_key)])
except ModuleNotFoundError as e:
    if e.name != "agent_routes":
        raise
    print("agent_routes.py not found: only the data endpoints are loaded")
