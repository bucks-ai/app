"use client";

import posthog from "@/app/posthog";
import { capture } from "@/lib/analytics/client";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, Suspense } from "react";
import { PostHogProvider as PHProvider } from "posthog-js/react";

function PostHogPageView() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (pathname) {
      let url = window.origin + pathname;
      const search = searchParams?.toString();
      if (search) url += `?${search}`;
      capture("$pageview", { $current_url: url });
    }
  }, [pathname, searchParams]);

  return null;
}

export default function PostHogProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <PHProvider client={posthog}>
      <Suspense fallback={null}>
        <PostHogPageView />
      </Suspense>
      {children}
    </PHProvider>
  );
}
