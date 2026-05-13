"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { Footer } from "@/components/shared/Footer";
import { Navbar } from "@/components/shared/Navbar";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

export default function LoginPage() {
  const [message, setMessage] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setMessage("Auth wiring comes next. This screen is ready for Supabase.");
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
                <SectionLabel>Operator access</SectionLabel>
                <StatusPill label="Frontend only" variant="neutral" />
              </div>
              <h1 className="mt-5 text-4xl font-semibold tracking-tight text-[#F0F0F0] sm:text-5xl">
                Sign in to Mission Control.
              </h1>
              <p className="mt-5 max-w-xl text-base leading-8 text-[#888888]">
                This shell is ready for account-backed startup builds, but no
                live authentication is connected on this branch.
              </p>
              <div className="mt-8 grid gap-3 rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
                <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
                  Integration state
                </p>
                <p className="text-sm leading-6 text-[#D4D4D4]">
                  Supabase auth, sessions, and protected routes are intentionally
                  deferred to the backend integration step.
                </p>
              </div>
            </div>

            <OperatorPanel className="p-6 shadow-[0_30px_140px_rgba(0,0,0,0.38)] sm:p-8">
              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <SectionLabel tone="muted">Email</SectionLabel>
                  <input
                    type="email"
                    name="email"
                    autoComplete="email"
                    className="mt-2 w-full rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-3 text-sm text-[#F0F0F0] outline-none transition-colors placeholder:text-[#444444] focus:border-[#4F46E5]"
                    placeholder="founder@company.com"
                  />
                </div>
                <div>
                  <SectionLabel tone="muted">Password</SectionLabel>
                  <input
                    type="password"
                    name="password"
                    autoComplete="current-password"
                    className="mt-2 w-full rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-3 text-sm text-[#F0F0F0] outline-none transition-colors placeholder:text-[#444444] focus:border-[#4F46E5]"
                    placeholder="Enter password"
                  />
                </div>
                <button
                  type="submit"
                  className="w-full rounded-md bg-[#4F46E5] px-4 py-3 text-sm font-semibold text-[#F0F0F0] transition-colors hover:bg-[#6366F1]"
                >
                  Sign in
                </button>
                {message ? (
                  <p className="rounded-md border border-[#4F46E5]/30 bg-[#4F46E5]/10 px-4 py-3 text-sm leading-6 text-[#C7D2FE]">
                    {message}
                  </p>
                ) : null}
              </form>

              <div className="mt-6 flex flex-col gap-3 border-t border-[#1C1C1C] pt-5 text-sm sm:flex-row sm:items-center sm:justify-between">
                <Link
                  href="/signup"
                  className="font-medium text-[#A5B4FC] transition-colors hover:text-[#C7D2FE]"
                >
                  Create account
                </Link>
                <Link
                  href="/intake"
                  className="text-[#888888] transition-colors hover:text-[#F0F0F0]"
                >
                  Back to intake
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
