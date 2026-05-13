// IMPORTANT: This client uses the service role key and bypasses Row Level Security.
// NEVER import this in client components or expose it to the browser.
// Only use in Route Handlers, Server Actions, or scripts that run server-side.

import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY ?? "";

// Returns null when env vars are absent so the build succeeds without real credentials.
// Note: not typed with <Database> — types are applied at the call site via `as` casts.
// Use the Supabase CLI (`supabase gen types`) to generate fully typed clients once connected.
export function createAdminClient() {
  if (!url || !serviceRoleKey) return null;
  return createClient(url, serviceRoleKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
}
