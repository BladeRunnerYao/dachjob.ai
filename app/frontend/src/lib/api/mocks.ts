import type { Application, CandidateProfile, JobPosting, LLMRun, MatchReport, ResumeArtifact } from './types';

export function getMockJobs(): JobPosting[] {
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

export function getMockApplications(): Application[] {
  return [
    { id: 'a1', job_id: '4414035441', job_title: 'AI Engineer - FDE (Forward Deployed Engineer)', company: 'Databricks', status: 'saved', score: 4.1, notes: 'Strong GenAI and cloud ML overlap; review customer-facing travel expectations.', created_at: '2026-05-22T08:30:00Z' },
    { id: 'a2', job_id: '4414349687', job_title: 'Senior Software / ML Engineer (Python) (f/m/d)', company: 'Digitec Galaxus AG', status: 'applied', score: 4.4, notes: 'Best Python and applied ML fit among the current examples.', created_at: '2026-05-22T09:30:00Z' },
    { id: 'a3', job_id: '4417727434', job_title: 'Senior DevOps & Cloud Platform Engineer, CH', company: 'vector8', status: 'saved', score: 3.7, notes: 'Good cloud and platform match; less direct ML emphasis.', created_at: '2026-05-22T10:30:00Z' },
  ];
}

export function getMockLLMRuns(): LLMRun[] {
  return [
    { id: 'r1', task: 'match_resume', provider: 'vertex_ai', model: 'google/gemini-2.5-flash', status: 'completed', latency_ms: 3240, created_at: '2026-05-16T09:15:00Z' },
    { id: 'r2', task: 'parse_jd', provider: 'vertex_ai', model: 'google/gemini-2.5-flash-lite', status: 'completed', latency_ms: 890, created_at: '2026-05-16T09:10:00Z' },
    { id: 'r3', task: 'generate_cv', provider: 'gemini', model: 'gemini-2.5-pro', status: 'failed', latency_ms: 15200, created_at: '2026-05-15T14:30:00Z', error_message: 'Token limit exceeded. Consider reducing the input size.' },
    { id: 'r5', task: 'match_resume', provider: 'vertex_ai', model: 'google/gemini-2.5-flash', status: 'completed', latency_ms: 4100, created_at: '2026-05-14T16:45:00Z' },
    { id: 'r6', task: 'parse_jd', provider: 'deepseek', model: 'deepseek-v4-flash', status: 'completed', latency_ms: 750, created_at: '2026-05-14T10:20:00Z' },
  ];
}

export function getMockProfile(): CandidateProfile {
  return {
    id: 'p1',
    full_name: 'Yao Chen',
    headline: 'Senior Full-Stack Engineer & AI/ML Specialist',
    location: 'Munich, Germany',
    raw_cv_md: '# Yao Chen\n\n## Experience\n\n### Senior Software Engineer - Tech Corp (2020-Present)\n- Built scalable microservices handling 1M+ requests/day\n- Led ML platform migration to Kubernetes\n\n### ML Engineer - AI Labs (2018-2020)\n- Developed NLP pipelines for document processing\n- Achieved 95% accuracy on entity extraction\n\n## Skills\n- Python, TypeScript, Go\n- Kubernetes, Docker, Terraform\n- TensorFlow, PyTorch\n- AWS, GCP, Azure\n\n## Education\n- M.Sc. Computer Science, TU Munich',
  };
}

export function getMockMatchReport(jobId: string): MatchReport {
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

export function getMockResume(jobId: string): ResumeArtifact {
  return {
    id: `r-${jobId}`,
    job_id: jobId,
    has_html: false,
    has_pdf: false,
    provenance: [{ step: 'match', score: 4.2 }, { step: 'generate', model: 'gpt-4o' }],
  };
}
