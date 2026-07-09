// Public signup endpoint — the single authoritative point where a new
// account first exists. Intentionally unauthenticated (see
// PUBLIC_ROUTE_ALLOWLIST in src/app/api/route-auth-inventory.test.ts): there
// is no user to authenticate yet.
//
// Runs supabase.auth.signUp() through the request-bound SSR client (not the
// browser client) so the resulting session cookie, if any, is set directly
// on the response — the client no longer talks to Supabase auth directly.
// This is also why user_signed_up is captured server-side here instead of
// client-side: it's the only point that can tell a brand-new account from a
// duplicate signup on an already-registered, confirmed email (Supabase
// returns an obfuscated user with an empty `identities` array in that case,
// see @supabase/auth-js's signUp() docs — no account was created, so no
// event fires).

import { NextRequest } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { apiError, badRequest, zodIssuesToFields } from "@/lib/api-error";
import { signupBodySchema } from "@/lib/schemas/signup";
import { limit, tooManyRequests, RATE_LIMITS } from "@/lib/rate-limit";
import { capture } from "@/lib/analytics/server";

export async function POST(request: NextRequest) {
  if (!hasSupabaseEnv()) {
    return apiError(
      "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local.",
      "supabase_not_configured",
      503,
    );
  }

  const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unknown";
  const rateLimitResult = await limit(`signup:${ip}`, RATE_LIMITS.authSignup);
  if (!rateLimitResult.allowed) return tooManyRequests();

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = signupBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }

  const { email, password } = parsed.data;

  const supabase = await createSupabaseServerClient();
  if (!supabase) {
    return apiError(
      "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local.",
      "supabase_not_configured",
      503,
    );
  }

  const { data, error } = await supabase.auth.signUp({ email, password });

  if (error) {
    return badRequest(error.message, "signup_failed");
  }

  // An existing, confirmed account re-submitting signUp gets an obfuscated
  // user back with no identities — no account was actually created.
  const accountCreated = Boolean(data.user && data.user.identities && data.user.identities.length > 0);

  if (accountCreated && data.user) {
    capture(
      "USER_SIGNED_UP",
      { id: data.user.id, email: data.user.email },
      { signup_method: "email" },
    );
  }

  return Response.json({ ok: true, hasSession: Boolean(data.session), email }, { status: 200 });
}
