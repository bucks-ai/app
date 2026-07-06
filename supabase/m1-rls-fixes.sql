-- =============================================================================
-- bucks.ai — M1 RLS Gap Fixes
-- =============================================================================
-- IMPORTANT: Arnav must run this file in the Supabase SQL Editor.
-- This file is intentionally NOT applied automatically.
--
-- How to apply:
--   1. Go to Supabase project → SQL Editor
--   2. Paste this entire file and click Run
--
-- Prerequisites:
--   supabase/schema.sql, supabase/agent-runs.sql, supabase/missions.sql,
--   supabase/research.sql, supabase/validation.sql, and
--   supabase/migrations/0001_runner_migrations.sql must already be applied.
--
-- This migration closes the three gaps documented in docs/M1-RLS-AUDIT.md:
--   1. public._runner_migrations never enabled RLS.
--   2. public.profiles was missing a DELETE policy.
--   3. Every business_id/user_id-scoped table's INSERT/UPDATE policies only
--      checked auth.uid() = user_id, without verifying the caller actually
--      owns the referenced business_id (or mission_id/lead_id/hypothesis_id).
--
-- This migration is additive and idempotent:
--   - ALTER TABLE ... ENABLE ROW LEVEL SECURITY is a no-op if already enabled.
--   - Every CREATE POLICY is preceded by DROP POLICY IF EXISTS on the exact
--     same policy name, so re-running this file is always safe.
--   - No existing policy is dropped without being immediately replaced by an
--     equal-or-stricter version. Nothing is weakened.
-- =============================================================================


-- =============================================================================
-- GAP 1 — public._runner_migrations has no RLS
-- Internal ledger written only via a service-role connection
-- (runner/langgraph/tools/db_tools.py). The service role bypasses RLS, so
-- enabling it with no policies denies every other role by default.
-- =============================================================================
ALTER TABLE public._runner_migrations ENABLE ROW LEVEL SECURITY;
-- Intentionally no policies: only the service role (which bypasses RLS) should
-- ever read or write this table. All other roles are denied by default.


-- =============================================================================
-- GAP 2 — public.profiles missing a DELETE policy
-- INSERT is intentionally left unpoliced: profile rows are only ever created
-- via the handle_new_user() SECURITY DEFINER trigger in supabase/schema.sql.
-- =============================================================================
DROP POLICY IF EXISTS "profiles: delete own" ON public.profiles;
CREATE POLICY "profiles: delete own"
  ON public.profiles FOR DELETE
  USING (auth.uid() = id);


-- =============================================================================
-- GAP 3 — business_id (and mission_id/lead_id/hypothesis_id) ownership was not
-- verified on INSERT/UPDATE. Previously a caller could attach a row to any
-- business_id as long as they stamped their own user_id on it. Each policy
-- below is replaced with a version that adds an EXISTS ownership check.
-- =============================================================================

-- business_blueprints
DROP POLICY IF EXISTS "blueprints: insert own" ON public.business_blueprints;
CREATE POLICY "blueprints: insert own"
  ON public.business_blueprints FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = business_blueprints.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "blueprints: update own" ON public.business_blueprints;
CREATE POLICY "blueprints: update own"
  ON public.business_blueprints FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = business_blueprints.business_id AND b.user_id = auth.uid()
    )
  );

-- human_required_actions
DROP POLICY IF EXISTS "human_actions: insert own" ON public.human_required_actions;
CREATE POLICY "human_actions: insert own"
  ON public.human_required_actions FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = human_required_actions.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "human_actions: update own" ON public.human_required_actions;
CREATE POLICY "human_actions: update own"
  ON public.human_required_actions FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = human_required_actions.business_id AND b.user_id = auth.uid()
    )
  );

-- agent_activity_logs
DROP POLICY IF EXISTS "activity_logs: insert own" ON public.agent_activity_logs;
CREATE POLICY "activity_logs: insert own"
  ON public.agent_activity_logs FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = agent_activity_logs.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "activity_logs: update own" ON public.agent_activity_logs;
CREATE POLICY "activity_logs: update own"
  ON public.agent_activity_logs FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = agent_activity_logs.business_id AND b.user_id = auth.uid()
    )
  );

-- tool_permissions (business_id is nullable)
DROP POLICY IF EXISTS "tool_permissions: insert own" ON public.tool_permissions;
CREATE POLICY "tool_permissions: insert own"
  ON public.tool_permissions FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND (
      business_id IS NULL
      OR EXISTS (
        SELECT 1 FROM public.businesses b
        WHERE b.id = tool_permissions.business_id AND b.user_id = auth.uid()
      )
    )
  );

DROP POLICY IF EXISTS "tool_permissions: update own" ON public.tool_permissions;
CREATE POLICY "tool_permissions: update own"
  ON public.tool_permissions FOR UPDATE
  USING (
    auth.uid() = user_id
    AND (
      business_id IS NULL
      OR EXISTS (
        SELECT 1 FROM public.businesses b
        WHERE b.id = tool_permissions.business_id AND b.user_id = auth.uid()
      )
    )
  );

-- agent_runs
DROP POLICY IF EXISTS "agent_runs: insert own" ON public.agent_runs;
CREATE POLICY "agent_runs: insert own"
  ON public.agent_runs FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = agent_runs.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "agent_runs: update own" ON public.agent_runs;
CREATE POLICY "agent_runs: update own"
  ON public.agent_runs FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = agent_runs.business_id AND b.user_id = auth.uid()
    )
  );

-- missions
DROP POLICY IF EXISTS "missions: insert own" ON public.missions;
CREATE POLICY "missions: insert own"
  ON public.missions FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = missions.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "missions: update own" ON public.missions;
CREATE POLICY "missions: update own"
  ON public.missions FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = missions.business_id AND b.user_id = auth.uid()
    )
  );

-- mission_tasks (checks both business_id and mission_id)
DROP POLICY IF EXISTS "mission_tasks: insert own" ON public.mission_tasks;
CREATE POLICY "mission_tasks: insert own"
  ON public.mission_tasks FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = mission_tasks.business_id AND b.user_id = auth.uid()
    )
    AND EXISTS (
      SELECT 1 FROM public.missions m
      WHERE m.id = mission_tasks.mission_id AND m.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "mission_tasks: update own" ON public.mission_tasks;
CREATE POLICY "mission_tasks: update own"
  ON public.mission_tasks FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = mission_tasks.business_id AND b.user_id = auth.uid()
    )
    AND EXISTS (
      SELECT 1 FROM public.missions m
      WHERE m.id = mission_tasks.mission_id AND m.user_id = auth.uid()
    )
  );

-- research_reports
DROP POLICY IF EXISTS "research_reports: insert own" ON public.research_reports;
CREATE POLICY "research_reports: insert own"
  ON public.research_reports FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_reports.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "research_reports: update own" ON public.research_reports;
CREATE POLICY "research_reports: update own"
  ON public.research_reports FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_reports.business_id AND b.user_id = auth.uid()
    )
  );

-- research_customer_segments
DROP POLICY IF EXISTS "research_customer_segments: insert own" ON public.research_customer_segments;
CREATE POLICY "research_customer_segments: insert own"
  ON public.research_customer_segments FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_customer_segments.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "research_customer_segments: update own" ON public.research_customer_segments;
CREATE POLICY "research_customer_segments: update own"
  ON public.research_customer_segments FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_customer_segments.business_id AND b.user_id = auth.uid()
    )
  );

-- research_buyer_budgets
DROP POLICY IF EXISTS "research_buyer_budgets: insert own" ON public.research_buyer_budgets;
CREATE POLICY "research_buyer_budgets: insert own"
  ON public.research_buyer_budgets FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_buyer_budgets.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "research_buyer_budgets: update own" ON public.research_buyer_budgets;
CREATE POLICY "research_buyer_budgets: update own"
  ON public.research_buyer_budgets FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_buyer_budgets.business_id AND b.user_id = auth.uid()
    )
  );

-- research_competitors
DROP POLICY IF EXISTS "research_competitors: insert own" ON public.research_competitors;
CREATE POLICY "research_competitors: insert own"
  ON public.research_competitors FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_competitors.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "research_competitors: update own" ON public.research_competitors;
CREATE POLICY "research_competitors: update own"
  ON public.research_competitors FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_competitors.business_id AND b.user_id = auth.uid()
    )
  );

-- research_monetization_models
DROP POLICY IF EXISTS "research_monetization_models: insert own" ON public.research_monetization_models;
CREATE POLICY "research_monetization_models: insert own"
  ON public.research_monetization_models FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_monetization_models.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "research_monetization_models: update own" ON public.research_monetization_models;
CREATE POLICY "research_monetization_models: update own"
  ON public.research_monetization_models FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_monetization_models.business_id AND b.user_id = auth.uid()
    )
  );

-- research_distribution_channels
DROP POLICY IF EXISTS "research_distribution_channels: insert own" ON public.research_distribution_channels;
CREATE POLICY "research_distribution_channels: insert own"
  ON public.research_distribution_channels FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_distribution_channels.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "research_distribution_channels: update own" ON public.research_distribution_channels;
CREATE POLICY "research_distribution_channels: update own"
  ON public.research_distribution_channels FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_distribution_channels.business_id AND b.user_id = auth.uid()
    )
  );

-- research_risks
DROP POLICY IF EXISTS "research_risks: insert own" ON public.research_risks;
CREATE POLICY "research_risks: insert own"
  ON public.research_risks FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_risks.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "research_risks: update own" ON public.research_risks;
CREATE POLICY "research_risks: update own"
  ON public.research_risks FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_risks.business_id AND b.user_id = auth.uid()
    )
  );

-- research_hypotheses
DROP POLICY IF EXISTS "research_hypotheses: insert own" ON public.research_hypotheses;
CREATE POLICY "research_hypotheses: insert own"
  ON public.research_hypotheses FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_hypotheses.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "research_hypotheses: update own" ON public.research_hypotheses;
CREATE POLICY "research_hypotheses: update own"
  ON public.research_hypotheses FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_hypotheses.business_id AND b.user_id = auth.uid()
    )
  );

-- research_evidence
DROP POLICY IF EXISTS "research_evidence: insert own" ON public.research_evidence;
CREATE POLICY "research_evidence: insert own"
  ON public.research_evidence FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_evidence.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "research_evidence: update own" ON public.research_evidence;
CREATE POLICY "research_evidence: update own"
  ON public.research_evidence FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = research_evidence.business_id AND b.user_id = auth.uid()
    )
  );

-- validation_personas
DROP POLICY IF EXISTS "validation_personas: insert own" ON public.validation_personas;
CREATE POLICY "validation_personas: insert own"
  ON public.validation_personas FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = validation_personas.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "validation_personas: update own" ON public.validation_personas;
CREATE POLICY "validation_personas: update own"
  ON public.validation_personas FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = validation_personas.business_id AND b.user_id = auth.uid()
    )
  );

-- validation_hypotheses
DROP POLICY IF EXISTS "validation_hypotheses: insert own" ON public.validation_hypotheses;
CREATE POLICY "validation_hypotheses: insert own"
  ON public.validation_hypotheses FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = validation_hypotheses.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "validation_hypotheses: update own" ON public.validation_hypotheses;
CREATE POLICY "validation_hypotheses: update own"
  ON public.validation_hypotheses FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = validation_hypotheses.business_id AND b.user_id = auth.uid()
    )
  );

-- validation_leads
DROP POLICY IF EXISTS "validation_leads: insert own" ON public.validation_leads;
CREATE POLICY "validation_leads: insert own"
  ON public.validation_leads FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = validation_leads.business_id AND b.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "validation_leads: update own" ON public.validation_leads;
CREATE POLICY "validation_leads: update own"
  ON public.validation_leads FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = validation_leads.business_id AND b.user_id = auth.uid()
    )
  );

-- validation_feedback_notes (also checks the optional lead_id/hypothesis_id belong to the caller)
DROP POLICY IF EXISTS "validation_feedback_notes: insert own" ON public.validation_feedback_notes;
CREATE POLICY "validation_feedback_notes: insert own"
  ON public.validation_feedback_notes FOR INSERT
  WITH CHECK (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = validation_feedback_notes.business_id AND b.user_id = auth.uid()
    )
    AND (
      lead_id IS NULL
      OR EXISTS (SELECT 1 FROM public.validation_leads l WHERE l.id = validation_feedback_notes.lead_id AND l.user_id = auth.uid())
    )
    AND (
      hypothesis_id IS NULL
      OR EXISTS (SELECT 1 FROM public.validation_hypotheses h WHERE h.id = validation_feedback_notes.hypothesis_id AND h.user_id = auth.uid())
    )
  );

DROP POLICY IF EXISTS "validation_feedback_notes: update own" ON public.validation_feedback_notes;
CREATE POLICY "validation_feedback_notes: update own"
  ON public.validation_feedback_notes FOR UPDATE
  USING (
    auth.uid() = user_id
    AND EXISTS (
      SELECT 1 FROM public.businesses b
      WHERE b.id = validation_feedback_notes.business_id AND b.user_id = auth.uid()
    )
    AND (
      lead_id IS NULL
      OR EXISTS (SELECT 1 FROM public.validation_leads l WHERE l.id = validation_feedback_notes.lead_id AND l.user_id = auth.uid())
    )
    AND (
      hypothesis_id IS NULL
      OR EXISTS (SELECT 1 FROM public.validation_hypotheses h WHERE h.id = validation_feedback_notes.hypothesis_id AND h.user_id = auth.uid())
    )
  );
