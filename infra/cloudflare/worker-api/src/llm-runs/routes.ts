import { Hono } from "hono";
import { Env } from "../types";
import { authMiddleware } from "../middleware/auth";

export const llmRunsRoutes = new Hono<{ Bindings: Env }>();

interface LLMRunRow {
  id: string;
  user_id: string | null;
  provider: string;
  model: string;
  task: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  latency_ms: number | null;
  status: string;
  error_message: string | null;
  created_at: string;
}

function formatLLMRun(row: LLMRunRow) {
  return {
    id: row.id,
    user_id: row.user_id,
    provider: row.provider,
    model: row.model,
    task: row.task || "",
    input_tokens: row.input_tokens || 0,
    output_tokens: row.output_tokens || 0,
    latency_ms: row.latency_ms || 0,
    status: row.status,
    error_message: row.error_message,
    created_at: row.created_at,
  };
}

llmRunsRoutes.get("/", async (c) => {
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }, 401);

  const task = c.req.query("task");
  const status = c.req.query("status");
  const limit = Math.min(Math.max(parseInt(c.req.query("limit") || "50", 10), 1), 200);
  const offset = Math.max(parseInt(c.req.query("offset") || "0", 10), 0);

  let where = "WHERE user_id = ?";
  const params: (string | number)[] = [userId];

  if (task) {
    where += " AND task = ?";
    params.push(task);
  }
  if (status) {
    where += " AND status = ?";
    params.push(status);
  }

  const countResult = await c.env.DB.prepare(`SELECT COUNT(*) AS cnt FROM llm_runs ${where}`)
    .bind(...params)
    .first<{ cnt: number }>();

  const result = await c.env.DB.prepare(
    `SELECT * FROM llm_runs ${where} ORDER BY created_at DESC LIMIT ? OFFSET ?`
  )
    .bind(...params, limit, offset)
    .all<LLMRunRow>();

  return c.json({
    items: (result.results || []).map(formatLLMRun),
    total: countResult?.cnt || 0,
  });
});
