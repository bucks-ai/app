import type { ResearchDistributionChannelRecord } from "@/types/research-ui";
import { ResearchStatusBadge } from "@/components/research/ResearchStatusBadge";

type DistributionChannelsPanelProps = {
  channels: ResearchDistributionChannelRecord[];
};

function score(value: number | null) {
  return value === null ? "--" : `${value}/10`;
}

export function DistributionChannelsPanel({
  channels,
}: DistributionChannelsPanelProps) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
          Distribution channels
        </p>
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
          {channels.length} channels
        </span>
      </div>

      <div className="mt-3 grid gap-2 lg:grid-cols-3">
        {channels.length > 0 ? (
          channels.map((channel) => (
            <div key={channel.id} className="min-w-0 rounded border border-border bg-background p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="break-words text-sm font-semibold text-foreground">
                    {channel.channel}
                  </p>
                  <p className="mt-1 break-words text-xs leading-5 text-secondary">
                    {channel.description ?? "Description not captured."}
                  </p>
                </div>
                <ResearchStatusBadge value={channel.priority} />
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2">
                {[
                  ["Speed", score(channel.speed_score)],
                  ["Cost", score(channel.cost_score)],
                  ["Hard", score(channel.difficulty_score)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded border border-border bg-surface p-2">
                    <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
                      {label}
                    </p>
                    <p className="mt-1 text-xs font-semibold text-secondary">{value}</p>
                  </div>
                ))}
              </div>
              <p className="mt-3 break-words text-xs leading-5 text-secondary">
                {channel.reasoning ?? "Reasoning not captured."}
              </p>
            </div>
          ))
        ) : (
          <p className="rounded border border-border bg-background px-3 py-4 text-sm text-muted">
            No distribution channels yet.
          </p>
        )}
      </div>
    </div>
  );
}
