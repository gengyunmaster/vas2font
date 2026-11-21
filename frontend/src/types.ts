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

export interface ApiFailure {
  code: string;
  message: string;
  details?: unknown;
}
