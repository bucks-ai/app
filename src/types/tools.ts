export type ToolCategory =
  | "Code"
  | "Deployment"
  | "Database"
  | "Auth"
  | "Payments"
  | "Analytics"
  | "Outreach"
  | "CRM"
  | "Marketing"
  | "Ads"
  | "Domains"
  | "AI Model"
  | "Automation"
  | "Monitoring"
  | "Storage";

export type ToolStatus =
  | "Preferred"
  | "Approved"
  | "External Approval Required"
  | "Blocked"
  | "Human Only";

export type SetupStatus =
  | "Fully Completed"
  | "Awaiting Human Legal Step"
  | "Requires Identity Or Payment Step"
  | "Blocked By Verification"
  | "Rejected By Policy"
  | "Not Connected";

export type RiskLevel = "Low" | "Medium" | "High" | "Critical";

export type ToolRegistryItem = {
  id: string;
  name: string;
  category: ToolCategory;
  status: ToolStatus;
  purpose: string;
  typicalUse: string;
  riskLevel: RiskLevel;
  canAiSetupFully: boolean;
  requiresTermsAcceptance: boolean;
  requiresIdentityVerification: boolean;
  requiresPaymentSetup: boolean;
  defaultPermissions: string[];
  humanOnlyReasons: string[];
  setupStatus: SetupStatus;
};

export type AutonomyRuleCategory =
  | "Spending"
  | "Outreach"
  | "Product"
  | "Sales"
  | "Legal";

export type AutonomyRule = {
  id: string;
  title: string;
  category: AutonomyRuleCategory;
  value: string;
  description: string;
  escalationRequired?: boolean;
  hardStop?: boolean;
};

export type AutonomyConstitution = {
  maxSpendPerActionUsd: number;
  maxDailySpendUsd: number;
  maxMonthlySpendUsd: number;
  maxColdEmailsPerDay: number;
  maxDMsPerDay: number;
  canDeployStaging: boolean;
  canDeployProductionIfTestsPass: boolean;
  cannotDeleteCustomerData: boolean;
  cannotSignContracts: boolean;
  cannotAcceptLegalTerms: boolean;
  cannotEnterBankTaxIdentityInformation: boolean;
  cannotGuaranteeCustomerOutcomes: boolean;
  maxDiscountPercent: number;
  mustEscalateActions: string[];
  humanOnlyActions: string[];
  rules: AutonomyRule[];
};
