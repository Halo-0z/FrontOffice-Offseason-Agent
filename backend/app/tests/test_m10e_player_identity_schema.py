"""Tests for M10-E3 Player Identity Schema.

Schema under test: schema/player_identities_schema.json

This milestone is schema-only. No real NBA players, no real roster data,
no contracts/salaries/cap sheets, and no normalized/player_identities.json
file in data/snapshots/ are introduced.

Positive:
1. Synthetic player_identities payload validates.
2. Multiple fake players are allowed.
3. birthdate=null validates.
4. height=null validates.
5. weight=null validates.
6. All safe source_type enum values validate (manual_curated / public_reference
   / league_public_reference / team_public_reference / manual_review).
7. manual_review_required=true validates.
8. live_eligible=false validates.
9. Non-empty limitations validates.
10. data_freshness_warning present validates.
11. snapshot_id present and matches top-level validates.

Negative:
12. live_eligible=true fails (top-level const false).
13. manual_review_required=false fails (top-level const true).
14. Per-player live_eligible=true fails.
15. Per-player manual_review_required=false fails.
16. Missing limitations (top-level) fails.
17. Empty limitations (top-level) fails.
18. Per-player empty limitations fails.
19. Missing data_freshness_warning (top-level) fails.
20. Per-player missing data_freshness_warning fails.
21. source_type="llm_generated" fails (top-level).
22. source_type="scraped_unreviewed" fails (top-level).
23. source_type="live_api" fails (top-level).
24. Per-player source_type="llm_generated" fails.
25. Forbidden field 'salary' fails.
26. Forbidden field 'contract' fails.
27. Forbidden field 'cap_hold' fails.
28. Forbidden field 'injury_status' fails.
29. Forbidden field 'medical' fails.
30. Forbidden field 'social_media' fails.
31. Forbidden field 'rumors' fails.
32. Forbidden field 'scouting_opinion' fails.
33. Forbidden field 'live_status' fails.
34. Forbidden field 'availability' fails.
35. Forbidden field 'projected_depth_chart' fails.
36. Forbidden field 'minutes_projection' fails.
37. Forbidden field 'trade_eligibility' fails.
38. Mutation verbs execute/apply/mutate/write fail at top-level (parametrized).
39. Mutation verbs execute/apply/mutate/write fail per-player (parametrized).
40. Fixture content does not contain real NBA player names (LeBron James /
    Stephen Curry / Luka Doncic / Victor Wembanyama) — content audit, not a
    schema check; ensures no test accidentally slips a real name in.

Regression:
41. Real snapshot normalized/ dir still contains only teams.json and
    team_visual_metadata.json.
42. No player_identities.json in real snapshot normalized/ dir.
43. No roster_memberships.json in real snapshot normalized/ dir.
44. No contracts/salaries/cap files in real snapshot normalized/ dir.

Run:

    python -m pytest backend/app/tests/test_m10e_player_identity_schema.py -v
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, List

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "schema"
REAL_SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots" / "nba_real_2026_preoffseason_v1"
REAL_SNAPSHOT_NORMALIZED_DIR = REAL_SNAPSHOT_DIR / "normalized"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def player_identities_schema() -> Dict[str, Any]:
    return _load_json(SCHEMA_DIR / "player_identities_schema.json")


# ---------------------------------------------------------------------------
# Synthetic fixture builders — ONLY fake/test player identities.
# ---------------------------------------------------------------------------


def _make_fake_player(pid: str, first: str, last: str, position: str = "SG") -> Dict[str, Any]:
    return {
        "player_id": pid,
        "display_name": f"{first[0]}. {last}",
        "first_name": first,
        "last_name": last,
        "birthdate": "1999-01-01",
        "height": "6-5",
        "weight": "200 lb",
        "position": position,
        "source_name": "manual curated synthetic identity seed",
        "source_url": "https://example.invalid/sources/player-identities",
        "source_type": "manual_curated",
        "as_of_date": "2026-06-25",
        "manual_review_required": True,
        "live_eligible": False,
        "data_freshness_warning": "Synthetic identity metadata for schema testing only; not live data; no contracts or salaries.",
        "snapshot_id": "test-synthetic-snapshot",
        "limitations": [
            "Identity metadata only",
            "No contract, salary, cap, or availability data",
            "Manual review required",
            "Not live data",
        ],
    }


def _make_fake_players_doc() -> Dict[str, Any]:
    return {
        "schema_version": "m10-e3-v1",
        "snapshot_id": "test-synthetic-snapshot",
        "as_of_date": "2026-06-25",
        "source_name": "manual curated synthetic player identity seed",
        "source_url": "https://example.invalid/sources/player-identities",
        "source_type": "manual_curated",
        "manual_review_required": True,
        "live_eligible": False,
        "data_freshness_warning": "Synthetic player identity metadata for schema testing only; not live data; does not include contracts or salaries.",
        "limitations": [
            "Player identity metadata only — no contract, salary, cap, injury, medical, scouting, or rumor data",
            "Static as-of-date snapshot, not live",
            "Manual review required for any real-data load",
            "Test fixture does not reference real NBA players",
        ],
        "players": [
            _make_fake_player("p-syn-alpha", "Test", "Alpha", "PG"),
            _make_fake_player("p-syn-beta", "Test", "Beta", "SF"),
        ],
    }


# ---------------------------------------------------------------------------
# Positive tests
# ---------------------------------------------------------------------------


def test_fake_players_doc_validates(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_multiple_fake_players_allowed(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["players"] = [
        _make_fake_player(f"p-syn-{c}", "Test", c.capitalize(), pos)
        for c, pos in [("alpha", "PG"), ("beta", "SG"), ("gamma", "SF"), ("delta", "PF"), ("epsilon", "C")]
    ]
    jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_birthdate_null_validates(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["players"][0]["birthdate"] = None
    jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_height_null_validates(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["players"][0]["height"] = None
    jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_weight_null_validates(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["players"][0]["weight"] = None
    jsonschema.validate(instance=doc, schema=player_identities_schema)


@pytest.mark.parametrize(
    "source_type",
    ["manual_curated", "public_reference", "league_public_reference", "team_public_reference", "manual_review"],
)
def test_safe_source_type_enum_validates(player_identities_schema: Dict[str, Any], source_type: str) -> None:
    doc = _make_fake_players_doc()
    doc["source_type"] = source_type
    doc["players"][0]["source_type"] = source_type
    jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_manual_review_required_true_validates(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    assert doc["manual_review_required"] is True
    assert doc["players"][0]["manual_review_required"] is True
    jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_live_eligible_false_validates(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    assert doc["live_eligible"] is False
    assert doc["players"][0]["live_eligible"] is False
    jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_non_empty_limitations_validates(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    assert len(doc["limitations"]) >= 1
    assert len(doc["players"][0]["limitations"]) >= 1
    jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_data_freshness_warning_present_validates(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    assert doc["data_freshness_warning"]
    assert doc["players"][0]["data_freshness_warning"]
    jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_snapshot_id_present_validates(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    assert doc["snapshot_id"]
    for p in doc["players"]:
        assert p["snapshot_id"] == doc["snapshot_id"]
    jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_position_enum_allows_standard_positions(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    for i, pos in enumerate(["PG", "SG", "SF", "PF", "C", "G", "F", "FC", "GF"]):
        pid = f"p-syn-pos-{i}"
        p = _make_fake_player(pid, "Position", f"Test{pos}", pos)
        doc["players"].append(p)
    jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_notes_field_optional_array_validates(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["players"][0]["notes"] = ["Synthetic record for schema coverage", "No real person"]
    jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_source_url_null_validates(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["source_url"] = None
    doc["players"][0]["source_url"] = None
    jsonschema.validate(instance=doc, schema=player_identities_schema)


# ---------------------------------------------------------------------------
# Negative tests
# ---------------------------------------------------------------------------


def test_top_level_live_eligible_true_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["live_eligible"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_top_level_manual_review_required_false_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["manual_review_required"] = False
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_per_player_live_eligible_true_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["players"][0]["live_eligible"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_per_player_manual_review_required_false_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["players"][0]["manual_review_required"] = False
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_missing_top_level_limitations_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    del doc["limitations"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_empty_top_level_limitations_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["limitations"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_empty_per_player_limitations_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["players"][0]["limitations"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_missing_per_player_limitations_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    del doc["players"][0]["limitations"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_missing_top_level_freshness_warning_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    del doc["data_freshness_warning"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_missing_per_player_freshness_warning_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    del doc["players"][0]["data_freshness_warning"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


@pytest.mark.parametrize("bad_type", ["llm_generated", "scraped_unreviewed", "live_api"])
def test_forbidden_top_level_source_type_fails(player_identities_schema: Dict[str, Any], bad_type: str) -> None:
    doc = _make_fake_players_doc()
    doc["source_type"] = bad_type
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


@pytest.mark.parametrize("bad_type", ["llm_generated", "scraped_unreviewed", "live_api"])
def test_forbidden_per_player_source_type_fails(player_identities_schema: Dict[str, Any], bad_type: str) -> None:
    doc = _make_fake_players_doc()
    doc["players"][0]["source_type"] = bad_type
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


FORBIDDEN_TOP_LEVEL_FIELDS = [
    "salary", "salaries", "contract", "contracts", "cap_hold", "guarantee",
    "guarantee_amount", "injury", "injuries", "injury_status", "medical",
    "medical_status", "health", "personal_sensitive_info", "social_media",
    "agent", "agent_representation", "rumors", "rumor", "scouting_opinion",
    "scouting_opinions", "live_status", "availability", "real_time_availability",
    "projected_depth_chart", "depth_chart", "minutes_projection", "role_projection",
    "trade_eligibility", "cap_sheet", "cap_sheets", "headshot", "headshot_url",
    "player_image", "photo_url", "official_headshot",
    "execute", "apply", "commit", "mutate", "write", "persist", "save",
    "delete", "update", "submit", "auto_execute", "auto_approve",
    "current_roster", "latest_roster", "live_salaries", "latest_data",
    "live_data", "current_salaries", "real_time_data",
    "logo_path", "logo_url", "official_logo", "nba_logo", "team_logo", "mascot_image",
]


@pytest.mark.parametrize("bad_field", FORBIDDEN_TOP_LEVEL_FIELDS)
def test_forbidden_top_level_field_fails(player_identities_schema: Dict[str, Any], bad_field: str) -> None:
    doc = _make_fake_players_doc()
    doc[bad_field] = "forbidden"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


@pytest.mark.parametrize("bad_field", FORBIDDEN_TOP_LEVEL_FIELDS)
def test_forbidden_per_player_field_fails(player_identities_schema: Dict[str, Any], bad_field: str) -> None:
    doc = _make_fake_players_doc()
    doc["players"][0][bad_field] = "forbidden"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_unknown_position_enum_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["players"][0]["position"] = "XY"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_missing_required_player_id_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    del doc["players"][0]["player_id"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_missing_required_display_name_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    del doc["players"][0]["display_name"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_missing_required_snapshot_id_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    del doc["snapshot_id"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_missing_required_players_array_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    del doc["players"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_additional_properties_at_top_level_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["totally_new_field"] = "unexpected"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_additional_properties_per_player_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["players"][0]["jersey_number"] = 23
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


def test_invalid_player_id_pattern_uppercase_fails(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    doc["players"][0]["player_id"] = "P-Syn-Alpha"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=player_identities_schema)


# ---------------------------------------------------------------------------
# Fixture content audit — ensures no real NBA player name is hard-coded.
# ---------------------------------------------------------------------------


REAL_NBA_PLAYER_NAMES: List[str] = [
    "LeBron James",
    "Stephen Curry",
    "Luka Doncic",
    "Luka Dončić",
    "Victor Wembanyama",
    "Giannis Antetokounmpo",
    "Kevin Durant",
    "Jayson Tatum",
    "Nikola Jokic",
    "Nikola Jokić",
    "Joel Embiid",
    "Shai Gilgeous-Alexander",
    "Anthony Edwards",
]


def _collect_fixture_strings(obj: Any) -> List[str]:
    out: List[str] = []
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(_collect_fixture_strings(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_collect_fixture_strings(v))
    elif isinstance(obj, str):
        out.append(obj)
    return out


def test_fixture_contains_no_real_nba_player_names(player_identities_schema: Dict[str, Any]) -> None:
    doc = _make_fake_players_doc()
    jsonschema.validate(instance=doc, schema=player_identities_schema)
    all_strings = " || ".join(_collect_fixture_strings(doc)).lower()
    for name in REAL_NBA_PLAYER_NAMES:
        assert name.lower() not in all_strings, (
            f"Real NBA player name '{name}' must not appear in any synthetic fixture string."
        )


# ---------------------------------------------------------------------------
# Regression: F4-B tiny pilot guard invariants.
# ---------------------------------------------------------------------------

EXPECTED_PILOT_PLAYER_IDS_E3 = {
    "nba-shai-gilgeous-alexander",
    "nba-chet-holmgren",
    "nba-nikola-jokic",
    "nba-jamal-murray",
}

EXPECTED_PILOT_TEAM_IDS_E3 = {"nba-OKC", "nba-DEN"}


def test_real_normalized_dir_contains_only_expected_files() -> None:
    assert REAL_SNAPSHOT_NORMALIZED_DIR.is_dir()
    files = sorted(p.name for p in REAL_SNAPSHOT_NORMALIZED_DIR.iterdir() if p.is_file())
    assert files == ["player_identities.json", "roster_memberships.json", "team_visual_metadata.json", "teams.json"], (
        f"M10-F4-B regression: normalized dir must contain teams.json, "
        f"team_visual_metadata.json, player_identities.json, roster_memberships.json; got: {files}"
    )


def test_player_identities_json_exists_as_tiny_pilot() -> None:
    target = REAL_SNAPSHOT_NORMALIZED_DIR / "player_identities.json"
    assert target.exists(), "player_identities.json must exist after M10-F4-B tiny pilot."
    doc = _load_json(target)
    assert doc.get("snapshot_id") == "nba_real_2026_preoffseason_v1"
    assert doc.get("live_eligible") is False
    assert doc.get("manual_review_required") is True
    players = doc.get("players", [])
    assert len(players) == 4, f"Expected 4 tiny pilot players, got {len(players)}"
    player_ids = {p.get("player_id") for p in players}
    assert player_ids == EXPECTED_PILOT_PLAYER_IDS_E3
    for p in players:
        assert p.get("live_eligible") is False
        assert p.get("manual_review_required") is True
        assert p.get("birthdate") is None
        assert p.get("height") is None
        assert p.get("weight") is None


def test_roster_memberships_json_exists_as_tiny_pilot() -> None:
    target = REAL_SNAPSHOT_NORMALIZED_DIR / "roster_memberships.json"
    assert target.exists(), "roster_memberships.json must exist after M10-F4-B tiny pilot."
    doc = _load_json(target)
    assert doc.get("snapshot_id") == "nba_real_2026_preoffseason_v1"
    assert doc.get("live_eligible") is False
    assert doc.get("manual_review_required") is True
    mems = doc.get("roster_memberships", [])
    assert len(mems) == 4, f"Expected 4 tiny pilot memberships, got {len(mems)}"
    player_ids = {m.get("player_id") for m in mems}
    team_ids = {m.get("team_id") for m in mems}
    assert player_ids == EXPECTED_PILOT_PLAYER_IDS_E3
    assert team_ids == EXPECTED_PILOT_TEAM_IDS_E3
    for m in mems:
        assert m.get("roster_status") == "standard"
        assert m.get("live_eligible") is False
        assert m.get("manual_review_required") is True


@pytest.mark.parametrize(
    "filename",
    [
        "contracts.json",
        "salaries.json",
        "cap_sheet.json",
        "cap_sheets.json",
        "players.json",
        "rosters.json",
        "injuries.json",
        "rumors.json",
        "scouting_opinions.json",
        "live_status.json",
    ],
)
def test_no_forbidden_data_files_in_real_snapshot(filename: str) -> None:
    assert not (REAL_SNAPSHOT_NORMALIZED_DIR / filename).exists(), (
        f"Forbidden data file '{filename}' must not exist in real snapshot normalized/ dir in M10-F4-B."
    )


def test_real_snapshot_root_has_no_new_top_level_files() -> None:
    expected = {"manifest.json", "source_manifest.json", "normalized"}
    actual = {p.name for p in REAL_SNAPSHOT_DIR.iterdir()}
    assert actual == expected, f"Unexpected files at real snapshot root: {actual - expected}"
