"""Weak-area detection and the day-by-day study plan. Plain Python, easy to test."""
import math
from datetime import date, timedelta


def weak_areas(rows, min_attempts=2, threshold=0.6):
    """Chapters with enough attempts and accuracy below the threshold, weakest first."""
    weak = [
        r for r in rows
        if r["chapter"] != "General" and r["attempts"] >= min_attempts and r["total"] > 0 and r["accuracy"] < threshold
    ]
    return sorted(weak, key=lambda r: r["accuracy"])


def _allocate(chapters, weak, study_days):
    """Days per chapter: weak chapters get double weight; every chapter gets at least one day."""
    weights = {c: 2 if c in weak else 1 for c in chapters}
    total = sum(weights.values())
    raw = {c: study_days * weights[c] / total for c in chapters}
    days = {c: max(1, math.floor(raw[c])) for c in chapters}
    while sum(days.values()) < study_days:
        c = max(chapters, key=lambda x: raw[x] - days[x])
        days[c] += 1
    while sum(days.values()) > study_days:
        c = min((x for x in chapters if days[x] > 1), key=lambda x: raw[x] - days[x])
        days[c] -= 1
    return days


def build_study_plan(chapters, exam_date, hours_per_day=2, weak=(), start=None):
    """One entry per day from today until the day before the exam."""
    start = start or date.today()
    total_days = (exam_date - start).days
    if total_days < 1:
        raise ValueError("The exam date must be in the future.")
    if total_days > 365:
        raise ValueError("Choose an exam date within the next year.")
    chapters = list(dict.fromkeys(chapters))
    if not chapters:
        raise ValueError("Choose at least one chapter.")
    weak = set(weak)

    revision_days = 2 if total_days >= 8 else 1 if total_days >= 3 else 0
    study_days = total_days - revision_days

    blocks = []  # each block is one day: (focus text, tasks)
    if study_days >= len(chapters):
        alloc = _allocate(chapters, weak, study_days)
        for chapter in chapters:
            n = alloc[chapter]
            for j in range(n):
                tasks = []
                if j == 0:
                    tasks += [f"Read the lesson on {chapter}", "Take the quiz"]
                else:
                    tasks += [f"Practise past-paper questions on {chapter}"]
                if chapter in weak and j > 0:
                    tasks += ["Redo the questions you missed (weak area)"]
                if n >= 2 and j == n - 1:
                    tasks += ["Take the quiz again and compare your score"]
                label = chapter + (" (weak area)" if chapter in weak else "")
                blocks.append((label, tasks))
    else:
        ordered = sorted(chapters, key=lambda c: (c not in weak, chapters.index(c)))
        per_day = math.ceil(len(ordered) / study_days)
        for i in range(0, len(ordered), per_day):
            group = ordered[i:i + per_day]
            tasks = [f"Skim {c} and do 2 past-paper questions" for c in group]
            blocks.append((", ".join(group), tasks))

    weak_list = sorted(weak)
    extra = total_days - len(blocks)  # revision days, plus any study days left unused
    for i in range(extra):
        last = i == extra - 1
        if last and revision_days >= 1:
            blocks.append(("Final revision", ["Light revision of your notes", "Quiz yourself on weak topics", "Rest well before the exam"]))
        elif weak_list:
            blocks.append(("Revise weak areas: " + ", ".join(weak_list), ["Review the lessons for these topics", "Redo past-paper questions you missed"]))
        else:
            blocks.append(("Mixed revision", ["Mixed practice from past papers", "Take a quiz on all chapters"]))

    return [
        {"day": i + 1, "date": (start + timedelta(days=i)).isoformat(), "focus": focus, "tasks": tasks, "hours": hours_per_day}
        for i, (focus, tasks) in enumerate(blocks)
    ]
