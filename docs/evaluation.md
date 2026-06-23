# Evaluation

This document defines the evaluation metrics and pytest cases for `FrontOffice-Offseason-Agent`.

## Metrics

| Metric | Definition | Target |
|---|---|---|
| `tool_call_success_rate` | Fraction of agent tool calls that succeed without exception. | >= 0.95 |
| `valid_json_rate` | Fraction of agent briefs that parse as JSON and contain all required fields. | 1.0 |
| `evidence_coverage_rate` | Fraction of plans that cite at least one valid `evidence_id`. | >= 0.80 |
| `transaction_validation_accuracy` | Agreement between `transaction_rule_engine` verdicts and a hand-labeled gold set. | >= 0.95 |
| `fallback_success_rate` | Fraction of failure scenarios that produce a structured `fallbacks` entry instead of crashing. | 1.0 |
| `guardrail_violation_count` | Number of times the agent attempts a forbidden direct mutation. | 0 |

## Pytest Cases (planned)

Located under `backend/app/tests/`. Each case maps to a milestone.

| Test | File | Scenario |
|---|---|---|
| Cap space enough, signing passes | `test_cap_sheet_service.py` | Team has cap room; signing is validated as `valid`. |
| Cap space insufficient, signing fails | `test_cap_sheet_service.py` | Team lacks cap room; signing is validated as `invalid` with cap reason. |
| Salary matching fails | `test_transaction_rule_engine.py` | Two-team trade where outgoing/incoming salaries violate matching rules. |
| Roster full fallback | `test_offseason_agent.py` | Roster at limit; agent emits `fallbacks` entry instead of forcing a signing. |
| Missing contract data fallback | `test_offseason_agent.py` | Player contract missing; agent skips and logs fallback. |
| Evidence missing fallback | `test_offseason_agent.py` | No evidence for a plan; agent marks `low_confidence` and lists in `limitations`. |
| Agent tries to modify roster directly and is blocked | `test_agent_guardrails.py` | Agent calls a forbidden mutator; guardrail raises and no state changes. |
| Structured output missing required field and is rejected | `test_agent_guardrails.py` | Brief missing `evidence_ids`; upstream validator rejects it. |

M2 rule validation tests (implemented in `test_transaction_rule_engine.py`):
minimum/MLE/simple-FA signing pass & fail paths, roster-full FAIL,
roster-at-max WARNING, apron-crossing warnings, valid two-team trade
PASS, salary-mismatch FAIL, unknown-team FAIL, empty-outgoing FAIL,
trade roster-overflow FAIL, dispatch correctness, immutable
`ValidationResult`, `requires_human_approval=True` invariant, and
no-mutation of `data/contracts.json`.

M3-A roster & depth chart deterministic tests (implemented in
`test_roster_need_service.py` and `test_depth_chart_projector.py`):
load 3 demo teams' roster players, position-count correctness, missing
position → HIGH need, single-player position → MEDIUM need, strengths
disjoint from needs, unknown-team raises clear exception, no mutation
of `data/players.json`, every standard position has a depth-chart slot,
empty slot → `starter=None` + `need_level=high`, single-player slot →
`medium`, multi-player slot → `low`, starters/backups derived from
roster (not hardcoded), determinism, and immutability.

M3-B free-agent matching & transaction preview deterministic tests
(implemented in `test_free_agent_service.py`,
`test_trade_simulator.py`, and the M3-B block of
`test_agent_guardrails.py`):

- Free-agent matching: load `data/free_agents.json` (non-empty), each
  free agent preserves `evidence_ids`, `rank_free_agents_for_team`
  returns `FreeAgentFit` objects with `fit_score` in `[0,1]`, ATL
  (which needs C) matches the C candidate `fa-005` against the C need
  with `fit_score > 0.5`, HIGH-priority match beats MEDIUM-priority
  match, `fit_score` deterministic across repeated calls and across
  all 3 demo teams, unknown `team_id` raises `TeamNotFoundError`, no
  mutation of `data/free_agents.json`, service does NOT call
  `transaction_rule_engine` (monkeypatch spy), service does NOT return
  `SigningTransaction` objects, `FreeAgentFit` is immutable.
- Transaction preview: `preview_signing` calls `validate_transaction`
  exactly once (spy), valid signing preview returns
  `requires_human_approval=True` with structured `roster_need_after` /
  `depth_chart_after` / `cap_summary_after`, invalid signing preview
  has `is_valid=False` with `roster_need_after=None` /
  `depth_chart_after=None` and a "Validation failed" limitation,
  preview does not mutate `data/players.json` or `data/contracts.json`,
  `preview_trade` on a valid trade returns a structured preview, invalid
  trade returns the validation-failed fallback, `preview_transaction`
  dispatches signing/trade correctly, unsupported transaction type
  raises `TransactionRuleEngineError`, preview is deterministic and
  immutable.
- Guardrails: every `TransactionPreview` (pass or fail) has
  `requires_human_approval=True`; a failed preview cannot be flipped to
  approved (frozen dataclass); `free_agent_service` cannot bypass the
  rule engine (monkeypatch engine to raise — FA matching still works,
  and `FreeAgentFit` has no `is_valid` / `status` /
  `requires_human_approval` field).

M4-A evidence retrieval deterministic tests (implemented in
`test_evidence_service.py` and the M4-A block of
`test_agent_guardrails.py`):

- Load `data/evidence_notes.json` (non-empty, >= 6 notes), every note
  has `evidence_id` / `title` / `summary` / `source` / `source_type` /
  `evidence_type` / `sample_data=True`, and the demo pool covers all
  required `EvidenceType` values (team / player / cap / roster /
  market / transaction context).
- `get_evidence_by_ids` returns matched notes for known ids, reports
  `missing_evidence_ids` for unknown ids, sets a clear
  `fallback_reason` when nothing is found, and never fabricates notes.
- `search_evidence` by `team_id` / `player_id` / `topics` / `query`
  (lowercase token overlap) returns relevant notes, applies `limit`
  after sorting, and returns empty `matched_notes` + `fallback_reason`
  when nothing matches.
- Determinism: same inputs produce identical `matched_notes` orderings
  across repeated calls; sort is score desc then `evidence_id` asc.
- No mutation of `data/evidence_notes.json` across all retrieval paths.
- Immutability: `EvidenceNote` / `EvidenceBundle` / `EvidenceQuery`
  are frozen.
- Error handling: missing file, malformed JSON, invalid
  `evidence_type`, and missing required fields all raise
  `EvidenceFileMissingError` with a clear message.
- `build_evidence_bundle` dispatches to id lookup when `evidence_ids`
  is non-empty, else facet search.
- Guardrails: missing evidence does not fabricate notes; every returned
  note/bundle is `sample_data=True`; `evidence_service` does not
  generate transaction proposals (no `transaction` / `proposal` /
  `is_valid` / `validation_result` fields on bundle or note);
  `evidence_service` does not call `transaction_rule_engine`
  (monkeypatch engine to raise — retrieval still works).

M4-B offseason agent tool orchestrator deterministic tests (implemented
in `test_offseason_agent.py` and the M4-B block of
`test_agent_guardrails.py`):

- `run_offseason_plan` returns a structured `OffseasonAgentRun` with
  `requires_human_approval=True` and `sample_data=True`.
- `tool_call_trace` includes all six key tools: `cap_sheet_service`,
  `roster_need_service`, `depth_chart_projector`,
  `free_agent_service`, `trade_simulator.preview_signing`, and
  `evidence_service`.
- DEM-ATL plan identifies roster needs and produces `free_agent_fits`
  (non-empty when filters allow).
- Every signing preview has `requires_human_approval=True` — no
  preview is treated as approved.
- No mutation of `data/players.json`, `data/contracts.json`,
  `data/free_agents.json`, or `data/evidence_notes.json` across a run.
- The orchestrator does not call any LLM / OpenAI API (no `openai` /
  `llm` / `anthropic` / `chat_completion` attributes on the module).
- The orchestrator does not use MCP (no `mcp` / `mcp_client` /
  `mcp_server` / `MCPClient` attributes on the module).
- No signing preview is generated as an approved transaction (even
  when `is_valid=True`, `requires_human_approval` is still `True`).
- `evidence_bundle` is returned from `evidence_service`; missing
  evidence and `fallback_reason` are preserved.
- Unknown `team_id` raises `TeamNotFoundError` (critical failure).
- `max_candidates` / `max_salary` / `target_positions` filters are
  applied correctly.
- Tool failure (monkeypatch `rank_free_agents_for_team` to raise)
  produces a `FAILED` `ToolCallRecord` and `AgentRunStatus.FAILED`.
- No free-agent candidates after filtering produces `FALLBACK` trace
  and `AgentRunStatus.PARTIAL`.
- Determinism: same inputs produce identical `OffseasonAgentRun` and
  identical `tool_call_trace` across repeated calls.
- Immutability: `OffseasonAgentRun` / `ToolCallRecord` / `OffseasonGoal`
  are frozen.
- `limitations` documents MVP scope (M4-B, no LLM, no MCP, no external
  NBA API, previews require human approval).
- Guardrails: agent run `requires_human_approval=True`; signing
  previews not approved; agent does not bypass `trade_simulator`
  (monkeypatch `preview_signing` to raise — trace records `FAILED`);
  tool trace records all key tools; agent does not use MCP/LLM; agent
  does not write data files.

M4-C structured proposal builder deterministic tests (implemented in
`test_proposal_builder.py` and the M4-C block of
`test_agent_guardrails.py`):

- `build_structured_proposal` returns a `StructuredProposal` with
  `requires_human_approval=True` and `sample_data=True`.
- A SUCCESS agent run with a valid signing preview produces
  `RECOMMENDED` (or a reasonable status among `RECOMMENDED` /
  `PARTIAL` / `BLOCKED` / `NO_ACTION`).
- Every `ProposalAction` has `requires_human_approval=True` — even
  when `is_valid=True`, the action is NOT approved/finalized.
- Actions preserve `transaction_id` / `validation_status` / `is_valid`
  from the underlying `TransactionPreview`.
- Actions carry `player_name` / `position` / `fit_score` when the
  `FreeAgentFit` matches the preview.
- `evidence_refs` come from the evidence bundle's `matched_notes`
  (never fabricated); `len(evidence_refs) == len(matched_notes)`.
- Missing evidence ids appear in `fallback_reasons`.
- No candidates produces `NO_ACTION` / `PARTIAL` and a
  `no_matching_candidate` risk.
- Validation-failed previews are NOT marked as approved/recommended
  valid (`is_valid=False`, status `BLOCKED` / `PARTIAL`,
  `validation_failed` risk present).
- `tool_call_trace` is preserved (echoed from the agent run).
- `limitations` documents MVP scope (M4-C, no LLM, no MCP, previews,
  human approval, sample/simulation data).
- `run_goal_and_build_proposal` works end-to-end from an
  `OffseasonGoal`.
- No mutation of `data/players.json`, `data/contracts.json`,
  `data/free_agents.json`, or `data/evidence_notes.json` across a
  build.
- The builder does not call any LLM / OpenAI API (no `openai` / `llm`
  / `anthropic` / `chat_completion` attributes on the module).
- The builder does not use MCP (no `mcp` / `mcp_client` / `mcp_server`
  / `MCPClient` attributes on the module).
- The builder does not call `transaction_rule_engine` (monkeypatch
  engine to raise — builder still works on a pre-built run).
- The builder does not call `trade_simulator` (monkeypatch simulator
  to raise — builder still works on a pre-built run).
- Determinism: same inputs produce identical `StructuredProposal`
  across repeated calls (both `build_structured_proposal` and
  `run_goal_and_build_proposal`).
- Immutability: `StructuredProposal` / `ProposalAction` /
  `ProposalRisk` are frozen.
- `proposal_id` is deterministic and human-readable
  (`prop-{team_id}-{slugified-objective}`).
- `cap_summary` / `roster_need_summary` / `depth_chart_summary` are
  populated from the agent run's structured fields.
- `sample_data` risk is always present.
- Action `evidence_ids` are a subset of `evidence_refs` ids, or the
  missing ones appear in `fallback_reasons` (no silent fabrication).
- When there are no candidates, the proposal includes a `HOLD` action
  (or no `SIGNING` action with `is_valid=True`).
- Guardrails: proposal `requires_human_approval=True`; actions not
  approved/finalized; builder does not re-validate transactions
  (monkeypatch engine + simulator to raise — builder still works);
  `evidence_refs` only from bundle; builder does not use MCP/LLM;
  builder does not write data files.

M4-D proposal evaluation / fallback layer deterministic tests
(implemented in `test_proposal_evaluator.py` and the M4-D block of
`test_agent_guardrails.py`):

- `evaluate_structured_proposal` returns a `ProposalEvaluation` with
  `status` (`PASS` / `WARNING` / `FAIL`), `issues`, `passed_checks`,
  `failed_checks`, `warnings`, `limitations`, and `sample_data=True`.
- A valid `RECOMMENDED` proposal evaluates to `PASS` or `WARNING`
  (never `FAIL`).
- A proposal missing `requires_human_approval=True` produces a `FAIL`
  evaluation with a `missing_human_approval` issue.
- An action missing `requires_human_approval=True` produces a `FAIL`
  evaluation with a `missing_human_approval` issue.
- An action with `validation_status="FAIL"` but `is_valid=True`
  produces a `FAIL` evaluation with an
  `approved_without_validation` / `invalid_action_recommended` issue.
- An invalid signing action cannot be evaluated as a clean `PASS`.
- A `RECOMMENDED` proposal with empty `evidence_refs` produces a
  `WARNING` (`missing_evidence` issue).
- A missing-evidence `fallback_reason` without a corresponding risk
  produces a `WARNING` (`missing_risk_for_fallback` issue).
- A `tool_call_trace` missing one of the six key tools produces a
  `missing_tool_trace` issue.
- A `NO_ACTION` proposal with a `HOLD` action or a
  `no_matching_candidate` risk does NOT fail evaluation.
- A `RECOMMENDED` proposal with no candidates produces a `FAIL`
  (`no_action_fallback` issue).
- `sample_data=True` is recognized and recorded as an INFO issue
  (`sample_data_only`).
- No mutation of `data/players.json`, `data/contracts.json`,
  `data/free_agents.json`, or `data/evidence_notes.json` across an
  evaluation.
- The evaluator does not call any LLM / OpenAI API (no `openai` /
  `llm` / `anthropic` / `chat_completion` attributes on the module).
- The evaluator does not use MCP (no `mcp` / `mcp_client` /
  `mcp_server` / `MCPClient` attributes on the module).
- The evaluator does not call `transaction_rule_engine` (monkeypatch
  engine to raise — evaluator still works on a pre-built proposal).
- The evaluator does not call `trade_simulator` (monkeypatch simulator
  to raise — evaluator still works on a pre-built proposal).
- `run_evaluation_scenario` returns an `EvaluationScenarioResult`
  with `scenario_id` / `proposal` / `evaluation` / `status` /
  `limitations`.
- `run_default_evaluation_scenarios` returns multiple
  `EvaluationScenarioResult` objects (4 default scenarios).
- Default scenarios all evaluate to a non-`FAIL` scenario status
  (unless a scenario explicitly tests a failure path).
- Scenario outputs are deterministic: two consecutive runs of
  `run_default_evaluation_scenarios` produce equal results.
- Immutability: `ProposalEvaluation` / `EvaluationIssue` /
  `EvaluationScenarioResult` are frozen.
- `passed_checks` is populated with the names of checks that passed.
- `limitations` documents MVP scope (M4-D, no LLM, no MCP, no
  external NBA API, evaluator does not approve transactions).
- Guardrails: evaluator does not approve transactions (no `approved`
  / `is_approved` field); evaluator does not change the proposal's
  `ProposalStatus` to "approved" (proposal status unchanged after
  evaluation; evaluation status is one of `PASS` / `WARNING` /
  `FAIL`); evaluator does not use MCP/LLM; evaluator does not write
  data files; evaluator FAILS proposals missing human approval.

### M4-D Scenario Evaluation

`run_default_evaluation_scenarios` runs 4 fixed demo scenarios
end-to-end as a regression suite. Each scenario builds a proposal via
`run_goal_and_build_proposal` (because the scenario suite evaluates
the full system), then evaluates it via
`evaluate_structured_proposal`, then checks expected constraints
(`expected_statuses`, `expected_min_actions`, `expected_risk_codes`).

| Scenario | Goal | Expected proposal status | Expected min actions | Expected risk codes |
|---|---|---|---|---|
| `success_center_signing` | DEM-ATL, target_positions=('C',), max_salary=20M | `RECOMMENDED` | 1 | `sample_data` |
| `strict_budget_no_action` | DEM-ATL, target_positions=('C',), max_salary=15M | `NO_ACTION` or `PARTIAL` | 0 | `no_matching_candidate` |
| `broad_need_multiple_candidates` | DEM-ATL, target_positions=(), max_salary=20M, max_candidates=2 | any non-`BLOCKED` | 1 | (none required) |
| `evidence_fallback_case` | DEM-ATL, evidence_query uses a non-matching query | any | 0 | (fallback / risk expected) |

### M4-D Guardrail Checks

The evaluator enforces the following guardrails on every
`StructuredProposal`:

| Guardrail | Issue code | Severity | Trigger |
|---|---|---|---|
| Human approval | `missing_human_approval` | ERROR | proposal or any action has `requires_human_approval=False` |
| Validation consistency | `approved_without_validation` | ERROR | action `validation_status="FAIL"` but `is_valid=True` |
| Validation consistency | `invalid_action_recommended` | ERROR/WARNING | `RECOMMENDED` with no valid action |
| Evidence | `missing_evidence` | WARNING | `RECOMMENDED` with empty `evidence_refs` |
| Evidence | `missing_risk_for_fallback` | WARNING | `fallback_reasons` mentions missing evidence but no risk |
| Tool trace | `missing_tool_trace` | WARNING | `tool_call_trace` missing one of the six key tools |
| Fallback | `no_action_fallback` | ERROR | `RECOMMENDED` with no candidates |
| Fallback | `missing_risk_for_fallback` | WARNING | `fallback_reasons` non-empty but no risk or limitation |
| Sample data | `sample_data_only` | INFO | always emitted (proposal is sample data) |
| Mutation | `no_mutation_guardrail` | ERROR | (reserved for runtime checks; evaluator itself does not mutate) |
| Determinism | `non_deterministic_output` | ERROR | (reserved for scenario determinism checks) |

### M4-D Fallback Checks

The evaluator checks fallback consistency:

- A `NO_ACTION` proposal must carry a `HOLD` action OR a
  `no_matching_candidate` risk; otherwise it produces a
  `no_action_fallback` issue.
- A `RECOMMENDED` proposal with no candidates produces a `FAIL`
  (`no_action_fallback`).
- Non-empty `fallback_reasons` must be backed by a risk or
  limitation; otherwise a `missing_risk_for_fallback` WARNING is
  emitted.

### M4-D Determinism Checks

- `evaluate_structured_proposal` is a pure function of its input:
  same proposal → same evaluation.
- `run_default_evaluation_scenarios` is deterministic: two
  consecutive runs produce equal `EvaluationScenarioResult` tuples
  (verified by `r1 == r2` in tests and in the verification commands).
- The evaluator does NOT depend on wall-clock time, random numbers,
  network, or any external state.

M5-A proposal viewer / CLI demo deterministic tests (implemented in
`test_proposal_viewer.py`, `test_run_offseason_demo.py`, and the M5-A
block of `test_agent_guardrails.py`):

- `format_proposal_brief` returns a `str`.
- The brief contains `team_id` / `objective` / proposal status /
  evaluation status.
- The brief contains recommended action `player_name` / `position` /
  `validation_status`.
- The brief contains `evidence_id` / evidence title.
- The brief contains `tool_call_trace` entries.
- The brief contains `requires_human_approval=True`.
- The brief contains `sample_data=True`.
- The NO_ACTION path shows `HOLD` action / fallback reasons /
  `no_matching_candidate` risk.
- `build_demo_payload` returns a stable dict with `proposal` /
  `evaluation` / `actions` / `evidence` / `tool_trace` / `limitations`
  / `requires_human_approval` / `sample_data` keys.
- `build_demo_brief` runs the default DEM-ATL C scenario.
- Output is deterministic: same input → same output (verified for
  `format_proposal_brief`, `build_demo_brief`, `build_demo_payload`,
  and the CLI script `--format text|json`).
- The viewer does not mutate `data/players.json`,
  `data/contracts.json`, `data/free_agents.json`, or
  `data/evidence_notes.json`.
- The viewer does not call any LLM / OpenAI API (no `openai` / `llm`
  / `anthropic` / `chat_completion` attributes on the module).
- The viewer does not use MCP (no `mcp` / `mcp_client` / `mcp_server`
  / `MCPClient` attributes on the module).
- The viewer does not approve transactions (no `approved` language in
  the brief; proposal `requires_human_approval` unchanged).
- The viewer does not change the proposal's `ProposalStatus` or the
  evaluation's `EvaluationStatus`.
- CLI script default run succeeds with exit code 0.
- CLI `--format text` output contains a recognizable proposal header
  (`FrontOffice-Offseason-Agent` / `proposal status` / `DEM-ATL`).
- CLI `--format json` output is valid JSON with `proposal` /
  `evaluation` / `actions` / `evidence` / `tool_trace` keys.
- CLI `--target-position C` works and produces a `RECOMMENDED`
  proposal with at least one `SIGNING` action.
- CLI strict-budget scenario (`--max-salary 15000000`) outputs
  `NO_ACTION` or `PARTIAL` with a `HOLD` action or
  `no_matching_candidate` risk.
- CLI unknown team (`--team-id UNKNOWN-TEAM-XYZ`) returns non-zero
  exit code with a clear error mentioning the known team ids.
- CLI text output mentions `requires_human_approval` and
  `sample_data` and the MVP limitations (`No LLM call` / `No MCP`).
- CLI does not mutate any data file.
- CLI does not import LLM / MCP clients (source inspection).
- CLI does not make network calls (source inspection).
- Guardrails: viewer does not approve transactions; viewer does not
  use MCP/LLM; viewer does not write data files; CLI demo does not
  write data files; CLI demo output mentions human approval / sample
  data limitations.

### M5-A CLI Demo Output Checks

The CLI script `backend/scripts/run_offseason_demo.py` supports two
output formats:

| Format | Behavior |
|---|---|
| `text` (default) | Calls `format_proposal_brief` and prints the human-readable brief to stdout. |
| `json` | Calls `build_demo_payload` and prints `json.dumps(payload, sort_keys=True, indent=2)` to stdout. |

Both formats are deterministic: two consecutive runs produce identical
stdout. The script writes no files and returns exit code 0 on success,
non-zero on argument/runtime errors (e.g. unknown `team_id`).

## Evaluation Harness (future, M6)

- Run the agent over a fixed set of `(team, goal)` seeds.
- Compare briefs against gold briefs for validation accuracy.
- Aggregate metrics into a single report JSON.
- Fail the harness if `guardrail_violation_count > 0` or `valid_json_rate < 1.0`.

## Notes

- M0 only declares the cases above as TODOs in the test files. Implementation lands in M1+.
- Metrics are computed on deterministic service outputs first; agent-layer metrics come online in M4+.
