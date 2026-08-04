type SoftObjectProps = {
  /** Rendered size in rem. */
  size?: number;
  className?: string;
  /** Drift speed in seconds. 0 disables the float. */
  drift?: number;
  /**
   * Varies the form between instances: rotates the silhouette and moves the
   * key light. Deliberately does NOT change hue — the palette is one teal
   * family, so variety comes from shape and lighting, not from introducing a
   * second brand colour.
   */
  seed?: number;
};

/**
 * An inflated, glossy blob — the "soft against structure" motif.
 *
 * Built from an SVG lighting filter rather than WebGL. The trick is that
 * `feGaussianBlur` on `SourceAlpha` produces a soft alpha ramp, and
 * `feSpecularLighting` then reads that ramp as a BUMP MAP: flat where the
 * shape is transparent, raised where it is opaque. A point light over that
 * surface gives the rounded-over-the-edge highlight that reads as inflation.
 *
 * Two hard constraints, both performance:
 *
 *  1. SVG filters are rasterized on the main thread and are NOT composited.
 *     So the filter is applied once, to a fixed-size element, and neither
 *     the filter parameters nor the element's dimensions ever animate.
 *     Only `transform` moves — that stays on the compositor.
 *  2. The filter region is deliberately tight. Cost scales with blur radius
 *     times layer area, which is the same failure mode as an animated blur.
 *
 * Limits worth knowing: there is no real geometry here, so no perspective,
 * self-shadowing, or refraction. It holds up as a static hero ornament at a
 * fixed viewing angle. If this ever needs to rotate or be lit dynamically,
 * bake it in Blender/Spline and ship a WebP with alpha instead.
 */
export function SoftObject({
  size = 22,
  className = "",
  drift = 9,
  seed = 0,
}: SoftObjectProps) {
  // Filter ids are document-global. Several of these render on one page, so a
  // fixed id would make every instance reuse whichever filter mounted first.
  // Derived from the seed rather than useId() so this stays a server
  // component and the markup is stable across SSR and hydration.
  const fid = `soft-inflate-${seed}`;
  const gid = `soft-body-${seed}`;
  const rotate = (seed % 4) * 22 - 33;
  const lightX = 58 + ((seed * 13) % 26) - 13;
  const lightY = 30 + ((seed * 7) % 18) - 9;

  return (
    <div
      aria-hidden
      className={`pointer-events-none select-none ${className}`}
      style={{
        width: `${size}rem`,
        height: `${size}rem`,
        animation:
          drift > 0 ? `soft-float ${drift}s ease-in-out infinite` : undefined,
      }}
    >
      <svg
        viewBox="0 0 200 200"
        style={{ transform: `rotate(${rotate}deg)` }}
        width="100%"
        height="100%"
        role="presentation"
        focusable="false"
      >
        <defs>
          <filter
            id={fid}
            x="-25%"
            y="-25%"
            width="150%"
            height="150%"
            colorInterpolationFilters="sRGB"
          >
            {/* The alpha ramp that becomes the bump map. Kept tight: a wide
                blur rounds the silhouette off into a plain sphere and loses
                the organic shape entirely. */}
            <feGaussianBlur in="SourceAlpha" stdDeviation="4.5" result="ramp" />

            {/* Broad body light — reads as rounded rather than flat. */}
            <feSpecularLighting
              in="ramp"
              surfaceScale="4"
              specularConstant="0.55"
              specularExponent="14"
              lightingColor="var(--soft-object-light)"
              result="body"
            >
              <fePointLight x={lightX} y={lightY + 8} z="120" />
            </feSpecularLighting>

            {/* Tight hotspot — this is the whole "wet/glossy" read. A high
                exponent concentrates it; a low one just fogs the surface. */}
            <feSpecularLighting
              in="ramp"
              surfaceScale="6"
              specularConstant="1.9"
              specularExponent="95"
              lightingColor="#ffffff"
              result="gloss"
            >
              <fePointLight x={lightX + 16} y={lightY} z="62" />
            </feSpecularLighting>

            {/* Clip both lighting passes back to the shape. */}
            <feComposite in="body" in2="SourceAlpha" operator="in" result="body" />
            <feComposite in="gloss" in2="SourceAlpha" operator="in" result="gloss" />

            {/* Specular light is ADDITIVE — it has to be summed onto the
                surface, not alpha-composited over it. feMerge does normal
                compositing, which is why merging a specular pass reads as a
                flat matte wash instead of a highlight. `arithmetic` with
                k2=k3=1 is the add. */}
            <feComposite
              in="SourceGraphic"
              in2="body"
              operator="arithmetic"
              k1="0"
              k2="1"
              k3="1"
              k4="0"
              result="lit"
            />
            <feComposite
              in="lit"
              in2="gloss"
              operator="arithmetic"
              k1="0"
              k2="1"
              k3="1"
              k4="0"
              result="shiny"
            />
            {/* The adds can push alpha past the silhouette; clip once more. */}
            <feComposite in="shiny" in2="SourceAlpha" operator="in" />
          </filter>

          <radialGradient id={gid} cx="36%" cy="30%" r="78%">
            <stop offset="0%" stopColor="var(--soft-object-hi)" />
            <stop offset="55%" stopColor="var(--soft-object-mid)" />
            <stop offset="100%" stopColor="var(--soft-object-lo)" />
          </radialGradient>
        </defs>

        {/* A soft, slightly irregular silhouette — a perfect circle reads as
            a button, not an object. */}
        <path
          filter={`url(#${fid})`}
          fill={`url(#${gid})`}
          d="M100 18c30 0 46 12 58 30s24 34 18 58-28 34-48 46-42 16-62 6-34-30-40-52 2-46 18-62S70 18 100 18Z"
        />
      </svg>
    </div>
  );
}
