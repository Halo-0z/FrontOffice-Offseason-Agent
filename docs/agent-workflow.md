# Agent Workflow

This document describes the standard offseason workflow the agent follows.

## Current Status (M4-B)

M4-B implements the **deterministic local tool orchestrator**
(`offseason_agent.run_offseason_plan`). The orchestrator runs a fixed
sequence of internal tool calls and returns a structured
`OffseasonAgentRun` with a full `tool_call_trace`. This is **not** an
MCP server, **not** an MCP client, **not** an LLM agent, and **not**
an OpenAI function-calling harness — it is a purely deterministic
local tool registry/orchestrator. No LLM, no network, no disk writes.

The final natural-language proposal/brief output is deferred to M4-C.

## M4-B Flow (implemented)

```
goal (OffseasonGoal)
  -> cap_sheet_service.summarize_cap_sheet(team_id)
  -> roster_need_service.evaluate_roster_needs(team_id)
  -> depth_chart_projector.project_current_depth_chart(team_id)
  -> free_agent_service.rank_free_agents_for_team(team_id)
       filtered by goal.target_positions / goal.max_salary / goal.max_candidates
  -> [for each top fit] trade_simulator.preview_signing(SigningTransaction)
       transaction_type picked conservatively:
         salary <= minimum_salary -> MINIMUM_SIGNING
         salary <= MLE            -> MLE_SIGNING
         otherwise                -> SIMPLE_FA_SIGNING
       every preview has requires_human_approval=True
  -> evidence_service.search_evidence(query, team_id)
     + evidence_service.get_evidence_by_ids(fit evidence_ids)
       merged into one EvidenceBundle (dedup by evidence_id)
  -> OffseasonAgentRun
       status: SUCCESS / PARTIAL / FAILED (derived from tool_call_trace)
       requires_human_approval: True (always)
       sample_data: True (always)
       limitations: MVP scope notes
       tool_call_trace: one ToolCallRecord per call
```

Each tool call is wrapped in a try/except. On failure the orchestrator
records a `FAILED` `ToolCallRecord` and continues (unless `team_id` is
unknown, which is a critical failure). When a tool returns an empty
result (e.g. no free-agent candidates after filtering), the trace
records `FALLBACK` with a clear `fallback_reason`.

### Tool Call Trace

Every `ToolCallRecord` contains:

| Field | Description |
|---|---|
| `tool_name` | Dotted name, e.g. `cap_sheet_service.summarize_cap_sheet`. |
| `status` | `SUCCESS` / `FALLBACK` / `FAILED`. |
| `input_summary` | Short deterministic string describing the input. |
| `output_summary` | Short deterministic string describing the output. |
| `fallback_reason` | `None` on SUCCESS; a clear string on FALLBACK/FAILED. |
| `evidence_ids` | Evidence ids produced or referenced by this call. |

### Run Status Derivation

- Any `FAILED` trace entry → `AgentRunStatus.FAILED`.
- Any `FALLBACK` trace entry (no FAILED) → `AgentRunStatus.PARTIAL`.
- Otherwise → `AgentRunStatus.SUCCESS`.

`SUCCESS` only means the orchestrator ran to completion — it does NOT
mean any transaction was approved. Every output is still a preview
that requires human approval.

## Standard Flow (target M4-C+)

The M4-B flow above is the deterministic core. M4-C will add the
final structured proposal/brief output (natural-language explanation,
plan cards, etc.) on top of the `OffseasonAgentRun`. The full target
flow:

1. **Receive team + offseason goal.** Input: `team_id`, `goal`.
2. **Load cap sheet.** `cap_sheet_service` → current cap space, aprons, exceptions.
3. **Analyze roster needs.** `roster_need_service` → positional/role shortfalls.
4. **Project current depth chart.** `depth_chart_projector` → current depth.
5. **Retrieve free-agent candidates.** `free_agent_service` filtered by needs, cap, and goal constraints.
6. **Preview signing actions.** `trade_simulator.preview_signing` per top fit (always validates via `transaction_rule_engine`).
7. **Retrieve supporting evidence.** `evidence_service.search_evidence` + `get_evidence_by_ids` → `EvidenceBundle`.
8. **Assemble structured run.** `OffseasonAgentRun` with `tool_call_trace`. **(Implemented in M4-B.)**
9. **Generate structured proposal/brief.** Natural-language plan cards, rationale, risk notes. **(Deferred to M4-C.)**
10. **Wait for human approval.** No state mutation until a human approves.

## Guardrails

- The agent **must not** write to cap/roster/contract state directly.
- The agent **must not** declare a transaction valid; only `transaction_rule_engine` can.
- The agent **must not** bypass `trade_simulator` (which calls `transaction_rule_engine` internally).
- The agent **must not** skip the human approval gate.
- The agent **must not** use MCP or call an LLM.
- If a required tool call fails or data is missing, the agent emits a **fallback** trace entry, not a silent success.
- The structured output **must** include all required fields; otherwise it is rejected upstream.

## Fallback Handling

| Trigger | Fallback |
|---|---|
| Missing contract data | Skip player, mark `fallbacks` entry, continue. |
| Roster full | Skip signing path, suggest trade-only or waive suggestion. |
| Cap space insufficient | Mark plan as `cap_risk`, suggest salary-dump trade. |
| Salary matching fails | Drop trade candidate, log to `fallbacks`. |
| Evidence missing | Mark plan `low_confidence`, list in `limitations`. |
| Agent attempts direct mutation | Blocked by guardrail, test `test_agent_guardrails.py`. |

## Structured Output Example

```json
{
  "team": "DEM",
  "goal": "Add a starting-caliber PG without shedding core salary.",
  "plans": [
    {
      "plan_id": "P-001",
      "type": "signing",
      "target_player_id": "fa-042",
      "rationale": "Roster lacks a true starting PG; cap space allows a mid-level deal.",
      "evidence_ids": ["ev-007", "ev-019"]
    },
    {
      "plan_id": "P-002",
      "type": "trade",
      "partner_team_id": "DEM-2",
      "outgoing": ["pl-018"],
      "incoming": ["pl-077"],
      "rationale": "Salary matching trade that upgrades backup wing depth.",
      "evidence_ids": ["ev-031"]
    }
  ],
  "transactions": [
    {
      "transaction_id": "T-001",
      "type": "signing",
      "team": "DEM",
      "player_id": "fa-042",
      "terms": { "years": 2, "annual_salary": 12500000 },
      "validation_status": "valid"
    },
    {
      "transaction_id": "T-002",
      "type": "trade",
      "team_a": "DEM",
      "team_b": "DEM-2",
      "team_a_outgoing": ["pl-018"],
      "team_b_outgoing": ["pl-077"],
      "validation_status": "valid"
    }
  ],
  "validation_status": "all_valid",
  "projected_depth_chart": {
    "PG": ["fa-042", "pl-009"],
    "SG": ["pl-021", "pl-033"],
    "SF": ["pl-007", "pl-040"],
    "PF": ["pl-011", "pl-025"],
    "C":  ["pl-002", "pl-050"]
  },
  "cap_risk": {
    "level": "low",
    "notes": "Plan stays below first apron after signings."
  },
  "basketball_fit": {
    "score": 0.78,
    "notes": "Improves PG rotation and wing defense; bench scoring unchanged."
  },
  "confidence": 0.72,
  "evidence_ids": ["ev-007", "ev-019", "ev-031"],
  "requires_human_approval": true,
  "fallbacks": [
    { "plan_id": "P-003", "reason": "cap_space_insufficient", "details": "Target fa-091 requires max contract." }
  ],
  "limitations": [
    "Demo cap rules; not a full CBA model.",
    "Trade values are heuristic, not market-tested.",
    "Evidence pool is local and small."
  ]
}
```

## Field Contract

| Field | Required | Notes |
|---|---|---|
| `team` | yes | Team id. |
| `goal` | yes | Offseason goal string. |
| `plans` | yes | Array of plan objects with rationale + evidence_ids. |
| `transactions` | yes | Array of validated transaction objects. |
| `validation_status` | yes | `all_valid` / `partial` / `all_invalid`. |
| `projected_depth_chart` | yes | Position -> player ids. |
| `cap_risk` | yes | `{level, notes}`. |
| `basketball_fit` | yes | `{score, notes}`. |
| `confidence` | yes | 0..1. |
| `evidence_ids` | yes | Flat list of cited evidence. |
| `requires_human_approval` | yes | Always `true` in M4. |
| `fallbacks` | yes | Array, possibly empty. |
| `limitations` | yes | Array, possibly empty. |

Missing any required field => the brief is rejected by the upstream validator (see `docs/evaluation.md`).
