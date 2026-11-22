"""Measure the running app: speed, citations, fallbacks and tool choice for a set of questions.
Prints a Markdown table you can paste into the README's Results section.

    python scripts/benchmark.py --url http://127.0.0.1:8000 --key YOUR_API_KEY
    python scripts/benchmark.py --url https://<your-space>.hf.space --key YOUR_API_KEY --questions my_questions.txt
"""
import argparse
import json
import statistics
import time
import urllib.error
import urllib.request

DEFAULT_QUESTIONS = [
    "What is supervised learning?",
    "Explain second normal form with an example",
    "Teach me ACID properties",
    "Solve Q3 from the 2023 paper",
    "Quiz me on normalization",
    "Past questions on transactions",
    "What is the difference between 2NF and 3NF?",
    "How does backpropagation work?",
    "Explain depth-first search",
    "What is a primary key?",
]


def ask(url, key, header, message, user, timeout=120):
    body = json.dumps({"message": message, "user": user}).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers[header] = key
    request = urllib.request.Request(url.rstrip("/") + "/ask", data=body, headers=headers, method="POST")
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read())
            return {"ok": True, "seconds": time.time() - started, "data": data}
    except urllib.error.HTTPError as e:
        return {"ok": False, "seconds": time.time() - started, "error": f"HTTP {e.code}"}
    except Exception as e:  # network error, timeout, bad JSON
        return {"ok": False, "seconds": time.time() - started, "error": type(e).__name__}


def summarize(results):
    done = [r for r in results if r["ok"]]
    seconds = sorted(r["seconds"] for r in done)
    step_ms = {}
    for r in done:
        for step in r["data"].get("steps", []):
            step_ms.setdefault(step["agent"], []).append(step["ms"])
    tools = {}
    for r in done:
        tools[r["data"].get("tool")] = tools.get(r["data"].get("tool"), 0) + 1
    answered = [r for r in done if r["data"].get("answer")]
    return {
        "questions": len(results),
        "succeeded": len(done),
        "median_s": round(statistics.median(seconds), 1) if seconds else None,
        "p95_s": round(seconds[min(len(seconds) - 1, int(len(seconds) * 0.95))], 1) if seconds else None,
        "citations_ok": sum(1 for r in answered if r["data"].get("citations_ok")),
        "answered": len(answered),
        "fallbacks": sum(1 for r in done if r["data"].get("fallback")),
        "tools": tools,
        "avg_step_ms": {a: int(sum(v) / len(v)) for a, v in step_ms.items()},
    }


def to_markdown(stats):
    lines = ["| Measure | Result |", "|---|---|"]
    lines.append(f"| Questions asked | {stats['questions']} |")
    lines.append(f"| Answered without an error | {stats['succeeded']} / {stats['questions']} |")
    lines.append(f"| Median time per answer | {stats['median_s']} s |")
    lines.append(f"| Slowest 5% (p95) | {stats['p95_s']} s |")
    lines.append(f"| Answers whose citations all point to real sources | {stats['citations_ok']} / {stats['answered']} |")
    lines.append(f"| Answers that used the fallback (model unavailable) | {stats['fallbacks']} |")
    lines.append(f"| Tools chosen by the router | {', '.join(f'{k} x{v}' for k, v in stats['tools'].items())} |")
    lines.append(f"| Average time per agent | {', '.join(f'{k} {v} ms' for k, v in stats['avg_step_ms'].items())} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--key", default="")
    parser.add_argument("--header", default="X-API-Key")
    parser.add_argument("--user", default="benchmark")
    parser.add_argument("--questions", help="a text file with one question per line")
    parser.add_argument("--delay", type=float, default=0, help="seconds to wait between questions")
    args = parser.parse_args()

    questions = DEFAULT_QUESTIONS
    if args.questions:
        with open(args.questions, encoding="utf-8") as f:
            questions = [line.strip() for line in f if line.strip()]

    results = []
    for i, question in enumerate(questions, 1):
        result = ask(args.url, args.key, args.header, question, args.user)
        status = f"{result['seconds']:.1f} s" if result["ok"] else result["error"]
        print(f"{i:>2}/{len(questions)}  {status:>8}  {question}")
        results.append(result)
        time.sleep(args.delay)
    print()
    print(to_markdown(summarize(results)))


if __name__ == "__main__":
    main()
