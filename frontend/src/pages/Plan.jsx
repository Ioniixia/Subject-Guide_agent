import { useState } from "react";
import { api } from "../api";

function tomorrowPlus(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

export default function Plan({ settings, filters }) {
  const [examDate, setExamDate] = useState(tomorrowPlus(14));
  const [hours, setHours] = useState(2);
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState("");

  async function build() {
    setError("");
    try {
      const reply = await api.studyPlan({ exam_date: examDate, hours_per_day: Number(hours), subject: filters.subject, user: settings.user });
      setPlan(reply.plan);
    } catch (e) {
      setPlan(null);
      setError(e.message);
    }
  }

  function download() {
    const rows = [["Day", "Date", "Focus", "Tasks", "Hours"], ...plan.map((d) => [d.day, d.date, d.focus, d.tasks.join("; "), d.hours])];
    const csv = rows.map((r) => r.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(",")).join("\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    link.download = "study_plan.csv";
    link.click();
  }

  return (
    <section>
      <h2>Build a study plan</h2>
      <label>
        Exam date
        <input type="date" value={examDate} min={tomorrowPlus(1)} onChange={(e) => setExamDate(e.target.value)} />
      </label>
      <label>
        Hours per day
        <input type="number" min="1" max="12" value={hours} onChange={(e) => setHours(e.target.value)} />
      </label>
      <button onClick={build}>Build my plan</button>
      {error && <p className="bad" role="alert">{error}</p>}

      {plan && (
        <>
          <table>
            <thead>
              <tr><th>Day</th><th>Date</th><th>Focus</th><th>Tasks</th><th>Hours</th></tr>
            </thead>
            <tbody>
              {plan.map((d) => (
                <tr key={d.day}>
                  <td>{d.day}</td><td>{d.date}</td><td>{d.focus}</td><td>{d.tasks.join("; ")}</td><td>{d.hours}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <button onClick={download}>Download plan (CSV)</button>
        </>
      )}
    </section>
  );
}
