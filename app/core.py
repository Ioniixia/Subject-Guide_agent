"""Retrieval helpers shared by the Streamlit app and the API. No Streamlit imports."""
import os
import re
from collections import Counter
from functools import lru_cache

ALL_UNITS = "All Units"

_uploaded_index = None  # set by the upload endpoint; used by the API


@lru_cache(maxsize=1)
def get_embeddings():
    from langchain_community.embeddings import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def load_builtin_index():
    """The saved index (faiss_index/), if it exists next to where the app is started."""
    if not os.path.isdir("faiss_index"):
        return None
    from langchain_community.vectorstores import FAISS

    return FAISS.load_local("faiss_index", get_embeddings(), allow_dangerous_deserialization=True)


def set_uploaded_index(index):
    """The upload endpoint calls this after it builds an index from uploaded files."""
    global _uploaded_index
    _uploaded_index = index


def active_stores(use_builtin: bool = True):
    """Indexes the API searches: the uploaded one (if any) plus the built-in one."""
    stores = []
    if _uploaded_index is not None:
        stores.append(_uploaded_index)
    if use_builtin:
        builtin = load_builtin_index()
        if builtin is not None:
            stores.append(builtin)
    return stores


def collect_tags(stores):
    """Return the set of (subject, chapter, source_type) found in the chunks of the given indexes."""
    found = set()
    for store in stores:
        for doc in store.docstore._dict.values():
            meta = doc.metadata or {}
            found.add((meta.get("subject"), meta.get("chapter"), meta.get("source_type")))
    return found


def list_chapters(stores, subject=None):
    """Real chapters in the indexes (the 'All Units' tag is not a chapter)."""
    return sorted({c for s, c, _ in collect_tags(stores) if c and c != ALL_UNITS and (not subject or s == subject)})


def make_filter(wanted: dict):
    """Metadata filter for FAISS. A list value means 'any of these'."""

    def matches(meta):
        for key, want in wanted.items():
            have = meta.get(key)
            if key == "chapter" and have == ALL_UNITS:
                continue  # question papers cover every unit, so they match any chapter
            if isinstance(want, (list, set, tuple)):
                if have not in want:
                    return False
            elif have != want:
                return False
        return True

    return matches


def search_docs(stores, question, k, tag_filter, source_types=None):
    """Search every index; returns (doc, score) pairs sorted best first (lower score = closer)."""
    wanted = dict(tag_filter)
    if source_types:
        wanted["source_type"] = source_types
    results = []
    for store in stores:
        extra = {"filter": make_filter(wanted), "fetch_k": max(store.index.ntotal, k)} if wanted else {}
        results.extend(store.similarity_search_with_score(question, k=k, **extra))
    results.sort(key=lambda pair: pair[1])
    return results


def retrieve(stores, question, k, tag_filter, types, all_types, per_type):
    """Pick the best chunks. In 'per_type' mode every source type contributes, so a lesson
    can combine notes, textbook, lab manual and past papers."""
    if per_type and len(types) > 1:
        share = max(1, round(k / len(types)))
        results = []
        for source_type in types:
            results.extend(search_docs(stores, question, share, tag_filter, [source_type])[:share])
    else:
        subset = types if set(types) != set(all_types) else None
        results = search_docs(stores, question, k, tag_filter, subset)[:k]

    seen, docs = set(), []
    for doc, _ in sorted(results, key=lambda pair: pair[1]):
        meta = doc.metadata or {}
        key = (meta.get("source"), meta.get("page"), meta.get("slide"), doc.page_content[:80])
        if key not in seen:
            seen.add(key)
            docs.append(doc)
    return docs


def _number(value) -> int:
    digits = re.sub(r"\D", "", str(value or ""))
    return int(digits) if digits else 0


def practice_questions(stores, subject=None, chapter=None, limit=30):
    """Past-paper questions to practise: newest paper first. Questions tagged with the
    chosen chapter come before the 'All Units' ones."""
    docs = []
    for store in stores:
        for doc in store.docstore._dict.values():
            meta = doc.metadata or {}
            if meta.get("source_type") != "question_paper":
                continue
            if subject and meta.get("subject") != subject:
                continue
            if chapter and meta.get("chapter") not in (chapter, ALL_UNITS):
                continue
            docs.append(doc)

    def order(doc):
        meta = doc.metadata
        exact = 0 if chapter and meta.get("chapter") == chapter else 1
        return (exact, -_number(meta.get("year")), _number(meta.get("question_no")))

    docs.sort(key=order)
    return docs[:limit]


def topic_of(docs, chapter_filter=None, subject_filter=None):
    """The (subject, chapter) a set of chunks is about, used when saving progress."""
    chapters = Counter(
        (d.metadata or {}).get("chapter") for d in docs
        if (d.metadata or {}).get("chapter") not in (None, ALL_UNITS)
    )
    subjects = Counter((d.metadata or {}).get("subject") for d in docs if (d.metadata or {}).get("subject"))
    chapter = chapter_filter or (chapters.most_common(1)[0][0] if chapters else "General")
    subject = subject_filter or (subjects.most_common(1)[0][0] if subjects else "General")
    return subject, chapter
