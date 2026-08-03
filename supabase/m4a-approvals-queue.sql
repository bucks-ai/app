-- =============================================================================
-- bucks.ai — M4a: In-App Approval Queue (mirrors outbox/inbox)
-- =============================================================================
-- IMPORTANT: Arnav must run this file in the Supabase SQL Editor after
-- merging feature/m4a/inapp-approvals into main.
-- This file is intentionally NOT applied automatically.
--
-- How to apply:
--   1. Go to Supabase project → SQL Editor
--   2. Paste this entire file and click Run
--
-- Prerequisites:
--   supabase/schema.sql must have been applied first (auth.users must exist).
--   supabase/validation.sql must have been applied (provides set_updated_at trigger).
--
-- This schema is additive (CREATE TABLE IF NOT EXISTS, CREATE INDEX IF NOT EXISTS)
-- and safe to run on a live project. Re-running is idempotent for tables and
-- indexes, but not for policies — drop existing policies first if re-running.
-- =============================================================================


-- =============================================================================
-- APPROVALS
-- One row per pending/resolved runner approval gate (merge approval, SQL
-- approval, resource/credential request, strategic review — see
-- runner/langgraph/tools/slack_approvals.py for the exact request_type values
-- and the inbox/ fulfillment-file convention each one maps to).
--
-- This table is not scoped to a business — the runner's file-based gates
-- belong to the operator building bucks.ai itself, not to any one founder's
-- business — so RLS here is owner-only (auth.uid() = user_id), with no
-- business_id ownership check to add (unlike supabase/m1-rls-fixes.sql's
-- business-scoped tables).
--
-- Rows are written by runner/langgraph/app_approvals_daemon.py using the
-- service role key (bypasses RLS), stamping user_id from the
-- RUNNER_OWNER_USER_ID env var. The app updates status/decided_by/decided_at
-- via an authenticated PATCH (src/app/api/approvals/[id]/route.ts), which RLS
-- restricts to the owning user.
--
-- The (request_type, request_id) unique constraint makes the runner's outbox
-- scan idempotent: re-scanning the same outbox file is a no-op upsert.
--
-- inbox_synced_at is set by the runner once it has written (or confirmed
-- already-written) the inbox/ fulfillment file for a decided row — this is
-- what makes the app and the Slack daemon (approvals_daemon.py) idempotent
-- with each other: whichever writes the inbox file first wins, the other
-- finds the file already exists and just marks its own row synced.
-- =============================================================================
CREATE TABLE IF NOT EXISTS public.approvals (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

  -- Matches tools/slack_approvals.APPROVAL_TYPES:
  -- merge_approval | sql_approval | resource_request | strategic_review
  request_type      TEXT NOT NULL,

  -- Matches tools/slack_approvals.classify_outbox_file()'s request_id (e.g. a task_id)
  request_id        TEXT NOT NULL,

  -- The outbox/ filename this row was created from (traceability)
  source_file       TEXT NOT NULL,

  -- Human-readable title (mirrors tools/slack_approvals._DISPLAY_TITLES)
  title             TEXT NOT NULL,

  -- Sanitized + truncated excerpt of the outbox file's content
  -- (tools/slack_approvals.sanitize_excerpt / truncate — never raw secrets)
  body              TEXT NOT NULL DEFAULT '',

  -- Lifecycle: pending | approved | rejected
  status            TEXT NOT NULL DEFAULT 'pending',

  -- Label of who made the decision (app user email/id, or the Slack actor
  -- name if the Slack daemon resolved it first)
  decided_by        TEXT,
  decided_at        TIMESTAMPTZ,

  -- Set once the runner has written (or found already-written) the inbox/
  -- fulfillment file for this decision
  inbox_synced_at   TIMESTAMPTZ,

  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT approvals_request_type_check
    CHECK (request_type IN ('merge_approval', 'sql_approval', 'resource_request', 'strategic_review')),
  CONSTRAINT approvals_status_check
    CHECK (status IN ('pending', 'approved', 'rejected')),
  CONSTRAINT approvals_request_type_id_unique
    UNIQUE (request_type, request_id)
);

DROP TRIGGER IF EXISTS trg_approvals_updated_at ON public.approvals;
CREATE TRIGGER trg_approvals_updated_at
  BEFORE UPDATE ON public.approvals
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();


-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_approvals_user_id
  ON public.approvals(user_id);

CREATE INDEX IF NOT EXISTS idx_approvals_status
  ON public.approvals(status);

CREATE INDEX IF NOT EXISTS idx_approvals_created_at
  ON public.approvals(created_at DESC);

-- Fast lookup for the runner's "decided but not yet inbox-synced" poll
CREATE INDEX IF NOT EXISTS idx_approvals_pending_sync
  ON public.approvals(status, inbox_synced_at)
  WHERE inbox_synced_at IS NULL;


-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- Owner-only: a user can only see/act on their own approval rows. No
-- business_id ownership check applies (this table has no business_id column).
-- =============================================================================
ALTER TABLE public.approvals ENABLE ROW LEVEL SECURITY;

CREATE POLICY "approvals: select own"
  ON public.approvals FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "approvals: insert own"
  ON public.approvals FOR INSERT
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "approvals: update own"
  ON public.approvals FOR UPDATE
  USING (auth.uid() = user_id);

CREATE POLICY "approvals: delete own"
  ON public.approvals FOR DELETE
  USING (auth.uid() = user_id);
