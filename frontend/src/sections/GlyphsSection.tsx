import { type FormEvent, useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { GlyphInspection, GlyphItem } from "../types";

interface GlyphsSectionProps {
  projectId: string;
  onCreateCorrection: (characters: string) => void;
}

type GlyphFilter = "all" | "covered" | "missing" | "duplicates" | "warnings";

export function GlyphsSection({ projectId, onCreateCorrection }: GlyphsSectionProps) {
  const [result, setResult] = useState<GlyphInspection | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<GlyphFilter>("all");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const limit = 48;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    const parameters = new URLSearchParams({
      search,
      status: filter,
      offset: String(offset),
      limit: String(limit),
    });
    try {
      setResult(await api<GlyphInspection>(`/api/projects/${projectId}/glyphs?${parameters}`));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to inspect glyphs");
    } finally {
      setLoading(false);
    }
  }, [projectId, search, filter, offset]);

  useEffect(() => {
    void load();
  }, [load]);

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    setOffset(0);
    setSearch(searchInput);
  }

  function toggle(character: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(character)) next.delete(character);
      else next.add(character);
      return next;
    });
  }

  return (
    <section className="paper-card content-card">
      <p className="eyebrow">Coverage and provenance</p>
      <h2>Glyph inspector</h2>
      <p className="section-copy">
        See which upload supplies each final glyph, find missing characters, and build a focused
        correction template.
      </p>
      <div className="glyph-summary">
        <span>
          <strong>{result?.covered ?? 0}</strong> covered
        </span>
        <span>
          <strong>{result?.missing ?? 0}</strong> missing
        </span>
        <span>
          <strong>{result?.duplicates ?? 0}</strong> with duplicates
        </span>
      </div>
      <div className="glyph-toolbar">
        <form onSubmit={submitSearch} className="glyph-search">
          <input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Character or U+6C38"
            aria-label="Search glyphs"
          />
          <button type="submit" className="button button-small button-secondary">
            Search
          </button>
        </form>
        <label>
          Show
          <select
            value={filter}
            onChange={(event) => {
              setFilter(event.target.value as GlyphFilter);
              setOffset(0);
            }}
          >
            <option value="all">All glyphs</option>
            <option value="covered">Covered</option>
            <option value="missing">Missing</option>
            <option value="duplicates">Duplicates</option>
            <option value="warnings">Overflow warnings</option>
          </select>
        </label>
        <button
          type="button"
          className="button button-small button-primary"
          disabled={selected.size === 0}
          onClick={() => onCreateCorrection(Array.from(selected).join(""))}
        >
          Create correction template{selected.size ? ` (${selected.size})` : ""}
        </button>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {loading && <p className="field-hint">Inspecting handwriting sources...</p>}
      <div className="glyph-grid">
        {result?.items.map((item) => (
          <GlyphCard
            key={item.codepoint}
            item={item}
            selected={selected.has(item.character)}
            onToggle={() => toggle(item.character)}
          />
        ))}
      </div>
      {result?.items.length === 0 && (
        <div className="empty-state">
          <h3>No glyphs found</h3>
          <p>Change the search or filter.</p>
        </div>
      )}
      <footer className="pagination">
        <button
          type="button"
          className="button button-small button-secondary"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - limit))}
        >
          Previous
        </button>
        <span>
          {result && result.total > 0
            ? `${offset + 1}-${Math.min(offset + limit, result.total)} of ${result.total}`
            : "0 results"}
        </span>
        <button
          type="button"
          className="button button-small button-secondary"
          disabled={!result || offset + limit >= result.total}
          onClick={() => setOffset(offset + limit)}
        >
          Next
        </button>
      </footer>
    </section>
  );
}

function GlyphCard({
  item,
  selected,
  onToggle,
}: {
  item: GlyphItem;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <article className={selected ? "glyph-card glyph-card-selected" : "glyph-card"}>
      <label className="glyph-select">
        <input type="checkbox" checked={selected} onChange={onToggle} />
        <span>Select</span>
      </label>
      <div className="glyph-thumbnail">
        {item.preview ? (
          <svg
            viewBox={item.preview.view_box}
            role="img"
            aria-label={`Handwritten ${item.character}`}
          >
            <g fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
              {item.preview.paths.map((path) => (
                <path key={path.d} d={path.d} strokeWidth={path.stroke_width} />
              ))}
            </g>
          </svg>
        ) : (
          <span>{item.character}</span>
        )}
      </div>
      <div className="glyph-card-title">
        <strong>{item.character}</strong>
        <code>U+{item.codepoint.toString(16).toUpperCase().padStart(4, "0")}</code>
      </div>
      <p className="glyph-source">
        {item.status === "missing"
          ? "Missing from all uploads"
          : `Priority ${item.source_position} · ${item.source_filename}`}
      </p>
      <div className="glyph-badges">
        {item.duplicate_count > 1 && <span className="badge">{item.duplicate_count} sources</span>}
        {item.overflow_strokes > 0 && <span className="badge badge-accent">Overflow</span>}
      </div>
    </article>
  );
}
