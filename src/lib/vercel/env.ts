// Server-side Vercel environment helpers.
// Never imported from client components.
// Safe to import without env vars — will not throw at module load time.

export function hasVercelEnv(): boolean {
  return Boolean(process.env.VERCEL_TOKEN);
}

export function getVercelEnv(): { token: string; teamId: string | undefined } {
  const token = process.env.VERCEL_TOKEN;
  if (!token) {
    throw new Error(
      "VERCEL_TOKEN is not set. Add it to .env.local."
    );
  }
  return {
    token,
    teamId: process.env.VERCEL_TEAM_ID || undefined,
  };
}

export function getVercelSetupMessage(): string {
  if (hasVercelEnv()) return "Vercel token is configured.";
  return (
    "Vercel token is not configured. " +
    "Add VERCEL_TOKEN to .env.local to enable Vercel project creation."
  );
}
