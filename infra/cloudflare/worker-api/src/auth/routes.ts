import { Hono } from "hono";
import * as jose from "jose";
import { Env } from "../types";
import { generateId, hashPassword, verifyPassword } from "../db/utils";
import { AppError } from "../middleware/error-handler";

export const authRoutes = new Hono<{ Bindings: Env }>();

// GET /api/auth/me
authRoutes.get("/me", async (c) => {
  const { authMiddleware } = await import("../middleware/auth");
  const userId = await authMiddleware(c);
  if (!userId) {
    return c.json({ error: { code: "UNAUTHORIZED", message: "Not authenticated" } }, 401);
  }

  const user = await c.env.DB.prepare("SELECT id, email, name, created_at FROM users WHERE id = ?")
    .bind(userId)
    .first<{ id: string; email: string; name: string; created_at: string }>();
  if (!user) {
    return c.json({ error: { code: "NOT_FOUND", message: "User not found" } }, 404);
  }
  return c.json({ id: user.id, email: user.email, name: user.name });
});

// POST /api/auth/register
authRoutes.post("/register", async (c) => {
  const body = await c.req.json<{ email: string; password: string; name?: string }>();

  if (!body.email || !body.password) {
    throw new AppError("VALIDATION_ERROR", "Email and password are required", 400);
  }
  if (body.password.length < 8) {
    throw new AppError("VALIDATION_ERROR", "Password must be at least 8 characters", 400);
  }

  const existing = await c.env.DB.prepare("SELECT id FROM users WHERE email = ?")
    .bind(body.email.toLowerCase())
    .first();
  if (existing) {
    throw new AppError("CONFLICT", "Email already registered", 409);
  }

  const id = generateId();
  const passwordHash = await hashPassword(body.password);
  const now = new Date().toISOString();

  await c.env.DB.prepare(
    "INSERT INTO users (id, email, name, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)"
  )
    .bind(id, body.email.toLowerCase(), body.name || "", passwordHash, now, now)
    .run();

  const token = await createToken(id, body.email.toLowerCase(), c.env.JWT_SECRET, c.env.JWT_EXPIRY_HOURS);

  return c.json({ token, user: { id, email: body.email.toLowerCase(), name: body.name || "" } }, 201);
});

// POST /api/auth/login
authRoutes.post("/login", async (c) => {
  const body = await c.req.json<{ email: string; password: string }>();

  if (!body.email || !body.password) {
    throw new AppError("VALIDATION_ERROR", "Email and password are required", 400);
  }

  const user = await c.env.DB.prepare("SELECT id, email, name, password_hash FROM users WHERE email = ?")
    .bind(body.email.toLowerCase())
    .first<{ id: string; email: string; name: string; password_hash: string }>();

  if (!user) {
    throw new AppError("INVALID_CREDENTIALS", "Invalid email or password", 401);
  }

  const valid = await verifyPassword(body.password, user.password_hash);
  if (!valid) {
    throw new AppError("INVALID_CREDENTIALS", "Invalid email or password", 401);
  }

  const token = await createToken(user.id, user.email, c.env.JWT_SECRET, c.env.JWT_EXPIRY_HOURS);

  return c.json({ token, user: { id: user.id, email: user.email, name: user.name } });
});

// POST /api/auth/logout (stateless JWT - just acknowledge)
authRoutes.post("/logout", (c) => {
  return c.json({ message: "Logged out" });
});

// POST /api/auth/forgot-password
authRoutes.post("/forgot-password", async (c) => {
  const body = await c.req.json<{ email: string }>();
  // In a real implementation, send an email with a reset link.
  // For now, just acknowledge to avoid leaking user existence.
  return c.json({ message: "If the email exists, a reset link has been sent." });
});

// POST /api/auth/reset-password
authRoutes.post("/reset-password", async (c) => {
  const body = await c.req.json<{ token: string; new_password: string }>();

  if (!body.token || !body.new_password) {
    throw new AppError("VALIDATION_ERROR", "Token and new_password are required", 400);
  }
  if (body.new_password.length < 8) {
    throw new AppError("VALIDATION_ERROR", "Password must be at least 8 characters", 400);
  }

  // Verify reset token (stored as JWT with short expiry)
  try {
    const secret = new TextEncoder().encode(c.env.JWT_SECRET);
    const { payload } = await jose.jwtVerify(body.token, secret);
    const userId = payload.sub as string;

    const passwordHash = await hashPassword(body.new_password);
    await c.env.DB.prepare("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?")
      .bind(passwordHash, new Date().toISOString(), userId)
      .run();

    return c.json({ message: "Password reset successfully" });
  } catch {
    throw new AppError("INVALID_TOKEN", "Invalid or expired reset token", 400);
  }
});

async function createToken(
  userId: string,
  email: string,
  jwtSecret: string,
  expiryHours: string
): Promise<string> {
  const secret = new TextEncoder().encode(jwtSecret);
  const hours = parseInt(expiryHours, 10) || 72;
  const token = await new jose.SignJWT({ sub: userId, email })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(`${hours}h`)
    .sign(secret);
  return token;
}
