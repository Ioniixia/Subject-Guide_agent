"""Small SQLite store for history, feedback and progress. Uses only the standard library."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

DB_PATH = os.getenv("APP_DB", os.path.join("data", "app.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, user TEXT, question TEXT, tool TEXT, run_id TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, user TEXT, run_id TEXT, rating TEXT, comment TEXT
);
CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, user TEXT, subject TEXT, chapter TEXT,
    kind TEXT, score REAL, total REAL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect():
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def add_history(user, question, tool, run_id):
    with closing(_connect()) as conn, conn:
        conn.execute("INSERT INTO history (ts, user, question, tool, run_id) VALUES (?,?,?,?,?)",
                     (_now(), user, question[:300], tool, run_id))


def list_history(user, limit=10):
    with closing(_connect()) as conn:
        rows = conn.execute("SELECT ts, question, tool, run_id FROM history WHERE user=? ORDER BY id DESC LIMIT ?",
                            (user, limit)).fetchall()
    return [dict(r) for r in rows]


def add_feedback(user, run_id, rating, comment=""):
    if rating not in ("up", "down"):
        raise ValueError("rating must be 'up' or 'down'")
    with closing(_connect()) as conn, conn:
        conn.execute("INSERT INTO feedback (ts, user, run_id, rating, comment) VALUES (?,?,?,?,?)",
                     (_now(), user, run_id, rating, comment[:500]))


def add_progress(user, subject, chapter, kind, score, total):
    """Save one result. kind is 'quiz' or 'practice'; score and total are numbers (e.g. 2 of 3)."""
    if total <= 0 or score < 0 or score > total:
        raise ValueError("score must be between 0 and total, and total must be above 0")
    with closing(_connect()) as conn, conn:
        conn.execute("INSERT INTO progress (ts, user, subject, chapter, kind, score, total) VALUES (?,?,?,?,?,?,?)",
                     (_now(), user, subject or "General", chapter or "General", kind, score, total))


def chapter_summary(user):
    """One row per subject and chapter: attempts, points earned, points possible, accuracy."""
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT subject, chapter, COUNT(*) AS attempts, SUM(score) AS earned, SUM(total) AS total "
            "FROM progress WHERE user=? GROUP BY subject, chapter ORDER BY subject, chapter", (user,)
        ).fetchall()
    return [
        {"subject": r["subject"], "chapter": r["chapter"], "attempts": r["attempts"],
         "earned": r["earned"], "total": r["total"],
         "accuracy": round(r["earned"] / r["total"], 3) if r["total"] else 0.0}
        for r in rows
    ]
