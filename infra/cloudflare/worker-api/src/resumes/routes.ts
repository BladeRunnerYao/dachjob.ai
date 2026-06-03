import { Hono } from "hono";
import { Env } from "../types";
import { authMiddleware } from "../middleware/auth";
import { AppError } from "../middleware/error-handler";
import { generateAndStoreResume } from "../resume-generator";

export const resumesRoutes = new Hono<{ Bindings: Env }>();

// POST /api/resumes/generate - Generate a tailored CV
resumesRoutes.post("/generate", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const body = await c.req.json<{ application_id: string; format?: string; confirmed_skills?: string[] }>();

  if (!body.application_id) {
    throw new AppError("VALIDATION_ERROR", "application_id is required", 400);
  }

  // Get application with job and profile
  const application = await c.env.DB.prepare(
    "SELECT * FROM applications WHERE id = ? AND user_id = ?"
  )
    .bind(body.application_id, userId)
    .first<{ id: string; job_id: string; profile_id: string; match_result: string }>();

  if (!application) throw new AppError("NOT_FOUND", "Application not found", 404);

  const job = await c.env.DB.prepare("SELECT id, title, company, raw_description, parsed_json FROM jobs WHERE id = ?")
    .bind(application.job_id)
    .first<{ id: string; title: string; company: string; raw_description: string; parsed_json: string | null }>();

  const profile = await c.env.DB.prepare("SELECT id, name, raw_cv_md, profile_json FROM candidate_profiles WHERE id = ?")
    .bind(application.profile_id)
    .first<{ id: string; name: string; raw_cv_md: string; profile_json: string | null }>();

  if (!job || !profile) throw new AppError("NOT_FOUND", "Related data not found", 404);

  const artifact = await generateAndStoreResume(c.env, userId, job, profile, {
    applicationId: application.id,
    confirmedSkills: body.confirmed_skills || [],
    matchResult: application.match_result,
    style: body.format || "us",
  });

  // Update application status
  const now = new Date().toISOString();
  await c.env.DB.prepare("UPDATE applications SET status = ?, updated_at = ? WHERE id = ?")
    .bind("completed", now, application.id)
    .run();

  return c.json({
    application_id: application.id,
    status: "completed",
    artifact_id: artifact.id,
  });
});

// GET /api/resumes/:id/html - Download generated resume HTML
resumesRoutes.get("/:id/html", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const artifactId = c.req.param("id");
  const artifact = await c.env.DB.prepare(
    "SELECT id, r2_key, content_type FROM artifacts WHERE id = ? AND user_id = ? AND type = 'cv_html'"
  )
    .bind(artifactId, userId)
    .first<{ id: string; r2_key: string; content_type: string }>();

  if (!artifact) {
    throw new AppError("NOT_FOUND", "Resume artifact not found", 404);
  }

  const object = await c.env.STORAGE.get(artifact.r2_key);
  if (!object) {
    throw new AppError("NOT_FOUND", "Resume HTML not found", 404);
  }

  const headers = new Headers();
  headers.set("Content-Type", artifact.content_type || "text/html; charset=utf-8");
  headers.set("Cache-Control", "private, max-age=3600");
  object.writeHttpMetadata(headers);
  return new Response(object.body, { headers });
});

// GET /api/resumes/:id/pdf - Cloudflare generation currently stores HTML only
resumesRoutes.get("/:id/pdf", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);
  throw new AppError("NOT_FOUND", "PDF not available for this artifact", 404);
});
