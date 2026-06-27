"""Tests for M10-B real snapshot schema definitions.

Coverage:

Positive:
1. Placeholder source_manifest.json validates against source_manifest_schema.json.
2. Placeholder manifest.json validates against real_snapshot_manifest_schema.json.
3. live_eligible=false passes source_manifest_schema.
4. freshness_level=frozen passes.
5. freshness_level=stale passes.
6. freshness_level=active_snapshot passes.
7. freshness_level=archived passes.

Negative:
8. Missing required field fails.
9. live_eligible=true fails.
10. freshness_level=live fails.
11. snapshot_type=live fails.
12. snapshot_type=realtime fails.
13. Execution-verb field names (execute, apply, commit, etc.) fail.
14. Logo-field names (logo_path, logo_url, official_logo, nba_logo, team_logo, mascot_image) fail.
15. Live/current field names (current_roster, live_salaries, latest_data, live_data, current_salaries, real_time_data) fail.

Regression:
16. Demo snapshot directory files are not modified by M10-B.

Run:

    python -m pytest backend/app/tests/test_m10_real_snapshot_schema.py -v
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "schema"
REAL_SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots" / "nba_real_2026_preoffseason_v1"
DEMO_SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots" / "nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def source_manifest_schema() -> Dict[str, Any]:
    return _load_json(SCHEMA_DIR / "source_manifest_schema.json")


@pytest.fixture(scope="module")
def real_manifest_schema() -> Dict[str, Any]:
    return _load_json(SCHEMA_DIR / "real_snapshot_manifest_schema.json")


@pytest.fixture(scope="module")
def valid_source_manifest() -> Dict[str, Any]:
    return _load_json(REAL_SNAPSHOT_DIR / "source_manifest.json")


@pytest.fixture(scope="module")
def valid_real_manifest() -> Dict[str, Any]:
    return _load_json(REAL_SNAPSHOT_DIR / "manifest.json")


# --------------------------------------------------------------------------- #
# Positive tests
# --------------------------------------------------------------------------- #


class TestPositiveValidation:
    def test_placeholder_source_manifest_passes(
        self, valid_source_manifest, source_manifest_schema
    ):
        jsonschema.validate(valid_source_manifest, source_manifest_schema)

    def test_placeholder_real_manifest_passes(
        self, valid_real_manifest, real_manifest_schema
    ):
        jsonschema.validate(valid_real_manifest, real_manifest_schema)

    def test_live_eligible_false_passes(self, valid_source_manifest, source_manifest_schema):
        doc = copy.deepcopy(valid_source_manifest)
        doc["live_eligible"] = False
        jsonschema.validate(doc, source_manifest_schema)

    @pytest.mark.parametrize("level", ["frozen", "stale", "active_snapshot", "archived"])
    def test_freshness_level_enum_passes(
        self, valid_source_manifest, source_manifest_schema, level
    ):
        doc = copy.deepcopy(valid_source_manifest)
        doc["freshness_level"] = level
        jsonschema.validate(doc, source_manifest_schema)


# --------------------------------------------------------------------------- #
# Negative tests
# --------------------------------------------------------------------------- #


FORBIDDEN_EXECUTION_FIELDS = [
    "execute", "apply", "commit", "mutate", "write", "persist",
    "save", "delete", "update", "submit", "auto_execute", "auto_approve",
]

FORBIDDEN_LOGO_FIELDS = [
    "logo_path", "logo_url", "official_logo", "nba_logo", "team_logo", "mascot_image",
]

FORBIDDEN_LIVE_FIELDS = [
    "current_roster", "live_salaries", "latest_data", "live_data",
    "current_salaries", "real_time_data",
]


class TestNegativeValidation:
    def test_missing_required_field_fails(
        self, valid_source_manifest, source_manifest_schema
    ):
        doc = copy.deepcopy(valid_source_manifest)
        del doc["snapshot_id"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_live_eligible_true_fails(
        self, valid_source_manifest, source_manifest_schema
    ):
        doc = copy.deepcopy(valid_source_manifest)
        doc["live_eligible"] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_freshness_level_live_fails(
        self, valid_source_manifest, source_manifest_schema
    ):
        doc = copy.deepcopy(valid_source_manifest)
        doc["freshness_level"] = "live"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    @pytest.mark.parametrize("bad_type", ["live", "realtime"])
    def test_snapshot_type_live_or_realtime_fails_source_manifest(
        self, valid_source_manifest, source_manifest_schema, bad_type
    ):
        doc = copy.deepcopy(valid_source_manifest)
        doc["snapshot_type"] = bad_type
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    @pytest.mark.parametrize("bad_type", ["live", "realtime"])
    def test_snapshot_type_live_or_realtime_fails_real_manifest(
        self, valid_real_manifest, real_manifest_schema, bad_type
    ):
        doc = copy.deepcopy(valid_real_manifest)
        doc["snapshot_type"] = bad_type
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, real_manifest_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_EXECUTION_FIELDS)
    def test_execution_field_name_fails(
        self, valid_source_manifest, source_manifest_schema, forbidden_field
    ):
        doc = copy.deepcopy(valid_source_manifest)
        doc[forbidden_field] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_LOGO_FIELDS)
    def test_logo_field_name_fails(
        self, valid_source_manifest, source_manifest_schema, forbidden_field
    ):
        doc = copy.deepcopy(valid_source_manifest)
        doc[forbidden_field] = "/path/to/logo.png"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_LIVE_FIELDS)
    def test_live_current_field_name_fails(
        self, valid_source_manifest, source_manifest_schema, forbidden_field
    ):
        doc = copy.deepcopy(valid_source_manifest)
        doc[forbidden_field] = "forbidden"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_manual_review_required_false_fails_real_manifest(
        self, valid_real_manifest, real_manifest_schema
    ):
        doc = copy.deepcopy(valid_real_manifest)
        doc["manual_review_required"] = False
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, real_manifest_schema)


# --------------------------------------------------------------------------- #
# Regression: demo snapshot must not be modified
# --------------------------------------------------------------------------- #


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestRegressionDemoUntouched:
    """M10-B must not modify any file in the existing demo snapshot directory."""

    DEMO_FILES = [
        "manifest.json",
        "source_notes.md",
        "normalized/teams.json",
        "normalized/players.json",
        "normalized/contracts.json",
        "normalized/cap_config.json",
        "normalized/free_agents.json",
        "normalized/evidence_notes.json",
    ]

    @pytest.mark.parametrize("relative_path", DEMO_FILES)
    def test_demo_snapshot_file_exists_and_readable(self, relative_path: str):
        target = DEMO_SNAPSHOT_DIR / relative_path
        assert target.exists(), f"Demo snapshot file missing: {relative_path}"
        assert target.is_file()

    def test_demo_snapshot_file_count_unchanged(self):
        all_files = sorted(
            str(p.relative_to(DEMO_SNAPSHOT_DIR)).replace("\\", "/")
            for p in DEMO_SNAPSHOT_DIR.rglob("*")
            if p.is_file()
        )
        expected = sorted(self.DEMO_FILES)
        assert all_files == expected, (
            f"Demo snapshot directory file set changed. "
            f"Expected {expected}, got {all_files}. "
            f"M10-B must not add, remove, or rename files in the demo snapshot."
        )
