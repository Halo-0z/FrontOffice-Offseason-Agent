"""Offseason agent.

Responsibility: orchestrate the offseason workflow. Decompose the goal,
call the deterministic services, assemble a structured brief, and emit
it for human approval.

Guardrails (enforced + tested in ``tests/test_agent_guardrails.py``):

- The agent must NOT directly mutate cap, roster, or contract state.
- The agent must NOT declare a transaction valid; only
  ``transaction_rule_engine`` can.
- The agent must NOT skip the human approval gate.
- On missing data or failed tool calls, the agent must emit a structured
  ``fallbacks`` entry, never a silent success.

Milestone: M4.

M0 scope: docstring + TODO only. No LLM API wiring in M0.
"""

# TODO(M4): implement run(team_id, goal) -> StructuredBrief.
# TODO(M4): implement assemble_brief(plans, transactions, depth_chart, evidence) -> dict.
# TODO(M4): wire tool calls to cap_sheet_service, roster_need_service,
#           free_agent_service, trade_simulator, transaction_rule_engine,
#           depth_chart_projector, evidence_service.
# TODO(M4): enforce guardrails via a thin mutator surface that raises on
#           direct state writes from the agent layer.
# TODO(M4): emit fallbacks + limitations instead of raising on missing data.
