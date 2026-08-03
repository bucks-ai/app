-- =============================================================================
-- bucks.ai — M1 mission_tasks.description column
-- =============================================================================
-- IMPORTANT: Arnav must run this file in the Supabase SQL Editor.
-- This file is intentionally NOT applied automatically.
--
-- How to apply:
--   1. Go to Supabase project → SQL Editor
--   2. Paste this entire file and click Run
--
-- Prerequisites:
--   supabase/missions.sql must already be applied (creates public.mission_tasks).
--
-- Why: instructions placed in a mission task's description were never reaching
-- the worker prompt — the runner task dict carried the field, but the DB row
-- backing seeded mission tasks had nowhere to store it. This adds a nullable
-- TEXT column so a description written on a mission_tasks row survives the
-- seed_tasks_from_mission() conversion and reaches generate_worker_prompt().
--
-- This migration is additive and idempotent:
--   - ADD COLUMN IF NOT EXISTS is a no-op if the column already exists.
--   - Nullable, no default — existing rows are unaffected.
-- =============================================================================

ALTER TABLE public.mission_tasks
  ADD COLUMN IF NOT EXISTS description TEXT;
