"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { LOBES } from "@/components/dashboard/brain/brain-model";

/**
 * The chrome that replaced WorkspaceSidebar.
 *
 * The sidebar was a flat ten-item list with 01-10 markers — an index asserting
 * that every region is a peer, one click away. That is precisely the surface
 * that made the Brain a doorway rather than a navigation system, so it is gone.
 *
 * What is here instead is scoped to one region:
 *   - a breadcrumb back through the Brain, at the zoom level each crumb owns,
 *   - the leaves of THIS region only,
 *   - nothing that names another region.
 *
 * Reaching Deploy from Research means climbing back out to the Brain and
 * descending again. That climb is the product, not friction to be optimised
 * away — it is what makes position mean something.
 */

export type RegionShellProps = {
  businessId: string;
  businessName: string;
  regionKey: string;
  /** Anchor id of the leaf currently in view, from ?section=. */
  activeSection: string | null;
  children: ReactNode;
};

/** Where the Brain sits when you back out to a given crumb. */
export function brainHref(focusId?: string) {
  return focusId ? `/dashboard?focus=${encodeURIComponent(focusId)}` : "/dashboard";
}

export function regionHref(
  businessId: string,
  regionTab: string,
  section?: string
) {
  const query = new URLSearchParams({ tab: regionTab });
  if (section) query.set("section", section);
  return `/dashboard/businesses/${businessId}?${query.toString()}`;
}

export function RegionShell({
  businessId,
  businessName,
  regionKey,
  activeSection,
  children,
}: RegionShellProps) {
  const lobe = LOBES.find((entry) => entry.tab === regionKey);

  return (
    <div className="region-shell">
      <header className="region-header">
        {/* Same position and behaviour as the Brain's own breadcrumb, so the
            crumb does not move when you cross from canvas to content. */}
        <nav aria-label="Location" className="region-crumbs">
          <Link href={brainHref()} className="region-crumb">
            Brain
          </Link>
          <span aria-hidden className="region-crumb-sep">
            /
          </span>
          <Link href={brainHref(businessId)} className="region-crumb">
            {businessName}
          </Link>
          {lobe ? (
            <>
              <span aria-hidden className="region-crumb-sep">
                /
              </span>
              <Link
                href={brainHref(`${businessId}:${lobe.key}`)}
                className="region-crumb"
                aria-current="page"
              >
                {lobe.label}
              </Link>
            </>
          ) : null}
        </nav>

        {lobe ? (
          <div className="region-title-block">
            <h1 className="region-title">{lobe.label}</h1>
            <p className="region-detail">{lobe.detail}</p>
          </div>
        ) : null}

        {/* Leaves of this region only. Regions with no addressable sections
            render no sub-nav rather than an empty rail pretending to be one. */}
        {lobe && lobe.leaves.length > 0 ? (
          <nav aria-label={`${lobe.label} sections`} className="region-leaves">
            {lobe.leaves.map((leaf) => {
              const isActive = leaf.section === activeSection;
              return (
                <Link
                  key={leaf.key}
                  href={regionHref(businessId, lobe.tab, leaf.section)}
                  className="region-leaf"
                  aria-current={isActive ? "true" : undefined}
                  data-active={isActive ? "true" : undefined}
                >
                  {leaf.label}
                </Link>
              );
            })}
          </nav>
        ) : null}
      </header>

      <div className="region-body">{children}</div>

      <footer className="region-foot">
        <Link href={brainHref(businessId)} className="region-exit">
          <span aria-hidden>&#8598;</span>
          Back to {businessName} in the Brain
        </Link>
      </footer>
    </div>
  );
}
