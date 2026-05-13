// Server-side GitHub environment helpers.
// Never imported from client components.
// Safe to import without env vars — will not throw at module load time.

export function hasGitHubEnv(): boolean {
  return Boolean(process.env.GITHUB_PERSONAL_ACCESS_TOKEN);
}

export function getGitHubEnv(): { token: string; defaultOwner: string | undefined } {
  const token = process.env.GITHUB_PERSONAL_ACCESS_TOKEN;
  if (!token) {
    throw new Error(
      "GITHUB_PERSONAL_ACCESS_TOKEN is not set. Add it to .env.local."
    );
  }
  return {
    token,
    defaultOwner: process.env.GITHUB_DEFAULT_OWNER || undefined,
  };
}

export function getGitHubSetupMessage(): string {
  if (hasGitHubEnv()) return "GitHub token is configured.";
  return (
    "GitHub token is not configured. " +
    "Add GITHUB_PERSONAL_ACCESS_TOKEN to .env.local to enable repo creation."
  );
}
