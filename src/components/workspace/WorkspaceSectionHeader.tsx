import type { ReactNode } from "react";

type WorkspaceSectionHeaderProps = {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
};

export function WorkspaceSectionHeader({
  eyebrow,
  title,
  description,
  children,
}: WorkspaceSectionHeaderProps) {
  return (
    <header className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div className="min-w-0">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
          {eyebrow}
        </p>
        <h2 className="mt-2 break-words text-2xl font-semibold tracking-tight text-foreground">
          {title}
        </h2>
        <p className="mt-2 max-w-3xl break-words text-sm leading-6 text-secondary">
          {description}
        </p>
      </div>
      {children ? <div className="shrink-0">{children}</div> : null}
    </header>
  );
}
