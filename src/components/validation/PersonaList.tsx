import type { ValidationPersonaRecord } from "@/types/validation-ui";
import { ValidationStatusBadge } from "@/components/validation/ValidationStatusBadge";

type PersonaListProps = {
  personas: ValidationPersonaRecord[];
};

function InlineList({ items }: { items: string[] | null }) {
  if (!items || items.length === 0) {
    return <span className="text-muted">Not captured</span>;
  }

  return (
    <span className="text-secondary">
      {items.slice(0, 3).join(", ")}
      {items.length > 3 ? ` +${items.length - 3}` : ""}
    </span>
  );
}

export function PersonaList({ personas }: PersonaListProps) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
          Personas
        </p>
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
          {personas.length} total
        </span>
      </div>

      <div className="mt-3 grid gap-2 lg:grid-cols-2">
        {personas.length > 0 ? (
          personas.map((persona) => (
            <div
              key={persona.id}
              className="min-w-0 rounded border border-border bg-background p-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-foreground">
                    {persona.name}
                  </p>
                  <p className="mt-0.5 truncate text-xs text-muted">
                    {persona.segment ?? "Segment not set"}
                  </p>
                </div>
                <ValidationStatusBadge value={persona.priority} />
              </div>

              <div className="mt-3 space-y-2 text-xs leading-5">
                <p>
                  <span className="font-mono uppercase tracking-widest text-muted">
                    Pain
                  </span>{" "}
                  <InlineList items={persona.pain_points} />
                </p>
                <p>
                  <span className="font-mono uppercase tracking-widest text-muted">
                    Outcomes
                  </span>{" "}
                  <InlineList items={persona.desired_outcomes} />
                </p>
                <p>
                  <span className="font-mono uppercase tracking-widest text-muted">
                    Channels
                  </span>{" "}
                  <InlineList items={persona.channels} />
                </p>
                <p>
                  <span className="font-mono uppercase tracking-widest text-muted">
                    WTP
                  </span>{" "}
                  <span className="text-secondary">
                    {persona.willingness_to_pay ?? "Not captured"}
                  </span>
                </p>
              </div>
            </div>
          ))
        ) : (
          <p className="rounded border border-border bg-background px-3 py-4 text-sm text-muted">
            No personas yet.
          </p>
        )}
      </div>
    </div>
  );
}
