import type { BackgroundTask, BackgroundTaskListResponse, JobPosting, CandidateProfile, Application, LLMRun, MatchReport, ResumeArtifact, JobImportResponse, PaginatedJobs, PaginatedLLMRuns, VersionResponse } from './types';

function getApiBase() {
  if (typeof window === 'undefined') {
    return process.env.INTERNAL_API_BASE_URL
      || process.env.NEXT_PUBLIC_API_BASE_URL
      || 'http://localhost:8000';
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
}

export class ApiClient {
  private RESUME_GENERATE_TIMEOUT_MS = 120_000;

  workerEnabled = false;

  private getAuthHeaders(): Record<string, string> {
    if (typeof window === 'undefined') return {};
    const token = localStorage.getItem('auth_token');
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  private async request<T>(path: string, options?: RequestInit & { timeoutMs?: number }): Promise<T> {
    const { timeoutMs, ...fetchOptions } = options || {};
    const url = `${getApiBase()}${path}`;
    const controller = timeoutMs ? new AbortController() : undefined;
    const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : undefined;

    try {
      const res = await fetch(url, {
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders(),
          ...fetchOptions.headers,
        } as Record<string, string>,
        cache: 'no-store',
        signal: controller?.signal,
        ...fetchOptions,
      });
      if (timer) clearTimeout(timer);
      if (res.status === 401 && typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
        window.location.href = '/login';
        throw new Error('Unauthorized');
      }

      const isBackgroundTask = res.status === 202;
      if (isBackgroundTask) {
        return res.json() as T;
      }

      if (!res.ok) {
        let message = `API error: ${res.status}`;
        try {
          const body = await res.json();
          if (body?.error?.message) {
            message = body.error.message;
          } else if (body?.detail) {
            message = body.detail;
          }
        } catch {
          try {
            const text = await res.text();
            if (text) message = text.slice(0, 512);
          } catch {}
        }
        throw new Error(message);
      }
      return res.json();
    } catch (e) {
      if (timer) clearTimeout(timer);
      if (e instanceof DOMException && e.name === 'AbortError') {
        throw new Error(`Request timed out after ${Math.round(timeoutMs! / 1000)}s`);
      }
      if (e instanceof Error) throw e;
      throw new Error('API unreachable');
    }
  }

  async initWorkerMode(): Promise<void> {
    try {
      const version = await this.fetch<VersionResponse>('/api/version');
      this.workerEnabled = version.worker_enabled;
    } catch {
      this.workerEnabled = false;
    }
  }

  private isBackgroundTaskResponse(data: unknown): data is BackgroundTask {
    return (
      typeof data === 'object' &&
      data !== null &&
      'kind' in data &&
      'status' in data &&
      'id' in data
    );
  }

  private checkTaskResult(task: BackgroundTask): void {
    if (task.status === 'failed') {
      const msg = task.error && typeof task.error === 'object'
        ? (task.error as Record<string, unknown>).message || 'Task failed'
        : 'Task failed';
      throw new Error(String(msg));
    }
    if (task.status === 'cancelled') {
      throw new Error('Task was cancelled');
    }
  }

  async pollTask(taskId: string, onUpdate?: (task: BackgroundTask) => void): Promise<BackgroundTask> {
    const terminal = new Set(['succeeded', 'failed', 'cancelled']);
    while (true) {
      const task = await this.fetch<BackgroundTask>(`/api/tasks/${taskId}`);
      if (onUpdate) onUpdate(task);
      if (terminal.has(task.status)) return task;
      await new Promise((r) => setTimeout(r, 2000));
    }
  }

  async getTask(taskId: string): Promise<BackgroundTask> {
    return this.fetch<BackgroundTask>(`/api/tasks/${taskId}`);
  }

  async listTasks(params?: { status?: string; kind?: string; limit?: number; offset?: number }): Promise<BackgroundTaskListResponse> {
    const q = new URLSearchParams();
    if (params?.status) q.set('status', params.status);
    if (params?.kind) q.set('kind', params.kind);
    if (params?.limit) q.set('limit', String(params.limit));
    if (params?.offset) q.set('offset', String(params.offset));
    const query = q.toString();
    return this.fetch<BackgroundTaskListResponse>(`/api/tasks${query ? '?' + query : ''}`);
  }

  async requestBlob(path: string): Promise<Blob> {
    const url = `${getApiBase()}${path}`;
    const res = await fetch(url, {
      headers: { ...this.getAuthHeaders() } as Record<string, string>,
    });
    if (res.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }
    if (!res.ok) {
      throw new Error(`Failed to fetch: ${res.status}`);
    }
    return res.blob();
  }

  async getResumeHtmlUrl(artifactId: string): Promise<string> {
    const blob = await this.requestBlob(`/api/resumes/${artifactId}/html`);
    return URL.createObjectURL(blob);
  }

  async getResumePdfUrl(artifactId: string): Promise<string> {
    const blob = await this.requestBlob(`/api/resumes/${artifactId}/pdf`);
    return URL.createObjectURL(blob);
  }

  async fetch<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: 'POST', body: JSON.stringify(body) });
  }

  async createResumeArtifact(jobId: string): Promise<ResumeArtifact> {
    const result = await this.request<ResumeArtifact | BackgroundTask>(`/api/jobs/${jobId}/resume`, {
      method: 'POST',
      body: JSON.stringify({}),
      timeoutMs: this.workerEnabled ? undefined : this.RESUME_GENERATE_TIMEOUT_MS,
    });
    if (this.isBackgroundTaskResponse(result)) {
      const task = await this.pollTask(result.id);
      this.checkTaskResult(task);
      const latest = await this.getLatestResumeArtifact(jobId);
      if (!latest) throw new Error('Resume generation completed but no artifact found');
      return latest;
    }
    return this.toResumeArtifact(result as ResumeArtifact & { html_object_key: string; pdf_object_key?: string | null; provenance_json?: unknown[] });
  }

  async patch<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
  }

  async getJobs(limit?: number, offset?: number): Promise<JobPosting[]> {
    try {
      const q = new URLSearchParams();
      q.set('limit', String(limit ?? 1000));
      q.set('offset', String(offset ?? 0));
      const result = await this.fetch<PaginatedJobs>(`/api/jobs?${q.toString()}`);
      return result.items;
    } catch {
      return this.getMockJobs();
    }
  }

  async getJobsPaginated(limit: number, offset: number): Promise<PaginatedJobs> {
    try {
      const q = new URLSearchParams();
      q.set('limit', String(limit));
      q.set('offset', String(offset));
      return await this.fetch<PaginatedJobs>(`/api/jobs?${q.toString()}`);
    } catch {
      const items = this.getMockJobs();
      return { items, total: items.length, limit, offset };
    }
  }

  async getJob(id: string): Promise<JobPosting> {
    try {
      return await this.fetch<JobPosting>(`/api/jobs/${id}`);
    } catch {
      const jobs = await this.getJobs();
      const job = jobs.find(j => j.id === id);
      if (!job) throw new Error('Job not found');
      return job;
    }
  }

  async createJob(rawJd: string): Promise<JobPosting> {
    const titleMatch = rawJd.match(/^#+\s*([^—\n-]+)(?:[—-]\s*([^\n]+))?/m);
    return this.post<JobPosting>('/api/jobs', {
      title: titleMatch?.[1]?.trim() || 'New Job',
      company: titleMatch?.[2]?.trim() || 'Unknown',
      raw_jd: rawJd,
    });
  }

  async importJobs(urlText: string): Promise<JobImportResponse> {
    const urls = Array.from(new Set(
      urlText
        .split(/[\s,]+/)
        .map((url) => url.trim())
        .filter((url) => /^https?:\/\//i.test(url))
    ));
    if (urls.length === 0) {
      throw new Error('No valid job URLs found');
    }
    const result = await this.post<JobImportResponse | BackgroundTask>('/api/jobs/import', { urls });
    if (this.isBackgroundTaskResponse(result)) {
      const task = await this.pollTask(result.id);
      this.checkTaskResult(task);
      const jobs = await this.getJobs();
      const taskResult = task.result as { imported_job_ids?: string[]; errors?: Array<{url: string; error: string}> } | undefined;
      return {
        imported: jobs,
        errors: taskResult?.errors || [],
      };
    }
    return result;
  }

  async getApplications(): Promise<Application[]> {
    try {
      return await this.fetch<Application[]>('/api/applications');
    } catch {
      return this.getMockApplications();
    }
  }

  async getProfile(): Promise<CandidateProfile> {
    try {
      const profile = await this.fetch<CandidateProfile>('/api/profile');
      return { ...profile, evidence_chunks: profile.evidence_chunks || [] };
    } catch {
      return this.getMockProfile();
    }
  }

  async uploadCv(rawCvMd: string): Promise<CandidateProfile> {
    const profile = await this.post<CandidateProfile>('/api/profile/cv', { raw_cv_md: rawCvMd });
    return { ...profile, evidence_chunks: profile.evidence_chunks || [] };
  }

  async importProfileFromUrl(url: string): Promise<CandidateProfile> {
    const profile = await this.post<CandidateProfile>('/api/profile/import-url', { url });
    return { ...profile, evidence_chunks: profile.evidence_chunks || [] };
  }

  async importProfileFromPdf(file: File): Promise<CandidateProfile> {
    const formData = new FormData();
    formData.append('file', file);
    const baseUrl = getApiBase();
    const headers = this.getAuthHeaders();
    const res = await fetch(`${baseUrl}/api/profile/import-pdf`, {
      method: 'POST',
      headers: { ...headers } as Record<string, string>,
      body: formData,
    });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    const profile = await res.json();
    return { ...profile, evidence_chunks: profile.evidence_chunks || [] };
  }

  private toMatchReport(report: {
    id: string;
    job_id: string;
    overall_score: number;
    recommendation: string;
    breakdown_json: Record<string, number>;
    gaps_json?: { gaps?: string[] } | null;
    explanation?: string | null;
  }): MatchReport {
    return {
      id: report.id,
      job_id: report.job_id,
      overall_score: Number(report.overall_score),
      recommendation: report.recommendation,
      breakdown: report.breakdown_json || {},
      top_reasons: report.explanation ? [report.explanation] : [],
      gaps: report.gaps_json?.gaps || [],
      explanation: report.explanation || undefined,
    };
  }

  async getLatestMatchReport(jobId: string): Promise<MatchReport | null> {
    try {
      const report = await this.fetch<{
        id: string;
        job_id: string;
        overall_score: number;
        recommendation: string;
        breakdown_json: Record<string, number>;
        gaps_json?: { gaps?: string[] } | null;
        explanation?: string | null;
      } | null>(`/api/jobs/${jobId}/match`);
      return report ? this.toMatchReport(report) : null;
    } catch {
      return null;
    }
  }

  async createMatchReport(jobId: string): Promise<MatchReport> {
    const result = await this.post<MatchReport | BackgroundTask>(`/api/jobs/${jobId}/match`, {});
    if (this.isBackgroundTaskResponse(result)) {
      const task = await this.pollTask(result.id);
      this.checkTaskResult(task);
      const latest = await this.getLatestMatchReport(jobId);
      if (!latest) throw new Error('Match completed but no report found');
      return latest;
    }
    return this.toMatchReport(result as MatchReport & { breakdown_json: Record<string, number>; gaps_json?: { gaps?: string[] } | null });
  }

  async getMatchReport(jobId: string): Promise<MatchReport> {
    const cached = await this.getLatestMatchReport(jobId);
    return cached || this.getMockMatchReport(jobId);
  }

  private toResumeArtifact(artifact: {
    id: string;
    job_id: string;
    html_object_key: string;
    pdf_object_key?: string | null;
    provenance_json?: unknown[];
  }): ResumeArtifact {
    return {
      id: artifact.id,
      job_id: artifact.job_id,
      has_html: !!artifact.html_object_key,
      has_pdf: !!artifact.pdf_object_key,
      provenance: artifact.provenance_json || [],
    };
  }

  async getLatestResumeArtifact(jobId: string): Promise<ResumeArtifact | null> {
    try {
      const artifact = await this.fetch<{
        id: string;
        job_id: string;
        html_object_key: string;
        pdf_object_key?: string | null;
        provenance_json?: unknown[];
      } | null>(`/api/jobs/${jobId}/resume`);
      return artifact ? this.toResumeArtifact(artifact) : null;
    } catch {
      return null;
    }
  }

  async getResumeArtifact(jobId: string): Promise<ResumeArtifact> {
    const cached = await this.getLatestResumeArtifact(jobId);
    return cached || this.getMockResume(jobId);
  }

  async getLLMRuns(params?: { task?: string; status?: string; limit?: number; offset?: number }): Promise<PaginatedLLMRuns> {
    try {
      const q = new URLSearchParams();
      if (params?.task) q.set('task', params.task);
      if (params?.status) q.set('status', params.status);
      if (params?.limit) q.set('limit', String(params.limit));
      if (params?.offset) q.set('offset', String(params.offset));
      const query = q.toString();
      return await this.fetch<PaginatedLLMRuns>(`/api/llm-runs${query ? '?' + query : ''}`);
    } catch {
      const items = this.getMockLLMRuns();
      return { items, total: items.length };
    }
  }

  getMockJobs(): JobPosting[] {
    return [
      {
        id: '4414035441',
        title: 'AI Engineer - FDE (Forward Deployed Engineer)',
        company: 'Databricks',
        location: 'Munich, Bavaria, Germany',
        url: 'https://www.linkedin.com/jobs/view/4414035441/',
        status: 'new',
        parsed_json: {
          skills: ['GenAI', 'RAG', 'LLMOps', 'PyTorch', 'AWS/Azure/GCP', 'Databricks', 'Spark'],
          years_exp: 5,
        },
        created_at: '2026-05-22T08:00:00Z',
        raw_jd: 'Customer-facing AI FDE role at Databricks focused on building and productionizing GenAI applications. Requirements include RAG, multi-agent systems, Text2SQL, fine-tuning, Hugging Face, LangChain, DSPy, PyTorch, cloud ML deployments, and strong technical communication.',
      },
      {
        id: '4414349687',
        title: 'Senior Software / ML Engineer (Python) (f/m/d)',
        company: 'Digitec Galaxus AG',
        location: 'Zurich, Switzerland',
        url: 'https://www.linkedin.com/jobs/view/4414349687/',
        status: 'new',
        parsed_json: {
          skills: ['Python', 'LLM/VLM', 'Evaluation', 'SQL', 'BigQuery', 'Airflow', 'Kafka', 'Kubernetes'],
          years_exp: 4,
        },
        created_at: '2026-05-22T09:00:00Z',
        raw_jd: 'Software/ML Engineering role for Digitec Galaxus focused on order management and finance systems. The role centers on Python ownership, PDF document interpretation with Vision Language Models, evaluation pipelines, SQL, orchestration, streaming, and DevOps practices.',
      },
      {
        id: '4417727434',
        title: 'Senior DevOps & Cloud Platform Engineer, CH',
        company: 'vector8',
        location: 'Zurich, Zurich, Switzerland',
        url: 'https://www.linkedin.com/jobs/view/4417727434/',
        status: 'new',
        parsed_json: {
          skills: ['Azure', 'AWS', 'Kubernetes', 'Docker', 'Terraform', 'GitHub Actions', 'Python', 'Bash'],
          years_exp: 5,
        },
        created_at: '2026-05-22T10:00:00Z',
        raw_jd: 'Senior cloud platform role at vector8 for Swiss AI transformation work. Requirements include Azure or AWS, Kubernetes, Docker, CI/CD automation with GitHub Actions, microservices, infrastructure as code, Python or Bash scripting, and client-facing collaboration.',
      },
    ];
  }

  getMockApplications(): Application[] {
    return [
      { id: 'a1', job_id: '4414035441', job_title: 'AI Engineer - FDE (Forward Deployed Engineer)', company: 'Databricks', status: 'saved', score: 4.1, notes: 'Strong GenAI and cloud ML overlap; review customer-facing travel expectations.', created_at: '2026-05-22T08:30:00Z' },
      { id: 'a2', job_id: '4414349687', job_title: 'Senior Software / ML Engineer (Python) (f/m/d)', company: 'Digitec Galaxus AG', status: 'applied', score: 4.4, notes: 'Best Python and applied ML fit among the current examples.', created_at: '2026-05-22T09:30:00Z' },
      { id: 'a3', job_id: '4417727434', job_title: 'Senior DevOps & Cloud Platform Engineer, CH', company: 'vector8', status: 'saved', score: 3.7, notes: 'Good cloud and platform match; less direct ML emphasis.', created_at: '2026-05-22T10:30:00Z' },
    ];
  }

  getMockLLMRuns(): LLMRun[] {
    return [
      { id: 'r1', task: 'match_resume', provider: 'vertex_ai', model: 'google/gemini-2.5-flash', status: 'completed', latency_ms: 3240, created_at: '2026-05-16T09:15:00Z' },
      { id: 'r2', task: 'parse_jd', provider: 'vertex_ai', model: 'google/gemini-2.5-flash-lite', status: 'completed', latency_ms: 890, created_at: '2026-05-16T09:10:00Z' },
      { id: 'r3', task: 'generate_cv', provider: 'gemini', model: 'gemini-2.5-pro', status: 'failed', latency_ms: 15200, created_at: '2026-05-15T14:30:00Z', error_message: 'Token limit exceeded. Consider reducing the input size.' },
      { id: 'r4', task: 'extract_evidence', provider: 'vertex_ai', model: 'google/gemini-2.5-flash-lite', status: 'completed', latency_ms: 2100, created_at: '2026-05-15T12:00:00Z' },
      { id: 'r5', task: 'match_resume', provider: 'vertex_ai', model: 'google/gemini-2.5-flash', status: 'completed', latency_ms: 4100, created_at: '2026-05-14T16:45:00Z' },
      { id: 'r6', task: 'parse_jd', provider: 'deepseek', model: 'deepseek-v4-flash', status: 'completed', latency_ms: 750, created_at: '2026-05-14T10:20:00Z' },
    ];
  }

  getMockProfile(): CandidateProfile {
    return {
      id: 'p1',
      full_name: 'Yao Chen',
      headline: 'Senior Full-Stack Engineer & AI/ML Specialist',
      location: 'Munich, Germany',
      raw_cv_md: '# Yao Chen\n\n## Experience\n\n### Senior Software Engineer - Tech Corp (2020-Present)\n- Built scalable microservices handling 1M+ requests/day\n- Led ML platform migration to Kubernetes\n\n### ML Engineer - AI Labs (2018-2020)\n- Developed NLP pipelines for document processing\n- Achieved 95% accuracy on entity extraction\n\n## Skills\n- Python, TypeScript, Go\n- Kubernetes, Docker, Terraform\n- TensorFlow, PyTorch\n- AWS, GCP, Azure\n\n## Education\n- M.Sc. Computer Science, TU Munich',
      evidence_chunks: [
        { id: 'e1', source_type: 'experience', source_label: 'Tech Corp - Senior Software Engineer', content: 'Built scalable microservices handling 1M+ requests/day' },
        { id: 'e2', source_type: 'experience', source_label: 'Tech Corp - Senior Software Engineer', content: 'Led ML platform migration to Kubernetes' },
        { id: 'e3', source_type: 'experience', source_label: 'AI Labs - ML Engineer', content: 'Developed NLP pipelines for document processing' },
        { id: 'e4', source_type: 'experience', source_label: 'AI Labs - ML Engineer', content: 'Achieved 95% accuracy on entity extraction' },
        { id: 'e5', source_type: 'skill', source_label: 'Technical Skills', content: 'Python, TypeScript, Go, Kubernetes, Docker, Terraform, TensorFlow, PyTorch, AWS, GCP, Azure' },
        { id: 'e6', source_type: 'education', source_label: 'TU Munich', content: 'M.Sc. Computer Science, TU Munich' },
      ],
    };
  }

  getMockMatchReport(jobId: string): MatchReport {
    return {
      id: `m-${jobId}`,
      job_id: jobId,
      overall_score: 4.2,
      recommendation: 'apply',
      breakdown: { skills_match: 4.5, experience: 4.0, education: 4.0, location: 5.0, seniority: 3.5 },
      top_reasons: ['Strong Python and ML experience', 'Relevant Kubernetes expertise', 'Good location match'],
      gaps: ['No industry-specific domain knowledge', 'Limited experience with CI/CD pipelines'],
    };
  }

  getMockResume(jobId: string): ResumeArtifact {
    return {
      id: `r-${jobId}`,
      job_id: jobId,
      has_html: false,
      has_pdf: false,
      provenance: [{ step: 'match', score: 4.2 }, { step: 'generate', model: 'gpt-4o' }],
    };
  }
}

export const api = new ApiClient();
