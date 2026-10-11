import os

import streamlit as st

from generate_answer import describe_source, generate_answer, generate_practice_answers
from prompts import MODES
from session_index import SOURCE_TYPES, SUPPORTED_EXTENSIONS, build_session_index

st.set_page_config(page_title="Academic Subject Guide AI", page_icon="📚", layout="wide")
st.title("📚 Academic Subject Guide AI")
st.caption("Upload your study material, then ask, solve or learn.")


@st.cache_resource(show_spinner="Loading embedding model (first time only)...")
def get_embeddings():
    from langchain_community.embeddings import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


@st.cache_resource(show_spinner="Loading built-in notes index...")
def load_builtin_index():
    """Person 1's saved index (faiss_index/), if it exists next to where the app is started."""
    if not os.path.isdir("faiss_index"):
        return None
    from langchain_community.vectorstores import FAISS

    return FAISS.load_local("faiss_index", get_embeddings(), allow_dangerous_deserialization=True)


def collect_tags(stores):
    """Return the set of (subject, chapter) pairs found in the chunks of the given indexes."""
    pairs = set()
    for store in stores:
        for doc in store.docstore._dict.values():
            meta = doc.metadata or {}
            pairs.add((meta.get("subject"), meta.get("chapter")))
    return pairs


def show_sources(docs):
    st.markdown("### 🔍 Source chunks")
    for i, doc in enumerate(docs, 1):
        with st.expander(f"[{i}] {describe_source(doc)}", expanded=(i == 1)):
            st.write(doc.page_content)


def show_extras(last):
    """Extra step for the 'Learn a topic' flow: reveal answers after the student tries."""
    if last["mode"] != "learn" or not last.get("text"):
        return
    if last.get("answers"):
        st.markdown("### ✅ Practice answers")
        st.markdown(last["answers"])
    elif st.button("Show answers to the practice questions", key="show_answers"):
        st.markdown("### ✅ Practice answers")
        try:
            last["answers"] = st.write_stream(
                generate_practice_answers(last["question"], last["docs"], last["text"])
            )
        except Exception as e:
            st.error(f"Error calling Gemini API: {e}")


# ---------- Sidebar: upload + tag documents ----------
st.sidebar.header("📁 Your documents")
uploads = st.sidebar.file_uploader(
    "Upload PDF, DOCX or PPTX files",
    type=SUPPORTED_EXTENSIONS,
    accept_multiple_files=True,
)

file_tags = {}
for f in uploads or []:
    with st.sidebar.expander(f.name, expanded=True):
        kind = st.selectbox("Type", SOURCE_TYPES, key=f"type_{f.name}")
        subject = st.text_input("Subject (optional)", key=f"subject_{f.name}")
        chapter = st.text_input("Chapter (optional)", key=f"chapter_{f.name}")
    file_tags[f.name] = (kind, subject, chapter)

if st.sidebar.button("Build index from uploaded files", disabled=not uploads):
    try:
        with st.spinner("Reading and indexing your files..."):
            files = [(f.name, f.getvalue(), *file_tags[f.name]) for f in uploads]
            index, n_chunks = build_session_index(files, get_embeddings())
        st.session_state["session_index"] = index
        st.session_state["indexed_files"] = [(n, t[0]) for n, t in file_tags.items()]
        st.sidebar.success(f"Indexed {len(files)} file(s) into {n_chunks} chunks.")
    except Exception as e:
        st.sidebar.error(f"Could not build index: {type(e).__name__}: {e}")

if st.session_state.get("indexed_files"):
    st.sidebar.markdown("**Indexed files:**")
    for name, kind in st.session_state["indexed_files"]:
        st.sidebar.write(f"• {name} ({kind})")

builtin = load_builtin_index() if os.path.isdir("faiss_index") else None
use_builtin = False
if builtin is not None:
    use_builtin = st.sidebar.checkbox("Also search the built-in notes index", value=False)

k = st.sidebar.slider("Chunks to retrieve", 2, 8, 4)

# Which indexes will be searched
stores = []
if st.session_state.get("session_index") is not None:
    stores.append(st.session_state["session_index"])
if use_builtin:
    stores.append(builtin)

# Subject / chapter filters, built from the tags found in the indexes
subject_filter = chapter_filter = None
tag_pairs = collect_tags(stores)
subjects = sorted({s for s, _ in tag_pairs if s})
if subjects or any(c for _, c in tag_pairs):
    st.sidebar.markdown("**Filter by subject / chapter**")
    picked = st.sidebar.selectbox("Subject", ["All subjects"] + subjects)
    subject_filter = None if picked == "All subjects" else picked
    chapters = sorted({c for s, c in tag_pairs if c and (subject_filter is None or s == subject_filter)})
    picked = st.sidebar.selectbox("Chapter", ["All chapters"] + chapters)
    chapter_filter = None if picked == "All chapters" else picked

# ---------- Main: choose a mode, then ask ----------
mode = st.radio(
    "What do you want to do?",
    list(MODES),
    format_func=lambda m: MODES[m]["label"],
    horizontal=True,
)

marks = None
if mode == "solve":
    marks = st.selectbox("Marks for this question (sets the answer length)", ["Not specified", "2", "5", "10"])
    marks = None if marks == "Not specified" else marks

question = st.text_area(MODES[mode]["label"], placeholder=MODES[mode]["placeholder"], height=100)
ask = st.button("Generate", type="primary")

if ask:
    docs = []
    if not question.strip():
        st.warning("Please enter something first.")
    elif not stores:
        st.warning("Upload files and click 'Build index from uploaded files' first.")
    else:
        # Search every index, then keep the best k results overall (lower score = closer match).
        tag_filter = {}
        if subject_filter:
            tag_filter["subject"] = subject_filter
        if chapter_filter:
            tag_filter["chapter"] = chapter_filter

        results = []
        for store in stores:
            extra = {"filter": tag_filter, "fetch_k": max(store.index.ntotal, k)} if tag_filter else {}
            results.extend(store.similarity_search_with_score(question, k=k, **extra))
        results.sort(key=lambda pair: pair[1])
        docs = [doc for doc, _ in results[:k]]
        if not docs:
            st.warning("No chunks match the selected subject/chapter. Try 'All subjects' or 'All chapters'.")

    if docs:
        last = {"question": question, "mode": mode, "docs": docs, "text": None, "answers": None}
        st.session_state["last"] = last

        left, right = st.columns([1, 1.5])
        with left:
            show_sources(docs)
        with right:
            st.markdown(f"### {MODES[mode]['title']}")
            try:
                last["text"] = st.write_stream(generate_answer(question, docs, mode, marks))
            except Exception as e:
                st.error(f"Error calling Gemini API: {e}")
            show_extras(last)

elif st.session_state.get("last"):
    # Re-draw the previous result, so the 'show answers' button keeps working.
    last = st.session_state["last"]
    left, right = st.columns([1, 1.5])
    with left:
        show_sources(last["docs"])
    with right:
        st.markdown(f"### {MODES[last['mode']]['title']}")
        st.markdown(last["text"] or "")
        show_extras(last)
