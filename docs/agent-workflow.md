# Agent Workflow

This document describes the standard offseason workflow the agent follows.

## Current Status (M5-B)

M5-B is a **docs-only polish / runbook / README packaging** milestone.
It does not add new backend features, does not change any service, and
does not change any test. It only polishes the project's external
documentation so the existing M0–M5-A deterministic backend is easy to
understand, run, and review.

The canonical demo path is now documented in
[docs/demo-runbook.md](demo-runbook.md). The short project overview is
in [docs/project-summary.md](project-summary.md). The README is
restructured into a clean project homepage with Quick Start, demo
scenarios, architecture overview, guardrails, milestones, and
limitations.

The deterministic backend itself is unchanged from M5-A:

```
OffseasonGoal
  -> run_offseason_plan            (M4-B: deterministic tool orchestrator)
  -> build_structured_proposal     (M4-C: proposal builder)
  -> evaluate_structured_proposal  (M4-D: evaluation guardrails)
  -> format_proposal_brief         (M5-A: CLI viewer, display only)
  -> human approval gate           (deferred — no auto-approval anywhere)
```

## Current Status (M5-A)

M5-A implements the **deterministic proposal viewer / CLI demo**
(`proposal_viewer.format_proposal_brief` +
`backend/scripts/run_offseason_demo.py`). The viewer consumes a M4-C
`StructuredProposal` and a M4-D `ProposalEvaluation` and formats them
into a human-readable text brief or a stable JSON-serializable dict.
It does NOT generate new proposals, does NOT approve transactions,
does NOT change the proposal's status to "approved", does NOT call
`transaction_rule_engine` or `trade_simulator`, does NOT call any
LLM, does NOT use MCP, and does NOT write to disk. The CLI script
`run_offseason_demo.py` accepts `--team-id` / `--objective` /
`--target-position` / `--max-salary` / `--max-candidates` /
`--evidence-query` / `--format text|json` and prints to stdout; it
writes no files.

This is **not** a frontend page, **not** an MCP server, **not** an
LLM agent, and **not** an OpenAI function-calling harness — it is a
purely deterministic display layer. No LLM, no network, no disk
writes.

Natural-language polish / LLM output is deferred to a later milestone.

## M4 Flow (implemented)

```
goal (OffseasonGoal)
  -> [M4-B] run_offseason_plan(goal)
       -> cap_sheet_service.summarize_cap_sheet(team_id)
       -> roster_need_service.evaluate_roster_needs(team_id)
       -> depth_chart_projector.project_current_depth_chart(team_id)
       -> free_agent_service.rank_free_agents_for_team(team_id)
            filtered by goal.target_positions / goal.max_salary / goal.max_candidates
       -> [for each top fit] trade_simulator.preview_signing(SigningTransaction)
            transaction_type picked conservatively:
              salary <= minimum_salary -> MINIMUM_SIGNING
              salary <= MLE            -> MLE_SIGNING
              otherwise                -> SIMPLE_FA_SIGNING
            every preview has requires_human_approval=True
       -> evidence_service.search_evidence(query, team_id)
          + evidence_service.get_evidence_by_ids(fit evidence_ids)
            merged into one EvidenceBundle (dedup by evidence_id)
       -> OffseasonAgentRun
            status: SUCCESS / PARTIAL / FAILED (derived from tool_call_trace)
            requires_human_approval: True (always)
            sample_data: True (always)
            limitations: MVP scope notes
            tool_call_trace: one ToolCallRecord per call
  -> [M4-C] build_structured_proposal(agent_run)
       -> derive ProposalStatus from agent_run.status + previews
       -> build ProposalAction per signing preview
            (transaction_id / validation_status / is_valid /
             player_name / position / fit_score / matched_need /
             cap_impact_summary / roster_impact_summary /
             depth_chart_impact_summary / evidence_ids /
             requires_human_approval=True)
       -> flatten EvidenceBundle.matched_notes -> ProposalEvidenceRef
            (never fabricate evidence ids)
       -> build ProposalRisk list
            (evidence_missing / validation_failed /
             no_matching_candidate / cap_pressure / sample_data)
       -> echo tool_call_trace from agent_run
       -> build short deterministic cap/roster/depth summaries
       -> collect fallback_reasons from trace + bundle
       -> StructuredProposal
            proposal_id: deterministic (team_id + slugified objective)
            requires_human_approval: True (always)
            sample_data: True (always)
            limitations: MVP scope notes
  -> [M4-D] evaluate_structured_proposal(proposal)
       -> check human-approval guardrail
            (proposal.requires_human_approval=True AND
             every ProposalAction.requires_human_approval=True)
       -> check validation guardrail
            (FAIL validations must not appear as valid recommended actions;
             RECOMMENDED with no valid action is WARNING/FAIL)
       -> check evidence guardrail
            (no fabricated evidence; empty evidence_refs on RECOMMENDED
             is WARNING; missing-evidence fallback without a risk is WARNING)
       -> check tool-trace guardrail
            (six key tools must appear in tool_call_trace)
       -> check fallback consistency
            (NO_ACTION must carry HOLD action or no_matching_candidate risk;
             fallback_reasons must be backed by a risk or limitation;
             no candidates but RECOMMENDED is FAIL)
       -> check sample-data guardrail
            (sample_data=True is required; recorded as INFO issue)
       -> ProposalEvaluation
            status: PASS / WARNING / FAIL (derived from issue severities)
            issues: list of EvaluationIssue (code / severity / summary / remediation)
            passed_checks / failed_checks / warnings / limitations
            sample_data: True (always)
       -> NOTE: evaluator does NOT approve transactions and does NOT
            change the proposal's ProposalStatus. It only emits issues.
  -> [M5-A] format_proposal_brief(proposal, evaluation)  /  CLI demo
       -> format header (team_id / objective / statuses /
            requires_human_approval / sample_data)
       -> format recommended actions (preview only)
       -> format risks / evidence refs / tool_call_trace
       -> format evaluation summary (status / issues / passed_checks)
       -> format fallback reasons / limitations
       -> NOTE: viewer does NOT approve transactions, does NOT call
            LLM/MCP, does NOT write to disk, does NOT re-build or
            re-evaluate the proposal. It only formats existing data.
  -> frontend / brief output
       (natural-language polish / LLM output deferred to a later milestone)
```

Each tool call in the M4-B run is wrapped in a try/except. On failure
the orchestrator records a `FAILED` `ToolCallRecord` and continues
(unless `team_id` is unknown, which is a critical failure). When a
tool returns an empty result (e.g. no free-agent candidates after
filtering), the trace records `FALLBACK` with a clear
`fallback_reason`.

The M4-C builder is **pure**: it does NOT re-run any tool, does NOT
call `transaction_rule_engine` or `trade_simulator` directly, and
does NOT write to disk. It only consumes the `OffseasonAgentRun`.

The M4-D evaluator is **pure**: it does NOT re-run any tool, does NOT
call `transaction_rule_engine` or `trade_simulator`, does NOT call
any LLM, does NOT use MCP, and does NOT write to disk. It only
consumes the `StructuredProposal`. The scenario runner
(`run_evaluation_scenario` / `run_default_evaluation_scenarios`) is
the only path that calls `run_goal_and_build_proposal`, because the
scenario suite is a regression test of the full end-to-end system.

The M5-A viewer is **pure**: it does NOT re-run any tool, does NOT
call `transaction_rule_engine` or `trade_simulator`, does NOT call
any LLM, does NOT use MCP, and does NOT write to disk. It only
formats existing `StructuredProposal` + `ProposalEvaluation` data.
The `build_demo_brief` / `build_demo_payload` convenience wrappers
call `run_goal_and_build_proposal` + `evaluate_structured_proposal`
to produce the proposal/evaluation, but `format_proposal_brief`
itself only consumes the already-built objects.

## M4-B Flow (implemented)

The M4-B portion of the M4 Flow above (from `goal` to
`OffseasonAgentRun`) is the deterministic core. Each tool call is
wrapped in a try/except. On failure the orchestrator records a
`FAILED` `ToolCallRecord` and continues (unless `team_id` is unknown,
which is a critical failure). When a tool returns an empty result
(e.g. no free-agent candidates after filtering), the trace records
`FALLBACK` with a clear `fallback_reason`.

### Tool Call Trace

Every `ToolCallRecord` contains:

| Field | Description |
|---|---|
| `tool_name` | Dotted name, e.g. `cap_sheet_service.summarize_cap_sheet`. |
| `status` | `SUCCESS` / `FALLBACK` / `FAILED`. |
| `input_summary` | Short deterministic string describing the input. |
| `output_summary` | Short deterministic string describing the output. |
| `fallback_reason` | `None` on SUCCESS; a clear string on FALLBACK/FAILED. |
| `evidence_ids` | Evidence ids produced or referenced by this call. |

### Run Status Derivation

- Any `FAILED` trace entry → `AgentRunStatus.FAILED`.
- Any `FALLBACK` trace entry (no FAILED) → `AgentRunStatus.PARTIAL`.
- Otherwise → `AgentRunStatus.SUCCESS`.

`SUCCESS` only means the orchestrator ran to completion — it does NOT
mean any transaction was approved. Every output is still a preview
that requires human approval.

## M4-C Proposal Status Derivation

The `proposal_builder` derives `ProposalStatus` from the agent run:

- `agent_run.status == FAILED` → `BLOCKED`.
- No fits and no previews → `NO_ACTION`.
- Previews exist but ALL failed validation → `BLOCKED`.
- At least one valid preview and `agent_run.status == SUCCESS` → `RECOMMENDED`.
- Otherwise (mixed valid/failed, or `agent_run.status == PARTIAL`) → `PARTIAL`.

`RECOMMENDED` only means the orchestrator ran cleanly and at least
one preview passed validation — it does NOT mean any transaction was
approved. Every action still has `requires_human_approval=True`.

## Standard Flow (target later milestones)

The M4 Flow above is the deterministic core. Later milestones will
add natural-language polish / LLM output on top of the
`StructuredProposal`. The full target flow:

1. **Receive team + offseason goal.** Input: `team_id`, `goal`.
2. **Load cap sheet.** `cap_sheet_service` → current cap space, aprons, exceptions.
3. **Analyze roster needs.** `roster_need_service` → positional/role shortfalls.
4. **Project current depth chart.** `depth_chart_projector` → current depth.
5. **Retrieve free-agent candidates.** `free_agent_service` filtered by needs, cap, and goal constraints.
6. **Preview signing actions.** `trade_simulator.preview_signing` per top fit (always validates via `transaction_rule_engine`).
7. **Retrieve supporting evidence.** `evidence_service.search_evidence` + `get_evidence_by_ids` → `EvidenceBundle`.
8. **Assemble structured run.** `OffseasonAgentRun` with `tool_call_trace`. **(Implemented in M4-B.)**
9. **Build structured proposal.** `StructuredProposal` with actions, risks, evidence refs. **(Implemented in M4-C.)**
10. **Evaluate proposal.** `proposal_evaluator.evaluate_structured_proposal` → `ProposalEvaluation` with `status` / `issues` / `passed_checks` / `failed_checks` / `warnings` / `limitations`. The evaluator does NOT approve transactions; it only emits issues and a PASS/WARNING/FAIL status. **(Implemented in M4-D.)**
11. **Format proposal brief / CLI demo.** `proposal_viewer.format_proposal_brief` → human-readable text brief; `run_offseason_demo.py` CLI exposes the full pipeline with `--format text|json`. The viewer only formats existing data; it does NOT approve transactions. **(Implemented in M5-A.)**
12. **Natural-language polish / LLM output.** Plan cards, rationale, risk notes. **(Deferred to a later milestone.)**
13. **Wait for human approval.** No state mutation until a human approves.

## Guardrails

- The agent **must not** write to cap/roster/contract state directly.
- The agent **must not** declare a transaction valid; only `transaction_rule_engine` can.
- The agent **must not** bypass `trade_simulator` (which calls `transaction_rule_engine` internally).
- The agent **must not** skip the human approval gate.
- The agent **must not** use MCP or call an LLM.
- If a required tool call fails or data is missing, the agent emits a **fallback** trace entry, not a silent success.
- The structured output **must** include all required fields; otherwise it is rejected upstream.
- The evaluator **must not** approve transactions or change the proposal's `ProposalStatus` to "approved" — it only emits issues and a PASS/WARNING/FAIL evaluation status.
- The evaluator **must not** call `transaction_rule_engine` or `trade_simulator`; it only consumes the `StructuredProposal`.
- The evaluator **must not** call any LLM, **must not** use MCP, and **must not** write to disk.
- The evaluator **must** FAIL any proposal missing `requires_human_approval=True` on the proposal or any action.
- The viewer **must not** approve transactions or change the proposal's `ProposalStatus` — it only formats existing data.
- The viewer **must not** call `transaction_rule_engine` or `trade_simulator`; it only consumes the `StructuredProposal` + `ProposalEvaluation`.
- The viewer **must not** call any LLM, **must not** use MCP, and **must not** write to disk.
- The CLI demo **must not** write output files; it prints to stdout only.
- The CLI demo output **must** mention `requires_human_approval` and `sample_data` so it is never mistaken for a real NBA prediction.

## Fallback Handling

| Trigger | Fallback |
|---|---|
| Missing contract data | Skip player, record `fallback_reason`, continue. |
| Roster full | Skip signing path, suggest trade-only or waive suggestion. |
| Cap space insufficient | Emit `cap_pressure` risk, suggest salary-dump trade. |
| Salary matching fails | Drop trade candidate, record `fallback_reason`. |
| Evidence missing | Record `fallback_reason`, emit `evidence_missing` risk, list in `limitations`. |
| Agent attempts direct mutation | Blocked by guardrail, test `test_agent_guardrails.py`. |

## Failure Paths (deterministic)

The workflow has three structured failure paths. Each produces a
deterministic, auditable output — never a silent success and never a
crash.

### No candidates -> NO_ACTION / HOLD / fallback

When `free_agent_service.rank_free_agents_for_team` returns no
candidates after filtering (e.g. `--max-salary 15000000` filters out
all centers), the M4-B orchestrator records a `FALLBACK`
`ToolCallRecord` with a clear `fallback_reason`. The M4-C builder
derives `ProposalStatus.NO_ACTION` (or `PARTIAL`) and emits a `HOLD`
`ProposalAction` plus a `no_matching_candidate` `ProposalRisk`. The
M4-D evaluator does **not** fail this proposal — a `NO_ACTION`
proposal with a `HOLD` action or a `no_matching_candidate` risk is a
valid fallback outcome. The M5-A viewer renders the `HOLD` action,
the `no_matching_candidate` risk, and the `fallback_reasons` section
so a human can see why no signing was proposed.

### Missing evidence -> fallback / risk

When `evidence_service.get_evidence_by_ids` cannot find a requested
`evidence_id`, it returns the id in `missing_evidence_ids` with a
clear `fallback_reason` — it never fabricates a note. The M4-C
builder surfaces missing ids in `fallback_reasons` and emits an
`evidence_missing` `ProposalRisk`. The M4-D evaluator emits a
`missing_risk_for_fallback` `WARNING` if a `fallback_reason` mentions
missing evidence but no risk backs it. The M5-A viewer renders the
`fallback_reasons` section and the `evidence_missing` risk so a human
can see exactly which evidence was not found.

### Validation failed -> issue / risk, no approval

When `transaction_rule_engine.validate_transaction` returns `FAIL`
for a signing or trade, `trade_simulator.preview_signing` returns a
`TransactionPreview` with `is_valid=False`,
`roster_need_after=None`, `depth_chart_after=None`, and a
"Validation failed" entry in `limitations` — the preview is never
approved. The M4-C builder emits a `ProposalAction` with
`validation_status="FAIL"`, `is_valid=False`, and a
`validation_failed` `ProposalRisk`; the proposal status becomes
`BLOCKED` (or `PARTIAL` if some actions pass). The M4-D evaluator
FAILs the proposal if a `FAIL` validation appears as a valid
recommended action (`approved_without_validation` /
`invalid_action_recommended` issue). The M5-A viewer renders the
`validation_status: FAIL` line and the `validation_failed` risk so a
human can see the action was rejected by the rule engine. No layer
in the system ever sets the action's `is_valid` to `True` after a
`FAIL` validation, and no layer ever marks the proposal as
`APPROVED`.

## Structured Output Example

The actual structured output is the `StructuredProposal` (M4-C) +
`ProposalEvaluation` (M4-D) produced by the deterministic pipeline.
The JSON payload below is a **simplified, schema-accurate** sketch of
what `backend/scripts/run_offseason_demo.py --format json` emits for
the default DEM-ATL scenario. Field names match the frozen dataclasses
in `backend/app/models/proposal.py` and `backend/app/models/evaluation.py`.
All values are **sample / simulation data** — this is a preview, not a
real NBA prediction, and no transaction is ever approved.

```json
{
  "proposal": {
    "proposal_id": "prop-DEM-ATL-add-frontcourt-help",
    "team_id": "DEM-ATL",
    "objective": "Add frontcourt help",
    "status": "RECOMMENDED",
    "recommended_actions": [
      {
        "action_id": "act-0-m4b-preview-0-fa-005",
        "action_type": "SIGNING",
        "team_id": "DEM-ATL",
        "transaction_id": "m4b-preview-0-fa-005",
        "player_id": "fa-005",
        "player_name": "Demo FA Quebec",
        "position": "C",
        "salary": 18000000,
        "validation_status": "PASS",
        "is_valid": true,
        "requires_human_approval": true,
        "fit_score": 0.78,
        "matched_need": "C: have 0, target 2",
        "cap_impact_summary": "cap_space_before=... cap_space_after=...",
        "roster_impact_summary": "roster_count_before=... roster_count_after=...",
        "depth_chart_impact_summary": "C starter=None -> fa-005",
        "evidence_ids": ["ev-001", "ev-003"],
        "limitations": ["preview only", "requires human approval"]
      }
    ],
    "risks": [
      { "code": "sample_data", "level": "LOW", "summary": "Demo/sample data.", "evidence_ids": [] }
    ],
    "evidence_refs": [
      { "evidence_id": "ev-001", "title": "...", "source": "...", "evidence_type": "team", "sample_data": true }
    ],
    "tool_call_trace": [
      { "tool_name": "cap_sheet_service", "status": "SUCCESS", "input_summary": "...", "output_summary": "...", "fallback_reason": null, "evidence_ids": [] }
    ],
    "cap_summary": "total_salary=... cap_space=...",
    "roster_need_summary": "roster_count=... needs=[C]",
    "depth_chart_summary": "PG:... SG:... SF:... PF:... C:None",
    "fallback_reasons": [],
    "limitations": ["M4-C deterministic proposal builder.", "No LLM call.", "No MCP.", "sample data", "preview only", "requires human approval"],
    "requires_human_approval": true,
    "sample_data": true
  },
  "evaluation": {
    "proposal_id": "prop-DEM-ATL-add-frontcourt-help",
    "team_id": "DEM-ATL",
    "status": "PASS",
    "issues": [
      { "code": "sample_data_only", "severity": "INFO", "summary": "Proposal built from sample data.", "action_id": null, "evidence_ids": [], "remediation": "" }
    ],
    "passed_checks": ["human_approval_guardrail", "validation_guardrail", "tool_trace_guardrail", "fallback_consistency", "sample_data_guardrail"],
    "failed_checks": [],
    "warnings": [],
    "limitations": ["M4-D deterministic evaluation.", "No LLM call.", "No MCP.", "sample data"],
    "sample_data": true
  },
  "actions": ["(alias for proposal.recommended_actions)"],
  "evidence": ["(alias for proposal.evidence_refs)"],
  "tool_trace": ["(alias for proposal.tool_call_trace)"],
  "limitations": ["(combined proposal + viewer limitations)"],
  "requires_human_approval": true,
  "sample_data": true
}
```

For the full payload, run `python backend/scripts/run_offseason_demo.py --format json`.

## Field Contract

The actual schema is defined by the frozen dataclasses in
`backend/app/models/proposal.py` and `backend/app/models/evaluation.py`.
The key fields are:

### `StructuredProposal`

| Field | Type | Notes |
|---|---|---|
| `proposal_id` | `str` | Deterministic id: `prop-{team_id}-{slugified-objective}`. |
| `team_id` | `str` | Team the proposal is for. |
| `objective` | `str` | Echoed from `OffseasonGoal`. |
| `status` | `ProposalStatus` | `RECOMMENDED` / `PARTIAL` / `BLOCKED` / `NO_ACTION`. Never `APPROVED`. |
| `recommended_actions` | `Tuple[ProposalAction, ...]` | Each action is a preview; `requires_human_approval=True`. |
| `risks` | `Tuple[ProposalRisk, ...]` | Each has `code` / `level` / `summary` / `evidence_ids`. |
| `evidence_refs` | `Tuple[ProposalEvidenceRef, ...]` | Flattened from matched evidence notes; never fabricated. |
| `tool_call_trace` | `Tuple[ToolCallRecord, ...]` | Echoed from `OffseasonAgentRun`. |
| `cap_summary` | `str` | Short deterministic cap summary. |
| `roster_need_summary` | `str` | Short deterministic roster-need summary. |
| `depth_chart_summary` | `str` | Short deterministic depth-chart summary. |
| `fallback_reasons` | `Tuple[str, ...]` | Human-readable fallback strings (may be empty). |
| `limitations` | `Tuple[str, ...]` | MVP limitation notes. |
| `requires_human_approval` | `bool` | Always `True`. |
| `sample_data` | `bool` | Always `True`. |

### `ProposalEvaluation`

| Field | Type | Notes |
|---|---|---|
| `proposal_id` | `str` | Echoed from the evaluated proposal. |
| `team_id` | `str` | Echoed from the evaluated proposal. |
| `status` | `EvaluationStatus` | `PASS` / `WARNING` / `FAIL`. Never `APPROVED`. |
| `issues` | `Tuple[EvaluationIssue, ...]` | Each has `code` / `severity` / `summary` / `action_id` / `evidence_ids` / `remediation`. |
| `passed_checks` | `Tuple[str, ...]` | Check names that passed. |
| `failed_checks` | `Tuple[str, ...]` | Check names that failed (ERROR only). |
| `warnings` | `Tuple[str, ...]` | Check names that produced warnings. |
| `limitations` | `Tuple[str, ...]` | MVP limitation notes. |
| `sample_data` | `bool` | Always `True`. |

The evaluator does NOT approve transactions and does NOT change the
proposal's `status` to `APPROVED`. It only emits issues and a
`PASS` / `WARNING` / `FAIL` evaluation status. See
`docs/evaluation.md` for the full test inventory.
