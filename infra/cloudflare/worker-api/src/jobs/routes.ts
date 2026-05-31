import { Hono } from "hono";
import { Env } from "../types";
import { authMiddleware } from "../middleware/auth";
import { generateId } from "../db/utils";
import { AppError } from "../middleware/error-handler";

export const jobsRoutes = new Hono<{ Bindings: Env }>();

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
  return c.json(formatJobResponse(job!), 201);
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
    } else {
      query += " AND (status = ? OR application_status = ?)";
      params.push(status, status);
    }
  }

  // Count total
  let countQuery = "SELECT COUNT(*) as cnt FROM jobs WHERE user_id = ?";
  const countParams: (string | number)[] = [userId];
  if (status && status !== "all") {
    if (status === "saved") {
      countQuery += " AND saved = 1";
    } else {
      countQuery += " AND (status = ? OR application_status = ?)";
      countParams.push(status, status);
    }
  }
  const countResult = await c.env.DB.prepare(countQuery).bind(...countParams).first<{ cnt: number }>();
  const total = countResult?.cnt || 0;

  query += " ORDER BY created_at DESC LIMIT ? OFFSET ?";
  params.push(limit, offset);

  const result = await c.env.DB.prepare(query).bind(...params).all();
  const items = (result.results || []).map(formatJobResponse);
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
  const values: (string | number)[] = [now];

  if (body.status !== undefined && body.status !== "saved") {
    updates.push("status = ?");
    values.push(body.status);
  }
  if (body.saved !== undefined) {
    updates.push("saved = ?");
    values.push(body.saved ? 1 : 0);
  }
  if (body.status === "saved") {
    updates.push("saved = 1");
  }

  values.push(jobId);
  await c.env.DB.prepare(`UPDATE jobs SET ${updates.join(", ")} WHERE id = ?`).bind(...values).run();

  const updated = await c.env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(jobId).first();
  return c.json(formatJobResponse(updated!));
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

  await c.env.DB.prepare("UPDATE jobs SET parsed_json = ?, updated_at = ? WHERE id = ?")
    .bind(JSON.stringify(parsedJson), now, jobId)
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

  return c.json(formatJobResponse(job));
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
function formatJobResponse(job: Record<string, any>) {
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
    parsed_json: job.parsed_json ? JSON.parse(job.parsed_json as string) : null,
    status: job.status,
    saved: Boolean(job.saved),
    application_status: job.application_status,
    created_at: job.created_at,
    updated_at: job.updated_at,
  };
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
  return formatJobResponse(job!);
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
  "requirements": ["req1", "req2"],
  "responsibilities": ["resp1", "resp2"],
  "nice_to_have": ["nice1", "nice2"],
  "benefits": ["benefit1"],
  "salary": "salary range if mentioned"
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
