import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, defaultBaseUrl, saveSettings } from "./api";
import { json, mockApi } from "./testUtils";

beforeEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("sends the API key header and leaves out empty fields", async () => {
    saveSettings({ baseUrl: "http://server:8000", apiKey: "secret", user: "asha" });
    const fetchMock = mockApi({ "POST /ask": () => json(200, { ok: true }) });
    await api.ask({ message: "hi", subject: "", chapter: undefined, source_types: [], marks: "" });
    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe("http://server:8000/ask");
    expect(options.headers["X-API-Key"]).toBe("secret");
    expect(JSON.parse(options.body)).toEqual({ message: "hi" });
  });

  it("explains a missing or wrong API key", async () => {
    mockApi({ "POST /ask": () => json(401, { detail: "Not authenticated" }) });
    await expect(api.ask({ message: "hi" })).rejects.toThrow(/API key/);
  });

  it("shows the server's message for a rejected request", async () => {
    mockApi({ "POST /ask": () => json(400, { detail: "That looks like an attempt to change my instructions." }) });
    await expect(api.ask({ message: "x" })).rejects.toThrow(/change my instructions/);
  });

  it("joins validation errors from the server", async () => {
    mockApi({ "POST /ask": () => json(422, { detail: [{ msg: "String should have at least 1 character" }] }) });
    await expect(api.ask({ message: "x" })).rejects.toThrow(/at least 1 character/);
  });

  it("reports an unreachable server in plain words", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("Failed to fetch"))));
    await expect(api.health()).rejects.toThrow(/Cannot reach the server/);
  });

  it("understands different shapes of the filters reply", async () => {
    mockApi({ "GET /filters": () => json(200, { subjects: ["AIML"], chapters: ["Search"], types: ["notes"] }) });
    expect(await api.filters()).toEqual({ subjects: ["AIML"], chapters: ["Search"], sourceTypes: ["notes"] });
  });

  it("uploads files as multipart form data", async () => {
    const fetchMock = mockApi({ "POST /upload": () => json(200, { indexed: 1 }) });
    await api.upload([new File(["x"], "notes.pdf")], { sourceType: "notes", subject: "AIML", chapter: "" });
    const body = fetchMock.mock.calls[0][1].body;
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("source_type")).toBe("notes");
    expect(body.get("subject")).toBe("AIML");
    expect(body.has("chapter")).toBe(false);
  });

  it("uses the local backend while developing and the same address once deployed", () => {
    expect(defaultBaseUrl({ port: "5173", origin: "http://localhost:5173" }, {})).toBe("http://127.0.0.1:8000");
    expect(defaultBaseUrl({ port: "", origin: "https://guide.hf.space" }, {})).toBe("https://guide.hf.space");
    expect(defaultBaseUrl({ port: "8000", origin: "http://127.0.0.1:8000" }, {})).toBe("http://127.0.0.1:8000");
    expect(defaultBaseUrl({ port: "", origin: "https://guide.hf.space" }, { VITE_API_URL: "https://api.example.com" })).toBe("https://api.example.com");
  });
});
