import type {
  ResearchBuyerBudgetRecord,
  ResearchCompetitorRecord,
  ResearchConfidence,
  ResearchCustomerSegmentRecord,
  ResearchDistributionChannelRecord,
  ResearchEvidenceRecord,
  ResearchHypothesisRecord,
  ResearchMonetizationModelRecord,
  ResearchPriority,
  ResearchReportRecord,
  ResearchRiskRecord,
  ResearchStatus,
  ResearchSummary,
  ResearchWorkspace,
} from "@/types/research";

export type {
  ResearchBuyerBudgetRecord,
  ResearchCompetitorRecord,
  ResearchConfidence,
  ResearchCustomerSegmentRecord,
  ResearchDistributionChannelRecord,
  ResearchEvidenceRecord,
  ResearchHypothesisRecord,
  ResearchMonetizationModelRecord,
  ResearchPriority,
  ResearchReportRecord,
  ResearchRiskRecord,
  ResearchStatus,
  ResearchSummary,
  ResearchWorkspace,
};

export type ResearchClientResult<T> =
  | { ok: true; data: T; warning?: string }
  | { ok: false; code: string; error: string };

export type ResearchWorkspaceGenerateResult = {
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
};

export type ResearchCustomerSegmentCreateInput = {
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
};

export type ResearchCustomerSegmentUpdateInput =
  Partial<ResearchCustomerSegmentCreateInput> & {
    id: string;
  };

export type ResearchBuyerBudgetCreateInput = {
  buyer: string;
  budget_owner?: string | null;
  existing_spend?: string | null;
  willingness_to_pay?: string | null;
  value_driver?: string | null;
  pricing_signal?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
};

export type ResearchBuyerBudgetUpdateInput = Partial<ResearchBuyerBudgetCreateInput> & {
  id: string;
};

export type ResearchCompetitorCreateInput = {
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
};

export type ResearchCompetitorUpdateInput = Partial<ResearchCompetitorCreateInput> & {
  id: string;
};

export type ResearchMonetizationModelCreateInput = {
  model: string;
  buyer?: string | null;
  price_assumption?: string | null;
  value_metric?: string | null;
  reasoning?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
};

export type ResearchMonetizationModelUpdateInput =
  Partial<ResearchMonetizationModelCreateInput> & {
    id: string;
  };

export type ResearchDistributionChannelCreateInput = {
  channel: string;
  description?: string | null;
  speed_score?: number | null;
  cost_score?: number | null;
  difficulty_score?: number | null;
  reasoning?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
};

export type ResearchDistributionChannelUpdateInput =
  Partial<ResearchDistributionChannelCreateInput> & {
    id: string;
  };

export type ResearchRiskCreateInput = {
  title: string;
  description?: string | null;
  severity?: string | null;
  mitigation?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
};

export type ResearchRiskUpdateInput = Partial<ResearchRiskCreateInput> & {
  id: string;
};

export type ResearchHypothesisCreateInput = {
  title: string;
  description?: string | null;
  test_method?: string | null;
  success_criteria?: string | null;
  confidence?: ResearchConfidence | null;
  priority?: ResearchPriority;
};

export type ResearchHypothesisUpdateInput = Partial<ResearchHypothesisCreateInput> & {
  id: string;
};

export type ResearchEvidenceCreateInput = {
  claim: string;
  source?: string | null;
  source_url?: string | null;
  evidence_type?: string | null;
  confidence?: ResearchConfidence | null;
  notes?: string | null;
};
