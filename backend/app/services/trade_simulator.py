"""Trade simulator (M3-B).

Deterministic preview service for proposed signings and trades. It
always delegates legality to the M2 ``transaction_rule_engine`` first,
then — only if validation passed — builds an in-memory preview roster
and computes the resulting roster-need report and depth chart.

Guardrails:

- No LLM calls. No network. No disk writes.
- ALWAYS calls ``transaction_rule_engine.validate_transaction`` first.
- If validation fails, returns a ``TransactionPreview`` with
  ``validation_result.is_valid=False`` and ``roster_need_after`` /
  ``depth_chart_after`` set to ``None`` (with a fallback note in
  ``limitations``). A failed preview is never "approved".
- If validation passes, builds a preview roster in memory (never writes
  to ``data/players.json`` or ``data/contracts.json``) and computes the
  post-transaction roster need + depth chart using M3-A projectors.
- ``requires_human_approval`` is always ``True``.

Run tests:

    python -m pytest backend/app/tests/test_trade_simulator.py
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from ..models.roster import (
    Position,
    ProjectedDepthChart,
    RosterNeedReport,
    RosterPlayer,
    TransactionPreview,
)
from ..models.transaction import (
    SigningTransaction,
    TradeTransaction,
    TransactionType,
)
from .depth_chart_projector import build_depth_chart_from_players
from .free_agent_service import get_free_agent_by_id
from .roster_need_service import (
    POSITION_TARGET_COUNTS,
    get_player_by_id,
    load_roster_players,
    summarize_position_counts,
)
from .transaction_rule_engine import (
    TransactionRuleEngineError,
    validate_transaction,
)


_MVP_LIMITATIONS: Tuple[str, ...] = (
    "MVP preview: in-memory only, never writes to data files.",
    "Post-transaction depth chart uses the same heuristic as current depth chart.",
    "Trade preview does not simulate multi-year contract decay.",
    "A passed preview still requires human approval before any state change.",
)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _evaluate_needs_from_players(
    team_id: str, players: Tuple[RosterPlayer, ...]
) -> RosterNeedReport:
    """Recompute a ``RosterNeedReport`` from an explicit player tuple.

    This mirrors ``roster_need_service.evaluate_roster_needs`` but
    operates on an in-memory preview roster instead of loading from
    disk. We inline the logic (rather than refactoring the public
    function) to keep M3-A's sealed API untouched.
    """
    from ..models.roster import NeedPriority, PositionNeed

    counts = summarize_position_counts(players)
    needs: List[PositionNeed] = []
    strengths: List[Position] = []
    for pos in Position:
        current = counts.get(pos, 0)
        target = POSITION_TARGET_COUNTS[pos]
        gap = target - current
        if gap > 0:
            priority = (
                NeedPriority.HIGH
                if gap >= 2
                else (NeedPriority.MEDIUM if gap == 1 else NeedPriority.LOW)
            )
            needs.append(
                PositionNeed(
                    position=pos,
                    current_count=current,
                    target_count=target,
                    priority=priority,
                    reason=f"{pos.value}: have {current}, target {target}, short {gap} (priority={priority.value}).",
                )
            )
        else:
            strengths.append(pos)
    priority_order = {
        NeedPriority.HIGH: 0,
        NeedPriority.MEDIUM: 1,
        NeedPriority.LOW: 2,
    }
    needs.sort(
        key=lambda n: (priority_order[n.priority], list(Position).index(n.position))
    )
    return RosterNeedReport(
        team_id=team_id,
        roster_count=len(players),
        needs=tuple(needs),
        strengths=tuple(strengths),
        limitations=(
            "Demo roster-need heuristic: target=2 per position. Not a scouting model.",
            "Computed on an in-memory preview roster.",
        ),
    )


def _preview_signing_roster(
    team_id: str, transaction: SigningTransaction, data_dir: Path | str
) -> Tuple[Tuple[RosterPlayer, ...], bool]:
    """Build the in-memory post-signing roster (current roster + new player).

    Returns ``(players, fa_profile_found)``. When the free-agent profile
    is found in ``data/free_agents.json``, the preview player uses the
    real ``name`` / ``position`` / ``role``. When it is NOT found, no
    preview player is appended and ``fa_profile_found`` is ``False``;
    the caller must then skip roster/depth-chart projection and emit a
    fallback limitation (we never hardcode a default position).
    """
    current = load_roster_players(team_id, data_dir)
    fa_profile = get_free_agent_by_id(transaction.player_id, data_dir)
    if fa_profile is None:
        return current, False

    try:
        position = Position(str(fa_profile.get("position", "")))
    except ValueError:
        # Profile exists but position is invalid: still refuse to
        # hardcode a default. Treat as missing profile.
        return current, False

    name = str(fa_profile.get("name", transaction.player_id))
    role = str(fa_profile.get("role", "bench"))
    new_player = RosterPlayer(
        player_id=transaction.player_id,
        name=name,
        team_id=team_id,
        position=position,
        role=role,
        contract_id=f"{transaction.transaction_id}-preview",
        salary=transaction.salary,
        sample_data=True,
    )
    return (*current, new_player), True


def _build_incoming_player(
    asset_player_id: str,
    target_team_id: str,
    salary: int,
    data_dir: Path | str,
) -> RosterPlayer | None:
    """Build a preview ``RosterPlayer`` for an incoming trade asset.

    Looks up the player profile in ``data/players.json``. Returns ``None``
    if the profile is missing or has an invalid position — the caller
    must then skip roster/depth-chart projection and emit a fallback
    limitation. We never hardcode a default position.
    """
    profile = get_player_by_id(asset_player_id, data_dir)
    if profile is None:
        return None
    try:
        position = Position(str(profile.get("position", "")))
    except ValueError:
        return None
    name = str(profile.get("name", asset_player_id))
    role = str(profile.get("role", "bench"))
    return RosterPlayer(
        player_id=asset_player_id,
        name=name,
        team_id=target_team_id,
        position=position,
        role=role,
        salary=salary,
        sample_data=True,
    )


def _preview_trade_rosters(
    transaction: TradeTransaction, data_dir: Path | str
) -> Tuple[Tuple[RosterPlayer, ...], Tuple[RosterPlayer, ...], bool]:
    """Build in-memory post-trade rosters for team A and team B.

    Outgoing players are removed by ``player_id``; incoming players are
    looked up in ``data/players.json`` and appended with the receiving
    team's id using their REAL position/name/role.

    Returns ``(roster_a, roster_b, all_profiles_found)``. When any
    incoming player profile is missing, ``all_profiles_found`` is
    ``False`` and the caller must skip roster/depth-chart projection
    (we never hardcode a default position). The returned rosters in
    that case are still the "kept" rosters (outgoing removed) but
    WITHOUT the unknown incoming players appended.
    """
    roster_a = load_roster_players(transaction.team_a_id, data_dir)
    roster_b = load_roster_players(transaction.team_b_id, data_dir)

    out_a_ids = {a.player_id for a in transaction.outgoing_from_a}
    out_b_ids = {a.player_id for a in transaction.outgoing_from_b}

    kept_a = tuple(p for p in roster_a if p.player_id not in out_a_ids)
    kept_b = tuple(p for p in roster_b if p.player_id not in out_b_ids)

    incoming_to_a: List[RosterPlayer] = []
    incoming_to_b: List[RosterPlayer] = []
    all_profiles_found = True

    for a in transaction.outgoing_from_b:
        player = _build_incoming_player(
            a.player_id, transaction.team_a_id, a.salary, data_dir
        )
        if player is None:
            all_profiles_found = False
        else:
            incoming_to_a.append(player)

    for a in transaction.outgoing_from_a:
        player = _build_incoming_player(
            a.player_id, transaction.team_b_id, a.salary, data_dir
        )
        if player is None:
            all_profiles_found = False
        else:
            incoming_to_b.append(player)

    return (*kept_a, *incoming_to_a), (*kept_b, *incoming_to_b), all_profiles_found


# --------------------------------------------------------------------------- #
# Public preview API
# --------------------------------------------------------------------------- #


def preview_signing(
    transaction: SigningTransaction, data_dir: Path | str = "data"
) -> TransactionPreview:
    """Preview a signing proposal.

    Always validates via ``transaction_rule_engine.validate_signing``
    first. If validation fails, returns a fallback preview. If it
    passes, looks up the free-agent profile in ``free_agents.json``:

    - If the profile is found, builds an in-memory post-signing roster
      using the real ``name`` / ``position`` / ``role``, and computes
      the resulting roster-need report and depth chart.
    - If the profile is NOT found, refuses to hardcode a default
      position: ``roster_need_after`` and ``depth_chart_after`` are set
      to ``None`` and a fallback note is added to ``limitations``.
    """
    validation = validate_transaction(transaction, data_dir)
    limitations: List[str] = list(_MVP_LIMITATIONS)

    if not validation.is_valid:
        limitations.append(
            "Validation failed; roster_need_after and depth_chart_after are None. "
            "This preview is NOT approved."
        )
        return TransactionPreview(
            transaction_id=transaction.transaction_id,
            validation_result=validation,
            roster_need_after=None,
            depth_chart_after=None,
            cap_summary_after=validation.cap_summary_after,
            requires_human_approval=True,
            limitations=tuple(limitations),
        )

    # Validation passed: look up FA profile and build preview roster.
    preview_players, fa_profile_found = _preview_signing_roster(
        transaction.team_id, transaction, data_dir
    )
    if not fa_profile_found:
        limitations.append(
            "Missing free-agent profile; roster/depth-chart projection was not generated."
        )
        return TransactionPreview(
            transaction_id=transaction.transaction_id,
            validation_result=validation,
            roster_need_after=None,
            depth_chart_after=None,
            cap_summary_after=validation.cap_summary_after,
            requires_human_approval=True,
            limitations=tuple(limitations),
        )

    roster_need_after = _evaluate_needs_from_players(
        transaction.team_id, preview_players
    )
    depth_chart_after = build_depth_chart_from_players(
        transaction.team_id, preview_players
    )
    return TransactionPreview(
        transaction_id=transaction.transaction_id,
        validation_result=validation,
        roster_need_after=roster_need_after,
        depth_chart_after=depth_chart_after,
        cap_summary_after=validation.cap_summary_after,
        requires_human_approval=True,
        limitations=tuple(limitations),
    )


def preview_trade(
    transaction: TradeTransaction, data_dir: Path | str = "data"
) -> TransactionPreview:
    """Preview a two-team trade proposal.

    Always validates via ``transaction_rule_engine.validate_trade``
    first. If validation fails, returns a fallback preview. If it
    passes, looks up each incoming player's profile in
    ``data/players.json``:

    - If ALL incoming player profiles are found, builds in-memory
      post-trade rosters using the real ``name`` / ``position`` /
      ``role``, and computes team A's roster-need report and depth
      chart as the preview (team B's is deferred).
    - If ANY incoming player profile is missing, refuses to hardcode a
      default position: ``roster_need_after`` and ``depth_chart_after``
      are set to ``None`` and a fallback note is added to
      ``limitations``. This conservative behavior avoids producing a
      misleading depth chart when some incoming positions are unknown.
    """
    validation = validate_transaction(transaction, data_dir)
    limitations: List[str] = list(_MVP_LIMITATIONS)

    if not validation.is_valid:
        limitations.append(
            "Validation failed; roster_need_after and depth_chart_after are None. "
            "This preview is NOT approved."
        )
        return TransactionPreview(
            transaction_id=transaction.transaction_id,
            validation_result=validation,
            roster_need_after=None,
            depth_chart_after=None,
            cap_summary_after=validation.cap_summary_after,
            requires_human_approval=True,
            limitations=tuple(limitations),
        )

    preview_a, _preview_b, all_profiles_found = _preview_trade_rosters(
        transaction, data_dir
    )
    if not all_profiles_found:
        limitations.append(
            "Missing incoming player profile; roster/depth-chart projection was not fully generated."
        )
        return TransactionPreview(
            transaction_id=transaction.transaction_id,
            validation_result=validation,
            roster_need_after=None,
            depth_chart_after=None,
            cap_summary_after=validation.cap_summary_after,
            requires_human_approval=True,
            limitations=tuple(limitations),
        )

    roster_need_after = _evaluate_needs_from_players(
        transaction.team_a_id, preview_a
    )
    depth_chart_after = build_depth_chart_from_players(
        transaction.team_a_id, preview_a
    )
    limitations.append(
        "Preview reflects team A's post-trade roster; team B's preview is deferred."
    )
    return TransactionPreview(
        transaction_id=transaction.transaction_id,
        validation_result=validation,
        roster_need_after=roster_need_after,
        depth_chart_after=depth_chart_after,
        cap_summary_after=validation.cap_summary_after,
        requires_human_approval=True,
        limitations=tuple(limitations),
    )


def preview_transaction(
    transaction, data_dir: Path | str = "data"
) -> TransactionPreview:
    """Dispatch to ``preview_signing`` or ``preview_trade`` by type."""
    if isinstance(transaction, SigningTransaction):
        return preview_signing(transaction, data_dir)
    if isinstance(transaction, TradeTransaction):
        return preview_trade(transaction, data_dir)
    raise TransactionRuleEngineError(
        f"Unsupported transaction type for preview: {type(transaction).__name__}"
    )
