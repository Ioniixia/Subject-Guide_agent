"""The agent pipeline as plain functions, so the Streamlit app and the API share one implementation.
Router -> Retriever -> Tutor -> Reviewer."""
from dataclasses import dataclass, field

import core
import db
from agent import TOOLS, AgentRun, check_citations, logger, route
from generate_answer import describe_source, generate_answer, generate_quiz

MANUAL_TOOL = {
    "qa": "answer_question",
    "solve": "solve_problem",
    "learn": "teach_topic",
    "revise": "teach_topic",
}


@dataclass
class Prepared:
    run: AgentRun
    message: str
    tool: str
    mode: str                      # qa, solve, learn, quiz or past
    marks: str | None
    docs: list
    related: list
    plan: dict | None              # the router's decision (agent mode only)
    subject: str
    chapter: str
    revise: bool = False
    extra: dict = field(default_factory=dict)


def doc_to_dict(doc, n=None):
    meta = doc.metadata or {}
    return {
        "n": n,
        "label": describe_source(doc),
        "source": meta.get("source"),
        "source_type": meta.get("source_type"),
        "subject": meta.get("subject"),
        "chapter": meta.get("chapter"),
        "page": meta.get("page"),
        "slide": meta.get("slide"),
        "question_no": meta.get("question_no"),
        "year": meta.get("year"),
        "marks": meta.get("marks"),
        "text": doc.page_content,
    }


def prepare(message, stores, *, ui_mode="agent", k=4, subject=None, chapter=None, source_types=None,
            use_llm_router=True, marks=None) -> Prepared:
    """Router and Retriever steps. Raises if one of them fails (the run is logged first)."""
    run = AgentRun(message, ui_mode)
    tag_filter = {}
    if subject:
        tag_filter["subject"] = subject
    if chapter:
        tag_filter["chapter"] = chapter
    subject_only = {"subject": subject} if subject else {}
    present = sorted({t for _, _, t in core.collect_tags(stores) if t})
    types = list(source_types) if source_types else present

    plan = None
    try:
        if ui_mode == "agent":
            with run.step("Router", "choose tool") as s:
                plan = route(message, use_llm=use_llm_router)
                s["detail"] = f"{plan['tool']} (by {plan['source']}): {plan['reason']}"
            tool, marks = plan["tool"], plan["marks"]
        else:
            tool = MANUAL_TOOL[ui_mode]
        mode = TOOLS[tool]["mode"]
        run.tool = tool

        with run.step("Retriever", "search the index") as s:
            if mode == "past":
                docs = [d for d, _ in core.search_docs(stores, message, 5, subject_only, ["question_paper"])[:5]]
            else:
                docs = core.retrieve(stores, message, k, tag_filter, types, present, per_type=(mode in ("learn", "quiz")))
            s["detail"] = f"{len(docs)} chunks"

        related = []
        if mode in ("qa", "learn") and "question_paper" in present:
            related = [d for d, _ in core.search_docs(stores, message, 3, subject_only, ["question_paper"])[:3]]
        if mode == "past":
            related = docs
    except Exception:
        run.finish()
        raise

    topic_subject, topic_chapter = core.topic_of(docs, chapter, subject)
    return Prepared(run, message, tool, mode, marks, docs, related, plan, topic_subject, topic_chapter,
                    revise=(ui_mode == "revise"))


def answer_stream(p: Prepared):
    """The Tutor's answer, streamed. Timing and errors are recorded in the run."""
    return p.run.track_stream("Tutor", p.tool, generate_answer(p.message, p.docs, p.mode, p.marks))


def write_quiz(p: Prepared, topic_text=""):
    with p.run.step("Tutor", "write quiz") as s:
        quiz = generate_quiz(p.message, p.docs, topic_text)
        s["detail"] = f"{len(quiz)} questions"
    return quiz


def finalize(p: Prepared, answer: str, user="guest"):
    """Reviewer step, history entry and run log. Returns (citations_ok, message)."""
    ok, message = True, ""
    if answer and p.mode in ("qa", "solve", "learn"):
        with p.run.step("Reviewer", "check citations") as s:
            ok, message = check_citations(answer, len(p.docs))
            s["detail"] = message
            if not ok:
                s["status"] = "warning"
    try:
        db.add_history(user, p.message, p.tool, p.run.id)
    except Exception as e:  # history must never break an answer
        logger.warning("Could not save history: %s", e)
    p.run.finish()
    return ok, message


def ask(message, stores, *, user="guest", **options) -> dict:
    """Whole pipeline without streaming, for the API."""
    p = prepare(message, stores, **options)
    if not p.docs:
        p.run.finish()
        return {"run_id": p.run.id, "tool": p.tool, "reason": (p.plan or {}).get("reason", ""), "mode": p.mode,
                "answer": "", "quiz": None, "sources": [], "related": [], "citations_ok": True,
                "steps": p.run.steps, "notice": "No chunks matched the question and filters."}
    answer, quiz = "", None
    try:
        if p.mode == "quiz":
            quiz = write_quiz(p)
        elif p.mode != "past":
            answer = "".join(answer_stream(p))
    except Exception:
        p.run.finish()
        raise
    ok, message = finalize(p, answer, user)
    return {
        "run_id": p.run.id,
        "tool": p.tool,
        "reason": (p.plan or {}).get("reason", ""),
        "mode": p.mode,
        "answer": answer,
        "quiz": quiz,
        "sources": [doc_to_dict(d, i) for i, d in enumerate(p.docs, 1)],
        "related": [doc_to_dict(d, i) for i, d in enumerate(p.related, 1)],
        "citations_ok": ok,
        "notice": "" if ok else message,
        "steps": p.run.steps,
    }
