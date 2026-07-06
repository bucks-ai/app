// Shared API error envelope helpers for Next.js App Router route handlers.
// Matches the { ok: false, error, code } shape already used across src/app/api/**/route.ts.

import type { ZodError } from "zod";

export function apiError(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

/** 401 envelope for routes guarded by requireUser() in src/lib/api-auth.ts. */
export function unauthorized(message = "Authentication required.") {
  return apiError(message, "unauthenticated", 401);
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
