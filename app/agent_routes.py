"""FastAPI routes for the study agents. Include them in the main app with:

    from agent_routes import router as agent_router
    app.include_router(agent_router)
"""
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import analytics
import core
import db
from agent import friendly_error
from agent_service import ask as run_ask
from agent_service import doc_to_dict
from generate_answer import generate_practice_answers, generate_quiz
from guardrails import GuardrailError, RateLimiter, check_message
from planner import build_study_plan, weak_areas

router = APIRouter()
limiter = RateLimiter()


class Filters(BaseModel):
    k: int = Field(4, ge=1, le=10)
    subject: Optional[str] = None
    chapter: Optional[str] = None
    source_types: Optional[list[str]] = None


class AskRequest(Filters):
    message: str = Field(..., min_length=1, max_length=2000)
    user: str = "guest"
    smart_routing: bool = True
    mode: str = Field("agent", pattern="^(agent|qa|solve|learn|revise)$")  # 'agent' lets the router choose
    marks: Optional[str] = Field(None, pattern="^(2|5|10)$")  # answer length when mode is 'solve'


class QuizRequest(Filters):
    topic: str = Field(..., min_length=1, max_length=500)


class PracticeAnswersRequest(Filters):
    topic: str
    lesson_text: str = Field(..., min_length=1)


class FeedbackRequest(BaseModel):
    run_id: str
    rating: str = Field(..., pattern="^(up|down)$")
    user: str = "guest"
    comment: str = ""


class ProgressRequest(BaseModel):
    user: str = "guest"
    subject: str = "General"
    chapter: str = "General"
    kind: str = Field("quiz", pattern="^(quiz|practice)$")
    score: float = Field(..., ge=0)
    total: float = Field(..., gt=0)


class StudyPlanRequest(BaseModel):
    exam_date: date
    hours_per_day: int = Field(2, ge=1, le=12)
    subject: Optional[str] = None
    chapters: Optional[list[str]] = None
    user: str = "guest"


class Source(BaseModel):
    n: Optional[int] = None
    label: str
    source: Optional[str] = None
    source_type: Optional[str] = None
    subject: Optional[str] = None
    chapter: Optional[str] = None
    page: Optional[Any] = None
    slide: Optional[Any] = None
    question_no: Optional[Any] = None
    year: Optional[Any] = None
    marks: Optional[Any] = None
    text: str


class Step(BaseModel):
    agent: str
    action: str
    detail: str = ""
    status: str
    ms: int


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    answer_index: int
    explanation: str


class AskResponse(BaseModel):
    run_id: str
    tool: str
    reason: str = ""
    mode: str
    answer: str
    quiz: Optional[list[QuizQuestion]] = None
    sources: list[Source]
    related: list[Source]
    citations_ok: bool
    fallback: bool = False  # true when Gemini failed and `answer` is built from the student's own notes
    notice: str = ""
    steps: list[Step]


class QuizResponse(BaseModel):
    questions: list[QuizQuestion]
    sources: list[Source]


class PracticeAnswersResponse(BaseModel):
    answers: str


class PastQuestionsResponse(BaseModel):
    questions: list[Source]


class SavedResponse(BaseModel):
    saved: bool


class HistoryItem(BaseModel):
    ts: str
    question: str
    tool: Optional[str] = None
    run_id: Optional[str] = None


class HistoryResponse(BaseModel):
    history: list[HistoryItem]


class ProgressRow(BaseModel):
    subject: str
    chapter: str
    attempts: int
    earned: float
    total: float
    accuracy: float


class ProgressResponse(BaseModel):
    chapters: list[ProgressRow]


class WeakAreasResponse(BaseModel):
    weak_areas: list[ProgressRow]


class PlanDay(BaseModel):
    day: int
    date: str
    focus: str
    tasks: list[str]
    hours: int


class StudyPlanResponse(BaseModel):
    plan: list[PlanDay]


class AnalyticsResponse(BaseModel):
    total_runs: int
    errors: int
    error_rate: float
    avg_total_ms: int
    by_tool: dict[str, int]
    avg_step_ms: dict[str, int]
    recent_errors: list[dict]


def _stores():
    stores = core.active_stores()
    if not stores:
        raise HTTPException(400, "No index is loaded. Upload files first, or add a built-in faiss_index/.")
    return stores


def _options(body: Filters):
    return dict(k=body.k, subject=body.subject, chapter=body.chapter, source_types=body.source_types)


def _gemini_error(e: Exception):
    return HTTPException(502, friendly_error(e))


def _guard(text: str) -> str:
    """Validate a student's text. A rejected message becomes a 400 with a message to show."""
    try:
        return check_message(text)
    except GuardrailError as e:
        raise HTTPException(400, str(e))


def _limit(user: str):
    if not limiter.allow(user or "guest"):
        raise HTTPException(429, "Too many requests. Please wait a moment and try again.")


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest):
    """The agent picks a tool, retrieves, answers and reviews. Returns answer, sources, steps and run_id."""
    _limit(body.user)
    message = _guard(body.message)
    stores = _stores()
    try:
        return run_ask(message, stores, user=body.user, use_llm_router=body.smart_routing,
                       ui_mode=body.mode, marks=body.marks, **_options(body))
    except GuardrailError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise _gemini_error(e)


@router.post("/quiz", response_model=QuizResponse)
def quiz(body: QuizRequest):
    """Three multiple-choice questions on a topic."""
    topic = _guard(body.topic)
    stores = _stores()
    present = sorted({t for _, _, t in core.collect_tags(stores) if t})
    tag_filter = {key: val for key, val in (("subject", body.subject), ("chapter", body.chapter)) if val}
    docs = core.retrieve(stores, topic, body.k, tag_filter, body.source_types or present, present, per_type=True)
    if not docs:
        raise HTTPException(404, "No study material matches this topic and filters.")
    try:
        return {"questions": generate_quiz(topic, docs, ""), "sources": [doc_to_dict(d, i) for i, d in enumerate(docs, 1)]}
    except Exception as e:
        raise _gemini_error(e)


@router.post("/practice-answers", response_model=PracticeAnswersResponse)
def practice_answers(body: PracticeAnswersRequest):
    """Answers to the practice questions at the end of a lesson."""
    topic = _guard(body.topic)
    stores = _stores()
    present = sorted({t for _, _, t in core.collect_tags(stores) if t})
    tag_filter = {key: val for key, val in (("subject", body.subject), ("chapter", body.chapter)) if val}
    docs = core.retrieve(stores, topic, body.k, tag_filter, body.source_types or present, present, per_type=True)
    try:
        return {"answers": "".join(generate_practice_answers(topic, docs, body.lesson_text))}
    except Exception as e:
        raise _gemini_error(e)


@router.get("/past-questions", response_model=PastQuestionsResponse)
def past_questions(subject: Optional[str] = None, chapter: Optional[str] = None, limit: int = 20):
    """Past-paper questions, newest first."""
    docs = core.practice_questions(_stores(), subject, chapter, limit=min(max(limit, 1), 100))
    return {"questions": [doc_to_dict(d, i) for i, d in enumerate(docs, 1)]}


@router.post("/feedback", response_model=SavedResponse)
def feedback(body: FeedbackRequest):
    """Thumbs up or down for one answer (use the run_id from /ask)."""
    db.add_feedback(body.user, body.run_id, body.rating, body.comment)
    return {"saved": True}


@router.get("/history", response_model=HistoryResponse)
def history(user: str = "guest", limit: int = 10):
    return {"history": db.list_history(user, min(max(limit, 1), 50))}


@router.post("/progress", response_model=SavedResponse)
def save_progress(body: ProgressRequest):
    """Save one quiz or practice result."""
    if body.score > body.total:
        raise HTTPException(422, "score cannot be above total")
    db.add_progress(body.user, body.subject, body.chapter, body.kind, body.score, body.total)
    return {"saved": True}


@router.get("/progress", response_model=ProgressResponse)
def get_progress(user: str = "guest"):
    """Accuracy per chapter."""
    return {"chapters": db.chapter_summary(user)}


@router.get("/weak-areas", response_model=WeakAreasResponse)
def get_weak_areas(user: str = "guest"):
    """Chapters with at least 2 attempts and accuracy below 60%, weakest first."""
    return {"weak_areas": weak_areas(db.chapter_summary(user))}


@router.post("/study-plan", response_model=StudyPlanResponse)
def study_plan(body: StudyPlanRequest):
    """A day-by-day plan from today to the exam, with extra time for weak areas."""
    chapters = body.chapters or core.list_chapters(core.active_stores(), body.subject)
    weak = [w["chapter"] for w in weak_areas(db.chapter_summary(body.user))]
    try:
        return {"plan": build_study_plan(chapters, body.exam_date, body.hours_per_day, weak)}
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics():
    """Summary of the agent run log: runs per tool, error rate and average times."""
    return analytics.summarize()
