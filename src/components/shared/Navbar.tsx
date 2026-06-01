"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createBrowserClient } from "@/lib/supabase/client";
import { LogoutButton } from "@/components/auth/LogoutButton";
import { ThemeToggle } from "@/components/shared/ThemeToggle";

export function Navbar() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const supabase = createBrowserClient();

    async function initAuth() {
      if (!supabase) {
        setIsAuthenticated(false);
        return;
      }
      const { data } = await supabase.auth.getSession();
      setIsAuthenticated(!!data.session);
    }

    initAuth();

    if (!supabase) return;

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setIsAuthenticated(!!session);
    });

    return () => subscription.unsubscribe();
  }, []);

  return (
    <nav
      className="fixed left-0 right-0 top-0 z-50 border-b border-border backdrop-blur-md"
      style={{ background: "var(--surface-glass)" }}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-4 sm:px-6">
        <Link
          href="/"
          className="text-lg font-semibold tracking-tight text-foreground"
        >
          bucks<span className="text-accent">.ai</span>
        </Link>
        <div className="flex items-center gap-3 sm:gap-5">
          {isAuthenticated && (
            <Link
              href="/dashboard"
              className="hidden text-sm text-secondary transition-colors hover:text-foreground md:inline"
            >
              Dashboard
            </Link>
          )}
          <Link
            href="/tools"
            className="text-sm text-secondary transition-colors hover:text-foreground"
          >
            Tools
          </Link>
          <Link
            href="/#how-it-works"
            className="hidden text-sm text-secondary transition-colors hover:text-foreground sm:inline"
          >
            How it works
          </Link>
          {isAuthenticated ? (
            <LogoutButton />
          ) : (
            <Link
              href="/login"
              className="text-sm text-secondary transition-colors hover:text-foreground"
            >
              Sign in
            </Link>
          )}
          <ThemeToggle />
          <Link
            href="/intake"
            className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-accent-contrast transition-colors hover:bg-accent-hover sm:px-4"
          >
            <span className="hidden sm:inline">Start building</span>
            <span className="sm:hidden">Start</span>
          </Link>
        </div>
      </div>
    </nav>
  );
}
