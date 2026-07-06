import * as Sentry from "@sentry/nextjs";

// Guard on the DSN so this is a complete no-op in environments (local dev, CI,
// preview builds) where Sentry isn't configured — no network calls, no errors.
const dsn = process.env.SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    tracesSampleRate: 0.1,
  });
}
