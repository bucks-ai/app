-- =============================================================================
-- bucks.ai — Supabase Database Schema
-- =============================================================================
-- How to apply this:
--   1. Go to your Supabase project → SQL Editor
--   2. Paste this entire file and click Run
--   3. Or use the Supabase CLI: supabase db push
-- =============================================================================


-- =============================================================================
-- PROFILES
-- One profile per authenticated user. Auto-created on signup via trigger below.
-- =============================================================================
create table if not exists public.profiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  email       text,
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

-- =============================================================================
-- BUSINESSES
-- Each row is one business idea a founder has submitted through /intake.
-- =============================================================================
create table if not exists public.businesses (
  id                   uuid primary key default gen_random_uuid(),
  user_id              uuid references auth.users(id) on delete cascade not null,

  -- Core idea fields (from /intake wizard)
  idea_name            text not null,
  one_line_idea        text,
  idea_description     text,
  target_customer      text,
  business_type        text,
  primary_goal         text,
  success_metric       text,

  -- Operational parameters
  budget               text,
  timeline             text,

  -- Autonomy / permissions config
  autonomy_preference  text,
  spending_limit       text,
  hard_constraints     text,
  human_only_actions   text,
  forbidden_actions    text,
  preferred_tools      text,

  -- Lifecycle status: blueprint_created | active | paused | completed
  status               text default 'blueprint_created',

  created_at           timestamptz default now(),
  updated_at           timestamptz default now()
);

-- =============================================================================
-- BUSINESS BLUEPRINTS
-- Each blueprint is a JSON document produced by /api/generate-blueprint.
-- A business can have multiple blueprints (e.g. re-generated after pivots).
-- =============================================================================
create table if not exists public.business_blueprints (
  id           uuid primary key default gen_random_uuid(),
  business_id  uuid references public.businesses(id) on delete cascade not null,
  user_id      uuid references auth.users(id) on delete cascade not null,
  blueprint    jsonb not null,
  created_at   timestamptz default now()
);

-- =============================================================================
-- HUMAN REQUIRED ACTIONS
-- Actions the AI cannot take autonomously — requires founder approval.
-- Examples: sign contracts, authorize payments, confirm legal decisions.
-- =============================================================================
create table if not exists public.human_required_actions (
  id           uuid primary key default gen_random_uuid(),
  business_id  uuid references public.businesses(id) on delete cascade not null,
  user_id      uuid references auth.users(id) on delete cascade not null,
  title        text not null,
  description  text,

  -- Status: pending | approved | rejected | completed
  status       text default 'pending',

  -- Risk level: low | medium | high | critical
  risk_level   text default 'medium',

  created_at   timestamptz default now(),
  updated_at   timestamptz default now()
);

-- =============================================================================
-- AGENT ACTIVITY LOGS
-- Audit trail of everything the AI agent does for each business.
-- =============================================================================
create table if not exists public.agent_activity_logs (
  id             uuid primary key default gen_random_uuid(),
  business_id    uuid references public.businesses(id) on delete cascade not null,
  user_id        uuid references auth.users(id) on delete cascade not null,
  activity_type  text not null,  -- e.g. 'blueprint_generated', 'tool_connected', 'email_sent'
  message        text not null,
  metadata       jsonb default '{}'::jsonb,
  created_at     timestamptz default now()
);

-- =============================================================================
-- TOOL PERMISSIONS
-- Tracks which external tools (GitHub, Stripe, etc.) are connected per business.
-- Mirrors the tool registry in src/tool-registry.ts.
-- =============================================================================
create table if not exists public.tool_permissions (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references auth.users(id) on delete cascade not null,
  business_id   uuid references public.businesses(id) on delete cascade,

  tool_id       text not null,   -- matches ToolId in tool-registry.ts
  tool_name     text not null,

  -- Connection state: not_connected | connected | error
  status        text default 'not_connected',

  -- Setup state: not_connected | in_progress | connected | error
  setup_status  text default 'not_connected',

  -- Risk level from tool registry: low | medium | high | critical
  risk_level    text default 'medium',

  -- Array of permission strings granted by the user
  permissions   jsonb default '[]'::jsonb,

  created_at    timestamptz default now(),
  updated_at    timestamptz default now()
);


-- =============================================================================
-- INDEXES — speeds up the most common query patterns
-- =============================================================================
create index if not exists idx_businesses_user_id
  on public.businesses(user_id);

create index if not exists idx_business_blueprints_business_id
  on public.business_blueprints(business_id);

create index if not exists idx_business_blueprints_user_id
  on public.business_blueprints(user_id);

create index if not exists idx_human_required_actions_business_id
  on public.human_required_actions(business_id);

create index if not exists idx_agent_activity_logs_business_id
  on public.agent_activity_logs(business_id);

create index if not exists idx_tool_permissions_user_id
  on public.tool_permissions(user_id);

create index if not exists idx_tool_permissions_business_id
  on public.tool_permissions(business_id);


-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- Users can only read/write their own rows.
-- =============================================================================
alter table public.profiles              enable row level security;
alter table public.businesses            enable row level security;
alter table public.business_blueprints  enable row level security;
alter table public.human_required_actions enable row level security;
alter table public.agent_activity_logs  enable row level security;
alter table public.tool_permissions     enable row level security;

-- profiles: each user sees and edits only their own profile
create policy "profiles: select own"
  on public.profiles for select
  using (auth.uid() = id);

create policy "profiles: update own"
  on public.profiles for update
  using (auth.uid() = id);

-- businesses
create policy "businesses: select own"
  on public.businesses for select
  using (auth.uid() = user_id);

create policy "businesses: insert own"
  on public.businesses for insert
  with check (auth.uid() = user_id);

create policy "businesses: update own"
  on public.businesses for update
  using (auth.uid() = user_id);

create policy "businesses: delete own"
  on public.businesses for delete
  using (auth.uid() = user_id);

-- business_blueprints
create policy "blueprints: select own"
  on public.business_blueprints for select
  using (auth.uid() = user_id);

create policy "blueprints: insert own"
  on public.business_blueprints for insert
  with check (auth.uid() = user_id);

create policy "blueprints: update own"
  on public.business_blueprints for update
  using (auth.uid() = user_id);

create policy "blueprints: delete own"
  on public.business_blueprints for delete
  using (auth.uid() = user_id);

-- human_required_actions
create policy "human_actions: select own"
  on public.human_required_actions for select
  using (auth.uid() = user_id);

create policy "human_actions: insert own"
  on public.human_required_actions for insert
  with check (auth.uid() = user_id);

create policy "human_actions: update own"
  on public.human_required_actions for update
  using (auth.uid() = user_id);

create policy "human_actions: delete own"
  on public.human_required_actions for delete
  using (auth.uid() = user_id);

-- agent_activity_logs
create policy "activity_logs: select own"
  on public.agent_activity_logs for select
  using (auth.uid() = user_id);

create policy "activity_logs: insert own"
  on public.agent_activity_logs for insert
  with check (auth.uid() = user_id);

create policy "activity_logs: update own"
  on public.agent_activity_logs for update
  using (auth.uid() = user_id);

create policy "activity_logs: delete own"
  on public.agent_activity_logs for delete
  using (auth.uid() = user_id);

-- tool_permissions
create policy "tool_permissions: select own"
  on public.tool_permissions for select
  using (auth.uid() = user_id);

create policy "tool_permissions: insert own"
  on public.tool_permissions for insert
  with check (auth.uid() = user_id);

create policy "tool_permissions: update own"
  on public.tool_permissions for update
  using (auth.uid() = user_id);

create policy "tool_permissions: delete own"
  on public.tool_permissions for delete
  using (auth.uid() = user_id);


-- =============================================================================
-- TRIGGER: auto-create profile when a new user signs up
-- =============================================================================
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;

-- Drop the trigger first so this script is idempotent (safe to re-run)
drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();
