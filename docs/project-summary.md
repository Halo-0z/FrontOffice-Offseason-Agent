# Project Summary

A short, review-friendly overview of `FrontOffice-Offseason-Agent`.
Intended for portfolio / resume / project-introduction use. For the
full technical picture, see
[README.md](../README.md) and
[docs/architecture.md](architecture.md). See
[docs/final-release-snapshot.md](final-release-snapshot.md) for the
final release snapshot.

## Project name

**FrontOffice-Offseason-Agent** — a deterministic NBA offseason
front-office decision workflow demo.

## Problem statement

Building an "agentic" workflow is easy to claim but hard to verify.
Most demos either (a) let an LLM compute cap legality itself (unsafe),
(b) skip evidence citation (untraceable), or (c) silently fail when
data is missing (untrustworthy).

This project builds a **controllable, testable agentic decision
workflow** for the NBA offseason domain, where:

- The agent **advises** but never **mutates**.
- Every transaction is **validated** by a deterministic rule engine.
- Every proposal is **grounded** in cited evidence.
- Every output is a **preview** awaiting human approval.
- Every failure is a **structured fallback**, not a silent success.

The domain is intentionally rich enough to exercise real agentic
patterns (tool calling, retrieval, decomposition, evidence citation,
fallback handling) but bounded enough to be fully deterministic and
testable on a single machine with no external services.

## Core workflow

```
OffseasonGoal
  -> run_offseason_plan            (deterministic tool orchestrator)
  -> StructuredProposal            (actions + risks + evidence refs)
  -> ProposalEvaluation            (guardrails + fallback checks)
  -> CLI viewer                    (text brief | JSON payload)
  -> human approval gate           (deferred — no auto-approval)
```

Each step is **pure** with respect to its input and is covered by
deterministic pytest cases.

## Key modules

| Module | Responsibility |
|---|---|
| `cap_sheet_service` | Loads demo cap config + team contracts; computes cap space, aprons, exceptions; pure `apply_signing_preview`. |
| `transaction_rule_engine` | Deterministic validation of signings (`MINIMUM` / `MLE` / `SIMPLE_FA`) and two-team trades (salary matching, roster limits, apron warnings). Always returns `requires_human_approval=True`. |
| `roster_need_service` | Loads demo players, computes per-position counts vs a heuristic target (2 per position), returns `RosterNeedReport` with `needs` / `strengths`. |
| `depth_chart_projector` | Builds `ProjectedDepthChart` with one slot per position (PG/SG/SF/PF/C); starter + backups; `need_level` high/medium/low. |
| `free_agent_service` | Reads demo free agents, joins with roster needs, returns `FreeAgentFit` candidates scored by position / role / salary affordability. Does NOT validate transactions. |
| `trade_simulator` | Previews signings / trades; always calls `transaction_rule_engine.validate_transaction` first. On FAIL returns a fallback preview; on PASS computes post-transaction roster need + depth chart in memory. |
| `evidence_service` | Loads demo evidence notes; supports id lookup + facet search (team / player / topics / query). Never fabricates notes; missing evidence becomes a `fallback_reason`. |
| `offseason_agent` | Deterministic tool orchestrator (`run_offseason_plan`). Runs a fixed tool sequence, records a `ToolCallRecord` per call, returns an `OffseasonAgentRun` with `tool_call_trace`. |
| `proposal_builder` | Converts an `OffseasonAgentRun` into a `StructuredProposal` (status / actions / risks / evidence_refs / fallback_reasons / limitations). Pure — does not re-run tools. |
| `proposal_evaluator` | Evaluates a `StructuredProposal` for safety / completeness / trustworthiness. Returns `ProposalEvaluation` (PASS / WARNING / FAIL + issues). Does NOT approve transactions. |
| `proposal_viewer` + CLI | Display layer. `format_proposal_brief` renders text; `build_demo_payload` returns a stable JSON dict; `backend/scripts/run_offseason_demo.py` exposes the full pipeline as a CLI. |

## Agentic features

- **Tool orchestration** — `offseason_agent.run_offseason_plan`
  invokes six backend tools in a fixed order and records a
  `tool_call_trace` per run.
- **Structured trace** — every `ToolCallRecord` carries `tool_name`,
  `status` (`SUCCESS` / `FALLBACK` / `FAILED`), `input_summary`,
  `output_summary`, `fallback_reason`, `evidence_ids`. The trace is
  part of the proposal, so a human can audit the run.
- **Evidence-grounded output** — proposals cite `evidence_id`s;
  missing evidence is reported as a `fallback_reason`, never
  fabricated. Every evidence ref carries `sample_data=True`.
- **Validation guardrails** — every signing / trade preview goes
  through `transaction_rule_engine.validate_transaction`. The agent
  never declares a transaction valid on its own. The evaluator FAILs
  any proposal where a `FAIL` validation appears as a valid
  recommended action.
- **Fallback handling** — missing data, full roster, cap mismatch,
  or no matching candidate produce a structured `fallback_reason`
  and a `HOLD` action. The evaluator FAILs a `RECOMMENDED` proposal
  with no candidates (`no_action_fallback`).
- **Deterministic evaluation** — the evaluator runs 4 fixed demo
  scenarios end-to-end as a regression suite. Scenario outputs are
  reproducible: two consecutive runs produce equal results.
- **Human approval boundary** — `requires_human_approval=True` is
  enforced on the proposal, on every action, and on every preview.
  No layer in the system ever sets a proposal's status to `APPROVED`.

## Testing / verification

The project is fully test-driven. The current regression suite:

```powershell
cd D:\FrontOffice-Offseason-Agent
D:\anaconda\python.exe -m pytest backend/app/tests
```

- **~325 tests passing** (deterministic, no network).
- **No-mutation checks** — `data/players.json`, `data/contracts.json`,
  `data/free_agents.json`, `data/evidence_notes.json` are byte-identical
  before and after every service / viewer / CLI run.
- **Determinism checks** — two consecutive runs of the same scenario
  produce identical `StructuredProposal`, `ProposalEvaluation`, and
  CLI stdout (text and JSON).
- **CLI text / JSON checks** — the CLI default run, strict-budget run,
  JSON run, and unknown-team run all behave as expected (exit codes,
  output content, output structure).
- **Guardrail checks** — every service module is verified to have no
  `openai` / `llm` / `anthropic` / `mcp` attributes; every preview is
  verified to have `requires_human_approval=True`; the viewer and
  evaluator are verified to not approve transactions.

See [docs/evaluation.md](evaluation.md) for the full test inventory
and [docs/demo-runbook.md](demo-runbook.md) for the canonical demo
path.

## Boundaries

- **Sample data** — 3 demo teams, a small free-agent pool, a small
  evidence note pool. Not real NBA data.
- **No LLM / MCP / API** — the project has not called any LLM, has
  not connected to MCP, and has not connected to the real NBA API or
  any live salary data source.
- **Preview only** — every output is a preview that requires a human
  to approve outside the system.
- **Human approval required** — no transaction is ever applied
  automatically.
- **Simplified CBA** — minimum / MLE / simple-FA signings and
  simplified two-team trade salary matching. Apron hard caps are
  warnings only. Bird rights, sign-and-trade, and multi-year contract
  decay are deferred.

## Next possible extensions

These are **not** implemented and **not** promised; they are the
natural next steps if the project continues:

- **Real data ingestion adapter** — a read-only adapter that loads
  real NBA salary / roster data from a licensed source, behind the
  same service interfaces. The deterministic core would not change.
- **Frontend viewer** — a Next.js / React UI that renders the JSON
  payload from `build_demo_payload` (cap sheet panel, plan card,
  depth chart, evidence panel, approval controls). The CLI viewer
  already produces the JSON contract for this.
- **Trade proposal expansion** — multi-team trades, sign-and-trade,
  Bird rights, draft-pick consideration. The rule engine is the
  place this would land.
- **Optional LLM polish layer** — a natural-language rationale /
  risk-note writer that runs **after** the deterministic proposal +
  evaluation are built. It would only consume the `StructuredProposal`
  + `ProposalEvaluation` and emit prose; it would not change status,
  not approve, and not call any backend tool.
- **Optional MCP integration** — exposing the existing deterministic
  tools as MCP tools, so an external MCP-compatible client could call
  them. This would only happen **after** the internal tool contracts
  are stable, and would not change the deterministic core.

Each extension would preserve the existing guardrails: the agent
advises, the rule engine validates, the human approves.
