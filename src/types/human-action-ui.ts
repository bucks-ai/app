// Shared between the Actions tab, the PATCH /api/human-actions/[id] route, and
// the server-side decision writer. Kept out of lib/human-actions.ts so client
// components can import it without reaching a server-only module.

export type HumanActionDecision = "approve" | "dismiss";
