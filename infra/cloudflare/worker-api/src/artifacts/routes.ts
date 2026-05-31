import { Hono } from "hono";
import { Env } from "../types";
import { authMiddleware } from "../middleware/auth";
import { generateId } from "../db/utils";
import { AppError } from "../middleware/error-handler";

export const artifactsRoutes = new Hono<{ Bindings: Env }>();

// GET /api/artifacts/:id - Download an artifact
artifactsRoutes.get("/:id", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const artifactId = c.req.param("id");
  const artifact = await c.env.DB.prepare(
    "SELECT * FROM artifacts WHERE id = ? AND user_id = ?"
  )
    .bind(artifactId, userId)
    .first<{ id: string; r2_key: string; content_type: string; type: string }>();

  if (!artifact) {
    throw new AppError("NOT_FOUND", "Artifact not found", 404);
  }

  const object = await c.env.STORAGE.get(artifact.r2_key);
  if (!object) {
    throw new AppError("NOT_FOUND", "File not found in storage", 404);
  }

  const headers = new Headers();
  headers.set("Content-Type", artifact.content_type);
  headers.set("Cache-Control", "private, max-age=3600");
  object.writeHttpMetadata(headers);

  return new Response(object.body, { headers });
});

// POST /api/uploads - Upload a file
artifactsRoutes.post("/upload", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const contentType = c.req.header("Content-Type") || "";

  if (contentType.includes("multipart/form-data")) {
    const formData = await c.req.formData();
    const file = formData.get("file") as File | null;
    const type = (formData.get("type") as string) || "upload";
    const applicationId = formData.get("application_id") as string | null;

    if (!file) {
      throw new AppError("VALIDATION_ERROR", "No file provided", 400);
    }

    // Enforce 10MB limit (free tier friendly)
    if (file.size > 10 * 1024 * 1024) {
      throw new AppError("VALIDATION_ERROR", "File too large (max 10MB)", 400);
    }

    const artifactId = generateId();
    const ext = file.name.split(".").pop() || "bin";
    const r2Key = `uploads/${userId}/${artifactId}.${ext}`;

    await c.env.STORAGE.put(r2Key, file.stream(), {
      httpMetadata: { contentType: file.type },
    });

    const now = new Date().toISOString();
    await c.env.DB.prepare(
      `INSERT INTO artifacts (id, user_id, application_id, type, r2_key, content_type, size_bytes, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    )
      .bind(artifactId, userId, applicationId, type, r2Key, file.type, file.size, now)
      .run();

    return c.json({ id: artifactId, r2_key: r2Key, size_bytes: file.size }, 201);
  }

  throw new AppError("VALIDATION_ERROR", "Expected multipart/form-data", 400);
});

// GET /api/artifacts - List user's artifacts
artifactsRoutes.get("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const applicationId = c.req.query("application_id");
  let query = "SELECT id, application_id, type, content_type, size_bytes, created_at FROM artifacts WHERE user_id = ?";
  const params: string[] = [userId];

  if (applicationId) {
    query += " AND application_id = ?";
    params.push(applicationId);
  }

  query += " ORDER BY created_at DESC LIMIT 100";

  const result = await c.env.DB.prepare(query).bind(...params).all();
  return c.json({ items: result.results });
});

// DELETE /api/artifacts/:id
artifactsRoutes.delete("/:id", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const artifactId = c.req.param("id");
  const artifact = await c.env.DB.prepare(
    "SELECT id, r2_key FROM artifacts WHERE id = ? AND user_id = ?"
  )
    .bind(artifactId, userId)
    .first<{ id: string; r2_key: string }>();

  if (!artifact) {
    throw new AppError("NOT_FOUND", "Artifact not found", 404);
  }

  // Delete from R2
  await c.env.STORAGE.delete(artifact.r2_key);

  // Delete from D1
  await c.env.DB.prepare("DELETE FROM artifacts WHERE id = ?").bind(artifactId).run();

  return c.json({ message: "Artifact deleted" });
});
