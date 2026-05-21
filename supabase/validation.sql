-- =============================================================================
-- bucks.ai — Customer Validation Schema
-- =============================================================================
-- IMPORTANT: Satvik must run this file in the Supabase SQL Editor after
-- merging feature/customer-validation-backend into main. This file is
-- intentionally NOT applied automatically.
--
-- How to apply:
--   1. Go to Supabase project → SQL Editor
--   2. Paste this entire file and click Run
--
-- This schema is additive and safe to run on a live project.
-- =============================================================================


-- =============================================================================
-- VALIDATION PERSONAS
-- Target customer archetypes to interview and validate against.
-- =============================================================================
create table if not exists public.validation_personas (
  id           uuid primary key default gen_random_uuid(),
  business_id  uuid references public.businesses(id) on delete cascade not null,
  user_id      uuid references auth.users(id) on delete cascade not null,

  name         text not null,
  role         text,
  company_type text,

  -- JSON arrays of strings
  pain_points  jsonb default '[]'::jsonb,
  goals        jsonb default '[]'::jsonb,

  notes        text,

  -- Priority: high | medium | low
  priority     text default 'medium',

  created_at   timestamptz default now(),
  updated_at   timestamptz default now()
);

-- =============================================================================
-- VALIDATION HYPOTHESES
-- Testable beliefs about the market, customer, or product.
-- =============================================================================
create table if not exists public.validation_hypotheses (
  id           uuid primary key default gen_random_uuid(),
  business_id  uuid references public.businesses(id) on delete cascade not null,
  user_id      uuid references auth.users(id) on delete cascade not null,

  statement    text not null,
  rationale    text,

  -- Status: untested | testing | supported | rejected | inconclusive
  status       text default 'untested',

  -- Free-text field for recording supporting/disconfirming evidence
  evidence     text,

  created_at   timestamptz default now(),
  updated_at   timestamptz default now()
);

-- =============================================================================
-- VALIDATION LEADS
-- People or companies to contact for customer discovery interviews.
-- =============================================================================
create table if not exists public.validation_leads (
  id              uuid primary key default gen_random_uuid(),
  business_id     uuid references public.businesses(id) on delete cascade not null,
  user_id         uuid references auth.users(id) on delete cascade not null,

  name            text not null,
  company         text,
  role            text,
  contact_info    text,

  -- Source: manual | blueprint | linkedin | twitter | email | referral | other
  source          text default 'manual',

  -- Status: identified | contacted | replied | scheduled | interviewed | not_interested
  status          text default 'identified',

  -- Optional FK to the persona this lead represents
  persona_id      uuid references public.validation_personas(id) on delete set null,

  notes           text,
  outreach_script text,

  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);

-- =============================================================================
-- VALIDATION FEEDBACK NOTES
-- Raw notes captured from customer interviews or outreach replies.
-- =============================================================================
create table if not exists public.validation_feedback_notes (
  id              uuid primary key default gen_random_uuid(),
  business_id     uuid references public.businesses(id) on delete cascade not null,
  user_id         uuid references auth.users(id) on delete cascade not null,

  -- Optional FKs for linking feedback to specific entities
  lead_id         uuid references public.validation_leads(id) on delete set null,
  persona_id      uuid references public.validation_personas(id) on delete set null,
  hypothesis_id   uuid references public.validation_hypotheses(id) on delete set null,

  note            text not null,

  -- Sentiment: positive | negative | neutral
  sentiment       text,

  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);


-- =============================================================================
-- INDEXES — speeds up the most common query patterns
-- =============================================================================
create index if not exists idx_validation_personas_business_id
  on public.validation_personas(business_id);

create index if not exists idx_validation_personas_user_id
  on public.validation_personas(user_id);

create index if not exists idx_validation_personas_priority
  on public.validation_personas(priority);

create index if not exists idx_validation_hypotheses_business_id
  on public.validation_hypotheses(business_id);

create index if not exists idx_validation_hypotheses_user_id
  on public.validation_hypotheses(user_id);

create index if not exists idx_validation_hypotheses_status
  on public.validation_hypotheses(status);

create index if not exists idx_validation_leads_business_id
  on public.validation_leads(business_id);

create index if not exists idx_validation_leads_user_id
  on public.validation_leads(user_id);

create index if not exists idx_validation_leads_status
  on public.validation_leads(status);

create index if not exists idx_validation_feedback_notes_business_id
  on public.validation_feedback_notes(business_id);

create index if not exists idx_validation_feedback_notes_user_id
  on public.validation_feedback_notes(user_id);


-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- Users can only read/write their own rows.
-- =============================================================================
alter table public.validation_personas        enable row level security;
alter table public.validation_hypotheses      enable row level security;
alter table public.validation_leads           enable row level security;
alter table public.validation_feedback_notes  enable row level security;

-- validation_personas
create policy "validation_personas: select own"
  on public.validation_personas for select
  using (auth.uid() = user_id);

create policy "validation_personas: insert own"
  on public.validation_personas for insert
  with check (auth.uid() = user_id);

create policy "validation_personas: update own"
  on public.validation_personas for update
  using (auth.uid() = user_id);

create policy "validation_personas: delete own"
  on public.validation_personas for delete
  using (auth.uid() = user_id);

-- validation_hypotheses
create policy "validation_hypotheses: select own"
  on public.validation_hypotheses for select
  using (auth.uid() = user_id);

create policy "validation_hypotheses: insert own"
  on public.validation_hypotheses for insert
  with check (auth.uid() = user_id);

create policy "validation_hypotheses: update own"
  on public.validation_hypotheses for update
  using (auth.uid() = user_id);

create policy "validation_hypotheses: delete own"
  on public.validation_hypotheses for delete
  using (auth.uid() = user_id);

-- validation_leads
create policy "validation_leads: select own"
  on public.validation_leads for select
  using (auth.uid() = user_id);

create policy "validation_leads: insert own"
  on public.validation_leads for insert
  with check (auth.uid() = user_id);

create policy "validation_leads: update own"
  on public.validation_leads for update
  using (auth.uid() = user_id);

create policy "validation_leads: delete own"
  on public.validation_leads for delete
  using (auth.uid() = user_id);

-- validation_feedback_notes
create policy "validation_feedback_notes: select own"
  on public.validation_feedback_notes for select
  using (auth.uid() = user_id);

create policy "validation_feedback_notes: insert own"
  on public.validation_feedback_notes for insert
  with check (auth.uid() = user_id);

create policy "validation_feedback_notes: update own"
  on public.validation_feedback_notes for update
  using (auth.uid() = user_id);

create policy "validation_feedback_notes: delete own"
  on public.validation_feedback_notes for delete
  using (auth.uid() = user_id);
