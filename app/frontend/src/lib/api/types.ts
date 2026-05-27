export interface JobPosting {
  id: string;
  title: string;
  company: string;
  location?: string;
  url?: string;
  source?: string;
  source_job_id?: string;
  posted_at?: string;
  employment_type?: string;
  workplace?: string;
  salary_text?: string;
  status: string;
  score?: number;
  recommendation?: string;
  parsed_json?: Record<string, unknown>;
  scraped_json?: Record<string, unknown>;
  skills?: JobSkill[];
  created_at: string;
  updated_at?: string;
  raw_jd?: string;
}

export interface JobSkill {
  id: string;
  name: string;
  category: string;
  source: string;
  confidence?: number;
  created_at: string;
}

export interface CandidateProfile {
  id: string;
  full_name: string;
  headline: string;
  location?: string;
  raw_cv_md: string;
}

export interface MatchReport {
  id: string;
  job_id: string;
  overall_score: number;
  recommendation: string;
  breakdown: Record<string, number>;
  top_reasons: string[];
  gaps: string[];
  explanation?: string;
}

export interface ResumeArtifact {
  id: string;
  job_id: string;
  has_html: boolean;
  has_pdf: boolean;
  provenance: unknown[];
}

export interface Application {
  id: string;
  job_id: string;
  job_title?: string;
  company?: string;
  status: string;
  score?: number;
  notes?: string;
  created_at: string;
}

export interface LLMRun {
  id: string;
  task: string;
  provider: string;
  model: string;
  status: string;
  latency_ms: number;
  created_at: string;
  error_message?: string;
}

export interface ImportError {
  url: string;
  error: string;
}

export interface JobImportResponse {
  imported: JobPosting[];
  errors: ImportError[];
}

export interface PaginatedLLMRuns {
  items: LLMRun[];
  total: number;
}

export interface PaginatedJobs {
  items: JobPosting[];
  total: number;
  limit: number;
  offset: number;
}

export type BackgroundTaskStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'retrying' | 'cancelled';

export interface BackgroundTask {
  id: string;
  kind: string;
  status: BackgroundTaskStatus;
  progress: number;
  result?: unknown;
  error?: { message?: string; exception_type?: string } | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface BackgroundTaskListResponse {
  items: BackgroundTask[];
  total: number;
}

export interface VersionResponse {
  worker_enabled: boolean;
  worker_fallback_to_sync: boolean;
}
