"""Snapshot bundle loader (M8-B Core).

Loads a validated snapshot bundle from disk into a ``SnapshotBundle``
dataclass. The loader is a **pure consumer** — it reads JSON, runs the
validator (when ``validate=True``), and returns raw dicts. It does NOT
convert to the existing ``PlayerContract`` / ``RosterPlayer`` /
``EvidenceNote`` dataclasses yet (that adaptation is deferred to
M8-C). It does NOT call any external API, does NOT call any LLM, does
NOT use MCP, and does NOT write any data file.

A snapshot bundle is resolved by ``snapshot_id`` from a data root
directory (default: ``<repo_root>/data/snapshots/<snapshot_id>``). The
loader also accepts a direct ``Path`` via ``resolve_snapshot_dir`` for
testing.

Milestone: M8-B (Core Snapshot Loader/Validator Foundation).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.services.snapshot_validator import (
    SnapshotValidationResult,
    validate_snapshot,
)


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class SnapshotError(Exception):
    """Base class for all snapshot loading errors."""


class SnapshotNotFoundError(SnapshotError):
    """Raised when a snapshot directory does not exist."""


class SnapshotValidationError(SnapshotError):
    """Raised when a snapshot fails validation during loading."""

    def __init__(self, result: SnapshotValidationResult) -> None:
        self.result = result
        super().__init__(
            f"snapshot '{result.snapshot_id}' failed validation: "
            f"{len(result.errors)} error(s)"
        )


class SnapshotLoadError(SnapshotError):
    """Raised when a snapshot passes validation but cannot be loaded
    (e.g. a file disappears between validation and read)."""


# --------------------------------------------------------------------------- #
# Bundle dataclass
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SnapshotBundle:
    """A loaded snapshot bundle.

    In M8-B, the entity fields are **raw dicts** (not converted to
    existing domain dataclasses). This keeps the loader decoupled from
    the demo-mode services. M8-C will adapt these dicts into the
    domain models and wire ``DATA_MODE=snapshot`` into the main
    pipeline.

    Attributes:
        snapshot_id: The snapshot identifier from the manifest.
        manifest: The raw manifest dict.
        teams: List of team dicts.
        players: List of player dicts.
        contracts: List of contract dicts.
        free_agents: List of free-agent dicts.
        cap_config: The cap config dict (single object).
        evidence_notes: List of evidence-note dicts.
        validation_result: The ``SnapshotValidationResult`` from the
            validator (always present, even when ``validate=False`` —
            in that case it is a synthetic "ok" result).
        data_mode: Always ``"snapshot"`` for a loaded bundle.
    """

    snapshot_id: str
    manifest: Dict[str, Any]
    teams: List[Dict[str, Any]] = field(default_factory=list)
    players: List[Dict[str, Any]] = field(default_factory=list)
    contracts: List[Dict[str, Any]] = field(default_factory=list)
    free_agents: List[Dict[str, Any]] = field(default_factory=list)
    cap_config: Dict[str, Any] = field(default_factory=dict)
    evidence_notes: List[Dict[str, Any]] = field(default_factory=list)
    validation_result: SnapshotValidationResult = field(
        default_factory=lambda: SnapshotValidationResult(is_valid=True)
    )
    data_mode: str = "snapshot"


# --------------------------------------------------------------------------- #
# Resolution
# --------------------------------------------------------------------------- #


def _default_data_root() -> Path:
    """Return the default data root: ``<repo_root>/data/snapshots``."""
    here = Path(__file__).resolve()
    # backend/app/services/snapshot_loader.py -> repo root is parents[3]
    for parent in here.parents:
        if (parent / "backend").is_dir() and (parent / "data").is_dir():
            return parent / "data" / "snapshots"
    return here.parents[3] / "data" / "snapshots"


def resolve_snapshot_dir(
    snapshot_id: str,
    data_root: Optional[Path] = None,
) -> Path:
    """Resolve a snapshot directory by ``snapshot_id``.

    Looks for ``<data_root>/<snapshot_id>/``. Raises
    ``SnapshotNotFoundError`` if the directory does not exist.
    """
    root = Path(data_root) if data_root is not None else _default_data_root()
    snapshot_dir = root / snapshot_id
    if not snapshot_dir.is_dir():
        raise SnapshotNotFoundError(
            f"snapshot directory not found: {snapshot_dir}"
        )
    return snapshot_dir


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def load_normalized_json(
    snapshot_dir: Path,
    filename: str,
    top_key: str,
) -> Any:
    """Load a single normalized JSON file and return the value under
    ``top_key``.

    Raises ``SnapshotLoadError`` if the file cannot be read or parsed.
    """
    path = Path(snapshot_dir) / "normalized" / filename
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SnapshotLoadError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SnapshotLoadError(f"invalid JSON in {path}: {exc}") from exc
    except Exception as exc:
        raise SnapshotLoadError(f"could not read {path}: {exc}") from exc

    if not isinstance(data, dict) or top_key not in data:
        raise SnapshotLoadError(
            f"{path} missing top-level key '{top_key}'"
        )

    return data[top_key]


def load_snapshot(
    snapshot_id: str,
    data_root: Optional[Path] = None,
    validate: bool = True,
) -> SnapshotBundle:
    """Load a snapshot bundle by ``snapshot_id``.

    Steps:
    1. Resolve the snapshot directory.
    2. If ``validate=True``, run ``validate_snapshot`` and raise
       ``SnapshotValidationError`` on failure.
    3. Load each normalized JSON file.
    4. Return a ``SnapshotBundle``.

    The loader never writes to disk and never calls any external API.
    """
    snapshot_dir = resolve_snapshot_dir(snapshot_id, data_root)

    # 1. Validate
    if validate:
        result = validate_snapshot(snapshot_dir)
        if not result.is_valid:
            raise SnapshotValidationError(result)
    else:
        result = SnapshotValidationResult(
            is_valid=True,
            snapshot_id=snapshot_id,
            manifest_status="skipped",
        )

    # 2. Load manifest
    manifest_path = snapshot_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SnapshotLoadError(
            f"could not load manifest.json: {exc}"
        ) from exc

    # 3. Load entities
    try:
        teams = load_normalized_json(snapshot_dir, "teams.json", "teams")
        players = load_normalized_json(snapshot_dir, "players.json", "players")
        contracts = load_normalized_json(
            snapshot_dir, "contracts.json", "contracts"
        )
        free_agents = load_normalized_json(
            snapshot_dir, "free_agents.json", "free_agents"
        )
        cap_config = load_normalized_json(
            snapshot_dir, "cap_config.json", "cap_config"
        )
        evidence_notes = load_normalized_json(
            snapshot_dir, "evidence_notes.json", "evidence_notes"
        )
    except SnapshotLoadError:
        raise
    except Exception as exc:
        raise SnapshotLoadError(
            f"unexpected error loading entities: {exc}"
        ) from exc

    return SnapshotBundle(
        snapshot_id=manifest.get("snapshot_id", snapshot_id),
        manifest=manifest,
        teams=list(teams) if isinstance(teams, list) else [],
        players=list(players) if isinstance(players, list) else [],
        contracts=list(contracts) if isinstance(contracts, list) else [],
        free_agents=list(free_agents) if isinstance(free_agents, list) else [],
        cap_config=cap_config if isinstance(cap_config, dict) else {},
        evidence_notes=(
            list(evidence_notes) if isinstance(evidence_notes, list) else []
        ),
        validation_result=result,
        data_mode="snapshot",
    )
