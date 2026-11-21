import { type FormEvent, useEffect, useRef, useState } from "react";
import { api, formatBytes, formatDate } from "../api";
import { ConfirmDialog } from "../components/Modal";
import type { Template, Upload } from "../types";

interface UploadsSectionProps {
  projectId: string;
  templates: Template[];
  uploads: Upload[];
  onChanged: () => Promise<void>;
}

export function UploadsSection({ projectId, templates, uploads, onChanged }: UploadsSectionProps) {
  const [file, setFile] = useState<File | null>(null);
  const [templateId, setTemplateId] = useState(templates[0]?.id ?? "");
  const [busy, setBusy] = useState(false);
  const [ordering, setOrdering] = useState(false);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState<Upload | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!templates.some((template) => template.id === templateId)) {
      setTemplateId(templates[0]?.id ?? "");
    }
  }, [templates, templateId]);

  function selectFile(selected: File | null) {
    setFile(selected);
    setError("");
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file || !templateId) return;
    setBusy(true);
    setError("");
    const form = new FormData();
    form.append("file", file);
    form.append("template_id", templateId);
    try {
      await api(`/api/projects/${projectId}/uploads`, { method: "POST", body: form });
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      await onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to upload the notebook");
    } finally {
      setBusy(false);
    }
  }

  async function move(index: number, direction: -1 | 1) {
    const destination = index + direction;
    if (destination < 0 || destination >= uploads.length) return;
    setOrdering(true);
    setError("");
    const ordered = [...uploads];
    [ordered[index], ordered[destination]] = [ordered[destination], ordered[index]];
    try {
      await api(`/api/projects/${projectId}/upload-order`, {
        method: "PUT",
        jsonBody: { ordered_ids: ordered.map((upload) => upload.id) },
      });
      await onChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to reorder uploads");
    } finally {
      setOrdering(false);
    }
  }

  async function remove() {
    if (!deleting) return;
    setBusy(true);
    try {
      await api(`/api/projects/${projectId}/uploads/${deleting.id}`, { method: "DELETE" });
      await onChanged();
      setDeleting(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to delete the upload");
      setDeleting(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="paper-card content-card">
      <p className="eyebrow">Handwriting sources</p>
      <h2>Notebook uploads</h2>
      <p className="section-copy">
        Upload the JSON file extracted from your vas ZIP. Higher entries override duplicate
        characters in lower entries.
      </p>
      <form onSubmit={upload} className="upload-form">
        <label
          className={file ? "drop-zone drop-zone-selected" : "drop-zone"}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            selectFile(event.dataTransfer.files[0] ?? null);
          }}
        >
          <input
            ref={fileInput}
            type="file"
            accept=".json,application/json"
            onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
          />
          <span className="drop-zone-title">
            {file ? file.name : "Choose or drop a notebook.json"}
          </span>
          <span className="field-hint">
            {file
              ? `${formatBytes(file.size)} ready to upload`
              : "JSON only. Do not upload the vas ZIP archive."}
          </span>
        </label>
        <label>
          Character set template
          <select
            value={templateId}
            onChange={(event) => setTemplateId(event.target.value)}
            required
          >
            {templates.map((template) => (
              <option value={template.id} key={template.id}>
                {template.name} v{template.version} ({template.character_count} characters)
              </option>
            ))}
          </select>
        </label>
        <button
          type="submit"
          className="button button-primary"
          disabled={!file || !templateId || busy}
        >
          {busy ? "Validating and uploading..." : "Upload notebook"}
        </button>
      </form>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="upload-list">
        {uploads.length === 0 ? (
          <div className="empty-state">
            <h3>No handwriting yet</h3>
            <p>Download a template, write in vas, and upload the exported JSON here.</p>
          </div>
        ) : (
          uploads.map((upload, index) => {
            const template = templates.find((item) => item.id === upload.template_id);
            return (
              <article className="upload-row" key={upload.id}>
                <div className="priority-number">{upload.position}</div>
                <div className="upload-details">
                  <div className="upload-title-row">
                    <h3>{upload.original_filename}</h3>
                    <span className="badge">{upload.glyph_count} glyphs</span>
                  </div>
                  <p>
                    {template ? `${template.name} v${template.version}` : "Referenced template"} ·{" "}
                    {upload.stroke_count} strokes · {formatBytes(upload.file_size_bytes)}
                  </p>
                  <p className="upload-date">Uploaded {formatDate(upload.created_at)}</p>
                  {(upload.validation_report.overflow_strokes > 0 ||
                    upload.validation_report.missing_characters.length > 0) && (
                    <details className="validation-details">
                      <summary>Validation notes</summary>
                      <p>
                        {upload.validation_report.overflow_strokes} strokes contain points outside
                        their assigned cells.
                      </p>
                      <p>
                        {upload.validation_report.missing_characters.length} template characters
                        have no handwriting in this upload.
                      </p>
                    </details>
                  )}
                </div>
                <div className="upload-actions">
                  <button
                    type="button"
                    className="text-button"
                    disabled={index === 0 || ordering}
                    onClick={() => move(index, -1)}
                  >
                    Up
                  </button>
                  <button
                    type="button"
                    className="text-button"
                    disabled={index === uploads.length - 1 || ordering}
                    onClick={() => move(index, 1)}
                  >
                    Down
                  </button>
                  <button
                    type="button"
                    className="text-button danger-text"
                    onClick={() => setDeleting(upload)}
                  >
                    Delete
                  </button>
                </div>
              </article>
            );
          })
        )}
      </div>
      {deleting && (
        <ConfirmDialog
          title="Delete upload"
          confirmLabel="Delete upload"
          busy={busy}
          onConfirm={remove}
          onClose={() => setDeleting(null)}
        >
          <p>
            Delete <strong>{deleting.original_filename}</strong> from the active font sources?
          </p>
          <p>
            Lower-priority glyphs will be used for characters that were covered only by this upload.
          </p>
        </ConfirmDialog>
      )}
    </section>
  );
}
