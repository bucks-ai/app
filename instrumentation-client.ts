import * as Sentry from "@sentry/nextjs";

// Guard on the public DSN so this is a complete no-op — no SDK init, no
// network calls — in environments where Sentry isn't configured.
const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    tracesSampleRate: 0.1,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
  });
}
