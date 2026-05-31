import { Context } from "hono";
import * as jose from "jose";
import { Env, JwtPayload } from "../types";

/**
 * Extract and verify JWT from Authorization header.
 * Returns the user ID if valid, null otherwise.
 */
export async function authMiddleware(c: Context<{ Bindings: Env }>): Promise<string | null> {
  const authHeader = c.req.header("Authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return null;
  }

  const token = authHeader.slice(7);
  try {
    const secret = new TextEncoder().encode(c.env.JWT_SECRET);
    const { payload } = await jose.jwtVerify(token, secret);
    const jwtPayload = payload as unknown as JwtPayload;
    return jwtPayload.sub;
  } catch {
    return null;
  }
}

/**
 * Require authentication - returns user ID or throws 401.
 */
export async function requireAuth(c: Context<{ Bindings: Env }>): Promise<string> {
  const userId = await authMiddleware(c);
  if (!userId) {
    throw new Response(
      JSON.stringify({ error: { code: "UNAUTHORIZED", message: "Authentication required" } }),
      { status: 401, headers: { "Content-Type": "application/json" } }
    );
  }
  return userId;
}
