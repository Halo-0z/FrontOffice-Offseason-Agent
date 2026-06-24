# FrontOffice-Offseason-Agent

> A deterministic NBA offseason front-office decision workflow demo that
> chains cap sheets, roster needs, transaction validation, evidence
> retrieval, structured proposals, evaluation guardrails, and a CLI
> viewer.

`FrontOffice-Offseason-Agent` is a standalone project. It is **not** a
submodule of, and does **not** depend on, `DraftMind` or any other
existing repo. It does not reuse DraftMind code or data.

This is a **demo-level controllable simulation system**, not a
real-world trade predictor. It does not guarantee that any simulated
plan will actually happen, and it is **not** a source of confirmed NBA
transactions.

## What it does

Given a team's cap sheet, player contracts, roster needs, the
free-agent pool, and league transaction/signing rules, the system:

- loads demo cap / contracts / free-agent data from local JSON
- evaluates roster needs and the current depth chart
- ranks free-agent fits against positional needs and cap feasibility
- previews signing / trade actions through deterministic validation
- retrieves local sample evidence and attaches it to proposals
- builds a `StructuredProposal` (JSON-serializable, immutable)
- evaluates guardrails and fallback safety on the proposal
- renders a CLI text / JSON demo output for human review

Every output is a **preview** that requires explicit human approval
before any state change. No transaction is ever applied automatically.

## Why it is agentic

This is not a CRUD app. The workflow is an **agentic decision loop**
with hard guardrails:

- **Goal decomposition** — an `OffseasonGoal` is broken into a fixed
  sequence of tool calls (cap → roster → depth → FA → preview →
  evidence).
- **Deterministic tool orchestration** — `offseason_agent.run_offseason_plan`
  invokes backend tools in order and records a `ToolCallRecord` per
  call (`tool_name` / `status` / `input_summary` / `output_summary` /
  `fallback_reason` / `evidence_ids`).
- **Structured `tool_call_trace`** — every run carries a full trace so
  a human can audit which tool was called, with what input, and what
  it returned.
- **Evidence-grounded output** — proposals cite `evidence_id`s; missing
  evidence is reported as a fallback, never fabricated.
- **Rule validation** — every signing / trade preview goes through
  `transaction_rule_engine.validate_transaction`; the agent never
  declares a transaction valid on its own.
- **Fallback handling** — missing data, full roster, cap mismatch, or
  no matching candidate produce a structured `fallback_reason` and a
  `HOLD` action instead of a silent failure.
- **Human approval boundary** — `requires_human_approval=True` is
  enforced on the proposal, on every action, and on every preview.
  The agent is an **advisor**, never a **mutator**.

## Quick Start

Run from the repo root on Windows PowerShell. The project uses
`D:\anaconda\python.exe` (Python 3.12+).

### Install backend dependencies

```powershell
cd D:\FrontOffice-Offseason-Agent

# Minimal backend + API + test dependencies (no LLM, no MCP, no NBA API)
D:\anaconda\python.exe -m pip install -r requirements.txt
```

### Run the test suite

```powershell
# 1. Run the full test suite (deterministic, no network)
D:\anaconda\python.exe -m pytest backend/app/tests
```

### Run the CLI demos

```powershell
# 2. Default demo: DEM-ATL, target C, max salary 20M
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py

# 3. Strict-budget demo: max salary 15M -> NO_ACTION / HOLD / fallback
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py --target-position C --max-salary 15000000 --max-candidates 2

# 4. Stable JSON payload for downstream tooling / future UI
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py --format json

# 5. Trade preview demo (M6-D): two-team trade with salary matching + depth chart
D:\anaconda\python.exe backend/scripts/run_trade_preview_demo.py --format json
```

The CLI prints to stdout and writes no files. Exit code is `0` on
success, non-zero on argument error or unknown team.

### Run the backend API (M7-A)

```powershell
# Start the FastAPI dev server (read-only, sample data only)
D:\anaconda\python.exe -m uvicorn backend.app.api:app --reload
```

API endpoints (sample / simulation data — not real NBA data, not a
prediction, not an approved transaction):

| Method | Path | Description |
|---|---|---|
| GET | `http://127.0.0.1:8000/api/health` | Liveness probe (`status: ok`, `sample_data: true`) |
| GET | `http://127.0.0.1:8000/api/offseason/scenarios` | List the three demo scenarios |
| POST | `http://127.0.0.1:8000/api/offseason/proposal-preview` | Generate a proposal preview (wraps `build_demo_payload`) |
| GET | `http://127.0.0.1:8000/api/offseason/trade-preview-demo` | Fixed two-team trade preview (wraps `run_trade_preview_demo`) |

API boundaries:

- **Sample data only** — every response has `sample_data: true`.
- **No real NBA API** — no network calls; all data is local JSON.
- **No LLM / MCP** — the API does not call any LLM or MCP tool.
- **No data writes** — the API never mutates `data/` files.
- **Preview only** — every response has `requires_human_approval: true`;
  a `PASS` / `RECOMMENDED` status never approves a transaction.
- **No transaction execution** — the API never approves, executes, or
  persists a signing or trade.

## Demo Scenarios

| Scenario | Command (abbreviated) | Expected result |
|---|---|---|
| Default recommendation | `run_offseason_demo.py` (no flags) | `proposal status: RECOMMENDED`, `evaluation status: PASS`, at least one `SIGNING` action |
| Strict-budget fallback | `--target-position C --max-salary 15000000 --max-candidates 2` | `proposal status: NO_ACTION` (or `PARTIAL`), `HOLD` action, `no_matching_candidate` risk, fallback reasons listed |
| JSON payload | `--format json` | Stable sorted-keys JSON with `proposal` / `evaluation` / `actions` / `evidence` / `tool_trace` / `limitations` |
| Unknown team | `--team-id UNKNOWN-TEAM-XYZ` | Non-zero exit code, clear error mentioning known team ids |

All demo data is **sample / simulation JSON**, not real NBA data. The
output is a **preview**, not a prediction.

## Architecture Overview

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

See [docs/architecture.md](docs/architecture.md) for the full layered
diagram and per-service responsibilities, and
[docs/agent-workflow.md](docs/agent-workflow.md) for the standard
workflow and guardrails.

## Guardrails

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
- **No transaction approval** — the viewer and evaluator do not
  approve transactions and do not change the proposal's status to
  "approved".

## Current Status / Milestones

| Milestone | Focus | Status |
|---|---|---|
| M0 | Project skeleton, placeholder files, boundary docs | done (tag `m0-project-skeleton`) |
| M1 | Cap Sheet Model (`SalaryCapConfig`, `TeamCapSheet`, `PlayerContract`) | done (tag `m1-cap-sheet-model`) |
| M2 | Transaction Rule Engine (signing / trade legality validation) | done (tag `m2-transaction-rule-engine`) |
| M3-A | Roster need + depth chart foundation | done (tag `m3a-roster-depth-foundation`) |
| M3-B | Free-agent matching + transaction preview | done (tag `m3b-free-agent-transaction-preview`) |
| M4-A | Evidence retrieval foundation | done (tag `m4a-evidence-retrieval-foundation`) |
| M4-B | Offseason agent tool orchestrator | done (tag `m4b-offseason-agent-tool-orchestrator`) |
| M4-C | Structured proposal builder | done (tag `m4c-structured-proposal-builder`) |
| M4-D | Proposal evaluation + fallback checks | done (tag `m4d-proposal-evaluation-fallback`) |
| M5-A | Lightweight proposal viewer / CLI demo | done (tag `m5a-proposal-viewer-cli-demo`) |
| M5-B | Project polish / demo runbook / README packaging | done (tag `m5b-project-polish-demo-runbook`) |
| M5-C | Docs consistency cleanup | done (tag `m5c-docs-consistency-cleanup`) |
| M5-D | Final release snapshot / submission package | done (tag `m5d-final-release-snapshot`) |
| M6-A | Static frontend proposal viewer | this milestone (static viewer, sample data) |

> Status note: M0–M5-D are implemented as a deterministic local
> backend with a CLI demo. M6-A adds a **static** frontend viewer
> (sample data, no API calls). The project has **not** called any LLM,
> has **not** connected to MCP, and has **not** connected to the real
> NBA API or any live salary data source. All players / contracts /
> free agents / evidence notes are demo / sample / simulation JSON.

## Repository Layout

```
FrontOffice-Offseason-Agent/
backend/
  app/
    main.py
    models/        # cap, roster, transaction, evidence, agent, proposal, evaluation
    services/      # cap_sheet, rule_engine, roster_need, free_agent,
                   # trade_sim, depth_chart, evidence, offseason_agent,
                   # proposal_builder, proposal_evaluator, proposal_viewer
    tests/         # cap, rule engine, agent, guardrails, proposal, evaluation, viewer, CLI
  scripts/
    run_offseason_demo.py   # M5-A CLI demo
data/              # cap_config, teams, players, contracts, free_agents, evidence_notes
                   # (demo / sample / simulation JSON — never mutated by code)
docs/              # architecture, agent-workflow, evaluation, demo-runbook, project-summary
```

## Limitations

- **Demo / sample data** — 3 demo teams, a small free-agent pool, and a
  small evidence note pool. Not real NBA data.
- **Simplified CBA rules** — minimum / MLE / simple-FA signings and
  simplified two-team trade salary matching
  (`incoming <= outgoing * 1.25 + 100_000`). Apron hard caps are
  warnings only. Bird rights, sign-and-trade, and multi-year contract
  decay are deferred.
- **No live NBA transaction feed** — no real-time news, injuries, or
  rumor integration.
- **No official approval / execution system** — every output is a
  preview that requires a human to approve outside the system.
- **CLI viewer + static frontend viewer** — the CLI script
  (`backend/scripts/run_offseason_demo.py`) renders text / JSON briefs;
  the M6-A static frontend viewer (`frontend/app/offseason/page.tsx`)
  renders two demo scenarios (default recommendation + strict-budget
  fallback) from a static payload. The frontend does **not** call any
  backend API — it renders a snapshot of the CLI JSON output.
- **No LLM / MCP integration** — natural-language polish and MCP tool
  hosting are deferred to later milestones.

## Documentation

- [docs/architecture.md](docs/architecture.md) — layered architecture
  and per-service responsibilities.
- [docs/agent-workflow.md](docs/agent-workflow.md) — standard workflow,
  tool call trace, status derivation, guardrails, fallback handling.
- [docs/evaluation.md](docs/evaluation.md) — metrics, pytest cases, and
  CLI demo output checks.
- [docs/demo-runbook.md](docs/demo-runbook.md) — step-by-step demo
  runbook with expected results and known Windows notes.
- [docs/project-summary.md](docs/project-summary.md) — short project
  summary for review / portfolio / introduction.
- [docs/final-release-snapshot.md](docs/final-release-snapshot.md) —
  final release snapshot for the M5-D submission package.
- [docs/submission-checklist.md](docs/submission-checklist.md) —
  canonical "is the project ready to submit" gate.

## Non-Goals

- Not a full-league real-world prediction.
- No real-time scraping of every salary site.
- No complete reimplementation of the NBA CBA.
- Simulated trades are **not** real news and must not be presented as
  such.

> This is a simulation/planning tool, not a source of confirmed NBA transactions.
