import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../api";
import { HINTS, MODES, buildExport, downloadText, filterBody, topicOf } from "../helpers";
import Quiz from "../components/Quiz";
import { Sources, Steps } from "../components/Sources";

export default function Study({ settings, filters, preset }) {
  const [mode, setMode] = useState("agent");
  const [message, setMessage] = useState("");
  const [marks, setMarks] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [extras, setExtras] = useState({});
  const lastPreset = useRef(null);

  const run = useCallback(
    async (text, runMode, runMarks) => {
      setLoading(true);
      setError("");
      setResult(null);
      setExtras({});
      try {
        const reply = await api.ask({
          message: text,
          mode: runMode,
          marks: runMode === "solve" ? runMarks : "",
          user: settings.user,
          ...filterBody(filters),
        });
        const topic = text;
        setResult({ ...reply, question: topic });

        // One-click revision: practice answers and a quiz right after the lesson
        if (runMode === "revise" && reply.answer && !reply.fallback) {
          const [answers, quiz] = await Promise.allSettled([
            api.practiceAnswers({ topic, lesson_text: reply.answer, ...filterBody(filters) }),
            api.quiz({ topic, ...filterBody(filters) }),
          ]);
          setExtras({
            answers: answers.status === "fulfilled" ? answers.value.answers : "",
            quiz: quiz.status === "fulfilled" ? quiz.value.questions : null,
          });
        }
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    },
    [settings.user, filters]
  );

  // The Progress page's Revise button sends a preset
  useEffect(() => {
    if (preset && preset.id !== lastPreset.current) {
      lastPreset.current = preset.id;
      setMode(preset.mode);
      setMessage(preset.message);
      run(preset.message, preset.mode, "");
    }
  }, [preset, run]);

  async function showAnswers() {
    try {
      const reply = await api.practiceAnswers({ topic: result.question, lesson_text: result.answer, ...filterBody(filters) });
      setExtras((e) => ({ ...e, answers: reply.answers }));
    } catch (e) {
      setError(e.message);
    }
  }

  async function startQuiz() {
    try {
      const reply = await api.quiz({ topic: result.question, ...filterBody(filters) });
      setExtras((e) => ({ ...e, quiz: reply.questions }));
    } catch (e) {
      setError(e.message);
    }
  }

  async function sendFeedback(rating) {
    try {
      await api.feedback({ run_id: result.run_id, rating, user: settings.user });
      setExtras((e) => ({ ...e, feedback: rating }));
    } catch (e) {
      setError(e.message);
    }
  }

  function saveQuizScore(score, total) {
    const { subject, chapter } = topicOf(result.sources, filters);
    api.saveProgress({ user: settings.user, subject, chapter, kind: "quiz", score, total })
      .then(() => setExtras((e) => ({ ...e, saved: chapter })))
      .catch((e) => setError(e.message));
  }

  const quiz = extras.quiz || result?.quiz;
  const isLesson = result && (result.mode === "learn" || result.mode === "quiz") && result.answer && !result.fallback;

  return (
    <section>
      <div className="modes" role="radiogroup" aria-label="What do you want to do?">
        {MODES.map(([value, label]) => (
          <label key={value} className="option">
            <input type="radio" name="mode" checked={mode === value} onChange={() => setMode(value)} />
            {label}
          </label>
        ))}
      </div>
      {mode === "solve" && (
        <label>
          Marks (sets the answer length)
          <select value={marks} onChange={(e) => setMarks(e.target.value)}>
            <option value="">Not specified</option>
            <option>2</option>
            <option>5</option>
            <option>10</option>
          </select>
        </label>
      )}
      <p className="hint">{HINTS[mode]}</p>
      <textarea
        aria-label="Your question, problem or topic"
        rows={4}
        maxLength={2000}
        value={message}
        onChange={(e) => setMessage(e.target.value)}
      />
      <button disabled={loading || !message.trim()} onClick={() => run(message, mode, marks)}>
        {loading ? "Thinking…" : "Generate"}
      </button>

      {error && <p className="bad" role="alert">{error}</p>}

      {result && (
        <div className="result">
          <p className="tool">
            Tool: <strong>{result.tool}</strong> {result.reason && <span>– {result.reason}</span>}
          </p>
          {result.fallback && <p className="warn">⚠️ {result.notice} The passages below come from your own material.</p>}
          {!result.fallback && result.notice && <p className="warn">⚠️ {result.notice}</p>}

          {result.answer && (
            <div className="card answer">
              <ReactMarkdown>{result.answer}</ReactMarkdown>
            </div>
          )}

          {result.answer && (
            <p>
              {extras.feedback ? (
                "Thanks for your feedback!"
              ) : (
                <>
                  <button className="small" aria-label="Helpful" onClick={() => sendFeedback("up")}>👍</button>{" "}
                  <button className="small" aria-label="Not helpful" onClick={() => sendFeedback("down")}>👎</button>
                </>
              )}
            </p>
          )}

          {result.answer && (
            <p>
              <button className="small" onClick={() => downloadText("study_notes.md", buildExport(result, extras))}>
                ⬇️ Download as Markdown
              </button>
            </p>
          )}

          {isLesson && result.mode === "learn" && (
            <p>
              {!extras.answers && <button onClick={showAnswers}>Show answers to the practice questions</button>}{" "}
              {!quiz && <button onClick={startQuiz}>Start a 3-question quiz</button>}
            </p>
          )}

          {extras.answers && (
            <div className="card answer">
              <h3>✅ Practice answers</h3>
              <ReactMarkdown>{extras.answers}</ReactMarkdown>
            </div>
          )}
          {quiz && <Quiz questions={quiz} onFinished={saveQuizScore} />}
          {extras.saved && <p className="good">Saved to your progress under {extras.saved}.</p>}

          {result.mode !== "past" && result.related?.length > 0 && (
            <div className="card">
              <h3>📝 Related past questions</h3>
              {result.related.map((q, i) => (
                <details key={i}>
                  <summary>{q.label}</summary>
                  <p>{q.text}</p>
                  <button className="small" onClick={() => { setMode("solve"); setMessage(q.text); run(q.text, "solve", ["2", "5", "10"].includes(String(q.marks)) ? String(q.marks) : ""); }}>
                    Solve this question
                  </button>
                </details>
              ))}
            </div>
          )}
          {result.mode === "past" && <Sources sources={result.sources} title="📝 Past questions" />}
          {result.mode !== "past" && <Sources sources={result.sources} />}
          <Steps steps={result.steps} />
        </div>
      )}
    </section>
  );
}
