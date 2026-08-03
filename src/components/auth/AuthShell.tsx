import type { ReactNode } from "react";
import { Footer } from "@/components/shared/Footer";
import { Navbar } from "@/components/shared/Navbar";
import { PageField } from "@/components/ui/PageField";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

type AuthShellProps = {
  eyebrow: string;
  /** Plain part of the headline. */
  title: string;
  /** Emphasised tail, set in the serif italic. Optional. */
  titleAccent?: string;
  intro: string;
  configured: boolean;
  children: ReactNode;
  /** Extra content under the intro copy (e.g. the env-setup hint). */
  aside?: ReactNode;
};

/**
 * Shared frame for /login and /signup.
 *
 * These two pages had drifted into separate copies of the same layout, each
 * hardcoding indigo (#4F46E5) and near-black (#080808) rather than reading
 * tokens — so the auth screens showed a purple CTA directly beneath the teal
 * navbar CTA, and stayed dark even in light mode. Sharing one shell means
 * they cannot disagree again.
 */
export function AuthShell({
  eyebrow,
  title,
  titleAccent,
  intro,
  configured,
  children,
  aside,
}: AuthShellProps) {
  return (
    <div className="theme-transition">
      <Navbar />
      <PageField />
      <main id="main-content" className="relative min-h-screen px-5 pb-24 pt-32 sm:px-6">
        <div className="relative mx-auto grid min-h-[calc(100vh-14rem)] max-w-6xl items-center">
          <div className="grid items-center gap-14 lg:grid-cols-[0.95fr_1.05fr] lg:gap-20">
            <div className="reveal is-visible">
              <div className="flex flex-wrap items-center gap-3">
                <SectionLabel>{eyebrow}</SectionLabel>
                <StatusPill
                  label={configured ? "Live auth" : "Not configured"}
                  variant={configured ? "success" : "warning"}
                />
              </div>
              <h1 className="display-lg text-balance mt-6 max-w-[13ch] text-5xl text-foreground sm:text-6xl">
                {title}
                {titleAccent ? (
                  <>
                    {" "}
                    <span className="display-accent">{titleAccent}</span>
                  </>
                ) : null}
              </h1>
              <p className="mt-6 max-w-md text-base leading-8 text-foreground-secondary">
                {intro}
              </p>
              {aside}
            </div>

            <div className="flow-card p-7 shadow-[var(--shadow-float)] sm:p-9">
              {children}
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
