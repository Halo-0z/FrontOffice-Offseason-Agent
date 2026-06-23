# Final Release Snapshot

This document is the **final release snapshot** for
`FrontOffice-Offseason-Agent`. It is the canonical "what is this
project, what does it do, and how do I verify it" reference for
reviewers, instructors, interviewers, and GitHub readers.

For the step-by-step demo path, see
[docs/demo-runbook.md](demo-runbook.md). For the short project
overview, see [docs/project-summary.md](project-summary.md). For the
submission checklist, see [docs/submission-checklist.md](submission-checklist.md).

## Project name

**FrontOffice-Offseason-Agent** — a deterministic NBA offseason
front-office decision workflow demo.

## Release status

- **Release line**: M5-D final release snapshot.
- **Base commit**: this snapshot is built on top of M5-C
  (`e20b9c7 Add M5-C docs consistency cleanup`, tag
  `m5c-docs-consistency-cleanup`).
- **Test status**: `325 passed` (deterministic, no network).
- **Working tree**: clean at the time of this snapshot (no uncommitted
  backend / tests / data changes).
- **Scope**: this release line (M0 → M5-D) is a **deterministic local
  backend + CLI demo**. It is **not** a frontend, **not** an MCP
  server/client, **not** an LLM agent, and **not** a real NBA data
  source.

## What this project is

`FrontOffice-Offseason-Agent` is a deterministic NBA offseason
front-office decision workflow demo. It chains salary cap, roster
needs, free-agent matching, transaction validation, evidence
retrieval, structured proposal, evaluation guardrails, and a CLI
viewer into a single testable workflow.

This is a **simulation / planning tool**. It is **not** a confirmed
NBA transaction source, **not** a real-world prediction system, and
**not** a source of real NBA news. Every player / contract / free
agent / evidence note is demo / sample / simulation JSON. Every
transaction output is a **preview** that requires explicit human
approval — no transaction is ever applied automatically.

## Final workflow

The end-to-end deterministic workflow:

```
OffseasonGoal
  -> run_offseason_plan            (M4-B: deterministic tool orchestrator)
       cap_sheet_service -> roster_need_service -> depth_chart_projector
       -> free_agent_service -> trade_simulator.preview_signing
       -> evidence_service
       -> OffseasonAgentRun (with tool_call_trace)
  -> build_structured_proposal     (M4-C: proposal builder)
       -> StructuredProposal (status / actions / risks / evidence_refs)
  -> evaluate_structured_proposal  (M4-D: evaluation guardrails)
       -> ProposalEvaluation (PASS / WARNING / FAIL + issues)
  -> format_proposal_brief         (M5-A: CLI viewer, display only)
       -> text brief  |  JSON payload
  -> human approval gate           (deferred — no auto-approval anywhere)
```

Each layer is **pure** with respect to its input:

- `proposal_builder` does not re-run tools or re-validate transactions.
- `proposal_evaluator` does not approve transactions or change the
  proposal's status.
- `proposal_viewer` does not re-build or re-evaluate; it only formats
  existing data.

## What is implemented

- **Local demo data loading** — `data/teams.json`,
  `data/players.json`, `data/contracts.json`, `data/free_agents.json`,
  `data/evidence_notes.json` (all sample / simulation JSON, never
  mutated by code).
- **Cap sheet summary** — `cap_sheet_service` loads cap config + team
  contracts, computes cap space / aprons / exceptions, pure
  `apply_signing_preview`.
- **Transaction validation** — `transaction_rule_engine` validates
  minimum / MLE / simple-FA signings and two-team trades (salary
  matching, roster limits, apron warnings). Always returns
  `requires_human_approval=True`.
- **Roster need evaluation** — `roster_need_service` computes
  per-position counts vs a heuristic target, returns `RosterNeedReport`
  with `needs` / `strengths`.
- **Depth chart projection** — `depth_chart_projector` builds
  `ProjectedDepthChart` with one slot per position (PG/SG/SF/PF/C);
  starter + backups; `need_level` high/medium/low.
- **Free agent matching** — `free_agent_service` reads demo free
  agents, joins with roster needs, returns `FreeAgentFit` candidates
  scored by position / role / salary affordability. Does NOT validate
  transactions.
- **Signing / trade preview** — `trade_simulator` previews signings /
  trades; always calls `transaction_rule_engine.validate_transaction`
  first. On FAIL returns a fallback preview; on PASS computes
  post-transaction roster need + depth chart in memory.
- **Local evidence retrieval** — `evidence_service` loads demo
  evidence notes; supports id lookup + facet search. Never fabricates
  notes; missing evidence becomes a `fallback_reason`.
- **Agent tool orchestration** — `offseason_agent.run_offseason_plan`
  runs a fixed tool sequence, records a `ToolCallRecord` per call,
  returns an `OffseasonAgentRun` with `tool_call_trace`.
- **Structured proposal JSON** — `proposal_builder` converts an
  `OffseasonAgentRun` into a `StructuredProposal` (status / actions /
  risks / evidence_refs / fallback_reasons / limitations).
- **Proposal evaluation** — `proposal_evaluator` evaluates a
  `StructuredProposal` for safety / completeness / trustworthiness.
  Returns `ProposalEvaluation` (PASS / WARNING / FAIL + issues).
- **CLI viewer** — `proposal_viewer` + `backend/scripts/run_offseason_demo.py`
  render the result as a human-readable text brief or a stable JSON
  payload.
- **Runbook / project summary / docs consistency cleanup** —
  `docs/demo-runbook.md`, `docs/project-summary.md`, and the M5-C
  docs consistency cleanup ensure the documentation matches the actual
  schema and method names.

## Agentic features

This is not a CRUD app. The workflow is an **agentic decision loop**
with hard guardrails:

- **Goal decomposition** — an `OffseasonGoal` is broken into a fixed
  sequence of tool calls (cap → roster → depth → FA → preview →
  evidence).
- **Deterministic tool orchestration** — `offseason_agent.run_offseason_plan`
  invokes backend tools in order and records a `ToolCallRecord` per
  call.
- **Structured `tool_call_trace`** — every run carries a full trace so
  a human can audit which tool was called, with what input, and what
  it returned.
- **Evidence-grounded output** — proposals cite `evidence_id`s via
  `evidence_refs`; missing evidence is reported as a `fallback_reason`,
  never fabricated.
- **Validation guardrails** — every signing / trade preview goes
  through `transaction_rule_engine.validate_transaction`; the agent
  never declares a transaction valid on its own. The evaluator FAILs
  any proposal where a `FAIL` validation appears as a valid
  recommended action.
- **Fallback handling** — missing data, full roster, cap mismatch, or
  no matching candidate produce a structured `fallback_reason` and a
  `HOLD` action instead of a silent failure.
- **Human approval boundary** — `requires_human_approval=True` is
  enforced on the proposal, on every action, and on every preview.
  The agent is an **advisor**, never a **mutator**.
- **Deterministic tests** — 325 pytest cases cover cap, rules, roster,
  depth, FA, trade, evidence, agent, proposal, evaluation, viewer, CLI,
  and guardrails. Same inputs always produce same outputs.

## Safety boundaries

The project enforces hard boundaries that are covered by
`backend/app/tests/test_agent_guardrails.py`:

- **No LLM** — no `openai` / `llm` / `anthropic` / `chat_completion`
  attributes on any service module.
- **No MCP** — no `mcp` / `mcp_client` / `mcp_server` / `MCPClient`
  attributes on any service module.
- **No external NBA API** — no network calls; all data is local JSON.
- **No external salary source** — no Spotrac / Basketball Reference /
  HoopsHype scraping.
- **Sample data only** — every proposal / evaluation / preview has
  `sample_data=True`.
- **Preview only** — every action has `requires_human_approval=True`;
  no transaction is ever applied.
- **No data mutation** — `data/players.json`, `data/contracts.json`,
  `data/free_agents.json`, `data/evidence_notes.json` are never
  written by any service, viewer, or CLI run (verified by no-mutation
  tests).
- **Requires human approval** — no transaction is ever applied
  automatically.
- **No transaction approval** — the viewer and evaluator do not
  approve transactions and do not change the proposal's status to
  "approved".

## Demo commands

Run from the repo root on Windows PowerShell. The project uses
`D:\anaconda\python.exe` (Python 3.12+).

```powershell
cd D:\FrontOffice-Offseason-Agent

# 1. Run the full test suite (deterministic, no network)
D:\anaconda\python.exe -m pytest backend/app/tests

# 2. Default demo: DEM-ATL, target C, max salary 20M
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py

# 3. Strict-budget demo: max salary 15M -> NO_ACTION / HOLD / fallback
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py --target-position C --max-salary 15000000 --max-candidates 2

# 4. Stable JSON payload for downstream tooling / future UI
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py --format json
```

The CLI prints to stdout and writes no files. Exit code is `0` on
success, non-zero on argument error or unknown team.

## Expected demo outputs

| Scenario | Command (abbreviated) | Expected result |
|---|---|---|
| Default recommendation | `run_offseason_demo.py` (no flags) | `proposal status: RECOMMENDED`, `evaluation status: PASS`, at least one `SIGNING` action |
| Strict-budget fallback | `--target-position C --max-salary 15000000 --max-candidates 2` | `proposal status: NO_ACTION`, `HOLD` action, `no_matching_candidate` risk, `fallback_reasons` listed |
| JSON payload | `--format json` | Stable sorted-keys JSON with `proposal` / `evaluation` / `actions` / `evidence` / `tool_trace` / `limitations` |
| Unknown team | `--team-id UNKNOWN-TEAM-XYZ` | Non-zero exit code, clear error mentioning known team ids |

All demo data is **sample / simulation JSON**, not real NBA data. The
output is a **preview**, not a prediction.

## Testing and verification

The canonical regression command (run from the repo root):

```powershell
D:\anaconda\python.exe -m pytest backend/app/tests
```

Expected: **325 passed**. A known Windows `PermissionError` from
pytest's atexit cleanup may appear after the session ends; it does
not affect test results.

Verification matrix:

| Check | Command (abbreviated) | Expected |
|---|---|---|
| Full test suite | `pytest backend/app/tests` | 325 passed |
| CLI default path | `run_offseason_demo.py` | exit 0, `RECOMMENDED` + `PASS` |
| CLI strict-budget fallback | `--target-position C --max-salary 15000000 --max-candidates 2` | exit 0, `NO_ACTION` + `HOLD` + `no_matching_candidate` |
| CLI JSON output | `--format json` | exit 0, valid sorted-keys JSON with all top-level keys |
| No-mutation | (one-liner comparing data files before/after) | `[True, True, True, True]` |
| Determinism | (one-liner comparing two JSON runs) | `True` |
| Docs consistency | (M5-C cleanup) | No stale method names or stale field names in docs |

## Milestone table

| Milestone | Focus | Tag |
|---|---|---|
| M0 | Project skeleton, placeholder files, boundary docs | `m0-project-skeleton` |
| M1 | Cap Sheet Model (`SalaryCapConfig`, `TeamCapSheet`, `PlayerContract`) | `m1-cap-sheet-model` |
| M2 | Transaction Rule Engine (signing / trade legality validation) | `m2-transaction-rule-engine` |
| M3-A | Roster need + depth chart foundation | `m3a-roster-depth-foundation` |
| M3-B | Free-agent matching + transaction preview | `m3b-free-agent-transaction-preview` |
| M4-A | Evidence retrieval foundation | `m4a-evidence-retrieval-foundation` |
| M4-B | Offseason agent tool orchestrator | `m4b-offseason-agent-tool-orchestrator` |
| M4-C | Structured proposal builder | `m4c-structured-proposal-builder` |
| M4-D | Proposal evaluation + fallback checks | `m4d-proposal-evaluation-fallback` |
| M5-A | Lightweight proposal viewer / CLI demo | `m5a-proposal-viewer-cli-demo` |
| M5-B | Project polish / demo runbook / README packaging | `m5b-project-polish-demo-runbook` |
| M5-C | Docs consistency cleanup | `m5c-docs-consistency-cleanup` |
| M5-D | Final release snapshot / submission package | (this milestone, docs-only) |

> Status note: M0–M5-C are implemented as a deterministic local
> backend. The project has **not** called any LLM, has **not**
> connected to MCP, and has **not** connected to the real NBA API or
> any live salary data source. All players / contracts / free agents /
> evidence notes are demo / sample / simulation JSON.

## Limitations

- **Demo / sample data** — 3 demo teams, a small free-agent pool, and a
  small evidence note pool. Not real NBA data.
- **Simplified CBA rules** — minimum / MLE / simple-FA signings and
  simplified two-team trade salary matching
  (`incoming <= outgoing * 1.25 + 100_000`). Apron hard caps are
  warnings only. Bird rights, sign-and-trade, and multi-year contract
  decay are deferred.
- **No live NBA data feed** — no real-time news, injuries, or rumor
  integration.
- **No frontend viewer yet** — the demo is the CLI script and the
  text / JSON brief. A Next.js / React UI is a future extension.
- **No external agent framework** — no LangChain / CrewAI / AutoGen.
  The orchestrator is a purely deterministic local tool registry.
- **No transaction execution system** — every output is a preview that
  requires a human to approve outside the system.

## Future extensions

These are **not implemented** and **not promised**; they are the
natural next steps if the project continues. Each would preserve the
existing guardrails: the agent advises, the rule engine validates, the
human approves.

- **Real data ingestion adapter** — a read-only adapter that loads
  real NBA salary / roster data from a licensed source, behind the
  same service interfaces. The deterministic core would not change.
- **Frontend viewer** — a Next.js / React UI that renders the JSON
  payload from `build_demo_payload` (cap sheet panel, plan card,
  depth chart, evidence panel, approval controls). The CLI viewer
  already produces the JSON contract for this.
- **Richer trade proposal generation** — multi-team trades,
  sign-and-trade, Bird rights, draft-pick consideration. The rule
  engine is the place this would land.
- **Optional LLM explanation layer** — a natural-language rationale /
  risk-note writer that runs **after** the deterministic proposal +
  evaluation are built. It would only consume the `StructuredProposal`
  + `ProposalEvaluation` and emit prose; it would not change status,
  not approve, and not call any backend tool.
- **Optional MCP integration** — exposing the existing deterministic
  tools as MCP tools, so an external MCP-compatible client could call
  them. This would only happen **after** the internal tool contracts
  are stable, and would not change the deterministic core.
