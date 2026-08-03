# M1 RLS Audit

## Summary

This audit reviewed every SQL file under `supabase/` (`schema.sql`, `agent-runs.sql`, `missions.sql`, `research.sql`, `validation.sql`, and `migrations/0001_runner_migrations.sql`) and enumerated all 23 tables they define, whether row level security (RLS) is enabled on each, and which policies exist for `SELECT`, `INSERT`, `UPDATE`, and `DELETE`. Overall, RLS hygiene across the 22 application tables in the `public` schema is good: every one of them enables RLS and ships a consistent "own row" policy pattern scoped to `auth.uid() = user_id`. Three categories of gaps were found. First, `_runner_migrations` (created in `migrations/0001_runner_migrations.sql`) has no schema qualifier and never enables RLS at all, leaving an internal ledger table open to any role with default PostgREST grants on the `public` schema. Second, `public.profiles` is missing `INSERT` and `DELETE` policies — profile creation currently relies entirely on the `SECURITY DEFINER` trigger, and there is no path for a user to delete their own profile row directly. Third, and most significant, twenty tables that carry both a `business_id` and a `user_id` column (everything descending from `businesses` except `businesses` itself and `profiles`) only check `auth.uid() = user_id` on `INSERT`/`UPDATE`. None of them verify that the `business_id` (or, for `mission_tasks`, the `mission_id`) supplied in the payload actually belongs to a business owned by the caller. This lets an authenticated user attach rows to a `business_id` they do not own (as long as they set `user_id` to themselves), which is a cross-tenant data-integrity gap even though the existing `SELECT` policies prevent the attacker from reading rows that belong to another `user_id`. This is a documentation-only audit — no SQL schema files were modified.

## Table Inventory

| Table | RLS Enabled | Policies | Gaps |
|---|---|---|---|
| `public.profiles` | Yes | SELECT own, UPDATE own | No INSERT policy (relies on `handle_new_user` trigger); no DELETE policy |
| `public.businesses` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | None |
| `public.business_blueprints` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.human_required_actions` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.agent_activity_logs` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.tool_permissions` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify nullable `business_id` belongs to caller |
| `public.agent_runs` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.missions` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.mission_tasks` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` or `mission_id` belong to caller |
| `public.research_reports` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.research_customer_segments` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.research_buyer_budgets` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.research_competitors` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.research_monetization_models` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.research_distribution_channels` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.research_risks` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.research_hypotheses` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.research_evidence` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.validation_personas` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.validation_hypotheses` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.validation_leads` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller |
| `public.validation_feedback_notes` | Yes | SELECT, INSERT, UPDATE, DELETE (own via `user_id`) | INSERT/UPDATE do not verify `business_id` belongs to caller; also accepts arbitrary `lead_id`/`hypothesis_id` without ownership check |
| `_runner_migrations` (no schema qualifier, defaults to `public`) | **No** | None | RLS never enabled — table is fully open to any role with default PostgREST grants on `public` |

## Recommended Fixes

### Gap 1 — `_runner_migrations` has no RLS

This table is an internal ledger written by `runner/langgraph/tools/db_tools.py` using a service-role connection. It is never meant to be reachable from the browser/anon/authenticated roles, so the fix is to enable RLS and add no permissive policies — the service role bypasses RLS automatically, while every other role is denied by default.

```sql
ALTER TABLE public._runner_migrations ENABLE ROW LEVEL SECURITY;
-- Intentionally no policies: only the service role (which bypasses RLS) should
-- ever read or write this table. All other roles are denied by default.
```

### Gap 2 — `public.profiles` missing INSERT/DELETE policies

Profile rows are created by the `handle_new_user` trigger (`SECURITY DEFINER`), so a permissive `INSERT` policy is not required for signup to work — but the missing policy should be documented as intentional rather than left as an oversight, and a `DELETE` policy should exist so a user can remove their own profile row (e.g. for account self-service) without needing a service-role call.

```sql
-- Explicitly document that direct user inserts are not allowed; profile rows
-- are only created via the handle_new_user() trigger (SECURITY DEFINER).
-- No INSERT policy is added here on purpose.

CREATE POLICY "profiles: delete own"
  ON public.profiles FOR DELETE
  USING (auth.uid() = id);
```

### Gap 3 — `business_id` ownership not verified on INSERT/UPDATE

The following pattern applies to every table listed below. Today, the `INSERT`/`UPDATE` policies only check `auth.uid() = user_id`, so a caller can attach a row to any `business_id` as long as they stamp their own `user_id` on it. The fix adds an `EXISTS` check against `public.businesses` to confirm the `business_id` is actually owned by the caller.

```sql
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
```
