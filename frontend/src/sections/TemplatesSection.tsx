import { type FormEvent, useMemo, useState } from "react";
import { api, apiBlob, downloadBlob } from "../api";
import { ConfirmDialog, Modal } from "../components/Modal";
import type { Template } from "../types";

interface TemplatesSectionProps {
  projectId: string;
  templates: Template[];
  onChanged: () => Promise<void>;
}

export function TemplatesSection({ projectId, templates, onChanged }: TemplatesSectionProps) {
  const [editing, setEditing] = useState<Template | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [name, setName] = useState("");
  const [version, setVersion] = useState(1);
  const [characters, setCharacters] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState("");
  const [deleting, setDeleting] = useState<Template | null>(null);
  const characterCount = useMemo(
    () =>
      new Set(Array.from(characters.normalize("NFC")).filter((character) => !/\s/.test(character)))
        .size,
    [characters],
  );

  function openCreate() {
    setEditing(null);
    setName("");
    setVersion(1);
    setCharacters("");
    setError("");
    setFormOpen(true);
  }

  function openEdit(template: Template) {
    setEditing(template);
    setName(template.name);
    setVersion(template.version);
    setCharacters(template.characters);
    setError("");
    setFormOpen(true);
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(`/api/projects/${projectId}/templates${editing ? `/${editing.id}` : ""}`, {
        method: editing ? "PATCH" : "POST",
        jsonBody: { name, version, characters },
      });
      await onChanged();
      setFormOpen(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to save the template");
    } finally {
      setBusy(false);
    }
  }

  async function download(template: Template) {
    setError("");
    setDownloading(template.id);
    try {
      const response = await apiBlob(`/api/templates/${template.id}/pdf`);
      downloadBlob(
        await response.blob(),
        `${template.name.replace(/[^A-Za-z0-9_-]+/g, "-")}-v${template.version}.pdf`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to download the PDF");
    } finally {
      setDownloading("");
    }
  }

  async function remove() {
    if (!deleting) return;
    setBusy(true);
    try {
      await api(`/api/projects/${projectId}/templates/${deleting.id}`, { method: "DELETE" });
      await onChanged();
      setDeleting(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete the template");
      setDeleting(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="paper-card content-card">
      <div className="section-heading">
        <div>
          <p className="eyebrow">Character sets</p>
          <h2>Writing templates</h2>
          <p className="section-copy">
            Choose a built-in set or compose a focused set for batch writing and glyph corrections.
          </p>
        </div>
        <button type="button" className="button button-primary" onClick={openCreate}>
          New template
        </button>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="template-grid">
        {templates.map((template) => (
          <article className="template-card" key={template.id}>
            <div className="template-card-heading">
              <span className={template.built_in ? "badge" : "badge badge-accent"}>
                {template.built_in ? "Built-in" : "Custom"}
              </span>
              <span className="template-version">v{template.version}</span>
            </div>
            <h3>{template.name}</h3>
            <p>{template.character_count.toLocaleString("en")} code points</p>
            <div className="character-sample">
              {Array.from(template.characters).slice(0, 18).join("")}
              {template.character_count > 18 && "..."}
            </div>
            <div className="card-actions">
              <button
                type="button"
                className="button button-small button-secondary"
                onClick={() => download(template)}
                disabled={downloading === template.id}
              >
                {downloading === template.id ? "Preparing PDF..." : "Download PDF"}
              </button>
              {!template.built_in && (
                <>
                  <button type="button" className="text-button" onClick={() => openEdit(template)}>
                    Edit
                  </button>
                  <button
                    type="button"
                    className="text-button danger-text"
                    onClick={() => setDeleting(template)}
                  >
                    Delete
                  </button>
                </>
              )}
            </div>
          </article>
        ))}
      </div>
      <aside className="callout">
        <strong>Active uploads protect their templates.</strong> Create a new version to change a
        template in use. A custom template can be edited or deleted after all referencing uploads
        are deleted.
      </aside>
      {formOpen && (
        <Modal
          title={editing ? "Edit template" : "New template"}
          onClose={() => setFormOpen(false)}
          wide
        >
          <form onSubmit={save} className="template-form">
            <div className="modal-body stack-form">
              <div className="two-column-fields">
                <label>
                  Template name
                  <input
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    maxLength={80}
                    required
                  />
                </label>
                <label>
                  Version
                  <input
                    type="number"
                    min={1}
                    max={1000000}
                    value={version}
                    onChange={(event) => setVersion(Number(event.target.value))}
                    required
                  />
                </label>
              </div>
              <label>
                Characters
                <textarea
                  value={characters}
                  onChange={(event) => setCharacters(event.target.value)}
                  rows={8}
                  placeholder="Enter or paste characters, for example: 永和九年"
                  required
                />
                <span className="field-hint">
                  {characterCount.toLocaleString("en")} unique non-whitespace code points. Order is
                  preserved.
                </span>
              </label>
              {error && (
                <p className="form-error" role="alert">
                  {error}
                </p>
              )}
            </div>
            <footer className="modal-actions">
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setFormOpen(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="button button-primary"
                disabled={busy || characterCount === 0}
              >
                {busy ? "Saving..." : editing ? "Save template" : "Create template"}
              </button>
            </footer>
          </form>
        </Modal>
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete template"
          confirmLabel="Delete template"
          busy={busy}
          onConfirm={remove}
          onClose={() => setDeleting(null)}
        >
          <p>
            Delete{" "}
            <strong>
              {deleting.name} v{deleting.version}
            </strong>
            ?
          </p>
          <p>This is allowed only when no active upload references the template.</p>
        </ConfirmDialog>
      )}
    </section>
  );
}
