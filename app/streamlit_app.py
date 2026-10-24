import os
import time

import streamlit as st

from generate_answer import describe_source, generate_answer, generate_practice_answers, generate_quiz
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
    """Return the set of (subject, chapter, source_type) found in the chunks of the given indexes."""
    found = set()
    for store in stores:
        for doc in store.docstore._dict.values():
            meta = doc.metadata or {}
            found.add((meta.get("subject"), meta.get("chapter"), meta.get("source_type")))
    return found


def make_filter(wanted: dict):
    """Metadata filter for FAISS. A list value means 'any of these'."""

    def matches(meta):
        for key, want in wanted.items():
            have = meta.get(key)
            if isinstance(want, (list, set, tuple)):
                if have not in want:
                    return False
            elif have != want:
                return False
        return True

    return matches


def search_docs(question, k, tag_filter, source_types=None):
    """Search every selected index; returns (doc, score) pairs sorted best first (lower score = closer)."""
    wanted = dict(tag_filter)
    if source_types:
        wanted["source_type"] = source_types
    results = []
    for store in stores:
        extra = {"filter": make_filter(wanted), "fetch_k": max(store.index.ntotal, k)} if wanted else {}
        results.extend(store.similarity_search_with_score(question, k=k, **extra))
    results.sort(key=lambda pair: pair[1])
    return results


def retrieve(question, k, tag_filter, types, all_types, per_type):
    """Pick the best chunks. In 'per_type' mode every source type contributes, so a lesson
    can combine notes, textbook, lab manual and past papers."""
    if per_type and len(types) > 1:
        share = max(1, round(k / len(types)))
        results = []
        for source_type in types:
            results.extend(search_docs(question, share, tag_filter, [source_type])[:share])
    else:
        subset = types if set(types) != set(all_types) else None
        results = search_docs(question, k, tag_filter, subset)[:k]

    seen, docs = set(), []
    for doc, _ in sorted(results, key=lambda pair: pair[1]):
        meta = doc.metadata or {}
        key = (meta.get("source"), meta.get("page"), meta.get("slide"), doc.page_content[:80])
        if key not in seen:
            seen.add(key)
            docs.append(doc)
    return docs


def queue_solve(question_text):
    """Button callback: switch to 'Solve a problem' and run it on this question."""
    st.session_state["mode"] = "solve"
    st.session_state["question"] = question_text
    st.session_state["auto_run"] = True


def show_sources(docs):
    st.markdown("### 🔍 Source chunks")
    for i, doc in enumerate(docs, 1):
        with st.expander(f"[{i}] {describe_source(doc)}", expanded=(i == 1)):
            st.write(doc.page_content)


def show_quiz(last):
    """Assessment step: a short multiple-choice quiz about the lesson."""
    st.markdown("### 🧪 Test yourself")
    if last.get("quiz") is None:
        if st.button("Start a 3-question quiz", key="start_quiz"):
            with st.spinner("Writing your quiz..."):
                try:
                    last["quiz"] = generate_quiz(last["question"], last["docs"], last["text"])
                    last["quiz_id"] = int(time.time())
                    last["quiz_picks"] = None
                except Exception as e:
                    st.error(f"Could not make a quiz: {e}")
        if last.get("quiz") is None:
            return

    quiz, quiz_id = last["quiz"], last["quiz_id"]
    with st.form(f"quiz_form_{quiz_id}"):
        for i, q in enumerate(quiz):
            st.markdown(f"**{i + 1}. {q['question']}**")
            st.radio("Choose one", q["options"], index=None, key=f"quiz_{quiz_id}_{i}", label_visibility="collapsed")
        submitted = st.form_submit_button("Check my answers")
    if submitted:
        last["quiz_picks"] = [st.session_state.get(f"quiz_{quiz_id}_{i}") for i in range(len(quiz))]

    picks = last.get("quiz_picks")
    if picks is not None:
        score = sum(1 for q, p in zip(quiz, picks) if p == q["options"][q["answer_index"]])
        st.success(f"Your score: {score} / {len(quiz)}")
        for i, (q, p) in enumerate(zip(quiz, picks), 1):
            right = q["options"][q["answer_index"]]
            if p == right:
                st.markdown(f"✅ **{i}.** Correct. {q['explanation']}")
            else:
                st.markdown(f"❌ **{i}.** The answer is **{right}**. {q['explanation']}")


def show_extras(last):
    """Extra steps for the 'Learn a topic' flow: practice answers, then a quiz."""
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
    show_quiz(last)


def show_related(last):
    """Past-paper questions that match the topic, each with a one-click solve button."""
    related = last.get("related") or []
    if not related:
        return
    st.markdown("### 📝 Related past questions")
    for i, doc in enumerate(related, 1):
        with st.expander(describe_source(doc), expanded=(i == 1)):
            st.write(doc.page_content)
            st.button("Solve this question", key=f"solve_{i}", on_click=queue_solve, args=(doc.page_content,))


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

# Filters, built from the tags found in the indexes
tags = collect_tags(stores)
subject_filter = chapter_filter = None
subjects = sorted({s for s, _, _ in tags if s})
present_types = sorted({t for _, _, t in tags if t})
selected_types = list(present_types)

if subjects or any(c for _, c, _ in tags) or present_types:
    st.sidebar.markdown("**Filters**")
if subjects or any(c for _, c, _ in tags):
    picked = st.sidebar.selectbox("Subject", ["All subjects"] + subjects)
    subject_filter = None if picked == "All subjects" else picked
    chapters = sorted({c for s, c, _ in tags if c and (subject_filter is None or s == subject_filter)})
    picked = st.sidebar.selectbox("Chapter", ["All chapters"] + chapters)
    chapter_filter = None if picked == "All chapters" else picked
if present_types:
    selected_types = st.sidebar.multiselect("Source types", present_types, default=present_types)

# ---------- Main: choose a mode, then ask ----------
mode = st.radio(
    "What do you want to do?",
    list(MODES),
    format_func=lambda m: MODES[m]["label"],
    horizontal=True,
    key="mode",
)

marks = None
if mode == "solve":
    marks = st.selectbox("Marks for this question (sets the answer length)", ["Not specified", "2", "5", "10"])
    marks = None if marks == "Not specified" else marks

st.caption(MODES[mode]["placeholder"])
question = st.text_area("Your question, problem or topic", height=100, key="question")
ask = st.button("Generate", type="primary")
if st.session_state.pop("auto_run", False):
    ask = True  # set by the 'Solve this question' buttons

if ask:
    docs = []
    if not question.strip():
        st.warning("Please enter something first.")
    elif not stores:
        st.warning("Upload files and click 'Build index from uploaded files' first.")
    elif present_types and not selected_types:
        st.warning("Select at least one source type.")
    else:
        tag_filter = {}
        if subject_filter:
            tag_filter["subject"] = subject_filter
        if chapter_filter:
            tag_filter["chapter"] = chapter_filter

        docs = retrieve(question, k, tag_filter, selected_types, present_types, per_type=(mode == "learn"))
        if not docs:
            st.warning("No chunks match the selected filters. Try 'All subjects', 'All chapters' or more source types.")

    if docs:
        related = []
        if mode in ("qa", "learn") and "question_paper" in present_types:
            related = [d for d, _ in search_docs(question, 3, tag_filter, ["question_paper"])[:3]]

        last = {
            "question": question, "mode": mode, "docs": docs, "related": related,
            "text": None, "answers": None, "quiz": None,
        }
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
            show_related(last)

elif st.session_state.get("last"):
    # Re-draw the previous result, so the buttons and the quiz keep working.
    last = st.session_state["last"]
    left, right = st.columns([1, 1.5])
    with left:
        show_sources(last["docs"])
    with right:
        st.markdown(f"### {MODES[last['mode']]['title']}")
        st.markdown(last["text"] or "")
        show_extras(last)
        show_related(last)
