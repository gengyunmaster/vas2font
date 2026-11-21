export interface Project {
  id: string;
  font_family: string;
  font_version: string;
  pipeline_version: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreated extends Project {
  access_code: string;
}

export interface Template {
  id: string;
  project_id: string | null;
  name: string;
  version: number;
  built_in: boolean;
  character_count: number;
  characters: string;
  created_at: string;
  updated_at: string;
}

export interface ValidationReport {
  missing_characters: string[];
  overflow_strokes: number;
  page_count: number;
}

export interface Upload {
  id: string;
  template_id: string;
  position: number;
  original_filename: string;
  file_size_bytes: number;
  sha256: string;
  vas_version: number;
  glyph_count: number;
  stroke_count: number;
  validation_report: ValidationReport;
  created_at: string;
  updated_at: string;
}

export interface GlyphPreview {
  view_box: string;
  paths: { d: string; stroke_width: number }[];
}

export interface GlyphItem {
  character: string;
  codepoint: number;
  status: "covered" | "missing";
  source_upload_id: string | null;
  source_filename: string | null;
  source_position: number | null;
  template_name: string | null;
  template_version: number | null;
  duplicate_count: number;
  overridden_upload_ids: string[];
  overflow_strokes: number;
  preview: GlyphPreview | null;
}

export interface GlyphInspection {
  items: GlyphItem[];
  total: number;
  covered: number;
  missing: number;
  duplicates: number;
  offset: number;
  limit: number;
}

export interface GenerationJob {
  id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  progress: number;
  stage: string;
  error: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  downloaded_at: string | null;
}

export interface ApiFailure {
  code: string;
  message: string;
  details?: unknown;
}
