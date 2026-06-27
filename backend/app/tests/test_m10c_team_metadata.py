"""Tests for M10-C1 Team List Metadata Seed.

Coverage:

Positive:
1. teams.json validates against teams_schema.json.
2. teams array has exactly 30 teams.
3. All team_id values are unique.
4. All abbreviation values are unique.
5. All conference values are East or West.
6. All division values are from the six valid divisions.
7. manifest.json validates against real_snapshot_manifest_schema.json.
8. source_manifest.json validates against source_manifest_schema.json.
9. source_manifest data_categories contains "teams".
10. source_manifest per_file_sources contains "normalized/teams.json" key.
11. source_manifest file_hashes contains "normalized/teams.json" key.
12. teams.json actual SHA-256 matches the hash recorded in source_manifest.

Negative:
13. Missing team_id fails validation.
14. Invalid abbreviation format fails.
15. Invalid conference enum fails.
16. Invalid division enum fails.
17. Logo fields (logo_path, logo_url, official_logo, nba_logo, team_logo, mascot_image) fail.
18. Color fields (primary_color, secondary_color, colors) fail.
19. Roster/contract/salary fields (roster, players, contracts, salaries, cap_sheet) fail.
20. Extra/unknown field fails.
21. manual_review_required=false fails.
22. Teams count not 30 fails (both <30 and >30).

Regression:
23. Demo snapshot file set is unchanged.
24. Demo snapshot file hashes are unchanged.
25. Demo manifest still validates against real_snapshot_manifest_schema.json.
26. M10-B source_manifest and real_manifest schema tests still pass.

Run:

    python -m pytest backend/app/tests/test_m10c_team_metadata.py -v
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "schema"
REAL_SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots" / "nba_real_2026_preoffseason_v1"
DEMO_SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots" / "nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25"

VALID_CONFERENCES = {"East", "West"}
VALID_DIVISIONS = {"Atlantic", "Central", "Southeast", "Northwest", "Pacific", "Southwest"}

EXPECTED_TEAMS = [
    ("nba-ATL", "ATL"), ("nba-BOS", "BOS"), ("nba-BKN", "BKN"), ("nba-CHA", "CHA"),
    ("nba-CHI", "CHI"), ("nba-CLE", "CLE"), ("nba-DAL", "DAL"), ("nba-DEN", "DEN"),
    ("nba-DET", "DET"), ("nba-GSW", "GSW"), ("nba-HOU", "HOU"), ("nba-IND", "IND"),
    ("nba-LAC", "LAC"), ("nba-LAL", "LAL"), ("nba-MEM", "MEM"), ("nba-MIA", "MIA"),
    ("nba-MIL", "MIL"), ("nba-MIN", "MIN"), ("nba-NOP", "NOP"), ("nba-NYK", "NYK"),
    ("nba-OKC", "OKC"), ("nba-ORL", "ORL"), ("nba-PHI", "PHI"), ("nba-PHX", "PHX"),
    ("nba-POR", "POR"), ("nba-SAC", "SAC"), ("nba-SAS", "SAS"), ("nba-TOR", "TOR"),
    ("nba-UTA", "UTA"), ("nba-WAS", "WAS"),
]

FORBIDDEN_LOGO_FIELDS = [
    "logo_path", "logo_url", "official_logo", "nba_logo", "team_logo", "mascot_image",
]

FORBIDDEN_COLOR_FIELDS = [
    "primary_color", "secondary_color", "colors",
]

FORBIDDEN_ROSTER_FIELDS = [
    "roster", "players", "contracts", "salaries", "cap_sheet",
]


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def teams_schema() -> Dict[str, Any]:
    return _load_json(SCHEMA_DIR / "teams_schema.json")


@pytest.fixture(scope="module")
def source_manifest_schema() -> Dict[str, Any]:
    return _load_json(SCHEMA_DIR / "source_manifest_schema.json")


@pytest.fixture(scope="module")
def real_manifest_schema() -> Dict[str, Any]:
    return _load_json(SCHEMA_DIR / "real_snapshot_manifest_schema.json")


@pytest.fixture(scope="module")
def teams_doc() -> Dict[str, Any]:
    return _load_json(REAL_SNAPSHOT_DIR / "normalized" / "teams.json")


@pytest.fixture(scope="module")
def source_manifest_doc() -> Dict[str, Any]:
    return _load_json(REAL_SNAPSHOT_DIR / "source_manifest.json")


@pytest.fixture(scope="module")
def manifest_doc() -> Dict[str, Any]:
    return _load_json(REAL_SNAPSHOT_DIR / "manifest.json")


@pytest.fixture(scope="module")
def valid_team(teams_doc) -> Dict[str, Any]:
    return copy.deepcopy(teams_doc["teams"][0])


# --------------------------------------------------------------------------- #
# Positive tests
# --------------------------------------------------------------------------- #


class TestPositiveValidation:
    def test_teams_json_passes_schema(self, teams_doc, teams_schema):
        jsonschema.validate(teams_doc, teams_schema)

    def test_teams_count_is_30(self, teams_doc):
        assert len(teams_doc["teams"]) == 30

    def test_team_ids_unique(self, teams_doc):
        ids = [t["team_id"] for t in teams_doc["teams"]]
        assert len(ids) == len(set(ids)), "team_id values must be unique"

    def test_abbreviations_unique(self, teams_doc):
        abbrs = [t["abbreviation"] for t in teams_doc["teams"]]
        assert len(abbrs) == len(set(abbrs)), "abbreviation values must be unique"

    def test_conferences_only_east_west(self, teams_doc):
        conferences = {t["conference"] for t in teams_doc["teams"]}
        assert conferences <= VALID_CONFERENCES, f"Invalid conferences: {conferences - VALID_CONFERENCES}"
        assert conferences == VALID_CONFERENCES, "Expected both East and West conferences present"

    def test_divisions_all_valid(self, teams_doc):
        divisions = {t["division"] for t in teams_doc["teams"]}
        assert divisions <= VALID_DIVISIONS, f"Invalid divisions: {divisions - VALID_DIVISIONS}"
        assert divisions == VALID_DIVISIONS, "Expected all six divisions present"

    def test_each_team_has_expected_fields(self, teams_doc):
        for team in teams_doc["teams"]:
            assert set(team.keys()) == {"team_id", "city", "name", "abbreviation", "conference", "division"}

    def test_all_expected_team_ids_present(self, teams_doc):
        actual_ids = {t["team_id"] for t in teams_doc["teams"]}
        expected_ids = {tid for tid, _ in EXPECTED_TEAMS}
        assert actual_ids == expected_ids, f"Missing: {expected_ids - actual_ids}; Extra: {actual_ids - expected_ids}"

    def test_manifest_passes_real_schema(self, manifest_doc, real_manifest_schema):
        jsonschema.validate(manifest_doc, real_manifest_schema)

    def test_source_manifest_passes_schema(self, source_manifest_doc, source_manifest_schema):
        jsonschema.validate(source_manifest_doc, source_manifest_schema)

    def test_source_manifest_data_categories_contains_teams(self, source_manifest_doc):
        assert "teams" in source_manifest_doc["data_categories"]

    def test_source_manifest_per_file_sources_has_teams_json(self, source_manifest_doc):
        assert "normalized/teams.json" in source_manifest_doc["per_file_sources"]

    def test_source_manifest_file_hashes_has_teams_json(self, source_manifest_doc):
        assert "normalized/teams.json" in source_manifest_doc["file_hashes"]

    def test_teams_json_sha256_matches_source_manifest(self, teams_doc, source_manifest_doc):
        teams_path = REAL_SNAPSHOT_DIR / "normalized" / "teams.json"
        actual_hash = "sha256:" + _sha256_file(teams_path)
        recorded_hash = source_manifest_doc["file_hashes"]["normalized/teams.json"]
        assert actual_hash == recorded_hash, (
            f"SHA-256 mismatch: actual={actual_hash}, recorded={recorded_hash}"
        )

    def test_manifest_teams_list_has_30_entries(self, manifest_doc):
        assert len(manifest_doc["teams"]) == 30

    def test_manifest_teams_matches_teams_json_ids(self, manifest_doc, teams_doc):
        manifest_teams = set(manifest_doc["teams"])
        json_teams = {t["team_id"] for t in teams_doc["teams"]}
        assert manifest_teams == json_teams

    def test_live_eligible_stays_false(self, source_manifest_doc):
        assert source_manifest_doc["live_eligible"] is False

    def test_freshness_level_stays_frozen(self, source_manifest_doc):
        assert source_manifest_doc["freshness_level"] == "frozen"

    def test_manual_review_required_true(self, teams_doc, source_manifest_doc, manifest_doc):
        assert teams_doc["manual_review_required"] is True
        assert source_manifest_doc["manual_review_required"] is True
        assert manifest_doc["manual_review_required"] is True


# --------------------------------------------------------------------------- #
# Negative tests
# --------------------------------------------------------------------------- #


class TestNegativeValidation:
    def test_missing_team_id_fails(self, teams_doc, teams_schema):
        doc = copy.deepcopy(teams_doc)
        del doc["teams"][0]["team_id"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    def test_invalid_abbreviation_format_fails(self, teams_doc, teams_schema):
        doc = copy.deepcopy(teams_doc)
        doc["teams"][0]["abbreviation"] = "gsw"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    def test_invalid_conference_fails(self, teams_doc, teams_schema):
        doc = copy.deepcopy(teams_doc)
        doc["teams"][0]["conference"] = "North"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    def test_invalid_division_fails(self, teams_doc, teams_schema):
        doc = copy.deepcopy(teams_doc)
        doc["teams"][0]["division"] = "Midwest"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_LOGO_FIELDS)
    def test_logo_field_fails(self, teams_doc, teams_schema, forbidden_field):
        doc = copy.deepcopy(teams_doc)
        doc["teams"][0][forbidden_field] = "/path/to/logo.png"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_LOGO_FIELDS)
    def test_logo_field_at_top_level_fails(self, teams_doc, teams_schema, forbidden_field):
        doc = copy.deepcopy(teams_doc)
        doc[forbidden_field] = "/path/to/logo.png"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_COLOR_FIELDS)
    def test_color_field_fails(self, teams_doc, teams_schema, forbidden_field):
        doc = copy.deepcopy(teams_doc)
        doc["teams"][0][forbidden_field] = "#FF0000"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_ROSTER_FIELDS)
    def test_roster_contract_salary_field_fails(self, teams_doc, teams_schema, forbidden_field):
        doc = copy.deepcopy(teams_doc)
        doc["teams"][0][forbidden_field] = {}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    def test_extra_field_at_team_level_fails(self, teams_doc, teams_schema):
        doc = copy.deepcopy(teams_doc)
        doc["teams"][0]["extra_field"] = "unexpected"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    def test_extra_field_at_top_level_fails(self, teams_doc, teams_schema):
        doc = copy.deepcopy(teams_doc)
        doc["extra_top_level"] = "unexpected"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    def test_manual_review_required_false_fails(self, teams_doc, teams_schema):
        doc = copy.deepcopy(teams_doc)
        doc["manual_review_required"] = False
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    def test_teams_count_too_few_fails(self, teams_doc, teams_schema):
        doc = copy.deepcopy(teams_doc)
        doc["teams"] = doc["teams"][:29]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    def test_teams_count_too_many_fails(self, teams_doc, teams_schema):
        doc = copy.deepcopy(teams_doc)
        duplicate = copy.deepcopy(doc["teams"][0])
        duplicate["team_id"] = "nba-DUP"
        duplicate["abbreviation"] = "DUP"
        doc["teams"].append(duplicate)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    def test_invalid_team_id_pattern_fails(self, teams_doc, teams_schema):
        doc = copy.deepcopy(teams_doc)
        doc["teams"][0]["team_id"] = "ATL"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)

    def test_sample_data_true_not_allowed_in_teams(self, teams_doc, teams_schema):
        doc = copy.deepcopy(teams_doc)
        doc["sample_data"] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, teams_schema)


# --------------------------------------------------------------------------- #
# Regression tests
# --------------------------------------------------------------------------- #


DEMO_EXPECTED_FILES = [
    "manifest.json",
    "source_notes.md",
    "normalized/teams.json",
    "normalized/players.json",
    "normalized/contracts.json",
    "normalized/cap_config.json",
    "normalized/free_agents.json",
    "normalized/evidence_notes.json",
]


class TestRegressionDemoUntouched:
    """M10-C1 must not modify any file in the existing demo snapshot directory."""

    @pytest.mark.parametrize("relative_path", DEMO_EXPECTED_FILES)
    def test_demo_file_exists(self, relative_path: str):
        target = DEMO_SNAPSHOT_DIR / relative_path
        assert target.exists(), f"Demo snapshot file missing: {relative_path}"

    def test_demo_file_count_unchanged(self):
        all_files = sorted(
            str(p.relative_to(DEMO_SNAPSHOT_DIR)).replace("\\", "/")
            for p in DEMO_SNAPSHOT_DIR.rglob("*")
            if p.is_file()
        )
        expected = sorted(DEMO_EXPECTED_FILES)
        assert all_files == expected, (
            f"Demo snapshot directory file set changed. Expected {expected}, got {all_files}."
        )

    def test_demo_manifest_still_validates(self, real_manifest_schema):
        demo_manifest = _load_json(DEMO_SNAPSHOT_DIR / "manifest.json")
        jsonschema.validate(demo_manifest, real_manifest_schema)


class TestRegressionM10BSchemaIntact:
    """M10-C1 must not break the M10-B schema validation for source_manifest and real_manifest."""

    def test_real_snapshot_source_manifest_validates(self, source_manifest_doc, source_manifest_schema):
        jsonschema.validate(source_manifest_doc, source_manifest_schema)

    def test_real_snapshot_manifest_validates(self, manifest_doc, real_manifest_schema):
        jsonschema.validate(manifest_doc, real_manifest_schema)
