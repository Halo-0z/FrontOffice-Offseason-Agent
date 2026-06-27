"""Tests for M10-D1 Backend Real Snapshot Metadata Read Model.

Covers:

- Service positive (load, 30 teams, merged visual metadata, disclaimers)
- API positive (GET /api/snapshots/metadata?snapshot_mode=real_snapshot)
- API negative (missing/invalid snapshot_mode, demo/live/current/latest rejected)
- Forbidden-field response scanning (roster, contracts, salaries, cap_sheet,
  logos, official branding, execute/apply/commit/mutate/write, file_hashes,
  per_file_sources)
- Hard error tests (missing files, hash mismatch, schema mismatch,
  unknown team_id, abbreviation mismatch, no demo fallback)
- Regression (demo snapshot files unchanged, M10-B/C1/C2 tests still pass,
  no mutation endpoints exposed).

Run:

    python -m pytest backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py -v
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from backend.app.api import app
from backend.app.services.real_snapshot_metadata_reader import (
    REAL_SNAPSHOT_ID,
    RealSnapshotCrossReferenceError,
    RealSnapshotHashError,
    RealSnapshotMetadataError,
    RealSnapshotModeError,
    RealSnapshotNotFoundError,
    RealSnapshotSchemaError,
    load_real_snapshot_metadata,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
SCHEMA_DIR = REPO_ROOT / "schema"
REAL_SNAPSHOT_DIR = DATA_DIR / "snapshots" / REAL_SNAPSHOT_ID
DEMO_SNAPSHOT_DIR = DATA_DIR / "snapshots" / "nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25"


# --------------------------------------------------------------------------- #
# Forbidden keys set (mirrors api.py _FORBIDDEN_RESPONSE_KEYS + extra)
# --------------------------------------------------------------------------- #


FORBIDDEN_KEYS = frozenset({
    "roster", "players", "contracts", "salaries", "cap_sheet",
    "free_agents", "draft_assets",
    "logo_path", "logo_url", "official_logo", "nba_logo", "team_logo",
    "mascot_image", "official_branding", "official_colors", "brand_colors",
    "pantone", "brand_guidelines",
    "execute", "apply", "commit", "mutate", "write", "persist", "save",
    "delete", "update", "submit", "auto_execute", "auto_approve",
    "file_hashes", "per_file_sources",
})


def _find_forbidden_key(obj: Any, _path: str = "") -> str | None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            p = f"{_path}.{k}" if _path else str(k)
            if kl in FORBIDDEN_KEYS:
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


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="module")
def real_metadata() -> Dict[str, Any]:
    md = load_real_snapshot_metadata("real_snapshot", DATA_DIR, SCHEMA_DIR)
    return md.to_dict()


# --------------------------------------------------------------------------- #
# Service positive tests
# --------------------------------------------------------------------------- #


class TestServicePositive:
    def test_loads_real_snapshot_metadata_successfully(self) -> None:
        md = load_real_snapshot_metadata("real_snapshot", DATA_DIR, SCHEMA_DIR)
        assert md is not None
        d = md.to_dict()
        assert d["snapshot_mode"] == "real_snapshot"
        assert d["snapshot_id"] == REAL_SNAPSHOT_ID

    def test_returns_thirty_teams(self, real_metadata: Dict[str, Any]) -> None:
        assert len(real_metadata["teams"]) == 30

    def test_each_team_has_identity_fields(self, real_metadata: Dict[str, Any]) -> None:
        for t in real_metadata["teams"]:
            assert t["team_id"].startswith("nba-")
            assert t["abbreviation"]
            assert len(t["abbreviation"]) == 3
            assert t["city"]
            assert t["name"]
            assert t["conference"] in {"East", "West"}
            assert t["division"]

    def test_each_team_has_merged_visual_metadata(self, real_metadata: Dict[str, Any]) -> None:
        for t in real_metadata["teams"]:
            vm = t["visual_metadata"]
            assert vm is not None
            assert vm["accent_color"].startswith("#")
            assert len(vm["accent_color"]) == 7
            assert vm["secondary_accent_color"].startswith("#")
            assert len(vm["secondary_accent_color"]) == 7
            assert vm["badge_style"] in {
                "abbreviation_badge", "neutral_badge", "conference_badge"
            }
            assert vm["no_official_branding"] is True

    def test_no_official_branding_top_level_flag(self, real_metadata: Dict[str, Any]) -> None:
        assert real_metadata["no_official_branding"] is True

    def test_live_eligible_is_false(self, real_metadata: Dict[str, Any]) -> None:
        assert real_metadata["live_eligible"] is False

    def test_as_of_date_present(self, real_metadata: Dict[str, Any]) -> None:
        assert real_metadata["as_of_date"] == "2026-06-25"

    def test_freshness_label_present(self, real_metadata: Dict[str, Any]) -> None:
        assert real_metadata["freshness_label"]
        assert isinstance(real_metadata["freshness_label"], str)

    def test_data_freshness_warning_present(self, real_metadata: Dict[str, Any]) -> None:
        w = real_metadata["data_freshness_warning"]
        assert w
        assert isinstance(w, str)

    def test_data_categories_includes_teams_and_visual(self, real_metadata: Dict[str, Any]) -> None:
        cats = set(real_metadata["data_categories"])
        assert "teams" in cats
        assert "team_visual_metadata" in cats

    def test_source_name_is_non_official_palette(self, real_metadata: Dict[str, Any]) -> None:
        assert "non-official" in real_metadata["source_name"].lower() or "non_official" in real_metadata["source_name"].lower()

    def test_manual_review_required_true(self, real_metadata: Dict[str, Any]) -> None:
        assert real_metadata["manual_review_required"] is True

    def test_limitations_includes_non_official_disclaimer(self, real_metadata: Dict[str, Any]) -> None:
        lim = " ".join(real_metadata["limitations"]).lower()
        assert ("not official" in lim) or ("non-official" in lim) or ("non_official" in lim)

    def test_season_and_snapshot_type_present(self, real_metadata: Dict[str, Any]) -> None:
        assert real_metadata["season"]
        assert real_metadata["snapshot_type"]


# --------------------------------------------------------------------------- #
# API positive tests
# --------------------------------------------------------------------------- #


class TestApiPositive:
    def test_get_metadata_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/snapshots/metadata", params={"snapshot_mode": "real_snapshot"})
        assert resp.status_code == 200, resp.text

    def test_response_snapshot_mode_is_real_snapshot(self, client: TestClient) -> None:
        resp = client.get("/api/snapshots/metadata", params={"snapshot_mode": "real_snapshot"})
        body = resp.json()
        assert body["snapshot_mode"] == "real_snapshot"

    def test_response_contains_thirty_teams(self, client: TestClient) -> None:
        resp = client.get("/api/snapshots/metadata", params={"snapshot_mode": "real_snapshot"})
        body = resp.json()
        assert len(body["teams"]) == 30

    def test_response_contains_freshness_fields(self, client: TestClient) -> None:
        resp = client.get("/api/snapshots/metadata", params={"snapshot_mode": "real_snapshot"})
        body = resp.json()
        for k in (
            "snapshot_id", "snapshot_type", "season", "as_of_date",
            "freshness_label", "data_freshness_warning", "source_name",
            "manual_review_required", "live_eligible", "no_official_branding",
            "data_categories", "limitations",
        ):
            assert k in body, f"missing top-level key: {k}"

    def test_response_does_not_contain_raw_source_manifest_internals(
        self, client: TestClient
    ) -> None:
        resp = client.get("/api/snapshots/metadata", params={"snapshot_mode": "real_snapshot"})
        body = resp.json()
        assert "file_hashes" not in body
        assert "per_file_sources" not in body
        # Internal source_manifest keys should not leak
        assert "source_url" not in body
        assert "schema_version" not in body

    def test_response_forbidden_keys_scan(self, client: TestClient) -> None:
        resp = client.get("/api/snapshots/metadata", params={"snapshot_mode": "real_snapshot"})
        body = resp.json()
        bad = _find_forbidden_key(body)
        assert bad is None, f"forbidden key present at: {bad}"


# --------------------------------------------------------------------------- #
# API negative tests
# --------------------------------------------------------------------------- #


class TestApiNegative:
    def test_missing_snapshot_mode_returns_4xx(self, client: TestClient) -> None:
        resp = client.get("/api/snapshots/metadata")
        assert resp.status_code in (400, 422)

    def test_empty_snapshot_mode_returns_4xx(self, client: TestClient) -> None:
        resp = client.get("/api/snapshots/metadata", params={"snapshot_mode": ""})
        assert resp.status_code in (400, 422)

    def test_demo_mode_rejected(self, client: TestClient) -> None:
        resp = client.get("/api/snapshots/metadata", params={"snapshot_mode": "demo"})
        assert resp.status_code == 400

    def test_live_mode_rejected(self, client: TestClient) -> None:
        resp = client.get("/api/snapshots/metadata", params={"snapshot_mode": "live"})
        assert resp.status_code == 400

    def test_current_mode_rejected(self, client: TestClient) -> None:
        resp = client.get("/api/snapshots/metadata", params={"snapshot_mode": "current"})
        assert resp.status_code == 400

    def test_latest_mode_rejected(self, client: TestClient) -> None:
        resp = client.get("/api/snapshots/metadata", params={"snapshot_mode": "latest"})
        assert resp.status_code == 400

    def test_arbitrary_mode_rejected(self, client: TestClient) -> None:
        resp = client.get("/api/snapshots/metadata", params={"snapshot_mode": "foo"})
        assert resp.status_code == 400

    def test_post_method_not_allowed(self, client: TestClient) -> None:
        # Endpoint is GET-only; POST should not be routed as a mutation endpoint.
        resp = client.post("/api/snapshots/metadata", json={"snapshot_mode": "real_snapshot"})
        # FastAPI returns 405 Method Not Allowed for GET-only routes.
        assert resp.status_code in (405, 404)


# --------------------------------------------------------------------------- #
# Hard error tests
# --------------------------------------------------------------------------- #


def _copy_real_snapshot_to(tmp_path: Path) -> Path:
    """Copy the real snapshot dir to tmp_path and return its path."""
    dest = tmp_path / REAL_SNAPSHOT_ID
    shutil.copytree(REAL_SNAPSHOT_DIR, dest)
    return dest


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


class TestHardErrors:
    def test_wrong_snapshot_mode_raises_before_io(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        # Even with non-existent data dir, wrong mode must raise before touching disk.
        with pytest.raises(RealSnapshotModeError):
            load_real_snapshot_metadata("demo", data_dir=data_dir, schema_dir=SCHEMA_DIR)

    def test_missing_snapshot_directory_is_hard_error(self, tmp_path: Path) -> None:
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        with pytest.raises(RealSnapshotNotFoundError):
            load_real_snapshot_metadata("real_snapshot", data_dir=data_dir, schema_dir=SCHEMA_DIR)

    def test_missing_teams_json_is_hard_error(self, tmp_path: Path) -> None:
        snap = _copy_real_snapshot_to(tmp_path / "data" / "snapshots")
        (snap / "normalized" / "teams.json").unlink()
        with pytest.raises(RealSnapshotNotFoundError):
            load_real_snapshot_metadata(
                "real_snapshot",
                data_dir=tmp_path / "data",
                schema_dir=SCHEMA_DIR,
            )

    def test_missing_visual_metadata_json_is_hard_error(self, tmp_path: Path) -> None:
        snap = _copy_real_snapshot_to(tmp_path / "data" / "snapshots")
        (snap / "normalized" / "team_visual_metadata.json").unlink()
        with pytest.raises(RealSnapshotNotFoundError):
            load_real_snapshot_metadata(
                "real_snapshot",
                data_dir=tmp_path / "data",
                schema_dir=SCHEMA_DIR,
            )

    def test_missing_manifest_json_is_hard_error(self, tmp_path: Path) -> None:
        snap = _copy_real_snapshot_to(tmp_path / "data" / "snapshots")
        (snap / "manifest.json").unlink()
        with pytest.raises(RealSnapshotNotFoundError):
            load_real_snapshot_metadata(
                "real_snapshot",
                data_dir=tmp_path / "data",
                schema_dir=SCHEMA_DIR,
            )

    def test_missing_source_manifest_json_is_hard_error(self, tmp_path: Path) -> None:
        snap = _copy_real_snapshot_to(tmp_path / "data" / "snapshots")
        (snap / "source_manifest.json").unlink()
        with pytest.raises(RealSnapshotNotFoundError):
            load_real_snapshot_metadata(
                "real_snapshot",
                data_dir=tmp_path / "data",
                schema_dir=SCHEMA_DIR,
            )

    def test_schema_mismatch_teams_is_hard_error(self, tmp_path: Path) -> None:
        snap = _copy_real_snapshot_to(tmp_path / "data" / "snapshots")
        teams = json.loads((snap / "normalized" / "teams.json").read_text(encoding="utf-8"))
        # Corrupt a team entry by removing required field 'city'
        teams["teams"][0].pop("city")
        _write_json(snap / "normalized" / "teams.json", teams)
        # Hash will also mismatch, but schema validation runs first.
        with pytest.raises((RealSnapshotSchemaError, RealSnapshotHashError)):
            load_real_snapshot_metadata(
                "real_snapshot",
                data_dir=tmp_path / "data",
                schema_dir=SCHEMA_DIR,
            )

    def test_hash_mismatch_is_hard_error(self, tmp_path: Path) -> None:
        snap = _copy_real_snapshot_to(tmp_path / "data" / "snapshots")
        # Tweak teams.json (add trailing whitespace) and update source_manifest hash
        # so schema passes but hash entry is wrong (we'll tamper with the file after
        # restoring a wrong expected hash).
        teams_path = snap / "normalized" / "teams.json"
        original = teams_path.read_text(encoding="utf-8")
        # Tamper the file (append a space after a bracket to change hash without breaking JSON).
        tampered = original.replace("\n]", "\n ]", 1)
        teams_path.write_text(tampered, encoding="utf-8")
        with pytest.raises(RealSnapshotHashError):
            load_real_snapshot_metadata(
                "real_snapshot",
                data_dir=tmp_path / "data",
                schema_dir=SCHEMA_DIR,
            )

    def test_unknown_team_id_in_visual_metadata_is_hard_error(self, tmp_path: Path) -> None:
        snap = _copy_real_snapshot_to(tmp_path / "data" / "snapshots")
        vpath = snap / "normalized" / "team_visual_metadata.json"
        vdoc = json.loads(vpath.read_text(encoding="utf-8"))
        # Replace first team_id with a fake id (after re-signing the hash to bypass hash check).
        original_tid = vdoc["visual_metadata"][0]["team_id"]
        vdoc["visual_metadata"][0]["team_id"] = "nba-ZZZ"
        _write_json(vpath, vdoc)
        # Update source_manifest hash to the new file hash to bypass hash check
        sm_path = snap / "source_manifest.json"
        sm = json.loads(sm_path.read_text(encoding="utf-8"))
        sm["file_hashes"]["normalized/team_visual_metadata.json"] = (
            f"sha256:{_sha256_file(vpath)}"
        )
        _write_json(sm_path, sm)
        with pytest.raises(RealSnapshotCrossReferenceError):
            load_real_snapshot_metadata(
                "real_snapshot",
                data_dir=tmp_path / "data",
                schema_dir=SCHEMA_DIR,
            )

    def test_visual_metadata_missing_for_a_team_is_hard_error(self, tmp_path: Path) -> None:
        snap = _copy_real_snapshot_to(tmp_path / "data" / "snapshots")
        vpath = snap / "normalized" / "team_visual_metadata.json"
        vdoc = json.loads(vpath.read_text(encoding="utf-8"))
        # Remove first entry, then re-sign hash and add dummy schema allowance
        vdoc["visual_metadata"].pop(0)
        _write_json(vpath, vdoc)
        sm_path = snap / "source_manifest.json"
        sm = json.loads(sm_path.read_text(encoding="utf-8"))
        sm["file_hashes"]["normalized/team_visual_metadata.json"] = (
            f"sha256:{_sha256_file(vpath)}"
        )
        _write_json(sm_path, sm)
        # Schema will catch minItems=30 first -> schema error.
        with pytest.raises((RealSnapshotSchemaError, RealSnapshotCrossReferenceError)):
            load_real_snapshot_metadata(
                "real_snapshot",
                data_dir=tmp_path / "data",
                schema_dir=SCHEMA_DIR,
            )

    def test_abbreviation_mismatch_is_hard_error(self, tmp_path: Path) -> None:
        snap = _copy_real_snapshot_to(tmp_path / "data" / "snapshots")
        vpath = snap / "normalized" / "team_visual_metadata.json"
        vdoc = json.loads(vpath.read_text(encoding="utf-8"))
        # Change abbreviation on first entry to mismatch teams.json
        original_abbr = vdoc["visual_metadata"][0]["abbreviation"]
        vdoc["visual_metadata"][0]["abbreviation"] = "ZZZ"
        _write_json(vpath, vdoc)
        sm_path = snap / "source_manifest.json"
        sm = json.loads(sm_path.read_text(encoding="utf-8"))
        sm["file_hashes"]["normalized/team_visual_metadata.json"] = (
            f"sha256:{_sha256_file(vpath)}"
        )
        _write_json(sm_path, sm)
        with pytest.raises(RealSnapshotCrossReferenceError):
            load_real_snapshot_metadata(
                "real_snapshot",
                data_dir=tmp_path / "data",
                schema_dir=SCHEMA_DIR,
            )

    def test_no_fallback_to_demo_when_real_missing(self, tmp_path: Path) -> None:
        """Even if a demo snapshot exists in data_dir, missing real snapshot must hard error."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        snap_parent = data_dir / "snapshots"
        snap_parent.mkdir()
        # Copy demo snapshot into place (but not the real one)
        shutil.copytree(DEMO_SNAPSHOT_DIR, snap_parent / DEMO_SNAPSHOT_DIR.name)
        with pytest.raises(RealSnapshotNotFoundError):
            load_real_snapshot_metadata(
                "real_snapshot",
                data_dir=data_dir,
                schema_dir=SCHEMA_DIR,
            )

    def test_no_fallback_to_demo_when_real_corrupted(self, tmp_path: Path) -> None:
        """Corrupted real snapshot must hard error, not silently serve demo."""
        snap = _copy_real_snapshot_to(tmp_path / "data" / "snapshots")
        # Corrupt teams.json
        (snap / "normalized" / "teams.json").write_text("{not valid json", encoding="utf-8")
        # Also copy demo to show it exists but must not be used
        snap_parent = tmp_path / "data" / "snapshots"
        shutil.copytree(DEMO_SNAPSHOT_DIR, snap_parent / DEMO_SNAPSHOT_DIR.name)
        with pytest.raises(RealSnapshotMetadataError):
            load_real_snapshot_metadata(
                "real_snapshot",
                data_dir=tmp_path / "data",
                schema_dir=SCHEMA_DIR,
            )


# --------------------------------------------------------------------------- #
# Regression tests
# --------------------------------------------------------------------------- #


class TestRegression:
    def test_demo_snapshot_file_set_unchanged(self) -> None:
        """Demo snapshot directory must have exactly the expected set of files."""
        expected = {
            "manifest.json",
            "source_notes.md",
            "normalized/cap_config.json",
            "normalized/contracts.json",
            "normalized/evidence_notes.json",
            "normalized/free_agents.json",
            "normalized/players.json",
            "normalized/teams.json",
        }
        found = set()
        for p in DEMO_SNAPSHOT_DIR.rglob("*"):
            if p.is_file():
                found.add(str(p.relative_to(DEMO_SNAPSHOT_DIR)).replace("\\", "/"))
        assert found == expected, f"demo snapshot set changed: {found ^ expected}"

    def test_teams_json_hash_unchanged(self) -> None:
        """normalized/teams.json in real snapshot must not be modified."""
        # Expected hash from M10-C1 sealed state (verified in C2 tests).
        teams_path = REAL_SNAPSHOT_DIR / "normalized" / "teams.json"
        actual = _sha256_file(teams_path)
        expected = "5b1e388bb2b7506832e7fbb0a06e105b9478d4a5caea9fe9514032bd22dc5fbb"
        assert actual == expected, (
            f"normalized/teams.json hash changed! expected {expected}, got {actual}"
        )

    def test_snapshot_loader_not_modified(self) -> None:
        """snapshot_loader.py must not be modified by M10-D1."""
        loader_path = REPO_ROOT / "backend" / "app" / "services" / "snapshot_loader.py"
        assert loader_path.is_file()
        # Sanity: the loader does NOT import real_snapshot_metadata_reader.
        text = loader_path.read_text(encoding="utf-8")
        assert "real_snapshot_metadata_reader" not in text

    def test_no_mutation_endpoints_exposed(self, client: TestClient) -> None:
        """Ensure no POST/PUT/PATCH/DELETE /api/snapshots/* endpoints exist."""
        for path in (
            "/api/snapshots/execute",
            "/api/snapshots/apply",
            "/api/snapshots/write",
            "/api/snapshots/commit",
            "/api/snapshots/mutate",
            "/api/snapshots/update",
            "/api/snapshots/delete",
        ):
            resp = client.post(path, json={})
            assert resp.status_code in (404, 405), f"{path} returned {resp.status_code}"
            resp2 = client.put(path, json={})
            assert resp2.status_code in (404, 405), f"{path} PUT returned {resp2.status_code}"

    def test_api_routes_list_includes_metadata_get_only(self, client: TestClient) -> None:
        """OpenAPI must list GET /api/snapshots/metadata but no write variants."""
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        paths = spec.get("paths", {})
        assert "/api/snapshots/metadata" in paths
        methods = set(paths["/api/snapshots/metadata"].keys())
        assert methods == {"get"}, f"expected only GET, got {methods}"

    def test_response_snapshot_mode_not_live_or_latest(self, client: TestClient) -> None:
        resp = client.get("/api/snapshots/metadata", params={"snapshot_mode": "real_snapshot"})
        body = resp.json()
        # As a data-status declaration, the response must not call itself live/current/latest.
        # (The word "live" may appear inside data_freshness_warning as a negation; that's fine.
        # But no top-level key is named live/current/latest.)
        for forbidden_top_key in ("live", "current", "latest", "live_data", "current_roster"):
            assert forbidden_top_key not in body
        assert body["live_eligible"] is False
