"""Search and upload helpers shared by the API (and usable from agent_routes.py)."""
import os
import sys
import tempfile
import uuid
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

from load_and_chunk import load_and_chunk_multiple

INDEX_PATH = os.path.join(ROOT, "faiss_index")
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx"}
SOURCE_TYPES = ["notes", "textbook", "lab_manual", "question_paper"]
MAX_UPLOAD_INDEXES = 20  # keep memory small: the oldest uploaded index is dropped

UPLOADS = {}  # index_id -> FAISS store built from uploaded files

# Metadata fields that are sent back to the caller
KEEP_FIELDS = ["source_file", "source_type", "subject", "chapter", "topic", "slide",
               "page", "question_no", "year", "marks", "difficulty"]


@lru_cache(maxsize=1)
def get_embeddings():
    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def get_builtin_store():
    return FAISS.load_local(INDEX_PATH, get_embeddings(), allow_dangerous_deserialization=True)


def _as_list(value):
    if value is None:
        return None
    return [value] if isinstance(value, str) else list(value)


def make_filter(subject=None, chapter=None, source_types=None, topic=None):
    """Build a metadata filter. Each field can be one value or a list of values."""
    wanted = {
        "subject": _as_list(subject),
        "chapter": _as_list(chapter),
        "source_type": _as_list(source_types),
        "topic": _as_list(topic),
    }
    wanted = {key: values for key, values in wanted.items() if values}
    if not wanted:
        return None

    def check(metadata):
        return all(metadata.get(key) in values for key, values in wanted.items())

    return check


def search(question, k=4, subject=None, chapter=None, source_types=None, topic=None,
           index_id=None, use_builtin=True):
    """Return the k closest (Document, distance) pairs. A lower distance is a closer match."""
    metadata_filter = make_filter(subject, chapter, source_types, topic)

    stores = []
    if use_builtin:
        stores.append(get_builtin_store())
    if index_id:
        if index_id not in UPLOADS:
            raise KeyError(index_id)
        stores.append(UPLOADS[index_id])

    results = []
    for store in stores:
        results.extend(
            store.similarity_search_with_score(
                question, k=k, filter=metadata_filter, fetch_k=max(store.index.ntotal, k)
            )
        )
    results.sort(key=lambda pair: pair[1])
    return results[:k]


def doc_to_dict(doc, distance=None):
    metadata = {key: doc.metadata[key] for key in KEEP_FIELDS if key in doc.metadata}
    out = {"text": doc.page_content, "metadata": metadata}
    if distance is not None:
        out["distance"] = round(float(distance), 4)
    return out


def list_filters():
    """Every subject, chapter, source type, topic and year found in the built-in index."""
    docs = list(get_builtin_store().docstore._dict.values())

    def unique(key):
        return sorted({d.metadata[key] for d in docs if d.metadata.get(key) is not None})

    return {
        "subjects": unique("subject"),
        "chapters": unique("chapter"),
        "source_types": unique("source_type"),
        "topics": unique("topic"),
        "years": unique("year"),
    }


def index_uploads(files, source_type, subject, chapter, year=None):
    """files: list of (filename, bytes). Builds an in-memory index and returns its id."""
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"source_type must be one of {SOURCE_TYPES}")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        configs = []
        for name, data in files:
            extension = os.path.splitext(name)[1].lower()
            if extension not in ALLOWED_EXTENSIONS:
                raise ValueError(f"{name}: only PDF, DOCX and PPTX files are supported")
            path = os.path.join(folder, os.path.basename(name))
            with open(path, "wb") as f:
                f.write(data)
            configs.append({"path": path, "source_type": source_type,
                            "subject": subject, "chapter": chapter, "year": year})
        chunks = load_and_chunk_multiple(configs)

    if not chunks:
        raise ValueError("No readable text was found in the uploaded files")

    store = FAISS.from_documents(chunks, get_embeddings())
    index_id = uuid.uuid4().hex[:8]
    UPLOADS[index_id] = store
    while len(UPLOADS) > MAX_UPLOAD_INDEXES:
        UPLOADS.pop(next(iter(UPLOADS)))
    return index_id, len(chunks)
