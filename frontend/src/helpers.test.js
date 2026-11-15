import { describe, expect, it } from "vitest";
import { buildExport, topicOf } from "./helpers";

describe("helpers", () => {
  it("builds a study note with the answer, quiz and sources", () => {
    const text = buildExport(
      { question: "Neural Networks", tool: "teach_topic", answer: "## Theory [1]", sources: [{ n: 1, label: "notes.pdf (notes)" }] },
      { answers: "1. A", quiz: [{ question: "Q?", options: ["a", "b", "c", "d"], answer_index: 1, explanation: "because" }] }
    );
    expect(text).toContain("# Neural Networks");
    expect(text).toContain("## Practice answers");
    expect(text).toContain("Answer: b. because");
    expect(text).toContain("1. notes.pdf (notes)");
  });

  it("works out the topic from the sources, ignoring All Units", () => {
    const sources = [{ chapter: "All Units", subject: "AIML" }, { chapter: "Search", subject: "AIML" }, { chapter: "Search", subject: "AIML" }];
    expect(topicOf(sources, {})).toEqual({ subject: "AIML", chapter: "Search" });
    expect(topicOf([], {})).toEqual({ subject: "General", chapter: "General" });
    expect(topicOf(sources, { chapter: "Chosen" }).chapter).toBe("Chosen");
  });
});
