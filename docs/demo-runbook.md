# Demo Runbook

This runbook walks through running the `FrontOffice-Offseason-Agent`
demo on a clean checkout. It is the canonical "show me the project"
path for reviewers, contributors, and demos.

## Purpose

The demo proves the end-to-end deterministic backend works:

- An `OffseasonGoal` is decomposed into a fixed tool-call sequence.
- Each tool call is recorded in a `tool_call_trace`.
- A `StructuredProposal` is built with actions, risks, and evidence
  refs.
- A `ProposalEvaluation` checks guardrails (human approval, validation
  consistency, evidence, tool trace, fallback consistency, sample
  data).
- A CLI viewer renders the result as a human-readable text brief or a
  stable JSON payload.

The demo is **deterministic**: same inputs → same outputs, no network,
no LLM, no MCP, no disk writes.

## Prerequisites

- **OS**: Windows (PowerShell). The commands below use Windows paths.
- **Python**: `D:\anaconda\python.exe` (Python 3.12+). Other Python
  interpreters may work but are not tested.
- **Repo root**: `D:\FrontOffice-Offseason-Agent`. All commands assume
  this is the current working directory.
- **No external services**: no database, no LLM API key, no MCP server,
  no NBA API key. All data is local JSON under `data/`.

## Step 0 — Smoke test

Run the full deterministic test suite. This is the fastest way to
confirm the project is healthy on this machine.

```powershell
cd D:\FrontOffice-Offseason-Agent
D:\anaconda\python.exe -m pytest backend/app/tests
```

**Expected**: all tests pass (currently 325 passed). A known Windows
`PermissionError` from pytest's atexit cleanup may appear after the
test session ends — it does **not** mean tests failed, as long as
pytest reports `passed`.

## Step 1 — Default recommendation demo

Runs the default DEM-ATL scenario: target center, max salary $20M,
max 2 candidates.

```powershell
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py
```

**Expected output (text brief)**:

- Banner: `FrontOffice-Offseason-Agent | DEMO PREVIEW (sample data)`.
- Header: `team_id: DEM-ATL`, `objective: Add frontcourt help`,
  `proposal status: RECOMMENDED`, `evaluation status: PASS`,
  `requires_human_approval: True`, `sample_data: True`.
- `cap summary` / `roster need summary` / `depth chart summary` lines.
- `--- Recommended Actions (preview only) ---` section with at least
  one `SIGNING` action containing `player_name`, `position: C`,
  `salary`, `validation_status: PASS`, `is_valid: True`,
  `requires_human_approval: True`, `fit_score`, `matched_need`,
  `cap_impact`, `roster_impact`, `depth_chart_impact`, `evidence_ids`.
- `--- Risks ---` section (including `sample_data`).
- `--- Evidence ---` section with `evidence_id` / title / source /
  `sample_data: True`.
- `--- Tool Trace ---` section listing all six key tools
  (`cap_sheet_service`, `roster_need_service`,
  `depth_chart_projector`, `free_agent_service`,
  `trade_simulator.preview_signing`, `evidence_service`) with
  `status: SUCCESS` (or `FALLBACK`).
- `--- Evaluation ---` section with `status: PASS`, issue counts,
  passed checks.
- `--- Fallback Reasons ---` section (possibly empty).
- `--- Limitations ---` section including `No LLM call`, `No MCP`,
  `sample data`, `preview only`, `requires human approval`.

**Exit code**: `0`.

## Step 2 — Strict-budget fallback demo

Tightens the cap so no free agent fits. This exercises the fallback
path: `NO_ACTION` proposal, `HOLD` action, `no_matching_candidate`
risk.

```powershell
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py --target-position C --max-salary 15000000 --max-candidates 2
```

**Expected output (text brief)**:

- Header: `proposal status: NO_ACTION` (or `PARTIAL`),
  `evaluation status: PASS` (or `WARNING`).
- `--- Recommended Actions (preview only) ---` section contains a
  `HOLD` action (no `SIGNING` action with `is_valid: True`).
- `--- Risks ---` section contains a `no_matching_candidate` risk.
- `--- Fallback Reasons ---` section is non-empty (e.g. "no
  free-agent candidates after filtering").
- `--- Evaluation ---` section: `NO_ACTION` with a `HOLD` action or
  `no_matching_candidate` risk does **not** fail evaluation.

**Exit code**: `0`.

## Step 3 — JSON payload demo

Emits a stable, sorted-keys JSON payload suitable for downstream
tooling or a future UI.

```powershell
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py --format json
```

**Expected output (JSON)**:

- Valid JSON (parses with `json.loads`).
- Top-level keys (sorted): `actions`, `evaluation`, `evidence`,
  `limitations`, `proposal`, `requires_human_approval`,
  `sample_data`, `tool_trace`.
- `proposal` contains `proposal_id`, `status`, `team_id`,
  `objective`, `risks`, `evidence_refs`, `tool_call_trace`,
  `fallback_reasons`, `limitations`, `requires_human_approval: true`,
  `sample_data: true`.
- `evaluation` contains `status`, `issues`, `passed_checks`,
  `failed_checks`, `warnings`, `limitations`, `sample_data: true`.
- `actions` is a list of action dicts with `action_type`,
  `player_name`, `position`, `salary`, `validation_status`,
  `is_valid`, `requires_human_approval: true`, `fit_score`,
  `matched_need`, `evidence_ids`, `limitations`.
- `evidence` is a list of evidence refs with `evidence_id`, `title`,
  `source`, `sample_data: true`.
- `tool_trace` is a list of tool call records with `tool_name`,
  `status`, `input_summary`, `output_summary`, `fallback_reason`,
  `evidence_ids`.
- `limitations` lists MVP scope (no LLM, no MCP, sample data, preview
  only, requires human approval).

**Exit code**: `0`.

Two consecutive `--format json` runs produce byte-identical stdout
(verified by the determinism check in Step 6).

## Step 4 — Unknown team error path

Confirms the CLI fails loudly on an unknown team instead of producing
a fake proposal.

```powershell
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py --team-id UNKNOWN-TEAM-XYZ
```

**Expected**: non-zero exit code, clear error message on stderr
mentioning the known team ids (e.g. `DEM-ATL`, `DEM-BOS`,
`DEM-LAL`). No proposal is printed.

## Step 5 — No-mutation check

Confirms the CLI does not write to any data file.

```powershell
D:\anaconda\python.exe -c "from pathlib import Path; files=['data/players.json','data/contracts.json','data/free_agents.json','data/evidence_notes.json']; before={f:Path(f).read_text(encoding='utf-8') for f in files}; import subprocess, sys; subprocess.run([sys.executable, 'backend/scripts/run_offseason_demo.py'], check=True, capture_output=True, text=True); after={f:Path(f).read_text(encoding='utf-8') for f in files}; print([before[f] == after[f] for f in files])"
```

**Expected**: `[True, True, True, True]`.

## Step 6 — Determinism check

Confirms two consecutive JSON runs produce identical output.

```powershell
D:\anaconda\python.exe -c "import subprocess, sys; a=subprocess.run([sys.executable, 'backend/scripts/run_offseason_demo.py', '--format', 'json'], check=True, capture_output=True, text=True).stdout; b=subprocess.run([sys.executable, 'backend/scripts/run_offseason_demo.py', '--format', 'json'], check=True, capture_output=True, text=True).stdout; print(a == b)"
```

**Expected**: `True`.

## What to look for in the output

Regardless of scenario, a healthy demo output should always show:

| Field | Where | Why it matters |
|---|---|---|
| `proposal status` | Header | `RECOMMENDED` / `PARTIAL` / `BLOCKED` / `NO_ACTION` — never `APPROVED`. |
| `evaluation status` | Header / Evaluation section | `PASS` / `WARNING` / `FAIL` — never `APPROVED`. |
| `requires_human_approval: True` | Header + every action | The agent never auto-approves. |
| `sample_data: True` | Header + every evidence ref | Output is demo data, not real NBA data. |
| `tool_call_trace` | Tool Trace section | All six key tools appear with `SUCCESS` / `FALLBACK` / `FAILED` status. |
| `evidence_ids` / `evidence_id` | Actions + Evidence section | Proposals cite evidence; missing evidence becomes a fallback, never fabricated. |
| `fallback_reasons` | Fallback Reasons section | Empty on a clean run; non-empty on `NO_ACTION` / missing evidence / validation failure. |
| `limitations` | Limitations section | Always includes `No LLM call`, `No MCP`, `sample data`, `preview only`, `requires human approval`. |
| `validation_status` | Each action | `PASS` / `WARNING` / `FAIL` from `transaction_rule_engine`, not from the agent. |

If any of these are missing or show `APPROVED` / `False` for
`requires_human_approval` / `False` for `sample_data`, the demo is
broken and the test suite should be re-run.

## Expected results summary

| Step | Command (abbreviated) | Expected exit code | Expected headline result |
|---|---|---|---|
| 0 | `pytest backend/app/tests` | 0 | 325 passed |
| 1 | `run_offseason_demo.py` | 0 | `RECOMMENDED` + `PASS` |
| 2 | `--target-position C --max-salary 15000000 --max-candidates 2` | 0 | `NO_ACTION` (or `PARTIAL`) + `HOLD` + `no_matching_candidate` |
| 3 | `--format json` | 0 | Valid sorted-keys JSON with all top-level keys |
| 4 | `--team-id UNKNOWN-TEAM-XYZ` | non-zero | Clear error mentioning known team ids |
| 5 | no-mutation one-liner | 0 | `[True, True, True, True]` |
| 6 | determinism one-liner | 0 | `True` |

## Known Windows note

On Windows, pytest may print an `Exception ignored in atexit callback`
with a `PermissionError` on
`C:\Users\<user>\AppData\Local\Temp\pytest-of-<user>\pytest-current`
after the test session ends. This is a known pytest cleanup issue on
Windows and does **not** affect test results. As long as pytest
reports `N passed`, the run is healthy.

## Safety boundaries

The demo is bounded by the same guardrails as the rest of the project:

- **Sample data only** — all players / contracts / free agents /
  evidence notes are demo / simulation JSON. The output is **not** a
  real NBA prediction.
- **Preview only** — every action has `requires_human_approval=True`;
  no transaction is ever applied.
- **No LLM / MCP / external data** — the CLI does not call any LLM,
  does not use MCP, and does not touch the network.
- **No transaction approval** — the viewer and evaluator do not
  approve transactions and do not change the proposal's status to
  "approved".
- **No data mutation** — `data/players.json`, `data/contracts.json`,
  `data/free_agents.json`, `data/evidence_notes.json` are never
  written by the CLI or any service.

If a demo run appears to mutate a data file, approve a transaction,
or call out to the network, stop and re-run the test suite —
something is wrong.
