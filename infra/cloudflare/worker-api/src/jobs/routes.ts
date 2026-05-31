import { Hono } from "hono";
import { Env } from "../types";
import { authMiddleware } from "../middleware/auth";
import { generateId } from "../db/utils";
import { AppError } from "../middleware/error-handler";

export const jobsRoutes = new Hono<{ Bindings: Env }>();

// POST /api/jobs - Create a job
jobsRoutes.post("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const body = await c.req.json<{
    title: string;
    company?: string;
    location?: string;
    job_url?: string;
    raw_description?: string;
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
      body.job_url || "",
      body.raw_description || "",
      body.source || "",
      body.employment_type || "",
      body.workplace || "",
      body.salary_text || "",
      now,
      now
    )
    .run();

  const job = await c.env.DB.prepare("SELECT * FROM jobs WHERE id = ?").bind(id).first();
  return c.json(job, 201);
});

// GET /api/jobs - List user's jobs
jobsRoutes.get("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const status = c.req.query("status");
  const saved = c.req.query("saved");
  const limit = Math.min(parseInt(c.req.query("limit") || "50", 10), 100);
  const offset = parseInt(c.req.query("offset") || "0", 10);

  let query = "SELECT * FROM jobs WHERE user_id = ?";
  const params: (string | number)[] = [userId];

  if (status) {
    query += " AND status = ?";
    params.push(status);
  }
  if (saved === "true") {
    query += " AND saved = 1";
  }

  query += " ORDER BY created_at DESC LIMIT ? OFFSET ?";
  params.push(limit, offset);

  const result = await c.env.DB.prepare(query).bind(...params).all();
  return c.json({ items: result.results, total: result.results.length });
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

  return c.json(job);
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
