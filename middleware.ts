import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

// Content-Security-Policy is shipped in Report-Only mode: it reports
// violations without blocking anything, so it can be tightened safely once
// we've reviewed real report data. connect-src includes the configured
// Supabase origin (rather than a hard-coded one) so it tracks whichever
// project the deployment actually points at.
function buildContentSecurityPolicy(): string {
  const connectSrc = ["'self'"];
  if (url) {
    try {
      const supabaseOrigin = new URL(url).origin;
      connectSrc.push(supabaseOrigin, supabaseOrigin.replace(/^http/, "ws"));
    } catch {
      // Malformed NEXT_PUBLIC_SUPABASE_URL — fall back to 'self' only.
    }
  }
  connectSrc.push(
    "https://*.posthog.com",
    "https://*.i.posthog.com",
    "https://*.ingest.sentry.io",
    "https://*.ingest.us.sentry.io",
    "https://vitals.vercel-insights.com",
    "https://*.vercel-insights.com",
  );

  return [
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' https://*.posthog.com https://vercel.live https://va.vercel-scripts.com",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob: https:",
    "font-src 'self' data:",
    `connect-src ${connectSrc.join(" ")}`,
    "frame-src 'self' https://vercel.live",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");
}

function applySecurityHeaders(response: NextResponse): NextResponse {
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set(
    "Content-Security-Policy-Report-Only",
    buildContentSecurityPolicy(),
  );
  return response;
}

export async function middleware(request: NextRequest) {
  // If Supabase is not configured, pass through without touching cookies.
  if (!url || !anonKey) {
    return applySecurityHeaders(NextResponse.next({ request }));
  }

  let response = NextResponse.next({ request });

  // Create a Supabase client that can read and write session cookies on the
  // request/response cycle. This is the only supported pattern for middleware.
  const supabase = createServerClient(url, anonKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        // Write updated cookies back to both the outgoing request and response
        // so that Server Components in this request see the refreshed session.
        cookiesToSet.forEach(({ name, value }) =>
          request.cookies.set(name, value),
        );
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options),
        );
      },
    },
  });

  // Calling getUser() refreshes the session token if it has expired.
  // The README advises using getUser() (not getSession()) for server-side auth.
  await supabase.auth.getUser();

  return applySecurityHeaders(response);
}

export const config = {
  matcher: [
    /*
     * Run on all paths except:
     * - _next/static  (static files)
     * - _next/image   (image optimisation)
     * - favicon.ico
     * - public assets with a file extension
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
