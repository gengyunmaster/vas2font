import { type FormEvent, useState } from "react";
import { api, setAccessCode } from "./api";
import { Modal } from "./components/Modal";
import type { Project, ProjectCreated } from "./types";

interface HomeProps {
  onOpen: (projectId: string, accessCode: string) => void;
}

export function Home({ onOpen }: HomeProps) {
  const [fontFamily, setFontFamily] = useState("My Handwriting");
  const [fontVersion, setFontVersion] = useState("1.0");
  const [codeInput, setCodeInput] = useState("");
  const [created, setCreated] = useState<ProjectCreated | null>(null);
  const [busy, setBusy] = useState<"create" | "open" | "import" | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  async function createProject(event: FormEvent) {
    event.preventDefault();
    setBusy("create");
    setError("");
    try {
      const project = await api<ProjectCreated>("/api/projects", {
        method: "POST",
        jsonBody: { font_family: fontFamily, font_version: fontVersion },
      });
      setCreated(project);
      setCopied(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create the project");
    } finally {
      setBusy(null);
    }
  }

  async function openProject(event: FormEvent) {
    event.preventDefault();
    setBusy("open");
    setError("");
    try {
      const project = await api<Project>("/api/projects/open", {
        method: "POST",
        jsonBody: { access_code: codeInput },
      });
      setAccessCode(codeInput);
      onOpen(project.id, codeInput);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to open the project");
    } finally {
      setBusy(null);
    }
  }

  async function importBackup(file: File | null) {
    if (!file) return;
    setBusy("import");
    setError("");
    try {
      const data = JSON.parse(await file.text());
      const project = await api<ProjectCreated>("/api/projects/import", {
        method: "POST",
        jsonBody: data,
      });
      setCreated(project);
      setCopied(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to import the project backup");
    } finally {
      setBusy(null);
    }
  }

  return (
    <main className="home-page">
      <section className="hero">
        <div className="brand-mark" aria-hidden="true">
          V
        </div>
        <p className="eyebrow">A personal type foundry</p>
        <h1>
          Your hand.
          <br />
          Your typeface.
        </h1>
        <p className="hero-copy">
          Turn natural handwriting into a living OpenType font. Write on paper-like templates in
          vas, then compose, refine, and download your own typeface.
        </p>
        <div className="hero-rule" aria-hidden="true" />
        <p className="hero-note">
          No account. No tracking. Your project opens with a private access code.
        </p>
      </section>
      <section className="home-actions" aria-label="Project actions">
        <div className="paper-card action-card">
          <p className="section-number">01</p>
          <h2>Create a project</h2>
          <p>Begin a new typeface with its own templates, notebooks, and font metadata.</p>
          <form onSubmit={createProject} className="stack-form">
            <label>
              Font name
              <input
                value={fontFamily}
                onChange={(event) => setFontFamily(event.target.value)}
                maxLength={80}
                required
              />
            </label>
            <label>
              Version
              <input
                value={fontVersion}
                onChange={(event) => setFontVersion(event.target.value)}
                pattern="\d+\.\d{1,3}"
                required
              />
            </label>
            <button type="submit" className="button button-primary" disabled={busy !== null}>
              {busy === "create" ? "Creating..." : "Create project"}
            </button>
          </form>
        </div>
        <div className="paper-card action-card">
          <p className="section-number">02</p>
          <h2>Open a project</h2>
          <p>
            Return to your work with the private access code shown when the project was created.
          </p>
          <form onSubmit={openProject} className="stack-form">
            <label>
              Access code
              <input
                value={codeInput}
                onChange={(event) => setCodeInput(event.target.value)}
                placeholder="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX-X"
                autoCapitalize="characters"
                autoComplete="off"
                spellCheck={false}
                required
              />
            </label>
            <button type="submit" className="button button-secondary" disabled={busy !== null}>
              {busy === "open" ? "Opening..." : "Open project"}
            </button>
          </form>
        </div>
        <div className="paper-card action-card">
          <p className="section-number">03</p>
          <h2>Import a backup</h2>
          <p>
            Restore templates, notebooks, metadata, and priority order as a new project with a new
            access code.
          </p>
          <label className="button button-secondary backup-file-button">
            {busy === "import" ? "Importing..." : "Import project backup"}
            <input
              type="file"
              accept=".json,application/json"
              disabled={busy !== null}
              onChange={(event) => importBackup(event.target.files?.[0] ?? null)}
            />
          </label>
        </div>
        {error && (
          <p className="form-error home-error" role="alert">
            {error}
          </p>
        )}
      </section>
      <footer className="home-footer">Handwritten in spirit. Open by design.</footer>
      {created && (
        <Modal title="Your private access code" onClose={() => setCreated(null)}>
          <div className="modal-body access-code-dialog">
            <p>
              Copy this code now. It is the only way to open, edit, or delete this project later.
            </p>
            <code className="access-code">{created.access_code}</code>
            <button
              type="button"
              className="button button-secondary"
              onClick={async () => {
                await navigator.clipboard.writeText(created.access_code);
                setCopied(true);
              }}
            >
              {copied ? "Copied" : "Copy access code"}
            </button>
            <p className="warning-copy">
              Anyone with this code has full access. The code cannot be recovered if lost.
            </p>
          </div>
          <footer className="modal-actions">
            <button
              type="button"
              className="button button-primary"
              onClick={() => {
                setAccessCode(created.access_code);
                onOpen(created.id, created.access_code);
              }}
            >
              Enter project
            </button>
          </footer>
        </Modal>
      )}
    </main>
  );
}
