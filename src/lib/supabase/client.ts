// Browser-side Supabase client.
// Safe to import in client components — only uses public env vars.

import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

// Returns null when env vars are absent so the build succeeds without real credentials.
// Note: not typed with <Database> — types are applied at the call site via `as` casts.
// Use the Supabase CLI (`supabase gen types`) to generate fully typed clients once connected.
export function createBrowserClient() {
  if (!url || !anonKey) return null;
  return createClient(url, anonKey);
}
