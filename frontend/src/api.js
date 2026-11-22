// Every call to the backend goes through this file.
const KEY_HEADER = import.meta.env.VITE_API_KEY_HEADER || "X-API-Key";
const STORAGE_KEY = "study-guide-settings";

// Where the backend is. On a deployed site the backend serves this page, so it is the same address.
// While developing (the Vite dev server on port 5173) it is the local backend. VITE_API_URL overrides both.
export function defaultBaseUrl(location = window.location, env = import.meta.env) {
  if (env.VITE_API_URL) return env.VITE_API_URL;
  if (["5173", "4173"].includes(location.port)) return "http://127.0.0.1:8000";
  return location.origin;
}

export function getSettings() {
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    saved = {};
  }
  return { baseUrl: defaultBaseUrl(), apiKey: "", user: "guest", ...saved };
}

export function saveSettings(settings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function explain(status, detail) {
  if (status === 401 || status === 403) return "The API key is missing or wrong. Open Settings and enter it.";
  if (status === 429) return detail || "Too many requests. Please wait a moment and try again.";
  return detail || `The request failed (status ${status}).`;
}

function detailText(data) {
  if (!data) return "";
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join("; ");
  return "";
}

async function request(path, { method = "GET", body, form, query } = {}) {
  const { baseUrl, apiKey } = getSettings();
  const url = new URL(path, baseUrl);
  Object.entries(query || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
  });

  const headers = {};
  if (apiKey) headers[KEY_HEADER] = apiKey;
  let payload;
  if (form) {
    payload = form; // the browser sets the multipart boundary itself
  } else if (body) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(url.toString(), { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check that the backend is running, that the address in Settings is right, and that the backend allows this website (CORS).");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, explain(response.status, detailText(data)));
  return data;
}

// Removes empty values so the backend only sees what the student chose.
const clean = (obj) => Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== "" && v !== undefined && v !== null && !(Array.isArray(v) && v.length === 0)));

function normalizeFilters(data) {
  const pick = (...keys) => {
    for (const key of keys) if (Array.isArray(data?.[key])) return data[key];
    return [];
  };
  return {
    subjects: pick("subjects", "subject"),
    chapters: pick("chapters", "chapter"),
    sourceTypes: pick("source_types", "sourceTypes", "types"),
  };
}

export const api = {
  health: () => request("/health"),
  ask: (body) => request("/ask", { method: "POST", body: clean(body) }),
  quiz: (body) => request("/quiz", { method: "POST", body: clean(body) }),
  practiceAnswers: (body) => request("/practice-answers", { method: "POST", body: clean(body) }),
  pastQuestions: (query) => request("/past-questions", { query }),
  feedback: (body) => request("/feedback", { method: "POST", body }),
  history: (user) => request("/history", { query: { user } }),
  saveProgress: (body) => request("/progress", { method: "POST", body }),
  progress: (user) => request("/progress", { query: { user } }),
  weakAreas: (user) => request("/weak-areas", { query: { user } }),
  studyPlan: (body) => request("/study-plan", { method: "POST", body: clean(body) }),
  analytics: () => request("/analytics"),
  // /filters and /upload belong to the data side of the backend. If their fields differ from
  // these, change only the two functions below (check the schemas on /docs).
  filters: async () => normalizeFilters(await request("/filters")),
  upload: (files, { sourceType, subject, chapter }) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    if (sourceType) form.append("source_type", sourceType);
    if (subject) form.append("subject", subject);
    if (chapter) form.append("chapter", chapter);
    return request("/upload", { method: "POST", form });
  },
};
