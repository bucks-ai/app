import type { Metadata } from "next";
import { ToolRegistryPage } from "@/components/tools/ToolRegistryPage";

export const metadata: Metadata = {
  title: "Tool Registry | bucks.ai",
  description:
    "Review bucks.ai's preferred tool stack, extended registry, risk and setup status, and the default autonomy constitution.",
};

export default function ToolsPage() {
  return <ToolRegistryPage />;
}
