// The subject and chapter a set of source chunks is about, used when saving progress.
export function topicOf(sources = [], filters = {}) {
  const most = (values) => {
    const counts = {};
    values.forEach((v) => (counts[v] = (counts[v] || 0) + 1));
    return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0];
  };
  const chapters = sources.map((s) => s.chapter).filter((c) => c && c !== "All Units");
  const subjects = sources.map((s) => s.subject).filter(Boolean);
  return {
    subject: filters.subject || most(subjects) || "General",
    chapter: filters.chapter || most(chapters) || "General",
  };
}

// The filters the backend understands, without the empty ones.
export function filterBody(filters) {
  return {
    subject: filters.subject,
    chapter: filters.chapter,
    source_types: filters.sourceTypes,
  };
}

export const MODES = [
  ["agent", "Ask anything (agent)"],
  ["qa", "Ask a question"],
  ["solve", "Solve a problem"],
  ["learn", "Learn a topic"],
  ["revise", "Revise a topic (all-in-one)"],
];

export const HINTS = {
  agent: "Type what you need, e.g. 'Teach me 2NF', 'Solve Q3 from the 2023 paper', 'Quiz me on ACID' or 'Past questions on transactions'.",
  qa: "e.g. Explain 2NF with an example",
  solve: "Paste an exam or textbook problem",
  learn: "e.g. Second Normal Form",
  revise: "Enter a topic. You get the lesson, practice answers and a quiz in one go.",
};

// A study note the student can keep: the answer, practice answers, quiz questions and the sources used.
export function buildExport(result, extras = {}) {
  const lines = [`# ${result.question}`, "", `_Tool: ${result.tool}_`, "", result.answer || ""];
  if (extras.answers) lines.push("", "## Practice answers", "", extras.answers);
  const quiz = extras.quiz || result.quiz;
  if (quiz?.length) {
    lines.push("", "## Quiz", "");
    quiz.forEach((q, i) => {
      lines.push(`${i + 1}. ${q.question}`);
      q.options.forEach((o) => lines.push(`   - ${o}`));
      lines.push(`   - Answer: ${q.options[q.answer_index]}. ${q.explanation}`);
    });
  }
  if (result.sources?.length) {
    lines.push("", "## Sources", "");
    result.sources.forEach((src, i) => lines.push(`${src.n ?? i + 1}. ${src.label}`));
  }
  return lines.join("\n") + "\n";
}

export function downloadText(filename, text, type = "text/markdown") {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([text], { type }));
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}
