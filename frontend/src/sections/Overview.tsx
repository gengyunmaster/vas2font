import { type FormEvent, useState } from "react";
import { api } from "../api";
import { ConfirmDialog } from "../components/Modal";
import type { Project } from "../types";

interface OverviewProps {
  project: Project;
  onChanged: () => Promise<void>;
  onDeleted: () => void;
}

export function Overview({ project, onChanged, onDeleted }: OverviewProps) {
  const [fontFamily, setFontFamily] = useState(project.font_family);
  const [fontVersion, setFontVersion] = useState(project.font_version);
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api(`/api/projects/${project.id}`, {
        method: "PATCH",
        jsonBody: { font_family: fontFamily, font_version: fontVersion },
      });
      await onChanged();
      setMessage("Font metadata saved. Generate the font again to update the preview.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save metadata");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setDeleting(true);
    try {
      await api(`/api/projects/${project.id}`, { method: "DELETE" });
      onDeleted();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete the project");
      setDeleting(false);
      setConfirming(false);
    }
  }

  return (
    <div className="section-layout">
      <section className="paper-card content-card">
        <p className="eyebrow">Font identity</p>
        <h2>Project metadata</h2>
        <p className="section-copy">
          These details are written into the OpenType name and version tables each time you generate
          the font.
        </p>
        <form onSubmit={save} className="stack-form metadata-form">
          <label>
            Font family
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
            <span className="field-hint">Use numeric major.minor notation, such as 1.0.</span>
          </label>
          <div className="form-row">
            <button type="submit" className="button button-primary" disabled={busy}>
              Save changes
            </button>
          </div>
        </form>
        {message && (
          <p className="form-success" role="status">
            {message}
          </p>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <dl className="metadata-list">
          <div>
            <dt>Pipeline</dt>
            <dd>Version {project.pipeline_version}</dd>
          </div>
          <div>
            <dt>Project ID</dt>
            <dd>
              <code>{project.id}</code>
            </dd>
          </div>
        </dl>
      </section>
      <aside className="paper-card danger-card">
        <p className="eyebrow">Danger zone</p>
        <h2>Delete this project</h2>
        <p>
          This closes the project to everyone with its access code. Templates and uploads are
          retained as soft-deleted records, not physically erased.
        </p>
        <button type="button" className="button button-danger" onClick={() => setConfirming(true)}>
          Delete project
        </button>
      </aside>
      {confirming && (
        <ConfirmDialog
          title="Delete project"
          confirmLabel="Delete project"
          busy={deleting}
          onConfirm={remove}
          onClose={() => setConfirming(false)}
        >
          <p>
            Delete <strong>{project.font_family}</strong> and disable its access code?
          </p>
          <p>This action cannot be undone in the application.</p>
        </ConfirmDialog>
      )}
    </div>
  );
}
