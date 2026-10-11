# Subject Guide & Question Bank AI Agent

An AI study assistant for students. It reads your course notes (PDF, DOCX, PPTX), then explains topics, answers questions, and solves problems using only that material, with the source of every answer cited.

**Live demo:** https://subject-guideagent-nvmsyd5d2gmqcemdjpjhgz.streamlit.app/

## Features
- **Three study modes**
  - *Ask a question:* a short answer based on your notes
  - *Solve a problem:* step-by-step working (given, concepts needed, steps, final answer)
  - *Learn a topic:* a lesson that goes from theory to an example to practice
- **Subject and chapter filter:** limit answers to one subject or chapter, for example AIML, Unit 3
- **Marks field:** sets the answer length to match a 2, 5, or 10 mark exam question
- **Source citations:** inline [1], [2] references showing the file, chapter, and slide or page
- **Multi-file upload:** add PDF, DOCX, and PPTX files and tag each one (notes, textbook, question paper, lab manual)
- **Built-in notes index:** AIML Units 1 to 3 (introduction to AI, AI frameworks, machine learning basics)

## How it works
1. Files are split into chunks, and each chunk is tagged with its source type, subject, chapter, and page or slide.
2. Chunks are embedded with `all-MiniLM-L6-v2` and stored in a FAISS index.
3. For each question, the most relevant chunks are retrieved, optionally filtered by subject and chapter.
4. Gemini writes the answer using only those chunks, in the chosen study mode.

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
Start the app:
```bash
python -m streamlit run app/streamlit_app.py
```

## Using your own notes
The course slides are not included in this repository. To build the index from your own files:
1. Put your PDF, DOCX, or PPTX files in `data/`.
2. Edit the `file_configs` list at the bottom of `src/build_index.py` with each file's path, source type, subject, and chapter.
3. Run `python src/build_index.py`.

## Project structure
```
app/           Streamlit app, study modes, and Gemini answer generation
src/           Document loading, chunking, tagging, and FAISS index code
data/          Study material (not committed)
faiss_index/   Saved built-in index
```

## Team
Ioniixia and yitong2907