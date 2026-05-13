// Server-side auth helpers — only call in Server Components, Route Handlers, or Server Actions.

import { createSupabaseServerClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

/** Returns the authenticated user, or null if no session. */
export async function getAuthenticatedUser() {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return null;
  const { data } = await supabase.auth.getUser();
  return data.user ?? null;
}

/**
 * Returns the authenticated user or redirects to /login.
 * Use in Server Components that require authentication.
 */
export async function requireAuthenticatedUser() {
  const user = await getAuthenticatedUser();
  if (!user) redirect("/login");
  return user;
}
