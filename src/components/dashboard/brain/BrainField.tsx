// The decorative half of the brain: cortex silhouette, longitudinal fissure,
// gyri, and the filament mesh. Non-interactive and hidden from assistive tech —
// every real affordance lives in BrainCanvas as a focusable button.
//
// Determinism is load-bearing here. This renders on the server and hydrates on
// the client, so every emitted number must be bit-identical in both. Two rules:
//
//   - No Math.random, and no Math.sin-based hashing. Trig is not guaranteed to
//     agree to the last bit across engines, and an 11th-decimal difference in a
//     path string is a hydration error. The PRNG is integer-only.
//   - Trig output is rounded to integers immediately. Everything downstream is
//     then plain arithmetic on integers, which IEEE-754 makes deterministic.

import { CORE, WORLD_H, WORLD_W } from "./brain-model";

type Point = { x: number; y: number };

/** xorshift-style integer hash. Math.imul is exact 32-bit math everywhere. */
function rand(seed: number) {
  let x = Math.imul(seed ^ 0x9e3779b9, 0x85ebca6b);
  x ^= x >>> 13;
  x = Math.imul(x, 0xc2b2ae35);
  x ^= x >>> 16;
  return (x >>> 0) / 4294967296;
}

/** Shortest angular distance between two angles, in radians. */
function angleGap(a: number, b: number) {
  const diff = Math.abs(a - b) % (Math.PI * 2);
  return diff > Math.PI ? Math.PI * 2 - diff : diff;
}

const RX = 505;
const RY = 395;

/**
 * Top-down cortex outline. An ellipse modulated two ways:
 *   - `cos(9t)` gives the gyri, the lobed edge.
 *   - Gaussian dips at the front (t=0) and back (t=PI) give the longitudinal
 *     fissure notches. Without them the lobed ellipse reads as a cloud, which
 *     is the single thing that separates this shape from a cumulus.
 */
function cortexPoints(scale = 1, phase = 0, steps = 96): Point[] {
  const points: Point[] = [];

  for (let i = 0; i < steps; i += 1) {
    const t = (i / steps) * Math.PI * 2;
    const gyri = 1 + 0.062 * Math.cos(11 * t + phase);
    const frontNotch = 0.22 * Math.exp(-Math.pow(angleGap(t, 0) / 0.26, 2));
    const backNotch = 0.15 * Math.exp(-Math.pow(angleGap(t, Math.PI) / 0.3, 2));
    // Narrower at the front than the back, like a brain seen from above.
    const taper = 1 - 0.08 * Math.cos(t);
    const m = (gyri - frontNotch - backNotch) * taper * scale;

    points.push({
      x: Math.round(CORE.x + Math.sin(t) * RX * m),
      y: Math.round(CORE.y - Math.cos(t) * RY * m),
    });
  }

  return points;
}

/**
 * Closed smooth curve through `points`: start at a midpoint, then use each
 * vertex as the control for a quadratic to the next midpoint. Cheap, stable,
 * and no cusps.
 */
function closedSpline(points: Point[]) {
  const mid = (a: Point, b: Point) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
  const first = mid(points[points.length - 1], points[0]);
  let d = `M ${first.x} ${first.y}`;

  for (let i = 0; i < points.length; i += 1) {
    const current = points[i];
    const next = mid(current, points[(i + 1) % points.length]);
    d += ` Q ${current.x} ${current.y} ${next.x} ${next.y}`;
  }

  return `${d} Z`;
}

const CORTEX_PATH = closedSpline(cortexPoints());

/* Longitudinal fissure, then gyri arcs mirrored across it. Drawn as arcs that
   follow the hemisphere rather than cutting across it. */
const FISSURE = `M ${CORE.x} ${CORE.y - RY * 0.9} Q ${CORE.x - 14} ${CORE.y} ${CORE.x} ${
  CORE.y + RY * 0.92
}`;

/* Gyri as inner contours of the outline itself. Each ring is phase-shifted so
   they do not nest like an onion, which is what turns concentric rings into
   something that reads as folds. */
const GYRI = [0.83, 0.66, 0.49, 0.32].map((scale, index) =>
  closedSpline(cortexPoints(scale, index * 1.4 + 0.7))
);

/* Scatters mesh points inside the cortex. sqrt on the radius keeps the spread
   even instead of clumping at the centre. */
function meshPoints(count: number): Point[] {
  const points: Point[] = [];

  for (let i = 0; i < count; i += 1) {
    const angle = rand(i + 1) * Math.PI * 2;
    const radius = Math.sqrt(rand(i + 97)) * 0.95;
    points.push({
      x: Math.round(CORE.x + Math.cos(angle) * radius * RX),
      y: Math.round(CORE.y + Math.sin(angle) * radius * RY),
    });
  }

  return points;
}

function filaments(points: Point[]) {
  const paths: { d: string; key: string }[] = [];

  points.forEach((from, i) => {
    const near = points
      .map((to, j) => ({
        to,
        j,
        // Squared integer distance — no Math.hypot, and ties break on index so
        // the sort is total rather than implementation-defined.
        d2: (to.x - from.x) ** 2 + (to.y - from.y) ** 2,
      }))
      .filter((entry) => entry.j > i && entry.d2 < 250 ** 2)
      .sort((a, b) => a.d2 - b.d2 || a.j - b.j)
      .slice(0, 3);

    for (const { to, j } of near) {
      const mx = (from.x + to.x) / 2;
      const my = (from.y + to.y) / 2;
      // Bow perpendicular-ish to the chord so the mesh reads as fibres.
      const bow = Math.round((from.y - to.y) * 0.18);
      paths.push({
        key: `${i}-${j}`,
        d: `M ${from.x} ${from.y} Q ${mx + bow} ${my - bow} ${to.x} ${to.y}`,
      });
    }
  });

  return paths;
}

const POINTS = meshPoints(130);
const MESH = filaments(POINTS);

type BrainFieldProps = {
  /** Filaments only animate when real work is in flight. */
  live: boolean;
};

export function BrainField({ live }: BrainFieldProps) {
  return (
    <svg
      aria-hidden
      focusable="false"
      className="brain-field"
      viewBox={`0 0 ${WORLD_W} ${WORLD_H}`}
      width={WORLD_W}
      height={WORLD_H}
    >
      <defs>
        <radialGradient id="brain-core-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--accent-bright)" stopOpacity="0.13" />
          <stop offset="55%" stopColor="var(--accent)" stopOpacity="0.045" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </radialGradient>
        <clipPath id="brain-cortex-clip">
          <path d={CORTEX_PATH} />
        </clipPath>
      </defs>

      <circle cx={CORE.x} cy={CORE.y} r={520} fill="url(#brain-core-glow)" />
      <path d={CORTEX_PATH} className="brain-cortex" />

      {/* Clipped so no filament escapes the silhouette. */}
      <g clipPath="url(#brain-cortex-clip)">
        <g className={`brain-mesh${live ? " is-live" : ""}`}>
          {MESH.map((path) => (
            <path key={path.key} d={path.d} />
          ))}
        </g>

        <g className="brain-synapses">
          {POINTS.filter((_, i) => i % 6 === 0).map((point, i) => (
            <circle key={i} cx={point.x} cy={point.y} r={2.5} />
          ))}
        </g>

        <g className="brain-folds">
          <path d={FISSURE} className="brain-fissure" />
          {GYRI.map((d, index) => (
            <path key={index} d={d} />
          ))}
        </g>
      </g>
    </svg>
  );
}
