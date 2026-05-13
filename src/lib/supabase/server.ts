// Server-side Supabase client for Next.js App Router.
// Uses @supabase/ssr to read/write auth cookies on the server.
// Only call this in Server Components, Route Handlers, or Server Actions.

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

// Returns null when env vars are absent so the build succeeds without real credentials.
// Note: not typed with <Database> — types are applied at the call site via `as` casts.
// Use the Supabase CLI (`supabase gen types`) to generate fully typed clients once connected.
export async function createSupabaseServerClient() {
  if (!url || !anonKey) return null;

  const cookieStore = await cookies();

  return createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options)
          );
        } catch {
          // setAll is called from Server Components where cookies are read-only.
          // Safe to ignore — middleware handles session refresh.
        }
      },
    },
  });
}
