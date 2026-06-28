"""Tests for M10-E4 Roster Membership Schema.

Schema under test: schema/roster_memberships_schema.json

This milestone is schema-only. No real NBA rosters, no real NBA player-to-team
mappings, no contracts/salaries/cap sheets, and no normalized/roster_memberships.json
file in data/snapshots/ are introduced.

Positive:
1. Synthetic roster_memberships payload validates.
2. Multiple fake memberships are allowed.
3. team_id pattern nba-ATL / nba-GSW validates.
4. player_id pattern player-test-alpha / p-syn-alpha validates.
5. All six safe roster_status enum values validate (standard / two_way /
   training_camp / unsigned_draft_rights / free_agent / unknown_manual_review).
6. All safe source_type enum values validate (manual_curated / public_reference
   / league_public_reference / team_public_reference / manual_review).
7. manual_review_required=true validates.
8. live_eligible=false validates.
9. Non-empty limitations validates.
10. data_freshness_warning present validates.
11. snapshot_id present and matches top-level validates.
12. source_url can be null.
13. notes is optional and accepts string arrays.
14. membership_id is optional and accepts safe lowercase ids.

Negative:
15. live_eligible=true fails (top-level const false).
16. manual_review_required=false fails (top-level const true).
17. Per-membership live_eligible=true fails.
18. Per-membership manual_review_required=false fails.
19. Missing top-level limitations fails.
20. Empty top-level limitations fails.
21. Per-membership empty limitations fails.
22. Missing per-membership limitations fails.
23. Missing top-level data_freshness_warning fails.
24. Missing per-membership data_freshness_warning fails.
25. source_type="llm_generated" fails (top-level).
26. source_type="scraped_unreviewed" fails (top-level).
27. source_type="live_api" fails (top-level).
28. Per-membership source_type="llm_generated" fails.
29. roster_status="inactive" fails (forbidden live/transaction semantics).
30. roster_status="waived" fails.
31. roster_status="traded" fails.
32. roster_status="injured" fails.
33. roster_status="suspended" fails.
34. roster_status="questionable" fails.
35. roster_status="probable" fails.
36. roster_status="day_to_day" fails.
37. roster_status="available" fails.
38. roster_status="unavailable" fails.
39. roster_status="active_now" fails.
40. roster_status="latest" fails.
41. roster_status="current" fails.
42. Forbidden field 'salary' fails.
43. Forbidden field 'contract' fails.
44. Forbidden field 'cap_hold' fails.
45. Forbidden field 'guarantee_amount' fails.
46. Forbidden field 'injury_status' fails.
47. Forbidden field 'medical' fails.
48. Forbidden field 'trade_eligibility' fails.
49. Forbidden field 'trade_restriction' fails.
50. Forbidden field 'no_trade_clause' fails.
51. Forbidden field 'availability' fails.
52. Forbidden field 'projected_depth_chart' fails.
53. Forbidden field 'minutes_projection' fails.
54. Forbidden field 'role_projection' fails.
55. Forbidden field 'starter' fails.
56. Forbidden field 'bench_role' fails.
57. Forbidden field 'rotation_role' fails.
58. Forbidden field 'rumors' fails.
59. Forbidden field 'scouting_opinion' fails.
60. Forbidden field 'live_status' fails.
61. Forbidden field 'current_status' fails.
62. Forbidden field 'latest_status' fails.
63. Mutation verbs execute/apply/mutate/write fail at top-level and per-membership
    (parametrized).
64. Fixture content does not contain real NBA player names (LeBron James /
    Stephen Curry / Luka Doncic / Victor Wembanyama etc.) — content audit.

Regression:
65. Real snapshot normalized/ dir still contains only teams.json and
    team_visual_metadata.json.
66. No player_identities.json in real snapshot normalized/ dir.
67. No roster_memberships.json in real snapshot normalized/ dir.
68. No contracts/salaries/cap files in real snapshot normalized/ dir.

Run:

    python -m pytest backend/app/tests/test_m10e_roster_membership_schema.py -v
"""

from __future__ import annotations

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
def roster_memberships_schema() -> Dict[str, Any]:
    return _load_json(SCHEMA_DIR / "roster_memberships_schema.json")


# ---------------------------------------------------------------------------
# Synthetic fixture builders — ONLY fake/test player memberships.
# ---------------------------------------------------------------------------


def _make_fake_membership(
    mid: str,
    pid: str,
    tid: str,
    status: str,
) -> Dict[str, Any]:
    return {
        "membership_id": mid,
        "team_id": tid,
        "player_id": pid,
        "roster_status": status,
        "source_name": "manual curated synthetic roster membership seed",
        "source_url": "https://example.invalid/sources/roster-memberships",
        "source_type": "manual_curated",
        "as_of_date": "2026-06-25",
        "manual_review_required": True,
        "live_eligible": False,
        "data_freshness_warning": "Synthetic membership metadata for schema testing only; not live data; does not reflect subsequent trades or signings.",
        "snapshot_id": "test-synthetic-snapshot",
        "limitations": [
            "Membership metadata only",
            "No contract, salary, cap, injury, or availability data",
            "Static as-of-date snapshot, not live",
            "Manual review required for any real-data load",
        ],
    }


def _make_fake_roster_doc() -> Dict[str, Any]:
    return {
        "schema_version": "m10-e4-v1",
        "snapshot_id": "test-synthetic-snapshot",
        "as_of_date": "2026-06-25",
        "source_name": "manual curated synthetic roster membership seed",
        "source_url": "https://example.invalid/sources/roster-memberships",
        "source_type": "manual_curated",
        "manual_review_required": True,
        "live_eligible": False,
        "data_freshness_warning": "Synthetic roster membership metadata for schema testing only; not live data; does not include contracts, salaries, or availability; does not reflect subsequent trades or signings.",
        "limitations": [
            "Roster membership metadata only — no contract, salary, cap, injury, medical, scouting, rumor, or availability data",
            "Status values limited to safe low-risk M10-E enum; inactive/waived/traded/injured/available are deferred to M10-F+",
            "Static as-of-date snapshot, not live or current",
            "Manual review required for any real-data load",
            "Test fixture does not reference real NBA players or real rosters",
        ],
        "roster_memberships": [
            _make_fake_membership("rm-syn-alpha", "player-test-alpha", "nba-ATL", "standard"),
            _make_fake_membership("rm-syn-beta", "player-test-beta", "nba-BOS", "two_way"),
        ],
    }


# ---------------------------------------------------------------------------
# Positive tests
# ---------------------------------------------------------------------------


def test_fake_roster_doc_validates(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_multiple_fake_memberships_allowed(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"] = [
        _make_fake_membership(f"rm-syn-{i}", f"player-test-{c}", f"nba-{abbr}", status)
        for i, (c, abbr, status) in enumerate(
            [
                ("alpha", "ATL", "standard"),
                ("beta", "BOS", "two_way"),
                ("gamma", "GSW", "training_camp"),
                ("delta", "LAL", "unsigned_draft_rights"),
                ("epsilon", "MIA", "free_agent"),
                ("zeta", "MIL", "unknown_manual_review"),
            ]
        )
    ]
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


@pytest.mark.parametrize("tid", ["nba-ATL", "nba-GSW", "nba-LAL", "nba-BOS", "nba-MIA"])
def test_team_id_nba_xxx_pattern_validates(roster_memberships_schema: Dict[str, Any], tid: str) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["team_id"] = tid
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


@pytest.mark.parametrize("pid", ["player-test-alpha", "p-syn-alpha", "player-test-beta", "p-syn-42"])
def test_player_id_pattern_validates(roster_memberships_schema: Dict[str, Any], pid: str) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["player_id"] = pid
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


@pytest.mark.parametrize(
    "status",
    ["standard", "two_way", "training_camp", "unsigned_draft_rights", "free_agent", "unknown_manual_review"],
)
def test_safe_roster_status_enum_validates(roster_memberships_schema: Dict[str, Any], status: str) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["roster_status"] = status
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


@pytest.mark.parametrize(
    "source_type",
    ["manual_curated", "public_reference", "league_public_reference", "team_public_reference", "manual_review"],
)
def test_safe_source_type_enum_validates(roster_memberships_schema: Dict[str, Any], source_type: str) -> None:
    doc = _make_fake_roster_doc()
    doc["source_type"] = source_type
    doc["roster_memberships"][0]["source_type"] = source_type
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_manual_review_required_true_validates(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    assert doc["manual_review_required"] is True
    assert doc["roster_memberships"][0]["manual_review_required"] is True
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_live_eligible_false_validates(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    assert doc["live_eligible"] is False
    assert doc["roster_memberships"][0]["live_eligible"] is False
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_non_empty_limitations_validates(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    assert len(doc["limitations"]) >= 1
    assert len(doc["roster_memberships"][0]["limitations"]) >= 1
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_data_freshness_warning_present_validates(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    assert doc["data_freshness_warning"]
    assert doc["roster_memberships"][0]["data_freshness_warning"]
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_snapshot_id_present_validates(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    assert doc["snapshot_id"]
    for m in doc["roster_memberships"]:
        assert m["snapshot_id"] == doc["snapshot_id"]
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_source_url_null_validates(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["source_url"] = None
    doc["roster_memberships"][0]["source_url"] = None
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_notes_field_optional_array_validates(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["notes"] = ["Synthetic membership for schema coverage", "No real player"]
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_membership_id_optional_validates(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    del doc["roster_memberships"][0]["membership_id"]
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_membership_id_safe_id_validates(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["membership_id"] = "rm-syn-valid-1"
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_invalid_team_id_pattern_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["team_id"] = "ATL"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_invalid_team_id_lowercase_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["team_id"] = "nba-atl"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


# ---------------------------------------------------------------------------
# Negative tests
# ---------------------------------------------------------------------------


def test_top_level_live_eligible_true_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["live_eligible"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_top_level_manual_review_required_false_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["manual_review_required"] = False
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_per_membership_live_eligible_true_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["live_eligible"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_per_membership_manual_review_required_false_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["manual_review_required"] = False
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_missing_top_level_limitations_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    del doc["limitations"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_empty_top_level_limitations_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["limitations"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_empty_per_membership_limitations_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["limitations"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_missing_per_membership_limitations_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    del doc["roster_memberships"][0]["limitations"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_missing_top_level_freshness_warning_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    del doc["data_freshness_warning"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_missing_per_membership_freshness_warning_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    del doc["roster_memberships"][0]["data_freshness_warning"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


@pytest.mark.parametrize("bad_type", ["llm_generated", "scraped_unreviewed", "live_api"])
def test_forbidden_top_level_source_type_fails(roster_memberships_schema: Dict[str, Any], bad_type: str) -> None:
    doc = _make_fake_roster_doc()
    doc["source_type"] = bad_type
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


@pytest.mark.parametrize("bad_type", ["llm_generated", "scraped_unreviewed", "live_api"])
def test_forbidden_per_membership_source_type_fails(roster_memberships_schema: Dict[str, Any], bad_type: str) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["source_type"] = bad_type
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


FORBIDDEN_ROSTER_STATUSES = [
    "inactive", "waived", "traded", "injured", "suspended",
    "questionable", "probable", "day_to_day",
    "available", "unavailable", "active_now", "latest", "current",
]


@pytest.mark.parametrize("bad_status", FORBIDDEN_ROSTER_STATUSES)
def test_forbidden_roster_status_fails(roster_memberships_schema: Dict[str, Any], bad_status: str) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["roster_status"] = bad_status
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


FORBIDDEN_TOP_LEVEL_FIELDS = [
    "salary", "salaries", "contract", "contracts", "cap_hold", "guarantee",
    "guarantee_amount", "cap_sheet", "cap_sheets",
    "injury", "injuries", "injury_status", "medical", "medical_status", "health",
    "trade_eligibility", "trade_restriction", "no_trade_clause",
    "availability", "real_time_availability", "live_status", "current_status",
    "latest_status", "active_now",
    "projected_depth_chart", "depth_chart", "minutes_projection", "role_projection",
    "starter", "bench_role", "rotation_role",
    "scouting_opinion", "scouting_opinions", "rumors", "rumor",
    "agent", "agent_representation", "social_media", "personal_sensitive_info",
    "headshot", "headshot_url", "player_image", "photo_url", "official_headshot",
    "execute", "apply", "commit", "mutate", "write", "persist", "save",
    "delete", "update", "submit", "auto_execute", "auto_approve",
    "inactive", "waived", "traded", "suspended", "questionable", "probable",
    "day_to_day", "available", "unavailable", "current_roster", "latest_roster",
    "live_salaries", "latest_data", "live_data", "current_salaries", "real_time_data",
    "current", "latest",
    "logo_path", "logo_url", "official_logo", "nba_logo", "team_logo", "mascot_image",
]


@pytest.mark.parametrize("bad_field", FORBIDDEN_TOP_LEVEL_FIELDS)
def test_forbidden_top_level_field_fails(roster_memberships_schema: Dict[str, Any], bad_field: str) -> None:
    doc = _make_fake_roster_doc()
    doc[bad_field] = "forbidden"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


@pytest.mark.parametrize("bad_field", FORBIDDEN_TOP_LEVEL_FIELDS)
def test_forbidden_per_membership_field_fails(roster_memberships_schema: Dict[str, Any], bad_field: str) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0][bad_field] = "forbidden"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_missing_required_team_id_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    del doc["roster_memberships"][0]["team_id"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_missing_required_player_id_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    del doc["roster_memberships"][0]["player_id"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_missing_required_roster_status_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    del doc["roster_memberships"][0]["roster_status"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_missing_required_snapshot_id_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    del doc["snapshot_id"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_missing_required_roster_array_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    del doc["roster_memberships"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_additional_properties_at_top_level_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["totally_new_field"] = "unexpected"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_additional_properties_per_membership_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["jersey_number"] = 23
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


def test_invalid_membership_id_pattern_uppercase_fails(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    doc["roster_memberships"][0]["membership_id"] = "RM-Syn-Alpha"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=doc, schema=roster_memberships_schema)


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


def test_fixture_contains_no_real_nba_player_names(roster_memberships_schema: Dict[str, Any]) -> None:
    doc = _make_fake_roster_doc()
    jsonschema.validate(instance=doc, schema=roster_memberships_schema)
    all_strings = " || ".join(_collect_fixture_strings(doc)).lower()
    for name in REAL_NBA_PLAYER_NAMES:
        assert name.lower() not in all_strings, (
            f"Real NBA player name '{name}' must not appear in any synthetic fixture string."
        )


# ---------------------------------------------------------------------------
# Regression: F4-B tiny pilot guard invariants.
# ---------------------------------------------------------------------------

EXPECTED_PILOT_PLAYER_IDS_E4 = {
    "nba-shai-gilgeous-alexander",
    "nba-chet-holmgren",
    "nba-nikola-jokic",
    "nba-jamal-murray",
}

EXPECTED_PILOT_TEAM_IDS_E4 = {"nba-OKC", "nba-DEN"}


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
    assert player_ids == EXPECTED_PILOT_PLAYER_IDS_E4
    for p in players:
        assert p.get("live_eligible") is False
        assert p.get("manual_review_required") is True


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
    assert player_ids == EXPECTED_PILOT_PLAYER_IDS_E4
    assert team_ids == EXPECTED_PILOT_TEAM_IDS_E4
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
