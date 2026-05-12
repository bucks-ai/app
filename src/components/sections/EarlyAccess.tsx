"use client";

import { useState } from "react";

export function EarlyAccess() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    // TODO: wire to backend (Supabase / Resend) when auth is integrated
    setSubmitted(true);
  }

  return (
    <section
      id="early-access"
      className="relative overflow-hidden bg-black px-6 py-28 text-center"
    >
      {/* Glow */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 70% 60% at 50% 100%, rgba(16,185,129,0.12) 0%, transparent 70%)",
        }}
      />

      <div className="relative z-10 mx-auto max-w-2xl">
        <h2 className="mb-4 text-3xl font-bold tracking-tight text-white sm:text-4xl">
          Get early access
        </h2>
        <p className="mb-10 text-neutral-400">
          We&apos;re onboarding a small group of founders first. Join the list
          to be among the first to launch with bucks.ai.
        </p>

        {submitted ? (
          <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-8 py-6">
            <p className="font-semibold text-emerald-400">
              You&apos;re on the list.
            </p>
            <p className="mt-1 text-sm text-neutral-400">
              We&apos;ll reach out when your spot opens up.
            </p>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit}
            className="flex flex-col items-center gap-3 sm:flex-row sm:justify-center"
          >
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@startup.com"
              className="w-full rounded-full border border-white/20 bg-white/5 px-5 py-3 text-sm text-white placeholder-neutral-500 outline-none transition-colors focus:border-emerald-500/60 sm:w-80"
            />
            <button
              type="submit"
              className="w-full rounded-full bg-emerald-500 px-7 py-3 text-sm font-semibold text-black transition-colors hover:bg-emerald-400 sm:w-auto"
            >
              Request access
            </button>
          </form>
        )}

        <p className="mt-6 text-xs text-neutral-600">
          No spam. No BS. Just an invite when you&apos;re up.
        </p>
      </div>
    </section>
  );
}
