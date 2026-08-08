// The brain's tree without the canvas, for viewports below lg.
//
// Pan-and-zoom on a phone means drag-to-discover, which fails the
// "gesture-alternative" rule: critical navigation must have visible controls.
// This renders the identical node tree as nested disclosures, so a touch or
// keyboard user reaches every destination the canvas reaches — same hrefs,
// same order, no second source of truth.

import Link from "next/link";
import { LOBES, type BrainBusiness, type BrainNode } from "./brain-model";

type BrainOutlineProps = {
  nodes: BrainNode[];
  businesses: BrainBusiness[];
};

export function BrainOutline({ nodes, businesses }: BrainOutlineProps) {
  const byId = new Map(nodes.map((node) => [node.id, node]));

  return (
    <div className="brain-outline lg:hidden">
      <div className="brain-outline-actions">
        <Link href="/intake" className="brain-action is-primary">
          New business
        </Link>
        <Link href="/tools" className="brain-action">
          Tool registry
        </Link>
      </div>

      {businesses.length === 0 ? (
        <p className="brain-outline-empty">
          No businesses yet. Start one and its brain appears here.
        </p>
      ) : null}

      {businesses.map((business) => (
        <details key={business.id} className="brain-outline-business">
          <summary>
            <span className="brain-outline-name">{business.name}</span>
            <span className="brain-outline-detail">{business.detail}</span>
            {business.approvals > 0 ? (
              <span className="brain-outline-count">
                {business.approvals} need{business.approvals === 1 ? "s" : ""} you
              </span>
            ) : null}
          </summary>

          <ul className="brain-outline-lobes">
            {LOBES.map((lobe) => {
              const lobeNode = byId.get(`${business.id}:${lobe.key}`);
              if (!lobeNode) return null;

              // Lobes with no third level are links, matching the canvas.
              // No href means no row — a "#" fallback would render exactly the
              // dead link this whole tree is built to avoid.
              if (lobe.leaves.length === 0) {
                if (!lobeNode.href) return null;
                return (
                  <li key={lobe.key}>
                    <Link href={lobeNode.href} className="brain-outline-leaf">
                      <span>{lobe.label}</span>
                      <span className="brain-outline-detail">{lobe.detail}</span>
                    </Link>
                  </li>
                );
              }

              return (
                <li key={lobe.key}>
                  <details className="brain-outline-lobe">
                    <summary>
                      <span>{lobe.label}</span>
                      <span className="brain-outline-detail">{lobe.detail}</span>
                    </summary>
                    <ul>
                      {lobe.leaves.map((leaf) => {
                        const leafNode = byId.get(
                          `${business.id}:${lobe.key}:${leaf.key}`
                        );
                        if (!leafNode?.href) return null;
                        return (
                          <li key={leaf.key}>
                            <Link href={leafNode.href} className="brain-outline-leaf">
                              <span>{leaf.label}</span>
                              <span className="brain-outline-detail">
                                {leaf.detail}
                              </span>
                            </Link>
                          </li>
                        );
                      })}
                    </ul>
                  </details>
                </li>
              );
            })}
          </ul>
        </details>
      ))}
    </div>
  );
}
