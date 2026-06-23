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
- `transaction_rule_engine` — Deterministic validation of signings and trades (cap legality, salary matching, roster limits, CBA-style rules). Returns `TransactionValidationResult`.
- `roster_need_service` — Analyzes roster composition and identifies positional/role shortfalls.
- `free_agent_service` — Reads the free-agent pool and returns candidate targets filtered by team need and cap feasibility.
- `trade_simulator` — Simulates two-team trades: salary matching, asset exchange, post-trade cap impact.
- `depth_chart_projector` — Projects the post-transaction depth chart for the upcoming season.
- `evidence_service` — Reads evidence notes and resolves `evidence_id` references for citation.
- `offseason_agent` — Orchestrates the workflow: decomposes the offseason goal, calls the tools above, assembles a structured proposal, and emits it for human approval.

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
