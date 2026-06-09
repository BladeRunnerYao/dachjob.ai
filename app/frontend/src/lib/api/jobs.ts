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
  if (options.added_date && addedDateForJob(job) !== options.added_date) return false;
  if (options.country && !countriesForJob(job).includes(options.country)) return false;
  if (options.stage && options.stage !== 'all') {
    return job.application_status === options.stage;
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
  if (queryOptions.added_date) q.set('added_date', queryOptions.added_date);
  if (queryOptions.country) q.set('country', queryOptions.country);
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
    const addedDateCounts = new Map<string, number>();
    const countryCounts = new Map<string, number>();
    let savedCount = 0;
    for (const job of jobs) {
      if (job.company) companyCounts.set(job.company, (companyCounts.get(job.company) || 0) + 1);
      const addedDate = addedDateForJob(job);
      if (addedDate) addedDateCounts.set(addedDate, (addedDateCounts.get(addedDate) || 0) + 1);
      for (const country of countriesForJob(job)) {
        countryCounts.set(country, (countryCounts.get(country) || 0) + 1);
      }
      if (job.saved) savedCount += 1;
      if (job.application_status) {
        statusCounts.set(job.application_status, (statusCounts.get(job.application_status) || 0) + 1);
      }
    }
    return {
      companies: [...companyCounts.entries()].map(([value, count]) => ({ value, count })),
      statuses: (['saved', 'applied', 'interview', 'rejected', 'offer'] as const).map((value) => ({
        value,
        count: value === 'saved' ? savedCount : statusCounts.get(value) || 0,
      })),
      added_dates: [...addedDateCounts.entries()]
        .sort(([left], [right]) => right.localeCompare(left))
        .map(([value, count]) => ({ value, count })),
      countries: [...countryCounts.entries()]
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([value, count]) => ({ value, count })),
    };
  }
}

function addedDateForJob(job: JobPosting): string {
  return (job.pipeline_added_at || job.created_at || '').slice(0, 10);
}

function countriesForJob(job: JobPosting): string[] {
  if (job.countries && job.countries.length > 0) return job.countries;
  const location = job.location || '';
  const pairs: Array<[string, RegExp]> = [
    ['Germany', /\b(germany|deutschland|berlin|hamburg|munich|münchen|frankfurt|stuttgart|leipzig)\b/i],
    ['Switzerland', /\b(switzerland|schweiz|zurich|zürich|basel|bern|geneva|lausanne|zug)\b/i],
    ['Austria', /\b(austria|österreich|vienna|wien)\b/i],
    ['United States', /\b(united states|usa|san francisco|new york|seattle|austin)\b|,\s*(ca|ny|tx|wa|ma)\b/i],
    ['Spain', /\b(spain|barcelona|madrid)\b/i],
  ];
  return pairs.filter(([, pattern]) => pattern.test(location)).map(([country]) => country);
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

export function deleteJob(jobId: string): Promise<{ message: string }> {
  return request<{ message: string }>(`/api/jobs/${jobId}`, {
    method: 'DELETE',
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
