-- =============================================================================
-- bucks.ai — Customer Validation Node Schema
-- =============================================================================
-- IMPORTANT: Satvik must run this file in the Supabase SQL Editor after
-- merging feature/customer-validation-backend into main.
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
-- Shared trigger function — auto-stamps updated_at on every update.
-- =============================================================================
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;


-- =============================================================================
-- VALIDATION PERSONAS
-- Target customer archetypes that future Persona Agents will enrich.
-- =============================================================================
create table if not exists public.validation_personas (
  id                uuid primary key default gen_random_uuid(),
  business_id       uuid references public.businesses(id) on delete cascade not null,
  user_id           uuid references auth.users(id) on delete cascade not null,

  -- Identity
  name              text not null,
  segment           text,
  description       text,

  -- Discovery fields (stored as jsonb arrays for Postgres compatibility)
  pain_points       jsonb default '[]'::jsonb,   -- text[]
  desired_outcomes  jsonb default '[]'::jsonb,   -- text[]
  channels          jsonb default '[]'::jsonb,   -- text[]

  -- Buying signal
  willingness_to_pay text,

  -- Priority: high | medium | low
  priority          text not null default 'medium',

  -- Status: active | archived
  status            text not null default 'active',

  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

drop trigger if exists trg_validation_personas_updated_at on public.validation_personas;
create trigger trg_validation_personas_updated_at
  before update on public.validation_personas
  for each row execute function public.set_updated_at();


-- =============================================================================
-- VALIDATION HYPOTHESES
-- Testable beliefs that future Hypothesis Agents will track.
-- =============================================================================
create table if not exists public.validation_hypotheses (
  id               uuid primary key default gen_random_uuid(),
  business_id      uuid references public.businesses(id) on delete cascade not null,
  user_id          uuid references auth.users(id) on delete cascade not null,

  -- What we're testing
  title            text not null,
  description      text,

  -- Type: customer | market | product | revenue | other
  type             text,

  assumption       text,
  success_criteria text,

  -- Status: untested | testing | supported | rejected | inconclusive
  status           text not null default 'untested',

  -- 0–100 confidence score; updated by Validation Score Agent in future
  confidence       integer check (confidence >= 0 and confidence <= 100),

  -- Priority: high | medium | low
  priority         text not null default 'medium',

  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

drop trigger if exists trg_validation_hypotheses_updated_at on public.validation_hypotheses;
create trigger trg_validation_hypotheses_updated_at
  before update on public.validation_hypotheses
  for each row execute function public.set_updated_at();


-- =============================================================================
-- VALIDATION LEADS
-- Potential interview contacts that future Lead Research Agents will enrich.
-- =============================================================================
create table if not exists public.validation_leads (
  id           uuid primary key default gen_random_uuid(),
  business_id  uuid references public.businesses(id) on delete cascade not null,
  user_id      uuid references auth.users(id) on delete cascade not null,

  -- Contact identity
  name         text not null,
  company      text,
  role         text,
  segment      text,

  -- Source: manual | blueprint | linkedin | twitter | email | referral | other
  source       text not null default 'manual',

  -- Reachability
  contact_url  text,
  email        text,

  -- Status: identified | contacted | replied | scheduled | interviewed | not_interested
  status       text not null default 'identified',

  notes        text,

  -- Priority: high | medium | low
  priority     text not null default 'medium',

  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

drop trigger if exists trg_validation_leads_updated_at on public.validation_leads;
create trigger trg_validation_leads_updated_at
  before update on public.validation_leads
  for each row execute function public.set_updated_at();


-- =============================================================================
-- VALIDATION FEEDBACK NOTES
-- Structured notes from customer conversations.
-- Future Feedback Analysis Agent will summarize and score these.
-- =============================================================================
create table if not exists public.validation_feedback_notes (
  id                        uuid primary key default gen_random_uuid(),
  business_id               uuid references public.businesses(id) on delete cascade not null,
  user_id                   uuid references auth.users(id) on delete cascade not null,

  -- Optional links to related entities
  lead_id                   uuid references public.validation_leads(id) on delete set null,
  hypothesis_id             uuid references public.validation_hypotheses(id) on delete set null,

  -- Core content
  summary                   text not null,

  -- Structured signals
  pain_signal               text,
  willingness_to_pay_signal text,

  -- Arrays (stored as jsonb)
  objections                jsonb default '[]'::jsonb,   -- text[]
  quotes                    jsonb default '[]'::jsonb,   -- text[]

  next_step                 text,

  -- Signal strength: weak | medium | strong
  signal_strength           text,

  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);

drop trigger if exists trg_validation_feedback_notes_updated_at on public.validation_feedback_notes;
create trigger trg_validation_feedback_notes_updated_at
  before update on public.validation_feedback_notes
  for each row execute function public.set_updated_at();


-- =============================================================================
-- INDEXES
-- =============================================================================

-- validation_personas
create index if not exists idx_validation_personas_business_id
  on public.validation_personas(business_id);
create index if not exists idx_validation_personas_user_id
  on public.validation_personas(user_id);
create index if not exists idx_validation_personas_priority
  on public.validation_personas(priority);
create index if not exists idx_validation_personas_status
  on public.validation_personas(status);
create index if not exists idx_validation_personas_created_at
  on public.validation_personas(created_at desc);

-- validation_hypotheses
create index if not exists idx_validation_hypotheses_business_id
  on public.validation_hypotheses(business_id);
create index if not exists idx_validation_hypotheses_user_id
  on public.validation_hypotheses(user_id);
create index if not exists idx_validation_hypotheses_status
  on public.validation_hypotheses(status);
create index if not exists idx_validation_hypotheses_priority
  on public.validation_hypotheses(priority);
create index if not exists idx_validation_hypotheses_created_at
  on public.validation_hypotheses(created_at desc);

-- validation_leads
create index if not exists idx_validation_leads_business_id
  on public.validation_leads(business_id);
create index if not exists idx_validation_leads_user_id
  on public.validation_leads(user_id);
create index if not exists idx_validation_leads_status
  on public.validation_leads(status);
create index if not exists idx_validation_leads_priority
  on public.validation_leads(priority);
create index if not exists idx_validation_leads_created_at
  on public.validation_leads(created_at desc);

-- validation_feedback_notes
create index if not exists idx_validation_feedback_notes_business_id
  on public.validation_feedback_notes(business_id);
create index if not exists idx_validation_feedback_notes_user_id
  on public.validation_feedback_notes(user_id);
create index if not exists idx_validation_feedback_notes_lead_id
  on public.validation_feedback_notes(lead_id);
create index if not exists idx_validation_feedback_notes_hypothesis_id
  on public.validation_feedback_notes(hypothesis_id);
create index if not exists idx_validation_feedback_notes_signal_strength
  on public.validation_feedback_notes(signal_strength);
create index if not exists idx_validation_feedback_notes_created_at
  on public.validation_feedback_notes(created_at desc);


-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- Users can only read/write rows attached to businesses they own.
-- Policy pattern mirrors supabase/schema.sql.
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
