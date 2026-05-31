import type { ExecutionTimelineEvent } from "@/types/execution";

export function categorizeActivityLog(
  activityType: string
): ExecutionTimelineEvent["category"] {
  if (
    activityType === "blueprint_created" ||
    activityType === "business_blueprint_saved"
  ) {
    return "blueprint";
  }

  if (
    activityType === "tool_permissions_seeded" ||
    activityType.startsWith("tool_permission_") ||
    activityType.includes("permission")
  ) {
    return "permissions";
  }

  if (
    activityType === "github_repo_created" ||
    activityType === "github_next_scaffold_prepared" ||
    activityType.startsWith("github_")
  ) {
    return "github";
  }

  if (
    activityType === "vercel_project_created" ||
    activityType.startsWith("vercel_")
  ) {
    return "vercel";
  }

  if (
    activityType === "human_action_required" ||
    activityType.startsWith("human_")
  ) {
    return "human";
  }

  if (
    activityType === "validation_workspace_seeded" ||
    activityType === "validation_feedback_added" ||
    activityType === "validation_status_updated" ||
    activityType === "validation_lead_contacted" ||
    activityType.startsWith("validation_")
  ) {
    return "validation";
  }

  if (
    activityType === "research_workspace_generated" ||
    activityType === "research_report_created" ||
    activityType === "research_segment_created" ||
    activityType === "research_buyer_budget_created" ||
    activityType === "research_competitor_created" ||
    activityType === "research_monetization_created" ||
    activityType === "research_distribution_created" ||
    activityType === "research_risk_created" ||
    activityType === "research_hypothesis_created" ||
    activityType === "research_evidence_created" ||
    activityType === "research_status_updated" ||
    activityType.startsWith("research_")
  ) {
    return "research";
  }

  if (activityType.startsWith("system_") || activityType === "agent_activity") {
    return "system";
  }

  return "other";
}
