import { isBuildTime, isProduction, request } from './base-client';
import { checkTaskResult, isBackgroundTaskResponse, pollTask } from './tasks';
import { getMockJobs } from './mocks';
import type { BackgroundTask, JobImportResponse, JobPosting, PaginatedJobs } from './types';

/** Filter out jobs whose title contains "smoke test" (case-insensitive). */
function filterSmokeTestJobs(jobs: JobPosting[]): JobPosting[] {
  return jobs.filter((j) => !/smoke\s*test/i.test(j.title ?? ''));
}

export async function getJobs(limit?: number, offset?: number): Promise<JobPosting[]> {
  try {
    const q = new URLSearchParams();
    q.set('limit', String(limit ?? 1000));
    q.set('offset', String(offset ?? 0));
    const result = await request<PaginatedJobs>(`/api/jobs?${q.toString()}`);
    return filterSmokeTestJobs(result.items);
  } catch {
    if (isProduction() && !isBuildTime()) throw new Error('API unreachable');
    return filterSmokeTestJobs(getMockJobs());
  }
}

export async function getJobsPaginated(limit: number, offset: number): Promise<PaginatedJobs> {
  try {
    const q = new URLSearchParams();
    q.set('limit', String(limit));
    q.set('offset', String(offset));
    const result = await request<PaginatedJobs>(`/api/jobs?${q.toString()}`);
    const filtered = filterSmokeTestJobs(result.items);
    return { items: filtered, total: result.total - (result.items.length - filtered.length), limit, offset };
  } catch {
    if (isProduction() && !isBuildTime()) throw new Error('API unreachable');
    const items = filterSmokeTestJobs(getMockJobs());
    return { items, total: items.length, limit, offset };
  }
}

export async function getJob(id: string): Promise<JobPosting> {
  try {
    return await request<JobPosting>(`/api/jobs/${id}`);
  } catch {
    if (isProduction() && !isBuildTime()) throw new Error('API unreachable');
    const jobs = await getJobs();
    const job = jobs.find((item) => item.id === id);
    if (!job) throw new Error('Job not found');
    return job;
  }
}

export function createJob(rawJd: string): Promise<JobPosting> {
  const titleMatch = rawJd.match(/^#+\s*([^—\n-]+)(?:[—-]\s*([^\n]+))?/m);
  return request<JobPosting>('/api/jobs', {
    method: 'POST',
    body: JSON.stringify({
      title: titleMatch?.[1]?.trim() || 'New Job',
      company: titleMatch?.[2]?.trim() || 'Unknown',
      raw_jd: rawJd,
    }),
  });
}

export async function parseJob(jobId: string): Promise<JobPosting> {
  const result = await request<{ job_id: string; status: string; parsed_json?: Record<string, unknown> } | BackgroundTask>(`/api/jobs/${jobId}/parse`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
  if (isBackgroundTaskResponse(result)) {
    const task = await pollTask(result.id);
    checkTaskResult(task);
  }
  return getJob(jobId);
}

export async function importJobs(urlText: string): Promise<JobImportResponse> {
  const urls = Array.from(new Set(
    urlText
      .split(/[\s,]+/)
      .map((url) => url.trim())
      .filter((url) => /^https?:\/\//i.test(url))
  ));
  if (urls.length === 0) {
    throw new Error('No valid job URLs found');
  }
  const result = await request<JobImportResponse | BackgroundTask>('/api/jobs/import', {
    method: 'POST',
    body: JSON.stringify({ urls }),
  });
  if (isBackgroundTaskResponse(result)) {
    const task = await pollTask(result.id);
    checkTaskResult(task);
    const jobs = await getJobs();
    const taskResult = task.result as { imported_job_ids?: string[]; errors?: Array<{ url: string; error: string }> } | undefined;
    return {
      imported: jobs,
      errors: taskResult?.errors || [],
    };
  }
  return result;
}
