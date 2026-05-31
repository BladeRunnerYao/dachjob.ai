import { Hono } from "hono";
import { Env } from "../types";
import { authMiddleware } from "../middleware/auth";
import { generateId } from "../db/utils";
import { AppError } from "../middleware/error-handler";

export const profilesRoutes = new Hono<{ Bindings: Env }>();

// POST /api/profiles - Create a profile
profilesRoutes.post("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const body = await c.req.json<{
    name: string;
    headline?: string;
    summary?: string;
    raw_cv_md?: string;
    profile_json?: Record<string, unknown>;
  }>();

  if (!body.name) {
    throw new AppError("VALIDATION_ERROR", "Name is required", 400);
  }

  const id = generateId();
  const now = new Date().toISOString();

  await c.env.DB.prepare(
    `INSERT INTO candidate_profiles (id, user_id, name, headline, summary, raw_cv_md, profile_json, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      id,
      userId,
      body.name,
      body.headline || "",
      body.summary || "",
      body.raw_cv_md || "",
      body.profile_json ? JSON.stringify(body.profile_json) : null,
      now,
      now
    )
    .run();

  const profile = await c.env.DB.prepare("SELECT * FROM candidate_profiles WHERE id = ?")
    .bind(id)
    .first();
  return c.json(profile, 201);
});

// GET /api/profiles - List user's profiles
profilesRoutes.get("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const result = await c.env.DB.prepare(
    "SELECT * FROM candidate_profiles WHERE user_id = ? ORDER BY created_at DESC"
  )
    .bind(userId)
    .all();

  return c.json({ items: result.results });
});

// GET /api/profiles/:id
profilesRoutes.get("/:id", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const profileId = c.req.param("id");
  const profile = await c.env.DB.prepare(
    "SELECT * FROM candidate_profiles WHERE id = ? AND user_id = ?"
  )
    .bind(profileId, userId)
    .first();

  if (!profile) {
    throw new AppError("NOT_FOUND", "Profile not found", 404);
  }

  return c.json(profile);
});

// DELETE /api/profiles/:id
profilesRoutes.delete("/:id", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const profileId = c.req.param("id");
  const profile = await c.env.DB.prepare(
    "SELECT id FROM candidate_profiles WHERE id = ? AND user_id = ?"
  )
    .bind(profileId, userId)
    .first();

  if (!profile) {
    throw new AppError("NOT_FOUND", "Profile not found", 404);
  }

  await c.env.DB.prepare("DELETE FROM candidate_profiles WHERE id = ?").bind(profileId).run();
  return c.json({ message: "Profile deleted" });
});
