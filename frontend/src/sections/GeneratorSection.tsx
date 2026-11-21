import { useCallback, useEffect, useState } from "react";
import { apiBlob } from "../api";
import type { Project } from "../types";

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
    clearPreview();
    setError(
      revision === 0 ? "" : "Project inputs changed. Generate a new font to update this section.",
    );
  }, [revision, clearPreview]);

  useEffect(() => clearPreview, [clearPreview]);

  async function generate() {
    setBusy(true);
    setError("");
    clearPreview();
    let pendingUrl: string | null = null;
    try {
      const response = await apiBlob(`/api/projects/${project.id}/font`, { method: "POST" });
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      pendingUrl = url;
      const family = `VAS2FontPreview${Date.now()}`;
      const style = document.createElement("style");
      style.dataset.vas2fontPreview = "true";
      style.textContent = `@font-face{font-family:"${family}";src:url("${url}") format("opentype");font-style:normal;font-weight:400;font-display:block;}`;
      document.head.appendChild(style);
      await document.fonts.load(`400 48px "${family}"`, text);
      setPreview({
        url,
        family,
        glyphCount: Number(response.headers.get("X-Handwritten-Glyph-Count") ?? "0"),
      });
    } catch (caught) {
      if (pendingUrl) URL.revokeObjectURL(pendingUrl);
      clearPreview();
      setError(caught instanceof Error ? caught.message : "Unable to generate the font");
    } finally {
      setBusy(false);
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
