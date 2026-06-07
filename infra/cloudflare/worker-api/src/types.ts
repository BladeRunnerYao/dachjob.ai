/**
 * Cloudflare Worker environment bindings.
 */
export interface Env {
  DB: D1Database;
  STORAGE: R2Bucket;
  JWT_SECRET: string;
  LLM_API_KEY: string;
  APP_ENV: string;
  JWT_EXPIRY_HOURS: string;
  CORS_ORIGIN: string;
  DEEPSEEK_MODEL?: string;
  DACHJOB_IMPORT_PARSED_TOKEN?: string;
  DACHJOB_IMPORT_PARSED_USER_ID?: string;
}

export interface JwtPayload {
  sub: string;
  email: string;
  iat: number;
  exp: number;
}
