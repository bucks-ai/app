// Static agent registry for bucks.ai's operating team.
// This is the source of truth for all 21 MVP agents across 6 nodes.
//
// Agents are pure static data — no DB, no runtime, no LLM calls.
// Business-aware status resolution lives in src/lib/agents/status.ts.

import type {
  AgentNodeId,
  AgentTemplate,
  AgentTemplateId,
} from "@/types/agents";

// ---------------------------------------------------------------------------
// Node metadata
// ---------------------------------------------------------------------------

const NODE_LABELS: Record<AgentNodeId, string> = {
  strategy: "Strategy",
  deployment: "Deployment",
  validation: "Validation",
  research: "Research",
  safety: "Safety & Permissions",
  orchestration: "Orchestration",
};

const NODE_DESCRIPTIONS: Record<AgentNodeId, string> = {
  strategy:
    "Captures founder intent, generates execution blueprints, and frames the opportunity thesis.",
  deployment:
    "Creates and manages code repositories, scaffolds applications, and monitors deployment health.",
  validation:
    "Structures customer discovery workflows, manages personas and hypotheses, and synthesizes feedback signals.",
  research:
    "Maps market opportunity, competitor landscape, monetisation models, distribution channels, and risk.",
  safety:
    "Monitors tool permission queues, flags high-risk operations, and enforces human-approval gates.",
  orchestration:
    "Routes tasks across nodes, surfaces the next recommended action, and monitors execution runs.",
};

export const AGENT_NODE_ORDER: AgentNodeId[] = [
  "strategy",
  "deployment",
  "validation",
  "research",
  "safety",
  "orchestration",
];

// ---------------------------------------------------------------------------
// Static agent definitions
// ---------------------------------------------------------------------------

const AGENTS: AgentTemplate[] = [
  // -------------------------------------------------------------------------
  // Strategy Node
  // -------------------------------------------------------------------------
  {
    id: "idea_intake",
    name: "Idea Intake Agent",
    node: "strategy",
    description: "Captures and structures the founder's business idea from the intake wizard.",
    purpose:
      "Turn raw founder input (name, idea, goal, budget, timeline, constraints) into a structured business record that downstream agents can act on.",
    capabilities: [
      {
        id: "intake_capture",
        label: "Intake capture",
        description: "Reads multi-step intake form fields and persists a business record.",
      },
      {
        id: "idea_structuring",
        label: "Idea structuring",
        description: "Normalises free-text fields into typed business metadata.",
      },
    ],
    toolAccess: {
      allowed: ["blueprint_read", "activity_log_write"],
      blocked: ["external_web", "outreach", "github_write", "vercel_write"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "draft",
    mvpBackingFeature: "Intake wizard — /intake + /api/businesses/save-blueprint",
  },
  {
    id: "blueprint",
    name: "Blueprint Agent",
    node: "strategy",
    description: "Generates the launch blueprint from intake data using AI.",
    purpose:
      "Transform a structured business idea into a comprehensive launch blueprint covering execution phases, tool requirements, milestones, and risk flags.",
    capabilities: [
      {
        id: "blueprint_generation",
        label: "Blueprint generation",
        description: "Calls the AI generation pipeline to produce a structured launch blueprint.",
      },
      {
        id: "blueprint_save",
        label: "Blueprint save",
        description: "Persists the generated blueprint to business_blueprints.",
      },
    ],
    toolAccess: {
      allowed: ["blueprint_read", "blueprint_write", "llm_generate", "activity_log_write"],
      blocked: ["external_web", "outreach", "github_write", "vercel_write"],
    },
    approvalRequirements: [
      {
        action: "save_blueprint",
        reason: "Founder must review and approve the AI-generated blueprint before it becomes the execution plan.",
        approver: "founder",
      },
    ],
    riskLevel: "medium",
    autonomyLevel: "execute_with_approval",
    mvpBackingFeature: "AI blueprint generation — /api/generate-blueprint",
  },
  {
    id: "opportunity_framing",
    name: "Opportunity Framing Agent",
    node: "strategy",
    description: "Synthesises the core opportunity thesis from research and blueprint data.",
    purpose:
      "Derive a concise, evidence-backed opportunity framing (wedge, target customer, money pool) from the research workspace and blueprint to guide strategic decisions.",
    capabilities: [
      {
        id: "thesis_synthesis",
        label: "Thesis synthesis",
        description: "Combines blueprint intent, research segments, and competitor gaps into an opportunity thesis.",
      },
      {
        id: "wedge_identification",
        label: "Wedge identification",
        description: "Identifies the specific angle or insight that gives this business an edge.",
      },
    ],
    toolAccess: {
      allowed: ["blueprint_read", "research_read", "activity_log_read"],
      blocked: ["external_web", "outreach", "blueprint_write", "research_write"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "suggest",
    mvpBackingFeature: "Research mode backend — /api/businesses/[id]/research",
  },

  // -------------------------------------------------------------------------
  // Deployment Node
  // -------------------------------------------------------------------------
  {
    id: "repository",
    name: "Repository Agent",
    node: "deployment",
    description: "Creates and tracks the GitHub repository for the business.",
    purpose:
      "Provision a GitHub repository with the correct name, visibility, and metadata so the scaffold and deployment agents have a target to work with.",
    capabilities: [
      {
        id: "repo_creation",
        label: "Repo creation",
        description: "Creates a GitHub repository via the GitHub API after founder approval.",
      },
      {
        id: "repo_metadata_read",
        label: "Repo metadata read",
        description: "Reads repository state, branch list, and commit activity.",
      },
    ],
    toolAccess: {
      allowed: ["github_read", "github_write", "activity_log_write", "tool_permission_read"],
      blocked: ["external_web", "outreach", "vercel_write"],
    },
    approvalRequirements: [
      {
        action: "create_github_repo",
        reason: "GitHub permission must be approved by the founder before a repo can be created.",
        approver: "founder",
      },
    ],
    riskLevel: "medium",
    autonomyLevel: "execute_with_approval",
    mvpBackingFeature: "GitHub repo creation — /api/github/create-repo",
  },
  {
    id: "scaffold",
    name: "Scaffold Agent",
    node: "deployment",
    description: "Writes a deployable Next.js scaffold into the GitHub repository.",
    purpose:
      "Prepare the business repository as a production-ready Next.js application so Vercel can deploy it immediately.",
    capabilities: [
      {
        id: "scaffold_generation",
        label: "Scaffold generation",
        description: "Generates Next.js boilerplate files and commits them to the repository.",
      },
      {
        id: "scaffold_status_check",
        label: "Scaffold status check",
        description: "Verifies the scaffold is present and deployment-ready.",
      },
    ],
    toolAccess: {
      allowed: ["github_read", "github_write", "activity_log_write"],
      blocked: ["external_web", "outreach", "vercel_write"],
    },
    approvalRequirements: [
      {
        action: "push_scaffold",
        reason: "Writing files to the repository requires GitHub permission to be approved.",
        approver: "founder",
      },
    ],
    riskLevel: "medium",
    autonomyLevel: "execute_when_approved",
    mvpBackingFeature: "Next.js scaffold preparation — /api/github/prepare-next-scaffold",
  },
  {
    id: "deployment_status",
    name: "Deployment Status Agent",
    node: "deployment",
    description: "Monitors Vercel deployment health and surfaces live deployment URLs.",
    purpose:
      "Track the current state of the Vercel project, detect failed builds, and report the live deployment URL so founders know when their app is accessible.",
    capabilities: [
      {
        id: "vercel_status_read",
        label: "Vercel status read",
        description: "Reads Vercel project and deployment state via the Vercel API.",
      },
      {
        id: "deployment_health_report",
        label: "Deployment health report",
        description: "Surfaces deployment URL, build status, and any failure reasons.",
      },
    ],
    toolAccess: {
      allowed: ["vercel_read", "activity_log_read", "activity_log_write"],
      blocked: ["external_web", "outreach", "vercel_write", "github_write"],
    },
    approvalRequirements: [
      {
        action: "trigger_deployment_change",
        reason: "Any write to Vercel (custom domains, env vars) requires founder approval.",
        approver: "founder",
      },
    ],
    riskLevel: "low",
    autonomyLevel: "observe",
    mvpBackingFeature:
      "Deployment status backend/UI — /api/businesses/[id]/execution-status + /api/vercel/refresh-deployment-status",
  },

  // -------------------------------------------------------------------------
  // Validation Node
  // -------------------------------------------------------------------------
  {
    id: "persona",
    name: "Persona Agent",
    node: "validation",
    description: "Creates and enriches customer personas for the validation workspace.",
    purpose:
      "Build structured target-customer archetypes from blueprint segments so the founder has concrete profiles to validate against in discovery interviews.",
    capabilities: [
      {
        id: "persona_create",
        label: "Persona creation",
        description: "Generates persona records from blueprint segment descriptions.",
      },
      {
        id: "persona_read",
        label: "Persona read",
        description: "Reads and surfaces persona list for the validation workspace.",
      },
    ],
    toolAccess: {
      allowed: ["validation_read", "validation_write", "blueprint_read", "activity_log_write"],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [
      {
        action: "outreach_via_persona",
        reason: "No external outreach is initiated without explicit founder approval.",
        approver: "founder",
      },
    ],
    riskLevel: "low",
    autonomyLevel: "draft",
    mvpBackingFeature:
      "Customer validation backend/UI — /api/businesses/[id]/validation/personas",
  },
  {
    id: "hypothesis",
    name: "Hypothesis Agent",
    node: "validation",
    description: "Generates and tracks validation hypotheses for the business.",
    purpose:
      "Define testable beliefs about the market, customer, and product so the founder can structure discovery interviews around the highest-risk assumptions.",
    capabilities: [
      {
        id: "hypothesis_create",
        label: "Hypothesis creation",
        description: "Generates hypothesis records from blueprint risk areas and research findings.",
      },
      {
        id: "hypothesis_status_update",
        label: "Hypothesis status update",
        description: "Updates hypothesis confidence as feedback is collected.",
      },
    ],
    toolAccess: {
      allowed: [
        "validation_read",
        "validation_write",
        "blueprint_read",
        "research_read",
        "activity_log_write",
      ],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "draft",
    mvpBackingFeature:
      "Customer validation backend/UI — /api/businesses/[id]/validation/hypotheses",
  },
  {
    id: "feedback_analysis",
    name: "Feedback Analysis Agent",
    node: "validation",
    description: "Analyses customer feedback notes and extracts validation signal.",
    purpose:
      "Synthesise raw feedback notes into structured signal strength, pain patterns, and hypothesis updates so the founder can identify go/no-go evidence quickly.",
    capabilities: [
      {
        id: "signal_extraction",
        label: "Signal extraction",
        description: "Tags feedback notes with signal strength and relevant hypotheses.",
      },
      {
        id: "pattern_summarisation",
        label: "Pattern summarisation",
        description: "Groups common objections and pain signals across multiple interviews.",
      },
    ],
    toolAccess: {
      allowed: ["validation_read", "validation_write", "activity_log_read", "activity_log_write"],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "suggest",
    mvpBackingFeature:
      "Customer validation backend/UI — /api/businesses/[id]/validation/feedback",
  },

  // -------------------------------------------------------------------------
  // Research Node
  // -------------------------------------------------------------------------
  {
    id: "market_research",
    name: "Market Research Agent",
    node: "research",
    description: "Generates the research workspace from blueprint data.",
    purpose:
      "Seed the research workspace with opportunity thesis, target customer profile, and a market-size estimate so the founder has a structured view of the opportunity before building.",
    capabilities: [
      {
        id: "workspace_generation",
        label: "Workspace generation",
        description: "Generates research workspace from blueprint fields (no external web browsing in MVP).",
      },
      {
        id: "thesis_draft",
        label: "Thesis draft",
        description: "Drafts the opportunity thesis and money-pool description.",
      },
    ],
    toolAccess: {
      allowed: ["research_read", "research_write", "blueprint_read", "activity_log_write"],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "execute_with_approval",
    mvpBackingFeature:
      "Research mode backend — /api/businesses/[id]/research (action: generate)",
  },
  {
    id: "customer_segment",
    name: "Customer Segment Agent",
    node: "research",
    description: "Identifies and profiles customer segments for the business.",
    purpose:
      "Break the target market into discrete segments ranked by pain level, ability to pay, and reachability so the founder can prioritise which customers to talk to first.",
    capabilities: [
      {
        id: "segment_identification",
        label: "Segment identification",
        description: "Derives segment records from blueprint and research report data.",
      },
      {
        id: "segment_scoring",
        label: "Segment scoring",
        description: "Assigns pain, ability-to-pay, and reachability scores per segment.",
      },
    ],
    toolAccess: {
      allowed: ["research_read", "research_write", "blueprint_read", "activity_log_write"],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "draft",
    mvpBackingFeature:
      "Research mode backend — /api/businesses/[id]/research/segments",
  },
  {
    id: "competitor",
    name: "Competitor Agent",
    node: "research",
    description: "Maps the competitive landscape and identifies wedge opportunities.",
    purpose:
      "Catalogue direct and indirect competitors with pricing, strengths, weaknesses, and wedge angles so the founder can articulate a differentiated position.",
    capabilities: [
      {
        id: "competitor_mapping",
        label: "Competitor mapping",
        description: "Generates competitor records from blueprint data (no external web in MVP).",
      },
      {
        id: "wedge_analysis",
        label: "Wedge analysis",
        description: "Identifies where this business can outflank each competitor.",
      },
    ],
    toolAccess: {
      allowed: ["research_read", "research_write", "blueprint_read", "activity_log_write"],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "draft",
    mvpBackingFeature:
      "Research mode backend — /api/businesses/[id]/research/competitors",
  },
  {
    id: "monetization",
    name: "Monetization Agent",
    node: "research",
    description: "Models pricing and monetisation strategies for the business.",
    purpose:
      "Enumerate viable monetisation models with buyer types, price assumptions, and value metrics so the founder can test willingness to pay during validation.",
    capabilities: [
      {
        id: "model_generation",
        label: "Model generation",
        description: "Generates monetisation model records from blueprint and segment data.",
      },
      {
        id: "pricing_signal_tracking",
        label: "Pricing signal tracking",
        description: "Records competitor pricing signals and buyer budget data.",
      },
    ],
    toolAccess: {
      allowed: ["research_read", "research_write", "blueprint_read", "activity_log_write"],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "suggest",
    mvpBackingFeature:
      "Research mode backend — /api/businesses/[id]/research/buyer-budgets",
  },
  {
    id: "distribution",
    name: "Distribution Agent",
    node: "research",
    description: "Maps acquisition channels and distribution strategies.",
    purpose:
      "Rank viable acquisition channels by speed, cost, and difficulty so the founder can choose the fastest route to first customers without spreading effort thin.",
    capabilities: [
      {
        id: "channel_mapping",
        label: "Channel mapping",
        description: "Generates distribution channel records from blueprint and segment data.",
      },
      {
        id: "channel_scoring",
        label: "Channel scoring",
        description: "Assigns speed, cost, and difficulty scores per channel.",
      },
    ],
    toolAccess: {
      allowed: ["research_read", "research_write", "blueprint_read", "activity_log_write"],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "suggest",
    mvpBackingFeature:
      "Research mode backend — /api/businesses/[id]/research/distribution",
  },
  {
    id: "risk",
    name: "Risk Agent",
    node: "research",
    description: "Identifies and scores business risks that could undermine the opportunity.",
    purpose:
      "Surface the highest-severity risks (market, technical, regulatory, competitive) early so the founder can design mitigation strategies before over-investing.",
    capabilities: [
      {
        id: "risk_identification",
        label: "Risk identification",
        description: "Generates risk records from blueprint and research data.",
      },
      {
        id: "risk_scoring",
        label: "Risk scoring",
        description: "Assigns severity levels and suggests mitigation strategies.",
      },
    ],
    toolAccess: {
      allowed: ["research_read", "research_write", "blueprint_read", "activity_log_write"],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "observe",
    mvpBackingFeature: "Research mode backend — /api/businesses/[id]/research/risks",
  },
  {
    id: "opportunity_scoring",
    name: "Opportunity Scoring Agent",
    node: "research",
    description: "Computes an opportunity score from research workspace data.",
    purpose:
      "Aggregate research signals (segment scores, risk severity, competitor gaps, monetisation confidence) into a single 0–100 score so the founder can make a go/no-go decision before the build phase.",
    capabilities: [
      {
        id: "score_computation",
        label: "Score computation",
        description: "Derives opportunity score from segment, competitor, risk, and monetisation data.",
      },
      {
        id: "recommendation_generation",
        label: "Recommendation generation",
        description: "Produces a proceed/pivot/kill recommendation with supporting rationale.",
      },
    ],
    toolAccess: {
      allowed: ["research_read", "research_write", "activity_log_write"],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "suggest",
    mvpBackingFeature:
      "Research mode backend — /api/businesses/[id]/research (opportunity_score field)",
  },

  // -------------------------------------------------------------------------
  // Safety / Permissions Node
  // -------------------------------------------------------------------------
  {
    id: "tool_permission",
    name: "Tool Permission Agent",
    node: "safety",
    description: "Monitors the tool permission queue and flags pending approvals.",
    purpose:
      "Track approval status for all external tools (GitHub, Vercel, Stripe, etc.) and surface pending decisions so no agent is blocked waiting on an unreviewed permission.",
    capabilities: [
      {
        id: "permission_monitoring",
        label: "Permission monitoring",
        description: "Reads the tool_permissions table and surfaces pending approvals.",
      },
      {
        id: "permission_status_report",
        label: "Permission status report",
        description: "Reports which tools are approved, blocked, or awaiting review.",
      },
    ],
    toolAccess: {
      allowed: ["tool_permission_read", "activity_log_read", "human_action_read"],
      blocked: ["external_web", "outreach", "tool_permission_write"],
    },
    approvalRequirements: [
      {
        action: "change_permission_status",
        reason: "All tool permission transitions are founder-controlled — this agent only monitors.",
        approver: "founder",
      },
    ],
    riskLevel: "low",
    autonomyLevel: "observe",
    mvpBackingFeature: "Tool permission setup queue — /api/tool-permissions",
  },
  {
    id: "risk_review",
    name: "Risk Review Agent",
    node: "safety",
    description: "Reviews high-risk operations and enforces human-approval gates.",
    purpose:
      "Intercept high-risk agent actions (writes to production, external outreach, legal/payment steps) and hold them until the founder explicitly approves or rejects.",
    capabilities: [
      {
        id: "action_interception",
        label: "Action interception",
        description: "Detects operations flagged as high-risk and creates human_required_actions.",
      },
      {
        id: "approval_tracking",
        label: "Approval tracking",
        description: "Monitors the human_required_actions queue for open approvals.",
      },
    ],
    toolAccess: {
      allowed: [
        "human_action_read",
        "human_action_write",
        "tool_permission_read",
        "activity_log_read",
      ],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [
      {
        action: "resolve_human_action",
        reason: "Human-required actions can only be resolved by the founder.",
        approver: "founder",
      },
    ],
    riskLevel: "human_controlled",
    autonomyLevel: "observe",
    mvpBackingFeature: "Human-required actions queue (human_required_actions table)",
  },

  // -------------------------------------------------------------------------
  // Orchestration Node
  // -------------------------------------------------------------------------
  {
    id: "task_router",
    name: "Task Router Agent",
    node: "orchestration",
    description: "Routes tasks to appropriate agents based on business phase and context.",
    purpose:
      "Determine which agents should be active at any given point in the business lifecycle and coordinate hand-offs between nodes so execution flows without gaps.",
    capabilities: [
      {
        id: "phase_detection",
        label: "Phase detection",
        description: "Reads execution phase and milestone state to determine which agents are relevant.",
      },
      {
        id: "task_routing",
        label: "Task routing",
        description: "Suggests which agent should handle the next unit of work.",
      },
    ],
    toolAccess: {
      allowed: [
        "activity_log_read",
        "blueprint_read",
        "tool_permission_read",
        "human_action_read",
      ],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "suggest",
    mvpBackingFeature: "Execution status backend — /api/businesses/[id]/execution-status",
  },
  {
    id: "next_action",
    name: "Next Action Agent",
    node: "orchestration",
    description: "Derives the single most important next action for the founder.",
    purpose:
      "Synthesise execution phase, blockers, and milestone state into one clear next action so the founder always knows what to do without reading every status panel.",
    capabilities: [
      {
        id: "next_action_derivation",
        label: "Next action derivation",
        description: "Reads execution status and derives the highest-priority recommended action.",
      },
      {
        id: "urgency_classification",
        label: "Urgency classification",
        description: "Labels next actions as critical/high/medium/low to guide prioritisation.",
      },
    ],
    toolAccess: {
      allowed: [
        "activity_log_read",
        "blueprint_read",
        "research_read",
        "validation_read",
        "tool_permission_read",
        "human_action_read",
      ],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "suggest",
    mvpBackingFeature:
      "Execution status next-actions + workspace next-action resolver — src/components/workspace/next-action.ts",
  },
  {
    id: "run_monitor",
    name: "Run Monitor Agent",
    node: "orchestration",
    description: "Monitors agent activity logs and surfaces anomalies or stalled runs.",
    purpose:
      "Watch the agent_activity_logs stream for failed runs, long-running operations, or unexpected silences, and alert the orchestration layer when intervention is needed.",
    capabilities: [
      {
        id: "log_monitoring",
        label: "Log monitoring",
        description: "Reads activity logs and detects failure or stall patterns.",
      },
      {
        id: "anomaly_surfacing",
        label: "Anomaly surfacing",
        description: "Creates human_required_actions for runs that need founder review.",
      },
    ],
    toolAccess: {
      allowed: [
        "activity_log_read",
        "human_action_write",
        "human_action_read",
      ],
      blocked: ["external_web", "outreach"],
    },
    approvalRequirements: [],
    riskLevel: "low",
    autonomyLevel: "observe",
    mvpBackingFeature:
      "Execution timeline backend — /api/businesses/[id]/execution-timeline",
  },
];

// ---------------------------------------------------------------------------
// Registry index — keyed by AgentTemplateId for O(1) lookups
// ---------------------------------------------------------------------------

export const AGENT_REGISTRY: Record<AgentTemplateId, AgentTemplate> = Object.fromEntries(
  AGENTS.map((agent) => [agent.id, agent])
) as Record<AgentTemplateId, AgentTemplate>;

// ---------------------------------------------------------------------------
// Exported helpers
// ---------------------------------------------------------------------------

export function getAgentTemplate(agentId: AgentTemplateId): AgentTemplate | null {
  return AGENT_REGISTRY[agentId] ?? null;
}

export function getAgentsByNode(nodeId: AgentNodeId): AgentTemplate[] {
  return AGENTS.filter((agent) => agent.node === nodeId);
}

export function getAllAgentTemplates(): AgentTemplate[] {
  return AGENTS;
}

export function getAgentNodeLabel(nodeId: AgentNodeId): string {
  return NODE_LABELS[nodeId];
}

export function getAgentNodeDescription(nodeId: AgentNodeId): string {
  return NODE_DESCRIPTIONS[nodeId];
}
