import { Hono } from "hono";
import { Env } from "../types";
import { authMiddleware } from "../middleware/auth";
import { generateId } from "../db/utils";
import { AppError } from "../middleware/error-handler";

export const applicationsRoutes = new Hono<{ Bindings: Env }>();

const VALID_STATUSES = ["draft", "applied", "interview", "offer", "rejected", "withdrawn"];

interface ApplicationRow {
  id: string;
  user_id: string;
  job_id: string;
  profile_id: string;
  status: string;
  match_score: number | null;
  match_result: string | null;
  notes?: string;
  created_at: string;
  updated_at: string;
  job_title?: string | null;
  company?: string | null;
  job_application_status?: string | null;
}

function formatApplicationResponse(app: ApplicationRow) {
  const effectiveStatus =
    app.status === "draft" && app.job_application_status ? app.job_application_status : app.status;
  return {
    id: app.id,
    job_id: app.job_id,
    job_title: app.job_title || "",
    company: app.company || "",
    status: displayStatus(effectiveStatus),
    score: app.match_score,
    match_score: app.match_score,
    notes: app.notes || null,
    created_at: app.created_at,
    updated_at: app.updated_at,
  };
}

function normalizeStatus(status: string | undefined): string {
  const normalized = (status || "draft").trim().toLowerCase();
  if (!VALID_STATUSES.includes(normalized)) {
    throw new AppError("VALIDATION_ERROR", `Invalid status: ${status}. Must be one of ${VALID_STATUSES.join(", ")}`, 422);
  }
  return normalized;
}

function displayStatus(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

// GET /api/applications - List user's applications
applicationsRoutes.get("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json([]);

  const result = await c.env.DB.prepare(
    `SELECT
       applications.*,
       jobs.title AS job_title,
       jobs.company AS company,
       jobs.application_status AS job_application_status
     FROM applications
     LEFT JOIN jobs ON jobs.id = applications.job_id AND jobs.user_id = applications.user_id
     WHERE applications.user_id = ?
     ORDER BY applications.created_at DESC`
  )
    .bind(userId)
    .all<ApplicationRow>();

  return c.json((result.results || []).map(formatApplicationResponse));
});

// POST /api/applications - Create application
applicationsRoutes.post("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const body = await c.req.json<{ job_id: string; status?: string; notes?: string }>();
  if (!body.job_id) {
    throw new AppError("VALIDATION_ERROR", "job_id is required", 400);
  }

  const status = normalizeStatus(body.status);

  // Get user's profile (if exists)
  const profile = await c.env.DB.prepare(
    "SELECT id FROM candidate_profiles WHERE user_id = ? ORDER BY created_at DESC LIMIT 1"
  )
    .bind(userId)
    .first<{ id: string }>();

  const id = generateId();
  const now = new Date().toISOString();
  const profileId = profile?.id || "";

  await c.env.DB.prepare(
    `INSERT INTO applications (id, user_id, job_id, profile_id, status, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(id, userId, body.job_id, profileId, status, now, now)
    .run();

  if (status !== "draft") {
    await c.env.DB.prepare(
      "UPDATE jobs SET application_status = ?, updated_at = ? WHERE id = ? AND user_id = ?"
    )
      .bind(status, now, body.job_id, userId)
      .run();
  }

  const app = await c.env.DB.prepare(
    `SELECT applications.*, jobs.title AS job_title, jobs.company AS company, jobs.application_status AS job_application_status
     FROM applications
     LEFT JOIN jobs ON jobs.id = applications.job_id AND jobs.user_id = applications.user_id
     WHERE applications.id = ?`
  )
    .bind(id)
    .first<ApplicationRow>();

  return c.json(formatApplicationResponse(app!), 201);
});

// PATCH /api/applications/:id - Update application
applicationsRoutes.patch("/:id", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const applicationId = c.req.param("id");
  const body = await c.req.json<{ status?: string; notes?: string }>();

  const app = await c.env.DB.prepare(
    "SELECT * FROM applications WHERE id = ? AND user_id = ?"
  )
    .bind(applicationId, userId)
    .first<ApplicationRow>();

  if (!app) {
    throw new AppError("NOT_FOUND", "Application not found", 404);
  }

  const normalizedStatus = body.status ? normalizeStatus(body.status) : undefined;

  const now = new Date().toISOString();
  const updates: string[] = ["updated_at = ?"];
  const values: (string | number)[] = [now];

  if (normalizedStatus) {
    updates.push("status = ?");
    values.push(normalizedStatus);
  }
  if (body.notes !== undefined) {
    updates.push("notes = ?");
    values.push(body.notes);
  }

  values.push(applicationId);
  await c.env.DB.prepare(`UPDATE applications SET ${updates.join(", ")} WHERE id = ?`)
    .bind(...values)
    .run();

  // Update job application_status if status changed
  if (normalizedStatus && app.job_id) {
    await c.env.DB.prepare(
      "UPDATE jobs SET application_status = ?, updated_at = ? WHERE id = ? AND user_id = ?"
    )
      .bind(normalizedStatus === "draft" ? null : normalizedStatus, now, app.job_id, userId)
      .run();
  }

  const updated = await c.env.DB.prepare(
    `SELECT applications.*, jobs.title AS job_title, jobs.company AS company, jobs.application_status AS job_application_status
     FROM applications
     LEFT JOIN jobs ON jobs.id = applications.job_id AND jobs.user_id = applications.user_id
     WHERE applications.id = ?`
  )
    .bind(applicationId)
    .first<ApplicationRow>();

  return c.json(formatApplicationResponse(updated!));
});

// GET /api/applications/:id
applicationsRoutes.get("/:id", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const applicationId = c.req.param("id");
  const app = await c.env.DB.prepare(
    `SELECT applications.*, jobs.title AS job_title, jobs.company AS company, jobs.application_status AS job_application_status
     FROM applications
     LEFT JOIN jobs ON jobs.id = applications.job_id AND jobs.user_id = applications.user_id
     WHERE applications.id = ? AND applications.user_id = ?`
  )
    .bind(applicationId, userId)
    .first<ApplicationRow>();

  if (!app) {
    throw new AppError("NOT_FOUND", "Application not found", 404);
  }

  return c.json(formatApplicationResponse(app));
});
