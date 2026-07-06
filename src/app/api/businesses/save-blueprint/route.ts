import { NextRequest } from "next/server";
import {
  createAgentActivityLog,
  createBusiness,
  createHumanRequiredActionsFromBlueprint,
  saveBusinessBlueprint,
} from "@/lib/projects";
import {
  seedToolPermissionsForBusiness,
  createToolPermissionActivityLog,
} from "@/lib/tool-permissions";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import { requireUser } from "@/lib/api-auth";
import { badRequest, zodIssuesToFields } from "@/lib/api-error";
import { saveBlueprintBodySchema } from "@/lib/schemas/save-blueprint";

function errorResponse(error: string, code: string, status: number) {
  return Response.json({ ok: false, error, code }, { status });
}

export async function POST(request: NextRequest) {
  if (!hasSupabaseEnv()) {
    return errorResponse(
      "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local.",
      "supabase_not_configured",
      503
    );
  }

  const { user, response } = await requireUser();
  if (!user) return response;

  let json: unknown;
  try {
    json = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.", "invalid_json");
  }

  const parsed = saveBlueprintBodySchema.safeParse(json);
  if (!parsed.success) {
    return badRequest(
      "Request body failed validation.",
      "validation_error",
      zodIssuesToFields(parsed.error),
    );
  }

  const { startupIdea, blueprint } = parsed.data;

  const businessResult = await createBusiness({
    user_id: user.id,
    idea_name: startupIdea.ideaName,
    one_line_idea: startupIdea.oneLineIdea,
    idea_description: startupIdea.ideaDescription,
    target_customer: startupIdea.targetCustomer,
    business_type: blueprint.businessType ?? startupIdea.businessTypeGuess,
    primary_goal: startupIdea.primaryGoal,
    success_metric: startupIdea.successMetric,
    budget: startupIdea.budget,
    timeline: startupIdea.timeline,
    autonomy_preference: startupIdea.autonomyPreference,
    spending_limit: startupIdea.spendingLimit,
    hard_constraints: startupIdea.hardConstraints,
    human_only_actions: startupIdea.humanOnlyActions,
    forbidden_actions: startupIdea.forbiddenActions,
    preferred_tools: startupIdea.preferredTools,
    status: "blueprint_created",
  });

  if (businessResult.error || !businessResult.data) {
    return errorResponse(
      businessResult.error ?? "Failed to create business.",
      "business_create_failed",
      500
    );
  }

  const business = businessResult.data;
  const blueprintResult = await saveBusinessBlueprint({
    business_id: business.id,
    user_id: user.id,
    blueprint: blueprint as unknown as Record<string, unknown>,
  });

  if (blueprintResult.error || !blueprintResult.data) {
    return errorResponse(
      blueprintResult.error ?? "Failed to save blueprint.",
      "blueprint_save_failed",
      500
    );
  }

  const actionsResult = await createHumanRequiredActionsFromBlueprint(
    business.id,
    user.id,
    blueprint as unknown as Record<string, unknown>
  );

  if (actionsResult.error || !actionsResult.data) {
    return errorResponse(
      actionsResult.error ?? "Failed to create human-required actions.",
      "human_actions_create_failed",
      500
    );
  }

  const activityResult = await createAgentActivityLog({
    business_id: business.id,
    user_id: user.id,
    activity_type: "blueprint_created",
    message: "Generated launch blueprint and saved business project.",
    metadata: {
      ideaName: startupIdea.ideaName,
      businessType: blueprint.businessType ?? startupIdea.businessTypeGuess,
    },
  });

  if (activityResult.error || !activityResult.data) {
    return errorResponse(
      activityResult.error ?? "Failed to create activity log.",
      "activity_log_create_failed",
      500
    );
  }

  // Seed tool permissions — soft failure: a seed error does not fail the blueprint save.
  let toolPermissionWarning: string | undefined;
  const seedResult = await seedToolPermissionsForBusiness(business.id, user.id);
  if (seedResult.error) {
    toolPermissionWarning = `Tool permission setup could not be initialised: ${seedResult.error}`;
  } else if (seedResult.data && seedResult.data.seeded > 0) {
    await createToolPermissionActivityLog({
      business_id: business.id,
      user_id: user.id,
      activity_type: "tool_permissions_seeded",
      message: "Created initial tool permission setup queue.",
      metadata: {
        seeded: seedResult.data.seeded,
        skipped: seedResult.data.skipped,
      },
    });
  }

  return Response.json(
    {
      ok: true,
      businessId: business.id,
      detailUrl: `/dashboard/businesses/${business.id}`,
      ...(toolPermissionWarning ? { toolPermissionWarning } : {}),
    },
    { status: 200 }
  );
}
