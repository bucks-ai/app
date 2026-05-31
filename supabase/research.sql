-- =============================================================================
-- bucks.ai — Research Node Schema
-- =============================================================================
-- IMPORTANT: Satvik must run this file in the Supabase SQL Editor after
-- merging feature/research-mode-backend into main.
-- This file is intentionally NOT applied automatically.
--
-- How to apply:
--   1. Go to Supabase project → SQL Editor
--   2. Paste this entire file and click Run
--
-- This schema is additive (create table IF NOT EXISTS, create index IF NOT EXISTS)
-- and safe to run on a live project. Re-running is idempotent for tables and
-- indexes, but not for policies — wrap policy creates in a transaction or drop
-- existing policies first if re-running.
-- =============================================================================


-- =============================================================================
-- UPDATED_AT TRIGGER
-- Reuses the shared set_updated_at() trigger function created in validation.sql.
-- If validation.sql has not been applied, uncomment the block below:
-- =============================================================================
-- create or replace function public.set_updated_at()
-- returns trigger
-- language plpgsql
-- as $$
-- begin
--   new.updated_at = now();
--   return new;
-- end;
-- $$;


-- =============================================================================
-- RESEARCH REPORTS
-- Top-level opportunity thesis and score for a business.
-- One report per business (most recent is considered the active report).
-- =============================================================================
create table if not exists public.research_reports (
  id                  uuid primary key default gen_random_uuid(),
  business_id         uuid references public.businesses(id) on delete cascade not null,
  user_id             uuid references auth.users(id) on delete cascade not null,

  title               text not null,

  -- Status: not_started | researching | draft | reviewed | ready_for_validation | needs_more_research
  status              text not null default 'draft',

  -- 0–100 opportunity score
  opportunity_score   integer check (opportunity_score >= 0 and opportunity_score <= 100),

  -- Narrative fields
  thesis              text,
  target_customer     text,
  money_pool          text,
  wedge               text,
  recommendation      text,
  summary             text,

  -- Confidence: assumption | weak_signal | medium_signal | strong_signal | validated | invalidated
  confidence          text,

  -- Priority: high | medium | low
  priority            text not null default 'medium',

  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

drop trigger if exists trg_research_reports_updated_at on public.research_reports;
create trigger trg_research_reports_updated_at
  before update on public.research_reports
  for each row execute function public.set_updated_at();


-- =============================================================================
-- RESEARCH CUSTOMER SEGMENTS
-- Target customer archetypes identified during market research.
-- =============================================================================
create table if not exists public.research_customer_segments (
  id                uuid primary key default gen_random_uuid(),
  business_id       uuid references public.businesses(id) on delete cascade not null,
  user_id           uuid references auth.users(id) on delete cascade not null,

  name              text not null,
  description       text,

  -- 0–10 scored attributes
  pain_level        integer check (pain_level >= 0 and pain_level <= 10),
  ability_to_pay    integer check (ability_to_pay >= 0 and ability_to_pay <= 10),
  reachability      integer check (reachability >= 0 and reachability <= 10),

  market_size_guess text,

  -- Stored as jsonb arrays for Postgres compatibility (text[])
  channels          jsonb default '[]'::jsonb,

  evidence_summary  text,
  confidence        text,
  priority          text not null default 'medium',

  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

drop trigger if exists trg_research_customer_segments_updated_at on public.research_customer_segments;
create trigger trg_research_customer_segments_updated_at
  before update on public.research_customer_segments
  for each row execute function public.set_updated_at();


-- =============================================================================
-- RESEARCH BUYER BUDGETS
-- Budget and willingness-to-pay analysis per buyer archetype.
-- =============================================================================
create table if not exists public.research_buyer_budgets (
  id                  uuid primary key default gen_random_uuid(),
  business_id         uuid references public.businesses(id) on delete cascade not null,
  user_id             uuid references auth.users(id) on delete cascade not null,

  buyer               text not null,
  budget_owner        text,
  existing_spend      text,
  willingness_to_pay  text,
  value_driver        text,
  pricing_signal      text,
  confidence          text,
  priority            text not null default 'medium',

  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

drop trigger if exists trg_research_buyer_budgets_updated_at on public.research_buyer_budgets;
create trigger trg_research_buyer_budgets_updated_at
  before update on public.research_buyer_budgets
  for each row execute function public.set_updated_at();


-- =============================================================================
-- RESEARCH COMPETITORS
-- Competitive landscape mapping.
-- =============================================================================
create table if not exists public.research_competitors (
  id                uuid primary key default gen_random_uuid(),
  business_id       uuid references public.businesses(id) on delete cascade not null,
  user_id           uuid references auth.users(id) on delete cascade not null,

  name              text not null,
  url               text,

  -- Category: direct | indirect | substitute | emerging
  category          text,

  positioning       text,
  pricing_summary   text,

  -- Stored as jsonb arrays (text[])
  strengths         jsonb default '[]'::jsonb,
  weaknesses        jsonb default '[]'::jsonb,

  wedge_opportunity text,
  confidence        text,
  priority          text not null default 'medium',

  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

drop trigger if exists trg_research_competitors_updated_at on public.research_competitors;
create trigger trg_research_competitors_updated_at
  before update on public.research_competitors
  for each row execute function public.set_updated_at();


-- =============================================================================
-- RESEARCH MONETIZATION MODELS
-- Revenue model assumptions for the business.
-- =============================================================================
create table if not exists public.research_monetization_models (
  id               uuid primary key default gen_random_uuid(),
  business_id      uuid references public.businesses(id) on delete cascade not null,
  user_id          uuid references auth.users(id) on delete cascade not null,

  model            text not null,
  buyer            text,
  price_assumption text,
  value_metric     text,
  reasoning        text,
  confidence       text,
  priority         text not null default 'medium',

  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

drop trigger if exists trg_research_monetization_models_updated_at on public.research_monetization_models;
create trigger trg_research_monetization_models_updated_at
  before update on public.research_monetization_models
  for each row execute function public.set_updated_at();


-- =============================================================================
-- RESEARCH DISTRIBUTION CHANNELS
-- Acquisition and distribution channel analysis.
-- =============================================================================
create table if not exists public.research_distribution_channels (
  id               uuid primary key default gen_random_uuid(),
  business_id      uuid references public.businesses(id) on delete cascade not null,
  user_id          uuid references auth.users(id) on delete cascade not null,

  channel          text not null,
  description      text,

  -- 0–10 scored attributes
  speed_score      integer check (speed_score >= 0 and speed_score <= 10),
  cost_score       integer check (cost_score >= 0 and cost_score <= 10),
  difficulty_score integer check (difficulty_score >= 0 and difficulty_score <= 10),

  reasoning        text,
  confidence       text,
  priority         text not null default 'medium',

  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

drop trigger if exists trg_research_distribution_channels_updated_at on public.research_distribution_channels;
create trigger trg_research_distribution_channels_updated_at
  before update on public.research_distribution_channels
  for each row execute function public.set_updated_at();


-- =============================================================================
-- RESEARCH RISKS
-- Risks that could undermine the opportunity.
-- =============================================================================
create table if not exists public.research_risks (
  id           uuid primary key default gen_random_uuid(),
  business_id  uuid references public.businesses(id) on delete cascade not null,
  user_id      uuid references auth.users(id) on delete cascade not null,

  title        text not null,
  description  text,

  -- Severity: critical | high | medium | low
  severity     text,
  mitigation   text,
  confidence   text,
  priority     text not null default 'medium',

  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

drop trigger if exists trg_research_risks_updated_at on public.research_risks;
create trigger trg_research_risks_updated_at
  before update on public.research_risks
  for each row execute function public.set_updated_at();


-- =============================================================================
-- RESEARCH HYPOTHESES
-- Testable beliefs that should be validated before building.
-- (Distinct from Customer Validation hypotheses — these are research-phase.)
-- =============================================================================
create table if not exists public.research_hypotheses (
  id               uuid primary key default gen_random_uuid(),
  business_id      uuid references public.businesses(id) on delete cascade not null,
  user_id          uuid references auth.users(id) on delete cascade not null,

  title            text not null,
  description      text,
  test_method      text,
  success_criteria text,
  confidence       text,
  priority         text not null default 'medium',

  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

drop trigger if exists trg_research_hypotheses_updated_at on public.research_hypotheses;
create trigger trg_research_hypotheses_updated_at
  before update on public.research_hypotheses
  for each row execute function public.set_updated_at();


-- =============================================================================
-- RESEARCH EVIDENCE
-- Evidence items supporting research findings and hypotheses.
-- =============================================================================
create table if not exists public.research_evidence (
  id            uuid primary key default gen_random_uuid(),
  business_id   uuid references public.businesses(id) on delete cascade not null,
  user_id       uuid references auth.users(id) on delete cascade not null,

  claim         text not null,
  source        text,
  source_url    text,

  -- Type: data_point | quote | case_study | trend | competitor_signal | customer_signal | market_report
  evidence_type text,

  confidence    text,
  notes         text,

  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

drop trigger if exists trg_research_evidence_updated_at on public.research_evidence;
create trigger trg_research_evidence_updated_at
  before update on public.research_evidence
  for each row execute function public.set_updated_at();


-- =============================================================================
-- INDEXES
-- =============================================================================

-- research_reports
create index if not exists idx_research_reports_business_id
  on public.research_reports(business_id);
create index if not exists idx_research_reports_user_id
  on public.research_reports(user_id);
create index if not exists idx_research_reports_status
  on public.research_reports(status);
create index if not exists idx_research_reports_created_at
  on public.research_reports(created_at desc);

-- research_customer_segments
create index if not exists idx_research_customer_segments_business_id
  on public.research_customer_segments(business_id);
create index if not exists idx_research_customer_segments_user_id
  on public.research_customer_segments(user_id);
create index if not exists idx_research_customer_segments_priority
  on public.research_customer_segments(priority);
create index if not exists idx_research_customer_segments_created_at
  on public.research_customer_segments(created_at desc);

-- research_buyer_budgets
create index if not exists idx_research_buyer_budgets_business_id
  on public.research_buyer_budgets(business_id);
create index if not exists idx_research_buyer_budgets_user_id
  on public.research_buyer_budgets(user_id);
create index if not exists idx_research_buyer_budgets_priority
  on public.research_buyer_budgets(priority);
create index if not exists idx_research_buyer_budgets_created_at
  on public.research_buyer_budgets(created_at desc);

-- research_competitors
create index if not exists idx_research_competitors_business_id
  on public.research_competitors(business_id);
create index if not exists idx_research_competitors_user_id
  on public.research_competitors(user_id);
create index if not exists idx_research_competitors_priority
  on public.research_competitors(priority);
create index if not exists idx_research_competitors_created_at
  on public.research_competitors(created_at desc);

-- research_monetization_models
create index if not exists idx_research_monetization_models_business_id
  on public.research_monetization_models(business_id);
create index if not exists idx_research_monetization_models_user_id
  on public.research_monetization_models(user_id);
create index if not exists idx_research_monetization_models_priority
  on public.research_monetization_models(priority);
create index if not exists idx_research_monetization_models_created_at
  on public.research_monetization_models(created_at desc);

-- research_distribution_channels
create index if not exists idx_research_distribution_channels_business_id
  on public.research_distribution_channels(business_id);
create index if not exists idx_research_distribution_channels_user_id
  on public.research_distribution_channels(user_id);
create index if not exists idx_research_distribution_channels_priority
  on public.research_distribution_channels(priority);
create index if not exists idx_research_distribution_channels_created_at
  on public.research_distribution_channels(created_at desc);

-- research_risks
create index if not exists idx_research_risks_business_id
  on public.research_risks(business_id);
create index if not exists idx_research_risks_user_id
  on public.research_risks(user_id);
create index if not exists idx_research_risks_severity
  on public.research_risks(severity);
create index if not exists idx_research_risks_priority
  on public.research_risks(priority);
create index if not exists idx_research_risks_created_at
  on public.research_risks(created_at desc);

-- research_hypotheses
create index if not exists idx_research_hypotheses_business_id
  on public.research_hypotheses(business_id);
create index if not exists idx_research_hypotheses_user_id
  on public.research_hypotheses(user_id);
create index if not exists idx_research_hypotheses_confidence
  on public.research_hypotheses(confidence);
create index if not exists idx_research_hypotheses_priority
  on public.research_hypotheses(priority);
create index if not exists idx_research_hypotheses_created_at
  on public.research_hypotheses(created_at desc);

-- research_evidence
create index if not exists idx_research_evidence_business_id
  on public.research_evidence(business_id);
create index if not exists idx_research_evidence_user_id
  on public.research_evidence(user_id);
create index if not exists idx_research_evidence_evidence_type
  on public.research_evidence(evidence_type);
create index if not exists idx_research_evidence_confidence
  on public.research_evidence(confidence);
create index if not exists idx_research_evidence_created_at
  on public.research_evidence(created_at desc);


-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- Users can only read/write rows attached to businesses they own.
-- Policy pattern mirrors supabase/schema.sql and supabase/validation.sql.
-- =============================================================================
alter table public.research_reports               enable row level security;
alter table public.research_customer_segments     enable row level security;
alter table public.research_buyer_budgets         enable row level security;
alter table public.research_competitors           enable row level security;
alter table public.research_monetization_models   enable row level security;
alter table public.research_distribution_channels enable row level security;
alter table public.research_risks                 enable row level security;
alter table public.research_hypotheses            enable row level security;
alter table public.research_evidence              enable row level security;

-- research_reports
create policy "research_reports: select own"
  on public.research_reports for select
  using (auth.uid() = user_id);

create policy "research_reports: insert own"
  on public.research_reports for insert
  with check (auth.uid() = user_id);

create policy "research_reports: update own"
  on public.research_reports for update
  using (auth.uid() = user_id);

create policy "research_reports: delete own"
  on public.research_reports for delete
  using (auth.uid() = user_id);

-- research_customer_segments
create policy "research_customer_segments: select own"
  on public.research_customer_segments for select
  using (auth.uid() = user_id);

create policy "research_customer_segments: insert own"
  on public.research_customer_segments for insert
  with check (auth.uid() = user_id);

create policy "research_customer_segments: update own"
  on public.research_customer_segments for update
  using (auth.uid() = user_id);

create policy "research_customer_segments: delete own"
  on public.research_customer_segments for delete
  using (auth.uid() = user_id);

-- research_buyer_budgets
create policy "research_buyer_budgets: select own"
  on public.research_buyer_budgets for select
  using (auth.uid() = user_id);

create policy "research_buyer_budgets: insert own"
  on public.research_buyer_budgets for insert
  with check (auth.uid() = user_id);

create policy "research_buyer_budgets: update own"
  on public.research_buyer_budgets for update
  using (auth.uid() = user_id);

create policy "research_buyer_budgets: delete own"
  on public.research_buyer_budgets for delete
  using (auth.uid() = user_id);

-- research_competitors
create policy "research_competitors: select own"
  on public.research_competitors for select
  using (auth.uid() = user_id);

create policy "research_competitors: insert own"
  on public.research_competitors for insert
  with check (auth.uid() = user_id);

create policy "research_competitors: update own"
  on public.research_competitors for update
  using (auth.uid() = user_id);

create policy "research_competitors: delete own"
  on public.research_competitors for delete
  using (auth.uid() = user_id);

-- research_monetization_models
create policy "research_monetization_models: select own"
  on public.research_monetization_models for select
  using (auth.uid() = user_id);

create policy "research_monetization_models: insert own"
  on public.research_monetization_models for insert
  with check (auth.uid() = user_id);

create policy "research_monetization_models: update own"
  on public.research_monetization_models for update
  using (auth.uid() = user_id);

create policy "research_monetization_models: delete own"
  on public.research_monetization_models for delete
  using (auth.uid() = user_id);

-- research_distribution_channels
create policy "research_distribution_channels: select own"
  on public.research_distribution_channels for select
  using (auth.uid() = user_id);

create policy "research_distribution_channels: insert own"
  on public.research_distribution_channels for insert
  with check (auth.uid() = user_id);

create policy "research_distribution_channels: update own"
  on public.research_distribution_channels for update
  using (auth.uid() = user_id);

create policy "research_distribution_channels: delete own"
  on public.research_distribution_channels for delete
  using (auth.uid() = user_id);

-- research_risks
create policy "research_risks: select own"
  on public.research_risks for select
  using (auth.uid() = user_id);

create policy "research_risks: insert own"
  on public.research_risks for insert
  with check (auth.uid() = user_id);

create policy "research_risks: update own"
  on public.research_risks for update
  using (auth.uid() = user_id);

create policy "research_risks: delete own"
  on public.research_risks for delete
  using (auth.uid() = user_id);

-- research_hypotheses
create policy "research_hypotheses: select own"
  on public.research_hypotheses for select
  using (auth.uid() = user_id);

create policy "research_hypotheses: insert own"
  on public.research_hypotheses for insert
  with check (auth.uid() = user_id);

create policy "research_hypotheses: update own"
  on public.research_hypotheses for update
  using (auth.uid() = user_id);

create policy "research_hypotheses: delete own"
  on public.research_hypotheses for delete
  using (auth.uid() = user_id);

-- research_evidence
create policy "research_evidence: select own"
  on public.research_evidence for select
  using (auth.uid() = user_id);

create policy "research_evidence: insert own"
  on public.research_evidence for insert
  with check (auth.uid() = user_id);

create policy "research_evidence: update own"
  on public.research_evidence for update
  using (auth.uid() = user_id);

create policy "research_evidence: delete own"
  on public.research_evidence for delete
  using (auth.uid() = user_id);
