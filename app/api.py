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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, field_validator

import core  # Yitong's shared retrieval module (app/core.py)
import retrieval

MAX_FILES = 10  # files per upload request
MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB per file
MAX_TOTAL_BYTES = 50 * 1024 * 1024  # 50 MB per upload request

app = FastAPI(
    title="Subject Guide API",
    version="1.0",
    swagger_ui_parameters={"persistAuthorization": True},  # /docs remembers the key after a refresh
)

# CORS: lets the React frontend (a different address) call this API from the browser.
# Add the deployed frontend address with:  CORS_ORIGINS=https://my-app.vercel.app,http://localhost:5173
_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins.split(",") if o.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-API-Key", "Content-Type"],
)

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

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("The question must not be empty")
        return value


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
    subject: str = Form("AIML", max_length=100),
    chapter: str = Form("General", max_length=100),
    year: int | None = Form(None),
):
    """Upload PDF, DOCX or PPTX files, tag them, and index them.

    Returns an index_id for /search. The new index is also given to the agent (core.py),
    so /ask can answer from the uploaded files."""
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Upload at most {MAX_FILES} files at a time")
    if year in (None, 0):  # the /docs page fills in 0 when the field is left alone
        year = None
    elif not 1990 <= year <= 2100:
        raise HTTPException(status_code=400, detail="year must be between 1990 and 2100")

    contents, total = [], 0
    for f in files:
        name = f.filename or "upload"
        if os.path.splitext(name)[1].lower() not in retrieval.ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"{name}: only PDF, DOCX and PPTX files are supported")
        data = f.file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail=f"{name} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
        if not data:
            raise HTTPException(status_code=400, detail=f"{name} is empty")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise HTTPException(status_code=413, detail=f"The files together are larger than {MAX_TOTAL_BYTES // (1024 * 1024)} MB")
        contents.append((name, data))

    try:
        index_id, chunks = retrieval.index_uploads(contents, source_type, subject, chapter, year)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    core.set_uploaded_index(retrieval.UPLOADS[index_id])
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
