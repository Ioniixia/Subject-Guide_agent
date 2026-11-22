
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../api";
import {
  HINTS,
  MODES,
  buildExport,
  downloadText,
  filterBody,
  topicOf,
} from "../helpers";
import Quiz from "../components/Quiz";
import { Sources, Steps } from "../components/Sources";

const MODE_DETAILS = {
  agent: { icon: "✦", subtitle: "Let AI choose the right study tool" },
  qa: { icon: "◉", subtitle: "Get clear answers to your questions" },
  solve: { icon: "⌘", subtitle: "Work through problems step by step" },
  learn: { icon: "▤", subtitle: "Understand a topic from the basics" },
  revise: { icon: "↗", subtitle: "Get a lesson, answers and a quiz" },
};

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

        setResult({ ...reply, question: text });

        if (runMode === "revise" && reply.answer && !reply.fallback) {
          const [answers, quiz] = await Promise.allSettled([
            api.practiceAnswers({
              topic: text,
              lesson_text: reply.answer,
              ...filterBody(filters),
            }),
            api.quiz({ topic: text, ...filterBody(filters) }),
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
      const reply = await api.practiceAnswers({
        topic: result.question,
        lesson_text: result.answer,
        ...filterBody(filters),
      });
      setExtras((e) => ({ ...e, answers: reply.answers }));
    } catch (e) {
      setError(e.message);
    }
  }

  async function startQuiz() {
    try {
      const reply = await api.quiz({
        topic: result.question,
        ...filterBody(filters),
      });
      setExtras((e) => ({ ...e, quiz: reply.questions }));
    } catch (e) {
      setError(e.message);
    }
  }

  async function sendFeedback(rating) {
    try {
      await api.feedback({
        run_id: result.run_id,
        rating,
        user: settings.user,
      });
      setExtras((e) => ({ ...e, feedback: rating }));
    } catch (e) {
      setError(e.message);
    }
  }

  function saveQuizScore(score, total) {
    const { subject, chapter } = topicOf(result.sources, filters);

    api.saveProgress({
      user: settings.user,
      subject,
      chapter,
      kind: "quiz",
      score,
      total,
    })
      .then(() => setExtras((e) => ({ ...e, saved: chapter })))
      .catch((e) => setError(e.message));
  }

  const quiz = extras.quiz || result?.quiz;
  const isLesson =
    result &&
    (result.mode === "learn" || result.mode === "quiz") &&
    result.answer &&
    !result.fallback;

  return (
    <section className="study-workspace">
      <div className="study-intro">
        <div>
          <span className="study-kicker">YOUR AI STUDY COMPANION</span>
          <h2>What would you like to learn today?</h2>
          <p>
            Ask a question, explore a topic or solve a problem.
            Your learning starts here.
          </p>
        </div>
        <div className="study-decoration" aria-hidden="true">
          <span>✦</span>
          <span>✧</span>
          <span>✦</span>
        </div>
      </div>

      <div className="study-panel">
        <div className="panel-heading">
          <div>
            <span className="section-label">STEP 01</span>
            <h3>Choose your study mode</h3>
          </div>
          <span className="mode-count">05 MODES</span>
        </div>

        <div className="mode-grid" role="radiogroup" aria-label="What do you want to do?">
          {MODES.map(([value, label]) => {
            const detail = MODE_DETAILS[value];

            return (
              <label
                key={value}
                className={`mode-card ${mode === value ? "selected" : ""}`}
              >
                <input
                  type="radio"
                  name="mode"
                  value={value}
                  aria-label={label}
                  checked={mode === value}
                  onChange={() => setMode(value)}
                />
                <span className="mode-icon">{detail.icon}</span>
                <span className="mode-name">{label}</span>
                <span className="mode-description">{detail.subtitle}</span>
                <span className="mode-check">
                  {mode === value ? "✓" : "+"}
                </span>
              </label>
            );
          })}
        </div>
      </div>

      <div className="study-panel composer-panel">
        <div className="panel-heading">
          <div>
            <span className="section-label">STEP 02</span>
            <h3>Enter your question or topic</h3>
          </div>
        </div>

        <p className="composer-hint">{HINTS[mode]}</p>

        {mode === "solve" && (
          <label className="marks-field">
            Answer length
            <select
              value={marks}
              onChange={(e) => setMarks(e.target.value)}
            >
              <option value="">Not specified</option>
              <option value="2">2 marks</option>
              <option value="5">5 marks</option>
              <option value="10">10 marks</option>
            </select>
          </label>
        )}

        <textarea
          className="question-input"
          aria-label="Your question, problem or topic"
          placeholder="Type your question here... What would you like help with?"
          rows={5}
          maxLength={2000}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />

        <div className="composer-footer">
          <span className="character-count">
            {message.length}/2000 characters
          </span>

          <button
            className="generate-button"
            disabled={loading || !message.trim()}
            onClick={() => run(message, mode, marks)}
          >
            {loading ? "Working on it..." : "Generate"}
          </button>
        </div>
      </div>

      {error && (
        <p className="bad" role="alert">{error}</p>
      )}

      {loading && (
        <div className="loading-panel" role="status">
          <span className="loading-symbol">✦</span>
          <div>
            <strong>Your study assistant is working</strong>
            <p>Finding relevant material and preparing your response...</p>
          </div>
        </div>
      )}

      {result && (
        <div className="result">
          <div className="result-heading">
            <div>
              <span className="section-label">YOUR STUDY RESULT</span>
              <h3>Here's what I found</h3>
            </div>
            <span className="result-badge">AI RESPONSE</span>
          </div>

          <p className="tool">
            Tool: <strong>{result.tool}</strong>{" "}
            {result.reason && <span>– {result.reason}</span>}
          </p>

          {result.fallback && (
            <p className="warn">
              {result.notice} The passages below come from your own material.
            </p>
          )}

          {!result.fallback && result.notice && (
            <p className="warn">{result.notice}</p>
          )}

          {result.answer && (
            <div className="card answer">
              <ReactMarkdown>{result.answer}</ReactMarkdown>
            </div>
          )}

          {result.answer && (
            <div className="result-actions">
              {extras.feedback ? (
                <span className="good">Thanks for your feedback!</span>
              ) : (
                <>
                  <button
                    className="small secondary-button"
                    aria-label="Helpful"
                    onClick={() => sendFeedback("up")}
                  >
                    👍 Helpful
                  </button>
                  <button
                    className="small secondary-button"
                    aria-label="Not helpful"
                    onClick={() => sendFeedback("down")}
                  >
                    👎 Not helpful
                  </button>
                </>
              )}

              <button
                className="small secondary-button"
                onClick={() =>
                  downloadText(
                    "study_notes.md",
                    buildExport(result, extras)
                  )
                }
              >
                Download as Markdown
              </button>
            </div>
          )}

          {isLesson && result.mode === "learn" && (
            <div className="study-panel next-actions">
              <h3>Continue learning</h3>
              {!extras.answers && (
                <button onClick={showAnswers}>
                  Show answers to the practice questions
                </button>
              )}
              {!quiz && (
                <button onClick={startQuiz}>
                  Start a 3-question quiz
                </button>
              )}
            </div>
          )}

          {extras.answers && (
            <div className="card answer">
              <h3>Practice answers</h3>
              <ReactMarkdown>{extras.answers}</ReactMarkdown>
            </div>
          )}

          {quiz && (
            <Quiz questions={quiz} onFinished={saveQuizScore} />
          )}

          {extras.saved && (
            <p className="good">
              Saved to your progress under {extras.saved}.
            </p>
          )}

         {result.mode !== "past" && result.related?.length > 0 && (
  <div className="card">
    <h3>Related questions</h3>
    {result.related.map((item, index) => (
      <div className="related-question" key={index}>
        <p>{typeof item === "string" ? item : item.label}</p>
        {typeof item === "object" && (
          <button
            type="button"
            onClick={() => {
              setMessage(item.text);
              setMode("solve");
              setMarks(String(item.marks ?? ""));
              run(item.text, "solve", String(item.marks ?? ""));
            }}
          >
            Solve this question
          </button>
        )}
      </div>
    ))}
  </div>
)}
          {result.mode !== "past" && (
            <Sources sources={result.sources} />
          )}

          <Steps steps={result.steps} />
        </div>
      )}
    </section>
  );
}
