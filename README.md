# FrontOffice-Offseason-Agent

> NBA offseason front-office transaction simulation agent.

## Project Positioning

`FrontOffice-Offseason-Agent` is a standalone project. It is **not** a submodule of, and does **not** depend on, `DraftMind` or any other existing repo. It does not reuse DraftMind code or data.

The system simulates an NBA front office during the offseason. Given a team's cap sheet, player contracts, roster needs, the free-agent pool, and league transaction/signing rules, the agent proposes feasible offseason signing/trade plans and projects the resulting depth chart for the next season.

This project is **not** a real-world trade predictor. It does not guarantee that any simulated plan will actually happen. The goal is to build a controllable, testable **agentic decision workflow** that demonstrates:

- tool calling
- retrieval
- task decomposition
- evidence citation
- human approval
- fallback handling
- testable evaluation

The first version is a **demo-level controllable simulation system**, not a full league prediction engine.

## Core Capabilities

| Capability | Description |
|---|---|
| tool calling | The agent invokes deterministic backend tools (cap, roster, rules, evidence) instead of computing results itself. |
| retrieval | Evidence notes and historical context are retrieved and cited by `evidence_id`. |
| task decomposition | The offseason goal is broken into load cap -> load roster -> analyze needs -> find targets -> simulate -> validate -> project -> brief. |
| evidence citation | Every proposal references `evidence_ids` so a human can trace the rationale. |
| human approval | No transaction is applied until a human explicitly approves. |
| fallback handling | Missing data, full roster, cap mismatch, etc. trigger structured fallbacks rather than silent failures. |
| testable evaluation | Pytest cases and metrics validate rule correctness and agent guardrails. |

## Agent Boundaries

The LLM/agent layer is an **advisor**, never a **mutator**.

- The LLM **must not** directly compute salary-cap legality. That is the job of `transaction_rule_engine`.
- The LLM **must not** directly modify roster, contract, or salary state.
- The LLM **may only** call backend tools, organize proposals, and explain risks/rationale.
- Every signing/trade **must** pass deterministic backend validation (`transaction_rule_engine`).
- Every proposal **must** wait for explicit human approval before any state change.

## MVP Scope

- 3 demo teams.
- Local demo data for contracts, free agents, and evidence notes.
- Signing simulation.
- Simple two-team trade simulation.
- Salary risk hints.
- Depth chart projection.
- Structured agent brief (JSON).

## Non-Goals

- Not a full-league real-world prediction.
- No real-time scraping of every salary site.
- No complete reimplementation of the NBA CBA.
- Simulated trades are **not** real news and must not be presented as such.

> This is a simulation/planning tool, not a source of confirmed NBA transactions.

## Roadmap

| Milestone | Focus |
|---|---|
| M0 | Project skeleton, placeholder files, boundary docs (this commit). |
| M1 | Cap Sheet Model (`SalaryCapConfig`, `TeamCapSheet`, `PlayerContract`). |
| M2 | Transaction Rule Engine (signing/trade legality validation). |
| M3 | Roster / Target / Projection services (roster need, FA pool, trade sim, depth chart, evidence). |
| M4 | Offseason Agent (task decomposition, tool orchestration, structured brief, evaluation/fallback). |
| M5 | Frontend Simulator (cap sheet panel, plan card, depth chart, evidence, approval controls). |
| M6 | Evaluation (metrics + pytest harness). |

> Status note: M0–M4-D are implemented as a deterministic local backend.
> The project has **not** called any LLM, has **not** connected to MCP,
> and has **not** connected to the real NBA API or any live salary data
> source. All players / contracts / free agents / evidence notes are
> demo/sample/simulation JSON.

## Repository Layout

```
FrontOffice-Offseason-Agent/
backend/
  app/
    main.py
    models/        # cap, roster, transaction, evidence
    services/      # cap_sheet, rule_engine, roster_need, free_agent, trade_sim, depth_chart, evidence, offseason_agent
    tests/         # cap, rule engine, agent, guardrails, m0 skeleton smoke test
frontend/
  app/offseason/   # page.tsx
  components/      # CapSheetPanel, TransactionPlanCard, DepthChartPreview, EvidencePanel, ApprovalControls
data/              # cap_config, teams, players, contracts, free_agents, evidence_notes (demo/sample/simulation JSON)
docs/              # architecture, agent-workflow, evaluation
```

## Status

M1 implemented: deterministic `cap_sheet_service` loads `SalaryCapConfig`
from `data/cap_config.json`, builds immutable `TeamCapSheet` objects from
`data/teams.json` + `data/contracts.json`, computes `CapSheetSummary`
(`total_salary`, `cap_space`, `tax_distance`, `first_apron_distance`,
`second_apron_distance`), and exposes a pure `apply_signing_preview`
that returns a new sheet without mutating the input. No LLM, no state
writes, no transaction legality logic (that is M2).

M2 implemented: deterministic `transaction_rule_engine` validates
demo-level signings (`MINIMUM_SIGNING`, `MLE_SIGNING`,
`SIMPLE_FA_SIGNING`) and simple two-team trades against MVP rules
(salary caps, MLE/minimum thresholds, roster slot limits, simplified
salary matching `incoming <= outgoing * 1.25 + 100_000`, apron
warnings). Returns a structured `ValidationResult` with `status`
(`PASS` / `WARNING` / `FAIL`), `is_valid`, `issues`, `warnings`,
`cap_summary_before`/`after`, `evidence_ids`, `requires_human_approval`
(always `True`), and `limitations`. This is **not** a complete NBA CBA
implementation; apron hard caps are warnings only. The engine never
mutates `data/contracts.json` or any roster state.

M3-A implemented: deterministic `roster_need_service` and
`depth_chart_projector`. `roster_need_service` loads demo players from
`data/players.json` (enriched with contract_id/salary from
`data/contracts.json`), computes per-position counts vs a heuristic
target (2 per position), and returns a `RosterNeedReport` with
`needs` (sorted by priority high→medium), `strengths`, and MVP
`limitations`. `depth_chart_projector` builds a `ProjectedDepthChart`
with one `DepthChartSlot` per position (PG/SG/SF/PF/C), where the
first player at each position is the starter, the rest are backups,
and `need_level` is `high` (empty) / `medium` (1 player) / `low` (2+).
No LLM, no proposals, no roster state writes.

M3-B implemented: deterministic `free_agent_service` and
`trade_simulator`. `free_agent_service` reads demo free agents from
`data/free_agents.json`, joins them with `evaluate_roster_needs`, and
returns `FreeAgentFit` candidates scored by position match, role
keyword, and salary affordability (deterministic, sorted by
`fit_score` desc then `free_agent_id` asc). It does NOT call
`transaction_rule_engine` and does NOT generate `SigningTransaction`
objects — it only *suggests* candidates. `trade_simulator` exposes
`preview_signing` / `preview_trade` / `preview_transaction`, each of
which ALWAYS calls `transaction_rule_engine.validate_transaction`
first; on FAIL it returns a `TransactionPreview` with
`roster_need_after`/`depth_chart_after` set to `None` and a fallback
note in `limitations` (never approved); on PASS it builds an in-memory
preview roster and computes the post-transaction `RosterNeedReport`
and `ProjectedDepthChart` via M3-A projectors. Every preview has
`requires_human_approval=True`. No LLM, no disk writes, no real NBA
data — all salaries/contracts/free agents are demo/sample/simulation
JSON. This is **not** a complete NBA trade simulator; multi-year
contract decay, Bird rights, and sign-and-trade rules are deferred.

M4-A implemented: deterministic `evidence_service` and `EvidenceNote` /
`EvidenceBundle` / `EvidenceQuery` models. `evidence_service` loads
DEMO/SAMPLE/SIMULATION evidence notes from `data/evidence_notes.json`
and returns structured `EvidenceBundle` objects via three entry points:
`get_evidence_by_ids` (exact id lookup, reports `missing_evidence_ids`
+ `fallback_reason`), `search_evidence` (deterministic scoring by
team_id / player_id / topics / lowercase query token overlap, sorted
by score desc then `evidence_id` asc, `limit` applied), and
`build_evidence_bundle` (dispatches to id lookup when `evidence_ids`
is non-empty, else facet search). When evidence is missing, returns
empty `matched_notes` + clear `fallback_reason` — it NEVER fabricates
notes. Every note/bundle is `sample_data=True`. No LLM, no network, no
disk writes, no calls to `transaction_rule_engine`, no proposal
generation. This is the **evidence foundation** for the M4-B offseason
agent.

M4-B implemented: deterministic local `offseason_agent` tool
orchestrator. `run_offseason_plan(goal)` runs a fixed sequence of
internal tool calls — `cap_sheet_service.summarize_cap_sheet` →
`roster_need_service.evaluate_roster_needs` →
`depth_chart_projector.project_current_depth_chart` →
`free_agent_service.rank_free_agents_for_team` (filtered by
`target_positions` / `max_salary` / `max_candidates`) →
`trade_simulator.preview_signing` (per top fit) →
`evidence_service.search_evidence` + `get_evidence_by_ids` — and
returns a structured `OffseasonAgentRun` with a full `tool_call_trace`
(one `ToolCallRecord` per call, recording `tool_name`, `status`
`SUCCESS`/`FALLBACK`/`FAILED`, `input_summary`, `output_summary`,
`fallback_reason`, `evidence_ids`). Every signing preview has
`requires_human_approval=True`; the run itself has
`requires_human_approval=True` and `sample_data=True`. On tool failure
the orchestrator records a `FAILED`/`FALLBACK` trace entry and
continues (unless `team_id` is unknown, which fails the run). This is
**not** an MCP server, **not** an MCP client, **not** an LLM agent,
and **not** an OpenAI function-calling harness — it is a purely
deterministic local tool registry/orchestrator. No LLM, no network,
no disk writes, no real NBA data. The final natural-language
proposal/brief output is deferred to M4-C.

M4-C implemented: deterministic `proposal_builder` that converts an
M4-B `OffseasonAgentRun` into a frontend-friendly
`StructuredProposal`. `build_structured_proposal(agent_run)` produces
a stable, immutable proposal object with `proposal_id`, `status`
(`RECOMMENDED` / `PARTIAL` / `BLOCKED` / `NO_ACTION`),
`recommended_actions` (each a `ProposalAction` with
`action_type` `SIGNING` / `TRADE` / `HOLD`, `validation_status`,
`is_valid`, `cap_impact_summary`, `roster_impact_summary`,
`depth_chart_impact_summary`, `evidence_ids`,
`requires_human_approval=True`), `risks` (each a `ProposalRisk` with
`code` / `level` / `summary` — e.g. `evidence_missing`,
`validation_failed`, `no_matching_candidate`, `cap_pressure`,
`sample_data`), `evidence_refs` (flattened from the bundle's
`matched_notes`, never fabricated), `tool_call_trace` (echoed from
the agent run), short deterministic `cap_summary` /
`roster_need_summary` / `depth_chart_summary` strings,
`fallback_reasons`, and `limitations`. The builder does NOT call any
LLM, does NOT use MCP, does NOT call `transaction_rule_engine` or
`trade_simulator` directly, and does NOT write to disk. Every action
is a preview that requires human approval. The convenience wrapper
`run_goal_and_build_proposal(goal)` runs `run_offseason_plan` then
`build_structured_proposal`. Natural-language polish / LLM output is
deferred to a later milestone.

M4-D implemented: deterministic `proposal_evaluator` that evaluates a
M4-C `StructuredProposal` for safety, completeness, and
trustworthiness — it does NOT generate new proposals and does NOT
approve transactions. `evaluate_structured_proposal(proposal)` returns
a `ProposalEvaluation` with `status` (`PASS` / `WARNING` / `FAIL`),
`issues` (each an `EvaluationIssue` with `code` / `severity` /
`summary` / `remediation`, e.g. `missing_human_approval`,
`approved_without_validation`, `invalid_action_recommended`,
`missing_tool_trace`, `missing_evidence`, `sample_data_only`,
`no_action_fallback`, `no_mutation_guardrail`,
`missing_risk_for_fallback`, `non_deterministic_output`),
`passed_checks`, `failed_checks`, `warnings`, `limitations`, and
`sample_data=True`. Checks cover: human-approval guardrail (proposal
+ every action must have `requires_human_approval=True`),
validation guardrail (FAIL validations must not appear as valid
recommended actions), evidence guardrail (no fabricated evidence,
empty `evidence_refs` on a `RECOMMENDED` proposal is a WARNING),
tool-trace guardrail (the six key tools must appear in
`tool_call_trace`), fallback consistency (`NO_ACTION` must carry a
`HOLD` action or `no_matching_candidate` risk; `fallback_reasons`
must be backed by a risk or limitation), sample-data guardrail
(`sample_data=True` is required and recorded as an INFO issue), and
determinism (scenario outputs are reproducible).
`run_evaluation_scenario(scenario)` and
`run_default_evaluation_scenarios()` run a fixed set of 4 demo
scenarios end-to-end (`success_center_signing`,
`strict_budget_no_action`, `broad_need_multiple_candidates`,
`evidence_fallback_case`) as a regression suite. The evaluator does
NOT call any LLM, does NOT use MCP, does NOT call
`transaction_rule_engine` or `trade_simulator`, does NOT write to
disk, and does NOT change the proposal's status to "approved". The
convenience wrapper `run_goal_and_build_proposal` is used inside the
scenario runner because the scenario suite evaluates the full
end-to-end system; `evaluate_structured_proposal` itself only
consumes a `StructuredProposal`.
