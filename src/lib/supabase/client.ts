// Browser-side Supabase client.
// Safe to import in client components — only uses public env vars.
// Uses @supabase/ssr so auth tokens are stored in cookies (not just localStorage),
// allowing server components to read the session via createSupabaseServerClient.

import { createBrowserClient as createSSRBrowserClient } from "@supabase/ssr";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

// Returns null when env vars are absent so the build succeeds without real credentials.
export function createBrowserClient() {
  if (!url || !anonKey) return null;
  return createSSRBrowserClient(url, anonKey);
}
