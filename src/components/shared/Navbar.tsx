"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createBrowserClient } from "@/lib/supabase/client";
import { LogoutButton } from "@/components/auth/LogoutButton";
import { ThemeToggle } from "@/components/shared/ThemeToggle";

export function Navbar() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [isScrolled, setIsScrolled] = useState(false);

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

  useEffect(() => {
    const onScroll = () => setIsScrolled(window.scrollY > 18);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <nav
      // Named so it is distinguishable from the dashboard's "Brain location"
      // nav when a screen reader lists landmarks.
      aria-label="Main"
      className={`fixed left-0 right-0 top-0 z-50 transition-all duration-200 ${
        isScrolled
          ? "bg-background/40"
          : "bg-transparent"
      }`}
    >
      <div
        className={`glass-surface mx-3 mt-3 flex max-w-6xl items-center justify-between gap-3 rounded-card px-3 transition-all duration-200 sm:mx-auto sm:px-5 ${
          isScrolled ? "py-2.5" : "py-3.5"
        }`}
      >
        <Link
          href="/"
          className="inline-flex min-h-11 items-center font-display text-lg font-semibold tracking-tight text-foreground"
        >
          bucks<span className="text-accent">.ai</span>
        </Link>
        <div className="flex min-w-0 items-center gap-2 sm:gap-4">
          {isAuthenticated && (
            <Link
              href="/dashboard"
              className="hidden min-h-11 items-center text-sm text-foreground-secondary transition-colors hover:text-foreground md:inline-flex"
            >
              Dashboard
            </Link>
          )}
          <Link
            href="/tools"
            className="hidden min-h-11 items-center text-sm text-foreground-secondary transition-colors hover:text-foreground sm:inline-flex"
          >
            Tools
          </Link>
          <Link
            href="/#execution-flow"
            className="hidden min-h-11 items-center text-sm text-foreground-secondary transition-colors hover:text-foreground sm:inline-flex"
          >
            Execution flow
          </Link>
          {isAuthenticated ? (
            <LogoutButton />
          ) : (
            <Link
              href="/login"
              className="hidden min-h-11 items-center whitespace-nowrap text-sm text-foreground-secondary transition-colors hover:text-foreground sm:inline-flex"
            >
              Sign in
            </Link>
          )}
          <ThemeToggle />
          <Link
            href="/dashboard"
            className="inline-flex min-h-11 cursor-pointer items-center rounded-lg border border-white/10 bg-accent bg-[image:var(--cta-gradient)] px-3 py-2 text-sm font-semibold text-accent-contrast shadow-[var(--shadow-cta)] transition-transform duration-200 hover:-translate-y-0.5 sm:px-4"
          >
            <span className="hidden sm:inline">Enter console</span>
            <span className="sm:hidden">Console</span>
          </Link>
        </div>
      </div>
    </nav>
  );
}
