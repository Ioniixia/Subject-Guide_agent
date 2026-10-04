import streamlit as st
from llm import generate_academic_answer

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

st.sidebar.header("⚙️ Settings")
use_real_faiss = st.sidebar.checkbox("Use Real FAISS Retriever", value=False)

query = st.text_input("Ask a Question or Past Paper Problem", placeholder="e.g., Explain Database Normalization or Q3 from 2023 paper...")
submit_btn = st.button("Generate Explanation", type="primary")

if submit_btn:
    if not query.strip():
        st.warning("Please enter a question.")
    else:
        # Toggle logic between placeholder context and real retriever module
        if use_real_faiss:
            try:
                from retriever import get_relevant_chunks
                retrieved_chunks = get_relevant_chunks(query, k=4)
            except ImportError:
                st.error("Retriever module not found. Falling back to placeholders.")
                retrieved_chunks = PLACEHOLDER_CHUNKS
        else:
            retrieved_chunks = PLACEHOLDER_CHUNKS

        col1, col2 = st.columns([1, 1.5])

        with col1:
            st.markdown("### 🔍 Retrieved Chunks")
            for i, chunk in enumerate(retrieved_chunks):
                with st.expander(f"Chunk {i+1}", expanded=(i==0)):
                    st.write(chunk)

        with col2:
            st.markdown("### 🤖 Gemini Explanation")
            with st.spinner("Generating answer..."):
                try:
                    answer = generate_academic_answer(query, retrieved_chunks)
                    st.markdown(answer)
                except Exception as e:
                    st.error(f"Error calling Gemini API: {e}")