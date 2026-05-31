import { Hono } from "hono";
import { Env } from "../types";
import { authMiddleware } from "../middleware/auth";
import { generateId } from "../db/utils";
import { AppError } from "../middleware/error-handler";

export const jobsRoutes = new Hono<{ Bindings: Env }>();

const APPLICATION_JOB_STATUSES = ["applied", "interview", "rejected", "offer"];

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

// POST /api/jobs/import - Import jobs from URLs
jobsRoutes.post("/import", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const body = await c.req.json<{ urls: string[] }>();
  if (!body.urls || body.urls.length === 0) {
    throw new AppError("VALIDATION_ERROR", "Provide at least one job URL", 400);
  }
  if (body.urls.length > 10) {
    throw new AppError("VALIDATION_ERROR", "Import at most 10 job URLs at a time", 400);
  }

  const imported: Record<string, unknown>[] = [];
  const errors: { url: string; error: string }[] = [];

  for (const url of body.urls) {
    try {
      const result = await importSingleJobUrl(c.env, userId, url.trim());
      imported.push(result);
    } catch (err) {
      errors.push({ url, error: (err as Error).message });
    }
  }

  return c.json({ imported, errors }, 201);
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
  }>();

  if (!body.title) {
    throw new AppError("VALIDATION_ERROR", "Title is required", 400);
  }

  const id = generateId();
  const now = new Date().toISOString();

  await c.env.DB.prepare(
    `INSERT INTO jobs (id, user_id, title, company, location, job_url, raw_description, source, employment_type, workplace, salary_text, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      id,
      userId,
      body.title,
      body.company || "",
      body.location || "",
      body.url || "",
      body.raw_jd || "",
      body.source || "",
      body.employment_type || "",
      body.workplace || "",
      body.salary_text || "",
      now,
      now
    )
    .run();

  const job = await c.env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(id).first();
  return c.json(await formatJobResponse(c.env, userId, job!), 201);
});

// GET /api/jobs - List user's jobs
jobsRoutes.get("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const status = c.req.query("status");
  const limit = Math.min(parseInt(c.req.query("limit") || "50", 10), 200);
  const offset = parseInt(c.req.query("offset") || "0", 10);

  let query = "SELECT * FROM jobs WHERE user_id = ?";
  const params: (string | number)[] = [userId];

  if (status && status !== "all") {
    if (status === "saved") {
      query += " AND saved = 1";
    } else if (status === "applied") {
      query += " AND application_status IN (?, ?, ?, ?)";
      params.push(...APPLICATION_JOB_STATUSES);
    } else if (status === "new") {
      query += " AND application_status IS NULL";
    } else {
      query += " AND application_status = ?";
      params.push(status);
    }
  }

  // Count total
  let countQuery = "SELECT COUNT(*) as cnt FROM jobs WHERE user_id = ?";
  const countParams: (string | number)[] = [userId];
  if (status && status !== "all") {
    if (status === "saved") {
      countQuery += " AND saved = 1";
    } else if (status === "applied") {
      countQuery += " AND application_status IN (?, ?, ?, ?)";
      countParams.push(...APPLICATION_JOB_STATUSES);
    } else if (status === "new") {
      countQuery += " AND application_status IS NULL";
    } else {
      countQuery += " AND application_status = ?";
      countParams.push(status);
    }
  }
  const countResult = await c.env.DB.prepare(countQuery).bind(...countParams).first<{ cnt: number }>();
  const total = countResult?.cnt || 0;

  query += " ORDER BY created_at DESC LIMIT ? OFFSET ?";
  params.push(limit, offset);

  const result = await c.env.DB.prepare(query).bind(...params).all();
  const items = await Promise.all((result.results || []).map((job) => formatJobResponse(c.env, userId, job)));
  return c.json({ items, total, limit, offset });
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
    "SELECT id, title, company, raw_description FROM jobs WHERE id = ? AND user_id = ?"
  )
    .bind(jobId, userId)
    .first<{ id: string; title: string; company: string; raw_description: string }>();
  if (!job) throw new AppError("NOT_FOUND", "Job not found", 404);

  const profile = await getLatestProfile(c.env, userId);
  if (!profile) throw new AppError("NOT_FOUND", "Profile not found", 404);

  const artifact = await generateAndStoreResume(c.env, userId, job, profile, body.confirmed_skills || [], body.style || "german");
  return c.json(artifact, 201);
});

// POST /api/jobs/:id/parse - Parse job description (trigger LLM)
jobsRoutes.post("/:id/parse", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const jobId = c.req.param("id");
  const job = await c.env.DB.prepare("SELECT * FROM jobs WHERE id = ? AND user_id = ?")
    .bind(jobId, userId)
    .first<{ id: string; raw_description: string }>();
  if (!job) throw new AppError("NOT_FOUND", "Job not found", 404);

  if (!c.env.LLM_API_KEY) {
    throw new AppError("LLM_NOT_CONFIGURED", "LLM_API_KEY not configured", 500);
  }

  const parsedJson = await parseJobDescription(c.env, job.raw_description);
  const now = new Date().toISOString();
  const parsedTitle = readParsedString(parsedJson, "title");
  const parsedCompany = readParsedString(parsedJson, "company");
  const parsedLocation = readParsedString(parsedJson, "location");
  const parsedEmploymentType = readParsedString(parsedJson, "employment_type");
  const parsedWorkplace = readParsedString(parsedJson, "workplace");
  const parsedSalary = readParsedString(parsedJson, "salary_range") || readParsedString(parsedJson, "salary_text");

  await c.env.DB.prepare(
    `UPDATE jobs
     SET parsed_json = ?,
         title = COALESCE(NULLIF(?, ''), title),
         company = COALESCE(NULLIF(?, ''), company),
         location = COALESCE(NULLIF(?, ''), location),
         employment_type = COALESCE(NULLIF(?, ''), employment_type),
         workplace = COALESCE(NULLIF(?, ''), workplace),
         salary_text = COALESCE(NULLIF(?, ''), salary_text),
         updated_at = ?
     WHERE id = ?`
  )
    .bind(
      JSON.stringify(parsedJson),
      parsedTitle || "",
      parsedCompany || "",
      parsedLocation || "",
      parsedEmploymentType || "",
      parsedWorkplace || "",
      parsedSalary || "",
      now,
      jobId
    )
    .run();

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

  await c.env.DB.prepare("DELETE FROM jobs WHERE id = ?").bind(jobId).run();
  return c.json({ message: "Job deleted" });
});

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function formatJobResponse(env: Env, userId: string, job: Record<string, any>) {
  const match = await getLatestMatchRow(env, userId, String(job.id));
  const matchResponse = match ? formatMatchResponse(match) : null;
  return {
    id: job.id,
    title: job.title,
    company: job.company,
    location: job.location,
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
    created_at: job.created_at,
    updated_at: job.updated_at,
  };
}

function safeJsonParse(value: string | null): Record<string, unknown> | null {
  if (!value) return null;
  try {
    return JSON.parse(value) as Record<string, unknown>;
  } catch {
    return null;
  }
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
    if (!env.LLM_API_KEY) throw new Error("LLM_API_KEY not configured");
    const response = await fetch("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.LLM_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "deepseek-chat",
        messages: [{ role: "user", content: prompt }],
        temperature: 0.2,
        response_format: { type: "json_object" },
      }),
    });
    if (!response.ok) throw new Error(`LLM API error: ${response.status}`);
    const data = (await response.json()) as { choices: { message: { content: string } }[] };
    parsed = JSON.parse(data.choices[0].message.content) as Record<string, unknown>;
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

async function generateAndStoreResume(
  env: Env,
  userId: string,
  job: { id: string; title: string; company: string; raw_description: string },
  profile: ProfileRow,
  confirmedSkills: string[],
  style: string
) {
  const startTime = Date.now();
  const prompt = `Generate a ${style} style, ATS-friendly HTML CV for this candidate and job.

Job: ${job.title} at ${job.company}
Job Description:
${job.raw_description.slice(0, 4000)}

Candidate Profile:
${profile.raw_cv_md.slice(0, 6000)}

Confirmed skills to emphasize: ${confirmedSkills.join(", ") || "none"}

Output only complete HTML.`;

  let html: string;
  try {
    if (!env.LLM_API_KEY) throw new Error("LLM_API_KEY not configured");
    const response = await fetch("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.LLM_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "deepseek-chat",
        messages: [{ role: "user", content: prompt }],
        temperature: 0.4,
      }),
    });
    if (!response.ok) throw new Error(`LLM API error: ${response.status}`);
    const data = (await response.json()) as { choices: { message: { content: string } }[] };
    html = data.choices[0].message.content;
    await logLLMRun(env, userId, "resume_generate", startTime, "success");
  } catch (err) {
    html = fallbackResumeHtml(profile.name, profile.raw_cv_md);
    await logLLMRun(env, userId, "resume_generate", startTime, "error", (err as Error).message);
  }

  const applicationId = await getOrCreateApplication(env, userId, job.id, profile.id);
  const artifactId = generateId();
  const r2Key = `resumes/${userId}/${job.id}/${artifactId}.html`;
  await env.STORAGE.put(r2Key, html, {
    httpMetadata: { contentType: "text/html; charset=utf-8" },
  });

  const now = new Date().toISOString();
  await env.DB.prepare(
    `INSERT INTO artifacts (id, user_id, application_id, type, r2_key, content_type, size_bytes, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(artifactId, userId, applicationId, "cv_html", r2Key, "text/html; charset=utf-8", html.length, now)
    .run();

  return {
    id: artifactId,
    job_id: job.id,
    html_object_key: r2Key,
    pdf_object_key: null,
    provenance_json: [{ source: "cloudflare-worker", style, confirmed_skills: confirmedSkills }],
  };
}

function fallbackResumeHtml(name: string, rawCvMd: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>CV - ${escapeHtml(name)}</title></head>
<body><main><h1>${escapeHtml(name)}</h1><pre>${escapeHtml(rawCvMd.slice(0, 6000))}</pre></main></body>
</html>`;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function logLLMRun(
  env: Env,
  userId: string,
  task: string,
  startTime: number,
  status: "success" | "error",
  errorMessage?: string
) {
  await env.DB.prepare(
    `INSERT INTO llm_runs (id, user_id, provider, model, task, latency_ms, status, error_message, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      generateId(),
      userId,
      "deepseek",
      "deepseek-chat",
      task,
      Date.now() - startTime,
      status,
      errorMessage || null,
      new Date().toISOString()
    )
    .run();
}

async function importSingleJobUrl(env: Env, userId: string, url: string): Promise<Record<string, unknown>> {
  // Fetch the job page
  const response = await fetch(url, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
    },
  });
  if (!response.ok) {
    throw new Error(`Failed to fetch URL: ${response.status}`);
  }

  const html = await response.text();
  const rawText = stripHtml(html).slice(0, 15000);

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
      const urlObj = new URL(url);
      company = urlObj.hostname.replace(/^www\./, "").split(".")[0];
      company = company.charAt(0).toUpperCase() + company.slice(1);
    } catch {
      company = "Unknown";
    }
  }

  const id = generateId();
  const now = new Date().toISOString();

  await env.DB.prepare(
    `INSERT INTO jobs (id, user_id, title, company, location, job_url, raw_description, source, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(id, userId, title, company, "", url, rawText, "url_import", now, now)
    .run();

  const job = await env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(id).first();
  return formatJobResponse(env, userId, job!);
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

async function parseJobDescription(env: Env, rawDescription: string): Promise<Record<string, unknown>> {
  const response = await fetch("https://api.deepseek.com/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.LLM_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "deepseek-chat",
      messages: [
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
      temperature: 0.2,
      response_format: { type: "json_object" },
    }),
  });

  if (!response.ok) {
    throw new AppError("LLM_ERROR", `LLM API error: ${response.status}`, 500);
  }

  const data = (await response.json()) as { choices: { message: { content: string } }[] };
  return JSON.parse(data.choices[0].message.content);
}
