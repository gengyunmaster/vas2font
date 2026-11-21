import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiBlob } from "../api";
import type { GenerationJob, Project } from "../types";

interface GeneratorSectionProps {
  project: Project;
  uploadCount: number;
  revision: number;
}

interface Preview {
  url: string;
  family: string;
  glyphCount: number;
}

const DEFAULT_TEXT =
  "The quick brown fox jumps over the lazy dog.\nABCDEFGHIJKLMNOPQRSTUVWXYZ\n0123456789\n一人永木水火心之女月田\n国明林好江语思草意问这龙赢";

export function GeneratorSection({ project, uploadCount, revision }: GeneratorSectionProps) {
  const [text, setText] = useState(DEFAULT_TEXT);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [job, setJob] = useState<GenerationJob | null>(null);
  const generationAttempt = useRef(0);

  const clearPreview = useCallback(() => {
    setPreview((current) => {
      if (current) URL.revokeObjectURL(current.url);
      return null;
    });
    document.querySelectorAll("style[data-vas2font-preview]").forEach((style) => {
      style.remove();
    });
  }, []);

  useEffect(() => {
    generationAttempt.current += 1;
    setBusy(false);
    setJob(null);
    clearPreview();
    setError(
      revision === 0 ? "" : "Project inputs changed. Generate a new font to update this section.",
    );
  }, [revision, clearPreview]);

  useEffect(
    () => () => {
      generationAttempt.current += 1;
      clearPreview();
    },
    [clearPreview],
  );

  async function generate() {
    const attempt = generationAttempt.current + 1;
    generationAttempt.current = attempt;
    setBusy(true);
    setError("");
    setJob(null);
    clearPreview();
    let pendingUrl: string | null = null;
    try {
      let currentJob = await api<GenerationJob>(`/api/projects/${project.id}/font`, {
        method: "POST",
      });
      setJob(currentJob);
      while (currentJob.status === "queued" || currentJob.status === "running") {
        await new Promise((resolve) => window.setTimeout(resolve, 400));
        if (generationAttempt.current !== attempt) return;
        currentJob = await api<GenerationJob>(
          `/api/projects/${project.id}/font/jobs/${currentJob.id}`,
        );
        setJob(currentJob);
      }
      if (currentJob.status === "failed") {
        throw new Error(currentJob.error || "Font generation failed");
      }
      const response = await apiBlob(
        `/api/projects/${project.id}/font/jobs/${currentJob.id}/download`,
      );
      if (generationAttempt.current !== attempt) return;
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      pendingUrl = url;
      const family = `VAS2FontPreview${Date.now()}`;
      const style = document.createElement("style");
      style.dataset.vas2fontPreview = "true";
      style.textContent = `@font-face{font-family:"${family}";src:url("${url}") format("opentype");font-style:normal;font-weight:400;font-display:block;}`;
      document.head.appendChild(style);
      await document.fonts.load(`400 48px "${family}"`, text);
      if (generationAttempt.current !== attempt) return;
      setPreview({
        url,
        family,
        glyphCount: Number(response.headers.get("X-Handwritten-Glyph-Count") ?? "0"),
      });
    } catch (caught) {
      if (generationAttempt.current !== attempt) return;
      if (pendingUrl) URL.revokeObjectURL(pendingUrl);
      clearPreview();
      setError(caught instanceof Error ? caught.message : "Unable to generate the font");
    } finally {
      if (generationAttempt.current === attempt) setBusy(false);
    }
  }

  const filename = `${project.font_family.replace(/[^A-Za-z0-9_-]+/g, "-") || "handwriting"}.otf`;

  return (
    <div className="generator-layout">
      <section className="paper-card content-card">
        <p className="eyebrow">Proof and export</p>
        <h2>Generate your font</h2>
        <p className="section-copy">
          Generation uses the current metadata and upload order. The font is created on demand and
          is never stored on the server.
        </p>
        <div className="generate-actions">
          <button
            type="button"
            className="button button-primary"
            onClick={generate}
            disabled={busy || uploadCount === 0}
          >
            {busy ? "Generating font..." : preview ? "Regenerate font" : "Generate font"}
          </button>
          {preview && (
            <a className="button button-secondary" href={preview.url} download={filename}>
              Download OTF
            </a>
          )}
        </div>
        {job && (
          <div className="generation-progress" aria-live="polite">
            <div>
              <span>{job.stage}</span>
              <strong>{job.progress}%</strong>
            </div>
            <progress max={100} value={job.progress} aria-label="Font generation progress" />
          </div>
        )}
        {uploadCount === 0 && (
          <p className="field-hint">Upload at least one notebook before generating.</p>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <label className="preview-input">
          Preview text
          <textarea value={text} onChange={(event) => setText(event.target.value)} rows={5} />
        </label>
        <div className="coverage-note">
          {preview
            ? `${preview.glyphCount} handwritten code points plus required automatic glyphs.`
            : "Your generated character coverage will appear here."}
        </div>
      </section>
      <section className="paper-card preview-card" aria-label="Font preview">
        <div className="preview-heading">
          <span className="eyebrow">Live specimen</span>
          <span>{preview ? "Generated font" : "Waiting for generation"}</span>
        </div>
        <div
          className={preview ? "font-preview font-preview-ready" : "font-preview"}
          style={preview ? { fontFamily: `"${preview.family}", serif` } : undefined}
        >
          {preview ? text || "Enter preview text above." : "Your handwriting will take shape here."}
        </div>
        <p className="preview-footnote">
          Characters outside the generated set use the system fallback font.
        </p>
      </section>
    </div>
  );
}
