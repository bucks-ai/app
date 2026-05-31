import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";

export type WorkspaceActionTarget =
  | "overview"
  | "research"
  | "actions"
  | "build"
  | "deploy"
  | "validation"
  | "tools"
  | "activity"
  | "settings";

export type PrimaryWorkspaceAction = {
  label: string;
  description: string;
  target: WorkspaceActionTarget;
  urgency: "critical" | "high" | "medium" | "low";
  reason:
    | "critical_blocker"
    | "human_required"
    | "github_approval"
    | "create_github_repo"
    | "prepare_scaffold"
    | "vercel_approval"
    | "create_vercel_project"
    | "failed_run"
    | "run_research_mode"
    | "review_opportunity_score"
    | "promote_research_hypothesis"
    | "review_pivot_risk"
    | "customer_validation"
    | "review_activity";
};

function permissionIsReady(status?: string | null) {
  return (
    status === "approved" ||
    status === "approved_by_founder" ||
    status === "connected_demo" ||
    status === "ready_to_connect"
  );
}

function findPermission(business: DashboardBusiness, toolId: string) {
  return business.toolPermissions?.find((permission) => permission.toolId === toolId);
}

function hasApprovalNeed(status?: string | null) {
  return (
    status === "approval_requested" ||
    status === "human_required" ||
    status === "not_connected" ||
    status === "blocked" ||
    status === "rejected"
  );
}

function eventLooksFailed(status?: string | null, title?: string | null) {
  const text = `${status ?? ""} ${title ?? ""}`.toLowerCase();
  return (
    text.includes("fail") ||
    text.includes("error") ||
    text.includes("blocked") ||
    text.includes("rejected")
  );
}

export function resolvePrimaryNextAction(
  business: DashboardBusiness,
  executionStatus?: BusinessExecutionStatus | null
): PrimaryWorkspaceAction {
  const criticalBlocker = executionStatus?.blockers?.find(
    (blocker) => blocker.severity === "critical" || blocker.severity === "blocked"
  );
  if (criticalBlocker) {
    return {
      label: criticalBlocker.title,
      description: criticalBlocker.description ?? "Resolve the blocker before execution can continue.",
      target: "actions",
      urgency: "critical",
      reason: "critical_blocker",
    };
  }

  const humanAction = business.humanActionItems?.[0] ?? null;
  if (humanAction) {
    return {
      label: humanAction.title,
      description: humanAction.reason,
      target: "actions",
      urgency: "critical",
      reason: "human_required",
    };
  }

  const researchAction = executionStatus?.nextActions?.find((action) =>
    [
      "run_research_mode",
      "review_opportunity_score",
      "validate_highest_risk_assumption",
      "move_research_hypotheses_to_validation",
    ].includes(action.id)
  );
  if (researchAction) {
    const moveToValidation = researchAction.id === "move_research_hypotheses_to_validation";

    return {
      label: researchAction.title,
      description:
        researchAction.description ??
        "Open Research Mode and continue mapping the opportunity.",
      target: moveToValidation ? "validation" : "research",
      urgency: researchAction.priority === "high" ? "high" : "medium",
      reason: moveToValidation ? "promote_research_hypothesis" : "run_research_mode",
    };
  }

  const researchGenerated = business.activityLogs?.some(
    (log) => log.activityType === "research_workspace_generated"
  );
  const researchReportCreated = business.activityLogs?.some(
    (log) => log.activityType === "research_report_created"
  );
  const researchHypothesisCreated = business.activityLogs?.some(
    (log) => log.activityType === "research_hypothesis_created"
  );
  const lowOpportunitySignal = business.activityLogs?.some((log) => {
    const metadata = log.metadata as Record<string, unknown> | null | undefined;
    const score = metadata?.opportunityScore ?? metadata?.opportunity_score;
    return typeof score === "number" && score < 45;
  });

  if (!researchGenerated && business.blueprintSummary) {
    return {
      label: "Run research mode",
      description: "Generate the research workspace to map opportunity, competitors, and risks.",
      target: "research",
      urgency: "medium",
      reason: "run_research_mode",
    };
  }

  if (lowOpportunitySignal) {
    return {
      label: "Review pivot risk",
      description: "The opportunity score looks weak; review research before pushing deeper into build.",
      target: "research",
      urgency: "high",
      reason: "review_pivot_risk",
    };
  }

  if (researchGenerated && !researchReportCreated) {
    return {
      label: "Review opportunity score",
      description: "Set or review the opportunity score before validation begins.",
      target: "research",
      urgency: "medium",
      reason: "review_opportunity_score",
    };
  }

  if (researchHypothesisCreated) {
    return {
      label: "Move hypotheses to validation",
      description: "Promote the riskiest research hypothesis into Customer Validation.",
      target: "validation",
      urgency: "medium",
      reason: "promote_research_hypothesis",
    };
  }

  const githubPermission = findPermission(business, "github");
  const githubStatus = githubPermission?.setupStatus ?? githubPermission?.status;
  if (githubPermission && hasApprovalNeed(githubStatus) && !permissionIsReady(githubStatus)) {
    return {
      label: "Approve GitHub access",
      description: "GitHub needs founder approval before bucks.ai can create or update repository assets.",
      target: "tools",
      urgency: "high",
      reason: "github_approval",
    };
  }

  if (!business.githubRepo) {
    return {
      label: "Create GitHub repo",
      description: "Create the source repository so build automation has a target.",
      target: "build",
      urgency: "high",
      reason: "create_github_repo",
    };
  }

  const scaffoldMilestone = executionStatus?.milestones?.find(
    (milestone) => milestone.id === "scaffold"
  );
  if (!scaffoldMilestone || scaffoldMilestone.status !== "complete") {
    return {
      label: "Prepare Next.js scaffold",
      description: "Generate the starter app files inside the GitHub repository.",
      target: "build",
      urgency: "medium",
      reason: "prepare_scaffold",
    };
  }

  const vercelPermission = findPermission(business, "vercel");
  const vercelStatus = vercelPermission?.setupStatus ?? vercelPermission?.status;
  if (vercelPermission && hasApprovalNeed(vercelStatus) && !permissionIsReady(vercelStatus)) {
    return {
      label: "Approve Vercel access",
      description: "Vercel must be approved before bucks.ai creates deployment infrastructure.",
      target: "tools",
      urgency: "high",
      reason: "vercel_approval",
    };
  }

  if (!business.vercelProject) {
    return {
      label: "Create Vercel project",
      description: "Connect the prepared repository to Vercel.",
      target: "deploy",
      urgency: "medium",
      reason: "create_vercel_project",
    };
  }

  const failedRun = executionStatus?.timeline?.find((event) =>
    eventLooksFailed(event.status, event.title)
  );
  if (failedRun) {
    return {
      label: "Review latest failed run",
      description: failedRun.title,
      target: "activity",
      urgency: "high",
      reason: "failed_run",
    };
  }

  const validationAction = executionStatus?.nextActions?.find((action) =>
    [
      "setup_validation_workspace",
      "add_first_five_leads",
      "record_first_feedback_note",
      "review_validation_signal",
      "start_customer_validation",
    ].includes(action.id)
  );
  if (validationAction) {
    return {
      label: validationAction.title,
      description:
        validationAction.description ??
        "Open Customer Validation and continue the demand signal workflow.",
      target: "validation",
      urgency: validationAction.priority === "high" ? "high" : "medium",
      reason: "customer_validation",
    };
  }

  if (business.vercelProject?.deploymentUrl) {
    return {
      label: "Set up validation workspace",
      description: "Use the live deployment and saved assets to begin customer validation.",
      target: "validation",
      urgency: "medium",
      reason: "customer_validation",
    };
  }

  return {
    label: "Review activity",
    description: "Check recent execution history and choose the next operating move.",
    target: "activity",
    urgency: "low",
    reason: "review_activity",
  };
}
