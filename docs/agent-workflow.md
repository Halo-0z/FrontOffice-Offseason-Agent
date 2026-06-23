# Agent Workflow

This document describes the standard offseason workflow the agent follows.

## Current Status (M4-C)

M4-C implements the **deterministic structured proposal builder**
(`proposal_builder.build_structured_proposal`). The builder consumes
an M4-B `OffseasonAgentRun` and produces a frontend-friendly
`StructuredProposal` with `proposal_id`, `status`
(`RECOMMENDED` / `PARTIAL` / `BLOCKED` / `NO_ACTION`),
`recommended_actions`, `risks`, `evidence_refs`, `tool_call_trace`,
short deterministic summaries, `fallback_reasons`, and `limitations`.
This is **not** an MCP server, **not** an MCP client, **not** an LLM
agent, and **not** an OpenAI function-calling harness — it is a purely
deterministic proposal builder. No LLM, no network, no disk writes.

Natural-language polish / LLM output is deferred to a later milestone.

## M4 Flow (implemented)

```
goal (OffseasonGoal)
  -> [M4-B] run_offseason_plan(goal)
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
  -> [M4-C] build_structured_proposal(agent_run)
       -> derive ProposalStatus from agent_run.status + previews
       -> build ProposalAction per signing preview
            (transaction_id / validation_status / is_valid /
             player_name / position / fit_score / matched_need /
             cap_impact_summary / roster_impact_summary /
             depth_chart_impact_summary / evidence_ids /
             requires_human_approval=True)
       -> flatten EvidenceBundle.matched_notes -> ProposalEvidenceRef
            (never fabricate evidence ids)
       -> build ProposalRisk list
            (evidence_missing / validation_failed /
             no_matching_candidate / cap_pressure / sample_data)
       -> echo tool_call_trace from agent_run
       -> build short deterministic cap/roster/depth summaries
       -> collect fallback_reasons from trace + bundle
       -> StructuredProposal
            proposal_id: deterministic (team_id + slugified objective)
            requires_human_approval: True (always)
            sample_data: True (always)
            limitations: MVP scope notes
  -> frontend / brief output
       (natural-language polish / LLM output deferred to a later milestone)
```

Each tool call in the M4-B run is wrapped in a try/except. On failure
the orchestrator records a `FAILED` `ToolCallRecord` and continues
(unless `team_id` is unknown, which is a critical failure). When a
tool returns an empty result (e.g. no free-agent candidates after
filtering), the trace records `FALLBACK` with a clear
`fallback_reason`.

The M4-C builder is **pure**: it does NOT re-run any tool, does NOT
call `transaction_rule_engine` or `trade_simulator` directly, and
does NOT write to disk. It only consumes the `OffseasonAgentRun`.

## M4-B Flow (implemented)

The M4-B portion of the M4 Flow above (from `goal` to
`OffseasonAgentRun`) is the deterministic core. Each tool call is
wrapped in a try/except. On failure the orchestrator records a
`FAILED` `ToolCallRecord` and continues (unless `team_id` is unknown,
which is a critical failure). When a tool returns an empty result
(e.g. no free-agent candidates after filtering), the trace records
`FALLBACK` with a clear `fallback_reason`.

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

## M4-C Proposal Status Derivation

The `proposal_builder` derives `ProposalStatus` from the agent run:

- `agent_run.status == FAILED` → `BLOCKED`.
- No fits and no previews → `NO_ACTION`.
- Previews exist but ALL failed validation → `BLOCKED`.
- At least one valid preview and `agent_run.status == SUCCESS` → `RECOMMENDED`.
- Otherwise (mixed valid/failed, or `agent_run.status == PARTIAL`) → `PARTIAL`.

`RECOMMENDED` only means the orchestrator ran cleanly and at least
one preview passed validation — it does NOT mean any transaction was
approved. Every action still has `requires_human_approval=True`.

## Standard Flow (target later milestones)

The M4 Flow above is the deterministic core. Later milestones will
add natural-language polish / LLM output on top of the
`StructuredProposal`. The full target flow:

1. **Receive team + offseason goal.** Input: `team_id`, `goal`.
2. **Load cap sheet.** `cap_sheet_service` → current cap space, aprons, exceptions.
3. **Analyze roster needs.** `roster_need_service` → positional/role shortfalls.
4. **Project current depth chart.** `depth_chart_projector` → current depth.
5. **Retrieve free-agent candidates.** `free_agent_service` filtered by needs, cap, and goal constraints.
6. **Preview signing actions.** `trade_simulator.preview_signing` per top fit (always validates via `transaction_rule_engine`).
7. **Retrieve supporting evidence.** `evidence_service.search_evidence` + `get_evidence_by_ids` → `EvidenceBundle`.
8. **Assemble structured run.** `OffseasonAgentRun` with `tool_call_trace`. **(Implemented in M4-B.)**
9. **Build structured proposal.** `StructuredProposal` with actions, risks, evidence refs. **(Implemented in M4-C.)**
10. **Natural-language polish / LLM output.** Plan cards, rationale, risk notes. **(Deferred to a later milestone.)**
11. **Wait for human approval.** No state mutation until a human approves.

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
