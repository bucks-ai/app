// Shared API error envelope helpers for Next.js App Router route handlers.
// Matches the { ok: false, error, code } shape already used across src/app/api/**/route.ts.

import * as Sentry from "@sentry/nextjs";
import type { ZodError } from "zod";

export function apiError(
  error: string,
  code: string,
  status: number,
  extra?: Record<string, unknown>,
) {
  return Response.json({ ok: false, error, code, ...(extra ?? {}) }, { status });
}

/**
 * 500 envelope for uncaught server errors. Reports the exception to Sentry
 * when SENTRY_DSN is configured; a complete no-op otherwise (no network calls).
 */
export function serverError(
  error: unknown,
  message = "Something went wrong. Please try again.",
) {
  if (process.env.SENTRY_DSN) {
    Sentry.captureException(error);
  }
  return apiError(message, "internal_error", 500);
}

/** 401 envelope for routes guarded by requireUser() in src/lib/api-auth.ts. */
export function unauthorized(message = "Authentication required.") {
  return apiError(message, "unauthenticated", 401);
}

/** 404 envelope for routes looking up a resource that does not exist or isn't owned by the caller. */
export function notFound(message: string, code = "not_found") {
  return apiError(message, code, 404);
}

/** 502 envelope for routes rejecting an AI-generated response that failed schema validation. */
export function aiOutputInvalid(message = "The AI returned a response that failed validation.") {
  return apiError(message, "AI_OUTPUT_INVALID", 502);
}

/** 400 envelope for routes validating request bodies with zod's safeParse(). */
export function badRequest(
  message: string,
  code: string,
  issues?: Record<string, string[]>,
) {
  return Response.json(
    { ok: false, error: message, code, ...(issues ? { issues } : {}) },
    { status: 400 },
  );
}

/** Groups a ZodError's issues by field path for the badRequest() envelope. */
export function zodIssuesToFields(error: ZodError): Record<string, string[]> {
  const fields: Record<string, string[]> = {};
  for (const issue of error.issues) {
    const key = issue.path.length ? issue.path.join(".") : "_body";
    (fields[key] ??= []).push(issue.message);
  }
  return fields;
}
