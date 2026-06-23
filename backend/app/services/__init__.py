"""Deterministic services + agent orchestration for the offseason agent.

Submodules (M1+):

- ``cap_sheet_service``         : cap sheet computation.
- ``transaction_rule_engine``   : signing/trade legality validation.
- ``roster_need_service``       : roster shortfall analysis.
- ``free_agent_service``        : free-agent candidate retrieval.
- ``trade_simulator``           : two-team trade simulation.
- ``depth_chart_projector``     : post-transaction depth chart projection.
- ``evidence_service``          : evidence note retrieval and citation.
- ``offseason_agent``           : task decomposition + tool orchestration.

M0 scope: package docstring only. No logic.
"""

__all__ = [
    "cap_sheet_service",
    "transaction_rule_engine",
    "roster_need_service",
    "free_agent_service",
    "trade_simulator",
    "depth_chart_projector",
    "evidence_service",
    "offseason_agent",
]
