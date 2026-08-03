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

type SignupErrors = {
  email?: string;
  password?: string;
  confirmPassword?: string;
};

export default function SignupPage() {
  const router = useRouter();
  const [errors, setErrors] = useState<SignupErrors>({});
  const [authError, setAuthError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAuthError("");
    setSuccessMessage("");

    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") ?? "").trim();
    const password = String(formData.get("password") ?? "");
    const confirmPassword = String(formData.get("confirmPassword") ?? "");

    const nextErrors: SignupErrors = {};
    if (!email) nextErrors.email = "Email is required.";
    if (!password) nextErrors.password = "Password is required.";
    if (password && !confirmPassword)
      nextErrors.confirmPassword = "Confirm your password.";
    if (password && confirmPassword && password !== confirmPassword)
      nextErrors.confirmPassword = "Passwords must match.";

    setErrors(nextErrors);
    if (Object.keys(nextErrors).length > 0) return;

    setLoading(true);

    const supabase = createBrowserClient();
    if (!supabase) {
      setAuthError(
        "Supabase is not configured. Check your environment variables.",
      );
      setLoading(false);
      return;
    }

    const { data, error } = await supabase.auth.signUp({ email, password });

    if (error) {
      setAuthError(error.message);
      setLoading(false);
      return;
    }

    // If a session was created immediately (email confirmation disabled), redirect.
    if (data.session) {
      router.push("/dashboard");
      router.refresh();
      return;
    }

    // Email confirmation required.
    setSuccessMessage(
      `Account created. Check ${email} for a confirmation link before signing in.`,
    );
    setLoading(false);
  }

  return (
    <AuthShell
      eyebrow="Founder account"
      title="Create your"
      titleAccent="operator account"
      configured={supabaseConfigured}
      intro={
        supabaseConfigured
          ? "Create an account to start building your company with bucks.ai."
          : "Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local to enable live signup."
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        <AuthField
          id="signup-email"
          label="Email"
          name="email"
          type="email"
          autoComplete="email"
          placeholder="founder@company.com"
          error={errors.email}
        />
        <AuthField
          id="signup-password"
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          placeholder="Create password"
          error={errors.password}
        />
        <AuthField
          id="signup-confirm-password"
          label="Confirm password"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          placeholder="Repeat password"
          error={errors.confirmPassword}
        />
        <button
          type="submit"
          disabled={loading}
          className="min-h-12 w-full rounded-xl bg-accent bg-[image:var(--cta-gradient)] px-4 py-3 text-sm font-semibold text-accent-contrast shadow-[var(--shadow-cta)] transition-transform duration-200 hover:-translate-y-0.5 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
        >
          {loading ? "Creating account…" : "Create account"}
        </button>
        {authError ? (
          <p
            role="alert"
            className="rounded-xl border border-error/25 bg-error/10 px-4 py-3 text-sm leading-6 text-error"
          >
            {authError}
          </p>
        ) : null}
        {successMessage ? (
          <p
            role="status"
            className="rounded-xl border border-success/25 bg-success/10 px-4 py-3 text-sm leading-6 text-success"
          >
            {successMessage}
          </p>
        ) : null}
      </form>

      <div className="mt-7 border-t border-edge pt-6 text-sm">
        <Link
          href="/login"
          className="font-medium text-accent transition-colors hover:text-accent-bright"
        >
          Already have an account? Sign in
        </Link>
      </div>
    </AuthShell>
  );
}
