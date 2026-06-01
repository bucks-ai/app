# HANDOFF: Agent Registry v1

**Branch:** `feature/agent-registry-v1`
**Author:** Arnav (AI session, 2026-06-01)
**Status:** Ready for review and merge

---

## Purpose

This task establishes the first formal agent registry for bucks.ai's operating team.

bucks.ai is an AI startup operator. Work is organised into **Nodes** (broad company/system
functions) containing **Agents** (specialist workers). This registry defines all 21 MVP
agents, their static templates, and a business-aware status resolver that maps live
business data onto each agent without requiring new database tables.

---

## Files Created

| File | Purpose |
|------|---------|
| `src/types/agents.ts` | All agent TypeScript types |
| `src/lib/agents/registry.ts` | Static agent registry (21 agents, 6 nodes) |
| `src/lib/agents/status.ts` | Business-aware agent status resolver |
| `src/app/api/businesses/[id]/agents/route.ts` | REST API route |
| `HANDOFF_agent-registry-v1.md` | This file |

## Files Modified

None. The task added new files only. No existing execution, validation, or research
logic was changed.

---

## 21 MVP Agents

### Strategy Node
| # | Agent | ID | Backing Feature |
|---|-------|----|----------------|
| 1 | Idea Intake Agent | `idea_intake` | Intake wizard |
| 2 | Blueprint Agent | `blueprint` | /api/generate-blueprint |
| 3 | Opportunity Framing Agent | `opportunity_framing` | Research mode backend |

### Deployment Node
| # | Agent | ID | Backing Feature |
|---|-------|----|----------------|
| 4 | Repository Agent | `repository` | /api/github/create-repo |
| 5 | Scaffold Agent | `scaffold` | /api/github/prepare-next-scaffold |
| 6 | Deployment Status Agent | `deployment_status` | /api/vercel + /api/businesses/[id]/execution-status |

### Validation Node
| # | Agent | ID | Backing Feature |
|---|-------|----|----------------|
| 7 | Persona Agent | `persona` | /api/businesses/[id]/validation/personas |
| 8 | Hypothesis Agent | `hypothesis` | /api/businesses/[id]/validation/hypotheses |
| 9 | Feedback Analysis Agent | `feedback_analysis` | /api/businesses/[id]/validation/feedback |

### Research Node
| #  | Agent | ID | Backing Feature |
|----|-------|----|----------------|
| 10 | Market Research Agent | `market_research` | /api/businesses/[id]/research |
| 11 | Customer Segment Agent | `customer_segment` | /api/businesses/[id]/research/segments |
| 12 | Competitor Agent | `competitor` | /api/businesses/[id]/research/competitors |
| 13 | Monetization Agent | `monetization` | /api/businesses/[id]/research/buyer-budgets |
| 14 | Distribution Agent | `distribution` | /api/businesses/[id]/research/distribution |
| 15 | Risk Agent | `risk` | /api/businesses/[id]/research/risks |
| 16 | Opportunity Scoring Agent | `opportunity_scoring` | Research report opportunity_score field |

### Safety / Permissions Node
| #  | Agent | ID | Backing Feature |
|----|-------|----|----------------|
| 17 | Tool Permission Agent | `tool_permission` | /api/tool-permissions |
| 18 | Risk Review Agent | `risk_review` | human_required_actions table |

### Orchestration Node
| #  | Agent | ID | Backing Feature |
|----|-------|----|----------------|
| 19 | Task Router Agent | `task_router` | /api/businesses/[id]/execution-status |
| 20 | Next Action Agent | `next_action` | src/components/workspace/next-action.ts |
| 21 | Run Monitor Agent | `run_monitor` | /api/businesses/[id]/execution-timeline |

---

## Node Grouping

```
strategy       → idea_intake, blueprint, opportunity_framing
deployment     → repository, scaffold, deployment_status
validation     → persona, hypothesis, feedback_analysis
research       → market_research, customer_segment, competitor,
                 monetization, distribution, risk, opportunity_scoring
safety         → tool_permission, risk_review
orchestration  → task_router, next_action, run_monitor
```

---

## How Status Is Resolved

No new database tables were created. Status is inferred from existing data:

| Signal | Source |
|--------|--------|
| Blueprint exists | `business_blueprints` via `getLatestBlueprintForBusiness` |
| GitHub repo | `agent_activity_logs` + `getLatestGitHubRepoForBusiness` |
| Scaffold prepared | `agent_activity_logs` (type: `github_next_scaffold_prepared`) |
| Vercel project | `getLatestVercelProjectForBusiness` |
| Tool permissions | `tool_permissions` via `getToolPermissionsForBusiness` |
| Research generated | `agent_activity_logs` (type: `research_workspace_generated`) |
| Research report | `agent_activity_logs` (type: `research_report_created`) |
| Validation seeded | `agent_activity_logs` (type: `validation_workspace_seeded`) |
| Feedback added | `agent_activity_logs` (type: `validation_feedback_added`) |
| Human actions | `human_required_actions` via `getHumanRequiredActions` |

Status values:
- `unavailable` — prerequisites are not met
- `ready` — prerequisites exist; waiting to run
- `active` — currently executing (reserved for Agent Runs v1)
- `blocked` — a dependency or permission is missing
- `waiting_for_approval` — pending founder approval
- `completed` — work has been done at least once
- `monitoring` — running continuously in watch mode

Status resolution is intentionally approximate — activity logs are used as a proxy
for table contents so the registry works even if validation/research schemas have not
been applied.

---

## API Route

```
GET /api/businesses/[id]/agents
Authorization: Session cookie (Supabase auth)
```

Response (success):
```json
{
  "ok": true,
  "data": {
    "summary": { "businessId": "...", "totalAgents": 21, ... },
    "nodes": [ { "nodeId": "strategy", "agents": [...], ... }, ... ],
    "agents": [ { "template": {...}, "businessStatus": {...} }, ... ]
  }
}
```

Response (error):
```json
{
  "ok": false,
  "code": "unauthenticated | forbidden | business_not_found | agent_registry_unavailable",
  "error": "Human-readable message"
}
```

---

## How to Test

### Manual smoke tests

```bash
# 1. Logged-out request — expect 401
curl http://localhost:3000/api/businesses/SOME_ID/agents

# 2. Wrong owner — expect 403
# Sign in as user A, request business owned by user B

# 3. Valid owner — expect 200 with 21 agents
# Sign in, get your business ID from dashboard, then:
curl -b your-session-cookie \
  http://localhost:3000/api/businesses/YOUR_BUSINESS_ID/agents | jq '.data.summary'

# 4. Verify agent count
curl ... | jq '.data.summary.totalAgents'   # → 21

# 5. Verify node grouping
curl ... | jq '[.data.nodes[] | .nodeId]'
# → ["strategy","deployment","validation","research","safety","orchestration"]

# 6. Verify no crash on missing validation/research data
# Works even before supabase/validation.sql and supabase/research.sql are applied
# because status resolution uses activity logs, not table queries
```

### Type check / build check
```bash
cd ~/bucks-ai-arnav-agent-registry
./scripts/check.sh
```

---

## Known Limitations

1. **Status is approximate** — inferred from activity log presence, not direct table queries. A business that had validation seeded and then fully deleted will still show `completed`.
2. **`active` status unused** — reserved for Agent Runs v1 when actual LLM execution sessions exist.
3. **No pagination** — all 21 agents returned in every response. Fine for MVP.
4. **No caching** — each request performs ~7 parallel Supabase queries. Acceptable for MVP.
5. **Node description hard-coded** — not localised. Fine for MVP.

---

## Intentionally Deferred

The following are explicitly out of scope for this task:

| Feature | Reason |
|---------|--------|
| Agent Runs v1 (run history, LLM execution) | Separate task; requires new `agent_runs` table |
| Operating Team UI | Separate task; deferred post-registry |
| Actual LLM agent execution | Requires Agent Runs v1 + orchestration layer |
| Dynamic / self-creating agents | Not in MVP scope |
| Multi-agent conversations | Requires orchestration graph engine |
| Workflow graph engine | Future milestone |
| `agent_runs` database table | Not needed for Agent Registry v1 |
| Supabase SQL migration | No new tables required for this task |
