# Subject Guide & Question Bank AI Agent

An AI study assistant for students. It reads your course material (PDF, DOCX, PPTX), then explains topics, answers questions, solves problems, and quizzes you, using only that material, with the source of every answer cited.

**Live demo:**  https://subject-guideagent-nvmsyd5d2gmqcemdjpjhgz.streamlit.app/

## Features
- **Study modes**
  - *Ask a question:* a short answer based on your notes
  - *Solve a problem:* step-by-step working (given, concepts needed, steps, final answer)
  - *Learn a topic:* a lesson that goes from theory to an example to practice
- **Test yourself:** a short quiz generated from the retrieved material
- **Related past questions:** exam questions that match your topic, with a *Solve this question* button
- **Filters:** limit answers by subject, chapter, and source type (notes, textbook, lab manual, question paper)
- **Marks field:** sets the answer length to match a 2, 5, or 10 mark exam question
- **Source citations:** inline [1], [2] references showing the file, chapter, and slide or page
- **Multi-file upload:** add your own PDF, DOCX, and PPTX files and tag each one
- **Built-in index:** AIML Units 1 to 3 (introduction to AI, AI frameworks, machine learning basics), plus a sample textbook chapter, a sample lab manual, and sample question papers

## How it works
1. Files are loaded by type: slides are read one slide at a time, and question papers are split so each question is its own chunk (with question number, year, and marks).
2. Every chunk is tagged with its source type, subject, chapter, and page or slide.
3. Chunks are embedded with `all-MiniLM-L6-v2` and stored in a FAISS index.
4. For each request, the most relevant chunks are retrieved, optionally filtered by subject, chapter, and source type.
5. Gemini writes the answer, lesson, or quiz using only those chunks, in the chosen study mode.

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
The course slides are not included in this repository. The sample question papers, textbook chapter, and lab manual in `data/` are examples written for this project, not real exam papers. To build the index from your own files:
1. Put your PDF, DOCX, or PPTX files in `data/`.
2. Edit the `file_configs` list at the bottom of `src/build_index.py`. Give each file its path, `source_type`, `subject`, and `chapter`. For question papers use `source_type: "question_paper"` and add a `year`, and number the questions as `Q1.`, `Q2.`, and so on.
3. Run `python src/build_index.py`.

## Project structure
```
app/           Streamlit app, study modes, quiz, and Gemini answer generation
src/           Document loading, chunking, tagging, and FAISS index code
data/          Sample study material
faiss_index/   Saved built-in index
```

## Team
Ioniixia and yitong2907