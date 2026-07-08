type BackgroundAtmosphereProps = {
  /** aurora bloom strength — hero uses "strong", quiet sections "soft" */
  intensity?: "soft" | "strong";
  /** show the hairline grid layer */
  grid?: boolean;
  /** show the fine noise layer (parent needs position:relative) */
  noise?: boolean;
  /** slow ambient drift on the aurora (CSS-only, killed by reduced-motion) */
  drift?: boolean;
};

const auroras = {
  soft: "radial-gradient(circle at 50% 0%, rgba(109,93,252,0.12), transparent 42%)",
  strong:
    "radial-gradient(circle at 28% 35%, rgba(109,93,252,0.24), transparent 36%), radial-gradient(circle at 72% 24%, rgba(34,211,238,0.08), transparent 34%)",
};

/**
 * Shared section atmosphere: aurora bloom + hairline grid + noise, all
 * pointer-transparent and low-contrast so text stays AA on top. Pure CSS —
 * the drift animation lives in globals.css behind prefers-reduced-motion.
 */
export function BackgroundAtmosphere({
  intensity = "soft",
  grid = true,
  noise = false,
  drift = false,
}: BackgroundAtmosphereProps) {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className={`absolute left-1/2 top-0 h-[34rem] w-[72rem] -translate-x-1/2 rounded-full opacity-75 blur-3xl ${
          drift ? "ambient-orbit" : ""
        }`}
        style={{ background: auroras[intensity] }}
      />
      {grid ? <div className="grid-backdrop absolute inset-0 opacity-50" /> : null}
      {noise ? <div className="noise-backdrop absolute inset-0" /> : null}
    </div>
  );
}
