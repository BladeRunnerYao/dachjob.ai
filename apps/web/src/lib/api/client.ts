import type { JobPosting, CandidateProfile, Application, LLMRun, MatchReport, ResumeArtifact } from './types';

function getApiBase() {
  if (typeof window === 'undefined') {
    return process.env.INTERNAL_API_BASE_URL
      || process.env.NEXT_PUBLIC_API_BASE_URL
      || 'http://localhost:8000';
  }
  return process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
}

function getPublicApiBase() {
  return process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
}

export class ApiClient {
  private async request<T>(path: string, options?: RequestInit): Promise<T> {
    const url = `${getApiBase()}${path}`;
    try {
      const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json', ...options?.headers },
        cache: 'no-store',
        ...options,
      });
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json();
    } catch {
      throw new Error('API unreachable');
    }
  }

  async fetch<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: 'POST', body: JSON.stringify(body) });
  }

  async patch<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
  }

  async getJobs(): Promise<JobPosting[]> {
    try {
      return await this.fetch<JobPosting[]>('/api/jobs');
    } catch {
      return this.getMockJobs();
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

  async getMatchReport(jobId: string): Promise<MatchReport> {
    try {
      await this.post(`/api/jobs/${jobId}/parse`, {});
      const report = await this.post<{
        id: string;
        job_id: string;
        overall_score: number;
        recommendation: string;
        breakdown_json: Record<string, number>;
        gaps_json?: { gaps?: string[] } | null;
        explanation?: string | null;
      }>(`/api/jobs/${jobId}/match`, {});
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
    } catch {
      return this.getMockMatchReport(jobId);
    }
  }

  async getResumeArtifact(jobId: string): Promise<ResumeArtifact> {
    try {
      const artifact = await this.post<{
        id: string;
        job_id: string;
        html_object_key: string;
        pdf_object_key?: string | null;
        provenance_json?: unknown[];
      }>(`/api/jobs/${jobId}/resume`, {});
      return {
        id: artifact.id,
        job_id: artifact.job_id,
        html_url: `${getPublicApiBase()}/api/resumes/${artifact.id}/html`,
        pdf_url: artifact.pdf_object_key || undefined,
        provenance: artifact.provenance_json || [],
      };
    } catch {
      return this.getMockResume(jobId);
    }
  }

  async getLLMRuns(): Promise<LLMRun[]> {
    try {
      return await this.fetch<LLMRun[]>('/api/llm-runs');
    } catch {
      return this.getMockLLMRuns();
    }
  }

  getMockJobs(): JobPosting[] {
    return [
      { id: '1', title: 'AI Platform Engineer', company: 'Siemens', location: 'Munich, Germany', url: 'https://siemens.com/careers/1', status: 'active', score: 4.5, recommendation: 'apply', parsed_json: { skills: ['Python', 'Kubernetes', 'MLOps', 'TensorFlow', 'Docker'], responsibilities: ['Build ML platform', 'Deploy models', 'Monitor pipelines'], years_exp: 4 }, created_at: '2026-05-15T08:00:00Z', raw_jd: 'Siemens is looking for an AI Platform Engineer to join our Munich office.\n\nRequirements:\n- 4+ years experience in ML engineering\n- Strong Python skills\n- Experience with Kubernetes and Docker\n- TensorFlow/PyTorch expertise\n- MLOps experience\n\nResponsibilities:\n- Design and build ML platform infrastructure\n- Deploy and monitor ML models in production\n- Collaborate with data scientists\n- Optimize training pipelines' },
      { id: '2', title: 'MLOps Engineer', company: 'SAP', location: 'Walldorf, Germany', url: 'https://sap.com/careers/2', status: 'active', score: 4.2, recommendation: 'apply', parsed_json: { skills: ['MLOps', 'Kubernetes', 'Python', 'CI/CD', 'Azure'], responsibilities: ['Manage ML pipelines', 'Automate deployments', 'Monitor model performance'], years_exp: 3 }, created_at: '2026-05-14T10:00:00Z', raw_jd: 'SAP seeks an MLOps Engineer for our Walldorf headquarters.\n\nRequirements:\n- 3+ years in MLOps or DevOps\n- Kubernetes and Docker proficiency\n- Python development experience\n- CI/CD pipeline management\n- Azure cloud experience\n\nResponsibilities:\n- Manage end-to-end ML pipelines\n- Automate model deployment and monitoring\n- Ensure system reliability and scalability' },
      { id: '3', title: 'Cloud Engineer', company: 'Deutsche Telekom', location: 'Bonn, Germany', url: 'https://telekom.com/careers/3', status: 'active', score: 3.8, recommendation: 'maybe', parsed_json: { skills: ['AWS', 'Terraform', 'Linux', 'Networking', 'CI/CD'], responsibilities: ['Design cloud architecture', 'Automate infrastructure', 'Manage deployments'], years_exp: 5 }, created_at: '2026-05-13T09:00:00Z', raw_jd: 'Deutsche Telekom is hiring a Cloud Engineer in Bonn.\n\nRequirements:\n- 5+ years cloud engineering experience\n- AWS certification preferred\n- Terraform and Infrastructure as Code\n- Linux system administration\n- Networking fundamentals\n\nResponsibilities:\n- Design and implement cloud architecture\n- Automate infrastructure provisioning\n- Manage production deployments' },
      { id: '4', title: 'Data Engineer', company: 'Bosch', location: 'Stuttgart, Germany', url: 'https://bosch.com/careers/4', status: 'active', score: 3.5, recommendation: 'maybe', parsed_json: { skills: ['Python', 'SQL', 'Spark', 'Airflow', 'Kafka'], responsibilities: ['Build data pipelines', 'Maintain data warehouse', 'Optimize ETL processes'], years_exp: 3 }, created_at: '2026-05-12T11:00:00Z', raw_jd: 'Bosch is looking for a Data Engineer in Stuttgart.\n\nRequirements:\n- 3+ years data engineering experience\n- Python and SQL proficiency\n- Apache Spark experience\n- Airflow or similar orchestrator\n- Kafka experience preferred\n\nResponsibilities:\n- Build and maintain data pipelines\n- Optimize ETL processes\n- Ensure data quality and governance' },
      { id: '5', title: 'AI Engineer', company: 'Allianz', location: 'Munich, Germany', url: 'https://allianz.com/careers/5', status: 'active', score: 3.2, recommendation: 'skip', parsed_json: { skills: ['Python', 'NLP', 'Transformers', 'AWS', 'Docker'], responsibilities: ['Develop NLP models', 'Deploy AI services', 'Research new approaches'], years_exp: 2 }, created_at: '2026-05-11T14:00:00Z', raw_jd: 'Allianz seeks an AI Engineer in Munich.\n\nRequirements:\n- 2+ years AI/ML engineering\n- NLP and transformer models\n- Python expertise\n- AWS experience\n- Docker knowledge\n\nResponsibilities:\n- Develop and deploy NLP models\n- Research and implement new AI approaches\n- Collaborate with product teams' },
      { id: '6', title: 'Platform Engineer', company: 'Zalando', location: 'Berlin, Germany', url: 'https://zalando.com/careers/6', status: 'active', score: 2.8, recommendation: 'skip', parsed_json: { skills: ['Go', 'Kubernetes', 'Microservices', 'gRPC', 'PostgreSQL'], responsibilities: ['Build internal platform', 'Design microservices', 'Improve developer experience'], years_exp: 5 }, created_at: '2026-05-10T07:00:00Z', raw_jd: 'Zalando is looking for a Platform Engineer in Berlin.\n\nRequirements:\n- 5+ years software engineering\n- Go programming experience\n- Kubernetes and microservices\n- gRPC and API design\n- PostgreSQL expertise\n\nResponsibilities:\n- Build internal developer platform\n- Design and implement microservices\n- Improve developer experience and productivity' },
    ];
  }

  getMockApplications(): Application[] {
    return [
      { id: 'a1', job_id: '1', job_title: 'AI Platform Engineer', company: 'Siemens', status: 'applied', score: 4.5, notes: 'Application submitted via LinkedIn', created_at: '2026-05-16T09:00:00Z' },
      { id: 'a2', job_id: '2', job_title: 'MLOps Engineer', company: 'SAP', status: 'interview', score: 4.2, notes: 'First round interview scheduled', created_at: '2026-05-15T10:00:00Z' },
      { id: 'a3', job_id: '3', job_title: 'Cloud Engineer', company: 'Deutsche Telekom', status: 'saved', score: 3.8, notes: '', created_at: '2026-05-14T11:00:00Z' },
      { id: 'a4', job_id: '4', job_title: 'Data Engineer', company: 'Bosch', status: 'applied', score: 3.5, notes: 'Waiting for response', created_at: '2026-05-13T08:00:00Z' },
    ];
  }

  getMockLLMRuns(): LLMRun[] {
    return [
      { id: 'r1', task: 'match_resume', model: 'gpt-4o', status: 'completed', latency_ms: 3240, created_at: '2026-05-16T09:15:00Z' },
      { id: 'r2', task: 'parse_jd', model: 'gpt-4o-mini', status: 'completed', latency_ms: 890, created_at: '2026-05-16T09:10:00Z' },
      { id: 'r3', task: 'generate_cv', model: 'gpt-4o', status: 'failed', latency_ms: 15200, created_at: '2026-05-15T14:30:00Z', error_message: 'Token limit exceeded. Consider reducing the input size.' },
      { id: 'r4', task: 'extract_evidence', model: 'gpt-4o-mini', status: 'completed', latency_ms: 2100, created_at: '2026-05-15T12:00:00Z' },
      { id: 'r5', task: 'match_resume', model: 'gpt-4o', status: 'completed', latency_ms: 4100, created_at: '2026-05-14T16:45:00Z' },
      { id: 'r6', task: 'parse_jd', model: 'gpt-4o-mini', status: 'completed', latency_ms: 750, created_at: '2026-05-14T10:20:00Z' },
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
      html_url: '#',
      pdf_url: '#',
      provenance: [{ step: 'match', score: 4.2 }, { step: 'generate', model: 'gpt-4o' }],
    };
  }
}

export const api = new ApiClient();
