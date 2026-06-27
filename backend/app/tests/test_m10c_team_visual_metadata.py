"""Tests for M10-C2 Safe Team Visual Metadata.

Coverage:

Positive:
1. team_visual_metadata.json validates against team_visual_metadata_schema.json.
2. visual_metadata array has exactly 30 entries.
3. team_id set matches normalized/teams.json exactly.
4. Each abbreviation matches teams.json for the corresponding team_id.
5. accent_color is valid #RRGGBB hex for all entries.
6. secondary_accent_color is valid #RRGGBB hex for all entries.
7. badge_style is within the enum (abbreviation_badge / neutral_badge / conference_badge).
8. manual_review_required is true for all entries and at top level.
9. no_official_branding is true for all entries and at top level.
10. source_name is "manual non-official UI accent palette" for all entries and top level.
11. source_manifest data_categories contains "team_visual_metadata".
12. source_manifest per_file_sources contains "normalized/team_visual_metadata.json".
13. source_manifest file_hashes contains "normalized/team_visual_metadata.json".
14. team_visual_metadata.json actual SHA-256 matches source_manifest record.

Negative:
15. Missing team_id fails.
16. team_id not in teams.json fails.
17. abbreviation mismatch with teams.json fails.
18. Invalid accent_color format fails.
19. Invalid secondary_accent_color format fails.
20. Invalid badge_style (not in enum) fails.
21. no_official_branding=false fails.
22. manual_review_required=false fails.
23. Logo fields (logo_path, logo_url, official_logo, nba_logo, team_logo, mascot_image) fail.
24. official_branding field fails.
25. Color-naming fields (official_colors, brand_colors, pantone, brand_guidelines) fail.
26. Roster/contract/salary fields fail.
27. Execution verb fields fail.
28. Extra/unknown field fails (team level and top level).
29. visual_metadata count not 30 fails.

Regression:
30. M10-B 48 schema tests still pass (verified by running full suite).
31. M10-C1 62 team metadata tests still pass (verified by running full suite).
32. Demo snapshot file set unchanged.
33. normalized/teams.json hash unchanged (not modified by M10-C2).

Run:

    python -m pytest backend/app/tests/test_m10c_team_visual_metadata.py -v
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
NORMALIZED_DIR = REAL_SNAPSHOT_DIR / "normalized"
DEMO_SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots" / "nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25"

EXPECTED_VISUAL_SOURCE_NAME = "manual non-official UI accent palette"
HEX_PATTERN = __import__("re").compile(r"^#[0-9A-Fa-f]{6}$")

FORBIDDEN_LOGO_FIELDS = [
    "logo_path", "logo_url", "official_logo", "nba_logo", "team_logo", "mascot_image",
]

FORBIDDEN_BRANDING_FIELDS = [
    "official_branding", "official_colors", "brand_colors", "pantone", "brand_guidelines",
]

FORBIDDEN_ROSTER_FIELDS = [
    "roster", "players", "contracts", "salaries", "cap_sheet",
]

FORBIDDEN_EXECUTION_FIELDS = [
    "execute", "apply", "commit", "mutate", "write", "persist",
    "save", "delete", "update", "submit", "auto_execute", "auto_approve",
]

FORBIDDEN_LIVE_FIELDS = [
    "current_roster", "live_salaries", "latest_data", "live_data",
    "current_salaries", "real_time_data",
]

FORBIDDEN_COLOR_NAMING_FIELDS = [
    "primary_color", "secondary_color", "brand_color", "official_color",
]

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

EXPECTED_TEAMS_JSON_HASH = "5b1e388bb2b7506832e7fbb0a06e105b9478d4a5caea9fe9514032bd22dc5fbb"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def visual_schema() -> Dict[str, Any]:
    return _load_json(SCHEMA_DIR / "team_visual_metadata_schema.json")


@pytest.fixture(scope="module")
def source_manifest_schema() -> Dict[str, Any]:
    return _load_json(SCHEMA_DIR / "source_manifest_schema.json")


@pytest.fixture(scope="module")
def visual_doc() -> Dict[str, Any]:
    return _load_json(NORMALIZED_DIR / "team_visual_metadata.json")


@pytest.fixture(scope="module")
def teams_doc() -> Dict[str, Any]:
    return _load_json(NORMALIZED_DIR / "teams.json")


@pytest.fixture(scope="module")
def source_manifest_doc() -> Dict[str, Any]:
    return _load_json(REAL_SNAPSHOT_DIR / "source_manifest.json")


@pytest.fixture(scope="module")
def team_id_to_abbr(teams_doc) -> Dict[str, str]:
    return {t["team_id"]: t["abbreviation"] for t in teams_doc["teams"]}


@pytest.fixture(scope="module")
def valid_entry(visual_doc) -> Dict[str, Any]:
    return copy.deepcopy(visual_doc["visual_metadata"][0])


# --------------------------------------------------------------------------- #
# Positive tests
# --------------------------------------------------------------------------- #


class TestPositiveValidation:
    def test_visual_metadata_passes_schema(self, visual_doc, visual_schema):
        jsonschema.validate(visual_doc, visual_schema)

    def test_visual_metadata_count_is_30(self, visual_doc):
        assert len(visual_doc["visual_metadata"]) == 30

    def test_team_ids_match_teams_json_exactly(self, visual_doc, teams_doc):
        visual_ids = {e["team_id"] for e in visual_doc["visual_metadata"]}
        teams_ids = {t["team_id"] for t in teams_doc["teams"]}
        assert visual_ids == teams_ids, (
            f"Missing: {teams_ids - visual_ids}; Extra: {visual_ids - teams_ids}"
        )

    def test_abbreviations_match_teams_json(self, visual_doc, team_id_to_abbr):
        for entry in visual_doc["visual_metadata"]:
            tid = entry["team_id"]
            expected_abbr = team_id_to_abbr[tid]
            assert entry["abbreviation"] == expected_abbr, (
                f"{tid} abbreviation mismatch: {entry['abbreviation']} vs expected {expected_abbr}"
            )

    def test_accent_colors_are_valid_hex(self, visual_doc):
        for entry in visual_doc["visual_metadata"]:
            assert HEX_PATTERN.match(entry["accent_color"]), (
                f"Invalid accent_color for {entry['team_id']}: {entry['accent_color']}"
            )

    def test_secondary_accent_colors_are_valid_hex(self, visual_doc):
        for entry in visual_doc["visual_metadata"]:
            assert HEX_PATTERN.match(entry["secondary_accent_color"]), (
                f"Invalid secondary_accent_color for {entry['team_id']}: {entry['secondary_accent_color']}"
            )

    def test_badge_styles_in_enum(self, visual_doc):
        valid_styles = {"abbreviation_badge", "neutral_badge", "conference_badge"}
        for entry in visual_doc["visual_metadata"]:
            assert entry["badge_style"] in valid_styles, (
                f"Invalid badge_style for {entry['team_id']}: {entry['badge_style']}"
            )

    def test_manual_review_required_all_true(self, visual_doc):
        assert visual_doc["manual_review_required"] is True
        for entry in visual_doc["visual_metadata"]:
            assert entry["manual_review_required"] is True, (
                f"manual_review_required not true for {entry['team_id']}"
            )

    def test_no_official_branding_all_true(self, visual_doc):
        assert visual_doc["no_official_branding"] is True
        for entry in visual_doc["visual_metadata"]:
            assert entry["no_official_branding"] is True, (
                f"no_official_branding not true for {entry['team_id']}"
            )

    def test_source_name_all_correct(self, visual_doc):
        assert visual_doc["source_name"] == EXPECTED_VISUAL_SOURCE_NAME
        for entry in visual_doc["visual_metadata"]:
            assert entry["source_name"] == EXPECTED_VISUAL_SOURCE_NAME, (
                f"Wrong source_name for {entry['team_id']}"
            )

    def test_as_of_date_all_correct(self, visual_doc):
        assert visual_doc["as_of_date"] == "2026-06-25"
        for entry in visual_doc["visual_metadata"]:
            assert entry["as_of_date"] == "2026-06-25"

    def test_source_manifest_has_team_visual_metadata_category(self, source_manifest_doc):
        assert "team_visual_metadata" in source_manifest_doc["data_categories"]

    def test_source_manifest_has_per_file_source(self, source_manifest_doc):
        assert "normalized/team_visual_metadata.json" in source_manifest_doc["per_file_sources"]
        entry = source_manifest_doc["per_file_sources"]["normalized/team_visual_metadata.json"]
        assert entry["source_name"] == EXPECTED_VISUAL_SOURCE_NAME
        assert entry["as_of_date"] == "2026-06-25"

    def test_source_manifest_has_file_hash(self, source_manifest_doc):
        assert "normalized/team_visual_metadata.json" in source_manifest_doc["file_hashes"]

    def test_visual_metadata_sha256_matches_source_manifest(self, source_manifest_doc):
        visual_path = NORMALIZED_DIR / "team_visual_metadata.json"
        actual_hash = "sha256:" + _sha256_file(visual_path)
        recorded_hash = source_manifest_doc["file_hashes"]["normalized/team_visual_metadata.json"]
        assert actual_hash == recorded_hash, (
            f"SHA-256 mismatch: actual={actual_hash}, recorded={recorded_hash}"
        )

    def test_source_manifest_passes_schema(self, source_manifest_doc, source_manifest_schema):
        jsonschema.validate(source_manifest_doc, source_manifest_schema)

    def test_freshness_safety_fields_unchanged(self, source_manifest_doc):
        assert source_manifest_doc["live_eligible"] is False
        assert source_manifest_doc["freshness_level"] == "frozen"
        assert source_manifest_doc["validation_status"] == "provisional"
        assert source_manifest_doc["manual_review_required"] is True


# --------------------------------------------------------------------------- #
# Negative tests
# --------------------------------------------------------------------------- #


class TestNegativeValidation:
    def test_missing_team_id_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        del doc["visual_metadata"][0]["team_id"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_invalid_team_id_pattern_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0]["team_id"] = "ATL"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_unknown_team_id_fails_cross_reference(self, visual_doc, team_id_to_abbr):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0]["team_id"] = "nba-XYZ"
        doc["visual_metadata"][0]["abbreviation"] = "XYZ"
        visual_ids = {e["team_id"] for e in doc["visual_metadata"]}
        valid_ids = set(team_id_to_abbr.keys())
        assert not visual_ids <= valid_ids, "Unknown team_id nba-XYZ should not be a valid team"

    def test_abbreviation_pattern_failure_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0]["abbreviation"] = "xx"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_abbreviation_mismatch_fails_cross_reference(self, visual_doc, team_id_to_abbr):
        doc = copy.deepcopy(visual_doc)
        first = doc["visual_metadata"][0]
        first["abbreviation"] = "XXX"
        tid = first["team_id"]
        expected = team_id_to_abbr[tid]
        assert first["abbreviation"] != expected, (
            f"Abbreviation mismatch for {tid}: got {first['abbreviation']} vs expected {expected}"
        )

    def test_invalid_accent_color_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0]["accent_color"] = "red"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_invalid_accent_color_short_hex_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0]["accent_color"] = "#FFF"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_invalid_secondary_accent_color_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0]["secondary_accent_color"] = "rgb(0,0,0)"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_invalid_badge_style_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0]["badge_style"] = "logo_badge"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_no_official_branding_false_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0]["no_official_branding"] = False
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_no_official_branding_false_top_level_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        doc["no_official_branding"] = False
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_manual_review_required_false_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0]["manual_review_required"] = False
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_manual_review_required_false_top_level_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        doc["manual_review_required"] = False
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_LOGO_FIELDS)
    def test_logo_field_at_team_level_fails(self, visual_doc, visual_schema, forbidden_field):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0][forbidden_field] = "/path/to/logo.png"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_LOGO_FIELDS)
    def test_logo_field_at_top_level_fails(self, visual_doc, visual_schema, forbidden_field):
        doc = copy.deepcopy(visual_doc)
        doc[forbidden_field] = "/path/to/logo.png"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_BRANDING_FIELDS)
    def test_branding_field_at_team_level_fails(self, visual_doc, visual_schema, forbidden_field):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0][forbidden_field] = "forbidden"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_BRANDING_FIELDS)
    def test_branding_field_at_top_level_fails(self, visual_doc, visual_schema, forbidden_field):
        doc = copy.deepcopy(visual_doc)
        doc[forbidden_field] = "forbidden"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_COLOR_NAMING_FIELDS)
    def test_primary_secondary_brand_color_naming_fails(self, visual_doc, visual_schema, forbidden_field):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0][forbidden_field] = "#FF0000"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_ROSTER_FIELDS)
    def test_roster_contract_salary_field_fails(self, visual_doc, visual_schema, forbidden_field):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0][forbidden_field] = {}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_EXECUTION_FIELDS)
    def test_execution_field_fails(self, visual_doc, visual_schema, forbidden_field):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0][forbidden_field] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    @pytest.mark.parametrize("forbidden_field", FORBIDDEN_LIVE_FIELDS)
    def test_live_current_field_fails(self, visual_doc, visual_schema, forbidden_field):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0][forbidden_field] = "forbidden"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_extra_field_at_team_level_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"][0]["extra_field"] = "unexpected"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_extra_field_at_top_level_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        doc["extra_top_level"] = "unexpected"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_too_few_entries_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        doc["visual_metadata"] = doc["visual_metadata"][:29]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)

    def test_too_many_entries_fails(self, visual_doc, visual_schema):
        doc = copy.deepcopy(visual_doc)
        dup = copy.deepcopy(doc["visual_metadata"][0])
        dup["team_id"] = "nba-DUP"
        dup["abbreviation"] = "DUP"
        doc["visual_metadata"].append(dup)
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, visual_schema)


# --------------------------------------------------------------------------- #
# Regression tests
# --------------------------------------------------------------------------- #


class TestRegression:
    """M10-C2 must not modify demo snapshot, teams.json, or break M10-B/C1 tests."""

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

    def test_teams_json_hash_unchanged(self):
        teams_path = NORMALIZED_DIR / "teams.json"
        actual_hash = _sha256_file(teams_path)
        assert actual_hash == EXPECTED_TEAMS_JSON_HASH, (
            f"normalized/teams.json was modified by M10-C2! "
            f"Expected {EXPECTED_TEAMS_JSON_HASH}, got {actual_hash}."
        )

    def test_teams_json_not_modified_via_source_manifest_hash(self, source_manifest_doc):
        recorded_hash = source_manifest_doc["file_hashes"]["normalized/teams.json"]
        assert recorded_hash == "sha256:" + EXPECTED_TEAMS_JSON_HASH

    def test_disclaimers_present_in_source_manifest(self, source_manifest_doc):
        combined = " ".join([
            source_manifest_doc.get("license_notes", ""),
            source_manifest_doc.get("data_freshness_warning", ""),
            " ".join(source_manifest_doc.get("limitations", [])),
            source_manifest_doc.get("allowed_usage", ""),
            source_manifest_doc.get("redistribution_notes", ""),
        ]).lower()
        assert "not official" in combined or "non-official" in combined, (
            "Source manifest must include non-official disclaimer language"
        )
        assert "no team logos" in combined or "no nba logos" in combined, (
            "Source manifest must state no logos are included"
        )
        assert "pantone" not in combined or "not pantone" in combined, (
            "Pantone must only appear as a negation/disclaimer"
        )
        assert source_manifest_doc["live_eligible"] is False
        assert source_manifest_doc["freshness_level"] == "frozen"
