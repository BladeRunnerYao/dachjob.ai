import { Hono } from "hono";
import { Env } from "../types";
import { authMiddleware } from "../middleware/auth";
import { generateId } from "../db/utils";
import { AppError } from "../middleware/error-handler";

export const profilesRoutes = new Hono<{ Bindings: Env }>();

interface ProfileRow {
  id: string;
  user_id: string;
  name: string;
  headline: string;
  summary: string;
  raw_cv_md: string;
  profile_json: string | null;
  created_at: string;
  updated_at: string;
}

function formatProfileResponse(profile: ProfileRow) {
  return {
    id: profile.id,
    tenant_id: profile.user_id,
    full_name: profile.name,
    headline: profile.headline,
    location: null,
    timezone: null,
    raw_cv_md: profile.raw_cv_md,
    profile_json: profile.profile_json ? JSON.parse(profile.profile_json) : null,
    created_at: profile.created_at,
    updated_at: profile.updated_at,
  };
}

// GET /api/profile - Get current user's profile
profilesRoutes.get("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json(null);

  const profile = await c.env.DB.prepare(
    "SELECT * FROM candidate_profiles WHERE user_id = ? ORDER BY created_at DESC LIMIT 1"
  )
    .bind(userId)
    .first<ProfileRow>();

  if (!profile) return c.json(null);
  return c.json(formatProfileResponse(profile));
});

// POST /api/profile/cv - Upload/update CV markdown
profilesRoutes.post("/cv", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const body = await c.req.json<{ raw_cv_md: string }>();
  if (!body.raw_cv_md) {
    throw new AppError("VALIDATION_ERROR", "raw_cv_md is required", 400);
  }

  const name = extractNameFromMd(body.raw_cv_md) || "Unknown";
  const headline = extractHeadlineFromMd(body.raw_cv_md) || "Unknown";
  const now = new Date().toISOString();

  const existing = await c.env.DB.prepare(
    "SELECT id FROM candidate_profiles WHERE user_id = ? ORDER BY created_at DESC LIMIT 1"
  )
    .bind(userId)
    .first<{ id: string }>();

  if (existing) {
    await c.env.DB.prepare(
      `UPDATE candidate_profiles SET name = ?, headline = ?, raw_cv_md = ?, updated_at = ? WHERE id = ?`
    )
      .bind(name, headline, body.raw_cv_md, now, existing.id)
      .run();
  } else {
    const id = generateId();
    await c.env.DB.prepare(
      `INSERT INTO candidate_profiles (id, user_id, name, headline, summary, raw_cv_md, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
    )
      .bind(id, userId, name, headline, "", body.raw_cv_md, now, now)
      .run();
  }

  const profile = await c.env.DB.prepare(
    "SELECT * FROM candidate_profiles WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1"
  )
    .bind(userId)
    .first<ProfileRow>();

  return c.json(formatProfileResponse(profile!));
});

// POST /api/profile/import-url - Import profile from URL
profilesRoutes.post("/import-url", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const body = await c.req.json<{ url: string }>();
  if (!body.url) {
    throw new AppError("VALIDATION_ERROR", "url is required", 400);
  }

  // Fetch the URL content
  const response = await fetch(body.url, {
    headers: {
      "User-Agent":
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
    },
  });
  if (!response.ok) {
    throw new AppError("FETCH_ERROR", `Failed to fetch URL: ${response.status}`, 400);
  }

  const htmlText = await response.text();
  const rawText = stripHtml(htmlText).slice(0, 30000);

  // Use LLM to convert to CV markdown
  const cvMd = await convertToCvMarkdown(c.env, userId, rawText, body.url, "profile_import_url");

  const name = extractNameFromMd(cvMd) || "Unknown";
  const headline = extractHeadlineFromMd(cvMd) || "Unknown";
  const now = new Date().toISOString();

  const existing = await c.env.DB.prepare(
    "SELECT id FROM candidate_profiles WHERE user_id = ? ORDER BY created_at DESC LIMIT 1"
  )
    .bind(userId)
    .first<{ id: string }>();

  if (existing) {
    await c.env.DB.prepare(
      `UPDATE candidate_profiles SET name = ?, headline = ?, raw_cv_md = ?, profile_json = ?, updated_at = ? WHERE id = ?`
    )
      .bind(name, headline, cvMd, JSON.stringify({ source_url: body.url }), now, existing.id)
      .run();
  } else {
    const id = generateId();
    await c.env.DB.prepare(
      `INSERT INTO candidate_profiles (id, user_id, name, headline, summary, raw_cv_md, profile_json, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
    )
      .bind(id, userId, name, headline, "", cvMd, JSON.stringify({ source_url: body.url }), now, now)
      .run();
  }

  const profile = await c.env.DB.prepare(
    "SELECT * FROM candidate_profiles WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1"
  )
    .bind(userId)
    .first<ProfileRow>();

  return c.json(formatProfileResponse(profile!));
});

// POST /api/profile/import-pdf - Import profile from PDF upload
profilesRoutes.post("/import-pdf", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const formData = await c.req.formData();
  const file = formData.get("file") as unknown as { name: string; arrayBuffer(): Promise<ArrayBuffer> } | null;
  if (!file || typeof file === "string") {
    throw new AppError("VALIDATION_ERROR", "PDF file is required", 400);
  }
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    throw new AppError("VALIDATION_ERROR", "Only PDF files are supported", 400);
  }

  // Read the file as text (basic extraction — full PDF parsing not available in Workers)
  const arrayBuffer = await file.arrayBuffer();
  const rawText = extractTextFromPdfBasic(new Uint8Array(arrayBuffer));

  const cvMd = await convertToCvMarkdown(c.env, userId, rawText, file.name, "profile_import_pdf");

  const name = extractNameFromMd(cvMd) || "Unknown";
  const headline = extractHeadlineFromMd(cvMd) || "Unknown";
  const now = new Date().toISOString();

  const existing = await c.env.DB.prepare(
    "SELECT id FROM candidate_profiles WHERE user_id = ? ORDER BY created_at DESC LIMIT 1"
  )
    .bind(userId)
    .first<{ id: string }>();

  if (existing) {
    await c.env.DB.prepare(
      `UPDATE candidate_profiles SET name = ?, headline = ?, raw_cv_md = ?, profile_json = ?, updated_at = ? WHERE id = ?`
    )
      .bind(name, headline, cvMd, JSON.stringify({ source_pdf: file.name }), now, existing.id)
      .run();
  } else {
    const id = generateId();
    await c.env.DB.prepare(
      `INSERT INTO candidate_profiles (id, user_id, name, headline, summary, raw_cv_md, profile_json, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
    )
      .bind(id, userId, name, headline, "", cvMd, JSON.stringify({ source_pdf: file.name }), now, now)
      .run();
  }

  const profile = await c.env.DB.prepare(
    "SELECT * FROM candidate_profiles WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1"
  )
    .bind(userId)
    .first<ProfileRow>();

  return c.json(formatProfileResponse(profile!));
});

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

function extractNameFromMd(md: string): string | null {
  const match = md.match(/^#\s+(.+)$/m);
  return match ? match[1].trim() : null;
}

function extractHeadlineFromMd(md: string): string | null {
  const sectionMatch = md.match(/^##\s+Profile(?:\s*\/\s*Summary)?\s*\n+(.+?)(?:\n+##\s|\Z)/ms);
  if (sectionMatch) {
    const firstSentence = sectionMatch[1].trim().split(".")[0].trim();
    return firstSentence ? firstSentence.slice(0, 200) : null;
  }
  return null;
}

function extractTextFromPdfBasic(bytes: Uint8Array): string {
  // Basic text extraction from PDF binary — extract ASCII printable text streams
  const decoder = new TextDecoder("latin1");
  const raw = decoder.decode(bytes);
  const textChunks: string[] = [];
  const streamRegex = /stream\s*\n([\s\S]*?)endstream/g;
  let match;
  while ((match = streamRegex.exec(raw)) !== null) {
    const content = match[1];
    // Extract text between parentheses (PDF text operators)
    const textOps = content.match(/\(([^)]*)\)/g);
    if (textOps) {
      for (const op of textOps) {
        const text = op.slice(1, -1).replace(/\\n/g, "\n").replace(/\\\\/g, "\\");
        if (/[a-zA-Z]/.test(text)) {
          textChunks.push(text);
        }
      }
    }
  }
  return textChunks.join(" ").slice(0, 30000) || "Unable to extract text from PDF";
}

async function convertToCvMarkdown(
  env: Env,
  userId: string,
  rawText: string,
  sourceLabel: string,
  task: string
): Promise<string> {
  const startTime = Date.now();
  if (!env.LLM_API_KEY) {
    await logLLMRun(env, userId, task, startTime, "error", "LLM_API_KEY not configured");
    throw new AppError("LLM_NOT_CONFIGURED", "LLM_API_KEY not configured", 500);
  }

  const systemPrompt = `You are a CV/resume extraction agent. Given raw text extracted from a personal website, LinkedIn profile, or PDF resume, extract all relevant information and format it into a clean, structured Markdown CV.

Extract and organize the following sections:

# Full Name

## Profile / Summary
Brief professional summary (2-3 sentences)

## Experience
For each position: **Job Title — Company (Start Date – End Date)**
- Bullet points describing responsibilities and achievements

## Skills
Comma-separated list of technical and professional skills

## Education
For each degree: **Degree — Institution (Year)**

## Certifications (if any)

## Languages (if any)

Preserve ALL original information. Do NOT invent or fabricate any details.
Output ONLY the Markdown content — no additional commentary, no JSON wrapper, no code fences.`;

  try {
    const response = await fetch("https://api.deepseek.com/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.LLM_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "deepseek-chat",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: `Raw text to extract from (${sourceLabel}):\n\n${rawText}` },
        ],
        temperature: 0.3,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      const message = `LLM API error: ${response.status} - ${errorText}`;
      await logLLMRun(env, userId, task, startTime, "error", message);
      throw new AppError("LLM_ERROR", message, 500);
    }

    const data = (await response.json()) as {
      choices: { message: { content: string } }[];
    };
    await logLLMRun(env, userId, task, startTime, "success");
    return data.choices[0].message.content.trim();
  } catch (err) {
    if (err instanceof AppError) throw err;
    await logLLMRun(env, userId, task, startTime, "error", (err as Error).message);
    throw err;
  }
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
