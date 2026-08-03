type BackgroundAtmosphereProps = {
  /** local bloom strength — hero uses "strong", quiet sections "soft" */
  intensity?: "soft" | "strong";
  /** show the hairline grid layer (usually off — PageField owns the grid) */
  grid?: boolean;
  /** show the fine noise layer (parent needs position:relative) */
  noise?: boolean;
  /** slow ambient drift on the bloom (CSS-only, killed by reduced-motion) */
  drift?: boolean;
};

/*
  These used to be indigo (rgba(109,93,252)) and cyan, left over from an
  earlier palette — which is why teal CTAs sat on a purple glow. They are
  now derived from --accent so the atmosphere can never drift off-brand.
*/
const auroras = {
  soft: "radial-gradient(circle at 50% 0%, color-mix(in srgb, var(--accent) 14%, transparent), transparent 46%)",
  strong:
    "radial-gradient(circle at 30% 34%, color-mix(in srgb, var(--accent) 22%, transparent), transparent 40%), radial-gradient(circle at 72% 22%, color-mix(in srgb, var(--accent-deep) 20%, transparent), transparent 38%)",
};

/**
 * A *local* accent bloom for one section — used sparingly, on top of the
 * page-wide <PageField />. Sections should not use this to establish their
 * own background; that is what produced the banded, choppy read.
 *
 * All layers are pointer-transparent and low-contrast so text stays AA.
 */
export function BackgroundAtmosphere({
  intensity = "soft",
  grid = false,
  noise = false,
  drift = false,
}: BackgroundAtmosphereProps) {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <div
        className={`absolute left-1/2 top-0 h-[34rem] w-[72rem] -translate-x-1/2 rounded-full opacity-70 blur-3xl ${
          drift ? "ambient-orbit" : ""
        }`}
        style={{ background: auroras[intensity] }}
      />
      {grid ? <div className="grid-backdrop absolute inset-0 opacity-50" /> : null}
      {noise ? <div className="noise-backdrop absolute inset-0" /> : null}
    </div>
  );
}
