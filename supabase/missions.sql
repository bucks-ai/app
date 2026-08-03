-- =============================================================================
-- bucks.ai — Mission Queue Schema
-- =============================================================================
-- IMPORTANT: Arnav must run this file in the Supabase SQL Editor after
-- merging feature/runner-mission-queue-schema into main.
-- This file is intentionally NOT applied automatically.
--
-- How to apply:
--   1. Go to Supabase project → SQL Editor
--   2. Paste this entire file and click Run
--
-- Prerequisites:
--   supabase/schema.sql must have been applied first (businesses table must exist).
--   supabase/validation.sql must have been applied (provides set_updated_at trigger).
--
-- This schema is additive (CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS)
-- and safe to run on a live project. Re-running is idempotent for tables and
-- indexes, but not for policies — drop existing policies first if re-running.
-- =============================================================================


-- =============================================================================
-- MISSIONS
-- One row per mission compiled from an inbox YAML file. A mission groups an
-- ordered set of runner tasks under a single strategic goal.
--
-- Lifecycle status:
--   queued    — all tasks waiting to start
--   running   — at least one task is currently running
--   completed — all tasks completed successfully
--   failed    — one or more tasks failed and exhausted retries
--   cancelled — mission was manually cancelled before completion
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.missions (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  business_id           UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
  user_id               UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Mission identity (mirrors the YAML mission file fields)
  name                  TEXT NOT NULL,
  goal                  TEXT,

  -- Lifecycle
  status                TEXT NOT NULL DEFAULT 'queued',

  -- Original YAML filename from inbox/ (e.g. "feature-auth.yml")
  source_file           TEXT,

  -- Total number of tasks compiled from the mission YAML
  task_count            INTEGER NOT NULL DEFAULT 0,

  -- Number of tasks in a terminal state (complete or failed)
  completed_task_count  INTEGER NOT NULL DEFAULT 0,

  -- Timestamps
  started_at            TIMESTAMPTZ,
  completed_at          TIMESTAMPTZ,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_missions_updated_at ON public.missions;
CREATE TRIGGER trg_missions_updated_at
  BEFORE UPDATE ON public.missions
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- =============================================================================
-- MISSION TASKS
-- One row per task compiled from a mission. Ordered by position (1-based).
-- Mirrors the task dict shape used by runner/langgraph/tools/task_tools.py.
--
-- Task status values match the runner's local queue:
--   queued | running | complete | failed | blocked
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.mission_tasks (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mission_id        UUID NOT NULL REFERENCES public.missions(id) ON DELETE CASCADE,
  business_id       UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
  user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Runner task identity — matches the id/title fields in tasks.local.json
  task_id           TEXT NOT NULL,
  title             TEXT NOT NULL,

  -- Task classification
  -- Valid types: backend | design | docs | frontend | general | infra | polish | test | ui
  type              TEXT NOT NULL DEFAULT 'general',

  -- Git branch this task will be executed on
  branch            TEXT NOT NULL,

  -- Preferred LLM worker: codex | claude | chatgpt (null = runner chooses)
  preferred_worker  TEXT,

  -- Execution order within the mission (1-based)
  position          INTEGER NOT NULL,

  -- Lifecycle (mirrors runner task status)
  status            TEXT NOT NULL DEFAULT 'queued',

  -- Output summary written by the worker on successful completion
  summary           TEXT,

  -- Error message if status = 'failed' or 'blocked'
  error             TEXT,

  -- Number of times this task has been retried after failure
  retry_count       INTEGER NOT NULL DEFAULT 0,

  -- Timestamps
  started_at        TIMESTAMPTZ,
  completed_at      TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_mission_tasks_updated_at ON public.mission_tasks;
CREATE TRIGGER trg_mission_tasks_updated_at
  BEFORE UPDATE ON public.mission_tasks
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- =============================================================================
-- INDEXES
-- =============================================================================

-- missions
CREATE INDEX IF NOT EXISTS idx_missions_business_id
  ON public.missions(business_id);

CREATE INDEX IF NOT EXISTS idx_missions_user_id
  ON public.missions(user_id);

CREATE INDEX IF NOT EXISTS idx_missions_status
  ON public.missions(status);

CREATE INDEX IF NOT EXISTS idx_missions_created_at
  ON public.missions(created_at DESC);

-- mission_tasks
CREATE INDEX IF NOT EXISTS idx_mission_tasks_mission_id
  ON public.mission_tasks(mission_id);

CREATE INDEX IF NOT EXISTS idx_mission_tasks_business_id
  ON public.mission_tasks(business_id);

CREATE INDEX IF NOT EXISTS idx_mission_tasks_user_id
  ON public.mission_tasks(user_id);

CREATE INDEX IF NOT EXISTS idx_mission_tasks_status
  ON public.mission_tasks(status);

CREATE INDEX IF NOT EXISTS idx_mission_tasks_task_id
  ON public.mission_tasks(task_id);

-- composite index for fetching a mission's tasks in order
CREATE INDEX IF NOT EXISTS idx_mission_tasks_mission_position
  ON public.mission_tasks(mission_id, position);


-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- Users can only access missions and mission_tasks for businesses they own.
-- Pattern mirrors supabase/agent-runs.sql.
-- =============================================================================
ALTER TABLE public.missions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "missions: select own"
  ON public.missions FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "missions: insert own"
  ON public.missions FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "missions: update own"
  ON public.missions FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "missions: delete own"
  ON public.missions FOR DELETE
  USING (auth.uid() = user_id);

ALTER TABLE public.mission_tasks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "mission_tasks: select own"
  ON public.mission_tasks FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "mission_tasks: insert own"
  ON public.mission_tasks FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "mission_tasks: update own"
  ON public.mission_tasks FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "mission_tasks: delete own"
  ON public.mission_tasks FOR DELETE
  USING (auth.uid() = user_id);
