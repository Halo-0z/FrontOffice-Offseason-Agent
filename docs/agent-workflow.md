# Agent Workflow

This document describes the standard offseason workflow the agent will follow in later milestones.

## Current Status (M4-A)

M4-A only implements the **evidence retrieval foundation**
(`evidence_service`). The full offseason agent orchestration
(`offseason_agent`) is **NOT implemented yet** — it is deferred to
M4-B. The flow below describes the target M4 design; only the
`evidence_service` step is currently backed by code.

## Standard Flow (target M4-B+)

1. **Receive team + offseason goal.** Input: `team_id`, `goal` (e.g. "retool around a star", "shed salary", "chase a max free agent").
2. **Load cap sheet.** `cap_sheet_service.load(team_id)` -> current cap space, aprons, guaranteed salaries, exceptions.
3. **Load roster.** `roster_need_service.load_roster(team_id)` -> current players, positions, roles.
4. **Analyze roster needs.** `roster_need_service.analyze(...)` -> positional/role shortfalls.
5. **Retrieve free-agent / trade candidates.** `free_agent_service.candidates(...)` and `trade_simulator.candidates(...)` filtered by needs and cap.
6. **Simulate signing/trade actions.** Build candidate `TransactionProposal` objects.
7. **Validate each transaction.** `transaction_rule_engine.validate(proposal)` -> `TransactionValidationResult`. Reject invalid ones or route to fallback.
8. **Project depth chart.** `depth_chart_projector.project(team_id, applied_transactions)` -> projected depth chart.
9. **Retrieve supporting evidence.** `evidence_service.search_evidence(...)` / `evidence_service.get_evidence_by_ids(...)` -> `EvidenceBundle` linking supporting `evidence_id`s to each plan. **(Implemented in M4-A.)**
10. **Generate structured proposal.** `offseason_agent.assemble_brief(...)` -> structured JSON brief. **(Deferred to M4-B.)**
11. **Wait for human approval.** No state mutation until a human approves via `ApprovalControls`.

## M4-A Scope

Only step 9 (`evidence_service`) is implemented. The
`evidence_service` is a deterministic, LLM-free, network-free local
citation layer: it loads DEMO/SAMPLE/SIMULATION notes from
`data/evidence_notes.json` and returns structured `EvidenceBundle`
objects. It is **not** a live RAG system and **not** an external news
scraper. When evidence is missing, it returns an empty
`matched_notes` tuple + a clear `fallback_reason` — it never
fabricates citations.

## Guardrails

- The agent **must not** write to cap/roster/contract state directly.
- The agent **must not** declare a transaction valid; only `transaction_rule_engine` can.
- The agent **must not** skip the human approval gate.
- If a required tool call fails or data is missing, the agent emits a **fallback** entry, not a silent success.
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
