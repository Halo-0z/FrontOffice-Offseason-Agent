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

## Evaluation Harness (future, M6)

- Run the agent over a fixed set of `(team, goal)` seeds.
- Compare briefs against gold briefs for validation accuracy.
- Aggregate metrics into a single report JSON.
- Fail the harness if `guardrail_violation_count > 0` or `valid_json_rate < 1.0`.

## Notes

- M0 only declares the cases above as TODOs in the test files. Implementation lands in M1+.
- Metrics are computed on deterministic service outputs first; agent-layer metrics come online in M4+.
