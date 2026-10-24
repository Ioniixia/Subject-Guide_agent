"""Prompt instructions for each study mode."""

MODES = {
    "qa": {
        "label": "Ask a question",
        "title": "🤖 Answer",
        "placeholder": "e.g., Explain 2NF with an example",
        "max_tokens": 1000,
        "instructions": """
Answer the student's question using ONLY the numbered reference materials.
Cite the sources you use inline like [1] or [2]. If the materials do not cover something, say so.

Formatting:
- Use short headings and bullet points.
- Keep the answer under 300 words.
- Include one short example only if it helps.
""",
    },
    "solve": {
        "label": "Solve a problem",
        "title": "🧮 Step-by-step solution",
        "placeholder": "Paste an exam or textbook problem, e.g., Normalize this table to 3NF...",
        "max_tokens": 1400,
        "instructions": """
You are a patient tutor. Solve the student's problem step by step using ONLY the numbered reference materials.
If the student refers to a numbered question from a past paper (for example "Q3 from the 2023 paper"),
find that question in the reference materials and solve it.
Cite the source of the question and of every rule or definition you use inline like [1].
If the materials do not contain the question or the rules needed to solve it, say exactly what is missing
instead of guessing, and solve only the part the notes support.

Use exactly these sections:
## Given and goal
One or two lines restating what is known and what must be found.
## Concepts needed
The rules or definitions used, with citations.
## Step-by-step solution
Numbered steps. For each step, say what you do and why, with citations.
## Final answer
The result, clearly stated.
## Quick check
One line showing how the student can verify the result.
""",
    },
    "learn": {
        "label": "Learn a topic",
        "title": "📖 Lesson",
        "placeholder": "e.g., Second Normal Form",
        "max_tokens": 1600,
        "instructions": """
You are a friendly teacher. Teach the topic using the numbered reference materials, citing them inline like [1].
The materials can come from different source types (notes, textbook, lab_manual, question_paper), shown in each source label.
Combine them: use notes and textbooks for the theory, lab manuals for the worked example, and past-paper
questions for the practice questions. If the materials do not cover part of the topic, say so briefly.

Use exactly these sections:
## 1. Theory
A short explanation: definition, key ideas and why it matters. Keep it under 150 words.
## 2. Worked example
One complete example, solved step by step.
## 3. Practice
Three practice questions of increasing difficulty (easy, medium, hard).
If a question_paper source is available, base at least one question on it and cite it like [n].
Do NOT give the answers.
""",
    },
}

PRACTICE_ANSWERS_INSTRUCTIONS = """
Below is a lesson that ends with practice questions. Give the answers to the practice questions only.
For each question, write: the answer, then a one or two line explanation of how to get it.
Use the numbered reference materials where they help, citing them like [1].
"""

MARKS_GUIDE = {
    "2": "The problem is worth 2 marks: keep the solution to 2 or 3 short lines.",
    "5": "The problem is worth 5 marks: aim for about 150 words.",
    "10": "The problem is worth 10 marks: aim for about 300 words with clear headings.",
}

QUIZ_INSTRUCTIONS = """
Write {n} multiple-choice questions that test whether a student understood the lesson below.
Base them on the lesson and the numbered reference materials. Mix easy and harder questions.

Return ONLY a JSON list, with no other text. Each item must have exactly these keys:
- "question": the question text
- "options": a list of exactly 4 answer texts (no letters like A) or B) in front)
- "answer_index": the position of the correct option, from 0 to 3
- "explanation": one short sentence saying why that option is correct
"""
