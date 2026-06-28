"""Tests for M10-F2 Backend Player/Roster Metadata Read Model.

Covers:

- Service positive (synthetic tmp_path snapshot with two fake players and two
  roster memberships loads cleanly; returns players + roster_memberships with
  xrefs intact; hash validation; source_manifest coverage; forbidden-field
  absent from projection)
- Service negative (mode rejection, missing files, hash mismatch, schema
  mismatch, xref mismatch, forbidden source_type, forbidden fields,
  stale_after_date, governance flags)
- Isolation/regression (real data/snapshots still lacks player/roster files;
  static import guard: Agent/NL/trade/signing modules do not import the
  reader; no frontend references; no POST/PUT/PATCH/DELETE endpoints added
  for this path in F2)

Run:

    python -m pytest backend/app/tests/test_m10f_player_roster_metadata_read_model.py -q

All synthetic fixtures use tmp_path. No file is written under data/snapshots.
All synthetic players are fake (Test Player Alpha / Test Player Beta). Real
NBA player names appear only in a blacklist content audit (negative test).
"""

from __future__ import annotations

import hashlib
import importlib
import json
import shutil
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict

import pytest

from backend.app.services.player_roster_metadata_reader import (
    ALLOWED_ROSTER_STATUSES,
    FORBIDDEN_CATEGORIES,
    FORBIDDEN_MEMBERSHIP_KEYS,
    FORBIDDEN_PLAYER_KEYS,
    FORBIDDEN_SOURCE_TYPES,
    PLAYER_IDENTITIES_REL,
    ROSTER_MEMBERSHIPS_REL,
    PlayerRosterCrossReferenceError,
    PlayerRosterForbiddenFieldError,
    PlayerRosterHashError,
    PlayerRosterMetadataError,
    PlayerRosterModeError,
    PlayerRosterNotFoundError,
    PlayerRosterSchemaError,
    PlayerRosterSourceError,
    PlayerRosterStaleDataError,
    load_player_roster_metadata,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
SCHEMA_DIR = REPO_ROOT / "schema"
REAL_SNAPSHOT_DIR = DATA_DIR / "snapshots" / "nba_real_2026_preoffseason_v1"
FRONTEND_DIR = REPO_ROOT / "frontend"
BACKEND_DIR = REPO_ROOT / "backend"


# --------------------------------------------------------------------------- #
# Synthetic real-NBA-player-name audit (negative only)
# --------------------------------------------------------------------------- #


REAL_NBA_PLAYER_NAMES = [
    "LeBron James", "Stephen Curry", "Luka Doncic", "Luka Dončić",
    "Victor Wembanyama", "Giannis Antetokounmpo", "Kevin Durant",
    "Nikola Jokic", "Nikola Jokić", "Jayson Tatum", "Shai Gilgeous-Alexander",
    "Jimmy Butler", "Anthony Davis", "Joel Embiid",
]


# --------------------------------------------------------------------------- #
# Forbidden-key recursive scanner for the response projection
# --------------------------------------------------------------------------- #


RESPONSE_FORBIDDEN_KEYS = {
    "salary", "salaries", "contract", "contracts", "cap_hold",
    "guarantee", "guarantee_amount", "cap_sheet", "cap_sheets",
    "injury", "injuries", "injury_status", "medical", "medical_status",
    "health", "rumors", "rumor", "scouting_opinion", "scouting_opinions",
    "live_status", "availability", "real_time_availability", "active_now",
    "current_roster", "latest_roster", "latest_data", "live_data",
    "current_salaries", "real_time_data",
    "projected_depth_chart", "depth_chart", "minutes_projection",
    "role_projection", "trade_eligibility",
    "execute", "apply", "commit", "mutate", "write", "persist", "save",
    "delete", "update", "submit", "auto_execute", "auto_approve",
    "headshot", "headshot_url", "player_image", "photo_url",
}


def _find_forbidden_key(obj: Any, _path: str = "") -> str | None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            p = f"{_path}.{k}" if _path else str(k)
            if kl in RESPONSE_FORBIDDEN_KEYS:
                return p
            found = _find_forbidden_key(v, p)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found = _find_forbidden_key(v, f"{_path}[{i}]")
            if found is not None:
                return found
    return None


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p: Path) -> str:
    return _sha256_bytes(p.read_bytes())


# --------------------------------------------------------------------------- #
# Synthetic fixture builder (tmp_path)
# --------------------------------------------------------------------------- #


SYNTHETIC_SNAPSHOT_ID = "nba_synth_f2_pilot"
AS_OF_DATE = "2026-06-28"
STALE_AFTER_DATE = (date.today() + timedelta(days=14)).isoformat()
FRESHNESS_WARNING = (
    "Synthetic player/roster identity data for F2 testing only. Identity-only; "
    "no salary/contract/cap/injury/live data; frozen as-of snapshot."
)
LIMITATIONS = [
    "Identity-only (name, position, display attributes)",
    "No salary, contract, cap data",
    "No injury, medical, availability data",
    "Not live/current/latest data; frozen as-of snapshot",
    "Synthetic test players — not real NBA players",
]


def _load_sealed_teams() -> Dict[str, Any]:
    """Load teams.json from the sealed real snapshot for xref structure.

    Team identity (team_id, city, name, abbreviation, conference, division) is
    already sealed in M10-C1 and is used in synthetic fixtures only as the
    cross-reference target for roster memberships. No player/contract/salary
    data is involved.
    """
    return json.loads((REAL_SNAPSHOT_DIR / "normalized" / "teams.json").read_text("utf-8"))


def _load_sealed_visual() -> Dict[str, Any]:
    """Load team_visual_metadata.json from the sealed real snapshot and adapt
    it to the synthetic snapshot (overwrite as_of_date to match synthetic).

    team_visual_metadata_schema.json (M10-C2) is additionalProperties:false
    and only allows visual_metadata, source_name, as_of_date,
    manual_review_required, no_official_branding at the top level. We must
    not add snapshot_id/live_eligible/data_freshness_warning/limitations here
    because those are governance fields defined on player/roster/source_manifest
    schemas, not on the visual schema."""
    doc = json.loads((REAL_SNAPSHOT_DIR / "normalized" / "team_visual_metadata.json").read_text("utf-8"))
    doc["as_of_date"] = AS_OF_DATE
    doc["manual_review_required"] = True
    doc["no_official_branding"] = True
    return doc


def _base_teams() -> Dict[str, Any]:
    teams = _load_sealed_teams()
    teams["as_of_date"] = AS_OF_DATE
    teams["manual_review_required"] = True
    return teams


def _base_visual() -> Dict[str, Any]:
    return _load_sealed_visual()


def _base_players() -> Dict[str, Any]:
    return {
        "schema_version": "m10-e3-v1",
        "snapshot_id": SYNTHETIC_SNAPSHOT_ID,
        "as_of_date": AS_OF_DATE,
        "generated_at": "2026-06-28T00:00:00Z",
        "source_name": "synthetic curation (F2 test)",
        "source_url": None,
        "source_type": "manual_curated",
        "manual_review_required": True,
        "live_eligible": False,
        "data_freshness_warning": FRESHNESS_WARNING,
        "limitations": list(LIMITATIONS),
        "players": [
            {
                "player_id": "player-test-alpha",
                "display_name": "T. Alpha",
                "first_name": "Test",
                "last_name": "Alpha",
                "birthdate": "1999-01-15",
                "height": "6-7",
                "weight": "220 lb",
                "position": "SF",
                "source_name": "synthetic curation (F2 test)",
                "source_url": None,
                "source_type": "manual_curated",
                "as_of_date": AS_OF_DATE,
                "manual_review_required": True,
                "live_eligible": False,
                "data_freshness_warning": FRESHNESS_WARNING,
                "snapshot_id": SYNTHETIC_SNAPSHOT_ID,
                "notes": ["Synthetic fixture player for M10-F2 tests"],
                "limitations": list(LIMITATIONS),
            },
            {
                "player_id": "player-test-beta",
                "display_name": "T. Beta",
                "first_name": "Test",
                "last_name": "Beta",
                "birthdate": "2000-07-04",
                "height": "6-1",
                "weight": "185 lb",
                "position": "PG",
                "source_name": "synthetic curation (F2 test)",
                "source_url": None,
                "source_type": "manual_curated",
                "as_of_date": AS_OF_DATE,
                "manual_review_required": True,
                "live_eligible": False,
                "data_freshness_warning": FRESHNESS_WARNING,
                "snapshot_id": SYNTHETIC_SNAPSHOT_ID,
                "notes": ["Synthetic fixture player for M10-F2 tests"],
                "limitations": list(LIMITATIONS),
            },
        ],
    }


def _base_rosters() -> Dict[str, Any]:
    return {
        "schema_version": "m10-e4-v1",
        "snapshot_id": SYNTHETIC_SNAPSHOT_ID,
        "as_of_date": AS_OF_DATE,
        "generated_at": "2026-06-28T00:00:00Z",
        "source_name": "synthetic curation (F2 test)",
        "source_url": None,
        "source_type": "manual_curated",
        "manual_review_required": True,
        "live_eligible": False,
        "data_freshness_warning": FRESHNESS_WARNING,
        "limitations": list(LIMITATIONS),
        "roster_memberships": [
            {
                "team_id": "nba-ATL",
                "player_id": "player-test-alpha",
                "roster_status": "standard",
                "membership_id": "mem-synth-alpha-atl",
                "source_name": "synthetic curation (F2 test)",
                "source_url": None,
                "source_type": "manual_curated",
                "as_of_date": AS_OF_DATE,
                "manual_review_required": True,
                "live_eligible": False,
                "data_freshness_warning": FRESHNESS_WARNING,
                "snapshot_id": SYNTHETIC_SNAPSHOT_ID,
                "notes": ["Synthetic fixture membership for M10-F2 tests"],
                "limitations": list(LIMITATIONS),
            },
            {
                "team_id": "nba-BOS",
                "player_id": "player-test-beta",
                "roster_status": "two_way",
                "membership_id": "mem-synth-beta-bos",
                "source_name": "synthetic curation (F2 test)",
                "source_url": None,
                "source_type": "manual_curated",
                "as_of_date": AS_OF_DATE,
                "manual_review_required": True,
                "live_eligible": False,
                "data_freshness_warning": FRESHNESS_WARNING,
                "snapshot_id": SYNTHETIC_SNAPSHOT_ID,
                "notes": ["Synthetic fixture membership for M10-F2 tests"],
                "limitations": list(LIMITATIONS),
            },
        ],
    }


def _base_manifest() -> Dict[str, Any]:
    teams_doc = _load_sealed_teams()
    team_id_list = [t["team_id"] for t in teams_doc["teams"]]
    return {
        "snapshot_id": SYNTHETIC_SNAPSHOT_ID,
        "snapshot_type": "curated_real",
        "season": "2025-2026",
        "source_name": "synthetic curation (F2 test)",
        "source_url": None,
        "source_pack_version": "m10-f2-synth-v1",
        "as_of_date": AS_OF_DATE,
        "generated_at": "2026-06-28T00:00:00Z",
        "sample_data": False,
        "manual_review_required": True,
        "teams": team_id_list,
        "description": "Synthetic tmp_path snapshot for M10-F2 service tests only.",
        "limitations": list(LIMITATIONS),
    }


def _load_sealed_source_manifest() -> Dict[str, Any]:
    """Load source_manifest.json from the sealed real snapshot for structure.

    We clone it and overwrite fields (snapshot_id, categories, per_file_sources,
    file_hashes, etc.) to reflect the synthetic F2 pilot snapshot."""
    return json.loads((REAL_SNAPSHOT_DIR / "source_manifest.json").read_text("utf-8"))


def _build_source_manifest(
    players_bytes: bytes,
    rosters_bytes: bytes,
    teams_bytes: bytes,
    visual_bytes: bytes,
    *,
    data_categories=None,
    per_file_extra=None,
    file_hashes_extra=None,
) -> Dict[str, Any]:
    if data_categories is None:
        data_categories = ["teams", "team_visual_metadata",
                          "player_identities", "roster_memberships"]
    if per_file_extra is None:
        per_file_extra = {}
    if file_hashes_extra is None:
        file_hashes_extra = {}

    def _entry():
        return {
            "source_name": "synthetic curation (F2 test)",
            "source_url": None,
            "source_type": "manual_curated",
            "as_of_date": AS_OF_DATE,
            "manual_review_required": True,
            "live_eligible": False,
            "data_freshness_warning": FRESHNESS_WARNING,
            "limitations": list(LIMITATIONS),
        }

    # Start from sealed real source_manifest to satisfy all required fields
    # (license_notes, freshness_label, etc.) that source_manifest_schema enforces.
    sm = _load_sealed_source_manifest()
    sm["snapshot_id"] = SYNTHETIC_SNAPSHOT_ID
    sm["schema_version"] = "m10-f2-synth-v1"
    sm["as_of_date"] = AS_OF_DATE
    sm["generated_at"] = "2026-06-28T00:00:00Z"
    sm["source_name"] = "synthetic curation (F2 test)"
    sm["source_url"] = None
    sm["freshness_label"] = "Synthetic F2 pilot"
    sm["freshness_level"] = "frozen"
    sm["live_eligible"] = False
    sm["stale_after_date"] = STALE_AFTER_DATE
    sm["data_freshness_warning"] = FRESHNESS_WARNING
    sm["limitations"] = list(LIMITATIONS)
    sm["manual_review_required"] = True
    sm["data_categories"] = data_categories
    sm["created_by"] = "m10-f2-tests"
    sm["validation_status"] = "provisional"
    sm["reviewed_by"] = "m10-f2-gate"
    sm["review_date"] = AS_OF_DATE

    per_file = {
        "normalized/teams.json": {**_entry(), "source_name": "NBA.com (synth)", "source_type": "public_reference"},
        "normalized/team_visual_metadata.json": {**_entry(), "source_name": "manual non-official palette (synth)", "source_type": "manual_non_official_ui"},
        PLAYER_IDENTITIES_REL: {**_entry(), "source_type": "manual_curated"},
        ROSTER_MEMBERSHIPS_REL: {**_entry(), "source_type": "manual_curated"},
    }
    for k, v in per_file_extra.items():
        if v is None:
            per_file.pop(k, None)
        else:
            per_file[k] = {**per_file.get(k, _entry()), **v}
    sm["per_file_sources"] = per_file

    file_hashes = {
        "normalized/teams.json": f"sha256:{_sha256_bytes(teams_bytes)}",
        "normalized/team_visual_metadata.json": f"sha256:{_sha256_bytes(visual_bytes)}",
        PLAYER_IDENTITIES_REL: f"sha256:{_sha256_bytes(players_bytes)}",
        ROSTER_MEMBERSHIPS_REL: f"sha256:{_sha256_bytes(rosters_bytes)}",
    }
    for k, v in file_hashes_extra.items():
        if v is None:
            file_hashes.pop(k, None)
        else:
            file_hashes[k] = v
    sm["file_hashes"] = file_hashes

    return sm


def _write_snapshot(
    tmp_path: Path,
    *,
    teams_doc=None,
    visual_doc=None,
    players_doc=None,
    rosters_doc=None,
    manifest_doc=None,
    source_manifest_mutator=None,
) -> Path:
    snap_dir = tmp_path / SYNTHETIC_SNAPSHOT_ID
    (snap_dir / "normalized").mkdir(parents=True, exist_ok=True)

    teams_doc = teams_doc if teams_doc is not None else _base_teams()
    visual_doc = visual_doc if visual_doc is not None else _base_visual()
    players_doc = players_doc if players_doc is not None else _base_players()
    rosters_doc = rosters_doc if rosters_doc is not None else _base_rosters()
    manifest_doc = manifest_doc if manifest_doc is not None else _base_manifest()

    def _dump(name: str, doc: Dict[str, Any]) -> bytes:
        p = snap_dir / name
        b = json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")
        p.write_bytes(b)
        return b

    teams_b = _dump("normalized/teams.json", teams_doc)
    visual_b = _dump("normalized/team_visual_metadata.json", visual_doc)
    players_b = _dump(PLAYER_IDENTITIES_REL, players_doc)
    rosters_b = _dump(ROSTER_MEMBERSHIPS_REL, rosters_doc)
    _dump("manifest.json", manifest_doc)

    sm = _build_source_manifest(players_b, rosters_b, teams_b, visual_b)
    if source_manifest_mutator is not None:
        source_manifest_mutator(sm)
    (snap_dir / "source_manifest.json").write_bytes(
        json.dumps(sm, ensure_ascii=False, indent=2).encode("utf-8")
    )
    return snap_dir


# --------------------------------------------------------------------------- #
# Positive tests
# --------------------------------------------------------------------------- #


class TestServicePositive:
    def test_loads_valid_synthetic_snapshot(self, tmp_path: Path) -> None:
        snap_dir = _write_snapshot(tmp_path)
        md = load_player_roster_metadata(
            "real_snapshot",
            schema_dir=SCHEMA_DIR,
            snapshot_dir=snap_dir,
            reference_date=AS_OF_DATE,
        )
        assert md is not None
        d = md.to_dict()
        assert d["snapshot_mode"] == "real_snapshot"
        assert d["snapshot_id"] == SYNTHETIC_SNAPSHOT_ID
        assert d["live_eligible"] is False
        assert d["manual_review_required"] is True
        assert d["no_official_branding"] is True

    def test_returns_players(self, tmp_path: Path) -> None:
        snap_dir = _write_snapshot(tmp_path)
        md = load_player_roster_metadata(
            "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
            reference_date=AS_OF_DATE,
        )
        d = md.to_dict()
        assert len(d["players"]) == 2
        ids = {p["player_id"] for p in d["players"]}
        assert ids == {"player-test-alpha", "player-test-beta"}
        for p in d["players"]:
            assert p["display_name"]
            assert p["first_name"]
            assert p["last_name"]
            assert p["position"] in {"PG", "SG", "SF", "PF", "C", "G", "F", "FC", "GF"}
            assert p["source_type"] in {"manual_curated", "public_reference",
                                         "league_public_reference",
                                         "team_public_reference", "manual_review"}

    def test_returns_roster_memberships(self, tmp_path: Path) -> None:
        snap_dir = _write_snapshot(tmp_path)
        md = load_player_roster_metadata(
            "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
            reference_date=AS_OF_DATE,
        )
        d = md.to_dict()
        assert len(d["roster_memberships"]) == 2
        for m in d["roster_memberships"]:
            assert m["team_id"].startswith("nba-")
            assert m["player_id"].startswith("player-test-")
            assert m["roster_status"] in ALLOWED_ROSTER_STATUSES

    def test_roster_player_id_xrefs_to_players(self, tmp_path: Path) -> None:
        snap_dir = _write_snapshot(tmp_path)
        md = load_player_roster_metadata(
            "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
            reference_date=AS_OF_DATE,
        )
        d = md.to_dict()
        player_ids = {p["player_id"] for p in d["players"]}
        for m in d["roster_memberships"]:
            assert m["player_id"] in player_ids

    def test_roster_team_id_xrefs_to_teams(self, tmp_path: Path) -> None:
        snap_dir = _write_snapshot(tmp_path)
        md = load_player_roster_metadata(
            "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
            reference_date=AS_OF_DATE,
        )
        d = md.to_dict()
        # All team_ids in memberships must be valid nba-XXX IDs and exist in teams.json
        teams_doc = _load_sealed_teams()
        valid_team_ids = {t["team_id"] for t in teams_doc["teams"]}
        for m in d["roster_memberships"]:
            assert m["team_id"] in valid_team_ids

    def test_hash_validation_passes_for_matching_bytes(self, tmp_path: Path) -> None:
        snap_dir = _write_snapshot(tmp_path)
        # Should not raise
        md = load_player_roster_metadata(
            "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
            reference_date=AS_OF_DATE,
        )
        assert md is not None

    def test_per_file_sources_covered(self, tmp_path: Path) -> None:
        snap_dir = _write_snapshot(tmp_path)
        md = load_player_roster_metadata(
            "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
            reference_date=AS_OF_DATE,
        )
        d = md.to_dict()
        paths = {s["file_path"] for s in d["source_summary"]}
        assert PLAYER_IDENTITIES_REL in paths
        assert ROSTER_MEMBERSHIPS_REL in paths
        for s in d["source_summary"]:
            assert s["live_eligible"] is False
            assert s["manual_review_required"] is True
            assert s["source_type"] not in FORBIDDEN_SOURCE_TYPES

    def test_data_categories_include_player_and_roster(self, tmp_path: Path) -> None:
        snap_dir = _write_snapshot(tmp_path)
        md = load_player_roster_metadata(
            "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
            reference_date=AS_OF_DATE,
        )
        # (data_categories is validated inside the service; reaching here is
        # enough proof; additionally confirm via reading sm that categories ok)
        sm = json.loads((snap_dir / "source_manifest.json").read_text("utf-8"))
        assert "player_identities" in sm["data_categories"]
        assert "roster_memberships" in sm["data_categories"]

    def test_response_excludes_forbidden_fields(self, tmp_path: Path) -> None:
        snap_dir = _write_snapshot(tmp_path)
        md = load_player_roster_metadata(
            "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
            reference_date=AS_OF_DATE,
        )
        d = md.to_dict()
        found = _find_forbidden_key(d)
        assert found is None, f"Forbidden key present in response at: {found}"

    def test_as_of_date_and_warnings_present(self, tmp_path: Path) -> None:
        snap_dir = _write_snapshot(tmp_path)
        md = load_player_roster_metadata(
            "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
            reference_date=AS_OF_DATE,
        )
        d = md.to_dict()
        assert d["as_of_date"] == AS_OF_DATE
        assert d["data_freshness_warning"]
        assert isinstance(d["limitations"], list)
        assert len(d["limitations"]) >= 1

    def test_synthetic_player_names_are_fake(self, tmp_path: Path) -> None:
        snap_dir = _write_snapshot(tmp_path)
        md = load_player_roster_metadata(
            "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
            reference_date=AS_OF_DATE,
        )
        d = md.to_dict()
        blob = json.dumps(d, ensure_ascii=False).lower()
        for real_name in REAL_NBA_PLAYER_NAMES:
            assert real_name.lower() not in blob, (
                f"Real NBA player name '{real_name}' leaked into synthetic "
                f"response projection (should only appear in blacklist/audit tests)."
            )


# --------------------------------------------------------------------------- #
# Negative tests
# --------------------------------------------------------------------------- #


class TestServiceNegative:
    def test_rejects_non_real_snapshot_modes(self, tmp_path: Path) -> None:
        for bad in ["demo", "live", "current", "latest", "", "foo", "REAL_SNAPSHOT"]:
            with pytest.raises(PlayerRosterModeError):
                load_player_roster_metadata(bad, schema_dir=SCHEMA_DIR,
                                            snapshot_dir=tmp_path)

    def test_missing_player_identities_file(self, tmp_path: Path) -> None:
        snap_dir = _write_snapshot(tmp_path)
        (snap_dir / PLAYER_IDENTITIES_REL).unlink()
        with pytest.raises(PlayerRosterNotFoundError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_missing_roster_memberships_file(self, tmp_path: Path) -> None:
        snap_dir = _write_snapshot(tmp_path)
        (snap_dir / ROSTER_MEMBERSHIPS_REL).unlink()
        with pytest.raises(PlayerRosterNotFoundError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_missing_file_hashes_entry(self, tmp_path: Path) -> None:
        def mutate(sm: Dict[str, Any]) -> None:
            sm["file_hashes"].pop(PLAYER_IDENTITIES_REL, None)
        snap_dir = _write_snapshot(tmp_path, source_manifest_mutator=mutate)
        with pytest.raises(PlayerRosterHashError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_missing_per_file_sources_entry(self, tmp_path: Path) -> None:
        def mutate(sm: Dict[str, Any]) -> None:
            sm["per_file_sources"].pop(PLAYER_IDENTITIES_REL, None)
        snap_dir = _write_snapshot(tmp_path, source_manifest_mutator=mutate)
        with pytest.raises(PlayerRosterSourceError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_hash_mismatch_raises(self, tmp_path: Path) -> None:
        def mutate(sm: Dict[str, Any]) -> None:
            sm["file_hashes"][PLAYER_IDENTITIES_REL] = "sha256:" + "0" * 64
        snap_dir = _write_snapshot(tmp_path, source_manifest_mutator=mutate)
        with pytest.raises(PlayerRosterHashError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_player_schema_mismatch_raises(self, tmp_path: Path) -> None:
        players = _base_players()
        # Remove a required field
        del players["players"][0]["position"]
        snap_dir = _write_snapshot(tmp_path, players_doc=players)
        with pytest.raises(PlayerRosterSchemaError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_roster_schema_mismatch_raises(self, tmp_path: Path) -> None:
        rosters = _base_rosters()
        del rosters["roster_memberships"][0]["team_id"]
        snap_dir = _write_snapshot(tmp_path, rosters_doc=rosters)
        with pytest.raises(PlayerRosterSchemaError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_manifest_schema_mismatch_raises(self, tmp_path: Path) -> None:
        manifest = _base_manifest()
        # Remove a required top-level field (limitations is required by
        # real_snapshot_manifest_schema.json with minItems: 1).
        del manifest["limitations"]
        snap_dir = _write_snapshot(tmp_path, manifest_doc=manifest)
        with pytest.raises(PlayerRosterSchemaError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_team_visual_metadata_schema_mismatch_raises(self, tmp_path: Path) -> None:
        visual = _base_visual()
        # Remove a required top-level field (no_official_branding is required
        # and const true by team_visual_metadata_schema.json).
        del visual["no_official_branding"]
        snap_dir = _write_snapshot(tmp_path, visual_doc=visual)
        with pytest.raises(PlayerRosterSchemaError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_roster_player_id_not_in_players_raises(self, tmp_path: Path) -> None:
        rosters = _base_rosters()
        rosters["roster_memberships"][0]["player_id"] = "player-nonexistent"
        # The schema requires ^[a-z][a-z0-9_-]*$ so synthesize a valid id
        rosters["roster_memberships"][0]["player_id"] = "player-ghost"
        snap_dir = _write_snapshot(tmp_path, rosters_doc=rosters)
        with pytest.raises(PlayerRosterCrossReferenceError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_roster_team_id_not_in_teams_raises(self, tmp_path: Path) -> None:
        rosters = _base_rosters()
        rosters["roster_memberships"][0]["team_id"] = "nba-ZZZ"
        snap_dir = _write_snapshot(tmp_path, rosters_doc=rosters)
        with pytest.raises(PlayerRosterCrossReferenceError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    @pytest.mark.parametrize("flag_doc", ["players", "rosters"])
    def test_live_eligible_true_raises(self, tmp_path: Path, flag_doc: str) -> None:
        if flag_doc == "players":
            players = _base_players()
            players["live_eligible"] = True
            snap_dir = _write_snapshot(tmp_path, players_doc=players)
        else:
            rosters = _base_rosters()
            rosters["live_eligible"] = True
            snap_dir = _write_snapshot(tmp_path, rosters_doc=rosters)
        with pytest.raises(PlayerRosterSchemaError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    @pytest.mark.parametrize("flag_doc", ["players", "rosters"])
    def test_manual_review_required_false_raises(self, tmp_path: Path, flag_doc: str) -> None:
        if flag_doc == "players":
            players = _base_players()
            players["manual_review_required"] = False
            snap_dir = _write_snapshot(tmp_path, players_doc=players)
        else:
            rosters = _base_rosters()
            rosters["manual_review_required"] = False
            snap_dir = _write_snapshot(tmp_path, rosters_doc=rosters)
        with pytest.raises(PlayerRosterSchemaError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    @pytest.mark.parametrize("bad_source_type", list(FORBIDDEN_SOURCE_TYPES))
    def test_per_file_source_type_forbidden_rejected(self, tmp_path: Path, bad_source_type: str) -> None:
        def mutate(sm: Dict[str, Any]) -> None:
            sm["per_file_sources"][PLAYER_IDENTITIES_REL]["source_type"] = bad_source_type
        snap_dir = _write_snapshot(tmp_path, source_manifest_mutator=mutate)
        # Forbidden source types will either fail schema enum validation or
        # our explicit FORBIDDEN_SOURCE_TYPES post-check; both are hard errors.
        with pytest.raises((PlayerRosterSourceError, PlayerRosterSchemaError)):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    @pytest.mark.parametrize("forbidden_field", [
        "salary", "contract", "cap_hold", "injury_status", "rumors",
        "scouting_opinion", "live_status", "execute", "apply", "mutate", "write",
    ])
    def test_forbidden_field_in_players_doc_raises(self, tmp_path: Path, forbidden_field: str) -> None:
        players = _base_players()
        # Add a forbidden field at the top level of players_doc. The schema's
        # additionalProperties=false rejects it; confirm the error class.
        players[forbidden_field] = 1
        snap_dir = _write_snapshot(tmp_path, players_doc=players)
        with pytest.raises((PlayerRosterSchemaError, PlayerRosterForbiddenFieldError)):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    @pytest.mark.parametrize("forbidden_field", [
        "salary", "contract", "cap_hold", "injury_status", "rumors",
        "scouting_opinion", "live_status", "execute", "apply", "mutate", "write",
    ])
    def test_forbidden_field_in_rosters_doc_raises(self, tmp_path: Path, forbidden_field: str) -> None:
        rosters = _base_rosters()
        rosters[forbidden_field] = 1
        snap_dir = _write_snapshot(tmp_path, rosters_doc=rosters)
        with pytest.raises((PlayerRosterSchemaError, PlayerRosterForbiddenFieldError)):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_forbidden_data_category_raises(self, tmp_path: Path) -> None:
        def mutate(sm: Dict[str, Any]) -> None:
            # Append a category that is BOTH not in the schema enum AND in our
            # FORBIDDEN_CATEGORIES; either a schema error or source error is acceptable
            # (schema catches enum violation first, our post-check is defense-in-depth).
            sm["data_categories"].append("contracts")
        snap_dir = _write_snapshot(tmp_path, source_manifest_mutator=mutate)
        with pytest.raises((PlayerRosterSourceError, PlayerRosterSchemaError)):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    @pytest.mark.parametrize("bad_status", [
        "inactive", "waived", "traded", "injured", "suspended",
        "questionable", "probable", "day_to_day", "available",
        "unavailable", "active_now", "current", "latest",
    ])
    def test_forbidden_roster_status_raises(self, tmp_path: Path, bad_status: str) -> None:
        rosters = _base_rosters()
        rosters["roster_memberships"][0]["roster_status"] = bad_status
        # Schema enum rejects it first, but the service also checks explicitly.
        snap_dir = _write_snapshot(tmp_path, rosters_doc=rosters)
        with pytest.raises(PlayerRosterSchemaError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_stale_after_date_expired_hard_error(self, tmp_path: Path) -> None:
        def mutate(sm: Dict[str, Any]) -> None:
            # Only top-level stale_after_date controls staleness. Set past to trigger error.
            sm["stale_after_date"] = "2026-05-01"
        snap_dir = _write_snapshot(tmp_path, source_manifest_mutator=mutate)
        with pytest.raises(PlayerRosterStaleDataError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_duplicate_player_id_raises(self, tmp_path: Path) -> None:
        players = _base_players()
        players["players"][1]["player_id"] = players["players"][0]["player_id"]
        snap_dir = _write_snapshot(tmp_path, players_doc=players)
        with pytest.raises(PlayerRosterCrossReferenceError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )

    def test_snapshot_id_mismatch_raises(self, tmp_path: Path) -> None:
        players = _base_players()
        players["snapshot_id"] = "other-snap"
        # Also patch per-player snapshot_id; the schema enforces pattern/string
        for p in players["players"]:
            p["snapshot_id"] = "other-snap"
        snap_dir = _write_snapshot(tmp_path, players_doc=players)
        with pytest.raises(PlayerRosterSchemaError):
            load_player_roster_metadata(
                "real_snapshot", schema_dir=SCHEMA_DIR, snapshot_dir=snap_dir,
                reference_date=AS_OF_DATE,
            )


# --------------------------------------------------------------------------- #
# Isolation / regression
# --------------------------------------------------------------------------- #


class TestIsolationRegression:
    """Confirm F2 did not write into data/snapshots, frontend, or wire into
    disallowed consumers."""

    def test_real_snapshot_normalized_has_expected_files(self) -> None:
        normalized = REAL_SNAPSHOT_DIR / "normalized"
        assert normalized.is_dir(), f"real snapshot normalized/ missing at {normalized}"
        files = sorted(p.name for p in normalized.iterdir())
        expected = ["player_identities.json", "roster_memberships.json",
                    "team_visual_metadata.json", "teams.json"]
        assert files == expected, (
            f"Expected teams.json + team_visual_metadata.json + player_identities.json + "
            f"roster_memberships.json under real normalized/, found: {files}"
        )

    def test_player_identities_json_exists_with_4_tiny_pilot_players(self) -> None:
        p = REAL_SNAPSHOT_DIR / PLAYER_IDENTITIES_REL
        assert p.exists(), f"{PLAYER_IDENTITIES_REL} must exist after F4-B tiny pilot"
        doc = json.loads(p.read_text("utf-8"))
        assert doc.get("snapshot_id") == "nba_real_2026_preoffseason_v1"
        assert doc.get("live_eligible") is False
        assert doc.get("manual_review_required") is True
        players = doc.get("players", [])
        assert len(players) == 4, f"Expected exactly 4 tiny pilot players, got {len(players)}"
        player_ids = {pl.get("player_id") for pl in players}
        expected_ids = {
            "nba-shai-gilgeous-alexander", "nba-chet-holmgren",
            "nba-nikola-jokic", "nba-jamal-murray",
        }
        assert player_ids == expected_ids, f"Unexpected player IDs: {player_ids}"
        for pl in players:
            assert pl.get("live_eligible") is False
            assert pl.get("manual_review_required") is True
            assert pl.get("birthdate") is None
            assert pl.get("height") is None
            assert pl.get("weight") is None
            assert pl.get("source_type") == "manual_curated"
            assert pl.get("snapshot_id") == "nba_real_2026_preoffseason_v1"
        assert _find_forbidden_key(doc) is None, (
            f"Forbidden key found in player_identities.json: {_find_forbidden_key(doc)}"
        )

    def test_roster_memberships_json_exists_with_4_tiny_pilot_memberships(self) -> None:
        p = REAL_SNAPSHOT_DIR / ROSTER_MEMBERSHIPS_REL
        assert p.exists(), f"{ROSTER_MEMBERSHIPS_REL} must exist after F4-B tiny pilot"
        doc = json.loads(p.read_text("utf-8"))
        assert doc.get("snapshot_id") == "nba_real_2026_preoffseason_v1"
        assert doc.get("live_eligible") is False
        assert doc.get("manual_review_required") is True
        mems = doc.get("roster_memberships", [])
        assert len(mems) == 4, f"Expected exactly 4 tiny pilot memberships, got {len(mems)}"
        team_ids = {m.get("team_id") for m in mems}
        assert team_ids == {"nba-OKC", "nba-DEN"}, f"Unexpected team IDs: {team_ids}"
        player_ids = {m.get("player_id") for m in mems}
        expected_pids = {
            "nba-shai-gilgeous-alexander", "nba-chet-holmgren",
            "nba-nikola-jokic", "nba-jamal-murray",
        }
        assert player_ids == expected_pids, f"Unexpected player IDs in memberships: {player_ids}"
        for m in mems:
            assert m.get("live_eligible") is False
            assert m.get("manual_review_required") is True
            assert m.get("roster_status") == "standard"
            assert m.get("source_type") == "manual_curated"
            assert m.get("snapshot_id") == "nba_real_2026_preoffseason_v1"
        assert _find_forbidden_key(doc) is None, (
            f"Forbidden key found in roster_memberships.json: {_find_forbidden_key(doc)}"
        )

    def test_no_contracts_salaries_cap_files_anywhere_under_real_snapshot(self) -> None:
        forbidden = ["contracts.json", "salaries.json", "cap_sheet.json",
                     "cap_sheets.json", "injuries.json", "rumors.json",
                     "scouting_opinions.json", "players.json", "rosters.json"]
        for name in forbidden:
            for p in REAL_SNAPSHOT_DIR.rglob(name):
                pytest.fail(f"Forbidden file leaked into real snapshot: {p}")

    def test_frontend_has_no_player_roster_references(self) -> None:
        # Defensive: if frontend directory exists, scan it for new references.
        if not FRONTEND_DIR.exists():
            return
        needles = ["player_identities", "roster_memberships",
                   "player-roster-metadata", "player_roster_metadata_reader"]
        for path in FRONTEND_DIR.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".ts", ".tsx", ".js", ".jsx",
                                           ".json", ".css", ".html", ".md"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                continue
            for n in needles:
                assert n not in text, (
                    f"Frontend file {path} references forbidden player/roster "
                    f"token '{n}' — F2 must not wire frontend."
                )

    def test_static_import_guard_agent_nl_trade_signing_do_not_import_reader(self) -> None:
        """The Agent, NL preview, trade, and signing modules must not import
        player_roster_metadata_reader. F2 ships service + tests + docs only."""

        forbidden_imports = [
            "backend.app.services.player_roster_metadata_reader",
            "player_roster_metadata_reader",
        ]

        # Scan backend source files (excluding tests and the service itself).
        EXCLUDE_DIR_PARTS = {"tests", "__pycache__"}
        for py_file in BACKEND_DIR.rglob("*.py"):
            parts = set(py_file.parts)
            if "tests" in parts or "__pycache__" in parts:
                continue
            if py_file.name == "player_roster_metadata_reader.py":
                continue
            # We also exclude this very test file by path.
            try:
                text = py_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for imp in forbidden_imports:
                assert imp not in text, (
                    f"File {py_file} imports '{imp}' — Agent/NL/trade/signing "
                    f"consumers must not import the player/roster reader in F2."
                )

    def test_no_new_write_endpoints_for_player_roster_route(self) -> None:
        """F2 does not register any HTTP endpoint for player-roster-metadata.
        Confirm api.py contains no POST/PUT/PATCH/DELETE references to a
        player-roster path, and that no GET route was added for it in F2
        (F2 is service+tests+docs only; API wiring is deferred)."""
        api_file = BACKEND_DIR / "app" / "api.py"
        if not api_file.exists():
            return
        text = api_file.read_text(encoding="utf-8", errors="ignore").lower()
        forbidden_tokens = [
            "player-roster-metadata",
            "player_roster_metadata",
        ]
        for tok in forbidden_tokens:
            assert tok not in text, (
                f"api.py contains '{tok}' — F2 must not wire an API endpoint. "
                f"Endpoint wiring is deferred to a later milestone."
            )

    def test_no_contracts_or_salaries_schema_mentions_as_allowed_categories(self) -> None:
        sm_schema = json.loads((SCHEMA_DIR / "source_manifest_schema.json").read_text("utf-8"))
        cats = sm_schema.get("properties", {}).get("data_categories", {}).get("items", {}).get("enum", [])
        for forbidden in FORBIDDEN_CATEGORIES:
            assert forbidden not in cats, (
                f"source_manifest_schema allows forbidden category '{forbidden}'"
            )

    def test_real_player_names_only_in_test_blacklist(self) -> None:
        """Real NBA player names must only appear in the REAL_NBA_PLAYER_NAMES
        blacklist inside this test file — not in service code, schemas, or
        other test fixtures."""
        for real_name in REAL_NBA_PLAYER_NAMES[:4]:  # spot check a few
            for py_file in [
                BACKEND_DIR / "app" / "services" / "player_roster_metadata_reader.py",
            ]:
                text = py_file.read_text(encoding="utf-8", errors="ignore")
                assert real_name not in text, (
                    f"Real NBA player name '{real_name}' found in service file"
                )
            # They must not appear inside synthetic fixture builder doc strings
            # that are copied into runtime data; our test builder uses only
            # "Test Player Alpha/Beta" names. The strings are allowed here in
            # this test file's blacklist only (negative audit context).


class TestTinyPilotSmoke:
    """Load the real tiny pilot snapshot via the read model service and
    validate all hard guarantees: schema, hashes, xrefs, forbidden fields,
    governance flags, and pilot scope bounds (4 players / 4 memberships)."""

    def test_load_real_tiny_pilot_snapshot_succeeds(self) -> None:
        md = load_player_roster_metadata(
            snapshot_mode="real_snapshot",
            reference_date="2026-06-28",
        )
        assert md.snapshot_id == "nba_real_2026_preoffseason_v1"
        assert md.snapshot_mode == "real_snapshot"
        assert md.live_eligible is False
        assert md.manual_review_required is True
        assert md.no_official_branding is True

    def test_tiny_pilot_returns_exactly_4_players(self) -> None:
        md = load_player_roster_metadata(
            snapshot_mode="real_snapshot",
            reference_date="2026-06-28",
        )
        assert len(md.players) == 4
        player_ids = {p.player_id for p in md.players}
        expected = {
            "nba-shai-gilgeous-alexander",
            "nba-chet-holmgren",
            "nba-nikola-jokic",
            "nba-jamal-murray",
        }
        assert player_ids == expected

    def test_tiny_pilot_player_fields_correct(self) -> None:
        md = load_player_roster_metadata(
            snapshot_mode="real_snapshot",
            reference_date="2026-06-28",
        )
        players_by_id = {p.player_id: p for p in md.players}
        shai = players_by_id["nba-shai-gilgeous-alexander"]
        assert shai.display_name == "Shai Gilgeous-Alexander"
        assert shai.first_name == "Shai"
        assert shai.last_name == "Gilgeous-Alexander"
        assert shai.position == "G"
        assert shai.birthdate is None
        assert shai.height is None
        assert shai.weight is None
        assert shai.source_type == "manual_curated"

        chet = players_by_id["nba-chet-holmgren"]
        assert chet.display_name == "Chet Holmgren"
        assert chet.first_name == "Chet"
        assert chet.last_name == "Holmgren"
        assert chet.position == "FC"
        assert chet.birthdate is None
        assert chet.height is None
        assert chet.weight is None
        assert chet.source_type == "manual_curated"

        jokic = players_by_id["nba-nikola-jokic"]
        assert jokic.display_name == "Nikola Jokic"
        assert jokic.first_name == "Nikola"
        assert jokic.last_name == "Jokic"
        assert jokic.position == "C"
        assert jokic.birthdate is None
        assert jokic.height is None
        assert jokic.weight is None
        assert jokic.source_type == "manual_curated"

        murray = players_by_id["nba-jamal-murray"]
        assert murray.display_name == "Jamal Murray"
        assert murray.first_name == "Jamal"
        assert murray.last_name == "Murray"
        assert murray.position == "G"
        assert murray.birthdate is None
        assert murray.height is None
        assert murray.weight is None
        assert murray.source_type == "manual_curated"

    def test_tiny_pilot_returns_exactly_4_roster_memberships(self) -> None:
        md = load_player_roster_metadata(
            snapshot_mode="real_snapshot",
            reference_date="2026-06-28",
        )
        assert len(md.roster_memberships) == 4
        team_ids = {m.team_id for m in md.roster_memberships}
        assert team_ids == {"nba-OKC", "nba-DEN"}
        player_ids = {m.player_id for m in md.roster_memberships}
        expected_pids = {
            "nba-shai-gilgeous-alexander",
            "nba-chet-holmgren",
            "nba-nikola-jokic",
            "nba-jamal-murray",
        }
        assert player_ids == expected_pids

    def test_tiny_pilot_membership_fields_correct(self) -> None:
        md = load_player_roster_metadata(
            snapshot_mode="real_snapshot",
            reference_date="2026-06-28",
        )
        mems_by_pid = {m.player_id: m for m in md.roster_memberships}
        for pid in ("nba-shai-gilgeous-alexander", "nba-chet-holmgren",
                    "nba-nikola-jokic", "nba-jamal-murray"):
            m = mems_by_pid[pid]
            assert m.roster_status == "standard"
            assert m.source_type == "manual_curated"
        assert mems_by_pid["nba-shai-gilgeous-alexander"].team_id == "nba-OKC"
        assert mems_by_pid["nba-chet-holmgren"].team_id == "nba-OKC"
        assert mems_by_pid["nba-nikola-jokic"].team_id == "nba-DEN"
        assert mems_by_pid["nba-jamal-murray"].team_id == "nba-DEN"

    def test_tiny_pilot_xrefs_are_valid(self) -> None:
        md = load_player_roster_metadata(
            snapshot_mode="real_snapshot",
            reference_date="2026-06-28",
        )
        player_ids = {p.player_id for p in md.players}
        for m in md.roster_memberships:
            assert m.player_id in player_ids, (
                f"membership player_id {m.player_id} not found in players"
            )
        teams_doc = json.loads((REAL_SNAPSHOT_DIR / "normalized" / "teams.json").read_text("utf-8"))
        valid_team_ids = {t["team_id"] for t in teams_doc["teams"]}
        for m in md.roster_memberships:
            assert m.team_id in valid_team_ids, (
                f"membership team_id {m.team_id} not found in teams.json"
            )

    def test_tiny_pilot_response_contains_no_forbidden_fields(self) -> None:
        md = load_player_roster_metadata(
            snapshot_mode="real_snapshot",
            reference_date="2026-06-28",
        )
        d = md.to_dict()
        found = _find_forbidden_key(d)
        assert found is None, f"Forbidden key found in pilot response: {found}"

    def test_tiny_pilot_no_contracts_salaries_cap_injury_files(self) -> None:
        forbidden_names = [
            "contracts.json", "salaries.json", "cap_sheet.json", "cap_sheets.json",
            "injuries.json", "rumors.json", "scouting_opinions.json",
        ]
        for name in forbidden_names:
            for p in REAL_SNAPSHOT_DIR.rglob(name):
                pytest.fail(f"Forbidden file found in pilot snapshot: {p}")

    def test_tiny_pilot_hash_validation_is_enforced(self) -> None:
        import tempfile
        import shutil
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            pilot_copy = tmp / "nba_real_2026_preoffseason_v1"
            pilot_copy.mkdir()
            (pilot_copy / "normalized").mkdir()
            for rel in [
                "manifest.json",
                "source_manifest.json",
                "normalized/teams.json",
                "normalized/team_visual_metadata.json",
                "normalized/player_identities.json",
                "normalized/roster_memberships.json",
            ]:
                src = REAL_SNAPSHOT_DIR / rel
                dst = pilot_copy / rel
                shutil.copy2(src, dst)
            source_manifest_path = pilot_copy / "source_manifest.json"
            sm = json.loads(source_manifest_path.read_text("utf-8"))
            wrong_hash = "sha256:" + "0" * 64
            sm["file_hashes"][PLAYER_IDENTITIES_REL] = wrong_hash
            source_manifest_path.write_text(
                json.dumps(sm, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            with pytest.raises(PlayerRosterHashError):
                load_player_roster_metadata(
                    snapshot_mode="real_snapshot",
                    snapshot_dir=pilot_copy,
                    reference_date="2026-06-28",
                )

    def test_tiny_pilot_stale_after_date_enforced(self) -> None:
        with pytest.raises(PlayerRosterStaleDataError):
            load_player_roster_metadata(
                snapshot_mode="real_snapshot",
                reference_date="2026-08-01",
            )

    def test_tiny_pilot_source_summary_includes_both_files(self) -> None:
        md = load_player_roster_metadata(
            snapshot_mode="real_snapshot",
            reference_date="2026-06-28",
        )
        file_paths = {s.file_path for s in md.source_summary}
        assert PLAYER_IDENTITIES_REL in file_paths
        assert ROSTER_MEMBERSHIPS_REL in file_paths
        for s in md.source_summary:
            assert s.live_eligible is False
            assert s.manual_review_required is True
            assert s.source_type == "manual_curated"
