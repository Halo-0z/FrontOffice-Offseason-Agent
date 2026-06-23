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

## Evaluation Harness (future, M6)

- Run the agent over a fixed set of `(team, goal)` seeds.
- Compare briefs against gold briefs for validation accuracy.
- Aggregate metrics into a single report JSON.
- Fail the harness if `guardrail_violation_count > 0` or `valid_json_rate < 1.0`.

## Notes

- M0 only declares the cases above as TODOs in the test files. Implementation lands in M1+.
- Metrics are computed on deterministic service outputs first; agent-layer metrics come online in M4+.
