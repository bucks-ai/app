import { GlassPanel } from "@/components/ui/GlassPanel";
import { StatusPill } from "@/components/ui/StatusPill";

export type ToolTileData = {
  name: string;
  role: string;
  access: "Connected" | "Approval gated" | "Read only" | "Preview";
  signal: string;
};

function variantForAccess(access: ToolTileData["access"]) {
  if (access === "Connected") return "success" as const;
  if (access === "Approval gated") return "warning" as const;
  return "neutral" as const;
}

export function ToolTile({
  tool,
  className = "",
}: {
  tool: ToolTileData;
  className?: string;
}) {
  return (
    <GlassPanel interactive variant="elevated" className={`p-4 ${className}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
            Tool
          </p>
          <h3 className="mt-2 text-base font-semibold text-foreground">{tool.name}</h3>
        </div>
        <StatusPill label={tool.access} variant={variantForAccess(tool.access)} />
      </div>
      <p className="mt-3 text-sm leading-6 text-foreground-secondary">{tool.role}</p>
      <p className="mt-4 border-t border-border/70 pt-3 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
        Signal: <span className="text-foreground-secondary">{tool.signal}</span>
      </p>
    </GlassPanel>
  );
}
