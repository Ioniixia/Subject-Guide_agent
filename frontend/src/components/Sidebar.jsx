import { useState } from "react";
import { api, saveSettings } from "../api";

const SOURCE_TYPES = ["notes", "textbook", "question_paper", "lab_manual"];

export default function Sidebar({ settings, onSettings, filters, onFilters, options, serverStatus, serverError, onUploaded }) {
  const [files, setFiles] = useState([]);
  const [tags, setTags] = useState({ sourceType: "notes", subject: "", chapter: "" });
  const [upload, setUpload] = useState({ busy: false, message: "", error: false });

  function updateSettings(change) {
    const next = { ...settings, ...change };
    saveSettings(next);
    onSettings(next);
  }

  async function doUpload() {
    setUpload({ busy: true, message: "", error: false });
    try {
      await api.upload(files, tags);
      setUpload({ busy: false, message: `Uploaded ${files.length} file(s).`, error: false });
      setFiles([]);
      onUploaded();
    } catch (e) {
      setUpload({ busy: false, message: e.message, error: true });
    }
  }

  function toggleType(type) {
    const current = filters.sourceTypes;
    onFilters({ ...filters, sourceTypes: current.includes(type) ? current.filter((t) => t !== type) : [...current, type] });
  }

  const typeOptions = options.sourceTypes.length ? options.sourceTypes : SOURCE_TYPES;

  return (
    <aside>
      <p className={`status ${serverStatus}`}>
        {serverStatus === "ok" ? "● Server connected" : serverStatus === "checking" ? "● Checking server…" : "● Server not reachable"}
      </p>
      {serverStatus === "down" && serverError && <p className="bad" role="status">{serverError}</p>}

      <details>
        <summary>⚙️ Settings</summary>
        <label>
          Server address
          <input value={settings.baseUrl} onChange={(e) => updateSettings({ baseUrl: e.target.value })} />
        </label>
        <label>
          Your name (keeps progress separate)
          <input value={settings.user} onChange={(e) => updateSettings({ user: e.target.value.trim() || "guest" })} />
        </label>
      </details>

      <h3>📁 Upload files</h3>
      <input
        type="file"
        multiple
        accept=".pdf,.docx,.pptx"
        aria-label="Upload files"
        onChange={(e) => setFiles(Array.from(e.target.files))}
      />
      <label>
        Type
        <select value={tags.sourceType} onChange={(e) => setTags({ ...tags, sourceType: e.target.value })}>
          {SOURCE_TYPES.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
      </label>
      <label>
        Subject (optional)
        <input value={tags.subject} onChange={(e) => setTags({ ...tags, subject: e.target.value })} />
      </label>
      <label>
        Chapter (optional)
        <input value={tags.chapter} onChange={(e) => setTags({ ...tags, chapter: e.target.value })} />
      </label>
      <button disabled={!files.length || upload.busy} onClick={doUpload}>
        {upload.busy ? "Uploading…" : "Upload"}
      </button>
      {upload.message && <p className={upload.error ? "bad" : "good"}>{upload.message}</p>}

      <h3>Filters</h3>
      <label>
        Subject
        {options.subjects.length ? (
          <select value={filters.subject} onChange={(e) => onFilters({ ...filters, subject: e.target.value })}>
            <option value="">All subjects</option>
            {options.subjects.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        ) : (
          <input value={filters.subject} placeholder="All subjects" onChange={(e) => onFilters({ ...filters, subject: e.target.value })} />
        )}
      </label>
      <label>
        Chapter
        {options.chapters.length ? (
          <select value={filters.chapter} onChange={(e) => onFilters({ ...filters, chapter: e.target.value })}>
            <option value="">All chapters</option>
            {options.chapters.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        ) : (
          <input value={filters.chapter} placeholder="All chapters" onChange={(e) => onFilters({ ...filters, chapter: e.target.value })} />
        )}
      </label>
      <fieldset>
        <legend>Source types (none ticked = all)</legend>
        {typeOptions.map((t) => (
          <label key={t} className="option">
            <input type="checkbox" checked={filters.sourceTypes.includes(t)} onChange={() => toggleType(t)} />
            {t}
          </label>
        ))}
      </fieldset>
    </aside>
  );
}
