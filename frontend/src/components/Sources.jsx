export function Sources({ sources, title = "🔍 Source chunks" }) {
  if (!sources?.length) return null;
  return (
    <div className="card">
      <h3>{title}</h3>
      {sources.map((s, i) => (
        <details key={i} open={i === 0}>
          <summary>
            [{s.n ?? i + 1}] {s.label}
          </summary>
          <p>{s.text}</p>
        </details>
      ))}
    </div>
  );
}

export function Steps({ steps }) {
  if (!steps?.length) return null;
  return (
    <details className="card">
      <summary>🧭 Agent steps ({steps.length})</summary>
      <table>
        <thead>
          <tr>
            <th>Agent</th>
            <th>Action</th>
            <th>Detail</th>
            <th>ms</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {steps.map((s, i) => (
            <tr key={i}>
              <td>{s.agent}</td>
              <td>{s.action}</td>
              <td>{s.detail}</td>
              <td>{s.ms}</td>
              <td>{s.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
