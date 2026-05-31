// Research Node — TypeScript types.
// These mirror the schema in supabase/research.sql.
//
// This module is the type foundation for the Research Node.
// Future agents (Market Research Agent, Customer Segment Agent,
// Competitor Agent, Monetization Agent, Distribution Agent,
// Risk Agent, Opportunity Scoring Agent) will import from here.

// ---------------------------------------------------------------------------
// Enum-like string union types
// ---------------------------------------------------------------------------

/** Overall status of the research workspace for a business. */
export type ResearchStatus =
  | "not_started"
  | "researching"
  | "draft"
  | "reviewed"
  | "ready_for_validation"
  | "needs_more_research";

/** Confidence level of a research finding or hypothesis. */
export type ResearchConfidence =
  | "assumption"
  | "weak_signal"
  | "medium_signal"
  | "strong_signal"
  | "validated"
  | "invalidated";

/** Relative priority across all research entities. */
export type ResearchPriority = "high" | "medium" | "low";

/** How a research finding was sourced. */
export type ResearchSource =
  | "ai_generated"
  | "founder_input"
  | "web_research"
  | "customer_interview"
  | "competitor_pricing"
  | "review_analysis"
  | "manual_note";

// ---------------------------------------------------------------------------
// Row types — shape of a row returned by SELECT
// ---------------------------------------------------------------------------

/**
 * A top-level research report summarising the opportunity thesis for a business.
 * One per business (the latest one is considered active).
 */
export interface ResearchReportRecord {
  id: string;
  business_id: string;
  user_id: string;
  /** Short report title (e.g. "Initial Market Research — June 2026"). */
  title: string;
  /** Overall research status. */
  status: ResearchStatus;
  /** 0–100 opportunity score; computed or manually set. */
  opportunity_score: number | null;
  /** Narrative describing why this is a strong / weak opportunity. */
  thesis: string | null;
  /** Description of the target customer. */
  target_customer: string | null;
  /** Size / depth of the monetisable opportunity ("$50M TAM", "thin SMB margins", etc.). */
  money_pool: string | null;
  /** The specific angle or insight that gives this business an edge. */
  wedge: string | null;
  /** Research recommendation: proceed, pivot, or kill. */
  recommendation: string | null;
  /** Concise summary paragraph for the dashboard card. */
  summary: string | null;
  /** Overall confidence in the report. */
  confidence: ResearchConfidence | null;
  priority: ResearchPriority;
  created_at: string;
  updated_at: string;
}

/** A target customer segment identified during research. */
export interface ResearchCustomerSegmentRecord {
  id: string;
  business_id: string;
  user_id: string;
  /** Segment name (e.g. "Early-stage founders", "SMB ops managers"). */
  name: string;
  /** Narrative description of who these people are. */
  description: string | null;
  /** 0–10: how acutely they feel the pain. */
  pain_level: number | null;
  /** 0–10: estimated willingness and ability to pay. */
  ability_to_pay: number | null;
  /** 0–10: how easily they can be reached / converted. */
  reachability: number | null;
  /** Qualitative market-size estimate ("niche", "$1B TAM", "20K companies"). */
  market_size_guess: string | null;
  /** Preferred acquisition channels for this segment. */
  channels: string[] | null;
  /** Short summary of evidence supporting this segment's viability. */
  evidence_summary: string | null;
  confidence: ResearchConfidence | null;
  priority: ResearchPriority;
  created_at: string;
  updated_at: string;
}

/** Budget and willingness-to-pay analysis for a buyer archetype. */
export interface ResearchBuyerBudgetRecord {
  id: string;
  business_id: string;
  user_id: string;
  /** The buyer persona label (e.g. "VP of Engineering", "Solo founder"). */
  buyer: string;
  /** Who controls the budget (e.g. "Same person", "CFO", "Dept. lead"). */
  budget_owner: string | null;
  /** Current spend on alternatives / substitutes. */
  existing_spend: string | null;
  /** Estimated willingness to pay (e.g. "$50–200/mo", "$5K/yr enterprise"). */
  willingness_to_pay: string | null;
  /** The outcome they're paying for (e.g. "hours saved", "risk reduced"). */
  value_driver: string | null;
  /** Any pricing signal discovered (e.g. "competitors charge $X"). */
  pricing_signal: string | null;
  confidence: ResearchConfidence | null;
  priority: ResearchPriority;
  created_at: string;
  updated_at: string;
}

/** A competitor or alternative solution identified during research. */
export interface ResearchCompetitorRecord {
  id: string;
  business_id: string;
  user_id: string;
  /** Competitor or product name. */
  name: string;
  /** Homepage or product URL. */
  url: string | null;
  /** Category: "direct", "indirect", "substitute", "emerging". */
  category: string | null;
  /** How this competitor positions itself. */
  positioning: string | null;
  /** Pricing summary ("$29/mo", "enterprise only", "freemium"). */
  pricing_summary: string | null;
  /** Key strengths of this competitor. */
  strengths: string[] | null;
  /** Known weaknesses or gaps. */
  weaknesses: string[] | null;
  /** How this business could wedge against or around this competitor. */
  wedge_opportunity: string | null;
  confidence: ResearchConfidence | null;
  priority: ResearchPriority;
  created_at: string;
  updated_at: string;
}

/** A potential monetisation model for the business. */
export interface ResearchMonetizationModelRecord {
  id: string;
  business_id: string;
  user_id: string;
  /** Model label (e.g. "SaaS subscription", "Usage-based", "Service retainer"). */
  model: string;
  /** Who pays (e.g. "End user", "Enterprise buyer", "Agency"). */
  buyer: string | null;
  /** Assumed price point (e.g. "$49/mo per seat"). */
  price_assumption: string | null;
  /** What the price is tied to (e.g. "per seat", "per API call", "per project"). */
  value_metric: string | null;
  /** Rationale for why this model fits. */
  reasoning: string | null;
  confidence: ResearchConfidence | null;
  priority: ResearchPriority;
  created_at: string;
  updated_at: string;
}

/** A distribution or acquisition channel identified for the business. */
export interface ResearchDistributionChannelRecord {
  id: string;
  business_id: string;
  user_id: string;
  /** Channel name (e.g. "LinkedIn outbound", "Product Hunt", "SEO", "Partnerships"). */
  channel: string;
  /** Description of how this channel would be used. */
  description: string | null;
  /** 0–10: how quickly this channel can produce results. */
  speed_score: number | null;
  /** 0–10: relative cost (lower = cheaper). */
  cost_score: number | null;
  /** 0–10: difficulty of execution (lower = easier). */
  difficulty_score: number | null;
  /** Reasoning for including / ranking this channel. */
  reasoning: string | null;
  confidence: ResearchConfidence | null;
  priority: ResearchPriority;
  created_at: string;
  updated_at: string;
}

/** A risk that could undermine the business opportunity. */
export interface ResearchRiskRecord {
  id: string;
  business_id: string;
  user_id: string;
  /** Short risk title (e.g. "Incumbent response", "Regulatory change"). */
  title: string;
  /** Expanded description of the risk and its implications. */
  description: string | null;
  /** Severity: "critical" | "high" | "medium" | "low". */
  severity: string | null;
  /** How the team can reduce or respond to this risk. */
  mitigation: string | null;
  confidence: ResearchConfidence | null;
  priority: ResearchPriority;
  created_at: string;
  updated_at: string;
}

/** A research-level hypothesis to validate before building. */
export interface ResearchHypothesisRecord {
  id: string;
  business_id: string;
  user_id: string;
  /** Short hypothesis title. */
  title: string;
  /** Expanded reasoning behind this hypothesis. */
  description: string | null;
  /** How to test this hypothesis (e.g. "5 customer interviews", "price test landing page"). */
  test_method: string | null;
  /** What a successful test looks like. */
  success_criteria: string | null;
  confidence: ResearchConfidence | null;
  priority: ResearchPriority;
  created_at: string;
  updated_at: string;
}

/** A piece of evidence supporting a research finding or hypothesis. */
export interface ResearchEvidenceRecord {
  id: string;
  business_id: string;
  user_id: string;
  /** The specific claim being evidenced. */
  claim: string;
  /** Source label (e.g. "G2 review", "Stripe blog", "customer interview"). */
  source: string | null;
  /** URL to the evidence source. */
  source_url: string | null;
  /**
   * Evidence type: "data_point" | "quote" | "case_study" | "trend" |
   * "competitor_signal" | "customer_signal" | "market_report"
   */
  evidence_type: string | null;
  confidence: ResearchConfidence | null;
  /** Free-text notes or context about this evidence. */
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Aggregate / workspace types
// ---------------------------------------------------------------------------

export interface ResearchSummary {
  businessId: string;
  status: ResearchStatus;
  hasReport: boolean;
  opportunityScore: number | null;
  segmentCount: number;
  buyerBudgetCount: number;
  competitorCount: number;
  monetizationModelCount: number;
  distributionChannelCount: number;
  riskCount: number;
  hypothesisCount: number;
  evidenceCount: number;
  canGenerate: boolean;
}

export interface ResearchWorkspace {
  summary: ResearchSummary;
  report: ResearchReportRecord | null;
  segments: ResearchCustomerSegmentRecord[];
  buyerBudgets: ResearchBuyerBudgetRecord[];
  competitors: ResearchCompetitorRecord[];
  monetizationModels: ResearchMonetizationModelRecord[];
  distributionChannels: ResearchDistributionChannelRecord[];
  risks: ResearchRiskRecord[];
  hypotheses: ResearchHypothesisRecord[];
  evidence: ResearchEvidenceRecord[];
}

// ---------------------------------------------------------------------------
// Input types — create
// ---------------------------------------------------------------------------

export interface NewResearchReportInput {
  business_id: string;
  user_id: string;
  title: string;
  status?: ResearchStatus;
  opportunity_score?: number | null;
  thesis?: string | null;
  target_customer?: string | null;
  money_pool?: string | null;
  wedge?: string | null;
  recommendation?: string | null;
  summary?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface NewResearchCustomerSegmentInput {
  business_id: string;
  user_id: string;
  name: string;
  description?: string | null;
  pain_level?: number | null;
  ability_to_pay?: number | null;
  reachability?: number | null;
  market_size_guess?: string | null;
  channels?: string[] | null;
  evidence_summary?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface NewResearchBuyerBudgetInput {
  business_id: string;
  user_id: string;
  buyer: string;
  budget_owner?: string | null;
  existing_spend?: string | null;
  willingness_to_pay?: string | null;
  value_driver?: string | null;
  pricing_signal?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface NewResearchCompetitorInput {
  business_id: string;
  user_id: string;
  name: string;
  url?: string | null;
  category?: string | null;
  positioning?: string | null;
  pricing_summary?: string | null;
  strengths?: string[] | null;
  weaknesses?: string[] | null;
  wedge_opportunity?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface NewResearchMonetizationModelInput {
  business_id: string;
  user_id: string;
  model: string;
  buyer?: string | null;
  price_assumption?: string | null;
  value_metric?: string | null;
  reasoning?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface NewResearchDistributionChannelInput {
  business_id: string;
  user_id: string;
  channel: string;
  description?: string | null;
  speed_score?: number | null;
  cost_score?: number | null;
  difficulty_score?: number | null;
  reasoning?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface NewResearchRiskInput {
  business_id: string;
  user_id: string;
  title: string;
  description?: string | null;
  severity?: string | null;
  mitigation?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface NewResearchHypothesisInput {
  business_id: string;
  user_id: string;
  title: string;
  description?: string | null;
  test_method?: string | null;
  success_criteria?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface NewResearchEvidenceInput {
  business_id: string;
  user_id: string;
  claim: string;
  source?: string | null;
  source_url?: string | null;
  evidence_type?: string | null;
  confidence?: ResearchConfidence | null;
  notes?: string | null;
}

// ---------------------------------------------------------------------------
// Input types — update
// ---------------------------------------------------------------------------

export interface UpdateResearchReportInput {
  id: string;
  business_id: string;
  title?: string;
  status?: ResearchStatus;
  opportunity_score?: number | null;
  thesis?: string | null;
  target_customer?: string | null;
  money_pool?: string | null;
  wedge?: string | null;
  recommendation?: string | null;
  summary?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface UpdateResearchCustomerSegmentInput {
  id: string;
  business_id: string;
  name?: string;
  description?: string | null;
  pain_level?: number | null;
  ability_to_pay?: number | null;
  reachability?: number | null;
  market_size_guess?: string | null;
  channels?: string[] | null;
  evidence_summary?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface UpdateResearchBuyerBudgetInput {
  id: string;
  business_id: string;
  buyer?: string;
  budget_owner?: string | null;
  existing_spend?: string | null;
  willingness_to_pay?: string | null;
  value_driver?: string | null;
  pricing_signal?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface UpdateResearchCompetitorInput {
  id: string;
  business_id: string;
  name?: string;
  url?: string | null;
  category?: string | null;
  positioning?: string | null;
  pricing_summary?: string | null;
  strengths?: string[] | null;
  weaknesses?: string[] | null;
  wedge_opportunity?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface UpdateResearchMonetizationModelInput {
  id: string;
  business_id: string;
  model?: string;
  buyer?: string | null;
  price_assumption?: string | null;
  value_metric?: string | null;
  reasoning?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface UpdateResearchDistributionChannelInput {
  id: string;
  business_id: string;
  channel?: string;
  description?: string | null;
  speed_score?: number | null;
  cost_score?: number | null;
  difficulty_score?: number | null;
  reasoning?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface UpdateResearchRiskInput {
  id: string;
  business_id: string;
  title?: string;
  description?: string | null;
  severity?: string | null;
  mitigation?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface UpdateResearchHypothesisInput {
  id: string;
  business_id: string;
  title?: string;
  description?: string | null;
  test_method?: string | null;
  success_criteria?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
}

export interface UpdateResearchEvidenceInput {
  id: string;
  business_id: string;
  claim?: string;
  source?: string | null;
  source_url?: string | null;
  evidence_type?: string | null;
  confidence?: ResearchConfidence | null;
  notes?: string | null;
}
