import type {
  AnalyticsPlan,
  BusinessBlueprint,
  BusinessTypeGuess,
  HumanRequiredAction,
  MarketingPlan,
  NextAutonomousAction,
  RequiredPermission,
  SalesPlan,
  StartupIdea,
  SuggestedTool,
} from "@/types/startup";

function normalizeList(value: string) {
  return value
    .split(/\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function inferBusinessType(idea: StartupIdea): BusinessTypeGuess {
  if (idea.businessTypeGuess !== "Unsure") {
    return idea.businessTypeGuess;
  }

  const haystack = [
    idea.oneLineIdea,
    idea.ideaDescription,
    idea.targetCustomer,
    idea.primaryGoal,
  ]
    .join(" ")
    .toLowerCase();

  if (
    haystack.includes("creator") ||
    haystack.includes("youtube") ||
    haystack.includes("newsletter") ||
    haystack.includes("podcast")
  ) {
    return "Creator Tool";
  }

  if (haystack.includes("agency") || haystack.includes("client services")) {
    return "Agency Tool";
  }

  if (
    haystack.includes("team") ||
    haystack.includes("sales") ||
    haystack.includes("ops") ||
    haystack.includes("enterprise") ||
    haystack.includes("workflow")
  ) {
    return "B2B";
  }

  if (
    haystack.includes("consumer") ||
    haystack.includes("student") ||
    haystack.includes("parent") ||
    haystack.includes("fitness") ||
    haystack.includes("travel")
  ) {
    return "B2C";
  }

  return "Prosumer";
}

function getTargetCustomer(idea: StartupIdea, businessType: BusinessTypeGuess) {
  if (idea.targetCustomer.trim()) {
    return idea.targetCustomer.trim();
  }

  switch (businessType) {
    case "B2B":
      return "lean software teams with a painful manual workflow";
    case "B2C":
      return "high-intent consumers looking for a faster self-serve solution";
    case "Creator Tool":
      return "creators who need to publish more without adding headcount";
    case "Agency Tool":
      return "agency owners who need to systemize delivery and reporting";
    case "Prosumer":
      return "power users who want professional-grade leverage without enterprise overhead";
    default:
      return "early adopters in the AI/software market";
  }
}

function getPainHypothesis(
  idea: StartupIdea,
  targetCustomer: string,
  businessType: BusinessTypeGuess,
) {
  const concept = idea.oneLineIdea.trim().toLowerCase() || "the workflow";

  switch (businessType) {
    case "B2B":
      return `${targetCustomer} are losing time and margin because ${concept} is still handled with fragmented tools, handoffs, and spreadsheets.`;
    case "B2C":
      return `${targetCustomer} want a fast outcome without learning complex software, but current options feel bloated, expensive, or too generic.`;
    case "Creator Tool":
      return `${targetCustomer} need to turn one idea into repeatable content, but their current stack forces too much manual editing, packaging, and publishing work.`;
    case "Agency Tool":
      return `${targetCustomer} need client-ready outputs on a predictable cadence, but current processes rely too heavily on founder memory and custom effort.`;
    case "Prosumer":
      return `${targetCustomer} want a tool that feels powerful on day one, but not enterprise-heavy. Existing products either oversimplify or bury the workflow in setup.`;
    default:
      return `${targetCustomer} have a real operational pain point that is expensive enough to solve, but the current workflow still feels too manual.`;
  }
}

function getSuggestedStack(idea: StartupIdea) {
  const haystack = [idea.oneLineIdea, idea.ideaDescription].join(" ").toLowerCase();
  const stack = [
    "Next.js 16 app shell for the product and marketing surface",
    "TypeScript for typed workflows, prompts, and internal actions",
    "Tailwind CSS for rapid premium UI iteration",
  ];

  if (
    haystack.includes("ai") ||
    haystack.includes("agent") ||
    haystack.includes("assistant") ||
    haystack.includes("automation")
  ) {
    stack.push("Provider-agnostic AI orchestration layer for later model routing");
  }

  if (haystack.includes("dashboard") || haystack.includes("analytics")) {
    stack.push("Structured event schema plus warehouse-friendly analytics layer");
  }

  if (haystack.includes("mobile")) {
    stack.push("React Native or Expo companion app after web workflow proves demand");
  }

  if (haystack.includes("workflow") || haystack.includes("ops")) {
    stack.push("Background job runner for queued automations and long-running tasks");
  }

  stack.push("Supabase auth and Postgres once persistence is introduced");

  return stack;
}

function getSuggestedTools(
  idea: StartupIdea,
  businessType: BusinessTypeGuess,
): SuggestedTool[] {
  const tools: SuggestedTool[] = [
    {
      name: "Vercel",
      category: "Build",
      purpose: "Deploy the landing page, app shell, and future API routes quickly.",
    },
    {
      name: "PostHog",
      category: "Analytics",
      purpose: "Track activation, retention, and feature usage from the first launch cohort.",
    },
    {
      name: "Linear",
      category: "Operations",
      purpose: "Convert blueprint actions into a visible execution queue.",
    },
  ];

  if (businessType === "B2B" || businessType === "Agency Tool") {
    tools.push({
      name: "Apollo or Clay",
      category: "Growth",
      purpose: "Build a focused list of outbound targets and enrich decision-maker context.",
    });
    tools.push({
      name: "HubSpot or Attio",
      category: "Growth",
      purpose: "Manage outbound pipeline, call notes, and early deal stages.",
    });
  }

  if (businessType === "B2C") {
    tools.push({
      name: "Meta Ads",
      category: "Growth",
      purpose: "Validate acquisition economics once messaging and onboarding are stable.",
    });
    tools.push({
      name: "Customer.io",
      category: "Growth",
      purpose: "Run lifecycle nudges for activation and retention loops.",
    });
  }

  if (businessType === "Creator Tool") {
    tools.push({
      name: "CapCut or Descript",
      category: "Growth",
      purpose: "Turn demo moments into short clips for creator-led acquisition.",
    });
    tools.push({
      name: "Beehiiv or Kit",
      category: "Growth",
      purpose: "Capture and nurture creator and community interest with launches and updates.",
    });
  }

  const preferredTools = normalizeList(idea.preferredTools).slice(0, 3);

  preferredTools.forEach((toolName) => {
    tools.push({
      name: toolName,
      category: "Operations",
      purpose: "Included because it was explicitly requested in the intake boundaries.",
    });
  });

  return tools;
}

function getRequiredPermissions(
  idea: StartupIdea,
  businessType: BusinessTypeGuess,
): RequiredPermission[] {
  const permissions: RequiredPermission[] = [
    {
      title: "Deployment and domain access",
      reason: "Required to publish the product, configure DNS, and point the marketing site live.",
      level: "Required",
    },
    {
      title: "Analytics workspace approval",
      reason: "Needed to create the event taxonomy, dashboards, and team access model.",
      level: "Required",
    },
    {
      title: "Repository and hosting credentials",
      reason: "Needed so bucks.ai can own shipping velocity inside a controlled environment.",
      level: "Required",
    },
  ];

  if (businessType === "B2B" || businessType === "Agency Tool") {
    permissions.push({
      title: "Outbound domain and inbox approval",
      reason: "Needed before any sales or outreach workflows can be prepared for human sign-off.",
      level: "Recommended",
    });
  }

  if (normalizeList(idea.preferredTools).length > 0) {
    permissions.push({
      title: "Third-party tool workspace access",
      reason: "Needed to honor the preferred tools listed in the intake and configure them correctly.",
      level: "Recommended",
    });
  }

  return permissions;
}

function getMarketingPlan(businessType: BusinessTypeGuess): MarketingPlan {
  switch (businessType) {
    case "B2B":
      return {
        motion: "Founder-led authority plus outbound proof building.",
        channels: [
          "LinkedIn thought pieces tied to one painful workflow",
          "Founder demos shared in targeted operator communities",
          "High-signal case-study landing pages for each ICP slice",
        ],
        launchAssets: [
          "Pain-to-outcome landing page",
          "Short demo walkthrough",
          "ROI calculator or before/after workflow proof",
        ],
        experiments: [
          "Test one vertical-specific landing page per ICP segment",
          "Pair outbound sequences with proof-driven retargeting",
          "Publish short teardown posts showing the manual workflow replaced",
        ],
      };
    case "B2C":
      return {
        motion: "Content, social, and paid acquisition around a fast self-serve loop.",
        channels: [
          "Short-form social clips",
          "SEO pages tied to high-intent problems",
          "Paid social once onboarding conversion stabilizes",
        ],
        launchAssets: [
          "Product explainer page",
          "Creator-ready demo clips",
          "Email welcome sequence for activated users",
        ],
        experiments: [
          "A/B test messaging against two top pains",
          "Run low-budget social ad creative tests",
          "Add referral hooks after initial activation is clear",
        ],
      };
    case "Creator Tool":
      return {
        motion: "Creator-first launch with visible product usage in public.",
        channels: [
          "Creator partnerships",
          "Short-form demo clips",
          "Community seeding in creator circles",
        ],
        launchAssets: [
          "Before/after content examples",
          "Shareable demo clips",
          "Launch thread with creator use cases",
        ],
        experiments: [
          "Seed a small cohort of creators for public feedback loops",
          "Turn onboarding wins into weekly clip-based distribution",
          "Bundle templates that creators can share downstream",
        ],
      };
    case "Agency Tool":
      return {
        motion: "Case-study driven acquisition backed by direct outreach to agency operators.",
        channels: [
          "Direct agency outreach",
          "Niche agency communities",
          "Case-study landing pages by service line",
        ],
        launchAssets: [
          "Operational case study",
          "Service-line specific pitch deck",
          "Client deliverable examples",
        ],
        experiments: [
          "Offer pilot automation audits to five target agencies",
          "Package one repeatable case study per agency niche",
          "Create a calculator tied to margin or utilization gains",
        ],
      };
    case "Prosumer":
      return {
        motion: "Hybrid content plus community education for sophisticated individual users.",
        channels: [
          "Product-led content",
          "Niche communities and forums",
          "Email nurture for activated trial users",
        ],
        launchAssets: [
          "Problem-first product page",
          "Template gallery",
          "Feature walkthrough email sequence",
        ],
        experiments: [
          "Test one paid acquisition channel only after retention signals",
          "Launch templates tied to the top use case",
          "Use community AMAs to tighten positioning language",
        ],
      };
    default:
      return {
        motion: "Focused launch to an early adopter segment with quick messaging feedback loops.",
        channels: ["Founder content", "Communities", "Direct outreach"],
        launchAssets: ["Landing page", "Demo", "Email capture"],
        experiments: [
          "Validate one core pain with one tight segment",
          "Collect objections and feed them back into positioning",
          "Convert interest into calls or signups inside the first two weeks",
        ],
      };
  }
}

function getSalesPlan(businessType: BusinessTypeGuess): SalesPlan {
  switch (businessType) {
    case "B2B":
      return {
        motion: "Outreach-heavy founder-led sales with tight ICP qualification.",
        channels: ["Cold email", "Warm LinkedIn follow-up", "Founder discovery calls"],
        enablement: [
          "Vertical-specific call script",
          "Short ROI proof deck",
          "Objection handling notes for budget, security, and workflow fit",
        ],
        sequence: [
          "Build a 50-account ICP list",
          "Send pain-specific outreach tied to one workflow",
          "Book discovery calls and capture objections",
          "Turn top objections into landing page proof and roadmap priorities",
        ],
      };
    case "B2C":
      return {
        motion: "Lifecycle nudges and conversion optimization more than classic sales.",
        channels: ["Product onboarding email", "Retargeting", "High-intent support touchpoints"],
        enablement: [
          "Activation email sequence",
          "Pricing FAQ",
          "Retention save flow for near-converted users",
        ],
        sequence: [
          "Drive signups into one fast activation path",
          "Trigger nudges for stalled onboarding steps",
          "Collect cancellation reasons and route them into product fixes",
        ],
      };
    case "Creator Tool":
      return {
        motion: "Creator outreach plus social proof loops.",
        channels: ["Creator DMs", "Launch partners", "Community moderators"],
        enablement: [
          "Creator pilot offer",
          "Swipeable launch assets",
          "Public proof package showing content uplift",
        ],
        sequence: [
          "Recruit 10 creators with relevant audience overlap",
          "Co-create examples they can publish publicly",
          "Use the best examples as onboarding proof",
        ],
      };
    case "Agency Tool":
      return {
        motion: "Direct agency outreach supported by case studies and audits.",
        channels: ["Direct email", "Agency operator communities", "Referral partnerships"],
        enablement: [
          "Agency audit offer",
          "Process teardown deck",
          "Service-line specific ROI narrative",
        ],
        sequence: [
          "Shortlist agencies with repeatable fulfillment pain",
          "Lead with an audit and one clear process bottleneck",
          "Convert pilots into case studies and referrals",
        ],
      };
    case "Prosumer":
      return {
        motion: "Low-friction self-serve conversion with optional high-touch support for serious users.",
        channels: ["Email nurture", "Live demo office hours", "Community referrals"],
        enablement: [
          "Template library",
          "Setup checklist",
          "Advanced workflow guide",
        ],
        sequence: [
          "Drive signups into a strong template-led onboarding path",
          "Invite activated users to office hours",
          "Turn advanced users into referral and testimonial sources",
        ],
      };
    default:
      return {
        motion: "Manual founder follow-up while the ICP becomes clearer.",
        channels: ["Email", "Community", "Warm intros"],
        enablement: ["Short pitch", "Demo", "Notes template"],
        sequence: [
          "Talk to early interested users",
          "Find the repeated buying trigger",
          "Tighten positioning before scaling distribution",
        ],
      };
  }
}

function getAnalyticsPlan(idea: StartupIdea): AnalyticsPlan {
  const northStarMetric =
    idea.successMetric.trim() || "Qualified activations per week";

  return {
    northStarMetric,
    events: [
      "Landing page CTA clicked",
      "Idea intake started",
      "Blueprint generated",
      "Core activation milestone completed",
      "Repeat usage or return session within 7 days",
    ],
    dashboards: [
      "Acquisition to activation funnel",
      "Weekly cohort retention",
      "Top feature engagement by customer segment",
      "Founder operating dashboard with spend vs. outcomes",
    ],
    reviewCadence: [
      "Daily review during launch week",
      "Weekly growth and product review",
      "Monthly decision checkpoint against kill criteria",
    ],
  };
}

function getHumanRequiredActions(
  idea: StartupIdea,
  businessType: BusinessTypeGuess,
): HumanRequiredAction[] {
  const actions: HumanRequiredAction[] = [
    {
      title: "Approve legal terms, privacy policy, and risk posture",
      reason: "Legal commitments must stay human-approved before anything goes live.",
      owner: "Founder or legal owner",
    },
    {
      title: "Approve payment processor setup and billing rules",
      reason: "Financial accounts, pricing, and charge risk require explicit human approval.",
      owner: "Founder or finance owner",
    },
    {
      title: "Approve contracts or live client agreements",
      reason: "Any contract, proposal, or client-facing commitment stays outside autonomous execution.",
      owner: "Founder or account owner",
    },
    {
      title: "Complete identity verification for vendors or platforms",
      reason: "Business identity checks cannot be delegated to autonomous flows.",
      owner: "Founder",
    },
  ];

  if (businessType === "B2B" || businessType === "Agency Tool") {
    actions.push({
      title: "Review live outreach copy before it reaches prospects",
      reason: "Live client communication is explicitly reserved for human sign-off.",
      owner: "Founder or sales owner",
    });
  }

  const customHumanOnly = normalizeList(idea.humanOnlyActions);

  customHumanOnly.slice(0, 3).forEach((item) => {
    actions.push({
      title: item,
      reason: "Added from the intake boundaries as a founder-defined human-only action.",
      owner: "Founder-defined approver",
    });
  });

  return actions;
}

function getNextAutonomousActions(
  idea: StartupIdea,
  businessType: BusinessTypeGuess,
): NextAutonomousAction[] {
  const actions: NextAutonomousAction[] = [
    {
      title: "Refine positioning into a launch narrative",
      detail: `Translate "${idea.oneLineIdea}" into homepage messaging, proof points, and a simple offer.`,
      phase: "Strategy",
    },
    {
      title: "Turn the blueprint into an MVP delivery plan",
      detail: "Sequence the first build into a narrow launch scope with one activation path and one retention loop.",
      phase: "Product",
    },
    {
      title: "Draft analytics instrumentation",
      detail: "Map the north-star metric to events, funnel checkpoints, and the first operator dashboard.",
      phase: "Analytics",
    },
  ];

  if (businessType === "B2B" || businessType === "Agency Tool") {
    actions.push({
      title: "Assemble outbound target list and proof assets",
      detail: "Prepare ICP filters, outreach angles, and one strong case-study page before live sending begins.",
      phase: "Go-to-market",
    });
  } else if (businessType === "Creator Tool") {
    actions.push({
      title: "Prepare creator launch kit",
      detail: "Package demo clips, creator examples, and community seeding posts for the first cohort.",
      phase: "Go-to-market",
    });
  } else {
    actions.push({
      title: "Prepare acquisition experiments",
      detail: "Build the first landing page variants, creative hooks, and signup loops for launch week.",
      phase: "Growth",
    });
  }

  return actions;
}

function getMvpScope(idea: StartupIdea, businessType: BusinessTypeGuess) {
  const scope = [
    "Focused landing page with a single promise and strong call to action",
    "Core workflow that proves the promised outcome end-to-end",
    "Simple admin or operator view for observing early usage",
    "Instrumentation for activation and retention checkpoints",
  ];

  if (businessType === "B2B" || businessType === "Agency Tool") {
    scope.push("Lead capture and qualification flow for founder-led follow-up");
  }

  if (businessType === "B2C" || businessType === "Creator Tool") {
    scope.push("Fast self-serve onboarding with one clear time-to-value moment");
  }

  if (idea.ideaDescription.trim()) {
    scope.push(`Differentiated workflow anchor: ${idea.ideaDescription.trim()}`);
  }

  return scope;
}

function getDifferentiation(
  idea: StartupIdea,
  businessType: BusinessTypeGuess,
) {
  const points = [
    `Narrative built around ${idea.primaryGoal.trim().toLowerCase() || "a concrete founder outcome"} instead of generic AI positioning.`,
    "Tighter launch scope than incumbents, making time-to-value easier to understand and buy.",
  ];

  if (businessType === "B2B") {
    points.push("Workflow-specific proof and ROI language rather than broad productivity claims.");
  }

  if (businessType === "Creator Tool") {
    points.push("Public examples and creator-visible output quality become the distribution moat.");
  }

  if (businessType === "Agency Tool") {
    points.push("Case-study led trust with direct ties to utilization, margin, or turnaround time.");
  }

  return points;
}

function getRisks(idea: StartupIdea, businessType: BusinessTypeGuess) {
  const risks = [
    "The initial ICP may be too broad, causing weak messaging and noisy feedback.",
    "The MVP could include too many workflows before one repeatable value moment is proven.",
  ];

  if (businessType === "B2B" || businessType === "Agency Tool") {
    risks.push("Outbound interest may not convert unless the ROI story is specific and credible.");
  }

  if (businessType === "B2C" || businessType === "Creator Tool") {
    risks.push("Acquisition can outpace retention if onboarding does not create value in the first session.");
  }

  normalizeList(idea.hardConstraints)
    .slice(0, 2)
    .forEach((constraint) => {
      risks.push(`Constraint pressure: ${constraint}.`);
    });

  normalizeList(idea.forbiddenActions)
    .slice(0, 2)
    .forEach((constraint) => {
      risks.push(`Operational boundary to respect: ${constraint}.`);
    });

  return risks;
}

function getSuccessMetrics(idea: StartupIdea, businessType: BusinessTypeGuess) {
  const metrics = [idea.successMetric.trim() || "Consistent weekly activated users"];

  if (businessType === "B2B" || businessType === "Agency Tool") {
    metrics.push("Positive reply rate from the first outbound cohort");
    metrics.push("Discovery-to-pilot conversion rate");
  } else {
    metrics.push("Visitor-to-signup conversion rate");
    metrics.push("7-day activation or retention rate");
  }

  metrics.push("Time from visit to first value moment");

  return metrics;
}

function getKillCriteria(idea: StartupIdea, businessType: BusinessTypeGuess) {
  const criteria = [
    `Pause or reposition if "${idea.primaryGoal.trim() || "the primary goal"}" is still unsupported after two clear iteration cycles.`,
    "Stop expanding scope if activation remains weak after simplifying onboarding and messaging.",
  ];

  if (businessType === "B2B" || businessType === "Agency Tool") {
    criteria.push("Revisit the ICP if outbound replies stay low despite targeted messaging and strong proof assets.");
  } else {
    criteria.push("Cut paid acquisition experiments if retention is weak and CAC cannot be justified.");
  }

  return criteria;
}

export function generateMockBlueprint(idea: StartupIdea): BusinessBlueprint {
  const businessType = inferBusinessType(idea);
  const targetCustomer = getTargetCustomer(idea, businessType);
  const analyticsPlan = getAnalyticsPlan(idea);

  return {
    businessSummary: `${idea.ideaName.trim() || "This startup"} is positioned as ${idea.oneLineIdea.trim() || "an AI-native software business"} for ${targetCustomer}. The first operating goal is ${idea.primaryGoal.trim() || "to validate demand quickly"} within ${idea.timeline.trim() || "a tight launch window"} while staying inside a working budget of ${idea.budget.trim() || "a disciplined MVP budget"}.`,
    businessType,
    targetCustomer,
    painHypothesis: getPainHypothesis(idea, targetCustomer, businessType),
    mvpScope: getMvpScope(idea, businessType),
    differentiation: getDifferentiation(idea, businessType),
    suggestedStack: getSuggestedStack(idea),
    requiredTools: getSuggestedTools(idea, businessType),
    requiredPermissions: getRequiredPermissions(idea, businessType),
    goToMarketMotion: getMarketingPlan(businessType).motion,
    marketingPlan: getMarketingPlan(businessType),
    salesPlan: getSalesPlan(businessType),
    analyticsPlan,
    humanRequiredActions: getHumanRequiredActions(idea, businessType),
    nextAutonomousActions: getNextAutonomousActions(idea, businessType),
    risks: getRisks(idea, businessType),
    successMetrics: getSuccessMetrics(idea, businessType),
    killCriteria: getKillCriteria(idea, businessType),
  };
}
