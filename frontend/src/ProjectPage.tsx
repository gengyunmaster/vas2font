import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "./api";
import { GeneratorSection } from "./sections/GeneratorSection";
import { GlyphsSection } from "./sections/GlyphsSection";
import { Overview } from "./sections/Overview";
import { TemplatesSection } from "./sections/TemplatesSection";
import { UploadsSection } from "./sections/UploadsSection";
import type { Project, Template, Upload } from "./types";

type Section = "overview" | "templates" | "uploads" | "glyphs" | "generate";

interface ProjectPageProps {
  projectId: string;
  onExit: (message?: string) => void;
}

export function ProjectPage({ projectId, onExit }: ProjectPageProps) {
  const [project, setProject] = useState<Project | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [section, setSection] = useState<Section>("overview");
  const [revision, setRevision] = useState(0);
  const [templateSeed, setTemplateSeed] = useState<{ characters: string; key: number } | null>(
    null,
  );
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextProject, nextTemplates, nextUploads] = await Promise.all([
        api<Project>(`/api/projects/${projectId}`),
        api<Template[]>(`/api/projects/${projectId}/templates`),
        api<Upload[]>(`/api/projects/${projectId}/uploads`),
      ]);
      setProject(nextProject);
      setTemplates(nextTemplates);
      setUploads(nextUploads);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) {
        onExit("The project could not be opened. Check your access code.");
        return;
      }
      setError(caught instanceof Error ? caught.message : "Unable to load the project");
    } finally {
      setLoading(false);
    }
  }, [projectId, onExit]);

  useEffect(() => {
    void load();
  }, [load]);

  async function changed() {
    await load();
    setRevision((value) => value + 1);
  }

  const navigation: { id: Section; label: string; count?: number }[] = [
    { id: "overview", label: "Overview" },
    {
      id: "templates",
      label: "Templates",
      count: templates.filter((template) => !template.built_in).length,
    },
    { id: "uploads", label: "Uploads", count: uploads.length },
    { id: "glyphs", label: "Glyphs" },
    { id: "generate", label: "Generate" },
  ];

  if (loading && !project) {
    return (
      <main className="project-loading">
        <div className="brand-mark" aria-hidden="true">
          V
        </div>
        <p>Opening your type foundry...</p>
      </main>
    );
  }

  if (!project) {
    return (
      <main className="project-loading">
        <p className="form-error" role="alert">
          {error || "The project is unavailable"}
        </p>
        <button type="button" className="button button-secondary" onClick={() => onExit()}>
          Return home
        </button>
      </main>
    );
  }

  return (
    <div className="project-page">
      <header className="project-header">
        <button type="button" className="project-brand" onClick={() => onExit()}>
          <span className="brand-mark brand-mark-small" aria-hidden="true">
            V
          </span>
          <span>VAS2Font</span>
        </button>
        <button type="button" className="text-button" onClick={() => onExit()}>
          Close project
        </button>
      </header>
      <section className="project-title">
        <div>
          <p className="eyebrow">Personal type foundry</p>
          <h1>{project.font_family}</h1>
          <p>Font version {project.font_version}</p>
        </div>
        <button
          type="button"
          className="button button-primary"
          onClick={() => setSection("generate")}
        >
          Generate font
        </button>
      </section>
      <nav className="project-nav" aria-label="Project sections">
        {navigation.map((item) => (
          <button
            type="button"
            key={item.id}
            className={section === item.id ? "nav-item nav-item-active" : "nav-item"}
            aria-current={section === item.id ? "page" : undefined}
            onClick={() => setSection(item.id)}
          >
            {item.label}
            {item.count !== undefined && <span>{item.count}</span>}
          </button>
        ))}
      </nav>
      {error && (
        <p className="form-error project-error" role="alert">
          {error}
        </p>
      )}
      <main className="project-content">
        {section === "overview" && (
          <Overview
            project={project}
            onChanged={changed}
            onDeleted={() => onExit("Project deleted")}
          />
        )}
        {section === "templates" && (
          <TemplatesSection
            projectId={project.id}
            templates={templates}
            onChanged={changed}
            seed={templateSeed}
            onSeedConsumed={() => setTemplateSeed(null)}
          />
        )}
        {section === "uploads" && (
          <UploadsSection
            projectId={project.id}
            templates={templates}
            uploads={uploads}
            onChanged={changed}
          />
        )}
        {section === "glyphs" && (
          <GlyphsSection
            key={`${project.id}-${revision}`}
            projectId={project.id}
            onCreateCorrection={(characters) => {
              setTemplateSeed({ characters, key: Date.now() });
              setSection("templates");
            }}
          />
        )}
        {section === "generate" && (
          <GeneratorSection
            key={project.id}
            project={project}
            uploadCount={uploads.length}
            revision={revision}
          />
        )}
      </main>
      <footer className="project-footer">Crafted one stroke at a time.</footer>
    </div>
  );
}
