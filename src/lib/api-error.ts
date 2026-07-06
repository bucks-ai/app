// Shared API error envelope helpers for Next.js App Router route handlers.
// Matches the { ok: false, error, code } shape already used across src/app/api/**/route.ts.

export function apiError(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

/** 401 envelope for routes guarded by requireUser() in src/lib/api-auth.ts. */
export function unauthorized(message = "Authentication required.") {
  return apiError(message, "unauthenticated", 401);
}
