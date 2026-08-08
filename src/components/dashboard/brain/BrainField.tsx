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

import { CORE, CORTEX_RX, CORTEX_RY, WORLD_H, WORLD_W } from "./brain-model";

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

const RX = CORTEX_RX;
const RY = CORTEX_RY;

/**
 * Top-down cortex outline, `t` measured from the frontal pole.
 *
 * The outline is deliberately SMOOTH. An earlier version modulated it with
 * `cos(11t)`, which put eleven evenly-spaced equal-amplitude scallops around
 * the edge — that is the signature of a cloud, and it read as one. A real
 * cortex from above has only three macro-features, and they are all here:
 * a deep cleft at the frontal pole, a shallower one at the occipital pole,
 * and temporal bulges at the widest point. Fold texture belongs on the
 * inside, not on the silhouette (see GYRI).
 */
function cortexPoints(scale = 1, steps = 128): Point[] {
  const points: Point[] = [];

  for (let i = 0; i < steps; i += 1) {
    const t = (i / steps) * Math.PI * 2;

    // The longitudinal fissure entering front and back. Narrow and deep, so
    // the shape cleaves into two hemispheres instead of merely denting.
    const frontCleft = 0.15 * Math.exp(-Math.pow(angleGap(t, 0) / 0.24, 2));
    const backCleft = 0.12 * Math.exp(-Math.pow(angleGap(t, Math.PI) / 0.2, 2));

    // Widest behind the middle, narrowing toward the frontal pole.
    const taper = 1 - 0.1 * Math.cos(t);
    // Temporal lobes: a slight swell either side, below the equator.
    const temporal =
      0.055 *
      (Math.exp(-Math.pow(angleGap(t, Math.PI * 0.62) / 0.42, 2)) +
        Math.exp(-Math.pow(angleGap(t, Math.PI * 1.38) / 0.42, 2)));

    const m = (1 - frontCleft - backCleft + temporal) * taper * scale;

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

/* The longitudinal fissure, running the full front-to-back axis. This is the
   line that makes the shape bilateral rather than radial. */
const FISSURE = `M ${CORE.x} ${Math.round(CORE.y - RY * 0.82)}
  C ${CORE.x - 16} ${Math.round(CORE.y - RY * 0.4)}
    ${CORE.x + 16} ${Math.round(CORE.y + RY * 0.4)}
    ${CORE.x} ${Math.round(CORE.y + RY * 0.86)}`;

/**
 * Gyri, one hemisphere at a time and mirrored across the fissure.
 *
 * The previous version drew closed contours of the whole outline at
 * decreasing scale. Sharing one centre made them read as a topographic map —
 * ripples around a peak — rather than as folds. Real gyri are elongated bands
 * running roughly front-to-back within a hemisphere, turning back on
 * themselves at the midline. These are C-curves that open toward the fissure,
 * which is what gives the shape its brain-ness.
 */
function gyriPaths(): string[] {
  const paths: string[] = [];

  for (const side of [-1, 1]) {
    for (let band = 0; band < 5; band += 1) {
      // How far out from the midline this band sits.
      const spread = 0.2 + band * 0.17;
      const points: Point[] = [];

      // Sweep front to back down one hemisphere.
      for (let i = 0; i <= 40; i += 1) {
        const u = i / 40;
        const t = -0.78 + u * 1.56 * Math.PI * 0.62;
        // Belly out from the midline in the middle, tuck back in at the poles,
        // so each band closes toward the fissure at both ends like a real fold.
        const belly = Math.sin(u * Math.PI);
        const wobble = 1 + 0.16 * Math.sin(u * Math.PI * (3 + band));

        points.push({
          x: Math.round(CORE.x + side * spread * RX * belly * wobble),
          y: Math.round(CORE.y - Math.cos(t) * RY * (0.34 + band * 0.11) * wobble),
        });
      }

      let d = `M ${points[0].x} ${points[0].y}`;
      for (let i = 1; i < points.length - 1; i += 1) {
        const next = {
          x: (points[i].x + points[i + 1].x) / 2,
          y: (points[i].y + points[i + 1].y) / 2,
        };
        d += ` Q ${points[i].x} ${points[i].y} ${next.x} ${next.y}`;
      }
      paths.push(d);
    }
  }

  return paths;
}

const GYRI = gyriPaths();

/* Scatters mesh points inside the cortex. sqrt on the radius keeps the spread
   even instead of clumping at the centre. */
function meshPoints(count: number): Point[] {
  const points: Point[] = [];

  for (let i = 0; i < count; i += 1) {
    const angle = rand(i + 1) * Math.PI * 2;
    const radius = Math.sqrt(rand(i + 97)) * 0.95;
    points.push({
      x: Math.round(CORE.x + Math.cos(angle) * radius * RX * 0.96),
      y: Math.round(CORE.y + Math.sin(angle) * radius * RY * 0.96),
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
      .filter((entry) => entry.j > i && entry.d2 < 300 ** 2)
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

const POINTS = meshPoints(190);
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

      <circle cx={CORE.x} cy={CORE.y} r={RY} fill="url(#brain-core-glow)" />
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
