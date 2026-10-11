# Subject Guide & Question Bank AI Agent

An AI study assistant for students. Upload your notes, textbooks, and lab manuals, ask a question, and get an answer built from your own material, with the source of each part cited.

**Live demo:** https://subject-guideagent-nvmsyd5d2gmqcemdjpjhgz.streamlit.app/

## Features
- Upload PDF, DOCX, and PPTX files and tag each one (notes, textbook, question paper, lab manual)
- Ask a question and get an answer based only on your documents
- Inline source citations like [1] and [2], with file name and page
- Also searches a built-in notes index

## How it works
1. Files are split into chunks and embedded with `all-MiniLM-L6-v2`.
2. The chunks are stored in a FAISS index.
3. For each question, the most relevant chunks are retrieved.
4. Gemini writes the answer using only those chunks.

## Tech stack
Python, LangChain, FAISS, Sentence-Transformers, Google Gemini, Streamlit

## Run locally
```bash
git clone https://github.com/Ioniixia/Subject-Guide_agent.git
cd Subject-Guide_agent
pip install -r requirements.txt
```
Create a `.env` file in the project root:
```
GEMINI_API_KEY=your_key_here
```
Build the built-in index and start the app:
```bash
python src/build_index.py
python -m streamlit run app/streamlit_app.py
```

## Project structure
```
app/           Streamlit app and Gemini answer generation
src/           Document loading, chunking, and FAISS index code
data/          Sample study material
faiss_index/   Saved built-in index
```

## Team
Ioniixia and yitong2907