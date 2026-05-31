import { Hono } from "hono";
import { Env } from "../types";
import { authMiddleware } from "../middleware/auth";
import { generateId } from "../db/utils";
import { AppError } from "../middleware/error-handler";
import { callDeepSeekChat, logLLMRun } from "../llm";

export const matchingRoutes = new Hono<{ Bindings: Env }>();

// POST /api/match - Match a profile against a job
matchingRoutes.post("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const body = await c.req.json<{ job_id: string; profile_id: string }>();

  if (!body.job_id || !body.profile_id) {
    throw new AppError("VALIDATION_ERROR", "job_id and profile_id are required", 400);
  }

  // Verify ownership
  const job = await c.env.DB.prepare("SELECT id, title, raw_description FROM jobs WHERE id = ? AND user_id = ?")
    .bind(body.job_id, userId)
    .first<{ id: string; title: string; raw_description: string }>();
  if (!job) throw new AppError("NOT_FOUND", "Job not found", 404);

  const profile = await c.env.DB.prepare(
    "SELECT id, name, raw_cv_md, profile_json FROM candidate_profiles WHERE id = ? AND user_id = ?"
  )
    .bind(body.profile_id, userId)
    .first<{ id: string; name: string; raw_cv_md: string; profile_json: string | null }>();
  if (!profile) throw new AppError("NOT_FOUND", "Profile not found", 404);

  // Call LLM for matching
  const matchResult = await performMatch(c.env, userId, job, profile);

  // Store the application
  const applicationId = generateId();
  const now = new Date().toISOString();

  await c.env.DB.prepare(
    `INSERT INTO applications (id, user_id, job_id, profile_id, status, match_score, match_result, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(
      applicationId,
      userId,
      body.job_id,
      body.profile_id,
      "matched",
      matchResult.match_score,
      JSON.stringify(matchResult),
      now,
      now
    )
    .run();

  return c.json({
    application_id: applicationId,
    match_score: matchResult.match_score,
    strengths: matchResult.strengths,
    gaps: matchResult.gaps,
    recommendations: matchResult.recommendations,
  });
});

interface MatchResult {
  match_score: number;
  strengths: string[];
  gaps: string[];
  recommendations: string[];
}

async function performMatch(
  env: Env,
  userId: string,
  job: { title: string; raw_description: string },
  profile: { name: string; raw_cv_md: string; profile_json: string | null }
): Promise<MatchResult> {
  const prompt = `You are an expert job matching assistant. Analyze the fit between this candidate profile and job description.

Job Title: ${job.title}
Job Description:
${job.raw_description.slice(0, 3000)}

Candidate Profile:
${profile.raw_cv_md.slice(0, 3000)}

Respond in JSON format:
{
  "match_score": <0-100>,
  "strengths": ["strength1", "strength2", ...],
  "gaps": ["gap1", "gap2", ...],
  "recommendations": ["recommendation1", "recommendation2", ...]
}`;

  const startTime = Date.now();
  let result: MatchResult;

  try {
    const response = await callDeepSeekChat(env, [{ role: "user", content: prompt }], {
      temperature: 0.3,
      json: true,
    });
    result = JSON.parse(response);
    await logLLMRun(env, userId, "matching", startTime, "success");
  } catch (err) {
    await logLLMRun(env, userId, "matching", startTime, "error", (err as Error).message);

    // Fallback: return a basic result
    result = {
      match_score: 50,
      strengths: ["Unable to analyze - LLM unavailable"],
      gaps: ["LLM service error"],
      recommendations: ["Please try again later"],
    };
  }

  return result;
}
