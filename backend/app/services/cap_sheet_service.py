"""Deterministic cap sheet service (M1).

This service is the single source of truth for salary state. It loads
league cap configuration and player contracts from the local demo JSON
files, builds ``TeamCapSheet`` objects, computes deterministic
``CapSheetSummary`` values, and exposes a pure ``apply_signing_preview``
helper that returns a *new* sheet without mutating the input.

Guardrails:

- No LLM calls. No network. No state writes to disk.
- All cap figures come from ``data/cap_config.json``; nothing is
  hardcoded in this module.
- ``apply_signing_preview`` is pure: it returns a new ``TeamCapSheet``
  and never mutates the input sheet or its contracts.
- ``transaction_rule_engine`` (M2) is responsible for declaring whether
  a signing is *legal*. This service only computes the cap math.

Run tests:

    python -m pytest backend/app/tests/test_cap_sheet_service.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..models.cap import (
    CapSheetSummary,
    PlayerContract,
    SalaryCapConfig,
    TeamCapSheet,
)


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class CapSheetError(Exception):
    """Base class for cap sheet service errors."""


class TeamNotFoundError(CapSheetError):
    """Raised when a requested ``team_id`` does not exist in ``teams.json``."""


class CapConfigMissingError(CapSheetError):
    """Raised when ``cap_config.json`` is missing or malformed."""


class ContractsMissingError(CapSheetError):
    """Raised when ``contracts.json`` is missing or malformed."""


# --------------------------------------------------------------------------- #
# Internal path / JSON helpers
# --------------------------------------------------------------------------- #


def _find_repo_root(start: Path | None = None) -> Path:
    """Walk upward from ``start`` to find the repo root.

    The repo root is the closest ancestor directory that contains *both*
    a ``backend`` entry and a ``data`` entry. This avoids hardcoding the
    absolute repo path and works regardless of the current working
    directory or which package path was used to import this module.

    Falls back to walking up from this file's location if ``start`` is
    None. Raises ``CapSheetError`` if no such directory is found.
    """
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "backend").exists() and (candidate / "data").exists():
            return candidate
    raise CapSheetError(
        f"could not locate repo root (containing both 'backend' and 'data') "
        f"starting from {here}"
    )


def _resolve_data_dir(data_dir: Path | str) -> Path:
    """Resolve a data directory path.

    Resolution rules:

    - Absolute paths are used as-is (e.g. a pytest ``tmp_path``).
    - Relative paths are resolved against the repo root discovered by
      ``_find_repo_root``. This makes the default ``"data"`` argument
      resolve to ``<repo_root>/data`` no matter what the current working
      directory is, so ``load_cap_config()`` works from both the repo
      root and the ``backend`` directory.
    - If a relative path already exists relative to the current working
      directory, that is *ignored* for the default ``"data"`` case; we
      always anchor at the repo root to avoid accidentally reading
      ``D:\\data`` when invoked from ``D:\\``.
    """
    p = Path(data_dir)
    if p.is_absolute():
        return p
    repo_root = _find_repo_root()
    return repo_root / p


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise CapSheetError(f"data file not found: {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise CapSheetError(f"invalid JSON in {path}: {exc}") from exc


# --------------------------------------------------------------------------- #
# Public loaders
# --------------------------------------------------------------------------- #


def load_cap_config(data_dir: Path | str = "data") -> SalaryCapConfig:
    """Load the league-wide ``SalaryCapConfig`` from ``cap_config.json``.

    Raises:
        CapConfigMissingError: if the file is missing, malformed, or
            missing required fields.
    """
    path = _resolve_data_dir(data_dir) / "cap_config.json"
    if not path.exists():
        raise CapConfigMissingError(f"cap_config.json not found at {path}")
    payload = _load_json(path)
    cfg = payload.get("cap_config")
    if not isinstance(cfg, dict):
        raise CapConfigMissingError(
            f"cap_config.json must contain an object under 'cap_config'; got {type(cfg).__name__}"
        )
    required = [
        "season",
        "salary_cap",
        "luxury_tax",
        "first_apron",
        "second_apron",
        "roster_min",
        "roster_max",
        "minimum_salary",
        "mid_level_exception",
    ]
    missing = [k for k in required if k not in cfg]
    if missing:
        raise CapConfigMissingError(
            f"cap_config.json missing required fields: {missing}"
        )
    return SalaryCapConfig(
        season=str(cfg["season"]),
        salary_cap=int(cfg["salary_cap"]),
        luxury_tax=int(cfg["luxury_tax"]),
        first_apron=int(cfg["first_apron"]),
        second_apron=int(cfg["second_apron"]),
        roster_min=int(cfg["roster_min"]),
        roster_max=int(cfg["roster_max"]),
        minimum_salary=int(cfg["minimum_salary"]),
        mid_level_exception=int(cfg["mid_level_exception"]),
    )


def load_contracts(data_dir: Path | str = "data") -> list[PlayerContract]:
    """Load all player contracts from ``contracts.json``.

    Raises:
        ContractsMissingError: if the file is missing or malformed.
    """
    path = _resolve_data_dir(data_dir) / "contracts.json"
    if not path.exists():
        raise ContractsMissingError(f"contracts.json not found at {path}")
    payload = _load_json(path)
    raw_contracts = payload.get("contracts")
    if not isinstance(raw_contracts, list):
        raise ContractsMissingError(
            "contracts.json must contain a list under 'contracts'"
        )
    contracts: list[PlayerContract] = []
    for i, c in enumerate(raw_contracts):
        if not isinstance(c, dict):
            raise ContractsMissingError(
                f"contracts.json entry #{i} is not an object: {c!r}"
            )
        try:
            contracts.append(
                PlayerContract(
                    contract_id=str(c["contract_id"]),
                    player_id=str(c["player_id"]),
                    team_id=str(c["team_id"]),
                    salary=int(c["salary"]),
                    years_remaining=int(c["years_remaining"]),
                    guaranteed=bool(c["guaranteed"]),
                    player_option=bool(c.get("player_option", False)),
                    team_option=bool(c.get("team_option", False)),
                    no_trade_clause=bool(c.get("no_trade_clause", False)),
                    sample_data=bool(c.get("sample_data", False)),
                )
            )
        except KeyError as exc:
            raise ContractsMissingError(
                f"contracts.json entry #{i} missing field {exc}"
            ) from exc
    return contracts


def _load_team_ids(data_dir: Path | str = "data") -> set[str]:
    """Load the set of valid ``team_id`` values from ``teams.json``."""
    path = _resolve_data_dir(data_dir) / "teams.json"
    payload = _load_json(path)
    teams = payload.get("teams")
    if not isinstance(teams, list):
        raise CapSheetError("teams.json must contain a list under 'teams'")
    return {str(t["team_id"]) for t in teams if isinstance(t, dict) and "team_id" in t}


def load_team_cap_sheet(
    team_id: str, data_dir: Path | str = "data"
) -> TeamCapSheet:
    """Load a single team's cap sheet.

    Raises:
        TeamNotFoundError: if ``team_id`` is not present in ``teams.json``.
        CapConfigMissingError: if the cap config cannot be loaded.
        ContractsMissingError: if contracts cannot be loaded.
    """
    team_ids = _load_team_ids(data_dir)
    if team_id not in team_ids:
        raise TeamNotFoundError(
            f"team_id {team_id!r} not found in teams.json; known: {sorted(team_ids)}"
        )
    cap_config = load_cap_config(data_dir)
    all_contracts = load_contracts(data_dir)
    team_contracts = tuple(c for c in all_contracts if c.team_id == team_id)
    return TeamCapSheet(
        team_id=team_id,
        season=cap_config.season,
        cap_config=cap_config,
        contracts=team_contracts,
    )


# --------------------------------------------------------------------------- #
# Deterministic computation
# --------------------------------------------------------------------------- #


def summarize_cap_sheet(sheet: TeamCapSheet) -> CapSheetSummary:
    """Compute a deterministic ``CapSheetSummary`` for a cap sheet.

    ``cap_space = salary_cap - total_salary``.
    Distance fields are signed: positive = below the line, negative = over.
    """
    total_salary = sum(c.salary for c in sheet.contracts)
    cfg = sheet.cap_config
    return CapSheetSummary(
        team_id=sheet.team_id,
        season=sheet.season,
        roster_count=len(sheet.contracts),
        total_salary=total_salary,
        cap_space=cfg.salary_cap - total_salary,
        tax_distance=cfg.luxury_tax - total_salary,
        first_apron_distance=cfg.first_apron - total_salary,
        second_apron_distance=cfg.second_apron - total_salary,
    )


# --------------------------------------------------------------------------- #
# Pure preview helpers
# --------------------------------------------------------------------------- #


def apply_signing_preview(
    sheet: TeamCapSheet, contract: PlayerContract
) -> TeamCapSheet:
    """Return a *new* ``TeamCapSheet`` with ``contract`` added.

    This is a pure preview: the input ``sheet`` is never mutated. The
    returned sheet is a fresh immutable dataclass instance.

    This function does NOT validate whether the signing is legal under
    cap rules. Legality is the responsibility of
    ``transaction_rule_engine`` in M2. Here we only attach the contract
    to a preview sheet so callers (and tests) can compute the resulting
    ``CapSheetSummary``.
    """
    if contract.team_id != sheet.team_id:
        # A signing preview must be for the same team. We do not raise a
        # rule-engine error here (that is M2's job); we simply refuse to
        # attach a mismatched contract to avoid silent state corruption.
        raise CapSheetError(
            f"contract team_id {contract.team_id!r} does not match "
            f"sheet team_id {sheet.team_id!r}"
        )
    new_contracts = (*sheet.contracts, contract)
    return TeamCapSheet(
        team_id=sheet.team_id,
        season=sheet.season,
        cap_config=sheet.cap_config,
        contracts=new_contracts,
    )


def iter_team_ids(data_dir: Path | str = "data") -> Iterable[str]:
    """Yield all known team ids from ``teams.json``."""
    return sorted(_load_team_ids(data_dir))
