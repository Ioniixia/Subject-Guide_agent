import { useState } from "react";

// A multiple-choice quiz. Calls onFinished(score, total) once, when the student checks the answers.
export default function Quiz({ questions, onFinished }) {
  const [picks, setPicks] = useState({});
  const [checked, setChecked] = useState(false);
  const score = questions.filter((q, i) => picks[i] === q.options[q.answer_index]).length;

  function check() {
    setChecked(true);
    if (onFinished) onFinished(score, questions.length);
  }

  return (
    <div className="card">
      <h3>🧪 Quiz</h3>
      {questions.map((q, i) => (
        <fieldset key={i} disabled={checked}>
          <legend>
            {i + 1}. {q.question}
          </legend>
          {q.options.map((option) => (
            <label key={option} className="option">
              <input
                type="radio"
                name={`q${i}`}
                checked={picks[i] === option}
                onChange={() => setPicks({ ...picks, [i]: option })}
              />
              {option}
            </label>
          ))}
          {checked && (
            <p className={picks[i] === q.options[q.answer_index] ? "good" : "bad"}>
              {picks[i] === q.options[q.answer_index]
                ? `✅ Correct. ${q.explanation}`
                : `❌ The answer is ${q.options[q.answer_index]}. ${q.explanation}`}
            </p>
          )}
        </fieldset>
      ))}
      {!checked ? (
        <button onClick={check}>Check my answers</button>
      ) : (
        <p className="score">
          Your score: {score} / {questions.length}
        </p>
      )}
    </div>
  );
}
