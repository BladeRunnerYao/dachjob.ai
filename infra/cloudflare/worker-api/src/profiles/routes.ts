import { Hono } from "hono";
import { Env } from "../types";
import { authMiddleware } from "../middleware/auth";
import { generateId } from "../db/utils";
import { AppError } from "../middleware/error-handler";
import { callDeepSeekChat, logLLMRun } from "../llm";
import { extractText, getDocumentProxy } from "unpdf";

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

  const arrayBuffer = await file.arrayBuffer();
  const rawText = await extractTextFromPdf(new Uint8Array(arrayBuffer));

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

async function extractTextFromPdf(bytes: Uint8Array): Promise<string> {
  let text = "";
  try {
    const pdf = await getDocumentProxy(bytes);
    const result = await extractText(pdf, { mergePages: true });
    text = result.text;
  } catch {
    text = extractTextFromPdfBasic(bytes);
  }

  text = normalizeExtractedText(text).slice(0, 50000);
  if (text.length < 100 || !/[a-zA-Z][a-zA-Z\s,.-]{40,}/.test(text)) {
    throw new AppError(
      "PDF_TEXT_EXTRACTION_FAILED",
      "Could not extract enough readable text from this PDF. Please upload a text-based PDF or paste the CV markdown.",
      400
    );
  }
  return text;
}

function extractTextFromPdfBasic(bytes: Uint8Array): string {
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
  return textChunks.join(" ");
}

function normalizeExtractedText(text: string): string {
  return text
    .replace(/\u0000/g, "")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
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
If a field is not present in the raw text, omit it instead of guessing.
Use only the supplied raw text as source material.
Output ONLY the Markdown content — no additional commentary, no JSON wrapper, no code fences.`;

  try {
    const content = await callDeepSeekChat(env, [
      { role: "system", content: systemPrompt },
      { role: "user", content: `Raw text to extract from (${sourceLabel}):\n\n${rawText}` },
    ], {
      temperature: 0.1,
    });
    await logLLMRun(env, userId, task, startTime, "success");
    return content.trim();
  } catch (err) {
    if (err instanceof AppError) throw err;
    await logLLMRun(env, userId, task, startTime, "error", (err as Error).message);
    throw err;
  }
}
