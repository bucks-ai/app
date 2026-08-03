"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AuthField } from "@/components/auth/AuthField";
import { AuthShell } from "@/components/auth/AuthShell";
import { createBrowserClient } from "@/lib/supabase/client";

const supabaseConfigured =
  !!process.env.NEXT_PUBLIC_SUPABASE_URL &&
  !!process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") ?? "").trim();
    const password = String(formData.get("password") ?? "");

    const supabase = createBrowserClient();
    if (!supabase) {
      setError("Supabase is not configured. Check your environment variables.");
      setLoading(false);
      return;
    }

    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (authError) {
      setError(authError.message);
      setLoading(false);
      return;
    }

    router.push("/dashboard");
    router.refresh();
  }

  return (
    <AuthShell
      eyebrow="Operator access"
      title="Sign in to"
      titleAccent="Mission Control"
      configured={supabaseConfigured}
      intro={
        supabaseConfigured
          ? "Sign in with your founder account to pick up your active builds where you left them."
          : "This screen is ready for Supabase. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local to enable live auth."
      }
      aside={
        supabaseConfigured ? null : (
          <div className="flow-well mt-8 grid gap-3 p-5">
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              Developer setup required
            </p>
            <p className="font-mono text-xs text-foreground-secondary">
              NEXT_PUBLIC_SUPABASE_URL=
              <br />
              NEXT_PUBLIC_SUPABASE_ANON_KEY=
            </p>
            <p className="text-sm leading-6 text-foreground-secondary">
              Copy .env.example to .env.local and fill in your Supabase project
              credentials. The build will not fail without them.
            </p>
          </div>
        )
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <AuthField
          id="login-email"
          label="Email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="founder@company.com"
          required
        />
        <AuthField
          id="login-password"
          label="Password"
          name="password"
          type="password"
          autoComplete="current-password"
          placeholder="Enter password"
          required
        />
        <button
          type="submit"
          disabled={loading}
          className="min-h-12 w-full rounded-xl bg-accent bg-[image:var(--cta-gradient)] px-4 py-3 text-sm font-semibold text-accent-contrast shadow-[var(--shadow-cta)] transition-transform duration-200 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
        {error ? (
          <p
            role="alert"
            className="rounded-xl border border-error/25 bg-error/10 px-4 py-3 text-sm leading-6 text-error"
          >
            {error}
          </p>
        ) : null}
      </form>

      <div className="mt-7 flex flex-col gap-3 border-t border-edge pt-6 text-sm sm:flex-row sm:items-center sm:justify-between">
        <Link
          href="/signup"
          className="font-medium text-accent transition-colors hover:text-accent-bright"
        >
          Create account
        </Link>
        <Link
          href="/intake"
          className="text-muted-foreground transition-colors hover:text-foreground"
        >
          Back to intake
        </Link>
      </div>
    </AuthShell>
  );
}
