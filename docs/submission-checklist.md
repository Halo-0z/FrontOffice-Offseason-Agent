# Submission Checklist

This checklist is the canonical "is the project ready to submit"
gate. Run every command and inspect every field before tagging a
release or handing the project to a reviewer.

For the final release snapshot, see
[docs/final-release-snapshot.md](final-release-snapshot.md). For the
step-by-step demo path, see [docs/demo-runbook.md](demo-runbook.md).

## Before submission

All of the following must be true before the project is considered
submittable:

- [ ] `git status --short` is empty (working tree clean).
- [ ] `D:\anaconda\python.exe -m pytest backend/app/tests` reports
      `325 passed` (no failures, no errors).
- [ ] CLI default demo runs with exit code `0` and prints
      `proposal status: RECOMMENDED` + `evaluation status: PASS`.
- [ ] CLI strict-budget fallback demo runs with exit code `0` and
      prints `proposal status: NO_ACTION` + a `HOLD` action + a
      `no_matching_candidate` risk.
- [ ] CLI JSON demo runs with exit code `0` and emits valid JSON with
      top-level keys `proposal` / `evaluation` / `actions` / `evidence`
      / `tool_trace` / `limitations`.
- [ ] No-mutation check returns `[True, True, True, True]` (the 4 data
      files are byte-identical before and after a CLI run).
- [ ] Determinism check returns `True` (two consecutive JSON runs
      produce byte-identical stdout).
- [ ] README.md links to `docs/architecture.md`,
      `docs/agent-workflow.md`, `docs/evaluation.md`,
      `docs/demo-runbook.md`, `docs/project-summary.md`,
      `docs/final-release-snapshot.md`, and
      `docs/submission-checklist.md`, and all links resolve.
- [ ] `docs/demo-runbook.md` exists and its commands match the actual
      CLI flags.
- [ ] `docs/project-summary.md` exists and its module list matches the
      actual services in `backend/app/services/`.
- [ ] `docs/final-release-snapshot.md` exists and its milestone table
      matches the actual git tags.

## Commands to run

Run from the repo root on Windows PowerShell:

```powershell
cd D:\FrontOffice-Offseason-Agent

# 1. Working tree must be clean
git status --short

# 2. Full deterministic test suite
D:\anaconda\python.exe -m pytest backend/app/tests

# 3. Default demo: RECOMMENDED + PASS
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py

# 4. Strict-budget fallback: NO_ACTION + HOLD + no_matching_candidate
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py --target-position C --max-salary 15000000 --max-candidates 2

# 5. JSON payload: stable sorted-keys JSON
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py --format json

# 6. No-mutation check: must print [True, True, True, True]
D:\anaconda\python.exe -c "from pathlib import Path; files=['data/players.json','data/contracts.json','data/free_agents.json','data/evidence_notes.json']; before={f:Path(f).read_text(encoding='utf-8') for f in files}; import subprocess, sys; subprocess.run([sys.executable, 'backend/scripts/run_offseason_demo.py'], check=True, capture_output=True, text=True); after={f:Path(f).read_text(encoding='utf-8') for f in files}; print([before[f] == after[f] for f in files])"

# 7. Determinism check: must print True
D:\anaconda\python.exe -c "import subprocess, sys; a=subprocess.run([sys.executable, 'backend/scripts/run_offseason_demo.py', '--format', 'json'], check=True, capture_output=True, text=True).stdout; b=subprocess.run([sys.executable, 'backend/scripts/run_offseason_demo.py', '--format', 'json'], check=True, capture_output=True, text=True).stdout; print(a == b)"
```

## What to inspect in the output

Regardless of scenario, a healthy submission must show all of the
following in the CLI output:

| Field | Where | Why it matters |
|---|---|---|
| `proposal status` | Header | `RECOMMENDED` / `PARTIAL` / `BLOCKED` / `NO_ACTION` — never `APPROVED`. |
| `evaluation status` | Header / Evaluation section | `PASS` / `WARNING` / `FAIL` — never `APPROVED`. |
| `requires_human_approval: True` | Header + every action | The agent never auto-approves. |
| `sample_data: True` | Header + every evidence ref | Output is demo data, not real NBA data. |
| `tool_call_trace` | Tool Trace section | All six key tools appear with `SUCCESS` / `FALLBACK` / `FAILED` status. |
| `evidence_refs` / `evidence_id` | Actions + Evidence section | Proposals cite evidence; missing evidence becomes a `fallback_reason`, never fabricated. |
| `fallback_reasons` | Fallback Reasons section | Empty on a clean run; non-empty on `NO_ACTION` / missing evidence / validation failure. |
| `limitations` | Limitations section | Always includes `No LLM call`, `No MCP`, `sample data`, `preview only`, `requires human approval`. |
| `validation_status` | Each action | `PASS` / `WARNING` / `FAIL` from `transaction_rule_engine`, not from the agent. |

If any of these are missing or show `APPROVED` / `False` for
`requires_human_approval` / `False` for `sample_data`, the submission
is broken and must not be tagged.

## Red flags

Stop and investigate immediately if any of the following appear during
the final docs / release phase:

- **Backend changed during final docs** — `git status --short` shows
  modified files under `backend/app/services/`,
  `backend/app/models/`, or `backend/scripts/`. M5-D is docs-only;
  backend changes are not allowed.
- **Tests changed during final docs** — `git status --short` shows
  modified files under `backend/app/tests/`. M5-D does not touch
  tests.
- **Data changed** — `git status --short` shows modified files under
  `data/`, or the no-mutation check returns anything other than
  `[True, True, True, True]`.
- **README claims real predictions** — README or any doc says the
  system "predicts" real NBA outcomes, "forecasts" real transactions,
  or is a "source of confirmed NBA transactions".
- **Docs claim LLM / MCP / API integration** — any doc says the
  project "uses LLM", "connects to MCP", "calls the NBA API", or
  "scrapes salary data".
- **CLI fails** — any of the three demo commands returns a non-zero
  exit code or prints an exception traceback.
- **Tests fail** — `pytest backend/app/tests` reports any failure or
  error.
- **git status dirty before final release** — `git status --short` is
  non-empty when the final release tag is about to be created.
- **Preview written as approved** — any doc or output shows a
  transaction with `requires_human_approval: False` or a proposal
  status of `APPROVED`.

If any red flag appears, fix it before submitting. Do not tag a
release with a red flag present.
