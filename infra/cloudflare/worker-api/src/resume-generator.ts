import { generateId } from "./db/utils";
import { callDeepSeekChat, logLLMRun } from "./llm";
import { Env } from "./types";

export interface ResumeJob {
  id: string;
  title: string;
  company: string;
  raw_description: string;
  parsed_json?: string | null;
}

export interface ResumeProfile {
  id: string;
  name: string;
  raw_cv_md: string;
  profile_json: string | null;
}

export interface ResumeGenerationOptions {
  applicationId?: string;
  confirmedSkills?: string[];
  matchResult?: string | null;
  style?: string;
}

export interface StoredResumeArtifact {
  id: string;
  job_id: string;
  html_object_key: string;
  pdf_object_key: null;
  provenance_json: Record<string, unknown>[];
}

export async function generateAndStoreResume(
  env: Env,
  userId: string,
  job: ResumeJob,
  profile: ResumeProfile,
  options: ResumeGenerationOptions = {}
): Promise<StoredResumeArtifact> {
  const result = await generateResumeHtml(env, userId, job, profile, options);
  const applicationId =
    options.applicationId || (await getOrCreateApplication(env, userId, job.id, profile.id));
  const artifactId = generateId();
  const r2Key = `resumes/${userId}/${job.id}/${artifactId}.html`;

  await env.STORAGE.put(r2Key, result.html, {
    httpMetadata: { contentType: "text/html; charset=utf-8" },
  });

  const now = new Date().toISOString();
  await env.DB.prepare(
    `INSERT INTO artifacts (id, user_id, application_id, type, r2_key, content_type, size_bytes, created_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(artifactId, userId, applicationId, "cv_html", r2Key, "text/html; charset=utf-8", result.html.length, now)
    .run();

  return {
    id: artifactId,
    job_id: job.id,
    html_object_key: r2Key,
    pdf_object_key: null,
    provenance_json: result.provenance,
  };
}

async function generateResumeHtml(
  env: Env,
  userId: string,
  job: ResumeJob,
  profile: ResumeProfile,
  options: ResumeGenerationOptions
): Promise<{ html: string; provenance: Record<string, unknown>[] }> {
  const style = normalizeResumeStyle(options.style);
  const parsedJob = parseJsonObject(job.parsed_json);
  const parsedProfile = parseJsonObject(profile.profile_json);
  const confirmedSkills = normalizeSkillList(options.confirmedSkills || []);
  const jdSkills = collectJobSkills(parsedJob);
  const prompt = buildResumePrompt({
    style,
    job,
    parsedJob,
    profile,
    parsedProfile,
    confirmedSkills,
    jdSkills,
    matchResult: options.matchResult || null,
  });
  const startTime = Date.now();

  try {
    const content = await callDeepSeekChat(
      env,
      [
        {
          role: "system",
          content:
            "You are a precise resume tailoring agent. Follow the user's resume policy exactly. Output only the requested HTML document.",
        },
        { role: "user", content: prompt },
      ],
      { temperature: 0.25 }
    );
    await logLLMRun(env, userId, "resume_generate", startTime, "success");
    return {
      html: extractHtmlDocument(content) || fallbackResumeHtml(profile.name, profile.raw_cv_md, job, style),
      provenance: buildProvenance(style, confirmedSkills, jdSkills, parsedJob),
    };
  } catch (err) {
    await logLLMRun(env, userId, "resume_generate", startTime, "error", (err as Error).message);
    return {
      html: fallbackResumeHtml(profile.name, profile.raw_cv_md, job, style),
      provenance: [
        {
          source: "cloudflare-worker-fallback",
          style,
          error: (err as Error).message,
        },
      ],
    };
  }
}

function buildResumePrompt(input: {
  style: "us" | "german";
  job: ResumeJob;
  parsedJob: Record<string, unknown> | null;
  profile: ResumeProfile;
  parsedProfile: Record<string, unknown> | null;
  confirmedSkills: string[];
  jdSkills: string[];
  matchResult: string | null;
}): string {
  const stylePolicy =
    input.style === "german"
      ? `Generate a DACH/German-recruiter-friendly HTML CV only if explicitly requested by the API style.
- A4 page, concise, modern two-column layout is allowed.
- Include work authorization or languages only when present in candidate evidence.
- Do not include unsupported personal data.`
      : `Generate a US / ATS-heavy software engineering resume.
- One page, one column, letterpaper, no photo, no date of birth, no marital status, no nationality, no full street address.
- Header: candidate name plus portfolio/location/email/phone only when present in the CV. Do not add a target-title line below the name.
- Standard ATS headings only: Summary, Technical Skills, Experience, Education.
- Technical Skills must be category bullets, not one dense paragraph.
- Experience must be reverse-chronological. Company line first, then role/title line, then concise bullets.
- Prefer the structure and density of the sb2nov/resume style, but output self-contained HTML/CSS rather than LaTeX.
- Keep it compact and readable; avoid graphics, sidebars, badges, tables for layout, and decorative color blocks.`;

  return `${stylePolicy}

Career-ops Resume Tailor Mode parity rules:
1. Internally extract all JD skill requirements: hard skills, soft skills, language requirements, education/certifications, and domain knowledge.
2. Use exact JD wording for ATS keywords when the candidate evidence supports the skill.
3. Treat API confirmed_skills as user-approved skills. If a JD skill is not present in the CV/profile/match evidence and not in confirmed_skills, do not claim it as experience.
4. Seamlessly integrate supported skills into Summary, Technical Skills, and existing work-experience bullets. Do not keyword-stuff.
5. Never invent employers, dates, degrees, metrics, tools, certifications, publications, security clearance, work authorization, or domain experience.
6. Do not expand generic evidence into specific vendor tools or services. For example, if the CV only says "serverless", do not write "AWS Lambda" or "Azure Functions" unless those exact services appear in the CV/profile/match evidence or confirmed_skills.
7. If the candidate has adjacent but not exact experience, phrase carefully: "experience with", "worked with", or omit the claim.
8. Prioritize evidence relevant to this job; compress older/lower-priority experience first.
9. Output a complete HTML document starting with <!DOCTYPE html>. The first bytes of the response must be <!DOCTYPE html>; do not include markdown fences, explanations, JSON, or provenance.

Target job:
Company: ${input.job.company || "Unknown"}
Title: ${input.job.title || "Unknown"}
Parsed JD JSON:
${JSON.stringify(input.parsedJob || {}, null, 2).slice(0, 6000)}

JD skill keywords to consider for ATS matching:
${input.jdSkills.length ? input.jdSkills.join(", ") : "No parsed skill keywords available; extract from raw JD."}

API confirmed_skills:
${input.confirmedSkills.length ? input.confirmedSkills.join(", ") : "None"}

Raw job description:
${input.job.raw_description.slice(0, 12000)}

Candidate CV markdown:
${input.profile.raw_cv_md.slice(0, 18000)}

Candidate profile JSON:
${JSON.stringify(input.parsedProfile || {}, null, 2).slice(0, 4000)}

Match analysis, if available:
${input.matchResult ? input.matchResult.slice(0, 4000) : "None"}

HTML/CSS constraints:
- Use inline <style> in <head>; no external assets.
- Use selectable text only.
- Use @page with ${input.style === "us" ? "Letter and 0.45in margins" : "A4 and print-friendly margins"}.
- Make links plain and ATS-readable.
- Escape special characters correctly.
- The visible resume language should be English for this English JD.`;
}

function normalizeResumeStyle(style?: string): "us" | "german" {
  const normalized = (style || "us").trim().toLowerCase();
  if (["german", "dach", "de"].includes(normalized)) return "german";
  return "us";
}

function collectJobSkills(parsedJob: Record<string, unknown> | null): string[] {
  if (!parsedJob) return [];
  const values = [
    ...readStringArray(parsedJob.must_have_skills),
    ...readStringArray(parsedJob.nice_to_have_skills),
    ...readStringArray(parsedJob.required_qualifications),
    ...readStringArray(parsedJob.preferred_qualifications),
  ];
  return normalizeSkillList(values.flatMap(splitSkillPhrase));
}

function readStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
    : [];
}

function splitSkillPhrase(value: string): string[] {
  if (value.length <= 80) return [value];
  return value
    .split(/[,;/]|\band\b|\bor\b/i)
    .map((part) => part.trim())
    .filter((part) => part.length > 1 && part.length <= 80);
}

function normalizeSkillList(skills: string[]): string[] {
  const seen = new Set<string>();
  const normalized: string[] = [];
  for (const skill of skills) {
    const cleaned = skill.replace(/\s+/g, " ").trim();
    const key = cleaned.toLowerCase();
    if (!cleaned || seen.has(key)) continue;
    seen.add(key);
    normalized.push(cleaned);
  }
  return normalized.slice(0, 80);
}

function parseJsonObject(value: string | null | undefined): Record<string, unknown> | null {
  if (!value) return null;
  try {
    const parsed = JSON.parse(value) as unknown;
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function extractHtmlDocument(content: string): string | null {
  const trimmed = content.trim().replace(/^```(?:html)?\s*/i, "").replace(/```$/i, "").trim();
  const htmlStart = trimmed.search(/<!doctype html>|<html[\s>]/i);
  if (htmlStart < 0) return null;
  const html = trimmed.slice(htmlStart);
  const htmlEnd = html.search(/<\/html\s*>/i);
  return htmlEnd >= 0 ? html.slice(0, htmlEnd + html.match(/<\/html\s*>/i)![0].length) : html;
}

function buildProvenance(
  style: "us" | "german",
  confirmedSkills: string[],
  jdSkills: string[],
  parsedJob: Record<string, unknown> | null
): Record<string, unknown>[] {
  return [
    {
      source: "cloudflare-worker",
      mode: "career-ops-resume-tailor",
      style,
      confirmed_skills: confirmedSkills,
      jd_skill_keywords: jdSkills,
      parsed_job_used: Boolean(parsedJob),
    },
  ];
}

function fallbackResumeHtml(name: string, rawCvMd: string, job: ResumeJob, style: "us" | "german"): string {
  const pageSize = style === "us" ? "Letter" : "A4";
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Resume - ${escapeHtml(name)}</title>
<style>
@page { size: ${pageSize}; margin: 0.45in; }
body { font-family: Arial, Helvetica, sans-serif; color: #111827; line-height: 1.35; font-size: 10.5pt; margin: 0; }
main { max-width: 7.5in; margin: 0 auto; }
h1 { font-size: 20pt; margin: 0 0 4pt; }
h2 { font-size: 11pt; text-transform: uppercase; border-bottom: 1px solid #111827; padding-bottom: 2pt; margin: 12pt 0 6pt; }
.target { color: #374151; margin-bottom: 10pt; }
pre { white-space: pre-wrap; font-family: inherit; font-size: 9.5pt; }
</style>
</head>
<body>
<main>
<h1>${escapeHtml(name)}</h1>
<div class="target">${escapeHtml(job.title)} at ${escapeHtml(job.company)}</div>
<h2>Resume Source</h2>
<pre>${escapeHtml(rawCvMd.slice(0, 10000))}</pre>
</main>
</body>
</html>`;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function getOrCreateApplication(env: Env, userId: string, jobId: string, profileId: string): Promise<string> {
  const existing = await env.DB.prepare(
    "SELECT id FROM applications WHERE user_id = ? AND job_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT 1"
  )
    .bind(userId, jobId)
    .first<{ id: string }>();
  if (existing) return existing.id;

  const id = generateId();
  const now = new Date().toISOString();
  await env.DB.prepare(
    `INSERT INTO applications (id, user_id, job_id, profile_id, status, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`
  )
    .bind(id, userId, jobId, profileId, "draft", now, now)
    .run();
  return id;
}

export const resumeGeneratorTestables = {
  buildResumePrompt,
  collectJobSkills,
  extractHtmlDocument,
  normalizeResumeStyle,
  parseJsonObject,
};
