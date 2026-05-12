export type BusinessTypeGuess =
  | "B2B"
  | "B2C"
  | "Prosumer"
  | "Creator Tool"
  | "Agency Tool"
  | "Unsure";

export type AutonomyPreference =
  | "Recommend only"
  | "Ask before major actions"
  | "Execute within limits"
  | "Maximum autonomy";

export type StartupIdea = {
  ideaName: string;
  oneLineIdea: string;
  ideaDescription: string;
  targetCustomer: string;
  businessTypeGuess: BusinessTypeGuess;
  primaryGoal: string;
  successMetric: string;
  budget: string;
  timeline: string;
  autonomyPreference: AutonomyPreference;
  spendingLimit: string;
  hardConstraints: string;
  humanOnlyActions: string;
  forbiddenActions: string;
  preferredTools: string;
};

export type SuggestedTool = {
  name: string;
  category: "Build" | "Growth" | "Analytics" | "Operations";
  purpose: string;
};

export type RequiredPermission = {
  title: string;
  reason: string;
  level: "Required" | "Recommended";
};

export type HumanRequiredAction = {
  title: string;
  reason: string;
  owner: string;
};

export type NextAutonomousAction = {
  title: string;
  detail: string;
  phase: string;
};

export type MarketingPlan = {
  motion: string;
  channels: string[];
  launchAssets: string[];
  experiments: string[];
};

export type SalesPlan = {
  motion: string;
  channels: string[];
  enablement: string[];
  sequence: string[];
};

export type AnalyticsPlan = {
  northStarMetric: string;
  events: string[];
  dashboards: string[];
  reviewCadence: string[];
};

export type BusinessBlueprint = {
  businessSummary: string;
  businessType: BusinessTypeGuess;
  targetCustomer: string;
  painHypothesis: string;
  mvpScope: string[];
  differentiation: string[];
  suggestedStack: string[];
  requiredTools: SuggestedTool[];
  requiredPermissions: RequiredPermission[];
  goToMarketMotion: string;
  marketingPlan: MarketingPlan;
  salesPlan: SalesPlan;
  analyticsPlan: AnalyticsPlan;
  humanRequiredActions: HumanRequiredAction[];
  nextAutonomousActions: NextAutonomousAction[];
  risks: string[];
  successMetrics: string[];
  killCriteria: string[];
};
