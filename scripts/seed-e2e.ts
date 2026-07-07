// Seeds (or resets) the dedicated E2E test user and its demo business.
//
// Usage: npm run seed:e2e
//
// Reads TEST_USER_EMAIL / TEST_USER_PASSWORD plus the Supabase service-role
// credentials from the environment (loads .env.local via dotenv). Idempotent:
// re-running deletes and recreates the demo business data for that one test
// user, and never touches any other user's rows.

import "dotenv/config";
import { createClient } from "@supabase/supabase-js";
import { seedE2E } from "../src/lib/seed-e2e";

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    console.error(`Missing required env var: ${name}`);
    process.exit(1);
  }
  return value;
}

async function main() {
  if (process.env.NODE_ENV === "production") {
    console.error("Refusing to run scripts/seed-e2e.ts with NODE_ENV=production.");
    process.exit(1);
  }

  const url = requireEnv("NEXT_PUBLIC_SUPABASE_URL");
  const serviceRoleKey = requireEnv("SUPABASE_SERVICE_ROLE_KEY");
  const email = requireEnv("TEST_USER_EMAIL");
  const password = requireEnv("TEST_USER_PASSWORD");

  const admin = createClient(url, serviceRoleKey, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  const { userId, businessId } = await seedE2E(admin, { email, password });

  console.log(`Seeded E2E test user ${email} (${userId}) with demo business ${businessId}.`);
}

main().catch((error) => {
  console.error("seed-e2e failed:", error instanceof Error ? error.message : error);
  process.exit(1);
});
