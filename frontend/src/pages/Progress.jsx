import { useEffect, useState } from "react";
import { api } from "../api";

export default function Progress({ settings, onRevise }) {
  const [data, setData] = useState({ chapters: [], weak: [], stats: null });
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled([api.progress(settings.user), api.weakAreas(settings.user), api.analytics()]).then(([p, w, a]) => {
      if (cancelled) return;
      if (p.status === "rejected") setError(p.reason.message);
      setData({
        chapters: p.status === "fulfilled" ? p.value.chapters : [],
        weak: w.status === "fulfilled" ? w.value.weak_areas : [],
        stats: a.status === "fulfilled" ? a.value : null,
      });
    });
    return () => {
      cancelled = true;
    };
  }, [settings.user, settings.apiKey, settings.baseUrl]);

  const { chapters, weak, stats } = data;
  return (
    <section>
      <h2>Progress for {settings.user}</h2>
      {error && <p className="bad" role="alert">{error}</p>}
      {!error && chapters.length === 0 && <p>No results yet. Finish a quiz or practise some questions, and your scores will show up here.</p>}

      {chapters.length > 0 && (
        <div className="card">
          {chapters.map((c) => (
            <div key={`${c.subject}-${c.chapter}`} className="bar-row">
              <span>{c.chapter} <small>({c.subject}, {c.attempts} attempts)</small></span>
              <div className="bar"><div style={{ width: `${Math.round(c.accuracy * 100)}%` }} /></div>
              <span>{Math.round(c.accuracy * 100)}%</span>
            </div>
          ))}
        </div>
      )}

      <h3>🎯 Weak areas</h3>
      {weak.length === 0 ? (
        <p>No weak areas yet. A chapter shows up here after 2 attempts with accuracy below 60%.</p>
      ) : (
        weak.map((w) => (
          <p key={`${w.subject}-${w.chapter}`}>
            <strong>{w.chapter}</strong> ({w.subject}): {Math.round(w.accuracy * 100)}% over {w.attempts} attempts{" "}
            <button className="small" onClick={() => onRevise(w.chapter)}>Revise</button>
          </p>
        ))
      )}

      {stats && stats.total_runs > 0 && (
        <details className="card">
          <summary>📈 System analytics</summary>
          <p>
            Runs: {stats.total_runs} · Error rate: {Math.round(stats.error_rate * 100)}% · Average time: {stats.avg_total_ms} ms
          </p>
          <p>Runs per tool: {Object.entries(stats.by_tool).map(([k, v]) => `${k} ${v}`).join(", ")}</p>
        </details>
      )}
    </section>
  );
}
