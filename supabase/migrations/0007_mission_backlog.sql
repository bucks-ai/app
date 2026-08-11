-- =============================================================================
-- M4c: mission_backlog — roadmap-as-data
-- =============================================================================
-- The founder approves the whole mission roadmap ONCE by setting approved=true
-- on each entry. The runner reads this table (ordered by position) and auto-seeds
-- the next approved, unstarted entry into missions/mission_tasks when the current
-- mission completes — eliminating per-mission seeding entirely.
--
-- Human gates that remain: SQL approvals, resource/credential gates, budget caps.
-- Per-mission seeding is abolished as an unnecessary gate.

CREATE TABLE IF NOT EXISTS mission_backlog (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position    INTEGER NOT NULL UNIQUE,   -- execution order; lowest first
    name        TEXT NOT NULL,
    goal        TEXT,
    approved    BOOLEAN NOT NULL DEFAULT FALSE,
    seeded_at   TIMESTAMPTZ,               -- set when the entry is promoted to missions
    mission_id  UUID REFERENCES missions(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mission_backlog_tasks (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backlog_id       UUID NOT NULL REFERENCES mission_backlog(id) ON DELETE CASCADE,
    position         INTEGER NOT NULL,
    title            TEXT NOT NULL,
    type             TEXT NOT NULL DEFAULT 'general',
    branch           TEXT,
    preferred_worker TEXT,
    description      TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (backlog_id, position)
);

-- Index for the hot query path: next approved, unstarted entry
CREATE INDEX IF NOT EXISTS idx_mission_backlog_approved_unseeded
    ON mission_backlog (position)
    WHERE approved = TRUE AND seeded_at IS NULL;

COMMENT ON TABLE mission_backlog IS
    'M4c roadmap-as-data: pre-approved mission specs. approved=true + seeded_at IS NULL = next auto-seed target.';
COMMENT ON TABLE mission_backlog_tasks IS
    'Task specs for each mission_backlog entry. Promoted to mission_tasks when the backlog entry is seeded.';
