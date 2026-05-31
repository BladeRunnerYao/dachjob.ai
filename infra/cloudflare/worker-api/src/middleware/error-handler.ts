import { Context } from "hono";
import { Env } from "../types";

export class AppError extends Error {
  constructor(
    public code: string,
    message: string,
    public statusCode: number = 400,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = "AppError";
  }
}

export function errorHandler(err: Error, c: Context<{ Bindings: Env }>) {
  if (err instanceof AppError) {
    return c.json(
      {
        error: {
          code: err.code,
          message: err.message,
          ...(err.details ? { details: err.details } : {}),
        },
      },
      err.statusCode as 400
    );
  }

  console.error("Unhandled error:", err.message, err.stack);
  return c.json(
    { error: { code: "INTERNAL_ERROR", message: "An unexpected error occurred" } },
    500
  );
}
