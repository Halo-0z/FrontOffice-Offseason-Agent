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
| M4 | Offseason Agent (task decomposition, tool orchestration, structured brief). |
| M5 | Frontend Simulator (cap sheet panel, plan card, depth chart, evidence, approval controls). |
| M6 | Evaluation (metrics + pytest harness). |

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
