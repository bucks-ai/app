"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { Footer } from "@/components/shared/Footer";
import { Navbar } from "@/components/shared/Navbar";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

type SignupErrors = {
  email?: string;
  password?: string;
  confirmPassword?: string;
};

export default function SignupPage() {
  const [message, setMessage] = useState("");
  const [errors, setErrors] = useState<SignupErrors>({});

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") ?? "").trim();
    const password = String(formData.get("password") ?? "");
    const confirmPassword = String(formData.get("confirmPassword") ?? "");
    const nextErrors: SignupErrors = {};

    if (!email) {
      nextErrors.email = "Email is required.";
    }

    if (!password) {
      nextErrors.password = "Password is required.";
    }

    if (password && confirmPassword && password !== confirmPassword) {
      nextErrors.confirmPassword = "Passwords must match.";
    }

    if (password && !confirmPassword) {
      nextErrors.confirmPassword = "Confirm your password.";
    }

    setErrors(nextErrors);
    setMessage("");

    if (Object.keys(nextErrors).length === 0) {
      setMessage(
        "Account creation will be wired to Supabase in the backend integration step.",
      );
    }
  }

  return (
    <>
      <Navbar />
      <main className="relative min-h-screen overflow-hidden bg-[#080808] px-5 pb-20 pt-28 sm:px-6">
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              "linear-gradient(rgba(79,70,229,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(79,70,229,0.025) 1px, transparent 1px)",
            backgroundSize: "64px 64px",
          }}
        />
        <div className="relative mx-auto grid min-h-[calc(100vh-11rem)] max-w-6xl items-center">
          <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
            <div>
              <div className="flex flex-wrap items-center gap-3">
                <SectionLabel>Founder account</SectionLabel>
                <StatusPill label="Supabase next" variant="warning" />
              </div>
              <h1 className="mt-5 text-4xl font-semibold tracking-tight text-[#F0F0F0] sm:text-5xl">
                Create the account shell.
              </h1>
              <p className="mt-5 max-w-xl text-base leading-8 text-[#888888]">
                This form validates locally so the interface is ready for the
                auth handoff. It does not create a real user yet.
              </p>
            </div>

            <OperatorPanel className="p-6 shadow-[0_30px_140px_rgba(0,0,0,0.38)] sm:p-8">
              <form onSubmit={handleSubmit} className="space-y-5" noValidate>
                <div>
                  <SectionLabel tone="muted">Email</SectionLabel>
                  <input
                    type="email"
                    name="email"
                    autoComplete="email"
                    className="mt-2 w-full rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-3 text-sm text-[#F0F0F0] outline-none transition-colors placeholder:text-[#444444] focus:border-[#4F46E5]"
                    placeholder="founder@company.com"
                    aria-describedby={errors.email ? "signup-email-error" : undefined}
                  />
                  {errors.email ? (
                    <p id="signup-email-error" className="mt-2 text-sm text-[#FCA5A5]">
                      {errors.email}
                    </p>
                  ) : null}
                </div>
                <div>
                  <SectionLabel tone="muted">Password</SectionLabel>
                  <input
                    type="password"
                    name="password"
                    autoComplete="new-password"
                    className="mt-2 w-full rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-3 text-sm text-[#F0F0F0] outline-none transition-colors placeholder:text-[#444444] focus:border-[#4F46E5]"
                    placeholder="Create password"
                    aria-describedby={
                      errors.password ? "signup-password-error" : undefined
                    }
                  />
                  {errors.password ? (
                    <p id="signup-password-error" className="mt-2 text-sm text-[#FCA5A5]">
                      {errors.password}
                    </p>
                  ) : null}
                </div>
                <div>
                  <SectionLabel tone="muted">Confirm password</SectionLabel>
                  <input
                    type="password"
                    name="confirmPassword"
                    autoComplete="new-password"
                    className="mt-2 w-full rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-3 text-sm text-[#F0F0F0] outline-none transition-colors placeholder:text-[#444444] focus:border-[#4F46E5]"
                    placeholder="Repeat password"
                    aria-describedby={
                      errors.confirmPassword
                        ? "signup-confirm-password-error"
                        : undefined
                    }
                  />
                  {errors.confirmPassword ? (
                    <p
                      id="signup-confirm-password-error"
                      className="mt-2 text-sm text-[#FCA5A5]"
                    >
                      {errors.confirmPassword}
                    </p>
                  ) : null}
                </div>
                <button
                  type="submit"
                  className="w-full rounded-md bg-[#4F46E5] px-4 py-3 text-sm font-semibold text-[#F0F0F0] transition-colors hover:bg-[#6366F1]"
                >
                  Create account
                </button>
                {message ? (
                  <p className="rounded-md border border-[#4F46E5]/30 bg-[#4F46E5]/10 px-4 py-3 text-sm leading-6 text-[#C7D2FE]">
                    {message}
                  </p>
                ) : null}
              </form>

              <div className="mt-6 border-t border-[#1C1C1C] pt-5 text-sm">
                <Link
                  href="/login"
                  className="font-medium text-[#A5B4FC] transition-colors hover:text-[#C7D2FE]"
                >
                  Already have an account? Sign in
                </Link>
              </div>
            </OperatorPanel>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
