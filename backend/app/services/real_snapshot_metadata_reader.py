"""Read-only service for loading real snapshot metadata.

M10-D1: Backend Real Snapshot Metadata Read Model.

This service is intentionally READ-ONLY. It loads four JSON files from a
curated real snapshot directory, validates them against their JSON schemas,
verifies file hashes against source_manifest.file_hashes, and returns a
sanitized projection suitable for the ``GET /api/snapshots/metadata``
endpoint.

Hard guarantees:

- Read-only: never mutates any file on disk.
- Explicit mode: callers MUST pass ``snapshot_mode="real_snapshot"``;
  any other mode raises ``RealSnapshotModeError`` before reading.
- Hard error on any problem (missing file, schema mismatch, hash mismatch,
  cross-reference mismatch). There is NO silent fallback to the demo
  snapshot.
- Response projection strips raw source_manifest internals (file_hashes,
  per_file_sources, file system paths) and excludes any roster/contract/
  salary/logo/branding fields.
- The service does NOT call any LLM, external API, or network.
- The service does NOT trigger any trade/signing/execute path.

The service is independent of ``snapshot_loader.py`` (which loads the demo
historical snapshot with full contract/cap data). M10-D1 only exposes
metadata (team identity + visual accent metadata), never cap data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class RealSnapshotMetadataError(Exception):
    """Base error for real snapshot metadata failures (hard error)."""


class RealSnapshotModeError(RealSnapshotMetadataError):
    """Raised when snapshot_mode is not 'real_snapshot'."""


class RealSnapshotNotFoundError(RealSnapshotMetadataError):
    """Raised when the real snapshot directory or a required file is missing."""


class RealSnapshotSchemaError(RealSnapshotMetadataError):
    """Raised when a file fails JSON Schema validation."""


class RealSnapshotHashError(RealSnapshotMetadataError):
    """Raised when a file's SHA-256 does not match source_manifest.file_hashes."""


class RealSnapshotCrossReferenceError(RealSnapshotMetadataError):
    """Raised when team_id/abbreviation cross-references are inconsistent."""


# --------------------------------------------------------------------------- #
# DTOs (response projection)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TeamVisualMetadata:
    """Sanitized per-team visual metadata (non-official UI accents)."""

    accent_color: str
    secondary_accent_color: str
    badge_style: str
    no_official_branding: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accent_color": self.accent_color,
            "secondary_accent_color": self.secondary_accent_color,
            "badge_style": self.badge_style,
            "no_official_branding": self.no_official_branding,
        }


@dataclass(frozen=True)
class TeamMetadata:
    """Team identity merged with its visual metadata."""

    team_id: str
    city: str
    name: str
    abbreviation: str
    conference: str
    division: str
    visual_metadata: TeamVisualMetadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": self.team_id,
            "city": self.city,
            "name": self.name,
            "abbreviation": self.abbreviation,
            "conference": self.conference,
            "division": self.division,
            "visual_metadata": self.visual_metadata.to_dict(),
        }


@dataclass(frozen=True)
class RealSnapshotMetadata:
    """Safe projection returned to API consumers."""

    snapshot_id: str
    snapshot_mode: str
    snapshot_type: str
    season: str
    as_of_date: str
    freshness_label: str
    data_freshness_warning: str
    source_name: str
    manual_review_required: bool
    live_eligible: bool
    no_official_branding: bool
    data_categories: List[str]
    limitations: List[str]
    teams: List[TeamMetadata] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_mode": self.snapshot_mode,
            "snapshot_type": self.snapshot_type,
            "season": self.season,
            "as_of_date": self.as_of_date,
            "freshness_label": self.freshness_label,
            "data_freshness_warning": self.data_freshness_warning,
            "source_name": self.source_name,
            "manual_review_required": self.manual_review_required,
            "live_eligible": self.live_eligible,
            "no_official_branding": self.no_official_branding,
            "data_categories": list(self.data_categories),
            "limitations": list(self.limitations),
            "teams": [t.to_dict() for t in self.teams],
        }


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #


REAL_SNAPSHOT_ID = "nba_real_2026_preoffseason_v1"
REQUIRED_SNAPSHOT_MODE = "real_snapshot"

REQUIRED_FILES = [
    "manifest.json",
    "source_manifest.json",
    "normalized/teams.json",
    "normalized/team_visual_metadata.json",
]

# File-relative paths used in source_manifest.file_hashes
HASH_KEY_TEAMS = "normalized/teams.json"
HASH_KEY_VISUAL = "normalized/team_visual_metadata.json"


# --------------------------------------------------------------------------- #
# Reader
# --------------------------------------------------------------------------- #


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "backend").is_dir() and (parent / "data").is_dir() and (parent / "schema").is_dir():
            return parent
    return here.parents[3]


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise RealSnapshotSchemaError(
            f"Invalid JSON in {path.name}: {exc}"
        ) from exc
    except OSError as exc:
        raise RealSnapshotNotFoundError(
            f"Could not read {path}: {exc}"
        ) from exc


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate(doc: Any, schema: Dict[str, Any], label: str) -> None:
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        raise RealSnapshotSchemaError(
            f"Schema validation failed for {label}: {exc.message}"
        ) from exc


def load_real_snapshot_metadata(
    snapshot_mode: str,
    data_dir: Optional[Path] = None,
    schema_dir: Optional[Path] = None,
) -> RealSnapshotMetadata:
    """Load, validate, and project real snapshot metadata.

    Args:
        snapshot_mode: MUST be the literal string ``"real_snapshot"``.
            Any other value (including "demo", "live", "current", "latest")
            raises ``RealSnapshotModeError`` BEFORE any disk I/O.
        data_dir: repo-root-relative ``data/`` directory. Auto-discovered if None.
        schema_dir: directory containing the JSON schemas. Auto-discovered if None.

    Returns:
        ``RealSnapshotMetadata`` — a frozen read-only DTO. Call ``.to_dict()``
        for a JSON-serializable projection.

    Raises:
        RealSnapshotModeError: snapshot_mode is not "real_snapshot".
        RealSnapshotNotFoundError: snapshot directory or a required file is missing.
        RealSnapshotSchemaError: any file fails schema validation.
        RealSnapshotHashError: SHA-256 mismatch.
        RealSnapshotCrossReferenceError: team_id/abbreviation mismatch between
            teams.json and team_visual_metadata.json.
    """
    if snapshot_mode != REQUIRED_SNAPSHOT_MODE:
        raise RealSnapshotModeError(
            f"snapshot_mode must be '{REQUIRED_SNAPSHOT_MODE}', got '{snapshot_mode}'. "
            "This endpoint does not serve demo/live/current/latest modes and does not "
            "fall back to demo."
        )

    repo_root = _find_repo_root()
    data_dir = data_dir or (repo_root / "data")
    schema_dir = schema_dir or (repo_root / "schema")

    snapshot_dir = data_dir / "snapshots" / REAL_SNAPSHOT_ID
    if not snapshot_dir.is_dir():
        raise RealSnapshotNotFoundError(
            f"Real snapshot directory not found: {snapshot_dir}"
        )

    # Load schemas
    source_manifest_schema = _load_json(schema_dir / "source_manifest_schema.json")
    real_manifest_schema = _load_json(schema_dir / "real_snapshot_manifest_schema.json")
    teams_schema = _load_json(schema_dir / "teams_schema.json")
    visual_schema = _load_json(schema_dir / "team_visual_metadata_schema.json")

    # Check required files exist
    paths: Dict[str, Path] = {}
    for rel in REQUIRED_FILES:
        p = snapshot_dir / rel
        if not p.is_file():
            raise RealSnapshotNotFoundError(
                f"Required real snapshot file missing: {rel} (expected at {p})"
            )
        paths[rel] = p

    # Load files
    manifest = _load_json(paths["manifest.json"])
    source_manifest = _load_json(paths["source_manifest.json"])
    teams_doc = _load_json(paths["normalized/teams.json"])
    visual_doc = _load_json(paths["normalized/team_visual_metadata.json"])

    # Validate schemas
    _validate(manifest, real_manifest_schema, "manifest.json")
    _validate(source_manifest, source_manifest_schema, "source_manifest.json")
    _validate(teams_doc, teams_schema, "normalized/teams.json")
    _validate(visual_doc, visual_schema, "normalized/team_visual_metadata.json")

    # Validate file hashes against source_manifest.file_hashes
    file_hashes = source_manifest.get("file_hashes", {})
    for key, rel_path in [(HASH_KEY_TEAMS, "normalized/teams.json"),
                           (HASH_KEY_VISUAL, "normalized/team_visual_metadata.json")]:
        expected_entry = file_hashes.get(key)
        if not expected_entry:
            raise RealSnapshotHashError(
                f"source_manifest.file_hashes missing entry for '{key}'"
            )
        if not isinstance(expected_entry, str) or not expected_entry.startswith("sha256:"):
            raise RealSnapshotHashError(
                f"source_manifest.file_hashes['{key}'] must be 'sha256:<hex>', got {expected_entry!r}"
            )
        expected_hex = expected_entry[len("sha256:"):]
        actual_hex = _sha256_file(paths[rel_path])
        if actual_hex != expected_hex:
            raise RealSnapshotHashError(
                f"Hash mismatch for {rel_path}: expected sha256:{expected_hex}, got sha256:{actual_hex}"
            )

    # Cross-reference: build visual index by team_id
    visual_by_team: Dict[str, Dict[str, Any]] = {}
    for entry in visual_doc["visual_metadata"]:
        tid = entry["team_id"]
        if tid in visual_by_team:
            raise RealSnapshotCrossReferenceError(
                f"Duplicate team_id '{tid}' in team_visual_metadata.json"
            )
        visual_by_team[tid] = entry

    teams_list: List[TeamMetadata] = []
    for team in teams_doc["teams"]:
        tid = team["team_id"]
        if tid not in visual_by_team:
            raise RealSnapshotCrossReferenceError(
                f"team_id '{tid}' present in teams.json but missing from team_visual_metadata.json"
            )
        v = visual_by_team[tid]
        if v["abbreviation"] != team["abbreviation"]:
            raise RealSnapshotCrossReferenceError(
                f"Abbreviation mismatch for {tid}: teams.json has '{team['abbreviation']}', "
                f"team_visual_metadata.json has '{v['abbreviation']}'"
            )
        if v.get("no_official_branding") is not True:
            raise RealSnapshotCrossReferenceError(
                f"team_visual_metadata entry for {tid} must have no_official_branding=true"
            )
        teams_list.append(
            TeamMetadata(
                team_id=tid,
                city=team["city"],
                name=team["name"],
                abbreviation=team["abbreviation"],
                conference=team["conference"],
                division=team["division"],
                visual_metadata=TeamVisualMetadata(
                    accent_color=v["accent_color"],
                    secondary_accent_color=v["secondary_accent_color"],
                    badge_style=v["badge_style"],
                    no_official_branding=True,
                ),
            )
        )

    # Reverse check: visual entries must all be in teams
    team_ids = {t["team_id"] for t in teams_doc["teams"]}
    for tid in visual_by_team:
        if tid not in team_ids:
            raise RealSnapshotCrossReferenceError(
                f"team_id '{tid}' present in team_visual_metadata.json but missing from teams.json"
            )

    if len(teams_list) != 30:
        raise RealSnapshotCrossReferenceError(
            f"Expected 30 teams after merge, got {len(teams_list)}"
        )

    # Safety assertions on source_manifest
    if source_manifest.get("live_eligible") is not False:
        raise RealSnapshotSchemaError(
            "source_manifest.live_eligible must be false for M10 real snapshots"
        )
    if source_manifest.get("manual_review_required") is not True:
        raise RealSnapshotSchemaError(
            "source_manifest.manual_review_required must be true"
        )

    no_official_branding_flag = bool(visual_doc.get("no_official_branding", False))

    return RealSnapshotMetadata(
        snapshot_id=manifest["snapshot_id"],
        snapshot_mode=REQUIRED_SNAPSHOT_MODE,
        snapshot_type=manifest["snapshot_type"],
        season=manifest["season"],
        as_of_date=manifest["as_of_date"],
        freshness_label=source_manifest["freshness_label"],
        data_freshness_warning=source_manifest["data_freshness_warning"],
        source_name=source_manifest["source_name"],
        manual_review_required=bool(manifest.get("manual_review_required", True)),
        live_eligible=False,
        no_official_branding=no_official_branding_flag,
        data_categories=list(source_manifest.get("data_categories", [])),
        limitations=list(source_manifest.get("limitations", [])),
        teams=teams_list,
    )
