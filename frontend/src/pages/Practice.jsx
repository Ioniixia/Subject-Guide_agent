import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../api";
import { filterBody, topicOf } from "../helpers";

export default function Practice({ settings, filters }) {
  const [questions, setQuestions] = useState([]);
  const [index, setIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [solution, setSolution] = useState(null);
  const [scores, setScores] = useState([]);
  const [started, setStarted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function start() {
    setError("");
    try {
      const reply = await api.pastQuestions({ subject: filters.subject, chapter: filters.chapter, limit: 15 });
      setQuestions(reply.questions);
      setIndex(0);
      setScores([]);
      setSolution(null);
      setAnswer("");
      setStarted(true);
      if (!reply.questions.length) setError("No past-paper questions found for these filters.");
    } catch (e) {
      setError(e.message);
    }
  }

  async function showSolution() {
    const q = questions[index];
    setBusy(true);
    setError("");
    try {
      const marks = ["2", "5", "10"].includes(String(q.marks)) ? String(q.marks) : "";
      const reply = await api.ask({ message: q.text, mode: "solve", marks, user: settings.user, subject: filters.subject });
      setSolution(reply);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function rate(score) {
    const q = questions[index];
    // Question papers cover every unit, so progress goes under the chapter of the notes that solved it
    const topic = topicOf(solution.sources, filters);
    const chapter = q.chapter && q.chapter !== "All Units" ? q.chapter : topic.chapter;
    try {
      await api.saveProgress({ user: settings.user, subject: q.subject || topic.subject, chapter, kind: "practice", score, total: 1 });
    } catch (e) {
      setError(e.message);
    }
    setScores([...scores, score]);
    setIndex(index + 1);
    setSolution(null);
    setAnswer("");
  }

  const finished = started && questions.length > 0 && index >= questions.length;
  const q = questions[index];

  return (
    <section>
      <h2>Practise with past-paper questions</h2>
      <p className="hint">Use the Subject and Chapter filters in the sidebar to choose what to practise.</p>
      <button onClick={start}>Start practice</button>
      {error && <p className="bad" role="alert">{error}</p>}

      {finished && (
        <p className="good">
          Practice finished! You scored {scores.reduce((a, b) => a + b, 0)} out of {questions.length}. Your results are on the Progress page.
        </p>
      )}

      {started && q && (
        <div className="card">
          <p>
            Question {index + 1} of {questions.length}
          </p>
          <progress value={index} max={questions.length} />
          <p><strong>{q.label}</strong></p>
          <p>{q.text}</p>
          <textarea aria-label="Your answer" rows={4} value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder="Try it first, then check the solution" />
          {!solution ? (
            <button disabled={busy} onClick={showSolution}>{busy ? "Writing the solution…" : "Show solution"}</button>
          ) : (
            <>
              <h3>🧮 Solution</h3>
              <ReactMarkdown>{solution.answer}</ReactMarkdown>
              <p>How did you do?</p>
              <button onClick={() => rate(1)}>✅ Got it</button>{" "}
              <button onClick={() => rate(0.5)}>🟡 Partly</button>{" "}
              <button onClick={() => rate(0)}>❌ Missed it</button>
            </>
          )}
        </div>
      )}
    </section>
  );
}
