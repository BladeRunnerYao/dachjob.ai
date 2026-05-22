export interface JobPosting {
  id: string;
  title: string;
  company: string;
  location?: string;
  url?: string;
  status: string;
  score?: number;
  recommendation?: string;
  parsed_json?: Record<string, unknown>;
  created_at: string;
  raw_jd?: string;
}

export interface CandidateProfile {
  id: string;
  full_name: string;
  headline: string;
  location?: string;
  raw_cv_md: string;
  evidence_chunks?: EvidenceChunk[];
}

export interface EvidenceChunk {
  id: string;
  source_type: string;
  source_label: string;
  content: string;
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
  html_url: string;
  pdf_url?: string;
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
  model: string;
  status: string;
  latency_ms: number;
  created_at: string;
  error_message?: string;
}
