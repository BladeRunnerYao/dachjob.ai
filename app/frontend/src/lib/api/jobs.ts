import { isBuildTime, isProduction, request } from './base-client';
import { checkTaskResult, isBackgroundTaskResponse, pollTask } from './tasks';
import { getMockJobs } from './mocks';
import type {
  BackgroundTask,
  JobFilterOptions,
  JobFilterStatus,
  JobImportResponse,
  JobQueryOptions,
  JobPosting,
  JobStatus,
  PaginatedJobs,
} from './types';

/** Filter out jobs whose title contains "smoke test" (case-insensitive). */
function filterSmokeTestJobs(jobs: JobPosting[]): JobPosting[] {
  return jobs.filter((j) => !/smoke\s*test/i.test(j.title ?? ''));
}

function matchesStatusFilter(job: JobPosting, status?: JobFilterStatus): boolean {
  if (!status) return true;
  if (status === 'saved') return Boolean(job.saved) || job.status === 'saved';
  if (status === 'applied') {
    return ['applied', 'interview', 'rejected', 'offer'].includes(
      job.application_status || job.status
    );
  }
  if (status === 'new') return !job.application_status && job.status !== 'applied';
  return (job.application_status || job.status) === status;
}

function matchesQueryFilters(job: JobPosting, options: JobQueryOptions = {}): boolean {
  if (!matchesStatusFilter(job, options.status)) return false;
  if (options.company && job.company !== options.company) return false;
  if (options.stage && options.stage !== 'all') {
    const stage = job.application_status || 'received';
    return stage === options.stage;
  }
  return true;
}

function buildJobsQuery(limit: number, offset: number, options: JobFilterStatus | JobQueryOptions = {}): string {
  const queryOptions: JobQueryOptions = typeof options === 'string' ? { status: options } : options;
  const q = new URLSearchParams();
  q.set('limit', String(limit));
  q.set('offset', String(offset));
  if (queryOptions.status) q.set('status', queryOptions.status);
  if (queryOptions.stage && queryOptions.stage !== 'all') q.set('stage', queryOptions.stage);
  if (queryOptions.company) q.set('company', queryOptions.company);
  return q.toString();
}

export async function getJobs(limit?: number, offset?: number, options?: JobFilterStatus | JobQueryOptions): Promise<JobPosting[]> {
  try {
    const query = buildJobsQuery(limit ?? 1000, offset ?? 0, options);
    const result = await request<PaginatedJobs>(`/api/jobs?${query}`);
    return filterSmokeTestJobs(result.items);
  } catch {
    if (isProduction() && !isBuildTime()) throw new Error('API unreachable');
    const jobs = filterSmokeTestJobs(getMockJobs());
    const queryOptions: JobQueryOptions = typeof options === 'string' ? { status: options } : (options || {});
    return jobs.filter((job) => matchesQueryFilters(job, queryOptions));
  }
}

export async function getJobsPaginated(limit: number, offset: number, options?: JobFilterStatus | JobQueryOptions): Promise<PaginatedJobs> {
  try {
    const query = buildJobsQuery(limit, offset, options);
    const result = await request<PaginatedJobs>(`/api/jobs?${query}`);
    const filtered = filterSmokeTestJobs(result.items);
    return { items: filtered, total: result.total - (result.items.length - filtered.length), limit, offset };
  } catch {
    if (isProduction() && !isBuildTime()) throw new Error('API unreachable');
    const allItems = filterSmokeTestJobs(getMockJobs());
    const queryOptions: JobQueryOptions = typeof options === 'string' ? { status: options } : (options || {});
    const items = allItems.filter((job) => matchesQueryFilters(job, queryOptions));
    return { items, total: items.length, limit, offset };
  }
}

export async function getJobFilters(): Promise<JobFilterOptions> {
  try {
    return await request<JobFilterOptions>('/api/jobs/filters');
  } catch {
    if (isProduction() && !isBuildTime()) throw new Error('API unreachable');
    const jobs = filterSmokeTestJobs(getMockJobs());
    const companyCounts = new Map<string, number>();
    const statusCounts = new Map<string, number>();
    for (const job of jobs) {
      if (job.company) companyCounts.set(job.company, (companyCounts.get(job.company) || 0) + 1);
      const status = job.application_status || 'received';
      statusCounts.set(status, (statusCounts.get(status) || 0) + 1);
    }
    return {
      companies: [...companyCounts.entries()].map(([value, count]) => ({ value, count })),
      statuses: (['received', 'applied', 'interview', 'rejected', 'offer'] as const).map((value) => ({
        value,
        count: statusCounts.get(value) || 0,
      })),
    };
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

export function updateJobStatus(
  jobId: string,
  status?: JobStatus,
  saved?: boolean
): Promise<JobPosting> {
  return request<JobPosting>(`/api/jobs/${jobId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status, saved }),
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
