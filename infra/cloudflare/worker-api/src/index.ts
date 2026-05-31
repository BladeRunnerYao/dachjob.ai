import { Hono } from "hono";
import { cors } from "hono/cors";
import { Env } from "./types";
import { authRoutes } from "./auth/routes";
import { jobsRoutes } from "./jobs/routes";
import { profilesRoutes } from "./profiles/routes";
import { matchingRoutes } from "./matching/routes";
import { resumesRoutes } from "./resumes/routes";
import { artifactsRoutes } from "./artifacts/routes";
import { applicationsRoutes } from "./applications/routes";
import { llmRunsRoutes } from "./llm-runs/routes";
import { errorHandler } from "./middleware/error-handler";

const app = new Hono<{ Bindings: Env }>();

function originMatches(pattern: string, origin: string): boolean {
  if (pattern === "*") return true;
  if (pattern.startsWith("*.")) {
    // wildcard subdomain: *.example.com matches a.example.com
    const suffix = pattern.slice(1); // ".example.com"
    return origin.endsWith(suffix);
  }
  return pattern === origin;
}

// Global CORS
app.use(
  "*",
  cors({
    origin: (origin, c) => {
      const allowed = c.env.CORS_ORIGIN || "*";
      if (allowed === "*") return "*";
      const origins = allowed.split(",").map((o: string) => o.trim());
      // Return the original origin if it matches any allowed pattern,
      // otherwise return the first allowed origin as fallback
      const match = origins.find((o: string) => originMatches(o, origin));
      return match ? origin : origins[0] || "";
    },
    allowMethods: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allowHeaders: ["Content-Type", "Authorization"],
    exposeHeaders: ["Content-Length"],
    maxAge: 86400,
    credentials: true,
  })
);

// Global error handler
app.onError(errorHandler);

// Health check
app.get("/api/health", (c) => {
  return c.json({ status: "healthy", service: "dachjob-api", platform: "cloudflare" });
});

// Mount routes
app.route("/api/auth", authRoutes);
app.route("/api/jobs", jobsRoutes);
app.route("/api/profile", profilesRoutes);
app.route("/api/match", matchingRoutes);
app.route("/api/resumes", resumesRoutes);
app.route("/api/artifacts", artifactsRoutes);
app.route("/api/applications", applicationsRoutes);
app.route("/api/llm-runs", llmRunsRoutes);

// User info endpoint
app.get("/api/me", async (c) => {
  const { authMiddleware } = await import("./middleware/auth");
  const userId = await authMiddleware(c);
  if (!userId) return c.json({ error: { code: "UNAUTHORIZED", message: "Not authenticated" } }, 401);

  const user = await c.env.DB.prepare("SELECT id, email, name, created_at FROM users WHERE id = ?")
    .bind(userId)
    .first();
  if (!user) return c.json({ error: { code: "NOT_FOUND", message: "User not found" } }, 404);
  return c.json(user);
});

// 404 fallback
app.notFound((c) => {
  return c.json({ error: { code: "NOT_FOUND", message: "Endpoint not found" } }, 404);
});

export default app;
