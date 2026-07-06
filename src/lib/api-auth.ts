// Shared route auth guard for Next.js App Router route handlers.
// Not yet wired into any route — see src/lib/api-error.ts for the 401 envelope shape.

import type { User } from "@supabase/supabase-js";
import { getAuthenticatedUser } from "@/lib/auth";
import { unauthorized } from "@/lib/api-error";

type RequireUserResult =
  | { user: User; response: null }
  | { user: null; response: Response };

/**
 * Resolves the authenticated Supabase user from the request cookies.
 * Use at the top of a route handler:
 *
 *   const { user, response } = await requireUser();
 *   if (!user) return response;
 */
export async function requireUser(): Promise<RequireUserResult> {
  const user = await getAuthenticatedUser();
  if (!user) return { user: null, response: unauthorized() };
  return { user, response: null };
}
