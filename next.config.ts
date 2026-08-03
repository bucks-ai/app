import type { NextConfig } from "next";
import path from "node:path";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  turbopack: {
    root: path.resolve(__dirname),
  },
};

// Source map upload only runs when a Sentry auth token is present (e.g. in
// CI/production). Without it, this is a no-op and `nextConfig` is exported
// unwrapped — no Sentry org/project required, no credentials requested.
const sentryAuthToken = process.env.SENTRY_AUTH_TOKEN;

export default sentryAuthToken
  ? withSentryConfig(nextConfig, {
      org: process.env.SENTRY_ORG,
      project: process.env.SENTRY_PROJECT,
      authToken: sentryAuthToken,
      silent: true,
      disableLogger: true,
    })
  : nextConfig;
