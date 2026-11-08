"""Summarise the agent run log (logs/agent_runs.jsonl)."""
import json
import os
from collections import Counter, defaultdict

LOG_FILE = os.path.join(os.getenv("AGENT_LOG_DIR", "logs"), "agent_runs.jsonl")


def summarize(log_file=None, limit=1000):
    path = log_file or LOG_FILE
    runs = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f.readlines()[-limit:]:
                try:
                    runs.append(json.loads(line))
                except ValueError:
                    continue

    by_tool = Counter(r.get("tool") or "unknown" for r in runs)
    step_times = defaultdict(list)
    for r in runs:
        for s in r.get("steps", []):
            step_times[s["agent"]].append(s["ms"])
    errors = [r for r in runs if r.get("status") == "error"]
    total = len(runs)
    return {
        "total_runs": total,
        "errors": len(errors),
        "error_rate": round(len(errors) / total, 3) if total else 0.0,
        "avg_total_ms": int(sum(r.get("total_ms", 0) for r in runs) / total) if total else 0,
        "by_tool": dict(by_tool),
        "avg_step_ms": {agent: int(sum(v) / len(v)) for agent, v in step_times.items()},
        "recent_errors": [{"time": r.get("time"), "tool": r.get("tool"), "error": r.get("error")} for r in errors[-5:]],
    }
