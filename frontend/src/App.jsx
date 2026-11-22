
import { useCallback, useEffect, useState } from "react";
import { api, getSettings } from "./api";
import Sidebar from "./components/Sidebar";
import Plan from "./pages/Plan";
import Practice from "./pages/Practice";
import Progress from "./pages/Progress";
import Study from "./pages/Study";
import "./styles.css";

const PAGES = ["Study", "Practice", "Progress", "Study plan"];

const PAGE_INFO = {
  Study: {
    eyebrow: "YOUR LEARNING SPACE",
    description: "Ask questions, understand concepts and get help with your studies.",
  },
  Practice: {
    eyebrow: "TEST YOUR KNOWLEDGE",
    description: "Practise what you've learned and check your understanding.",
  },
  Progress: {
    eyebrow: "YOUR PERFORMANCE",
    description: "Review your learning progress and identify topics to revisit.",
  },
  "Study plan": {
    eyebrow: "YOUR STUDY ROUTINE",
    description: "Organise your topics and build a focused study plan.",
  },
};

export default function App() {
  const [settings, setSettings] = useState(getSettings());
  const [page, setPage] = useState("Study");
  const [filters, setFilters] = useState({
    subject: "",
    chapter: "",
    sourceTypes: [],
  });
  const [options, setOptions] = useState({
    subjects: [],
    chapters: [],
    sourceTypes: [],
  });
  const [serverStatus, setServerStatus] = useState("checking");
  const [serverError, setServerError] = useState("");
  const [preset, setPreset] = useState(null);

  const refresh = useCallback(async () => {
    try {
      await api.health();
      setServerStatus("ok");
      setServerError("");
    } catch (e) {
      setServerStatus("down");
      setServerError(
        e.status === 404
          ? "The server is running, but it has no /health endpoint."
          : e.status
            ? `The server answered with an error: ${e.message}`
            : e.message
      );
      return;
    }

    try {
      setOptions(await api.filters());
    } catch {
      setOptions({ subjects: [], chapters: [], sourceTypes: [] });
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, settings.baseUrl, settings.apiKey]);

  function revise(chapter) {
    setPreset({ id: Date.now(), mode: "revise", message: chapter });
    setPage("Study");
  }

  const pageInfo = PAGE_INFO[page];

  return (
    <div className="layout">
      <Sidebar
        settings={settings}
        onSettings={setSettings}
        filters={filters}
        onFilters={setFilters}
        options={options}
        serverStatus={serverStatus}
        serverError={serverError}
        onUploaded={refresh}
      />

      <div className="workspace">
        <header className="topbar">
          <div className="brand">
            <div className="brand-mark">✦</div>
            <div>
              <h1>Academic Subject Guide</h1>
              <p>AI-powered learning assistant</p>
            </div>
          </div>

          <nav aria-label="Main navigation">
            {PAGES.map((name) => (
              <button
                key={name}
                className={name === page ? "tab active" : "tab"}
                onClick={() => setPage(name)}
                aria-current={name === page ? "page" : undefined}
              >
                {name}
              </button>
            ))}
          </nav>
        </header>

        <main>
          <div className="page-heading">
            <p className="eyebrow">{pageInfo.eyebrow}</p>
            <h2>{page}</h2>
            <p>{pageInfo.description}</p>
          </div>

          <div className="page-content">
            <div hidden={page !== "Study"}>
              <Study
                settings={settings}
                filters={filters}
                preset={preset}
              />
            </div>

            {page === "Practice" && (
              <Practice settings={settings} filters={filters} />
            )}

            {page === "Progress" && (
              <Progress settings={settings} onRevise={revise} />
            )}

            {page === "Study plan" && (
              <Plan settings={settings} filters={filters} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
