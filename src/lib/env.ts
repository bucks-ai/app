// Fail-fast environment validation for the M1 milestone.
//
// Unlike the per-integration env helpers (src/lib/supabase/env.ts,
// src/lib/github/env.ts, src/lib/vercel/env.ts) which deliberately tolerate
// missing credentials so the app can build/run before those optional
// integrations are configured, the vars validated here are the hard
// baseline the app needs to operate. They are validated once, eagerly,
// at module load — importing this module anywhere throws immediately if
// any of these vars is missing or malformed, listing every problem at once.
import { z } from "zod";

const serverEnvSchema = z.object({
  SUPABASE_URL: z.string().url(),
  SUPABASE_SERVICE_ROLE_KEY: z.string().min(1),
  OPENAI_API_KEY: z.string().min(1),
  GITHUB_TOKEN: z.string().min(1),
  VERCEL_TOKEN: z.string().min(1),
  VERCEL_PROJECT_ID: z.string().min(1),
});

const clientEnvSchema = z.object({
  NEXT_PUBLIC_SUPABASE_URL: z.string().url(),
  NEXT_PUBLIC_SUPABASE_ANON_KEY: z.string().min(1),
});

export type ServerEnv = z.infer<typeof serverEnvSchema>;
export type ClientEnv = z.infer<typeof clientEnvSchema>;

function formatIssues(issues: z.ZodIssue[]): string {
  return issues
    .map((issue) => `  - ${issue.path.join(".") || "(root)"}: ${issue.message}`)
    .join("\n");
}

// Exported for unit testing — validates an arbitrary env-shaped object
// without touching process.env or relying on module-load side effects.
export function validateEnv(source: Record<string, string | undefined>): {
  server: ServerEnv;
  client: ClientEnv;
} {
  const serverResult = serverEnvSchema.safeParse(source);
  const clientResult = clientEnvSchema.safeParse(source);

  if (!serverResult.success || !clientResult.success) {
    const issues = [
      ...(serverResult.success ? [] : serverResult.error.issues),
      ...(clientResult.success ? [] : clientResult.error.issues),
    ];
    throw new Error(
      `Invalid or missing environment variables:\n${formatIssues(issues)}`
    );
  }

  return { server: serverResult.data, client: clientResult.data };
}

const { server, client } = validateEnv(process.env);

// Typed accessors — prefer these over reading process.env directly.
export const serverEnv: ServerEnv = server;
export const clientEnv: ClientEnv = client;
