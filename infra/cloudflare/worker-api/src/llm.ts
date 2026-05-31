import { generateId } from "./db/utils";
import { Env } from "./types";

export const DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash";

type Message = {
  role: "system" | "user" | "assistant";
  content: string;
};

export function getDeepSeekModel(env: Env): string {
  return env.DEEPSEEK_MODEL || DEFAULT_DEEPSEEK_MODEL;
}

export async function callDeepSeekChat(
  env: Env,
  messages: Message[],
  options: { temperature?: number; json?: boolean } = {}
): Promise<string> {
  if (!env.LLM_API_KEY) {
    throw new Error("LLM_API_KEY not configured");
  }

  const response = await fetch("https://api.deepseek.com/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.LLM_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: getDeepSeekModel(env),
      messages,
      temperature: options.temperature ?? 0.2,
      ...(options.json ? { response_format: { type: "json_object" } } : {}),
    }),
  });

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`LLM API error: ${response.status}${text ? ` - ${text}` : ""}`);
  }

  const data = (await response.json()) as { choices: { message: { content: string } }[] };
  return data.choices[0]?.message?.content || "";
}

export async function logLLMRun(
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
      getDeepSeekModel(env),
      task,
      Date.now() - startTime,
      status,
      errorMessage || null,
      new Date().toISOString()
    )
    .run();
}
