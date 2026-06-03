interface SecretStoreBinding {
  get(): Promise<string>;
}

interface Env {
  STATE: KVNamespace;
  DACHJOB_API?: Fetcher;
  GITHUB_TOKEN_SECRET?: SecretStoreBinding | string;
  DACHJOB_JWT_SECRET?: SecretStoreBinding | string;
  GITHUB_OWNER: string;
  GITHUB_REPO: string;
  GITHUB_REF: string;
  PIPELINE_PATH: string;
  DACHJOB_API_BASE_URL: string;
  DACHJOB_USER_ID: string;
  DACHJOB_USER_EMAIL: string;
  MIN_IMPORTS_PER_RUN?: string;
  MAX_IMPORTS_PER_RUN?: string;
  MIN_PARSES_PER_RUN?: string;
  MAX_PARSES_PER_RUN?: string;
  MAX_ATTEMPTS_PER_URL?: string;
  BOOTSTRAP_MODE?: "import" | "mark_seen";
  MANUAL_TRIGGER_SECRET?: SecretStoreBinding | string;
}

interface GithubContentResponse {
  sha: string;
  content: string;
  encoding: string;
}

interface GithubCommitSummary {
  sha: string;
  commit: { author?: { date?: string } };
}

interface GithubCommitDetail extends GithubCommitSummary {
  files?: Array<{ filename: string; patch?: string }>;
}

interface PipelineJobLink {
  url: string;
  key: string;
  title?: string;
  company?: string;
  location?: string;
  status?: string | null;
  active: boolean;
  line: string;
  addedAt?: string;
  sourceSha?: string;
}

interface ImportResponse {
  imported?: Array<{ url?: string; job_url?: string; id?: string }>;
  cache_hits?: Array<{ url?: string; job_url?: string; id?: string }>;
  errors?: Array<{ url: string; error: string }>;
}

interface RunSummary {
  trigger: string;
  startedAt: string;
  finishedAt: string;
  githubSha: string;
  discovered: number;
  candidates: number;
  attempted: number;
  imported: number;
  cacheHits: number;
  failed: number;
  parseCandidates: number;
  parseAttempted: number;
  parsed: number;
  parseFailed: number;
  skipped: number;
  dryRun: boolean;
  errors: string[];
}

interface UnparsedJobsResponse {
  items?: Array<{ id: string; title?: string; company?: string }>;
}

const STATE_LAST_SHA = "pipeline:last_sha";
const STATE_INITIALIZED = "pipeline:initialized";
const STATE_PROCESSED_JOBS = "pipeline:processed_jobs";
const STATE_ATTEMPTS = "pipeline:attempts";
const RUN_HISTORY_PREFIX = "pipeline:run:";

interface ProcessedJobRecord {
  url: string;
  key: string;
  status: string;
  sourceSha: string;
  at: string;
}

interface AttemptRecord {
  url: string;
  count: number;
  lastAttemptAt: string;
}

export default {
  async scheduled(_event: ScheduledEvent, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(runImporter(env, "scheduled", false));
  },

  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return json({ status: "healthy", service: "dachjob-pipeline-importer" });
    }

    if (url.pathname === "/run") {
      const authorized = await isManualTriggerAuthorized(request, env);
      if (!authorized) return json({ error: "unauthorized" }, 401);

      const dryRun = url.searchParams.get("dry_run") === "1";
      const limitOverride = url.searchParams.has("limit")
        ? parsePositiveInt(url.searchParams.get("limit"), 0)
        : undefined;
      const parseLimitOverride = url.searchParams.has("parse_limit")
        ? parsePositiveInt(url.searchParams.get("parse_limit"), 0)
        : undefined;
      const summary = await runImporter(env, "manual", dryRun, limitOverride, parseLimitOverride);
      return json(summary);
    }

    return json({ error: "not_found" }, 404);
  },
};

async function runImporter(
  env: Env,
  trigger: string,
  dryRun: boolean,
  maxImportsOverride?: number,
  maxParsesOverride?: number
): Promise<RunSummary> {
  const startedAt = new Date().toISOString();
  const errors: string[] = [];
  const maxImports = resolveRandomLimit(
    maxImportsOverride,
    env.MIN_IMPORTS_PER_RUN,
    env.MAX_IMPORTS_PER_RUN,
    trigger === "scheduled" ? 4 : 5
  );
  const maxParses = resolveRandomLimit(
    maxParsesOverride,
    env.MIN_PARSES_PER_RUN,
    env.MAX_PARSES_PER_RUN,
    trigger === "scheduled" ? 3 : 5
  );
  const maxAttempts = parsePositiveInt(env.MAX_ATTEMPTS_PER_URL, 12);

  const pipeline = await fetchPipeline(env);
  const links = extractPipelineJobLinks(pipeline.markdown).filter((link) => link.active);
  const initialized = (await env.STATE.get(STATE_INITIALIZED)) === "1";
  const bootstrapMode = env.BOOTSTRAP_MODE || "import";
  const processedJobs = await getJson<Record<string, ProcessedJobRecord>>(env, STATE_PROCESSED_JOBS, {});
  const attemptsByKey = await getJson<Record<string, AttemptRecord>>(env, STATE_ATTEMPTS, {});

  if (!initialized && bootstrapMode === "mark_seen" && !dryRun) {
    for (const link of links) {
      processedJobs[link.key] = {
        url: link.url,
        key: link.key,
        status: "bootstrap_seen",
        sourceSha: pipeline.sha,
        at: startedAt,
      };
    }
    await env.STATE.put(STATE_PROCESSED_JOBS, JSON.stringify(processedJobs));
    await env.STATE.put(STATE_INITIALIZED, "1");
    await env.STATE.put(STATE_LAST_SHA, pipeline.sha);
    const summary = finishSummary(trigger, startedAt, pipeline.sha, links.length, 0, 0, 0, 0, 0, 0, 0, 0, 0, links.length, dryRun, []);
    await persistSummary(env, summary);
    return summary;
  }

  const candidates: PipelineJobLink[] = [];
  for (const link of links) {
    if (processedJobs[link.key]) continue;

    const attempts = attemptsByKey[link.key]?.count || 0;
    if (attempts >= maxAttempts) continue;
    candidates.push(link);
  }

  const selected = await selectNewestCandidates(env, candidates, maxImports);
  let imported = 0;
  let cacheHits = 0;
  let failed = 0;
  let parseCandidates = 0;
  let parseAttempted = 0;
  let parsed = 0;
  let parseFailed = 0;
  let token: string | null = null;

  if (!dryRun && selected.length > 0) {
    token = await createDachJobJwt(env);
    for (const batch of chunk(selected, 10)) {
      try {
        const response = await importBatch(env, token, batch);
        const failedUrls = new Map((response.errors || []).map((error) => [normalizeUrlForComparison(error.url), error.error]));
        const importedCount = response.imported?.length || 0;
        const cacheHitCount = response.cache_hits?.length || 0;
        imported += importedCount;
        cacheHits += cacheHitCount;

        for (const link of batch) {
          const normalized = normalizeUrlForComparison(link.url);
          const failure = failedUrls.get(normalized);
          if (failure) {
            failed += 1;
            if (isProfileMismatchError(failure)) {
              markSeen(processedJobs, attemptsByKey, link, "profile_mismatch", startedAt, pipeline.sha);
            } else {
              incrementAttempt(processedJobs, attemptsByKey, link, startedAt, maxAttempts);
            }
            continue;
          }
          markSeen(processedJobs, attemptsByKey, link, "imported", startedAt, pipeline.sha);
        }

        for (const error of response.errors || []) {
          errors.push(`${error.url}: ${error.error}`);
        }
      } catch (error) {
        failed += batch.length;
        errors.push(error instanceof Error ? error.message : String(error));
        for (const link of batch) incrementAttempt(processedJobs, attemptsByKey, link, startedAt, maxAttempts);
      }
    }
  }

  if (!dryRun && maxParses > 0) {
    token ||= await createDachJobJwt(env);
    try {
      const parseSummary = await parseLatestUnparsedJobs(env, token, maxParses);
      parseCandidates = parseSummary.candidates;
      parseAttempted = parseSummary.attempted;
      parsed = parseSummary.parsed;
      parseFailed = parseSummary.failed;
      errors.push(...parseSummary.errors);
    } catch (error) {
      parseFailed += maxParses;
      errors.push(error instanceof Error ? error.message : String(error));
    }
  }

  if (!dryRun) {
    await env.STATE.put(STATE_PROCESSED_JOBS, JSON.stringify(processedJobs));
    await env.STATE.put(STATE_ATTEMPTS, JSON.stringify(attemptsByKey));
    await env.STATE.put(STATE_INITIALIZED, "1");
    await env.STATE.put(STATE_LAST_SHA, pipeline.sha);
  }

  const skipped = links.length - selected.length;
  const summary = finishSummary(
    trigger,
    startedAt,
    pipeline.sha,
    links.length,
    candidates.length,
    selected.length,
    imported,
    cacheHits,
    failed,
    parseCandidates,
    parseAttempted,
    parsed,
    parseFailed,
    skipped,
    dryRun,
    errors
  );
  if (!dryRun) await persistSummary(env, summary);
  return summary;
}

async function selectNewestCandidates(env: Env, candidates: PipelineJobLink[], maxImports: number): Promise<PipelineJobLink[]> {
  if (maxImports <= 0 || candidates.length === 0) return [];
  const windowSize = Math.min(candidates.length, Math.max(50, maxImports * 20));
  const likelyNewest = candidates.slice(-windowSize);
  const withHistory = await attachPipelineAddedTimes(env, likelyNewest);
  return withHistory
    .sort((left, right) => new Date(right.addedAt || 0).getTime() - new Date(left.addedAt || 0).getTime())
    .slice(0, maxImports);
}

async function parseLatestUnparsedJobs(
  env: Env,
  token: string,
  limit: number
): Promise<{ candidates: number; attempted: number; parsed: number; failed: number; errors: string[] }> {
  const response = await apiJson<UnparsedJobsResponse>(env, token, `/api/jobs/unparsed?limit=${limit}`);
  const jobs = response.items || [];
  let parsed = 0;
  let failed = 0;
  const errors: string[] = [];

  for (const job of jobs) {
    try {
      await apiJson(env, token, `/api/jobs/${encodeURIComponent(job.id)}/parse`, { method: "POST" });
      parsed += 1;
    } catch (error) {
      failed += 1;
      errors.push(`${job.id}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  return {
    candidates: jobs.length,
    attempted: jobs.length,
    parsed,
    failed,
    errors,
  };
}

async function fetchPipeline(env: Env): Promise<{ sha: string; markdown: string }> {
  const token = await getSecret(env.GITHUB_TOKEN_SECRET, "GITHUB_TOKEN_SECRET");
  const apiUrl = new URL(
    `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/contents/${env.PIPELINE_PATH}`
  );
  apiUrl.searchParams.set("ref", env.GITHUB_REF || "main");

  const response = await fetch(apiUrl.toString(), {
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "dachjob-pipeline-importer",
    },
  });
  if (!response.ok) {
    throw new Error(`GitHub pipeline fetch failed: ${response.status} ${await response.text()}`);
  }

  const body = (await response.json()) as GithubContentResponse;
  if (body.encoding !== "base64") {
    throw new Error(`Unsupported GitHub content encoding: ${body.encoding}`);
  }

  return { sha: body.sha, markdown: decodeBase64Text(body.content) };
}

async function attachPipelineAddedTimes(env: Env, links: PipelineJobLink[]): Promise<PipelineJobLink[]> {
  if (links.length === 0) return links;
  const byKey = new Map(links.map((link) => [link.key, link]));
  const token = await getSecret(env.GITHUB_TOKEN_SECRET, "GITHUB_TOKEN_SECRET");
  const commits = await fetchPipelineCommits(env, token);
  const fallbackDate = commits[0]?.commit.author?.date || new Date().toISOString();

  for (const commit of [...commits].reverse()) {
    if ([...byKey.values()].every((link) => link.addedAt)) break;
    const detail = await fetchCommitDetail(env, token, commit.sha);
    const patch = detail.files?.find((file) => file.filename === env.PIPELINE_PATH)?.patch || "";
    for (const line of patch.split("\n")) {
      if (!line.startsWith("+") || line.startsWith("+++")) continue;
      const urlMatch = line.match(/https?:\/\/[^\s|)~]+/i);
      if (!urlMatch) continue;
      const key = canonicalJobKey(cleanupUrl(urlMatch[0]));
      const link = byKey.get(key);
      if (link && !link.addedAt) {
        link.addedAt = commit.commit.author?.date || fallbackDate;
        link.sourceSha = commit.sha;
      }
    }
  }

  return links.map((link) => ({
    ...link,
    addedAt: link.addedAt || fallbackDate,
    sourceSha: link.sourceSha || commits[0]?.sha,
  }));
}

async function fetchPipelineCommits(env: Env, token: string): Promise<GithubCommitSummary[]> {
  const url = new URL(`https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/commits`);
  url.searchParams.set("sha", env.GITHUB_REF || "main");
  url.searchParams.set("path", env.PIPELINE_PATH);
  url.searchParams.set("per_page", "50");
  return githubJson<GithubCommitSummary[]>(url.toString(), token);
}

async function fetchCommitDetail(env: Env, token: string, sha: string): Promise<GithubCommitDetail> {
  return githubJson<GithubCommitDetail>(
    `https://api.github.com/repos/${env.GITHUB_OWNER}/${env.GITHUB_REPO}/commits/${sha}`,
    token
  );
}

async function githubJson<T>(url: string, token: string): Promise<T> {
  const response = await fetch(url, {
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "dachjob-pipeline-importer",
    },
  });
  if (!response.ok) {
    throw new Error(`GitHub request failed: ${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

function extractPipelineJobLinks(markdown: string): PipelineJobLink[] {
  const links = new Map<string, PipelineJobLink>();
  const taskLinePattern = /^\s*-\s*\[[ xX]\]\s+(.+)$/gim;
  let match: RegExpExecArray | null;

  while ((match = taskLinePattern.exec(markdown)) !== null) {
    const line = match[1].trim();
    const urlMatch = line.match(/https?:\/\/[^\s|)~]+/i);
    if (!urlMatch) continue;
    const url = cleanupUrl(urlMatch[0]);
    const key = canonicalJobKey(url);
    if (!links.has(key)) links.set(key, parsePipelineLine(line, url, key));
  }

  return [...links.values()];
}

function parsePipelineLine(line: string, url: string, key: string): PipelineJobLink {
  const parts = line.split("|").map((part) => cleanMarkdown(part.trim()));
  const urlIndex = parts.findIndex((part) => part.includes(url));
  const company = parts[urlIndex + 1]?.trim() || undefined;
  const title = parts[urlIndex + 2]?.trim() || undefined;
  const metadata = parts.slice(Math.max(urlIndex + 3, 1)).join("; ");
  const location = metadata.match(/Location:\s*([^;|]+)/i)?.[1]?.trim();
  const status = parsePipelineStatus(line);
  const inactive = /closed\s*\(|no longer accepting|discarded|expired|inactive/i.test(line) && !status;

  return {
    url,
    key,
    title,
    company,
    location,
    status,
    active: !inactive,
    line,
  };
}

function parsePipelineStatus(line: string): string | null {
  if (/\bRejected\b/i.test(line)) return "rejected";
  if (/\bOffer\b/i.test(line)) return "offer";
  if (/\bInterview\b|\bRound\s+\d/i.test(line) && !/Use:\s*Interview practice/i.test(line)) return "interview";
  if (/\bApplied\b|\bResponded\b/i.test(line)) return "applied";
  return null;
}

function cleanMarkdown(value: string): string {
  return value.replace(/^~+|~+$/g, "").trim();
}

async function importBatch(env: Env, token: string, jobs: PipelineJobLink[]): Promise<ImportResponse> {
  const request = new Request(`${env.DACHJOB_API_BASE_URL.replace(/\/$/, "")}/api/jobs/import`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      jobs: jobs.map((job) => ({
        url: job.url,
        added_at: job.addedAt,
        status: job.status,
        source_sha: job.sourceSha,
        title: job.title,
        company: job.company,
        location: job.location,
        prepare: false,
      })),
    }),
  });

  const response = env.DACHJOB_API ? await env.DACHJOB_API.fetch(request) : await fetch(request);
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`DachJob import failed: HTTP ${response.status}: ${text.slice(0, 500)}`);
  }
  return text ? ((JSON.parse(text) as ImportResponse) || {}) : {};
}

async function apiJson<T = unknown>(
  env: Env,
  token: string,
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const request = new Request(`${env.DACHJOB_API_BASE_URL.replace(/\/$/, "")}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(init.headers || {}),
    },
  });

  const response = env.DACHJOB_API ? await env.DACHJOB_API.fetch(request) : await fetch(request);
  const text = await response.text();
  if (!response.ok) {
    throw new Error(`DachJob API failed: HTTP ${response.status}: ${text.slice(0, 500)}`);
  }
  return text ? (JSON.parse(text) as T) : ({} as T);
}

async function createDachJobJwt(env: Env): Promise<string> {
  const secret = await getSecret(env.DACHJOB_JWT_SECRET, "DACHJOB_JWT_SECRET");
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: "HS256", typ: "JWT" };
  const payload = {
    sub: env.DACHJOB_USER_ID,
    email: env.DACHJOB_USER_EMAIL,
    iat: now,
    exp: now + 30 * 60,
  };

  const encodedHeader = base64UrlEncodeText(JSON.stringify(header));
  const encodedPayload = base64UrlEncodeText(JSON.stringify(payload));
  const signingInput = `${encodedHeader}.${encodedPayload}`;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const signature = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(signingInput));
  return `${signingInput}.${base64UrlEncodeBytes(new Uint8Array(signature))}`;
}

async function isManualTriggerAuthorized(request: Request, env: Env): Promise<boolean> {
  if (!env.MANUAL_TRIGGER_SECRET) return true;
  const expected = await getSecret(env.MANUAL_TRIGGER_SECRET, "MANUAL_TRIGGER_SECRET");
  const provided = request.headers.get("Authorization")?.replace(/^Bearer\s+/i, "") || new URL(request.url).searchParams.get("token");
  return provided === expected;
}

async function getSecret(binding: SecretStoreBinding | string | undefined, name: string): Promise<string> {
  if (!binding) throw new Error(`${name} is not configured`);
  if (typeof binding === "string") return binding;
  return binding.get();
}

function incrementAttempt(
  processedJobs: Record<string, ProcessedJobRecord>,
  attemptsByKey: Record<string, AttemptRecord>,
  link: PipelineJobLink,
  at: string,
  maxAttempts: number
): void {
  const current = (attemptsByKey[link.key]?.count || 0) + 1;
  if (current >= maxAttempts) {
    markSeen(processedJobs, attemptsByKey, link, "failed_max_attempts", at, "");
    return;
  }
  attemptsByKey[link.key] = { url: link.url, count: current, lastAttemptAt: at };
}

function markSeen(
  processedJobs: Record<string, ProcessedJobRecord>,
  attemptsByKey: Record<string, AttemptRecord>,
  link: PipelineJobLink,
  status: string,
  at: string,
  sourceSha: string
): void {
  processedJobs[link.key] = {
    url: link.url,
    key: link.key,
    status,
    sourceSha,
    at,
  };
  delete attemptsByKey[link.key];
}

async function persistSummary(env: Env, summary: RunSummary): Promise<void> {
  await env.STATE.put(`${RUN_HISTORY_PREFIX}${summary.startedAt}`, JSON.stringify(summary), {
    expirationTtl: 60 * 60 * 24 * 30,
  });
}

function finishSummary(
  trigger: string,
  startedAt: string,
  githubSha: string,
  discovered: number,
  candidates: number,
  attempted: number,
  imported: number,
  cacheHits: number,
  failed: number,
  parseCandidates: number,
  parseAttempted: number,
  parsed: number,
  parseFailed: number,
  skipped: number,
  dryRun: boolean,
  errors: string[]
): RunSummary {
  return {
    trigger,
    startedAt,
    finishedAt: new Date().toISOString(),
    githubSha,
    discovered,
    candidates,
    attempted,
    imported,
    cacheHits,
    failed,
    parseCandidates,
    parseAttempted,
    parsed,
    parseFailed,
    skipped,
    dryRun,
    errors: errors.slice(0, 50),
  };
}

function resolveRandomLimit(
  override: number | undefined,
  minValue: string | null | undefined,
  maxValue: string | null | undefined,
  fallbackMax: number
): number {
  if (override !== undefined) return override;
  const max = parsePositiveInt(maxValue, fallbackMax);
  const min = Math.min(parsePositiveInt(minValue, max), max);
  if (max <= min) return max;
  return min + Math.floor(Math.random() * (max - min + 1));
}

function isProfileMismatchError(error: string): boolean {
  return error.includes("PROFILE_MISMATCH:");
}

function cleanupUrl(url: string): string {
  return url.trim().replace(/[),.;]+$/g, "");
}

function canonicalJobKey(url: string): string {
  const parsed = new URL(url);
  const linkedInJobId = parsed.hostname.endsWith("linkedin.com") && parsed.pathname.match(/\/jobs\/view\/(?:[^/]+-)?(\d+)/);
  if (linkedInJobId) return `linkedin:${linkedInJobId[1]}`;

  const indeedId = parsed.hostname.endsWith("indeed.com") ? parsed.searchParams.get("jk") : null;
  if (indeedId) return `indeed:${indeedId}`;

  const greenhouseToken = parsed.searchParams.get("gh_jid");
  if (greenhouseToken) return `${parsed.hostname.toLowerCase().replace(/^www\./, "")}:gh_jid:${greenhouseToken}`;

  parsed.hash = "";
  parsed.search = "";
  parsed.hostname = parsed.hostname.toLowerCase().replace(/^www\./, "");
  parsed.pathname = parsed.pathname.replace(/\/+$/, "");
  return `${parsed.hostname}${parsed.pathname}`.toLowerCase();
}

function normalizeUrlForComparison(url: string): string {
  try {
    return canonicalJobKey(url);
  } catch {
    return cleanupUrl(url).toLowerCase();
  }
}

async function getJson<T>(env: Env, key: string, fallback: T): Promise<T> {
  const value = await env.STATE.get(key, "json");
  return value === null ? fallback : (value as T);
}

function decodeBase64Text(value: string): string {
  const binary = atob(value.replace(/\s/g, ""));
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

function base64UrlEncodeText(value: string): string {
  return base64UrlEncodeBytes(new TextEncoder().encode(value));
}

function base64UrlEncodeBytes(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function chunk<T>(items: T[], size: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < items.length; i += size) chunks.push(items.slice(i, i + size));
  return chunks;
}

function parsePositiveInt(value: string | null | undefined, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
