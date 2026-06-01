-- =============================================================================
-- bucks.ai — Agent Runs Schema (Agent Runs v1)
-- =============================================================================
-- IMPORTANT: Arnav must run this file in the Supabase SQL Editor after
-- merging feature/agent-runs-v1 into main.
-- This file is intentionally NOT applied automatically.
--
-- How to apply:
--   1. Go to Supabase project → SQL Editor
--   2. Paste this entire file and click Run
--
-- Prerequisites:
--   supabase/schema.sql must have been applied first (businesses table must exist).
--   supabase/validation.sql should have been applied (provides set_updated_at trigger).
--   If validation.sql was not applied, uncomment the set_updated_at block below.
--
-- This schema is additive (CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS)
-- and safe to run on a live project. Re-running is idempotent for tables and
-- indexes, but not for policies — drop existing policies first if re-running.
-- =============================================================================


-- =============================================================================
-- UPDATED_AT TRIGGER
-- Reuses the shared set_updated_at() trigger created in validation.sql.
-- If validation.sql has NOT been applied, uncomment the block below:
-- =============================================================================
-- CREATE OR REPLACE FUNCTION public.set_updated_at()
-- RETURNS TRIGGER
-- LANGUAGE plpgsql
-- AS $$
-- BEGIN
--   NEW.updated_at = NOW();
--   RETURN NEW;
-- END;
-- $$;


-- =============================================================================
-- AGENT RUNS
-- Durable history of work performed (or inferred) by a bucks.ai agent.
-- One row per unit of work. May be created in real-time or back-filled from
-- agent_activity_logs.
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.agent_runs (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id              UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
  user_id                  UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Which agent performed this work (matches AgentTemplateId in types/agents.ts)
  agent_id                 TEXT NOT NULL,

  -- Which node this agent belongs to (matches AgentNodeId in types/agents.ts)
  node_id                  TEXT NOT NULL,

  -- Human-readable label for this run
  title                    TEXT NOT NULL,

  -- Optional human/AI-generated summary of what happened
  summary                  TEXT,

  -- Run lifecycle:
  --   queued | running | completed | failed | blocked | skipped | waiting_for_approval
  status                   TEXT NOT NULL DEFAULT 'completed',

  -- How this run record was created:
  --   system_inferred | user_triggered | activity_log_backfill | workflow | manual_note
  source                   TEXT NOT NULL DEFAULT 'system_inferred',

  -- What event caused this run (optional)
  trigger                  TEXT,

  -- Input data passed to the agent (structured, optional)
  input                    JSONB NOT NULL DEFAULT '{}'::JSONB,

  -- Output produced by the agent (structured, optional)
  output                   JSONB NOT NULL DEFAULT '{}'::JSONB,

  -- Artifacts produced: URLs, repos, etc.
  -- Each item: { type, label, url?, metadata? }
  artifacts                JSONB NOT NULL DEFAULT '[]'::JSONB,

  -- Error information if status = 'failed'
  -- Shape: { code, message, detail?, retriable? }
  error                    JSONB,

  -- UUIDs of agent_activity_logs rows that this run was derived from or relates to
  related_activity_log_ids UUID[] NOT NULL DEFAULT '{}',

  -- Timestamps
  started_at               TIMESTAMPTZ,
  completed_at             TIMESTAMPTZ,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_agent_runs_updated_at ON public.agent_runs;
CREATE TRIGGER trg_agent_runs_updated_at
  BEFORE UPDATE ON public.agent_runs
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_agent_runs_business_id
  ON public.agent_runs(business_id);

CREATE INDEX IF NOT EXISTS idx_agent_runs_user_id
  ON public.agent_runs(user_id);

CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_id
  ON public.agent_runs(agent_id);

CREATE INDEX IF NOT EXISTS idx_agent_runs_node_id
  ON public.agent_runs(node_id);

CREATE INDEX IF NOT EXISTS idx_agent_runs_status
  ON public.agent_runs(status);

CREATE INDEX IF NOT EXISTS idx_agent_runs_source
  ON public.agent_runs(source);

CREATE INDEX IF NOT EXISTS idx_agent_runs_created_at
  ON public.agent_runs(created_at DESC);


-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- Users can only access agent_runs for businesses they own.
-- Pattern mirrors supabase/schema.sql and supabase/validation.sql.
-- =============================================================================
ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "agent_runs: select own"
  ON public.agent_runs FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "agent_runs: insert own"
  ON public.agent_runs FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "agent_runs: update own"
  ON public.agent_runs FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "agent_runs: delete own"
  ON public.agent_runs FOR DELETE
  USING (auth.uid() = user_id);
