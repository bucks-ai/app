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

  if (activityType.startsWith("system_") || activityType === "agent_activity") {
    return "system";
  }

  return "other";
}
