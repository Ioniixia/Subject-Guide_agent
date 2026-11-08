import datetime
import os
import time

import pandas as pd
import streamlit as st

import analytics
import core
import db
from agent import friendly_error
from agent_service import answer_stream, finalize, prepare, write_quiz
from generate_answer import describe_source, generate_answer, generate_practice_answers
from planner import build_study_plan, weak_areas
from prompts import MODES
from session_index import SOURCE_TYPES, SUPPORTED_EXTENSIONS, build_session_index

st.set_page_config(page_title="Academic Subject Guide AI", page_icon="📚", layout="wide")
st.title("📚 Academic Subject Guide AI")

MODE_OPTIONS = ["agent", "qa", "solve", "learn", "revise"]
MODE_LABELS = {
    "agent": "Ask anything (agent)",
    "qa": MODES["qa"]["label"],
    "solve": MODES["solve"]["label"],
    "learn": MODES["learn"]["label"],
    "revise": "Revise a topic (all-in-one)",
}
HINTS = {
    "agent": "Type what you need, e.g. 'Teach me 2NF', 'Solve Q3 from the 2023 paper', 'Quiz me on ACID' or 'Past questions on transactions'.",
    "qa": MODES["qa"]["placeholder"],
    "solve": MODES["solve"]["placeholder"],
    "learn": MODES["learn"]["placeholder"],
    "revise": "Enter a topic, e.g. Normalization. You get the lesson, practice answers, a quiz and related past questions in one go.",
}
TITLES = {**{m: MODES[m]["title"] for m in MODES}, "quiz": "🧪 Quiz", "past": "📝 Past questions"}
PAGES = ["Study", "Practice", "Progress", "Study plan"]


# ---------- Sidebar: user, upload + tag documents ----------
user = st.sidebar.text_input("Your name (keeps your progress separate)", value="guest", key="user").strip() or "guest"

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
            index, n_chunks = build_session_index(files, core.get_embeddings())
        st.session_state["session_index"] = index
        st.session_state["indexed_files"] = [(n, t[0]) for n, t in file_tags.items()]
        st.sidebar.success(f"Indexed {len(files)} file(s) into {n_chunks} chunks.")
    except Exception as e:
        st.sidebar.error(f"Could not build index: {type(e).__name__}: {e}")

if st.session_state.get("indexed_files"):
    st.sidebar.markdown("**Indexed files:**")
    for name, kind in st.session_state["indexed_files"]:
        st.sidebar.write(f"• {name} ({kind})")

builtin = core.load_builtin_index() if os.path.isdir("faiss_index") else None
use_builtin = False
if builtin is not None:
    use_builtin = st.sidebar.checkbox("Also search the built-in notes index", value=False)

k = st.sidebar.slider("Chunks to retrieve", 2, 8, 4)
smart_routing = st.sidebar.checkbox("Smart routing (Gemini picks the tool)", value=True)

# Which indexes will be searched
stores = []
if st.session_state.get("session_index") is not None:
    stores.append(st.session_state["session_index"])
if use_builtin:
    stores.append(builtin)

# Filters, built from the tags found in the indexes
tags = core.collect_tags(stores)
subject_filter = chapter_filter = None
subjects = sorted({s for s, _, _ in tags if s})
present_types = sorted({t for _, _, t in tags if t})
selected_types = list(present_types)

if subjects or any(c for _, c, _ in tags) or present_types:
    st.sidebar.markdown("**Filters**")
if subjects or any(c for _, c, _ in tags):
    picked = st.sidebar.selectbox("Subject", ["All subjects"] + subjects)
    subject_filter = None if picked == "All subjects" else picked
    chapters = core.list_chapters(stores, subject_filter)
    picked = st.sidebar.selectbox("Chapter", ["All chapters"] + chapters)
    chapter_filter = None if picked == "All chapters" else picked
if present_types:
    selected_types = st.sidebar.multiselect("Source types", present_types, default=present_types)

try:
    history = db.list_history(user, 8)
except Exception:
    history = []
if history:
    with st.sidebar.expander(f"🕘 Recent questions ({len(history)})"):
        for item in history:
            st.write(f"• {item['question'][:80]}  \n  _{item['tool']}_")


# ---------- Shared pieces ----------
def go_study(mode, question_text):
    """Button callback: open the Study page on a mode and run it."""
    st.session_state["page"] = "Study"
    st.session_state["mode"] = mode
    st.session_state["question"] = question_text
    st.session_state["auto_run"] = True


def queue_solve(question_text):
    go_study("solve", question_text)


def show_sources(docs):
    st.markdown("### 🔍 Source chunks")
    for i, doc in enumerate(docs, 1):
        with st.expander(f"[{i}] {describe_source(doc)}", expanded=(i == 1)):
            st.write(doc.page_content)


def save_feedback(last, rating):
    try:
        db.add_feedback(last["user"], last["run_id"], rating)
    except Exception:
        pass
    last["feedback"] = rating


def show_feedback(last):
    if not last.get("text") or last["mode"] == "past":
        return
    if last.get("feedback"):
        st.caption("Thanks for your feedback!")
        return
    up, down, _ = st.columns([1, 1, 8])
    up.button("👍", key="fb_up", on_click=save_feedback, args=(last, "up"), help="This answer helped")
    down.button("👎", key="fb_down", on_click=save_feedback, args=(last, "down"), help="This answer did not help")


def show_quiz(last):
    """Assessment step: a short multiple-choice quiz. The score is saved to your progress."""
    if last["mode"] != "quiz":
        st.markdown("### 🧪 Test yourself")
    if last.get("quiz") is None:
        if st.button("Start a 3-question quiz", key="start_quiz"):
            with st.spinner("Writing your quiz..."):
                try:
                    from generate_answer import generate_quiz

                    last["quiz"] = generate_quiz(last["question"], last["docs"], last["text"])
                    last["quiz_id"] = int(time.time())
                    last["quiz_picks"] = None
                except Exception as e:
                    st.error(f"Could not make a quiz. {friendly_error(e)}")
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
        if not last.get("quiz_saved"):
            try:
                db.add_progress(last["user"], last["subject"], last["chapter"], "quiz", score, len(quiz))
                last["quiz_saved"] = True
            except Exception:
                pass
        if last.get("quiz_saved"):
            st.caption(f"Saved to your progress under {last['chapter']}.")
        for i, (q, p) in enumerate(zip(quiz, picks), 1):
            right = q["options"][q["answer_index"]]
            if p == right:
                st.markdown(f"✅ **{i}.** Correct. {q['explanation']}")
            else:
                st.markdown(f"❌ **{i}.** The answer is **{right}**. {q['explanation']}")


def show_extras(last):
    """Extra steps after a lesson or quiz: practice answers, then the quiz."""
    if last["mode"] not in ("learn", "quiz") or not last.get("text"):
        return
    if last["mode"] == "learn":
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
                st.error(friendly_error(e))
    show_quiz(last)


def show_related(last):
    """Past-paper questions that match the topic, each with a one-click solve button."""
    related = last.get("related") or []
    if not related:
        return
    if last["mode"] != "past":
        st.markdown("### 📝 Related past questions")
    for i, doc in enumerate(related, 1):
        with st.expander(describe_source(doc), expanded=(i == 1)):
            st.write(doc.page_content)
            st.button("Solve this question", key=f"solve_{i}", on_click=queue_solve, args=(doc.page_content,))


def show_steps(last):
    """The agent's trace: which agent did what, and how long it took."""
    steps = last.get("steps") or []
    if not steps:
        return
    with st.expander(f"🧭 Agent steps ({len(steps)})", expanded=last.get("picked_by_agent", False)):
        st.dataframe(
            [
                {"Agent": s["agent"], "Action": s["action"], "Detail": s["detail"], "Time (ms)": s["ms"], "Status": s["status"]}
                for s in steps
            ],
            hide_index=True,
        )


# ---------- Page 1: Study ----------
def run_study(question, mode, marks):
    try:
        p = prepare(
            question, stores, ui_mode=mode, k=k, subject=subject_filter, chapter=chapter_filter,
            source_types=selected_types, use_llm_router=smart_routing, marks=marks,
        )
    except Exception as e:
        st.error(friendly_error(e))
        return
    if not p.docs:
        p.run.finish()
        if p.mode == "past":
            st.warning("No past-paper questions found. Index a question paper first, or relax the filters.")
        else:
            st.warning("No chunks match the selected filters. Try 'All subjects', 'All chapters' or more source types.")
        return

    last = {
        "question": question, "mode": p.mode, "tool": p.tool, "docs": p.docs, "related": p.related,
        "text": None, "answers": None, "quiz": None, "steps": p.run.steps, "run_id": p.run.id,
        "picked_by_agent": p.plan is not None, "subject": p.subject, "chapter": p.chapter, "user": user,
    }
    st.session_state["last"] = last

    left, right = st.columns([1, 1.5])
    with left:
        show_sources(p.docs)
    with right:
        st.markdown(f"### {TITLES[p.mode]}")
        try:
            if p.mode == "past":
                st.markdown("These past-paper questions match your topic:")
                last["text"] = "past questions"
            elif p.mode == "quiz":
                with st.spinner("Writing your quiz..."):
                    last["quiz"] = write_quiz(p)
                last["quiz_id"] = int(time.time())
                last["text"] = "Here is a short quiz on your topic."
                st.markdown(last["text"])
            else:
                last["text"] = st.write_stream(answer_stream(p))
                if p.revise:  # one-click revision: practice answers and a quiz as well
                    with st.spinner("Writing the practice answers and a quiz..."):
                        with p.run.step("Tutor", "practice answers"):
                            last["answers"] = "".join(generate_practice_answers(question, p.docs, last["text"]))
                        last["quiz"] = write_quiz(p, last["text"])
                        last["quiz_id"] = int(time.time())
        except Exception as e:
            st.error(friendly_error(e))
        ok, message = finalize(p, last["text"] or "", user)
        if not ok:
            st.caption(f"⚠️ {message} Check the source chunks before relying on this answer.")
        show_extras(last)
        show_related(last)
        show_feedback(last)
        show_steps(last)


def study_page():
    st.caption("Upload your study material, then just ask. The agent picks the right tool.")
    mode = st.radio("What do you want to do?", MODE_OPTIONS, format_func=lambda m: MODE_LABELS[m],
                    horizontal=True, key="mode")
    marks = None
    if mode == "solve":
        marks = st.selectbox("Marks for this question (sets the answer length)", ["Not specified", "2", "5", "10"])
        marks = None if marks == "Not specified" else marks

    st.caption(HINTS[mode])
    question = st.text_area("Your question, problem or topic", height=100, key="question")
    ask = st.button("Generate", type="primary")
    if st.session_state.pop("auto_run", False):
        ask = True  # set by the 'Solve this question' and 'Revise' buttons

    if ask:
        if not question.strip():
            st.warning("Please enter something first.")
        elif not stores:
            st.warning("Upload files and click 'Build index from uploaded files' first.")
        elif present_types and not selected_types:
            st.warning("Select at least one source type.")
        else:
            run_study(question, mode, marks)
    elif st.session_state.get("last"):
        # Re-draw the previous result, so the buttons and the quiz keep working.
        last = st.session_state["last"]
        left, right = st.columns([1, 1.5])
        with left:
            show_sources(last["docs"])
        with right:
            st.markdown(f"### {TITLES[last['mode']]}")
            if last["mode"] == "past":
                st.markdown("These past-paper questions match your topic:")
            else:
                st.markdown(last["text"] or "")
            show_extras(last)
            show_related(last)
            show_feedback(last)
            show_steps(last)


# ---------- Page 2: Practice ----------
def practice_rate(pr, doc, score):
    meta = doc.metadata or {}
    subject, chapter = meta.get("subject"), meta.get("chapter")
    if chapter in (None, core.ALL_UNITS):
        # Question papers cover every unit, so use the chapter of the notes that solved it
        topic_subject, chapter = core.topic_of(pr.get("solution_docs") or [], chapter_filter, subject_filter)
        subject = subject or topic_subject
    try:
        db.add_progress(user, subject or subject_filter or "General", chapter, "practice", score, 1)
    except Exception:
        pass
    pr["scores"].append(score)
    pr["i"] += 1
    pr["solution_for"] = None


def practice_page():
    st.subheader("Practise with past-paper questions")
    st.caption("Use the Subject and Chapter filters in the sidebar to choose what to practise.")
    if not stores:
        st.info("Upload files, or tick the built-in notes index, to find past-paper questions.")
        return

    if st.button("Start practice", type="primary"):
        questions = core.practice_questions(stores, subject_filter, chapter_filter, limit=15)
        if not questions:
            st.warning("No past-paper questions found for these filters.")
            st.session_state.pop("practice", None)
        else:
            st.session_state["practice"] = {"questions": questions, "i": 0, "solution_for": None, "solution": None, "scores": []}

    pr = st.session_state.get("practice")
    if not pr:
        return
    total = len(pr["questions"])
    if pr["i"] >= total:
        st.success(f"Practice finished! You scored {sum(pr['scores']):g} out of {total}. Your results are on the Progress page.")
        if st.button("Practise again"):
            st.session_state.pop("practice", None)
            st.rerun()
        return

    i = pr["i"]
    doc = pr["questions"][i]
    st.progress(i / total, text=f"Question {i + 1} of {total}")
    st.markdown(f"**{describe_source(doc)}**")
    st.write(doc.page_content)
    st.text_area("Your answer (try it first, then check the solution)", key=f"practice_answer_{i}", height=120)

    if pr["solution_for"] != i:
        if st.button("Show solution", key=f"show_solution_{i}"):
            note_types = [t for t in present_types if t != "question_paper"] or present_types
            notes = core.retrieve(stores, doc.page_content, k, {}, note_types, present_types, per_type=False)
            marks = str((doc.metadata or {}).get("marks") or "")
            marks = marks if marks in ("2", "5", "10") else None
            try:
                with st.spinner("Writing the solution from your notes..."):
                    pr["solution"] = "".join(generate_answer(doc.page_content, notes, "solve", marks))
                pr["solution_docs"] = notes
                pr["solution_for"] = i
                st.rerun()
            except Exception as e:
                st.error(friendly_error(e))
    else:
        st.markdown("### 🧮 Solution")
        st.markdown(pr["solution"])
        with st.expander("Sources used"):
            for n, d in enumerate(pr["solution_docs"], 1):
                st.markdown(f"**[{n}]** {describe_source(d)}")
        st.markdown("**How did you do?**")
        a, b, c = st.columns(3)
        a.button("✅ Got it", key=f"rate_full_{i}", on_click=practice_rate, args=(pr, doc, 1))
        b.button("🟡 Partly", key=f"rate_half_{i}", on_click=practice_rate, args=(pr, doc, 0.5))
        c.button("❌ Missed it", key=f"rate_zero_{i}", on_click=practice_rate, args=(pr, doc, 0))


# ---------- Page 3: Progress ----------
def progress_page():
    st.subheader(f"Progress for {user}")
    rows = db.chapter_summary(user)
    if not rows:
        st.info("No results yet. Finish a quiz or practise some questions, and your scores will show up here.")
    else:
        table = pd.DataFrame(rows)
        table["accuracy"] = (table["accuracy"] * 100).round(0)
        st.dataframe(
            table.rename(columns={"subject": "Subject", "chapter": "Chapter", "attempts": "Attempts",
                                  "earned": "Points", "total": "Out of", "accuracy": "Accuracy %"}),
            hide_index=True,
        )
        st.bar_chart(table.set_index("chapter")["accuracy"])

        weak = weak_areas(rows)
        st.markdown("### 🎯 Weak areas")
        if not weak:
            st.success("No weak areas yet. A chapter shows up here after 2 attempts with accuracy below 60%.")
        for w in weak:
            col1, col2 = st.columns([4, 1])
            col1.write(f"**{w['chapter']}** ({w['subject']}): {int(w['accuracy'] * 100)}% over {w['attempts']} attempts")
            col2.button("Revise", key=f"revise_{w['subject']}_{w['chapter']}", on_click=go_study, args=("revise", w["chapter"]))

    with st.expander("📈 System analytics (from the agent run log)"):
        stats = analytics.summarize()
        if not stats["total_runs"]:
            st.write("No runs logged yet.")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Runs", stats["total_runs"])
            c2.metric("Error rate", f"{int(stats['error_rate'] * 100)}%")
            c3.metric("Average time", f"{stats['avg_total_ms']} ms")
            st.bar_chart(pd.Series(stats["by_tool"], name="runs"))
            st.write("Average time per agent (ms):", stats["avg_step_ms"])
            if stats["recent_errors"]:
                st.write("Recent errors:", stats["recent_errors"])


# ---------- Page 4: Study plan ----------
def plan_page():
    st.subheader("Build a study plan")
    chapters = core.list_chapters(stores, subject_filter)
    if not chapters:
        st.info("Upload files or tick the built-in index with chapter tags, so the plan can use your chapters.")
        return
    today = datetime.date.today()
    exam_date = st.date_input("Exam date", value=today + datetime.timedelta(days=14), min_value=today + datetime.timedelta(days=1))
    hours = st.slider("Hours you can study per day", 1, 8, 2)
    chosen = st.multiselect("Chapters to cover", chapters, default=chapters)
    weak = [w["chapter"] for w in weak_areas(db.chapter_summary(user))]
    if weak:
        st.caption("Weak areas get extra days: " + ", ".join(weak))

    if st.button("Build my plan", type="primary"):
        try:
            st.session_state["plan"] = build_study_plan(chosen, exam_date, hours, weak)
        except ValueError as e:
            st.error(str(e))
            st.session_state.pop("plan", None)

    plan = st.session_state.get("plan")
    if plan:
        table = pd.DataFrame(
            [{"Day": d["day"], "Date": d["date"], "Focus": d["focus"], "Tasks": "; ".join(d["tasks"]), "Hours": d["hours"]} for d in plan]
        )
        st.dataframe(table, hide_index=True)
        st.download_button("Download plan (CSV)", table.to_csv(index=False), file_name="study_plan.csv", mime="text/csv")


# ---------- Dispatch ----------
page = st.radio("Page", PAGES, horizontal=True, key="page", label_visibility="collapsed")
if page == "Study":
    study_page()
elif page == "Practice":
    practice_page()
elif page == "Progress":
    progress_page()
else:
    plan_page()
