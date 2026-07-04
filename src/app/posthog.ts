import posthog from "posthog-js";

if (typeof window !== "undefined") {
  posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY!, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
    ui_host: "https://us.posthog.com",
    capture_pageview: false, // handled manually via PostHogPageView
    capture_pageleave: true,
  });
}

export default posthog;
