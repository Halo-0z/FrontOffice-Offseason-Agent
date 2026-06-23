# Architecture

This document describes the layered architecture of `FrontOffice-Offseason-Agent`.

## Layers

```
+-----------------------------------------------+
|  Frontend presentation layer (Next.js/React)  |
|  - CapSheetPanel, TransactionPlanCard,        |
|    DepthChartPreview, EvidencePanel,          |
|    ApprovalControls                           |
+----------------------+------------------------+
                       |
+----------------------v------------------------+
|  Human approval layer                         |
|  - All proposals wait for explicit approval   |
|  - No state mutation without sign-off         |
+----------------------+------------------------+
                       |
+----------------------v------------------------+
|  Agent orchestration layer (offseason_agent)  |
|  - Task decomposition                         |
|  - Tool call orchestration                    |
|  - Structured brief generation                |
|  - LLM only advises, never mutates            |
+----------------------+------------------------+
                       |
+----------------------v------------------------+
|  Deterministic services layer                 |
|  - cap_sheet_service                          |
|  - transaction_rule_engine                    |
|  - roster_need_service                        |
|  - free_agent_service                         |
|  - trade_simulator                            |
|  - depth_chart_projector                      |
|  - evidence_service                           |
+----------------------+------------------------+
                       |
+----------------------v------------------------+
|  Data layer                                   |
|  - data/cap_config.json                       |
|  - data/teams.json                            |
|  - data/players.json                          |
|  - data/contracts.json                        |
|  - data/free_agents.json                      |
|  - data/evidence_notes.json                   |
+-----------------------------------------------+
```

## Service Responsibilities

- `cap_sheet_service` — Computes and exposes the team cap sheet (cap space, aprons, guarantees, exceptions). The single source of truth for salary state. M1 implements: `load_cap_config`, `load_contracts`, `load_team_cap_sheet`, `summarize_cap_sheet`, and a pure `apply_signing_preview` that returns a new `TeamCapSheet` without mutating the input. All cap figures come from `data/cap_config.json`; nothing is hardcoded in Python.
- `transaction_rule_engine` — Deterministic validation of signings and trades (cap legality, salary matching, roster limits, CBA-style rules). Returns `ValidationResult`. M2 implements `validate_signing` / `validate_trade` / `validate_transaction` for `MINIMUM_SIGNING`, `MLE_SIGNING`, `SIMPLE_FA_SIGNING`, and `TWO_TEAM_TRADE`. MVP rules: minimum/MLE salary thresholds, simple-FA must stay under the cap, roster slot limits (`roster_max`), simplified salary matching (`incoming <= outgoing * 1.25 + 100_000`), and apron crossing warnings. Apron hard caps are **not** enforced in M2 (warnings only). The engine never mutates `data/contracts.json` or any roster state; every result has `requires_human_approval=True`.
- `roster_need_service` — Analyzes roster composition and identifies positional/role shortfalls. M3-A implements: `load_roster_players` (loads demo players from `data/players.json`, enriched with `contract_id`/`salary` from `data/contracts.json`), `summarize_position_counts`, and `evaluate_roster_needs` (returns a `RosterNeedReport` with `needs` sorted by priority high→medium, `strengths`, and MVP `limitations`). Heuristic target = 2 players per position; this is a demo roster-planning rule, not a salary/CBA rule, and is kept in this service (not in `cap_config`). Does not call `transaction_rule_engine` or generate proposals.
- `free_agent_service` — Reads the free-agent pool and returns candidate targets filtered by team need and cap feasibility. M3-B implements: `load_free_agents` (reads `data/free_agents.json`), `match_free_agents_to_needs` / `rank_free_agents_for_team` (joins free agents with `evaluate_roster_needs` and returns `FreeAgentFit` objects scored by position match, role keyword, and salary affordability). Deterministic sort: `fit_score` desc then `free_agent_id` asc. Does NOT call `transaction_rule_engine` and does NOT generate `SigningTransaction` objects — it only *suggests* candidates; turning a candidate into a proposal is the agent's (M4) job and validating it is the rule engine's (M2) job. No LLM, no disk writes.
- `trade_simulator` — Previews proposed signings and trades; legality is always delegated to `transaction_rule_engine`. M3-B implements `preview_signing` / `preview_trade` / `preview_transaction`. Each function ALWAYS calls `validate_transaction` first. On FAIL it returns a `TransactionPreview` with `roster_need_after`/`depth_chart_after` set to `None` and a fallback note in `limitations` (a failed preview is never approved). On PASS it builds an in-memory preview roster (current roster + new/incoming players, never writing to `data/players.json` or `data/contracts.json`) and computes the post-transaction `RosterNeedReport` and `ProjectedDepthChart` via M3-A projectors. Every preview has `requires_human_approval=True`. MVP limitations: trade preview reflects team A's roster only (team B deferred); incoming players default to position PG until the M4 agent supplies real positions; no multi-year contract decay. This is **not** a complete NBA trade simulator.
- `depth_chart_projector` — Projects the post-transaction depth chart for the upcoming season. M3-A implements the *current* depth chart: `project_current_depth_chart` and the pure `build_depth_chart_from_players`. One `DepthChartSlot` per position (PG/SG/SF/PF/C); first player at each position is the starter, rest are backups; `need_level` is `high` (empty) / `medium` (1) / `low` (2+). M3-B's `trade_simulator` reuses `build_depth_chart_from_players` on in-memory preview rosters to produce `depth_chart_after`; no separate post-transaction projector was added.
- `evidence_service` — The **evidence foundation** for the future M4-B offseason agent. M4-A implements: `load_evidence_notes` (reads DEMO/SAMPLE/SIMULATION notes from `data/evidence_notes.json`), `get_evidence_by_ids` (exact id lookup, reports `missing_evidence_ids` + `fallback_reason`), `search_evidence` (deterministic scoring by `team_id` / `player_id` / `topics` / lowercase query token overlap, sorted by score desc then `evidence_id` asc, `limit` applied), and `build_evidence_bundle` (dispatches to id lookup when `evidence_ids` is non-empty, else facet search). When evidence is missing, returns empty `matched_notes` + clear `fallback_reason` — it NEVER fabricates notes. Every note/bundle is `sample_data=True`. This is **not** an external news scraper or live RAG: no LLM, no network, no embeddings, no disk writes, no calls to `transaction_rule_engine`, no proposal generation. It is the local demo citation layer the agent will use to justify plans.
- `offseason_agent` — Orchestrates the workflow: decomposes the offseason goal, calls the tools above, assembles a structured proposal, and emits it for human approval. M4-B implements a **deterministic local tool orchestrator** (`run_offseason_plan`): it runs a fixed sequence of internal tool calls (`cap_sheet_service` → `roster_need_service` → `depth_chart_projector` → `free_agent_service` → `trade_simulator.preview_signing` → `evidence_service`), records a `ToolCallRecord` per call (with `tool_name` / `status` / `input_summary` / `output_summary` / `fallback_reason` / `evidence_ids`), and returns a structured `OffseasonAgentRun`. This is **not** an MCP server, **not** an MCP client, **not** an LLM agent, and **not** an OpenAI function-calling harness. No LLM, no network, no disk writes. Every signing preview has `requires_human_approval=True`; the run itself has `requires_human_approval=True` and `sample_data=True`. On tool failure the orchestrator records a `FAILED`/`FALLBACK` trace entry and continues (unless `team_id` is unknown). The final natural-language proposal/brief output is deferred to M4-C.
- `proposal_builder` — Converts an M4-B `OffseasonAgentRun` into a frontend-friendly `StructuredProposal`. M4-C implements `build_structured_proposal(agent_run)` and the convenience wrapper `run_goal_and_build_proposal(goal)`. The builder derives a `ProposalStatus` (`RECOMMENDED` / `PARTIAL` / `BLOCKED` / `NO_ACTION`) from the agent run, builds `ProposalAction` objects (one per signing preview, with `validation_status` / `is_valid` / `cap_impact_summary` / `roster_impact_summary` / `depth_chart_impact_summary` / `evidence_ids` / `requires_human_approval=True`), flattens `EvidenceNote`s into `ProposalEvidenceRef`s (never fabricating ids), emits `ProposalRisk`s (`evidence_missing` / `validation_failed` / `no_matching_candidate` / `cap_pressure` / `sample_data`), and echoes the `tool_call_trace`. It is a **deterministic proposal builder**, **not** an LLM writer, **not** an MCP server, and **not** a re-validation layer — it does NOT call `transaction_rule_engine` or `trade_simulator` directly and does NOT write to disk. Every action is a preview that requires human approval. Natural-language polish / LLM output is deferred to a later milestone.
- `proposal_evaluator` — Evaluates a M4-C `StructuredProposal` for safety, completeness, and trustworthiness. M4-D implements `evaluate_structured_proposal(proposal)`, `run_evaluation_scenario(scenario)`, and `run_default_evaluation_scenarios()`. The evaluator returns a `ProposalEvaluation` with `status` (`PASS` / `WARNING` / `FAIL`), `issues` (each an `EvaluationIssue` with `code` / `severity` / `summary` / `remediation`), `passed_checks`, `failed_checks`, `warnings`, `limitations`, and `sample_data=True`. Checks cover: human-approval guardrail (proposal + every action must have `requires_human_approval=True`), validation guardrail (FAIL validations must not appear as valid recommended actions), evidence guardrail (no fabricated evidence; empty `evidence_refs` on a `RECOMMENDED` proposal is a WARNING), tool-trace guardrail (the six key tools must appear in `tool_call_trace`), fallback consistency (`NO_ACTION` must carry a `HOLD` action or `no_matching_candidate` risk; `fallback_reasons` must be backed by a risk or limitation), sample-data guardrail, and determinism. The evaluator is **not** an approval layer — it does NOT approve transactions, does NOT change the proposal's status to "approved", does NOT call `transaction_rule_engine` or `trade_simulator`, does NOT call any LLM, does NOT use MCP, and does NOT write to disk. `evaluate_structured_proposal` only consumes a `StructuredProposal`; the scenario runner (`run_evaluation_scenario` / `run_default_evaluation_scenarios`) calls `run_goal_and_build_proposal` end-to-end because the scenario suite is a regression test of the full system.

## Critical Invariant

The LLM in the agent layer **does not directly modify system state**. It can only:

1. Call deterministic backend tools.
2. Organize proposals and explain risks.
3. Emit a structured brief awaiting human approval.

All mutations (cap, roster, contract) flow through `transaction_rule_engine` validation **and** human approval. This is enforced by guardrails covered in `docs/agent-workflow.md` and tested in `backend/app/tests/test_agent_guardrails.py`.

## Data Flow (per offseason goal)

```
team + goal
  -> cap_sheet_service.load(team)
  -> roster_need_service.analyze(team)
  -> free_agent_service.candidates(team, needs, cap)
  -> trade_simulator.candidates(team, needs, cap)
  -> [for each candidate] transaction_rule_engine.validate(...)
  -> depth_chart_projector.project(team, applied_transactions)
  -> evidence_service.attach(evidence_ids)
  -> offseason_agent.assemble_brief(...)
  -> human approval gate
```
