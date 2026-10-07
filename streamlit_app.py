import os

import streamlit as st

from generate_answer import describe_source, generate_answer
from session_index import SOURCE_TYPES, SUPPORTED_EXTENSIONS, build_session_index

st.set_page_config(page_title="Academic Subject Guide AI", page_icon="📚", layout="wide")
st.title("📚 Academic Subject Guide AI")
st.caption("Upload your study material, then ask a question about it.")


@st.cache_resource(show_spinner="Loading embedding model (first time only)...")
def get_embeddings():
    from langchain_community.embeddings import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


@st.cache_resource(show_spinner="Loading built-in notes index...")
def load_builtin_index():
    """Person 1's saved index (faiss_index/), if it exists next to this file."""
    if not os.path.isdir("faiss_index"):
        return None
    from langchain_community.vectorstores import FAISS

    return FAISS.load_local("faiss_index", get_embeddings(), allow_dangerous_deserialization=True)


# ---------- Sidebar: upload + tag documents ----------
st.sidebar.header("📁 Your documents")
uploads = st.sidebar.file_uploader(
    "Upload PDF, DOCX or PPTX files",
    type=SUPPORTED_EXTENSIONS,
    accept_multiple_files=True,
)

file_types = {}
for f in uploads or []:
    file_types[f.name] = st.sidebar.selectbox(f"Type of {f.name}", SOURCE_TYPES, key=f"type_{f.name}")

if st.sidebar.button("Build index from uploaded files", disabled=not uploads):
    try:
        with st.spinner("Reading and indexing your files..."):
            files = [(f.name, f.getvalue(), file_types[f.name]) for f in uploads]
            index, n_chunks = build_session_index(files, get_embeddings())
        st.session_state["session_index"] = index
        st.session_state["indexed_files"] = [(n, t) for n, t in file_types.items()]
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
    use_builtin = st.sidebar.checkbox("Also search the built-in notes index", value=True)

k = st.sidebar.slider("Chunks to retrieve", 2, 8, 4)

# ---------- Main: question + answer ----------
question = st.text_input("Ask a question", placeholder="e.g., Explain 2NF with an example")
ask = st.button("Generate answer", type="primary")

if ask:
    stores = []
    if st.session_state.get("session_index") is not None:
        stores.append(st.session_state["session_index"])
    if use_builtin:
        stores.append(builtin)

    if not question.strip():
        st.warning("Please enter a question.")
    elif not stores:
        st.warning("Upload files and click 'Build index from uploaded files' first.")
    else:
        # Search every index, then keep the best k results overall (lower score = closer match).
        results = []
        for store in stores:
            results.extend(store.similarity_search_with_score(question, k=k))
        results.sort(key=lambda pair: pair[1])
        docs = [doc for doc, _ in results[:k]]

        left, right = st.columns([1, 1.5])
        with left:
            st.markdown("### 🔍 Source chunks")
            for i, doc in enumerate(docs, 1):
                with st.expander(f"[{i}] {describe_source(doc)}", expanded=(i == 1)):
                    st.write(doc.page_content)
        with right:
            st.markdown("### 🤖 Answer")
            try:
                st.write_stream(generate_answer(question, docs))
            except Exception as e:
                st.error(f"Error calling Gemini API: {e}")
