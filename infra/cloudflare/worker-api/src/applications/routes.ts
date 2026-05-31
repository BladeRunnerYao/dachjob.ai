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
}

function formatApplicationResponse(app: ApplicationRow) {
  return {
    id: app.id,
    job_id: app.job_id,
    status: app.status,
    match_score: app.match_score,
    notes: app.notes || null,
    created_at: app.created_at,
    updated_at: app.updated_at,
  };
}

// GET /api/applications - List user's applications
applicationsRoutes.get("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json([]);

  const result = await c.env.DB.prepare(
    "SELECT * FROM applications WHERE user_id = ? ORDER BY created_at DESC"
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

  const status = body.status || "draft";
  if (!VALID_STATUSES.includes(status)) {
    throw new AppError("VALIDATION_ERROR", `Invalid status: ${status}. Must be one of ${VALID_STATUSES.join(", ")}`, 422);
  }

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

  // Update job application_status
  await c.env.DB.prepare(
    "UPDATE jobs SET application_status = ?, updated_at = ? WHERE id = ? AND user_id = ?"
  )
    .bind(status, now, body.job_id, userId)
    .run();

  const app = await c.env.DB.prepare("SELECT * FROM applications WHERE id = ?")
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

  if (body.status && !VALID_STATUSES.includes(body.status)) {
    throw new AppError("VALIDATION_ERROR", `Invalid status: ${body.status}`, 422);
  }

  const now = new Date().toISOString();
  const updates: string[] = ["updated_at = ?"];
  const values: (string | number)[] = [now];

  if (body.status) {
    updates.push("status = ?");
    values.push(body.status);
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
  if (body.status && app.job_id) {
    await c.env.DB.prepare(
      "UPDATE jobs SET application_status = ?, updated_at = ? WHERE id = ?"
    )
      .bind(body.status, now, app.job_id)
      .run();
  }

  const updated = await c.env.DB.prepare("SELECT * FROM applications WHERE id = ?")
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
    "SELECT * FROM applications WHERE id = ? AND user_id = ?"
  )
    .bind(applicationId, userId)
    .first<ApplicationRow>();

  if (!app) {
    throw new AppError("NOT_FOUND", "Application not found", 404);
  }

  return c.json(formatApplicationResponse(app));
});
