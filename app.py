import streamlit as st
from llm import generate_academic_answer_stream

# Page Configuration
st.set_page_config(page_title="Academic Subject Guide AI", page_icon="📚", layout="wide")

st.title("📚 Academic Assistant & Question Solver")
st.caption("Track A - Week 1: Gemini LLM Integration & UI Prototype")

# Placeholder chunks simulating retriever output until Person 1 completes FAISS
PLACEHOLDER_CHUNKS = [
    "Database Normalization is the process of organizing data to reduce redundancy. Common forms include 1NF, 2NF, 3NF, and BCNF.",
    "First Normal Form (1NF) requires a primary key and atomic (indivisible) column values with no repeating groups.",
    "Second Normal Form (2NF) requires 1NF compliance and that all non-key attributes fully depend on the primary key, removing partial dependencies.",
    "Question 3 (2023 DBMS Paper): Explain 2NF with a student-course registration table example and show how to decompose it."
]


@st.cache_resource(show_spinner="Loading retriever (happens once when the app opens)...")
def load_vectorstore():
    """Load the embedding model and FAISS index once and reuse them."""
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain_community.vectorstores import FAISS

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    return FAISS.load_local(
        "faiss_index", embeddings, allow_dangerous_deserialization=True
    )


# Load the retriever as soon as the page opens, so ticking the box is instant.
# If the index is missing, the app still works with the placeholder chunks.
vectorstore = None
retriever_error = None
try:
    vectorstore = load_vectorstore()
except Exception as e:
    retriever_error = f"{type(e).__name__}: {e}"

st.sidebar.header("⚙️ Settings")
use_real_faiss = st.sidebar.checkbox("Use Real FAISS Retriever", value=False)
if retriever_error:
    st.sidebar.error(f"Could not load index: {retriever_error}")

query = st.text_input("Ask a Question or Past Paper Problem", placeholder="e.g., Explain Database Normalization or Q3 from 2023 paper...")
submit_btn = st.button("Generate Explanation", type="primary")

if submit_btn:
    if not query.strip():
        st.warning("Please enter a question.")
    else:
        # Toggle logic between placeholder context and real retriever
        if use_real_faiss and vectorstore is not None:
            try:
                results = vectorstore.similarity_search(query, k=3)
                retrieved_chunks = [d.page_content for d in results]
            except Exception as e:
                st.error(f"Retriever failed: {type(e).__name__}: {e}")
                retrieved_chunks = PLACEHOLDER_CHUNKS
        else:
            retrieved_chunks = PLACEHOLDER_CHUNKS

        col1, col2 = st.columns([1, 1.5])

        with col1:
            st.markdown("### 🔍 Retrieved Chunks")
            for i, chunk in enumerate(retrieved_chunks):
                with st.expander(f"Chunk {i+1}", expanded=(i == 0)):
                    st.write(chunk)

        with col2:
            st.markdown("### 🤖 Gemini Explanation")
            try:
                st.write_stream(
                    generate_academic_answer_stream(query, retrieved_chunks)
                )
            except Exception as e:
                st.error(f"Error calling Gemini API: {e}")
