import { Hono, type Context } from "hono";
import { Env } from "../types";
import { authMiddleware } from "../middleware/auth";
import { generateId } from "../db/utils";
import { AppError } from "../middleware/error-handler";
import { callDeepSeekChat, logLLMRun } from "../llm";
import { generateAndStoreResume } from "../resume-generator";
import {
  JOB_COUNTRIES,
  countriesForLocation,
  inferCountriesFromLocation,
  parseSerializedCountries,
  serializeCountries,
} from "./location-country";

export const jobsRoutes = new Hono<{ Bindings: Env }>();

const APPLICATION_JOB_STATUSES = ["applied", "interview", "rejected", "offer"];
const PROFILE_MISMATCH_ERROR_PREFIX = "PROFILE_MISMATCH:";

interface ApplicationMatchRow {
  id: string;
  job_id: string;
  match_score: number | null;
  match_result: string | null;
  created_at: string;
  updated_at: string;
}

interface ProfileRow {
  id: string;
  name: string;
  raw_cv_md: string;
  profile_json: string | null;
}

interface JobImportItem {
  url: string;
  added_at?: string;
  status?: string | null;
  source_sha?: string;
  title?: string;
  company?: string;
  location?: string;
  countries?: string[];
  prepare?: boolean;
}

interface JobImportBody {
  urls?: string[];
  jobs?: JobImportItem[];
}

interface ParsedJobImportItem {
  url: string;
  job_key?: string;
  title: string;
  company?: string;
  location?: string;
  countries?: string[];
  raw_description: string;
  parsed_json: Record<string, unknown>;
  employment_type?: string;
  workplace?: string;
  salary_text?: string;
  pipeline_added_at?: string;
  pipeline_source_sha?: string;
  status?: string | null;
}

interface ParsedJobImportBody {
  jobs?: ParsedJobImportItem[];
}

// POST /api/jobs/import - Import jobs from URLs
jobsRoutes.post("/import", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const body = await c.req.json<JobImportBody>();
  const items = normalizeImportItems(body);
  if (items.length === 0) {
    throw new AppError("VALIDATION_ERROR", "Provide at least one job URL", 400);
  }
  if (items.length > 10) {
    throw new AppError("VALIDATION_ERROR", "Import at most 10 job URLs at a time", 400);
  }

  const imported: Record<string, unknown>[] = [];
  const cacheHits: Record<string, unknown>[] = [];
  const errors: { url: string; error: string }[] = [];

  for (const item of items) {
    try {
      const result = await importSingleJobUrl(c.env, userId, item);
      if (result.cacheHit) {
        cacheHits.push(result.job);
      } else {
        imported.push(result.job);
      }
    } catch (err) {
      errors.push({ url: item.url, error: (err as Error).message });
    }
  }

  return c.json({ imported, cache_hits: cacheHits, errors }, 201);
});

// POST /api/jobs/import-parsed - Import already parsed jobs without invoking LLM parsing.
jobsRoutes.post("/import-parsed", async (c) => {
  const userId = await importParsedUserId(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const body = await c.req.json<ParsedJobImportBody>();
  const items = normalizeParsedImportItems(body);
  if (items.length === 0) {
    throw new AppError("VALIDATION_ERROR", "Provide at least one parsed job", 400);
  }
  if (items.length > 10) {
    throw new AppError("VALIDATION_ERROR", "Import at most 10 parsed jobs at a time", 400);
  }

  const imported: Record<string, unknown>[] = [];
  const cacheHits: Record<string, unknown>[] = [];
  const errors: { url: string; error: string }[] = [];

  for (const item of items) {
    try {
      const result = await importSingleParsedJob(c.env, userId, item);
      if (result.cacheHit) {
        cacheHits.push(result.job);
      } else {
        imported.push(result.job);
      }
    } catch (err) {
      errors.push({ url: item.url, error: (err as Error).message });
    }
  }

  return c.json({ imported, cache_hits: cacheHits, errors }, 201);
});

// POST /api/jobs - Create a job
jobsRoutes.post("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const body = await c.req.json<{
    title: string;
    company?: string;
    location?: string;
    url?: string;
    raw_jd?: string;
    source?: string;
    employment_type?: string;
    workplace?: string;
    salary_text?: string;
    countries?: string[];
  }>();

  if (!body.title) {
    throw new AppError("VALIDATION_ERROR", "Title is required", 400);
  }

  const id = generateId();
  const now = new Date().toISOString();
  const jobKey = body.url ? canonicalJobKey(body.url) : null;
  const countries = serializeCountries(body.countries || inferCountriesFromLocation(body.location));

  await c.env.DB.prepare(
    `INSERT INTO jobs (id, user_id, title, company, location, countries, job_url, job_key, raw_description, source, employment_type, workplace, salary_text, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      id,
      userId,
      body.title,
      body.company || "",
      body.location || "",
      countries,
      body.url || "",
      jobKey,
      body.raw_jd || "",
      body.source || "",
      body.employment_type || "",
      body.workplace || "",
      body.salary_text || "",
      now,
      now
    )
    .run();

  await prepareJobAfterCreate(c.env, userId, id);

  const job = await c.env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(id).first();
  return c.json(await formatJobResponse(c.env, userId, job!), 201);
});

// GET /api/jobs - List user's jobs
jobsRoutes.get("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const status = c.req.query("status");
  const stage = c.req.query("stage");
  const company = c.req.query("company");
  const addedDate = c.req.query("added_date");
  const country = c.req.query("country");
  const limit = Math.min(parseInt(c.req.query("limit") || "50", 10), 200);
  const offset = parseInt(c.req.query("offset") || "0", 10);

  let query = "SELECT * FROM jobs WHERE user_id = ?";
  const params: (string | number)[] = [userId];

  const filterSql = buildJobFilterSql({ status, stage, company, addedDate, country });
  query += filterSql.sql;
  params.push(...filterSql.params);

  // Count total
  let countQuery = "SELECT COUNT(*) as cnt FROM jobs WHERE user_id = ?";
  const countParams: (string | number)[] = [userId];
  countQuery += filterSql.sql;
  countParams.push(...filterSql.params);
  const countResult = await c.env.DB.prepare(countQuery).bind(...countParams).first<{ cnt: number }>();
  const total = countResult?.cnt || 0;

  query += " ORDER BY created_at DESC LIMIT ? OFFSET ?";
  params.push(limit, offset);

  const result = await c.env.DB.prepare(query).bind(...params).all();
  const items = await Promise.all((result.results || []).map((job) => formatJobResponse(c.env, userId, job)));
  return c.json({ items, total, limit, offset });
});

// GET /api/jobs/filters - Distinct filter options for Jobs page
jobsRoutes.get("/filters", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ companies: [], statuses: [], added_dates: [], countries: [] });

  const companyRows = await c.env.DB.prepare(
    `SELECT company, COUNT(*) AS count
     FROM jobs
     WHERE user_id = ? AND company IS NOT NULL AND TRIM(company) != ''
     GROUP BY company
     ORDER BY LOWER(company)`
  )
    .bind(userId)
    .all<{ company: string; count: number }>();

  const statusRows = await c.env.DB.prepare(
    `SELECT
       SUM(CASE WHEN saved = 1 THEN 1 ELSE 0 END) AS saved,
       SUM(CASE WHEN application_status = 'applied' THEN 1 ELSE 0 END) AS applied,
       SUM(CASE WHEN application_status = 'interview' THEN 1 ELSE 0 END) AS interview,
       SUM(CASE WHEN application_status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
       SUM(CASE WHEN application_status = 'offer' THEN 1 ELSE 0 END) AS offer
     FROM jobs
     WHERE user_id = ?`
  )
    .bind(userId)
    .first<{ saved: number; applied: number; interview: number; rejected: number; offer: number }>();

  const addedDateRows = await c.env.DB.prepare(
    `SELECT date(COALESCE(pipeline_added_at, created_at)) AS added_date, COUNT(*) AS count
     FROM jobs
     WHERE user_id = ? AND COALESCE(pipeline_added_at, created_at) IS NOT NULL
     GROUP BY date(COALESCE(pipeline_added_at, created_at))
     ORDER BY added_date DESC`
  )
    .bind(userId)
    .all<{ added_date: string; count: number }>();

  const countryRows = await getCountryFilterRows(c.env, userId);

  return c.json({
    companies: (companyRows.results || []).map((row) => ({ value: row.company, count: row.count })),
    statuses: normalizeStatusCounts(statusRows || { saved: 0, applied: 0, interview: 0, rejected: 0, offer: 0 }),
    added_dates: (addedDateRows.results || [])
      .filter((row) => row.added_date)
      .map((row) => ({ value: row.added_date, count: row.count })),
    countries: countryRows,
  });
});

// GET /api/jobs/unparsed - Latest imported jobs that still need LLM parsing
jobsRoutes.get("/unparsed", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const limit = Math.min(parseInt(c.req.query("limit") || "5", 10), 25);
  const offset = parseInt(c.req.query("offset") || "0", 10);
  const result = await c.env.DB.prepare(
    `SELECT id, title, company, job_url, pipeline_added_at, created_at
     FROM jobs
     WHERE user_id = ?
       AND raw_description IS NOT NULL
       AND TRIM(raw_description) != ''
       AND (parsed_json IS NULL OR TRIM(parsed_json) = '')
     ORDER BY COALESCE(pipeline_added_at, created_at) DESC
     LIMIT ? OFFSET ?`
  )
    .bind(userId, limit, offset)
    .all();

  return c.json({ items: result.results || [], limit, offset });
});

// PATCH /api/jobs/:id/status - Update job status
jobsRoutes.patch("/:id/status", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const jobId = c.req.param("id");
  const body = await c.req.json<{ status?: string; saved?: boolean }>();

  const job = await c.env.DB.prepare("SELECT * FROM jobs WHERE id = ? AND user_id = ?")
    .bind(jobId, userId)
    .first();
  if (!job) throw new AppError("NOT_FOUND", "Job not found", 404);

  const now = new Date().toISOString();
  const updates: string[] = ["updated_at = ?"];
  const values: (string | number | null)[] = [now];

  if (body.status !== undefined && body.status !== "saved") {
    updates.push("application_status = ?");
    values.push(body.status === "new" ? null : body.status);
  }
  if (body.saved !== undefined) {
    updates.push("saved = ?");
    values.push(body.saved ? 1 : 0);
  }
  if (body.status === "saved") {
    updates.push("saved = 1");
  }

  values.push(jobId, userId);
  await c.env.DB.prepare(`UPDATE jobs SET ${updates.join(", ")} WHERE id = ? AND user_id = ?`).bind(...values).run();

  if (body.saved === true || body.status === "saved") {
    await ensureApplicationForJob(c.env, userId, jobId);
  }

  if (body.status !== undefined && body.status !== "saved") {
    await syncApplicationForJobStatus(c.env, userId, jobId, body.status === "new" ? null : body.status);
  }

  const updated = await c.env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(jobId).first();
  return c.json(await formatJobResponse(c.env, userId, updated!));
});

// GET /api/jobs/:id/match - Latest match report for a job
jobsRoutes.get("/:id/match", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const jobId = c.req.param("id");
  const job = await c.env.DB.prepare("SELECT id FROM jobs WHERE id = ? AND user_id = ?")
    .bind(jobId, userId)
    .first();
  if (!job) throw new AppError("NOT_FOUND", "Job not found", 404);

  const match = await getLatestMatchRow(c.env, userId, jobId);
  return c.json(match ? formatMatchResponse(match) : null);
});

// POST /api/jobs/:id/match - Compute a match with the latest profile
jobsRoutes.post("/:id/match", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const jobId = c.req.param("id");
  const job = await c.env.DB.prepare(
    "SELECT id, title, company, raw_description FROM jobs WHERE id = ? AND user_id = ?"
  )
    .bind(jobId, userId)
    .first<{ id: string; title: string; company: string; raw_description: string }>();
  if (!job) throw new AppError("NOT_FOUND", "Job not found", 404);

  const profile = await getLatestProfile(c.env, userId);
  if (!profile) throw new AppError("NOT_FOUND", "Profile not found", 404);

  const report = await computeAndStoreMatch(c.env, userId, job, profile);
  return c.json(report, 201);
});

// GET /api/jobs/:id/resume - Latest generated resume artifact for a job
jobsRoutes.get("/:id/resume", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const jobId = c.req.param("id");
  const job = await c.env.DB.prepare("SELECT id FROM jobs WHERE id = ? AND user_id = ?")
    .bind(jobId, userId)
    .first();
  if (!job) throw new AppError("NOT_FOUND", "Job not found", 404);

  const artifact = await getLatestResumeArtifact(c.env, userId, jobId);
  return c.json(artifact);
});

// POST /api/jobs/:id/resume - Generate a tailored resume for a job
jobsRoutes.post("/:id/resume", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const jobId = c.req.param("id");
  const body: { confirmed_skills?: string[]; style?: string } = await c.req
    .json<{ confirmed_skills?: string[]; style?: string }>()
    .catch(() => ({}));
  const job = await c.env.DB.prepare(
    "SELECT id, title, company, raw_description, parsed_json FROM jobs WHERE id = ? AND user_id = ?"
  )
    .bind(jobId, userId)
    .first<{ id: string; title: string; company: string; raw_description: string; parsed_json: string | null }>();
  if (!job) throw new AppError("NOT_FOUND", "Job not found", 404);

  const profile = await getLatestProfile(c.env, userId);
  if (!profile) throw new AppError("NOT_FOUND", "Profile not found", 404);

  const match = await getLatestMatchRow(c.env, userId, jobId);
  const artifact = await generateAndStoreResume(c.env, userId, job, profile, {
    confirmedSkills: body.confirmed_skills || [],
    matchResult: match?.match_result || null,
    style: body.style || "us",
  });
  return c.json(artifact, 201);
});

// POST /api/jobs/:id/parse - Parse job description (trigger LLM)
jobsRoutes.post("/:id/parse", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const jobId = c.req.param("id");
  const job = await c.env.DB.prepare("SELECT id, title, company, job_url, raw_description FROM jobs WHERE id = ? AND user_id = ?")
    .bind(jobId, userId)
    .first<{ id: string; title: string; company: string; job_url: string; raw_description: string }>();
  if (!job) throw new AppError("NOT_FOUND", "Job not found", 404);

  let rawDescription = job.raw_description;
  if (isLimitedLinkedInJobText(job.job_url, rawDescription, job.title, job.company)) {
    const refreshed = await fetchJobPage(job.job_url);
    if (isLimitedLinkedInJobText(job.job_url, refreshed.rawText, job.title, job.company)) {
      throw new AppError("FETCH_RETRY", "LinkedIn returned limited job content; retry later", 503);
    }
    rawDescription = refreshed.rawText;
    await c.env.DB.prepare("UPDATE jobs SET raw_description = ?, updated_at = ? WHERE id = ? AND user_id = ?")
      .bind(rawDescription, new Date().toISOString(), jobId, userId)
      .run();
  }

  const parsedJson = await parseAndStoreJobDetails(c.env, userId, jobId, rawDescription);

  return c.json({ job_id: jobId, status: "parsed", parsed_json: parsedJson });
});

// GET /api/jobs/:id
jobsRoutes.get("/:id", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const jobId = c.req.param("id");
  const job = await c.env.DB.prepare("SELECT * FROM jobs WHERE id = ? AND user_id = ?")
    .bind(jobId, userId)
    .first();

  if (!job) {
    throw new AppError("NOT_FOUND", "Job not found", 404);
  }

  return c.json(await formatJobResponse(c.env, userId, job));
});

// DELETE /api/jobs/:id
jobsRoutes.delete("/:id", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const jobId = c.req.param("id");
  const job = await c.env.DB.prepare("SELECT id FROM jobs WHERE id = ? AND user_id = ?")
    .bind(jobId, userId)
    .first();

  if (!job) {
    throw new AppError("NOT_FOUND", "Job not found", 404);
  }

  await c.env.DB.batch([
    c.env.DB.prepare(
      `UPDATE artifacts
       SET application_id = NULL
       WHERE application_id IN (SELECT id FROM applications WHERE job_id = ? AND user_id = ?)`
    ).bind(jobId, userId),
    c.env.DB.prepare("DELETE FROM applications WHERE job_id = ? AND user_id = ?").bind(jobId, userId),
    c.env.DB.prepare("DELETE FROM jobs WHERE id = ? AND user_id = ?").bind(jobId, userId),
  ]);
  return c.json({ message: "Job deleted" });
});

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function formatJobResponse(env: Env, userId: string, job: Record<string, any>) {
  const match = await getLatestMatchRow(env, userId, String(job.id));
  const matchResponse = match ? formatMatchResponse(match) : null;
  return {
    id: job.id,
    job_key: job.job_key,
    title: job.title,
    company: job.company,
    location: job.location,
    countries: countriesForJob(job),
    url: job.job_url,
    source: job.source,
    employment_type: job.employment_type,
    workplace: job.workplace,
    salary_text: job.salary_text,
    raw_jd: job.raw_description,
    parsed_json: safeJsonParse(job.parsed_json as string | null),
    status: job.status,
    saved: Boolean(job.saved),
    application_status: job.application_status,
    score: matchResponse?.overall_score ?? null,
    recommendation: matchResponse?.recommendation ?? null,
    pipeline_added_at: job.pipeline_added_at,
    pipeline_source_sha: job.pipeline_source_sha,
    created_at: job.created_at,
    updated_at: job.updated_at,
  };
}

function normalizeImportItems(body: JobImportBody): JobImportItem[] {
  if (Array.isArray(body.jobs) && body.jobs.length > 0) {
    return body.jobs
      .map((job) => ({ ...job, url: job.url?.trim() || "" }))
      .filter((job) => /^https?:\/\//i.test(job.url));
  }
  return (body.urls || [])
    .map((url) => ({ url: url.trim() }))
    .filter((job) => /^https?:\/\//i.test(job.url));
}

async function importParsedUserId(c: Context<{ Bindings: Env }>): Promise<string | null> {
  const authorization = c.req.header("Authorization");
  const serviceToken = c.env.DACHJOB_IMPORT_PARSED_TOKEN;
  const serviceUserId = c.env.DACHJOB_IMPORT_PARSED_USER_ID;
  const bearer = authorization?.match(/^Bearer\s+(.+)$/i)?.[1]?.trim();
  if (serviceToken && serviceUserId && bearer && bearer === serviceToken) {
    return serviceUserId;
  }
  return authMiddleware(c);
}

function normalizeParsedImportItems(body: ParsedJobImportBody): ParsedJobImportItem[] {
  return (body.jobs || [])
    .map((job) => ({
      ...job,
      url: job.url?.trim() || "",
      title: job.title?.trim() || "",
      company: job.company?.trim() || "",
      location: job.location?.trim() || "",
      raw_description: job.raw_description?.trim() || "",
    }))
    .filter(
      (job) =>
        /^https?:\/\//i.test(job.url) &&
        Boolean(job.title) &&
        Boolean(job.raw_description) &&
        typeof job.parsed_json === "object" &&
        job.parsed_json !== null &&
        !Array.isArray(job.parsed_json)
    );
}

function buildJobFilterSql(filters: {
  status?: string;
  stage?: string;
  company?: string;
  addedDate?: string;
  country?: string;
}): { sql: string; params: (string | number)[] } {
  let sql = "";
  const params: (string | number)[] = [];

  if (filters.status && filters.status !== "all") {
    const status = normalizeStageFilter(filters.status);
    if (status === "saved") {
      sql += " AND saved = 1";
    } else if (status === "applied") {
      sql += " AND application_status IN (?, ?, ?, ?)";
      params.push(...APPLICATION_JOB_STATUSES);
    } else if (status === "received") {
      sql += " AND application_status IS NULL";
    } else if (status) {
      sql += " AND application_status = ?";
      params.push(status);
    }
  }

  const stage = normalizeStageFilter(filters.stage);
  if (stage && stage !== "all") {
    if (stage === "received") {
      sql += " AND application_status IS NULL";
    } else {
      sql += " AND application_status = ?";
      params.push(stage);
    }
  }

  const company = filters.company?.trim();
  if (company) {
    sql += " AND company = ?";
    params.push(company);
  }

  const addedDate = filters.addedDate?.trim();
  if (addedDate) {
    sql += " AND date(COALESCE(pipeline_added_at, created_at)) = ?";
    params.push(addedDate);
  }

  const country = filters.country?.trim();
  if (country && (JOB_COUNTRIES as readonly string[]).includes(country)) {
    sql += " AND countries LIKE ?";
    params.push(`%|${country}|%`);
  }

  return { sql, params };
}

function normalizeStageFilter(value?: string): string | null {
  const normalized = (value || "").trim().toLowerCase();
  if (!normalized || normalized === "new") return normalized ? "received" : null;
  if (normalized === "all" || normalized === "saved") return normalized;
  if (normalized === "received") return "received";
  if (APPLICATION_JOB_STATUSES.includes(normalized)) return normalized;
  return null;
}

function normalizeStatusCounts(counts: { saved: number; applied: number; interview: number; rejected: number; offer: number }) {
  return ["saved", "applied", "interview", "rejected", "offer"].map((status) => ({
    value: status,
    count: counts[status as keyof typeof counts] || 0,
  }));
}

async function getCountryFilterRows(env: Env, userId: string): Promise<Array<{ value: string; count: number }>> {
  const rows = await Promise.all(
    JOB_COUNTRIES.map(async (country) => {
      const result = await env.DB.prepare(
        `SELECT COUNT(*) AS count
         FROM jobs
         WHERE user_id = ? AND countries LIKE ?`
      )
        .bind(userId, `%|${country}|%`)
        .first<{ count: number }>();
      return { value: country, count: result?.count || 0 };
    })
  );
  return rows.filter((row) => row.count > 0);
}

function canonicalJobKey(url: string): string {
  const parsed = new URL(url);
  const linkedInJobId = parsed.hostname.endsWith("linkedin.com")
    ? parsed.pathname.match(/\/jobs\/view\/(?:[^/]+-)?(\d+)/)
    : null;
  if (linkedInJobId) return `linkedin:${linkedInJobId[1]}`;

  const indeedId = parsed.hostname.endsWith("indeed.com") ? parsed.searchParams.get("jk") : null;
  if (indeedId) return `indeed:${indeedId}`;

  const greenhouseToken = parsed.searchParams.get("gh_jid");
  if (greenhouseToken) return `${parsed.hostname.toLowerCase().replace(/^www\./, "")}:gh_jid:${greenhouseToken}`;

  parsed.hash = "";
  parsed.search = "";
  parsed.hostname = parsed.hostname.toLowerCase().replace(/^www\./, "");
  parsed.pathname = parsed.pathname.replace(/\/+$/, "");
  return `${parsed.hostname}${parsed.pathname}`.toLowerCase();
}

function normalizeIsoDate(value?: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function normalizePipelineStatus(value?: string | null): string | null {
  const normalized = (value || "").trim().toLowerCase();
  if (!normalized || normalized === "received" || normalized === "new") return null;
  return APPLICATION_JOB_STATUSES.includes(normalized) ? normalized : null;
}

async function updateExistingImportedJob(
  env: Env,
  userId: string,
  jobId: string,
  metadata: { jobKey: string; addedAt: string; status: string | null; sourceSha?: string }
) {
  await env.DB.prepare(
    `UPDATE jobs
     SET job_key = COALESCE(job_key, ?),
         pipeline_added_at = COALESCE(pipeline_added_at, ?),
         pipeline_source_sha = COALESCE(pipeline_source_sha, ?),
         created_at = CASE
           WHEN pipeline_added_at IS NULL AND created_at > ? THEN ?
           ELSE created_at
         END,
         updated_at = ?
     WHERE id = ? AND user_id = ?`
  )
    .bind(
      metadata.jobKey,
      metadata.addedAt,
      metadata.sourceSha || null,
      metadata.addedAt,
      metadata.addedAt,
      new Date().toISOString(),
      jobId,
      userId
    )
    .run();
  if (metadata.status) {
    await setJobApplicationStatus(env, userId, jobId, metadata.status);
  }
}

function safeJsonParse(value: string | null): Record<string, unknown> | null {
  if (!value) return null;
  try {
    return JSON.parse(value) as Record<string, unknown>;
  } catch {
    return null;
  }
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function countriesForJob(job: Record<string, any>): string[] {
  const persisted = parseSerializedCountries(job.countries as string | null);
  if (persisted.length > 0) return persisted;
  return countriesForLocation(job.location as string | null).countries;
}

function readParsedString(parsed: Record<string, unknown>, key: string): string | null {
  const value = parsed[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

async function getLatestMatchRow(env: Env, userId: string, jobId: string): Promise<ApplicationMatchRow | null> {
  return env.DB.prepare(
    `SELECT id, job_id, match_score, match_result, created_at, updated_at
     FROM applications
     WHERE user_id = ? AND job_id = ? AND match_result IS NOT NULL
     ORDER BY updated_at DESC, created_at DESC
     LIMIT 1`
  )
    .bind(userId, jobId)
    .first<ApplicationMatchRow>();
}

function normalizeScore(score: number | null | undefined): number {
  if (score == null || Number.isNaN(score)) return 1;
  const fivePoint = score > 5 ? score / 20 : score;
  return Math.round(Math.min(Math.max(fivePoint, 1), 5) * 100) / 100;
}

function recommendationForScore(score: number): string {
  if (score >= 4.2) return "apply";
  if (score >= 3.6) return "maybe";
  return "skip";
}

function formatMatchResponse(match: ApplicationMatchRow) {
  const parsed = safeJsonParse(match.match_result);
  const score = normalizeScore(
    typeof parsed?.overall_score === "number"
      ? parsed.overall_score
      : typeof parsed?.match_score === "number"
        ? parsed.match_score
        : match.match_score
  );
  const recommendation =
    typeof parsed?.recommendation === "string" ? parsed.recommendation : recommendationForScore(score);
  const gaps = Array.isArray(parsed?.gaps) ? parsed.gaps : [];
  const topReasons = Array.isArray(parsed?.top_reasons)
    ? parsed.top_reasons
    : Array.isArray(parsed?.strengths)
      ? parsed.strengths
      : [];
  return {
    id: match.id,
    job_id: match.job_id,
    overall_score: score,
    recommendation,
    breakdown_json: typeof parsed?.breakdown === "object" && parsed.breakdown ? parsed.breakdown : {},
    gaps_json: { gaps },
    explanation:
      typeof parsed?.explanation === "string"
        ? parsed.explanation
        : topReasons.map(String).join(" "),
    created_at: match.created_at,
  };
}

async function getLatestProfile(env: Env, userId: string): Promise<ProfileRow | null> {
  return env.DB.prepare(
    "SELECT id, name, raw_cv_md, profile_json FROM candidate_profiles WHERE user_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT 1"
  )
    .bind(userId)
    .first<ProfileRow>();
}

async function getOrCreateApplication(env: Env, userId: string, jobId: string, profileId: string): Promise<string> {
  const existing = await env.DB.prepare(
    "SELECT id FROM applications WHERE user_id = ? AND job_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT 1"
  )
    .bind(userId, jobId)
    .first<{ id: string }>();
  if (existing) return existing.id;

  const id = generateId();
  const now = new Date().toISOString();
  await env.DB.prepare(
    `INSERT INTO applications (id, user_id, job_id, profile_id, status, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(id, userId, jobId, profileId, "draft", now, now)
    .run();
  return id;
}

async function ensureApplicationForJob(env: Env, userId: string, jobId: string) {
  const profile = await getLatestProfile(env, userId);
  await getOrCreateApplication(env, userId, jobId, profile?.id || "");
}

async function syncApplicationForJobStatus(
  env: Env,
  userId: string,
  jobId: string,
  status: string | null
) {
  const profile = await getLatestProfile(env, userId);
  const applicationId = await getOrCreateApplication(env, userId, jobId, profile?.id || "");
  const now = new Date().toISOString();
  await env.DB.prepare("UPDATE applications SET status = ?, updated_at = ? WHERE id = ? AND user_id = ?")
    .bind(status || "draft", now, applicationId, userId)
    .run();
}

async function setJobApplicationStatus(
  env: Env,
  userId: string,
  jobId: string,
  status: string
) {
  const now = new Date().toISOString();
  await env.DB.prepare(
    "UPDATE jobs SET application_status = ?, updated_at = ? WHERE id = ? AND user_id = ?"
  )
    .bind(status, now, jobId, userId)
    .run();
  await syncApplicationForJobStatus(env, userId, jobId, status);
}

async function computeAndStoreMatch(
  env: Env,
  userId: string,
  job: { id: string; title: string; company: string; raw_description: string },
  profile: ProfileRow
) {
  const startTime = Date.now();
  const prompt = `You are an expert job matching assistant. Analyze the fit between this candidate profile and job description.

Job: ${job.title} at ${job.company}
Job Description:
${job.raw_description.slice(0, 5000)}

Candidate Profile:
${profile.raw_cv_md.slice(0, 5000)}

Respond only as JSON:
{
  "overall_score": <number from 1 to 5>,
  "recommendation": "apply" | "maybe" | "skip",
  "breakdown": {"role_relevance": <1-5>, "skill_match": <1-5>, "dach_feasibility": <1-5>},
  "top_reasons": ["reason"],
  "gaps": ["gap"],
  "explanation": "short explanation"
}`;

  let parsed: Record<string, unknown>;
  try {
    const content = await callDeepSeekChat(env, [{ role: "user", content: prompt }], {
      temperature: 0.2,
      json: true,
    });
    parsed = JSON.parse(content) as Record<string, unknown>;
    await logLLMRun(env, userId, "job_match", startTime, "success");
  } catch (err) {
    parsed = {
      overall_score: 2.5,
      recommendation: "maybe",
      breakdown: {},
      top_reasons: ["Unable to complete LLM match analysis."],
      gaps: [(err as Error).message],
      explanation: "The match could not be fully analyzed. Please try again later.",
    };
    await logLLMRun(env, userId, "job_match", startTime, "error", (err as Error).message);
  }

  const score = normalizeScore(typeof parsed.overall_score === "number" ? parsed.overall_score : null);
  parsed.overall_score = score;
  parsed.recommendation = typeof parsed.recommendation === "string" ? parsed.recommendation : recommendationForScore(score);

  const applicationId = await getOrCreateApplication(env, userId, job.id, profile.id);
  const now = new Date().toISOString();
  await env.DB.prepare(
    "UPDATE applications SET match_score = ?, match_result = ?, updated_at = ? WHERE id = ? AND user_id = ?"
  )
    .bind(score, JSON.stringify(parsed), now, applicationId, userId)
    .run();

  const match = await getLatestMatchRow(env, userId, job.id);
  return formatMatchResponse(match!);
}

async function getLatestResumeArtifact(env: Env, userId: string, jobId: string) {
  const row = await env.DB.prepare(
    `SELECT artifacts.id, artifacts.r2_key, artifacts.created_at, applications.job_id
     FROM artifacts
     JOIN applications ON applications.id = artifacts.application_id
     WHERE artifacts.user_id = ? AND applications.user_id = ? AND applications.job_id = ? AND artifacts.type = 'cv_html'
     ORDER BY artifacts.created_at DESC
     LIMIT 1`
  )
    .bind(userId, userId, jobId)
    .first<{ id: string; r2_key: string; created_at: string; job_id: string }>();
  if (!row) return null;
  return {
    id: row.id,
    job_id: row.job_id,
    html_object_key: row.r2_key,
    pdf_object_key: null,
    provenance_json: [],
  };
}

async function importSingleJobUrl(
  env: Env,
  userId: string,
  item: JobImportItem
): Promise<{ job: Record<string, unknown>; cacheHit: boolean }> {
  const cleanedUrl = item.url.trim();
  const jobKey = canonicalJobKey(cleanedUrl);
  const addedAt = normalizeIsoDate(item.added_at) || new Date().toISOString();
  const requestedStatus = normalizePipelineStatus(item.status);
  const existing = await env.DB.prepare(
    "SELECT * FROM jobs WHERE user_id = ? AND (job_key = ? OR job_url = ?)"
  )
    .bind(userId, jobKey, cleanedUrl)
    .first();
  if (existing) {
    await updateExistingImportedJob(env, userId, String(existing.id), {
      jobKey,
      addedAt,
      status: requestedStatus,
      sourceSha: item.source_sha,
    });
    await logLLMRun(env, userId, "job_import", Date.now(), "cache_hit", `Duplicate job import: ${cleanedUrl}`);
    const refreshed = await env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(existing.id).first();
    return { job: await formatJobResponse(env, userId, refreshed || existing), cacheHit: true };
  }

  const { html, rawText } = await fetchJobPage(cleanedUrl);

  // Extract title from HTML
  const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
  let title = titleMatch ? titleMatch[1].trim() : "Imported Job";
  // Clean title
  title = title.replace(/\s*[\|–—-]\s*LinkedIn.*$/i, "").trim();
  title = title.replace(/\s*[\|–—-]\s*Greenhouse.*$/i, "").trim();

  // Try to extract company from title
  const companyMatch = title.match(/(?:at|@|[\|–—-])\s*(.+?)$/);
  let company = companyMatch ? companyMatch[1].trim() : "";
  if (companyMatch) {
    title = title.replace(/\s*(?:at|@|[\|–—-])\s*.+?$/, "").trim();
  }

  if (!company) {
    try {
      const urlObj = new URL(cleanedUrl);
      company = urlObj.hostname.replace(/^www\./, "").split(".")[0];
      company = company.charAt(0).toUpperCase() + company.slice(1);
    } catch {
      company = "Unknown";
    }
  }
  title = item.title?.trim() || title;
  company = item.company?.trim() || company;

  if (isLimitedLinkedInJobText(cleanedUrl, rawText, title, company)) {
    throw new Error("RETRYABLE_FETCH: LinkedIn returned limited job content; retry later");
  }

  const mismatchReason = getProfileMismatchReason(`${title}\n${company}\n${rawText}`);
  if (mismatchReason) {
    await logLLMRun(env, userId, "job_import", Date.now(), "skipped", mismatchReason);
    throw new Error(`${PROFILE_MISMATCH_ERROR_PREFIX} ${mismatchReason}`);
  }

  const id = generateId();
  const now = new Date().toISOString();
  const location = item.location?.trim() || "";
  const countries = serializeCountries(item.countries || inferCountriesFromLocation(location));

  await env.DB.prepare(
    `INSERT INTO jobs (
       id, user_id, title, company, location, countries, job_url, job_key, raw_description, source,
       pipeline_added_at, pipeline_source_sha, created_at, updated_at
     )
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      id,
      userId,
      title,
      company,
      location,
      countries,
      cleanedUrl,
      jobKey,
      rawText,
      "pipeline_md",
      addedAt,
      item.source_sha || null,
      addedAt,
      now
    )
    .run();

  if (item.prepare !== false) {
    await prepareJobAfterCreate(env, userId, id);
  }
  if (requestedStatus) {
    await setJobApplicationStatus(env, userId, id, requestedStatus);
  }

  const job = await env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(id).first();
  return { job: await formatJobResponse(env, userId, job!), cacheHit: false };
}

async function importSingleParsedJob(
  env: Env,
  userId: string,
  item: ParsedJobImportItem
): Promise<{ job: Record<string, unknown>; cacheHit: boolean }> {
  const cleanedUrl = item.url.trim();
  const jobKey = item.job_key?.trim() || canonicalJobKey(cleanedUrl);
  const addedAt = normalizeIsoDate(item.pipeline_added_at) || new Date().toISOString();
  const requestedStatus = normalizePipelineStatus(item.status);
  const now = new Date().toISOString();
  const countries = serializeCountries(item.countries || inferCountriesFromLocation(item.location));
  const parsedJson = JSON.stringify(item.parsed_json);

  const existing = await env.DB.prepare(
    "SELECT * FROM jobs WHERE user_id = ? AND (job_key = ? OR job_url = ?)"
  )
    .bind(userId, jobKey, cleanedUrl)
    .first();

  if (existing) {
    await env.DB.prepare(
      `UPDATE jobs
       SET title = ?,
           company = ?,
           location = ?,
           countries = ?,
           job_url = ?,
           job_key = ?,
           raw_description = ?,
           parsed_json = ?,
           source = ?,
           employment_type = ?,
           workplace = ?,
           salary_text = ?,
           pipeline_added_at = COALESCE(pipeline_added_at, ?),
           pipeline_source_sha = COALESCE(?, pipeline_source_sha),
           updated_at = ?
       WHERE id = ? AND user_id = ?`
    )
      .bind(
        item.title,
        item.company || "",
        item.location || "",
        countries,
        cleanedUrl,
        jobKey,
        item.raw_description,
        parsedJson,
        "li_job_scout_opencode",
        item.employment_type || "",
        item.workplace || "",
        item.salary_text || "",
        addedAt,
        item.pipeline_source_sha || null,
        now,
        existing.id,
        userId
      )
      .run();
    if (requestedStatus) {
      await setJobApplicationStatus(env, userId, String(existing.id), requestedStatus);
    }
    const refreshed = await env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(existing.id).first();
    return { job: await formatJobResponse(env, userId, refreshed || existing), cacheHit: true };
  }

  const id = generateId();
  await env.DB.prepare(
    `INSERT INTO jobs (
       id, user_id, title, company, location, countries, job_url, job_key, raw_description,
       parsed_json, source, employment_type, workplace, salary_text,
       pipeline_added_at, pipeline_source_sha, created_at, updated_at
     )
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      id,
      userId,
      item.title,
      item.company || "",
      item.location || "",
      countries,
      cleanedUrl,
      jobKey,
      item.raw_description,
      parsedJson,
      "li_job_scout_opencode",
      item.employment_type || "",
      item.workplace || "",
      item.salary_text || "",
      addedAt,
      item.pipeline_source_sha || null,
      addedAt,
      now
    )
    .run();
  if (requestedStatus) {
    await setJobApplicationStatus(env, userId, id, requestedStatus);
  }
  const job = await env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(id).first();
  return { job: await formatJobResponse(env, userId, job!), cacheHit: false };
}

function getProfileMismatchReason(text: string): string | null {
  const normalized = text.replace(/\s+/g, " ").trim();
  const title = normalized.slice(0, 240);
  if (/(^|[^a-z0-9])(c\+\+|c\/c\+\+)([^a-z0-9]|$)/i.test(title) && /\b(engineer|developer|entwickler|programmer)\b/i.test(title)) {
    return "Hard C/C++ role in title";
  }

  const sentences = normalized.split(/(?<=[.!?;])\s+|\n+/).slice(0, 120);
  for (const sentence of sentences) {
    if (sentence.length > 500) continue;
    if (!/(^|[^a-z0-9])(c\+\+|c\/c\+\+|embedded c)([^a-z0-9]|$)/i.test(sentence)) continue;
    if (
      /\b(including,? but not limited to|not limited to|one or more|any of|desirable|nice to have|preferred|plus|bonus|such as)\b/i.test(
        sentence
      )
    ) {
      continue;
    }
    if (
      /\b(required|required qualifications?|requirements?|must have|you have|we expect|professional experience|proven experience|strong experience|solid experience|hands[- ]on experience|expertise in|proficiency in|programming in|coding in|daily)\b/i.test(
        sentence
      )
    ) {
      return "Hard C/C++ requirement";
    }
  }

  const firstText = normalized.slice(0, 1200);
  const looksLikeFirmwareRole = /\b(firmware|embedded software|hardware validation|fpga)\b/i.test(firstText);
  const hasTargetScope = /\b(cloud|platform|backend|data platform|ml platform|ai platform|infrastructure|kubernetes|distributed systems)\b/i.test(
    firstText
  );
  if (looksLikeFirmwareRole && !hasTargetScope) {
    return "Firmware/embedded role without backend, cloud, data, or platform scope";
  }

  return null;
}

async function fetchJobPage(url: string): Promise<{ html: string; rawText: string }> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  let response: Response;
  try {
    response = await fetch(url, {
      signal: controller.signal,
      headers: {
        "User-Agent":
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
      },
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Timed out fetching URL after 15s");
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
  if (!response.ok) {
    throw new Error(`Failed to fetch URL: ${response.status}`);
  }

  const html = await response.text();
  return { html, rawText: stripHtml(html).slice(0, 15000) };
}

function isLimitedLinkedInJobText(url: string, rawText: string, title?: string, company?: string): boolean {
  if (!isLinkedInUrl(url)) return false;
  const text = rawText.replace(/\s+/g, " ").trim();
  if (text.length < 1200) return true;

  const firstPage = normalizeComparableText(text.slice(0, 3500));
  const normalizedTitle = normalizeTextNeedle(title);
  const normalizedCompany = normalizeTextNeedle(company);
  const hasTitle = !normalizedTitle || firstPage.includes(normalizedTitle);
  const hasCompany = !normalizedCompany || firstPage.includes(normalizedCompany);
  if (!hasTitle || !hasCompany) return true;

  const authWallOnly =
    /join or sign in to find your next job|sign in to create job alert|authwall|login to linkedin/i.test(text) &&
    text.length < 2500;
  return authWallOnly;
}

function isLinkedInUrl(url: string): boolean {
  try {
    return new URL(url).hostname.toLowerCase().endsWith("linkedin.com");
  } catch {
    return false;
  }
}

function normalizeTextNeedle(value?: string): string | null {
  const normalized = normalizeComparableText(value || "");
  return normalized.length >= 3 ? normalized : null;
}

function normalizeComparableText(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9+.#]+/g, " ")
    .trim();
}

function stripHtml(html: string): string {
  let text = html.replace(/<script[^>]*>.*?<\/script>/gis, "");
  text = text.replace(/<style[^>]*>.*?<\/style>/gis, "");
  text = text.replace(/<[^>]+>/g, " ");
  text = text.replace(/&nbsp;/g, " ");
  text = text.replace(/&amp;/g, "&");
  text = text.replace(/&lt;/g, "<");
  text = text.replace(/&gt;/g, ">");
  text = text.replace(/&quot;/g, '"');
  text = text.replace(/\s+/g, " ");
  return text.trim();
}

async function prepareJobAfterCreate(env: Env, userId: string, jobId: string) {
  const job = await env.DB.prepare(
    "SELECT id, title, company, raw_description FROM jobs WHERE id = ? AND user_id = ?"
  )
    .bind(jobId, userId)
    .first<{ id: string; title: string; company: string; raw_description: string }>();
  if (!job) return;

  try {
    await parseAndStoreJobDetails(env, userId, job.id, job.raw_description);
  } catch {
    // Keep the add/import flow usable even if the model provider is temporarily unavailable.
  }

  const refreshed = await env.DB.prepare(
    "SELECT id, title, company, raw_description FROM jobs WHERE id = ? AND user_id = ?"
  )
    .bind(jobId, userId)
    .first<{ id: string; title: string; company: string; raw_description: string }>();
  const profile = await getLatestProfile(env, userId);
  if (!refreshed || !profile) return;

  await computeAndStoreMatch(env, userId, refreshed, profile);
}

async function parseAndStoreJobDetails(
  env: Env,
  userId: string,
  jobId: string,
  rawDescription: string
): Promise<Record<string, unknown> | null> {
  if (!rawDescription.trim()) return null;

  const startTime = Date.now();
  try {
    const content = await callDeepSeekChat(
      env,
      [
        {
          role: "system",
          content: `Extract structured job information from the description. Return JSON with:
{
  "title": "job title",
  "company": "company name",
  "location": "location",
  "employment_type": "full-time/part-time/contract",
  "workplace": "remote/hybrid/onsite if mentioned",
  "responsibilities": ["resp1", "resp2"],
  "required_qualifications": ["required qualification"],
  "preferred_qualifications": ["preferred qualification"],
  "must_have_skills": ["skill"],
  "nice_to_have_skills": ["skill"],
  "experience_years": 3,
  "benefits": ["benefit"],
  "salary_range": "salary range if mentioned"
}`,
        },
        { role: "user", content: rawDescription.slice(0, 8000) },
      ],
      { temperature: 0.2, json: true }
    );
    const parsedJson = JSON.parse(content) as Record<string, unknown>;
    const now = new Date().toISOString();
    const parsedTitle = readParsedString(parsedJson, "title");
    const parsedCompany = readParsedString(parsedJson, "company");
    const parsedLocation = readParsedString(parsedJson, "location");
    const parsedCountries = parsedLocation ? serializeCountries(inferCountriesFromLocation(parsedLocation)) : "";
    const parsedEmploymentType = readParsedString(parsedJson, "employment_type");
    const parsedWorkplace = readParsedString(parsedJson, "workplace");
    const parsedSalary = readParsedString(parsedJson, "salary_range") || readParsedString(parsedJson, "salary_text");

    await env.DB.prepare(
      `UPDATE jobs
       SET parsed_json = ?,
           title = COALESCE(NULLIF(?, ''), title),
           company = COALESCE(NULLIF(?, ''), company),
           location = COALESCE(NULLIF(?, ''), location),
           countries = CASE WHEN ? != '' THEN ? ELSE countries END,
           employment_type = COALESCE(NULLIF(?, ''), employment_type),
           workplace = COALESCE(NULLIF(?, ''), workplace),
           salary_text = COALESCE(NULLIF(?, ''), salary_text),
           updated_at = ?
       WHERE id = ? AND user_id = ?`
    )
      .bind(
        JSON.stringify(parsedJson),
        parsedTitle || "",
        parsedCompany || "",
        parsedLocation || "",
        parsedCountries,
        parsedCountries,
        parsedEmploymentType || "",
        parsedWorkplace || "",
        parsedSalary || "",
        now,
        jobId,
        userId
      )
      .run();

    await logLLMRun(env, userId, "job_parse", startTime, "success");
    return parsedJson;
  } catch (err) {
    await logLLMRun(env, userId, "job_parse", startTime, "error", (err as Error).message);
    throw new AppError("LLM_ERROR", (err as Error).message, 500);
  }
}

export const jobsRoutesTestables = {
  canonicalJobKey,
  normalizeParsedImportItems,
};
