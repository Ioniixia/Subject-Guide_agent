import { vi } from "vitest";

export const json = (status, data) => ({ ok: status < 400, status, json: async () => data });

// A fake backend: routes maps "METHOD /path" to a function (body, options) => response.
export function mockApi(routes) {
  const fetchMock = vi.fn(async (url, options = {}) => {
    const key = `${options.method || "GET"} ${new URL(url).pathname}`;
    const handler = routes[key];
    if (!handler) return json(404, { detail: `no mock for ${key}` });
    const body = typeof options.body === "string" ? JSON.parse(options.body) : null;
    return handler(body, options);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export const callsTo = (fetchMock, key) =>
  fetchMock.mock.calls
    .filter(([url, options = {}]) => `${options.method || "GET"} ${new URL(url).pathname}` === key)
    .map(([, options]) => (typeof options?.body === "string" ? JSON.parse(options.body) : options));

export const askReply = (extra = {}) => ({
  run_id: "run1", tool: "answer_question", reason: "Default: a direct question.", mode: "qa",
  answer: "Supervised learning uses labelled data [1].", quiz: null, citations_ok: true, fallback: false, notice: "",
  sources: [{ n: 1, label: "notes.pdf (notes), chapter: Neural Networks, page 3", text: "Labelled examples.", chapter: "Neural Networks", subject: "AIML" }],
  related: [], steps: [{ agent: "Router", action: "choose tool", detail: "answer_question", ms: 12, status: "ok" }],
  ...extra,
});

export const baseRoutes = {
  "GET /health": () => json(200, { status: "ok" }),
  "GET /filters": () => json(200, { subjects: ["AIML", "DBMS"], chapters: ["Search", "Neural Networks"], source_types: ["notes", "question_paper"] }),
};
