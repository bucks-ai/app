// Research Node — server-side helpers.
//
// All public functions require an authenticated user and verify business
// ownership before reading or writing data.
//
// Safe to call when supabase/research.sql has not yet been applied —
// returns error code "research_schema_missing" in that case so the API
// layer can return a helpful message without crashing.
//
// This module is the data rail that future Research Node agents
// (Market Research Agent, Customer Segment Agent, Competitor Agent,
// Monetization Agent, Distribution Agent, Risk Agent,
// Opportunity Scoring Agent) will call.
//
// NOTE: generateResearchWorkspaceFromBlueprint produces deterministic
// placeholder research derived from blueprint fields. No external web
// browsing or AI generation is performed in this task.

import { createSupabaseServerClient } from "@/lib/supabase/server";
import {
  getCurrentUser,
  getBusinessById,
  createAgentActivityLog,
} from "@/lib/projects";
import type {
  NewResearchReportInput,
  UpdateResearchReportInput,
  NewResearchCustomerSegmentInput,
  UpdateResearchCustomerSegmentInput,
  NewResearchBuyerBudgetInput,
  UpdateResearchBuyerBudgetInput,
  NewResearchCompetitorInput,
  UpdateResearchCompetitorInput,
  NewResearchMonetizationModelInput,
  UpdateResearchMonetizationModelInput,
  NewResearchDistributionChannelInput,
  UpdateResearchDistributionChannelInput,
  NewResearchRiskInput,
  UpdateResearchRiskInput,
  NewResearchHypothesisInput,
  UpdateResearchHypothesisInput,
  NewResearchEvidenceInput,
  ResearchReportRecord,
  ResearchCustomerSegmentRecord,
  ResearchBuyerBudgetRecord,
  ResearchCompetitorRecord,
  ResearchMonetizationModelRecord,
  ResearchDistributionChannelRecord,
  ResearchRiskRecord,
  ResearchHypothesisRecord,
  ResearchEvidenceRecord,
  ResearchWorkspace,
  ResearchSummary,
  ResearchConfidence,
  ResearchPriority,
} from "@/types/research";

// ---------------------------------------------------------------------------
// Result wrapper (matches pattern in src/lib/projects.ts)
// ---------------------------------------------------------------------------

type Result<T> =
  | { data: T; error: null; code?: undefined }
  | { data: null; error: string; code: string };

function ok<T>(data: T): Result<T> {
  return { data, error: null };
}

function err<T>(message: string, code = "unknown_error"): Result<T> {
  return { data: null, error: message, code };
}

const NO_CLIENT =
  "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local.";

const SCHEMA_MISSING_MSG =
  "Research schema is not applied. Run supabase/research.sql in the Supabase SQL Editor.";

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/** Detects a "relation does not exist" Postgres error (table not created yet). */
function isMissingTableError(e: { message?: string; code?: string }): boolean {
  return (
    e.code === "42P01" ||
    (typeof e.message === "string" &&
      e.message.includes("relation") &&
      e.message.includes("does not exist"))
  );
}

/** Strip undefined values so Supabase only updates supplied fields. */
function omitUndefined(obj: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined));
}

/** Build update payload by dropping id + business_id from the input object. */
function updatePayload(input: Record<string, unknown>): Record<string, unknown> {
  return omitUndefined(
    Object.fromEntries(
      Object.entries(input).filter(([k]) => k !== "id" && k !== "business_id")
    )
  );
}

async function getAuthenticatedUser() {
  const result = await getCurrentUser();
  if (result.error || !result.data) return null;
  return result.data;
}

async function verifyOwnership(businessId: string, userId: string): Promise<boolean> {
  const result = await getBusinessById(businessId);
  if (result.error || !result.data) return false;
  return result.data.user_id === userId;
}

function asStr(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

function asArr(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

// ---------------------------------------------------------------------------
// getResearchWorkspace
// ---------------------------------------------------------------------------

export async function getResearchWorkspace(
  businessId: string
): Promise<Result<ResearchWorkspace>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(businessId, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const [
    reportRes,
    segmentsRes,
    buyerBudgetsRes,
    competitorsRes,
    monetizationRes,
    distributionRes,
    risksRes,
    hypothesesRes,
    evidenceRes,
  ] = await Promise.all([
    supabase
      .from("research_reports")
      .select("*")
      .eq("business_id", businessId)
      .order("created_at", { ascending: false })
      .limit(1),
    supabase
      .from("research_customer_segments")
      .select("*")
      .eq("business_id", businessId)
      .order("priority", { ascending: true })
      .order("created_at", { ascending: true }),
    supabase
      .from("research_buyer_budgets")
      .select("*")
      .eq("business_id", businessId)
      .order("priority", { ascending: true })
      .order("created_at", { ascending: true }),
    supabase
      .from("research_competitors")
      .select("*")
      .eq("business_id", businessId)
      .order("priority", { ascending: true })
      .order("created_at", { ascending: true }),
    supabase
      .from("research_monetization_models")
      .select("*")
      .eq("business_id", businessId)
      .order("priority", { ascending: true })
      .order("created_at", { ascending: true }),
    supabase
      .from("research_distribution_channels")
      .select("*")
      .eq("business_id", businessId)
      .order("priority", { ascending: true })
      .order("created_at", { ascending: true }),
    supabase
      .from("research_risks")
      .select("*")
      .eq("business_id", businessId)
      .order("priority", { ascending: true })
      .order("created_at", { ascending: true }),
    supabase
      .from("research_hypotheses")
      .select("*")
      .eq("business_id", businessId)
      .order("priority", { ascending: true })
      .order("created_at", { ascending: true }),
    supabase
      .from("research_evidence")
      .select("*")
      .eq("business_id", businessId)
      .order("created_at", { ascending: false }),
  ]);

  for (const res of [
    reportRes, segmentsRes, buyerBudgetsRes, competitorsRes,
    monetizationRes, distributionRes, risksRes, hypothesesRes, evidenceRes,
  ]) {
    if (res.error) {
      if (isMissingTableError(res.error as { message?: string; code?: string })) {
        return err(SCHEMA_MISSING_MSG, "research_schema_missing");
      }
      return err(res.error.message, "query_error");
    }
  }

  const report = ((reportRes.data ?? []) as ResearchReportRecord[])[0] ?? null;
  const segments = (segmentsRes.data ?? []) as ResearchCustomerSegmentRecord[];
  const buyerBudgets = (buyerBudgetsRes.data ?? []) as ResearchBuyerBudgetRecord[];
  const competitors = (competitorsRes.data ?? []) as ResearchCompetitorRecord[];
  const monetizationModels = (monetizationRes.data ?? []) as ResearchMonetizationModelRecord[];
  const distributionChannels = (distributionRes.data ?? []) as ResearchDistributionChannelRecord[];
  const risks = (risksRes.data ?? []) as ResearchRiskRecord[];
  const hypotheses = (hypothesesRes.data ?? []) as ResearchHypothesisRecord[];
  const evidence = (evidenceRes.data ?? []) as ResearchEvidenceRecord[];

  const summary: ResearchSummary = {
    businessId,
    status: report?.status ?? "not_started",
    hasReport: report !== null,
    opportunityScore: report?.opportunity_score ?? null,
    segmentCount: segments.length,
    buyerBudgetCount: buyerBudgets.length,
    competitorCount: competitors.length,
    monetizationModelCount: monetizationModels.length,
    distributionChannelCount: distributionChannels.length,
    riskCount: risks.length,
    hypothesisCount: hypotheses.length,
    evidenceCount: evidence.length,
    canGenerate: report === null && segments.length === 0,
  };

  return ok({
    summary,
    report,
    segments,
    buyerBudgets,
    competitors,
    monetizationModels,
    distributionChannels,
    risks,
    hypotheses,
    evidence,
  });
}

// ---------------------------------------------------------------------------
// generateResearchWorkspaceFromBlueprint
// Produces deterministic placeholder research from blueprint fields.
// No external web browsing or AI calls — documented limitation.
// ---------------------------------------------------------------------------

export async function generateResearchWorkspaceFromBlueprint(businessId: string): Promise<
  Result<{
    generated: boolean;
    report: boolean;
    segments: number;
    buyerBudgets: number;
    competitors: number;
    monetizationModels: number;
    distributionChannels: number;
    risks: number;
    hypotheses: number;
    evidence: number;
  }>
> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(businessId, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  // Fetch blueprint — generation works with or without one
  const { data: blueprints } = await supabase
    .from("business_blueprints")
    .select("blueprint")
    .eq("business_id", businessId)
    .order("created_at", { ascending: false })
    .limit(1);

  const blueprint =
    (blueprints?.[0]?.blueprint as Record<string, unknown> | null) ?? null;

  // Build seed payloads from blueprint fields
  const reportInput = buildReportSeed(businessId, user.id, blueprint);
  const segmentInputs = buildSegmentSeeds(businessId, user.id, blueprint);
  const buyerBudgetInputs = buildBuyerBudgetSeeds(businessId, user.id, blueprint);
  const competitorInputs = buildCompetitorSeeds(businessId, user.id, blueprint);
  const monetizationInputs = buildMonetizationSeeds(businessId, user.id, blueprint);
  const distributionInputs = buildDistributionSeeds(businessId, user.id, blueprint);
  const riskInputs = buildRiskSeeds(businessId, user.id, blueprint);
  const hypothesisInputs = buildHypothesisSeeds(businessId, user.id, blueprint);
  const evidenceInputs = buildEvidenceSeeds(businessId, user.id, blueprint);

  // Insert report
  const reportRes = await supabase
    .from("research_reports")
    .insert(reportInput as unknown as Record<string, unknown>)
    .select()
    .single();

  if (reportRes.error) {
    if (isMissingTableError(reportRes.error as { message?: string; code?: string })) {
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    }
    return err(reportRes.error.message, "research_generate_failed");
  }

  // Insert supporting tables
  const segRes = await supabase
    .from("research_customer_segments")
    .insert(segmentInputs as unknown as Record<string, unknown>[])
    .select();
  if (segRes.error) return err(segRes.error.message, "research_generate_failed");

  const bbRes = await supabase
    .from("research_buyer_budgets")
    .insert(buyerBudgetInputs as unknown as Record<string, unknown>[])
    .select();
  if (bbRes.error) return err(bbRes.error.message, "research_generate_failed");

  const compRes = await supabase
    .from("research_competitors")
    .insert(competitorInputs as unknown as Record<string, unknown>[])
    .select();
  if (compRes.error) return err(compRes.error.message, "research_generate_failed");

  const monRes = await supabase
    .from("research_monetization_models")
    .insert(monetizationInputs as unknown as Record<string, unknown>[])
    .select();
  if (monRes.error) return err(monRes.error.message, "research_generate_failed");

  const distRes = await supabase
    .from("research_distribution_channels")
    .insert(distributionInputs as unknown as Record<string, unknown>[])
    .select();
  if (distRes.error) return err(distRes.error.message, "research_generate_failed");

  const riskRes = await supabase
    .from("research_risks")
    .insert(riskInputs as unknown as Record<string, unknown>[])
    .select();
  if (riskRes.error) return err(riskRes.error.message, "research_generate_failed");

  const hypRes = await supabase
    .from("research_hypotheses")
    .insert(hypothesisInputs as unknown as Record<string, unknown>[])
    .select();
  if (hypRes.error) return err(hypRes.error.message, "research_generate_failed");

  const evRes = await supabase
    .from("research_evidence")
    .insert(evidenceInputs as unknown as Record<string, unknown>[])
    .select();
  if (evRes.error) return err(evRes.error.message, "research_generate_failed");

  void createAgentActivityLog({
    business_id: businessId,
    user_id: user.id,
    activity_type: "research_workspace_generated",
    message: `Research workspace generated from blueprint with ${segmentInputs.length} segments, ${competitorInputs.length} competitors, ${riskInputs.length} risks.`,
    metadata: {
      seededFromBlueprint: blueprint !== null,
      segmentCount: (segRes.data ?? []).length,
      buyerBudgetCount: (bbRes.data ?? []).length,
      competitorCount: (compRes.data ?? []).length,
      monetizationModelCount: (monRes.data ?? []).length,
      distributionChannelCount: (distRes.data ?? []).length,
      riskCount: (riskRes.data ?? []).length,
      hypothesisCount: (hypRes.data ?? []).length,
      evidenceCount: (evRes.data ?? []).length,
    },
  });

  return ok({
    generated: true,
    report: true,
    segments: (segRes.data ?? []).length,
    buyerBudgets: (bbRes.data ?? []).length,
    competitors: (compRes.data ?? []).length,
    monetizationModels: (monRes.data ?? []).length,
    distributionChannels: (distRes.data ?? []).length,
    risks: (riskRes.data ?? []).length,
    hypotheses: (hypRes.data ?? []).length,
    evidence: (evRes.data ?? []).length,
  });
}

// ---------------------------------------------------------------------------
// Seed builder helpers
// ---------------------------------------------------------------------------

function buildReportSeed(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown> | null
): NewResearchReportInput {
  const name = asStr(blueprint?.ideaName ?? blueprint?.idea_name ?? blueprint?.name) ?? "This Business";
  const problem = asStr(blueprint?.problem ?? blueprint?.coreProblem ?? blueprint?.core_problem) ?? "a identified problem";
  const target = asStr(blueprint?.targetCustomer ?? blueprint?.target_customer) ?? "target customers";

  return {
    business_id: businessId,
    user_id: userId,
    title: `Initial Market Research — ${name}`,
    status: "draft",
    opportunity_score: null,
    thesis: `${name} addresses ${problem} for ${target}. This placeholder thesis should be replaced with real research findings.`,
    target_customer: target,
    money_pool: asStr(blueprint?.monetization ?? blueprint?.revenue ?? blueprint?.businessModel ?? blueprint?.business_model) ?? null,
    wedge: asStr(blueprint?.unfairAdvantage ?? blueprint?.unfair_advantage ?? blueprint?.differentiator) ?? null,
    recommendation: "Review and enrich this research before committing to build.",
    summary: `Placeholder research for ${name}. Run the Market Research Agent to replace with real findings.`,
    confidence: "assumption",
    priority: "high",
  };
}

function buildSegmentSeeds(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown> | null
): NewResearchCustomerSegmentInput[] {
  const targetCustomer = asStr(blueprint?.targetCustomer ?? blueprint?.target_customer);

  const rawPersonas = asArr(
    blueprint?.targetPersonas ?? blueprint?.target_personas ?? blueprint?.personas
  );

  if (rawPersonas.length > 0) {
    return rawPersonas.slice(0, 3).map((p, i) => {
      const obj = (typeof p === "object" && p !== null ? p : {}) as Record<string, unknown>;
      const name = asStr(obj.name ?? obj.title ?? obj.persona) ?? targetCustomer ?? `Segment ${i + 1}`;
      return {
        business_id: businessId,
        user_id: userId,
        name,
        description: asStr(obj.description ?? obj.summary),
        pain_level: 6,
        ability_to_pay: 5,
        reachability: 5,
        market_size_guess: null,
        channels: asArr(obj.channels).map(String).filter(Boolean),
        evidence_summary: "Placeholder — enrich with real customer research.",
        confidence: "assumption" as ResearchConfidence,
        priority: (i === 0 ? "high" : "medium") as ResearchPriority,
      };
    });
  }

  const base = targetCustomer ?? "Target Customer";
  return [
    {
      business_id: businessId,
      user_id: userId,
      name: `${base} — Early Adopter`,
      description: "Hands-on operators who move fast and have a high tolerance for early-stage products.",
      pain_level: 7,
      ability_to_pay: 6,
      reachability: 7,
      market_size_guess: null,
      channels: ["LinkedIn", "Twitter / X", "Slack communities"],
      evidence_summary: "Placeholder — replace with real segment research.",
      confidence: "assumption" as const,
      priority: "high" as const,
    },
    {
      business_id: businessId,
      user_id: userId,
      name: `${base} — SMB Buyer`,
      description: "Small-to-mid-size business operators who need ROI justification.",
      pain_level: 6,
      ability_to_pay: 5,
      reachability: 5,
      market_size_guess: null,
      channels: ["LinkedIn", "Email outreach", "Content / SEO"],
      evidence_summary: "Placeholder — replace with real segment research.",
      confidence: "assumption" as const,
      priority: "medium" as const,
    },
    {
      business_id: businessId,
      user_id: userId,
      name: `${base} — Enterprise Champion`,
      description: "Internal champion inside a large org who must build a business case.",
      pain_level: 5,
      ability_to_pay: 8,
      reachability: 3,
      market_size_guess: null,
      channels: ["LinkedIn", "Referrals", "Industry events"],
      evidence_summary: "Placeholder — replace with real segment research.",
      confidence: "assumption" as const,
      priority: "low" as const,
    },
  ];
}

function buildBuyerBudgetSeeds(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown> | null
): NewResearchBuyerBudgetInput[] {
  const target = asStr(blueprint?.targetCustomer ?? blueprint?.target_customer) ?? "Target Buyer";
  const pricing = asStr(
    blueprint?.pricing ?? blueprint?.revenueModel ?? blueprint?.revenue_model ??
    blueprint?.monetization ?? blueprint?.businessModel ?? blueprint?.business_model
  );

  return [
    {
      business_id: businessId,
      user_id: userId,
      buyer: `${target} — Individual / Startup`,
      budget_owner: "Self",
      existing_spend: "Currently using free tools or manual workarounds",
      willingness_to_pay: pricing ?? "$25–99/mo",
      value_driver: "Time saved and reduced operational friction",
      pricing_signal: "Placeholder — validate through customer interviews",
      confidence: "assumption" as const,
      priority: "high" as const,
    },
    {
      business_id: businessId,
      user_id: userId,
      buyer: `${target} — Mid-Market / SMB`,
      budget_owner: "Department lead or founder",
      existing_spend: "Paying for point solutions or agency services",
      willingness_to_pay: pricing ?? "$200–500/mo",
      value_driver: "Scalable output without proportional headcount growth",
      pricing_signal: "Placeholder — validate through customer interviews",
      confidence: "assumption" as const,
      priority: "medium" as const,
    },
  ];
}

function buildCompetitorSeeds(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown> | null
): NewResearchCompetitorInput[] {
  const rawCompetitors = asArr(
    blueprint?.competitors ?? blueprint?.competitorAnalysis ?? blueprint?.competitor_analysis
  );

  if (rawCompetitors.length > 0) {
    return rawCompetitors.slice(0, 3).map((c, i) => {
      const obj = (typeof c === "object" && c !== null ? c : {}) as Record<string, unknown>;
      return {
        business_id: businessId,
        user_id: userId,
        name: asStr(obj.name ?? obj.competitor) ?? `Competitor ${i + 1}`,
        url: asStr(obj.url ?? obj.website),
        category: "direct",
        positioning: asStr(obj.positioning ?? obj.description),
        pricing_summary: asStr(obj.pricing ?? obj.price),
        strengths: asArr(obj.strengths).map(String).filter(Boolean),
        weaknesses: asArr(obj.weaknesses).map(String).filter(Boolean),
        wedge_opportunity: asStr(obj.wedge ?? obj.opportunity),
        confidence: "assumption" as const,
        priority: (i === 0 ? "high" : "medium") as ResearchPriority,
      };
    });
  }

  return [
    {
      business_id: businessId,
      user_id: userId,
      name: "Incumbent / Status Quo",
      url: null,
      category: "indirect",
      positioning: "Manual processes, spreadsheets, or legacy tools",
      pricing_summary: "Hidden cost — staff time and error rate",
      strengths: ["Familiar to users", "Zero switching cost to adopt"],
      weaknesses: ["Slow", "Error-prone", "Doesn't scale"],
      wedge_opportunity: "10x speed with better UX and automated workflows",
      confidence: "assumption" as const,
      priority: "high" as const,
    },
    {
      business_id: businessId,
      user_id: userId,
      name: "Horizontal Platform Competitor",
      url: null,
      category: "indirect",
      positioning: "Broad platform addressing many use cases",
      pricing_summary: "$50–300/mo for full platform",
      strengths: ["Brand recognition", "Rich feature set", "Integrations"],
      weaknesses: ["Not optimised for this specific use case", "Complexity"],
      wedge_opportunity: "Vertical focus with deeper workflow automation",
      confidence: "assumption" as const,
      priority: "medium" as const,
    },
    {
      business_id: businessId,
      user_id: userId,
      name: "Direct Competitor (TBD)",
      url: null,
      category: "direct",
      positioning: "Placeholder — identify real direct competitors through research",
      pricing_summary: null,
      strengths: [],
      weaknesses: [],
      wedge_opportunity: "Placeholder — complete competitor research to find wedge",
      confidence: "assumption" as const,
      priority: "medium" as const,
    },
  ];
}

function buildMonetizationSeeds(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown> | null
): NewResearchMonetizationModelInput[] {
  const target = asStr(blueprint?.targetCustomer ?? blueprint?.target_customer) ?? "customer";
  const pricing = asStr(
    blueprint?.pricing ?? blueprint?.revenueModel ?? blueprint?.revenue_model ??
    blueprint?.monetization
  );

  return [
    {
      business_id: businessId,
      user_id: userId,
      model: "SaaS Subscription",
      buyer: target,
      price_assumption: pricing ?? "$49/mo (individual) — $199/mo (team)",
      value_metric: "Per seat or per workspace",
      reasoning: "Recurring revenue model; aligns with SaaS best practices for B2B tools.",
      confidence: "assumption" as const,
      priority: "high" as const,
    },
    {
      business_id: businessId,
      user_id: userId,
      model: "Usage-Based / Pay-as-You-Go",
      buyer: target,
      price_assumption: "Per unit of value delivered (e.g. per run, per output, per API call)",
      value_metric: "Consumption-based",
      reasoning: "Lower barrier to entry; scales with customer usage and success.",
      confidence: "assumption" as const,
      priority: "medium" as const,
    },
  ];
}

function buildDistributionSeeds(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown> | null
): NewResearchDistributionChannelInput[] {
  const rawChannels = asArr(
    blueprint?.distributionChannels ?? blueprint?.distribution_channels ??
    blueprint?.channels ?? blueprint?.goToMarket ?? blueprint?.go_to_market
  );

  if (rawChannels.length >= 3) {
    return rawChannels.slice(0, 3).map((c, i) => {
      const label = typeof c === "string" ? c : asStr((c as Record<string, unknown>)?.channel ?? (c as Record<string, unknown>)?.name) ?? `Channel ${i + 1}`;
      return {
        business_id: businessId,
        user_id: userId,
        channel: label,
        description: "Placeholder — enrich with real channel research.",
        speed_score: 5,
        cost_score: 5,
        difficulty_score: 5,
        reasoning: "Identified from blueprint — validate with real acquisition experiments.",
        confidence: "assumption" as const,
        priority: (i === 0 ? "high" : "medium") as ResearchPriority,
      };
    });
  }

  void blueprint; // suppress unused warning if no channels found

  return [
    {
      business_id: businessId,
      user_id: userId,
      channel: "Founder-led outbound (LinkedIn / email)",
      description: "Direct outreach from founder to ideal customer profiles.",
      speed_score: 8,
      cost_score: 2,
      difficulty_score: 4,
      reasoning: "Fastest way to get early customers and learn about buyer objections.",
      confidence: "assumption" as const,
      priority: "high" as const,
    },
    {
      business_id: businessId,
      user_id: userId,
      channel: "Content / SEO",
      description: "Long-form content targeting pain-point search queries.",
      speed_score: 3,
      cost_score: 3,
      difficulty_score: 6,
      reasoning: "Compounds over time; high ROI if the right keywords exist.",
      confidence: "assumption" as const,
      priority: "medium" as const,
    },
    {
      business_id: businessId,
      user_id: userId,
      channel: "Community / Product Hunt / Hacker News",
      description: "Launch in relevant online communities for early awareness.",
      speed_score: 7,
      cost_score: 1,
      difficulty_score: 5,
      reasoning: "Low-cost awareness channel for B2B SaaS in the developer / founder space.",
      confidence: "assumption" as const,
      priority: "medium" as const,
    },
  ];
}

function buildRiskSeeds(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown> | null
): NewResearchRiskInput[] {
  const rawRisks = asArr(blueprint?.risks ?? blueprint?.keyRisks ?? blueprint?.key_risks);

  if (rawRisks.length >= 3) {
    return rawRisks.slice(0, 3).map((r, i) => {
      const label = typeof r === "string" ? r : asStr((r as Record<string, unknown>)?.title ?? (r as Record<string, unknown>)?.risk) ?? `Risk ${i + 1}`;
      return {
        business_id: businessId,
        user_id: userId,
        title: label,
        description: typeof r === "string" ? null : asStr((r as Record<string, unknown>)?.description),
        severity: "high",
        mitigation: typeof r === "string" ? null : asStr((r as Record<string, unknown>)?.mitigation),
        confidence: "assumption" as const,
        priority: (i === 0 ? "high" : "medium") as ResearchPriority,
      };
    });
  }

  return [
    {
      business_id: businessId,
      user_id: userId,
      title: "Market timing risk — solution too early or too late",
      description: "If the market is not yet ready to pay for this solution, acquiring customers will be extremely difficult regardless of product quality.",
      severity: "high",
      mitigation: "Run 10 customer discovery interviews before committing to build. Look for people who have already hacked together a workaround.",
      confidence: "assumption" as const,
      priority: "high" as const,
    },
    {
      business_id: businessId,
      user_id: userId,
      title: "Incumbent response — large player copies the feature",
      description: "An existing platform with significant distribution adds similar functionality, making it hard to differentiate.",
      severity: "medium",
      mitigation: "Build deep vertical workflow rather than a generic feature. Target a niche the incumbent will not prioritise.",
      confidence: "assumption" as const,
      priority: "high" as const,
    },
    {
      business_id: businessId,
      user_id: userId,
      title: "Customer acquisition cost exceeds lifetime value",
      description: "CAC is too high relative to the ACV, making the unit economics negative at scale.",
      severity: "high",
      mitigation: "Start with founder-led sales to understand buyer psychology before investing in paid acquisition.",
      confidence: "assumption" as const,
      priority: "medium" as const,
    },
  ];
}

function buildHypothesisSeeds(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown> | null
): NewResearchHypothesisInput[] {
  const name = asStr(blueprint?.ideaName ?? blueprint?.idea_name ?? blueprint?.name) ?? "this business";
  const target = asStr(blueprint?.targetCustomer ?? blueprint?.target_customer) ?? "target customers";
  const problem = asStr(blueprint?.problem ?? blueprint?.coreProblem ?? blueprint?.core_problem) ?? "the identified problem";

  return [
    {
      business_id: businessId,
      user_id: userId,
      title: `${target} encounter ${problem} frequently enough to pay for a solution`,
      description: "If the problem is infrequent or low-severity, there is no viable market.",
      test_method: "5 customer discovery interviews — ask about frequency and current workarounds without mentioning the solution.",
      success_criteria: "5+ interviewees describe the problem unprompted and rank it a top-3 pain.",
      confidence: "assumption" as const,
      priority: "high" as const,
    },
    {
      business_id: businessId,
      user_id: userId,
      title: `${name} can acquire its first 10 customers within 90 days of launch`,
      description: "Validates that distribution is feasible and the ICP is reachable before scaling spend.",
      test_method: "Founder-led outbound — identify 50 ideal leads, convert 10 to paying customers.",
      success_criteria: "10 paying customers within 90 days with a CAC under the target payback period.",
      confidence: "assumption" as const,
      priority: "high" as const,
    },
    {
      business_id: businessId,
      user_id: userId,
      title: "Willingness to pay meets or exceeds the target price tier",
      description: "Validates revenue model assumptions before building pricing infrastructure.",
      test_method: "Ask 10 interviewees: 'What would you pay for this today if it existed?' and price-anchor against current spend.",
      success_criteria: "7+ interviewees quote a number at or above the target price without prompting.",
      confidence: "assumption" as const,
      priority: "medium" as const,
    },
  ];
}

function buildEvidenceSeeds(
  businessId: string,
  userId: string,
  blueprint: Record<string, unknown> | null
): NewResearchEvidenceInput[] {
  const name = asStr(blueprint?.ideaName ?? blueprint?.idea_name ?? blueprint?.name) ?? "this business";
  const problem = asStr(blueprint?.problem ?? blueprint?.coreProblem ?? blueprint?.core_problem);

  const seeds: NewResearchEvidenceInput[] = [
    {
      business_id: businessId,
      user_id: userId,
      claim: `Founder identified "${problem ?? "the core problem"}" as a real pain point`,
      source: "Founder input",
      source_url: null,
      evidence_type: "customer_signal",
      confidence: "weak_signal",
      notes: `Derived from the business blueprint for ${name}. Validate with external sources.`,
    },
    {
      business_id: businessId,
      user_id: userId,
      claim: "Placeholder — add a real market data point (report, article, or statistic) supporting the opportunity",
      source: null,
      source_url: null,
      evidence_type: "market_report",
      confidence: "assumption",
      notes: "This is a seed placeholder. Replace with real research from industry reports, G2, Gartner, etc.",
    },
    {
      business_id: businessId,
      user_id: userId,
      claim: "Placeholder — add a quote or signal from a real customer discovery conversation",
      source: null,
      source_url: null,
      evidence_type: "customer_signal",
      confidence: "assumption",
      notes: "Conduct 5 customer interviews and log the strongest signal here.",
    },
  ];

  return seeds;
}

// ---------------------------------------------------------------------------
// CRUD — Research Reports
// ---------------------------------------------------------------------------

export async function createResearchReport(
  input: NewResearchReportInput
): Promise<Result<ResearchReportRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_reports")
    .insert({ ...input, user_id: user.id } as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_create_failed");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "research_report_created",
    message: `Research report "${input.title}" created.`,
    metadata: { reportTitle: input.title, status: input.status ?? "draft" },
  });

  return ok(data as ResearchReportRecord);
}

export async function updateResearchReport(
  input: UpdateResearchReportInput
): Promise<Result<ResearchReportRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_reports")
    .update(updatePayload(input as unknown as Record<string, unknown>))
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_update_failed");
  }

  if (input.status) {
    void createAgentActivityLog({
      business_id: input.business_id,
      user_id: user.id,
      activity_type: "research_status_updated",
      message: `Research report status updated to "${input.status}".`,
      metadata: { reportId: input.id, newStatus: input.status },
    });
  }

  return ok(data as ResearchReportRecord);
}

// ---------------------------------------------------------------------------
// CRUD — Customer Segments
// ---------------------------------------------------------------------------

export async function createResearchCustomerSegment(
  input: NewResearchCustomerSegmentInput
): Promise<Result<ResearchCustomerSegmentRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_customer_segments")
    .insert({ ...input, user_id: user.id } as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_create_failed");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "research_segment_created",
    message: `Customer segment "${input.name}" added to research workspace.`,
    metadata: { segmentName: input.name, priority: input.priority },
  });

  return ok(data as ResearchCustomerSegmentRecord);
}

export async function updateResearchCustomerSegment(
  input: UpdateResearchCustomerSegmentInput
): Promise<Result<ResearchCustomerSegmentRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_customer_segments")
    .update(updatePayload(input as unknown as Record<string, unknown>))
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_update_failed");
  }

  return ok(data as ResearchCustomerSegmentRecord);
}

// ---------------------------------------------------------------------------
// CRUD — Buyer Budgets
// ---------------------------------------------------------------------------

export async function createResearchBuyerBudget(
  input: NewResearchBuyerBudgetInput
): Promise<Result<ResearchBuyerBudgetRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_buyer_budgets")
    .insert({ ...input, user_id: user.id } as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_create_failed");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "research_buyer_budget_created",
    message: `Buyer budget analysis for "${input.buyer}" added to research workspace.`,
    metadata: { buyer: input.buyer, priority: input.priority },
  });

  return ok(data as ResearchBuyerBudgetRecord);
}

export async function updateResearchBuyerBudget(
  input: UpdateResearchBuyerBudgetInput
): Promise<Result<ResearchBuyerBudgetRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_buyer_budgets")
    .update(updatePayload(input as unknown as Record<string, unknown>))
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_update_failed");
  }

  return ok(data as ResearchBuyerBudgetRecord);
}

// ---------------------------------------------------------------------------
// CRUD — Competitors
// ---------------------------------------------------------------------------

export async function createResearchCompetitor(
  input: NewResearchCompetitorInput
): Promise<Result<ResearchCompetitorRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_competitors")
    .insert({ ...input, user_id: user.id } as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_create_failed");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "research_competitor_created",
    message: `Competitor "${input.name}" added to research workspace.`,
    metadata: { competitorName: input.name, category: input.category, priority: input.priority },
  });

  return ok(data as ResearchCompetitorRecord);
}

export async function updateResearchCompetitor(
  input: UpdateResearchCompetitorInput
): Promise<Result<ResearchCompetitorRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_competitors")
    .update(updatePayload(input as unknown as Record<string, unknown>))
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_update_failed");
  }

  return ok(data as ResearchCompetitorRecord);
}

// ---------------------------------------------------------------------------
// CRUD — Monetization Models
// ---------------------------------------------------------------------------

export async function createResearchMonetizationModel(
  input: NewResearchMonetizationModelInput
): Promise<Result<ResearchMonetizationModelRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_monetization_models")
    .insert({ ...input, user_id: user.id } as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_create_failed");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "research_monetization_created",
    message: `Monetization model "${input.model}" added to research workspace.`,
    metadata: { model: input.model, priority: input.priority },
  });

  return ok(data as ResearchMonetizationModelRecord);
}

export async function updateResearchMonetizationModel(
  input: UpdateResearchMonetizationModelInput
): Promise<Result<ResearchMonetizationModelRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_monetization_models")
    .update(updatePayload(input as unknown as Record<string, unknown>))
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_update_failed");
  }

  return ok(data as ResearchMonetizationModelRecord);
}

// ---------------------------------------------------------------------------
// CRUD — Distribution Channels
// ---------------------------------------------------------------------------

export async function createResearchDistributionChannel(
  input: NewResearchDistributionChannelInput
): Promise<Result<ResearchDistributionChannelRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_distribution_channels")
    .insert({ ...input, user_id: user.id } as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_create_failed");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "research_distribution_created",
    message: `Distribution channel "${input.channel}" added to research workspace.`,
    metadata: { channel: input.channel, priority: input.priority },
  });

  return ok(data as ResearchDistributionChannelRecord);
}

export async function updateResearchDistributionChannel(
  input: UpdateResearchDistributionChannelInput
): Promise<Result<ResearchDistributionChannelRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_distribution_channels")
    .update(updatePayload(input as unknown as Record<string, unknown>))
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_update_failed");
  }

  return ok(data as ResearchDistributionChannelRecord);
}

// ---------------------------------------------------------------------------
// CRUD — Risks
// ---------------------------------------------------------------------------

export async function createResearchRisk(
  input: NewResearchRiskInput
): Promise<Result<ResearchRiskRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_risks")
    .insert({ ...input, user_id: user.id } as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_create_failed");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "research_risk_created",
    message: `Risk "${input.title}" added to research workspace.`,
    metadata: { riskTitle: input.title, severity: input.severity, priority: input.priority },
  });

  return ok(data as ResearchRiskRecord);
}

export async function updateResearchRisk(
  input: UpdateResearchRiskInput
): Promise<Result<ResearchRiskRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_risks")
    .update(updatePayload(input as unknown as Record<string, unknown>))
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_update_failed");
  }

  return ok(data as ResearchRiskRecord);
}

// ---------------------------------------------------------------------------
// CRUD — Research Hypotheses
// ---------------------------------------------------------------------------

export async function createResearchHypothesis(
  input: NewResearchHypothesisInput
): Promise<Result<ResearchHypothesisRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_hypotheses")
    .insert({ ...input, user_id: user.id } as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_create_failed");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "research_hypothesis_created",
    message: `Research hypothesis "${input.title}" added.`,
    metadata: { hypothesisTitle: input.title, priority: input.priority },
  });

  return ok(data as ResearchHypothesisRecord);
}

export async function updateResearchHypothesis(
  input: UpdateResearchHypothesisInput
): Promise<Result<ResearchHypothesisRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_hypotheses")
    .update(updatePayload(input as unknown as Record<string, unknown>))
    .eq("id", input.id)
    .eq("user_id", user.id)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_update_failed");
  }

  if (input.confidence) {
    void createAgentActivityLog({
      business_id: input.business_id,
      user_id: user.id,
      activity_type: "research_status_updated",
      message: `Research hypothesis confidence updated to "${input.confidence}".`,
      metadata: { hypothesisId: input.id, newConfidence: input.confidence },
    });
  }

  return ok(data as ResearchHypothesisRecord);
}

// ---------------------------------------------------------------------------
// CRUD — Evidence
// ---------------------------------------------------------------------------

export async function createResearchEvidence(
  input: NewResearchEvidenceInput
): Promise<Result<ResearchEvidenceRecord>> {
  const supabase = await createSupabaseServerClient();
  if (!supabase) return err(NO_CLIENT, "missing_supabase_env");

  const user = await getAuthenticatedUser();
  if (!user) return err("Authentication required.", "unauthenticated");

  const owned = await verifyOwnership(input.business_id, user.id);
  if (!owned) return err("Access denied.", "forbidden");

  const { data, error } = await supabase
    .from("research_evidence")
    .insert({ ...input, user_id: user.id } as unknown as Record<string, unknown>)
    .select()
    .single();

  if (error) {
    if (isMissingTableError(error as { message?: string; code?: string }))
      return err(SCHEMA_MISSING_MSG, "research_schema_missing");
    return err(error.message, "research_create_failed");
  }

  void createAgentActivityLog({
    business_id: input.business_id,
    user_id: user.id,
    activity_type: "research_evidence_created",
    message: "Research evidence record added.",
    metadata: {
      claim: input.claim.slice(0, 100),
      evidenceType: input.evidence_type,
      confidence: input.confidence,
    },
  });

  return ok(data as ResearchEvidenceRecord);
}

// ---------------------------------------------------------------------------
// getResearchSummary (lightweight — summary only)
// ---------------------------------------------------------------------------

export async function getResearchSummary(
  businessId: string
): Promise<Result<ResearchSummary>> {
  const result = await getResearchWorkspace(businessId);
  if (result.error || !result.data) {
    return err(result.error ?? "Failed to load research workspace.", result.code ?? "unknown_error");
  }
  return ok(result.data.summary);
}
