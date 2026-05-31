import { Hono } from "hono";
import { Env } from "../types";
import { authMiddleware } from "../middleware/auth";
import { generateId } from "../db/utils";
import { AppError } from "../middleware/error-handler";

export const resumesRoutes = new Hono<{ Bindings: Env }>();

// POST /api/resumes/generate - Generate a tailored CV
resumesRoutes.post("/generate", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const body = await c.req.json<{ application_id: string; format?: string }>();

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

  const job = await c.env.DB.prepare("SELECT * FROM jobs WHERE id = ?")
    .bind(application.job_id)
    .first<{ title: string; company: string; raw_description: string }>();

  const profile = await c.env.DB.prepare("SELECT * FROM candidate_profiles WHERE id = ?")
    .bind(application.profile_id)
    .first<{ name: string; raw_cv_md: string; profile_json: string | null }>();

  if (!job || !profile) throw new AppError("NOT_FOUND", "Related data not found", 404);

  // Generate CV using LLM
  const cvHtml = await generateCV(c.env, job, profile, application.match_result);

  // Store in R2
  const r2Key = `applications/${application.id}/cv.html`;
  await c.env.STORAGE.put(r2Key, cvHtml, {
    httpMetadata: { contentType: "text/html" },
  });

  // Create artifact record
  const artifactId = generateId();
  const now = new Date().toISOString();

  await c.env.DB.prepare(
    `INSERT INTO artifacts (id, user_id, application_id, type, r2_key, content_type, size_bytes, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(artifactId, userId, application.id, "cv_html", r2Key, "text/html", cvHtml.length, now)
    .run();

  // Update application status
  await c.env.DB.prepare("UPDATE applications SET status = ?, updated_at = ? WHERE id = ?")
    .bind("completed", now, application.id)
    .run();

  return c.json({
    application_id: application.id,
    status: "completed",
    artifact_id: artifactId,
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

async function generateCV(
  env: Env,
  job: { title: string; company: string; raw_description: string },
  profile: { name: string; raw_cv_md: string; profile_json: string | null },
  matchResult: string | null
): Promise<string> {
  const prompt = `You are an expert CV writer. Generate a tailored HTML CV for the following candidate applying to the specified job.

Job: ${job.title} at ${job.company}
Job Description: ${job.raw_description.slice(0, 2000)}

Candidate Profile:
${profile.raw_cv_md.slice(0, 3000)}

${matchResult ? `Match Analysis: ${matchResult.slice(0, 1000)}` : ""}

Generate a professional, ATS-friendly HTML CV that highlights relevant experience for this role.
Output ONLY the HTML content (starting with <!DOCTYPE html>), no markdown fences.`;

  const startTime = Date.now();

  try {
    if (!env.LLM_API_KEY) {
      return generateFallbackCV(profile.name, profile.raw_cv_md);
    }

    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.LLM_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "deepseek/deepseek-chat-v3-0324:free",
        messages: [{ role: "user", content: prompt }],
        temperature: 0.4,
      }),
    });

    if (!response.ok) throw new Error(`LLM error: ${response.status}`);

    const data = (await response.json()) as {
      choices: { message: { content: string } }[];
    };
    const content = data.choices[0].message.content;
    const latencyMs = Date.now() - startTime;

    await env.DB.prepare(
      `INSERT INTO llm_runs (id, provider, model, task, latency_ms, status, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?)`
    )
      .bind(generateId(), "openrouter", "default", "cv_generation", latencyMs, "success", new Date().toISOString())
      .run();

    return content;
  } catch (err) {
    const latencyMs = Date.now() - startTime;
    await env.DB.prepare(
      `INSERT INTO llm_runs (id, provider, model, task, latency_ms, status, error_message, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    )
      .bind(generateId(), "openrouter", "default", "cv_generation", latencyMs, "error", (err as Error).message, new Date().toISOString())
      .run();

    return generateFallbackCV(profile.name, profile.raw_cv_md);
  }
}

function generateFallbackCV(name: string, rawCvMd: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>CV - ${name}</title>
<style>body{font-family:system-ui,sans-serif;max-width:800px;margin:0 auto;padding:2rem;line-height:1.6}h1{color:#1a1a2e}</style>
</head>
<body>
<h1>${name}</h1>
<pre>${rawCvMd.slice(0, 5000)}</pre>
</body>
</html>`;
}
