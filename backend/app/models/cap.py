"""Salary cap models for FrontOffice-Offseason-Agent (M1).

This module defines the deterministic, immutable data structures used by
``cap_sheet_service`` to represent the league cap configuration, player
contracts, a team's cap sheet, and a summary view of that sheet.

All dataclasses are frozen so that the agent layer and any caller cannot
mutate cap state in place. Mutations flow through pure functions in
``cap_sheet_service`` (e.g. ``apply_signing_preview``) that return new
``TeamCapSheet`` instances.

These are DEMO/SAMPLE/SIMULATION models. They do not implement the full
NBA CBA. M1 scope is intentionally narrow: enough to compute
``total_salary``, ``cap_space``, and apron distances, and to support
``apply_signing_preview`` for the M2 transaction rule engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class SalaryCapConfig:
    """League-wide salary cap configuration for a single season.

    All monetary values are in USD (integer cents-of-a-dollar not used;
    plain integer dollars). Loaded from ``data/cap_config.json``.

    Attributes:
        season: Season label, e.g. ``"2025-2026"``.
        salary_cap: The soft salary cap.
        luxury_tax: The luxury tax line.
        first_apron: The first apron.
        second_apron: The second apron.
        roster_min: Minimum roster size.
        roster_max: Maximum roster size.
        minimum_salary: League minimum salary (single-season).
        mid_level_exception: Non-taxpayer mid-level exception amount.
        source_name: (M8-B optional provenance) snapshot source label.
        source_url: (M8-B optional provenance) snapshot source URL.
        as_of_date: (M8-B optional provenance) ISO date the snapshot is
            current as of.
        manual_review_required: (M8-B optional provenance) flag set by
            the snapshot loader when a row needs manual review.
    """

    season: str
    salary_cap: int
    luxury_tax: int
    first_apron: int
    second_apron: int
    roster_min: int
    roster_max: int
    minimum_salary: int
    mid_level_exception: int
    # M8-B optional provenance — defaults keep demo mode unchanged.
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    as_of_date: Optional[str] = None
    manual_review_required: bool = False


@dataclass(frozen=True)
class PlayerContract:
    """A single player contract entry on a team's cap sheet.

    Attributes:
        contract_id: Stable contract identifier, e.g. ``"ct-001"``.
        player_id: Player identifier, e.g. ``"pl-001"``.
        team_id: Team identifier, e.g. ``"DEM-ATL"``.
        salary: Current-season salary (cap hit), in USD.
        years_remaining: Years remaining after the current season.
        guaranteed: Whether the current-season salary is guaranteed.
        player_option: Whether the player holds an option year.
        team_option: Whether the team holds an option year.
        no_trade_clause: Whether the player has a no-trade clause.
        sample_data: True if this is demo/sample/simulation data.
    """

    contract_id: str
    player_id: str
    team_id: str
    salary: int
    years_remaining: int
    guaranteed: bool
    player_option: bool = False
    team_option: bool = False
    no_trade_clause: bool = False
    sample_data: bool = False
    # M8-B optional provenance — defaults keep demo mode unchanged.
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    as_of_date: Optional[str] = None
    manual_review_required: bool = False


@dataclass(frozen=True)
class TeamCapSheet:
    """A single team's cap sheet for a season.

    Attributes:
        team_id: Team identifier.
        season: Season label (mirrors ``SalaryCapConfig.season``).
        cap_config: The league cap configuration in effect.
        contracts: Tuple of ``PlayerContract`` for this team. A tuple is
            used instead of a list so the field is hashable and the
            dataclass can stay frozen.
    """

    team_id: str
    season: str
    cap_config: SalaryCapConfig
    contracts: Tuple[PlayerContract, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CapSheetSummary:
    """A deterministic summary view of a ``TeamCapSheet``.

    All distance fields are signed: positive means the team is below the
    line (has room), negative means the team is over the line.

    Attributes:
        team_id: Team identifier.
        season: Season label.
        roster_count: Number of contracts on the sheet.
        total_salary: Sum of current-season salaries.
        cap_space: ``salary_cap - total_salary``.
        tax_distance: ``luxury_tax - total_salary``.
        first_apron_distance: ``first_apron - total_salary``.
        second_apron_distance: ``second_apron - total_salary``.
    """

    team_id: str
    season: str
    roster_count: int
    total_salary: int
    cap_space: int
    tax_distance: int
    first_apron_distance: int
    second_apron_distance: int
