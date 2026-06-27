"""Read-only service for loading player/roster metadata from a real snapshot.

M10-F2: Backend Player/Roster Read Model (synthetic fixture / no real data).

This service is intentionally READ-ONLY. It loads player_identities.json and
roster_memberships.json from a curated real snapshot directory (or a synthetic
tmp_path fixture for tests), validates them against their JSON schemas,
verifies file hashes against source_manifest.file_hashes, cross-references
player_ids and team_ids, checks lineage/governance flags, and returns a
sanitized read-only projection suitable for a future
``GET /api/snapshots/player-roster-metadata`` endpoint.

Hard guarantees (M10-F1 design gate):

- Read-only: never mutates any file on disk.
- Explicit mode: callers MUST pass ``snapshot_mode="real_snapshot"``; any other
  mode raises ``PlayerRosterModeError`` before reading.
- No real data in this milestone: F2 ships with synthetic tmp_path tests only.
  The real snapshot directory currently does not contain player_identities.json
  or roster_memberships.json; attempting to load against the real snapshot
  raises ``PlayerRosterNotFoundError``, which is the expected behavior until
  F3/F4 approve and land pilot data.
- Hard error on any problem (missing file, schema mismatch, hash mismatch,
  cross-reference mismatch, forbidden source_type, stale data, governance
  flags). There is NO silent fallback to the demo snapshot.
- Response projection excludes any salary/contract/cap, injury/medical,
  rumor/scouting, live/current/latest, depth-chart/minutes/role projection,
  trade eligibility, mutation verbs, logo/branding fields.
- The service does NOT call any LLM, external API, or network.
- The service does NOT trigger any trade/signing/execute path.
- The service does NOT import from the Agent, NL preview, trade, or signing
  modules.

The service is independent of ``snapshot_loader.py`` (which loads the demo
historical snapshot with full contract/cap data). F2 exposes only identity
and roster-membership metadata, never cap/salary/contract data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import jsonschema


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class PlayerRosterMetadataError(Exception):
    """Base error for player/roster metadata failures (hard error)."""


class PlayerRosterModeError(PlayerRosterMetadataError):
    """Raised when snapshot_mode is not 'real_snapshot'."""


class PlayerRosterNotFoundError(PlayerRosterMetadataError):
    """Raised when the snapshot directory or a required file is missing."""


class PlayerRosterSchemaError(PlayerRosterMetadataError):
    """Raised when a file fails JSON Schema validation or governance checks."""


class PlayerRosterHashError(PlayerRosterMetadataError):
    """Raised when a file's SHA-256 does not match source_manifest.file_hashes."""


class PlayerRosterCrossReferenceError(PlayerRosterMetadataError):
    """Raised when player_id/team_id cross-references are inconsistent."""


class PlayerRosterStaleDataError(PlayerRosterMetadataError):
    """Raised when snapshot data is past stale_after_date."""


class PlayerRosterForbiddenFieldError(PlayerRosterMetadataError):
    """Raised when forbidden fields (salary/contract/etc.) are detected."""


class PlayerRosterSourceError(PlayerRosterMetadataError):
    """Raised when source_type/source_manifest entries are invalid."""


# --------------------------------------------------------------------------- #
# Forbidden key sets (defense in depth beyond schema propertyNames)
# --------------------------------------------------------------------------- #


FORBIDDEN_TOP_LEVEL_KEYS: frozenset[str] = frozenset({
    "salary", "salaries", "contract", "contracts", "cap_hold", "guarantee",
    "guarantee_amount", "cap_sheet", "cap_sheets",
    "injury", "injuries", "injury_status", "medical", "medical_status",
    "health", "availability", "real_time_availability",
    "rumors", "rumor", "scouting_opinion", "scouting_opinions",
    "live_status", "current_roster", "latest_roster", "latest_data",
    "live_data", "current_salaries", "real_time_data", "active_now",
    "projected_depth_chart", "depth_chart", "minutes_projection",
    "role_projection", "trade_eligibility", "no_trade_clause",
    "trade_restriction", "starter", "bench_role", "rotation_role",
    "headshot", "headshot_url", "player_image", "photo_url",
    "official_headshot", "logo_path", "logo_url", "official_logo",
    "nba_logo", "team_logo", "mascot_image",
    "execute", "apply", "commit", "mutate", "write", "persist", "save",
    "delete", "update", "submit", "auto_execute", "auto_approve",
    "social_media", "agent", "agent_representation",
    "personal_sensitive_info",
})

FORBIDDEN_PLAYER_KEYS: frozenset[str] = FORBIDDEN_TOP_LEVEL_KEYS

FORBIDDEN_MEMBERSHIP_KEYS: frozenset[str] = frozenset(
    FORBIDDEN_TOP_LEVEL_KEYS
    | {
        "inactive", "waived", "traded", "suspended", "injured",
        "questionable", "probable", "day_to_day", "available",
        "unavailable", "current", "latest", "active",
    }
)

FORBIDDEN_SOURCE_TYPES: frozenset[str] = frozenset({
    "llm_generated",
    "scraped_unreviewed",
    "live_api",
    "social_media",
    "rumor",
})

FORBIDDEN_CATEGORIES: frozenset[str] = frozenset({
    "contracts", "salaries", "cap_sheets", "injuries", "rumors",
    "live_status", "current_roster", "latest_roster",
})

ALLOWED_ROSTER_STATUSES: frozenset[str] = frozenset({
    "standard", "two_way", "training_camp", "unsigned_draft_rights",
    "free_agent", "unknown_manual_review",
})


# --------------------------------------------------------------------------- #
# DTOs (response projection)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PlayerIdentity:
    """Sanitized per-player identity (no money/injury/live fields)."""

    player_id: str
    display_name: str
    first_name: str
    last_name: str
    position: str
    birthdate: Optional[str]
    height: Optional[str]
    weight: Optional[str]
    source_name: str
    source_type: str
    as_of_date: str
    data_freshness_warning: str
    limitations: List[str]
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "player_id": self.player_id,
            "display_name": self.display_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "position": self.position,
            "birthdate": self.birthdate,
            "height": self.height,
            "weight": self.weight,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "as_of_date": self.as_of_date,
            "data_freshness_warning": self.data_freshness_warning,
            "limitations": list(self.limitations),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class RosterMembership:
    """Sanitized per-membership (team_id, player_id, roster_status only)."""

    team_id: str
    player_id: str
    roster_status: str
    membership_id: Optional[str]
    source_name: str
    source_type: str
    as_of_date: str
    data_freshness_warning: str
    limitations: List[str]
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": self.team_id,
            "player_id": self.player_id,
            "roster_status": self.roster_status,
            "membership_id": self.membership_id,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "as_of_date": self.as_of_date,
            "data_freshness_warning": self.data_freshness_warning,
            "limitations": list(self.limitations),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class SourceFileSummary:
    """Per-file lineage summary (safe projection; no hashes in response)."""

    file_path: str
    source_name: str
    source_type: str
    as_of_date: str
    manual_review_required: bool
    live_eligible: bool
    stale_after_date: Optional[str]
    data_freshness_warning: str
    limitations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "as_of_date": self.as_of_date,
            "manual_review_required": self.manual_review_required,
            "live_eligible": self.live_eligible,
            "stale_after_date": self.stale_after_date,
            "data_freshness_warning": self.data_freshness_warning,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class PlayerRosterMetadata:
    """Safe projection returned to API consumers."""

    snapshot_id: str
    snapshot_mode: str
    as_of_date: str
    data_freshness_warning: str
    limitations: List[str]
    manual_review_required: bool
    live_eligible: bool
    no_official_branding: bool
    players: List[PlayerIdentity] = field(default_factory=list)
    roster_memberships: List[RosterMembership] = field(default_factory=list)
    source_summary: List[SourceFileSummary] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_mode": self.snapshot_mode,
            "as_of_date": self.as_of_date,
            "data_freshness_warning": self.data_freshness_warning,
            "limitations": list(self.limitations),
            "manual_review_required": self.manual_review_required,
            "live_eligible": self.live_eligible,
            "no_official_branding": self.no_official_branding,
            "players": [p.to_dict() for p in self.players],
            "roster_memberships": [m.to_dict() for m in self.roster_memberships],
            "source_summary": [s.to_dict() for s in self.source_summary],
            "warnings": list(self.warnings),
        }


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #


REAL_SNAPSHOT_ID = "nba_real_2026_preoffseason_v1"
REQUIRED_SNAPSHOT_MODE = "real_snapshot"

PLAYER_IDENTITIES_REL = "normalized/player_identities.json"
ROSTER_MEMBERSHIPS_REL = "normalized/roster_memberships.json"
TEAMS_REL = "normalized/teams.json"
VISUAL_REL = "normalized/team_visual_metadata.json"
SOURCE_MANIFEST_REL = "source_manifest.json"
MANIFEST_REL = "manifest.json"

REQUIRED_REL_FILES = [
    MANIFEST_REL,
    SOURCE_MANIFEST_REL,
    TEAMS_REL,
    VISUAL_REL,
    PLAYER_IDENTITIES_REL,
    ROSTER_MEMBERSHIPS_REL,
]

HASH_PREFIX = "sha256:"


# --------------------------------------------------------------------------- #
# Helpers
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
        raise PlayerRosterSchemaError(f"Invalid JSON in {path.name}: {exc}") from exc
    except OSError as exc:
        raise PlayerRosterNotFoundError(f"Could not read {path}: {exc}") from exc


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate(doc: Any, schema: Dict[str, Any], label: str) -> None:
    try:
        jsonschema.validate(doc, schema)
    except jsonschema.ValidationError as exc:
        raise PlayerRosterSchemaError(
            f"Schema validation failed for {label}: {exc.message}"
        ) from exc


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _scan_forbidden_keys(
    obj: Any,
    forbidden: Set[str],
    label: str,
    _path: str = "",
) -> None:
    """Recursively scan dict keys for forbidden substrings/exact matches.

    This is defense-in-depth on top of JSON Schema ``propertyNames``, to catch
    fields nested inside free-form containers that might be introduced in a
    future schema loosening.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            p = f"{_path}.{k}" if _path else str(k)
            if kl in forbidden:
                raise PlayerRosterForbiddenFieldError(
                    f"Forbidden field '{k}' present in {label} at {p}"
                )
            _scan_forbidden_keys(v, forbidden, label, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _scan_forbidden_keys(v, forbidden, label, f"{_path}[{i}]")


# --------------------------------------------------------------------------- #
# Reader
# --------------------------------------------------------------------------- #


def load_player_roster_metadata(
    snapshot_mode: str,
    data_dir: Optional[Path] = None,
    schema_dir: Optional[Path] = None,
    snapshot_dir: Optional[Path] = None,
    reference_date: Optional[str] = None,
) -> PlayerRosterMetadata:
    """Load, validate, and project player/roster metadata.

    Args:
        snapshot_mode: MUST be the literal string ``"real_snapshot"``. Any other
            value (including "demo", "live", "current", "latest") raises
            ``PlayerRosterModeError`` BEFORE any disk I/O.
        data_dir: repo-root-relative ``data/`` directory. Auto-discovered if
            None. Ignored if snapshot_dir is given.
        schema_dir: directory containing the JSON schemas. Auto-discovered if
            None.
        snapshot_dir: explicit snapshot directory (used by tests with tmp_path
            synthetic fixtures). When given, data_dir is ignored for finding
            the snapshot, but schemas still load from schema_dir/repo root.
        reference_date: YYYY-MM-DD override for staleness checks (for tests);
            if None, uses today's date.

    Returns:
        ``PlayerRosterMetadata`` — a frozen read-only DTO. Call ``.to_dict()``
        for a JSON-serializable projection.

    Raises:
        PlayerRosterModeError: snapshot_mode is not "real_snapshot".
        PlayerRosterNotFoundError: snapshot directory or a required file is
            missing.
        PlayerRosterSchemaError: any file fails schema validation or
            governance-flag checks.
        PlayerRosterHashError: SHA-256 mismatch.
        PlayerRosterCrossReferenceError: player_id/team_id mismatches.
        PlayerRosterSourceError: invalid source_type, missing per-file source
            entries, forbidden data_categories.
        PlayerRosterStaleDataError: data past stale_after_date (hard error).
        PlayerRosterForbiddenFieldError: forbidden fields found beyond schema.
    """
    if snapshot_mode != REQUIRED_SNAPSHOT_MODE:
        raise PlayerRosterModeError(
            f"snapshot_mode must be '{REQUIRED_SNAPSHOT_MODE}', got '{snapshot_mode}'. "
            "The player/roster reader does not serve demo/live/current/latest "
            "modes and does not fall back to demo."
        )

    repo_root = _find_repo_root()
    schema_dir = schema_dir or (repo_root / "schema")

    if snapshot_dir is None:
        data_dir = data_dir or (repo_root / "data")
        snapshot_dir = data_dir / "snapshots" / REAL_SNAPSHOT_ID

    if not snapshot_dir.is_dir():
        raise PlayerRosterNotFoundError(
            f"Snapshot directory not found: {snapshot_dir}"
        )

    # Load schemas
    source_manifest_schema = _load_json(schema_dir / "source_manifest_schema.json")
    player_identities_schema = _load_json(schema_dir / "player_identities_schema.json")
    roster_memberships_schema = _load_json(schema_dir / "roster_memberships_schema.json")
    teams_schema = _load_json(schema_dir / "teams_schema.json")
    manifest_schema = _load_json(schema_dir / "real_snapshot_manifest_schema.json")
    visual_schema = _load_json(schema_dir / "team_visual_metadata_schema.json")

    # Check required files exist
    paths: Dict[str, Path] = {}
    for rel in REQUIRED_REL_FILES:
        p = snapshot_dir / rel
        if not p.is_file():
            raise PlayerRosterNotFoundError(
                f"Required player/roster snapshot file missing: {rel} (expected at {p})"
            )
        paths[rel] = p

    # Load documents
    manifest = _load_json(paths[MANIFEST_REL])
    source_manifest = _load_json(paths[SOURCE_MANIFEST_REL])
    teams_doc = _load_json(paths[TEAMS_REL])
    visual_doc = _load_json(paths[VISUAL_REL])
    players_doc = _load_json(paths[PLAYER_IDENTITIES_REL])
    rosters_doc = _load_json(paths[ROSTER_MEMBERSHIPS_REL])

    # Validate schemas for all six snapshot files (hard error on mismatch).
    _validate(manifest, manifest_schema, MANIFEST_REL)
    _validate(source_manifest, source_manifest_schema, SOURCE_MANIFEST_REL)
    _validate(teams_doc, teams_schema, TEAMS_REL)
    _validate(visual_doc, visual_schema, VISUAL_REL)
    _validate(players_doc, player_identities_schema, PLAYER_IDENTITIES_REL)
    _validate(rosters_doc, roster_memberships_schema, ROSTER_MEMBERSHIPS_REL)

    # Snapshot id consistency
    snap_id = manifest.get("snapshot_id")
    if not snap_id:
        raise PlayerRosterSchemaError("manifest.json missing snapshot_id")
    if players_doc.get("snapshot_id") != snap_id:
        raise PlayerRosterSchemaError(
            f"player_identities snapshot_id '{players_doc.get('snapshot_id')}' "
            f"does not match manifest snapshot_id '{snap_id}'"
        )
    if rosters_doc.get("snapshot_id") != snap_id:
        raise PlayerRosterSchemaError(
            f"roster_memberships snapshot_id '{rosters_doc.get('snapshot_id')}' "
            f"does not match manifest snapshot_id '{snap_id}'"
        )

    # Governance flags at file level
    for doc, label in [
        (source_manifest, "source_manifest"),
        (players_doc, PLAYER_IDENTITIES_REL),
        (rosters_doc, ROSTER_MEMBERSHIPS_REL),
    ]:
        if doc.get("live_eligible") is not False:
            raise PlayerRosterSchemaError(
                f"{label}.live_eligible must be false"
            )
        if doc.get("manual_review_required") is not True:
            raise PlayerRosterSchemaError(
                f"{label}.manual_review_required must be true"
            )
        warn = doc.get("data_freshness_warning")
        if not isinstance(warn, str) or not warn:
            raise PlayerRosterSchemaError(
                f"{label}.data_freshness_warning must be a non-empty string"
            )
        lim = doc.get("limitations")
        if not isinstance(lim, list) or len(lim) < 1 or not all(isinstance(x, str) and x for x in lim):
            raise PlayerRosterSchemaError(
                f"{label}.limitations must be a non-empty list of non-empty strings"
            )

    # data_categories must include player_identities/roster_memberships and
    # must NOT include contracts/salaries/cap_sheets/injuries/rumors/live
    categories = set(source_manifest.get("data_categories", []))
    if "player_identities" not in categories:
        raise PlayerRosterSourceError(
            "source_manifest.data_categories must include 'player_identities'"
        )
    if "roster_memberships" not in categories:
        raise PlayerRosterSourceError(
            "source_manifest.data_categories must include 'roster_memberships'"
        )
    forbidden_cats_found = categories & FORBIDDEN_CATEGORIES
    if forbidden_cats_found:
        raise PlayerRosterSourceError(
            f"source_manifest.data_categories contains forbidden categories: "
            f"{sorted(forbidden_cats_found)}"
        )

    # per_file_sources must cover both files
    per_file_sources = source_manifest.get("per_file_sources")
    if not isinstance(per_file_sources, dict):
        raise PlayerRosterSourceError(
            "source_manifest.per_file_sources must be an object"
        )
    for key in (PLAYER_IDENTITIES_REL, ROSTER_MEMBERSHIPS_REL):
        entry = per_file_sources.get(key)
        if not isinstance(entry, dict):
            raise PlayerRosterSourceError(
                f"source_manifest.per_file_sources missing entry for '{key}'"
            )
        src_type = entry.get("source_type")
        if src_type is not None and src_type in FORBIDDEN_SOURCE_TYPES:
            raise PlayerRosterSourceError(
                f"per_file_sources['{key}'].source_type '{src_type}' is forbidden"
            )
        if entry.get("live_eligible") is not False:
            # live_eligible is const false if present; absence is tolerated at
            # the per-file level but we still surface the top-level constraint.
            if "live_eligible" in entry:
                raise PlayerRosterSchemaError(
                    f"per_file_sources['{key}'].live_eligible must be false"
                )
        if "manual_review_required" in entry and entry.get("manual_review_required") is not True:
            raise PlayerRosterSchemaError(
                f"per_file_sources['{key}'].manual_review_required must be true if present"
            )

    # file_hashes must cover both files and match on-disk bytes
    file_hashes = source_manifest.get("file_hashes")
    if not isinstance(file_hashes, dict):
        raise PlayerRosterHashError(
            "source_manifest.file_hashes must be an object"
        )
    for rel in (PLAYER_IDENTITIES_REL, ROSTER_MEMBERSHIPS_REL):
        expected = file_hashes.get(rel)
        if not isinstance(expected, str) or not expected.startswith(HASH_PREFIX):
            raise PlayerRosterHashError(
                f"source_manifest.file_hashes missing or invalid entry for '{rel}'"
            )
        expected_hex = expected[len(HASH_PREFIX):]
        actual_hex = _sha256_file(paths[rel])
        if actual_hex != expected_hex:
            raise PlayerRosterHashError(
                f"Hash mismatch for {rel}: expected sha256:{expected_hex}, got sha256:{actual_hex}"
            )

    # Staleness check. source_manifest.stale_after_date is top-level (YYYY-MM-DD|null).
    # If null or missing, default to as_of_date + 30 days (hard error if past).
    ref_date = _parse_date(reference_date) if reference_date else date.today()
    warnings: List[str] = []
    stale_after = source_manifest.get("stale_after_date")
    if stale_after:
        try:
            stale_date = _parse_date(stale_after)
        except ValueError as exc:
            raise PlayerRosterSchemaError(
                f"source_manifest.stale_after_date '{stale_after}' is not YYYY-MM-DD"
            ) from exc
    else:
        try:
            as_of = _parse_date(source_manifest["as_of_date"])
            from datetime import timedelta
            stale_date = as_of + timedelta(days=30)
            stale_after = stale_date.isoformat()
            warnings.append(
                f"source_manifest had no explicit stale_after_date; defaulted to "
                f"as_of_date+30d = {stale_after}"
            )
        except (KeyError, ValueError) as exc:
            raise PlayerRosterSchemaError(
                f"source_manifest.as_of_date invalid: {source_manifest.get('as_of_date')!r}"
            ) from exc
    if ref_date > stale_date:
        raise PlayerRosterStaleDataError(
            f"Snapshot is past stale_after_date ({stale_after}); "
            f"reference_date={ref_date.isoformat()}. Data must be re-reviewed."
        )

    # Build team index for xref (id -> abbreviation)
    team_ids: Set[str] = set()
    for team in teams_doc.get("teams", []):
        tid = team.get("team_id")
        if not isinstance(tid, str):
            raise PlayerRosterSchemaError("teams.json contains entry without team_id")
        if tid in team_ids:
            raise PlayerRosterCrossReferenceError(f"Duplicate team_id '{tid}' in teams.json")
        team_ids.add(tid)

    # Build player index
    player_ids: Set[str] = set()
    players_out: List[PlayerIdentity] = []
    for p in players_doc.get("players", []):
        pid = p.get("player_id")
        if not isinstance(pid, str):
            raise PlayerRosterSchemaError("player_identities entry without player_id")
        if pid in player_ids:
            raise PlayerRosterCrossReferenceError(f"Duplicate player_id '{pid}' in player_identities.json")
        player_ids.add(pid)

        # Per-record governance
        if p.get("live_eligible") is not False:
            raise PlayerRosterSchemaError(f"player '{pid}' has live_eligible != false")
        if p.get("manual_review_required") is not True:
            raise PlayerRosterSchemaError(f"player '{pid}' has manual_review_required != true")
        pos = p.get("position")
        if pos not in {"PG", "SG", "SF", "PF", "C", "G", "F", "FC", "GF"}:
            raise PlayerRosterSchemaError(f"player '{pid}' has invalid position '{pos}'")

        # Defense-in-depth forbidden-key scan
        _scan_forbidden_keys(p, FORBIDDEN_PLAYER_KEYS, f"player '{pid}'")

        notes = p.get("notes") or []
        if not isinstance(notes, list):
            notes = []
        players_out.append(
            PlayerIdentity(
                player_id=pid,
                display_name=p["display_name"],
                first_name=p["first_name"],
                last_name=p["last_name"],
                position=pos,
                birthdate=p.get("birthdate"),
                height=p.get("height"),
                weight=p.get("weight"),
                source_name=p["source_name"],
                source_type=p["source_type"],
                as_of_date=p["as_of_date"],
                data_freshness_warning=p["data_freshness_warning"],
                limitations=list(p.get("limitations", [])),
                notes=list(notes),
            )
        )

    # Process roster memberships
    memberships_out: List[RosterMembership] = []
    for m in rosters_doc.get("roster_memberships", []):
        tid = m.get("team_id")
        pid = m.get("player_id")
        status = m.get("roster_status")

        if tid not in team_ids:
            raise PlayerRosterCrossReferenceError(
                f"roster_membership team_id '{tid}' not found in teams.json"
            )
        if pid not in player_ids:
            raise PlayerRosterCrossReferenceError(
                f"roster_membership player_id '{pid}' not found in player_identities.json"
            )
        if status not in ALLOWED_ROSTER_STATUSES:
            raise PlayerRosterSchemaError(
                f"roster_membership for {pid}/{tid} has forbidden roster_status '{status}'"
            )
        if m.get("live_eligible") is not False:
            raise PlayerRosterSchemaError(
                f"roster_membership {pid}/{tid} has live_eligible != false"
            )
        if m.get("manual_review_required") is not True:
            raise PlayerRosterSchemaError(
                f"roster_membership {pid}/{tid} has manual_review_required != true"
            )
        if m.get("snapshot_id") != snap_id:
            raise PlayerRosterSchemaError(
                f"roster_membership {pid}/{tid} snapshot_id mismatch"
            )

        _scan_forbidden_keys(m, FORBIDDEN_MEMBERSHIP_KEYS, f"membership {pid}/{tid}")

        notes = m.get("notes") or []
        if not isinstance(notes, list):
            notes = []
        memberships_out.append(
            RosterMembership(
                team_id=tid,
                player_id=pid,
                roster_status=status,
                membership_id=m.get("membership_id"),
                source_name=m["source_name"],
                source_type=m["source_type"],
                as_of_date=m["as_of_date"],
                data_freshness_warning=m["data_freshness_warning"],
                limitations=list(m.get("limitations", [])),
                notes=list(notes),
            )
        )

    # Top-level defense-in-depth forbidden scan on player/roster docs
    _scan_forbidden_keys(players_doc, FORBIDDEN_TOP_LEVEL_KEYS, PLAYER_IDENTITIES_REL)
    _scan_forbidden_keys(rosters_doc, FORBIDDEN_TOP_LEVEL_KEYS, ROSTER_MEMBERSHIPS_REL)

    # Source summary projection (safe; strip hashes and paths to files)
    source_summary: List[SourceFileSummary] = []
    for rel in (PLAYER_IDENTITIES_REL, ROSTER_MEMBERSHIPS_REL):
        e = per_file_sources[rel]
        source_summary.append(
            SourceFileSummary(
                file_path=rel,
                source_name=e["source_name"],
                source_type=e["source_type"],
                as_of_date=e["as_of_date"],
                manual_review_required=True,
                live_eligible=False,
                stale_after_date=e.get("stale_after_date"),
                data_freshness_warning=e.get("data_freshness_warning", players_doc["data_freshness_warning"]),
                limitations=list(e.get("limitations", players_doc.get("limitations", []))),
            )
        )

    # Determine no_official_branding (must be true). visual_doc was already
    # loaded and schema-validated above.
    no_official_branding = bool(visual_doc.get("no_official_branding", False))
    if not no_official_branding:
        raise PlayerRosterSchemaError(
            "team_visual_metadata.json must set no_official_branding=true"
        )

    # players file source_type check (per-record)
    for p in players_doc.get("players", []):
        st = p.get("source_type")
        if st in FORBIDDEN_SOURCE_TYPES:
            raise PlayerRosterSourceError(
                f"player '{p.get('player_id')}' has forbidden source_type '{st}'"
            )
    for m in rosters_doc.get("roster_memberships", []):
        st = m.get("source_type")
        if st in FORBIDDEN_SOURCE_TYPES:
            raise PlayerRosterSourceError(
                f"membership {m.get('player_id')}/{m.get('team_id')} has forbidden source_type '{st}'"
            )

    # Final DTO
    return PlayerRosterMetadata(
        snapshot_id=snap_id,
        snapshot_mode=REQUIRED_SNAPSHOT_MODE,
        as_of_date=manifest.get("as_of_date", players_doc.get("as_of_date", "")),
        data_freshness_warning=source_manifest.get(
            "data_freshness_warning", players_doc.get("data_freshness_warning", "")
        ),
        limitations=list(
            source_manifest.get("limitations", [])
        ) + list(players_doc.get("limitations", [])) + list(rosters_doc.get("limitations", [])),
        manual_review_required=True,
        live_eligible=False,
        no_official_branding=True,
        players=players_out,
        roster_memberships=memberships_out,
        source_summary=source_summary,
        warnings=warnings,
    )
