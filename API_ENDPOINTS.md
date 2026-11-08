## API endpoints

Run the API locally from the repo root, then open the interactive docs at `http://localhost:8000/docs`:

```
uvicorn api_test:app --app-dir app --reload
```

All request and reply bodies are JSON. `user` is a simple name that keeps history and progress separate (default `guest`).

### Agent endpoints

| Method and path | Purpose | Main request fields | Main reply fields |
|---|---|---|---|
| `POST /ask` | The agent picks a tool, retrieves, answers and reviews | `message`, `mode` (`agent`, `qa`, `solve`, `learn`, `revise`), `marks` (`2`, `5`, `10`), `subject`, `chapter`, `source_types`, `k`, `smart_routing`, `user` | `run_id`, `tool`, `reason`, `answer`, `quiz`, `sources`, `related`, `citations_ok`, `steps` |
| `POST /quiz` | Three multiple-choice questions on a topic | `topic`, `subject`, `chapter`, `source_types`, `k` | `questions`, `sources` |
| `POST /practice-answers` | Answers to the practice questions at the end of a lesson | `topic`, `lesson_text`, filters | `answers` |
| `GET /past-questions` | Past-paper questions, newest first | query: `subject`, `chapter`, `limit` | `questions` |
| `POST /feedback` | Thumbs up or down for one answer | `run_id`, `rating` (`up` or `down`), `user`, `comment` | `saved` |
| `GET /history` | Recent questions | query: `user`, `limit` | `history` |

### Progress and planning

| Method and path | Purpose | Main request fields | Main reply fields |
|---|---|---|---|
| `POST /progress` | Save one quiz or practice result | `user`, `subject`, `chapter`, `kind` (`quiz` or `practice`), `score`, `total` | `saved` |
| `GET /progress` | Accuracy per chapter | query: `user` | `chapters` |
| `GET /weak-areas` | Chapters with at least 2 attempts and accuracy below 60% | query: `user` | `weak_areas` |
| `POST /study-plan` | Day-by-day plan from today to the exam, with extra days for weak areas | `exam_date` (YYYY-MM-DD, within a year), `hours_per_day`, `subject`, `chapters`, `user` | `plan` |
| `GET /analytics` | Summary of the agent run log | none | `total_runs`, `error_rate`, `avg_total_ms`, `by_tool`, `avg_step_ms`, `recent_errors` |

### Errors

| Status | Meaning |
|---|---|
| `400` | No index is loaded yet. Upload files first, or add a built-in `faiss_index/`. |
| `404` | No study material matches the topic and filters. |
| `422` | The request is invalid (for example an empty message, a past exam date, or a score above the total). |
| `502` | Gemini failed (rate limit, busy or key problem). The `detail` field says what to do. |

### Example

Request:

```json
POST /ask
{"message": "Teach me backpropagation", "user": "asha", "subject": "AIML", "k": 4}
```

Reply (shortened):

```json
{
  "run_id": "3f9a1c2b",
  "tool": "teach_topic",
  "reason": "The message asks to learn a topic.",
  "mode": "learn",
  "answer": "## 1. Theory ... [1] ...",
  "quiz": null,
  "sources": [{"n": 1, "label": "notes.pdf (notes), chapter: Neural Networks, page 3", "text": "..."}],
  "related": [{"n": 1, "label": "question_paper.pdf (question_paper), chapter: All Units, 2023, Q3, 5 marks", "text": "..."}],
  "citations_ok": true,
  "steps": [{"agent": "Router", "action": "choose tool", "ms": 640, "status": "ok"}]
}
```

Use `run_id` from `/ask` when sending `/feedback`.
