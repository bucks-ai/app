import type { ReactNode } from "react";

type BlueprintSectionProps = {
  title: string;
  description?: string;
  children: ReactNode;
};

export function BlueprintSection({
  title,
  description,
  children,
}: BlueprintSectionProps) {
  return (
    <section className="rounded-3xl border border-white/10 bg-white/[0.04] p-6 shadow-[0_20px_80px_rgba(0,0,0,0.22)] backdrop-blur-sm">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-emerald-400/80">
            Mission Control
          </p>
          <h2 className="mt-2 text-xl font-semibold text-white">{title}</h2>
          {description ? (
            <p className="mt-2 max-w-2xl text-sm leading-6 text-neutral-400">
              {description}
            </p>
          ) : null}
        </div>
        <div className="hidden rounded-full border border-emerald-500/20 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300 md:block">
          Live draft
        </div>
      </div>
      {children}
    </section>
  );
}
