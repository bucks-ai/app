export type StatusVariant = "accent" | "success" | "warning" | "danger" | "neutral";

export type DashboardBusiness = {
  id: string;
  name: string;
  businessType: string;
  status: string;
  statusVariant: StatusVariant;
  goal: string;
  created: string;
  overview: string;
  blueprintSummary: string;
  nextActions: string[];
  humanActions: string[];
  activity: ActivityItem[];
  permissions: ToolPermission[];
};

export type ActivityItem = {
  time: string;
  actor: string;
  event: string;
  tone?: StatusVariant;
};

export type HumanAction = {
  title: string;
  business: string;
  reason: string;
  status: string;
};

export type ToolPermission = {
  tool: string;
  access: string;
  note: string;
  tone: StatusVariant;
};

export const demoBusinesses: DashboardBusiness[] = [
  {
    id: "acme-analytics",
    name: "Acme Analytics",
    businessType: "B2B SaaS",
    status: "Blueprint created",
    statusVariant: "accent",
    goal: "10 paying users in 60 days",
    created: "Demo date: Apr 08, 2026",
    overview:
      "A lightweight analytics workspace for early B2B teams that need activation, retention, and revenue signals without a heavy data stack.",
    blueprintSummary:
      "Position around founder-led growth, ship a narrow metrics dashboard first, and validate with product-led SaaS operators who already track onboarding by spreadsheet.",
    nextActions: [
      "Draft landing page sections for the activation analytics wedge.",
      "Map the minimum event schema needed for the demo product.",
      "Prepare a 20-account founder-led outreach list for review.",
    ],
    humanActions: [
      "Approve the first outreach segment before any live messages are sent.",
      "Confirm monthly budget ceiling for paid enrichment tools.",
    ],
    activity: [
      {
        time: "09:42",
        actor: "Blueprint agent",
        event: "Created initial ICP, wedge, and launch sequence.",
        tone: "accent",
      },
      {
        time: "10:05",
        actor: "Stack agent",
        event: "Recommended Next.js, Postgres, and event ingestion queue.",
      },
      {
        time: "10:18",
        actor: "GTM agent",
        event: "Flagged outreach approval as human-required.",
        tone: "warning",
      },
    ],
    permissions: [
      {
        tool: "Vercel",
        access: "Staging-ready",
        note: "Production deploys stay approval-gated.",
        tone: "accent",
      },
      {
        tool: "CRM",
        access: "Mock only",
        note: "No live contacts are connected in this shell.",
        tone: "neutral",
      },
      {
        tool: "Email",
        access: "Human-required",
        note: "Outbound remains blocked until approval flows exist.",
        tone: "warning",
      },
    ],
  },
  {
    id: "clipforge-ai",
    name: "ClipForge AI",
    businessType: "Creator Tool",
    status: "GTM mapped",
    statusVariant: "success",
    goal: "5 pilot streamers",
    created: "Demo date: Apr 12, 2026",
    overview:
      "A clipping and repurposing assistant for streamers who want short-form highlights without spending hours in post-production.",
    blueprintSummary:
      "Lead with time saved per stream, validate through pilot streamer workflows, and keep the first product focused on highlight detection plus export presets.",
    nextActions: [
      "Turn the pilot offer into a one-page signup experience.",
      "Draft intake questions for streamer source content and publishing goals.",
      "Create a permission checklist for uploaded media handling.",
    ],
    humanActions: [
      "Review media rights language before asking for sample content.",
      "Approve any public creator outreach copy.",
    ],
    activity: [
      {
        time: "11:20",
        actor: "GTM agent",
        event: "Mapped pilot criteria and streamer outreach lanes.",
        tone: "success",
      },
      {
        time: "11:31",
        actor: "Ops agent",
        event: "Queued rights review before accepting real media uploads.",
        tone: "warning",
      },
      {
        time: "11:46",
        actor: "Product agent",
        event: "Scoped export presets for TikTok, Shorts, and Reels.",
      },
    ],
    permissions: [
      {
        tool: "Storage",
        access: "Pending",
        note: "Real file storage is not wired in this branch.",
        tone: "warning",
      },
      {
        tool: "Social APIs",
        access: "Blocked",
        note: "No publishing integrations are active.",
        tone: "danger",
      },
      {
        tool: "Analytics",
        access: "Sample only",
        note: "Dashboard numbers are placeholders.",
        tone: "neutral",
      },
    ],
  },
  {
    id: "invoicepilot",
    name: "InvoicePilot",
    businessType: "Agency Tool",
    status: "Permissions pending",
    statusVariant: "warning",
    goal: "First paid pilot",
    created: "Demo date: Apr 18, 2026",
    overview:
      "An invoice follow-up operator for small agencies that need cleaner collections workflows without adding finance headcount.",
    blueprintSummary:
      "Start with aging reminders and approval-controlled follow-up drafts, then validate with agencies that already manage collections in spreadsheets.",
    nextActions: [
      "Mock invoice aging states for the first operator dashboard.",
      "Draft collection follow-up templates for founder review.",
      "Prepare a pilot onboarding checklist for agency owners.",
    ],
    humanActions: [
      "Approve payment-related language before customer-facing use.",
      "Connect finance tools only after backend permissions are implemented.",
    ],
    activity: [
      {
        time: "13:02",
        actor: "Risk agent",
        event: "Escalated payment and collections language to human review.",
        tone: "warning",
      },
      {
        time: "13:14",
        actor: "Blueprint agent",
        event: "Defined first paid pilot success criteria.",
        tone: "accent",
      },
      {
        time: "13:33",
        actor: "Stack agent",
        event: "Kept accounting integrations deferred for backend work.",
      },
    ],
    permissions: [
      {
        tool: "Accounting",
        access: "Blocked",
        note: "No QuickBooks, Stripe, or bank data is connected.",
        tone: "danger",
      },
      {
        tool: "Email drafts",
        access: "Human-required",
        note: "Drafting is allowed in mock form only.",
        tone: "warning",
      },
      {
        tool: "CRM",
        access: "Sample only",
        note: "Pilot pipeline is demo data.",
        tone: "neutral",
      },
    ],
  },
];

export const demoActivity: ActivityItem[] = [
  {
    time: "Today 09:42",
    actor: "Blueprint agent",
    event: "Created a sample blueprint record for Acme Analytics.",
    tone: "accent",
  },
  {
    time: "Today 11:20",
    actor: "GTM agent",
    event: "Mapped pilot criteria for ClipForge AI.",
    tone: "success",
  },
  {
    time: "Today 13:02",
    actor: "Risk agent",
    event: "Marked InvoicePilot payment language as human-required.",
    tone: "warning",
  },
];

export const demoHumanActions: HumanAction[] = [
  {
    title: "Approve first outreach segment",
    business: "Acme Analytics",
    reason: "Live prospect contact requires founder approval.",
    status: "Needs review",
  },
  {
    title: "Review media rights language",
    business: "ClipForge AI",
    reason: "Uploaded creator content needs clear permission boundaries.",
    status: "Legal-adjacent",
  },
  {
    title: "Confirm payment copy",
    business: "InvoicePilot",
    reason: "Collections and payment workflows stay human-gated.",
    status: "Human-only",
  },
];

export const demoPermissions: ToolPermission[] = [
  {
    tool: "Blueprint generator",
    access: "Ready",
    note: "Existing OpenAI route remains untouched.",
    tone: "success",
  },
  {
    tool: "Supabase",
    access: "Not wired",
    note: "Auth and database integration are intentionally deferred.",
    tone: "warning",
  },
  {
    tool: "Outbound tools",
    access: "Approval-gated",
    note: "No live email, CRM, or social actions are connected.",
    tone: "warning",
  },
  {
    tool: "Billing",
    access: "Blocked",
    note: "No Stripe or payment operations exist in this shell.",
    tone: "danger",
  },
];

export function getDemoBusiness(id: string) {
  return demoBusinesses.find((business) => business.id === id);
}
