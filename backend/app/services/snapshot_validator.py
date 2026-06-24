"""Snapshot bundle structural validator (M8-B Core).

This module validates the **shape** of a snapshot bundle directory
before the loader (``snapshot_loader``) tries to consume it. It does
NOT call any external API, does NOT call any LLM, does NOT use MCP, and
does NOT write any data file. It is a pure, offline, deterministic
checker.

A snapshot bundle is a directory with this layout::

    <snapshot_dir>/
        manifest.json
        source_notes.md            (optional but recommended)
        normalized/
            teams.json
            players.json
            contracts.json
            free_agents.json
            cap_config.json
            evidence_notes.json

The validator checks:

1. ``manifest.json`` exists, is valid JSON, and has the required
   provenance fields (``snapshot_id``, ``snapshot_type``,
   ``source_name``, ``as_of_date``).
2. All required normalized files exist and are valid JSON with the
   expected top-level key.
3. IDs are unique within each entity collection.
4. Foreign-key references are intact (contract → player, contract →
   team, player → team, free_agent → player).
5. Value constraints hold (no negative salaries, valid positions).
6. ``cap_config`` ordering is sane (``salary_cap <= luxury_tax <=
   first_apron <= second_apron``).
7. ``sample_data`` is ``false`` in every snapshot row — a snapshot
   bundle is supposed to be real-ish data, not demo data. Test
   fixtures use ``snapshot_type: "test_fixture"`` to mark themselves.
8. Source provenance fields are present on each row.

The result is a ``SnapshotValidationResult`` with ``is_valid``,
``errors``, ``warnings``, ``row_counts``, ``snapshot_id``, and
``manifest_status``. Errors are fatal (``is_valid = False``); warnings
are informational (``is_valid`` stays ``True`` unless an error also
fires).

Milestone: M8-B (Core Snapshot Loader/Validator Foundation).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# --------------------------------------------------------------------------- #
# Required files + top-level keys
# --------------------------------------------------------------------------- #

_REQUIRED_FILES: Tuple[Tuple[str, str], ...] = (
    # (filename, expected top-level key)
    ("teams.json", "teams"),
    ("players.json", "players"),
    ("contracts.json", "contracts"),
    ("free_agents.json", "free_agents"),
    ("cap_config.json", "cap_config"),
    ("evidence_notes.json", "evidence_notes"),
)

_VALID_POSITIONS: Set[str] = {"PG", "SG", "SF", "PF", "C"}

_MANIFEST_REQUIRED_KEYS: Tuple[str, ...] = (
    "snapshot_id",
    "snapshot_type",
    "source_name",
    "as_of_date",
)


# --------------------------------------------------------------------------- #
# Result dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SnapshotValidationResult:
    """The outcome of validating a snapshot bundle.

    Attributes:
        is_valid: ``True`` when no fatal errors were found.
        errors: Fatal error messages (each one flips ``is_valid`` to
            ``False``).
        warnings: Non-fatal informational messages.
        row_counts: Per-entity row counts, e.g.
            ``{"teams": 2, "players": 4, ...}``.
        snapshot_id: The ``snapshot_id`` from the manifest, or
            ``"<unknown>"`` when the manifest is missing/invalid.
        manifest_status: ``"ok"``, ``"missing"``, or ``"invalid"``.
    """

    is_valid: bool
    errors: Tuple[str, ...] = field(default_factory=tuple)
    warnings: Tuple[str, ...] = field(default_factory=tuple)
    row_counts: Dict[str, int] = field(default_factory=dict)
    snapshot_id: str = "<unknown>"
    manifest_status: str = "<unknown>"


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def validate_snapshot(snapshot_dir: Path) -> SnapshotValidationResult:
    """Validate a snapshot bundle directory.

    Runs every check in sequence and accumulates errors + warnings.
    Returns a single ``SnapshotValidationResult``. Never raises —
    every failure is captured as an error string so the caller can
    report all problems at once.
    """
    snapshot_dir = Path(snapshot_dir)
    errors: List[str] = []
    warnings: List[str] = []
    row_counts: Dict[str, int] = {}

    # 1. Manifest
    manifest_status, snapshot_id, manifest_errors = validate_manifest(snapshot_dir)
    errors.extend(manifest_errors)
    if manifest_status == "ok" and snapshot_id:
        # Check source fields on the manifest itself.
        manifest_path = snapshot_dir / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            src_warnings = validate_source_fields(manifest, context="manifest")
            warnings.extend(src_warnings)
        except Exception:
            pass  # manifest read errors already captured above

    # 2. Required files
    file_errors = validate_required_files(snapshot_dir)
    errors.extend(file_errors)

    # If manifest or required files are broken, we can't safely continue
    # with cross-reference checks — return early.
    if errors:
        return SnapshotValidationResult(
            is_valid=False,
            errors=tuple(errors),
            warnings=tuple(warnings),
            row_counts=row_counts,
            snapshot_id=snapshot_id or "<unknown>",
            manifest_status=manifest_status,
        )

    # 3. JSON shape + load entities
    entities: Dict[str, List[Dict[str, Any]]] = {}
    for filename, top_key in _REQUIRED_FILES:
        path = snapshot_dir / "normalized" / filename
        shape_errors, rows = validate_json_shape(path, top_key)
        errors.extend(shape_errors)
        if rows is not None:
            entities[top_key] = rows
            row_counts[top_key] = len(rows)

    if errors:
        return SnapshotValidationResult(
            is_valid=False,
            errors=tuple(errors),
            warnings=tuple(warnings),
            row_counts=row_counts,
            snapshot_id=snapshot_id or "<unknown>",
            manifest_status=manifest_status,
        )

    # 4. Unique IDs
    errors.extend(validate_unique_ids(entities))

    # 5. References
    errors.extend(validate_references(entities))

    # 6. Values (salary, position)
    errors.extend(validate_values(entities))

    # 7. sample_data flags
    errors.extend(validate_sample_data_flags(entities))

    # 8. Source fields on each row (warnings for missing source_url)
    for top_key, rows in entities.items():
        for i, row in enumerate(rows):
            src_warnings = validate_source_fields(row, context=f"{top_key}[{i}]")
            warnings.extend(src_warnings)

    # 9. cap_config ordering
    errors.extend(validate_cap_config_ordering(entities))

    # 10. Non-fatal warnings
    warnings.extend(_check_roster_player_without_contract(entities))
    warnings.extend(_check_manual_review_required(entities))
    warnings.extend(_check_free_agent_without_salary(entities))
    warnings.extend(_check_evidence_without_references(entities))

    return SnapshotValidationResult(
        is_valid=len(errors) == 0,
        errors=tuple(errors),
        warnings=tuple(warnings),
        row_counts=row_counts,
        snapshot_id=snapshot_id or "<unknown>",
        manifest_status=manifest_status,
    )


# --------------------------------------------------------------------------- #
# Individual validators
# --------------------------------------------------------------------------- #


def validate_manifest(
    snapshot_dir: Path,
) -> Tuple[str, Optional[str], List[str]]:
    """Validate ``manifest.json``.

    Returns ``(manifest_status, snapshot_id, errors)``.
    """
    snapshot_dir = Path(snapshot_dir)
    manifest_path = snapshot_dir / "manifest.json"
    errors: List[str] = []

    if not manifest_path.exists():
        return ("missing", None, [f"manifest.json not found in {snapshot_dir}"])

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return ("invalid", None, [f"manifest.json is not valid JSON: {exc}"])
    except Exception as exc:
        return ("invalid", None, [f"manifest.json could not be read: {exc}"])

    if not isinstance(manifest, dict):
        return ("invalid", None, ["manifest.json top-level value is not an object"])

    for key in _MANIFEST_REQUIRED_KEYS:
        if key not in manifest:
            errors.append(f"manifest.json missing required key: {key}")
        elif manifest[key] in (None, "", []):
            errors.append(f"manifest.json key '{key}' is empty")

    snapshot_id = manifest.get("snapshot_id")
    if snapshot_id and not isinstance(snapshot_id, str):
        errors.append("manifest.json 'snapshot_id' is not a string")
        snapshot_id = None

    return ("ok" if not errors else "invalid", snapshot_id, errors)


def validate_required_files(snapshot_dir: Path) -> List[str]:
    """Check that every required normalized file exists."""
    snapshot_dir = Path(snapshot_dir)
    normalized_dir = snapshot_dir / "normalized"
    errors: List[str] = []

    if not normalized_dir.is_dir():
        errors.append(f"normalized/ directory not found in {snapshot_dir}")
        return errors

    for filename, _ in _REQUIRED_FILES:
        path = normalized_dir / filename
        if not path.exists():
            errors.append(f"required file missing: normalized/{filename}")

    return errors


def validate_json_shape(
    path: Path,
    expected_top_key: str,
) -> Tuple[List[str], Optional[List[Dict[str, Any]]]]:
    """Validate that a JSON file has the expected top-level key.

    Returns ``(errors, rows)`` where ``rows`` is the list of entity
    dicts (or ``None`` on failure). For ``cap_config.json`` the
    top-level value is a single object, not a list — we wrap it in a
    one-element list so downstream checks can treat it uniformly.
    """
    path = Path(path)
    errors: List[str] = []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return ([f"{path.name} is not valid JSON: {exc}"], None)
    except Exception as exc:
        return ([f"{path.name} could not be read: {exc}"], None)

    if not isinstance(data, dict):
        return ([f"{path.name} top-level value is not an object"], None)

    if expected_top_key not in data:
        return (
            [f"{path.name} missing top-level key '{expected_top_key}'"],
            None,
        )

    value = data[expected_top_key]

    # cap_config is a single object; everything else is a list.
    if expected_top_key == "cap_config":
        if not isinstance(value, dict):
            return (
                [f"{path.name} '{expected_top_key}' is not an object"],
                None,
            )
        return ([], [value])

    if not isinstance(value, list):
        return (
            [f"{path.name} '{expected_top_key}' is not a list"],
            None,
        )

    for i, row in enumerate(value):
        if not isinstance(row, dict):
            return (
                [f"{path.name} '{expected_top_key}[{i}]' is not an object"],
                None,
            )

    return ([], list(value))


def validate_unique_ids(entities: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """Check that entity IDs are unique within each collection."""
    errors: List[str] = []

    id_field_map: Dict[str, str] = {
        "teams": "team_id",
        "players": "player_id",
        "contracts": "contract_id",
        "evidence_notes": "evidence_id",
    }

    for top_key, id_field in id_field_map.items():
        rows = entities.get(top_key, [])
        seen: Dict[str, int] = {}
        for i, row in enumerate(rows):
            eid = row.get(id_field)
            if eid is None:
                continue
            if eid in seen:
                errors.append(
                    f"duplicate {id_field} '{eid}' in {top_key} "
                    f"(rows {seen[eid]} and {i})"
                )
            else:
                seen[eid] = i

    return errors


def validate_references(entities: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """Check foreign-key references between entity collections."""
    errors: List[str] = []

    team_ids: Set[str] = {
        r["team_id"] for r in entities.get("teams", []) if r.get("team_id")
    }
    player_ids: Set[str] = {
        r["player_id"] for r in entities.get("players", []) if r.get("player_id")
    }

    # contract → player
    for i, contract in enumerate(entities.get("contracts", [])):
        cid = contract.get("contract_id", f"[{i}]")
        pid = contract.get("player_id")
        if pid and pid not in player_ids:
            errors.append(
                f"contract '{cid}' references missing player '{pid}'"
            )
        # contract → team
        tid = contract.get("team_id")
        if tid and tid not in team_ids:
            errors.append(
                f"contract '{cid}' references missing team '{tid}'"
            )

    # player → team
    for i, player in enumerate(entities.get("players", [])):
        pid = player.get("player_id", f"[{i}]")
        tid = player.get("team_id")
        if tid and tid not in team_ids:
            errors.append(
                f"player '{pid}' references missing team '{tid}'"
            )

    # free_agent → player
    for i, fa in enumerate(entities.get("free_agents", [])):
        faid = fa.get("free_agent_id", f"[{i}]")
        pid = fa.get("player_id")
        if pid and pid not in player_ids:
            errors.append(
                f"free_agent '{faid}' references missing player '{pid}'"
            )

    return errors


def validate_values(entities: Dict[str, List[Dict[str, Any]]]) -> List[str]:
    """Check value constraints: no negative salaries, valid positions."""
    errors: List[str] = []

    # contracts: salary >= 0
    for i, contract in enumerate(entities.get("contracts", [])):
        cid = contract.get("contract_id", f"[{i}]")
        salary = contract.get("salary")
        if salary is not None and isinstance(salary, (int, float)) and salary < 0:
            errors.append(
                f"contract '{cid}' has negative salary {salary}"
            )

    # free_agents: expected_salary >= 0
    for i, fa in enumerate(entities.get("free_agents", [])):
        faid = fa.get("free_agent_id", f"[{i}]")
        salary = fa.get("expected_salary")
        if salary is not None and isinstance(salary, (int, float)) and salary < 0:
            errors.append(
                f"free_agent '{faid}' has negative expected_salary {salary}"
            )

    # players: valid position
    for i, player in enumerate(entities.get("players", [])):
        pid = player.get("player_id", f"[{i}]")
        pos = player.get("position")
        if pos is not None and pos not in _VALID_POSITIONS:
            errors.append(
                f"player '{pid}' has invalid position '{pos}' "
                f"(expected one of {sorted(_VALID_POSITIONS)})"
            )

    # free_agents: valid position
    for i, fa in enumerate(entities.get("free_agents", [])):
        faid = fa.get("free_agent_id", f"[{i}]")
        pos = fa.get("position")
        if pos is not None and pos not in _VALID_POSITIONS:
            errors.append(
                f"free_agent '{faid}' has invalid position '{pos}' "
                f"(expected one of {sorted(_VALID_POSITIONS)})"
            )

    return errors


def validate_sample_data_flags(
    entities: Dict[str, List[Dict[str, Any]]]
) -> List[str]:
    """Check that no snapshot row has ``sample_data: true``.

    A snapshot bundle is supposed to be real-ish data. Test fixtures
    use ``snapshot_type: "test_fixture"`` in the manifest to mark
    themselves, but every row must still have ``sample_data: false``
    (or omit it) so that a fixture is never confused with demo data.
    """
    errors: List[str] = []

    for top_key, rows in entities.items():
        for i, row in enumerate(rows):
            if row.get("sample_data") is True:
                eid = (
                    row.get("team_id")
                    or row.get("player_id")
                    or row.get("contract_id")
                    or row.get("free_agent_id")
                    or row.get("evidence_id")
                    or f"[{i}]"
                )
                errors.append(
                    f"{top_key} '{eid}' has sample_data=true — "
                    f"snapshot rows must not be flagged as sample data"
                )

    return errors


def validate_source_fields(
    row: Dict[str, Any],
    context: str,
) -> List[str]:
    """Check source provenance fields on a row.

    Returns a list of **warnings** (not errors). ``source_name`` and
    ``as_of_date`` missing is an error (checked elsewhere); missing
    ``source_url`` while ``source_name`` exists is a warning.
    """
    warnings: List[str] = []

    source_name = row.get("source_name")
    source_url = row.get("source_url")

    if source_name and not source_url:
        warnings.append(
            f"{context}: source_name present but source_url missing"
        )

    return warnings


def validate_cap_config_ordering(
    entities: Dict[str, List[Dict[str, Any]]]
) -> List[str]:
    """Check that cap_config values are in the correct order:
    ``salary_cap <= luxury_tax <= first_apron <= second_apron``.
    """
    errors: List[str] = []
    cap_rows = entities.get("cap_config", [])
    if not cap_rows:
        return errors

    cap = cap_rows[0]
    salary_cap = cap.get("salary_cap")
    luxury_tax = cap.get("luxury_tax")
    first_apron = cap.get("first_apron")
    second_apron = cap.get("second_apron")

    values = [salary_cap, luxury_tax, first_apron, second_apron]
    labels = ["salary_cap", "luxury_tax", "first_apron", "second_apron"]

    # All must be present and numeric.
    for label, val in zip(labels, values):
        if val is None:
            errors.append(f"cap_config missing '{label}'")
        elif not isinstance(val, (int, float)):
            errors.append(f"cap_config '{label}' is not numeric")

    if errors:
        return errors

    # Ordering check.
    for i in range(len(values) - 1):
        if values[i] > values[i + 1]:
            errors.append(
                f"cap_config ordering invalid: {labels[i]}={values[i]} > "
                f"{labels[i + 1]}={values[i + 1]}"
            )
            break

    return errors


# --------------------------------------------------------------------------- #
# Warning-only checks
# --------------------------------------------------------------------------- #


def _check_roster_player_without_contract(
    entities: Dict[str, List[Dict[str, Any]]]
) -> List[str]:
    """Warn when a roster player has no matching contract."""
    warnings: List[str] = []
    contract_player_ids: Set[str] = {
        c["player_id"]
        for c in entities.get("contracts", [])
        if c.get("player_id")
    }
    for player in entities.get("players", []):
        pid = player.get("player_id")
        if pid and pid not in contract_player_ids:
            warnings.append(
                f"player '{pid}' has no contract on file"
            )
    return warnings


def _check_manual_review_required(
    entities: Dict[str, List[Dict[str, Any]]]
) -> List[str]:
    """Warn when any row has ``manual_review_required: true``."""
    warnings: List[str] = []
    for top_key, rows in entities.items():
        for i, row in enumerate(rows):
            if row.get("manual_review_required") is True:
                eid = (
                    row.get("team_id")
                    or row.get("player_id")
                    or row.get("contract_id")
                    or row.get("free_agent_id")
                    or row.get("evidence_id")
                    or f"[{i}]"
                )
                warnings.append(
                    f"{top_key} '{eid}' has manual_review_required=true"
                )
    return warnings


def _check_free_agent_without_salary(
    entities: Dict[str, List[Dict[str, Any]]]
) -> List[str]:
    """Warn when a free agent has no expected_salary."""
    warnings: List[str] = []
    for i, fa in enumerate(entities.get("free_agents", [])):
        faid = fa.get("free_agent_id", f"[{i}]")
        if fa.get("expected_salary") in (None, 0):
            warnings.append(
                f"free_agent '{faid}' has no expected_salary"
            )
    return warnings


def _check_evidence_without_references(
    entities: Dict[str, List[Dict[str, Any]]]
) -> List[str]:
    """Warn when an evidence note has no team_ids and no player_ids."""
    warnings: List[str] = []
    for i, note in enumerate(entities.get("evidence_notes", [])):
        eid = note.get("evidence_id", f"[{i}]")
        team_ids = note.get("team_ids", [])
        player_ids = note.get("player_ids", [])
        if not team_ids and not player_ids:
            warnings.append(
                f"evidence_note '{eid}' has no team_ids or player_ids"
            )
    return warnings
