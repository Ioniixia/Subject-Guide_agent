import { useCallback, useEffect, useState } from "react";
import { api, getSettings } from "./api";
import Sidebar from "./components/Sidebar";
import Plan from "./pages/Plan";
import Practice from "./pages/Practice";
import Progress from "./pages/Progress";
import Study from "./pages/Study";
import "./styles.css";

const PAGES = ["Study", "Practice", "Progress", "Study plan"];

export default function App() {
  const [settings, setSettings] = useState(getSettings());
  const [page, setPage] = useState("Study");
  const [filters, setFilters] = useState({ subject: "", chapter: "", sourceTypes: [] });
  const [options, setOptions] = useState({ subjects: [], chapters: [], sourceTypes: [] });
  const [serverStatus, setServerStatus] = useState("checking");
  const [preset, setPreset] = useState(null);

  const refresh = useCallback(async () => {
    try {
      await api.health();
      setServerStatus("ok");
    } catch {
      setServerStatus("down");
      return;
    }
    try {
      setOptions(await api.filters());
    } catch {
      setOptions({ subjects: [], chapters: [], sourceTypes: [] }); // the filter boxes become free text
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, settings.baseUrl, settings.apiKey]);

  function revise(chapter) {
    setPreset({ id: Date.now(), mode: "revise", message: chapter });
    setPage("Study");
  }

  return (
    <div className="layout">
      <header>
        <h1>📚 Academic Subject Guide AI</h1>
        <nav>
          {PAGES.map((name) => (
            <button key={name} className={name === page ? "tab active" : "tab"} onClick={() => setPage(name)}>
              {name}
            </button>
          ))}
        </nav>
      </header>
      <Sidebar
        settings={settings}
        onSettings={setSettings}
        filters={filters}
        onFilters={setFilters}
        options={options}
        serverStatus={serverStatus}
        onUploaded={refresh}
      />
      <main>
        {/* Study stays mounted so a result is still there when you come back to the page */}
        <div hidden={page !== "Study"}><Study settings={settings} filters={filters} preset={preset} /></div>
        {page === "Practice" && <Practice settings={settings} filters={filters} />}
        {page === "Progress" && <Progress settings={settings} onRevise={revise} />}
        {page === "Study plan" && <Plan settings={settings} filters={filters} />}
      </main>
    </div>
  );
}
