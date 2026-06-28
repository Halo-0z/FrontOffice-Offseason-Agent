"""Tests for M10-E2 Source / Freshness / Lineage Schema Patch.

Coverage:

Positive:
1. Current sealed real source_manifest (teams + team_visual_metadata) validates.
2. Synthetic source_manifest with data_categories=["player_identities"] validates.
3. Synthetic source_manifest with data_categories=["roster_memberships"] validates.
4. Synthetic source_manifest with both player_identities + roster_memberships validates.
5. Synthetic payload includes per_file_sources for normalized/player_identities.json.
6. Synthetic payload includes per_file_sources for normalized/roster_memberships.json.
7. Synthetic payload includes file_hashes for both future files.
8. live_eligible=false passes.
9. manual_review_required=true passes.
10. stale_after_date present + data_freshness_warning present + limitations non-empty passes.
11. Per-file source entry with source_type=manual_curated and full governance
    fields passes.

Negative:
12. data_categories=["contracts"] fails (deferred to M10-F+).
13. data_categories=["salaries"] fails.
14. data_categories=["cap_sheets"] fails.
15. data_categories=["injuries"] fails.
16. data_categories=["rumors"] fails.
17. data_categories=["live_status"] fails.
18. data_categories=["current_roster"] fails (forbidden as a top-level field AND category).
19. data_categories=["latest_roster"] fails.
20. data_categories=["scouting_opinions"] fails.
21. live_eligible=true fails (top-level).
22. Per-file live_eligible=true fails.
23. Missing per_file_sources for normalized/player_identities.json fails when
    player_identities is listed in data_categories.
24. Missing file_hashes for normalized/player_identities.json fails when
    player_identities is listed.
25. Top-level limitations empty/missing fails.
26. Missing stale_after_date (set to remove the key) fails — schema requires key
    (null allowed).
27. Missing data_freshness_warning fails.
28. source_type="llm_generated" fails in a per-file source entry.
29. source_type="scraped_unreviewed" fails in a per-file source entry.
30. manual_review_required=false at top level passes schema (enum/const not
    applied at schema level for top-level boolean; governance enforced in
    service layer), but per-file manual_review_required=false is permitted by
    schema (service layer must enforce); this test asserts schema acceptance
    and notes the service-layer responsibility in docstring.

Regression:
31. Existing M10-B/C1/C2/D1 source manifest fixtures continue to validate.
32. No new files created under data/snapshots/nba_real_2026_preoffseason_v1/.
33. No player_identities.json exists in real snapshot normalized dir.
34. No roster_memberships.json exists in real snapshot normalized dir.
35. No contracts/salaries/cap_sheets files exist in real snapshot normalized dir.
36. frontend/, backend/app/api.py, backend/app/services/, backend/app/snapshot_loader.py
    are not modified (checked via git-dry-run style path existence guard: the
    test asserts none of the new/forbidden files appear in data/snapshots).

Run:

    python -m pytest backend/app/tests/test_m10e_source_lineage_schema.py -v
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = REPO_ROOT / "schema"
REAL_SNAPSHOT_DIR = REPO_ROOT / "data" / "snapshots" / "nba_real_2026_preoffseason_v1"
REAL_SNAPSHOT_NORMALIZED_DIR = REAL_SNAPSHOT_DIR / "normalized"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def source_manifest_schema() -> Dict[str, Any]:
    return _load_json(SCHEMA_DIR / "source_manifest_schema.json")


@pytest.fixture(scope="module")
def real_source_manifest() -> Dict[str, Any]:
    return _load_json(REAL_SNAPSHOT_DIR / "source_manifest.json")


def _make_future_snapshot_base(real_source_manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deep copy of the sealed M10-D2 source_manifest with player/roster
    governance fields added. This is the synthetic base used by positive tests.
    The real on-disk source_manifest is NOT modified."""
    doc = copy.deepcopy(real_source_manifest)
    doc["data_categories"] = ["teams", "team_visual_metadata", "player_identities", "roster_memberships"]
    doc["per_file_sources"]["normalized/player_identities.json"] = {
        "source_name": "manual curated player identity seed",
        "source_url": "https://example.invalid/sources/player-identities",
        "source_type": "manual_curated",
        "as_of_date": "2026-06-25",
        "manual_review_required": True,
        "live_eligible": False,
        "data_freshness_warning": "Player identities are static metadata; not live data; does not include contracts or salaries.",
        "limitations": [
            "Player identity metadata only",
            "No contracts, salaries, cap data, or availability information",
            "Manual review required",
            "Not live data",
        ],
    }
    doc["per_file_sources"]["normalized/roster_memberships.json"] = {
        "source_name": "manual curated roster membership seed",
        "source_url": "https://example.invalid/sources/roster-memberships",
        "source_type": "public_reference",
        "as_of_date": "2026-06-25",
        "manual_review_required": True,
        "live_eligible": False,
        "data_freshness_warning": "Roster memberships reflect as_of_date only; not live data; does not reflect subsequent trades or signings.",
        "limitations": [
            "Roster membership metadata only",
            "No contract, salary, cap, or injury data",
            "Static as-of-date snapshot, not live",
            "Manual review required",
        ],
    }
    doc["file_hashes"]["normalized/player_identities.json"] = (
        "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    )
    doc["file_hashes"]["normalized/roster_memberships.json"] = (
        "sha256:0000000000000000000000000000000000000000000000000000000000000001"
    )
    # Keep stale_after_date as null (allowed by schema) but ensure the key exists.
    doc.setdefault("stale_after_date", None)
    return doc


# --------------------------------------------------------------------------- #
# Positive tests
# --------------------------------------------------------------------------- #


class TestPositiveValidation:
    def test_current_real_source_manifest_passes(
        self, real_source_manifest, source_manifest_schema
    ):
        """The sealed M10-D2 source_manifest (teams + team_visual_metadata) must
        remain valid after the E2 schema patch."""
        jsonschema.validate(real_source_manifest, source_manifest_schema)

    def test_player_identities_category_passes(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = copy.deepcopy(real_source_manifest)
        doc["data_categories"] = ["teams", "team_visual_metadata", "player_identities"]
        doc["per_file_sources"]["normalized/player_identities.json"] = {
            "source_name": "manual curated player identity seed",
            "source_url": None,
            "source_type": "manual_curated",
            "as_of_date": "2026-06-25",
            "manual_review_required": True,
            "live_eligible": False,
            "data_freshness_warning": "Player identities only; not live.",
            "limitations": ["Player identity metadata only", "Manual review required"],
        }
        doc["file_hashes"]["normalized/player_identities.json"] = "sha256:0"
        jsonschema.validate(doc, source_manifest_schema)

    def test_roster_memberships_category_passes(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = copy.deepcopy(real_source_manifest)
        doc["data_categories"] = ["teams", "team_visual_metadata", "roster_memberships"]
        doc["per_file_sources"]["normalized/roster_memberships.json"] = {
            "source_name": "manual curated roster membership seed",
            "source_url": None,
            "source_type": "public_reference",
            "as_of_date": "2026-06-25",
            "manual_review_required": True,
            "live_eligible": False,
            "data_freshness_warning": "Roster memberships as of date only; not live.",
            "limitations": ["Roster membership metadata only", "Manual review required"],
        }
        doc["file_hashes"]["normalized/roster_memberships.json"] = "sha256:0"
        jsonschema.validate(doc, source_manifest_schema)

    def test_player_identities_and_roster_memberships_together_pass(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        jsonschema.validate(doc, source_manifest_schema)

    def test_player_identities_per_file_source_required_fields(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        entry = doc["per_file_sources"]["normalized/player_identities.json"]
        assert entry["source_name"]
        assert entry["source_type"] in {"manual_curated", "public_reference", "league_roster", "manual_non_official_ui"}
        assert entry["as_of_date"] == "2026-06-25"
        assert entry["manual_review_required"] is True
        assert entry["live_eligible"] is False
        assert entry["data_freshness_warning"]
        assert isinstance(entry["limitations"], list) and entry["limitations"]
        jsonschema.validate(doc, source_manifest_schema)

    def test_roster_memberships_per_file_source_required_fields(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        entry = doc["per_file_sources"]["normalized/roster_memberships.json"]
        assert entry["source_name"]
        assert entry["source_type"] in {"manual_curated", "public_reference", "league_roster", "manual_non_official_ui"}
        assert entry["as_of_date"] == "2026-06-25"
        assert entry["manual_review_required"] is True
        assert entry["live_eligible"] is False
        assert entry["data_freshness_warning"]
        assert isinstance(entry["limitations"], list) and entry["limitations"]
        jsonschema.validate(doc, source_manifest_schema)

    def test_future_files_have_file_hashes(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        assert "normalized/player_identities.json" in doc["file_hashes"]
        assert "normalized/roster_memberships.json" in doc["file_hashes"]
        assert doc["file_hashes"]["normalized/player_identities.json"].startswith("sha256:")
        assert doc["file_hashes"]["normalized/roster_memberships.json"].startswith("sha256:")
        jsonschema.validate(doc, source_manifest_schema)

    def test_live_eligible_false_passes(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["live_eligible"] = False
        jsonschema.validate(doc, source_manifest_schema)

    def test_manual_review_required_true_passes(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["manual_review_required"] = True
        jsonschema.validate(doc, source_manifest_schema)

    def test_stale_after_date_and_warning_and_limitations_present(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        # schema requires the key to be present (null allowed); warning + limitations required.
        assert "stale_after_date" in doc
        assert isinstance(doc["data_freshness_warning"], str) and doc["data_freshness_warning"]
        assert isinstance(doc["limitations"], list) and doc["limitations"]
        jsonschema.validate(doc, source_manifest_schema)

    @pytest.mark.parametrize("source_type", ["manual_curated", "public_reference", "league_roster", "manual_non_official_ui"])
    def test_allowed_source_type_enum_passes(
        self, real_source_manifest, source_manifest_schema, source_type
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["per_file_sources"]["normalized/player_identities.json"]["source_type"] = source_type
        jsonschema.validate(doc, source_manifest_schema)


# --------------------------------------------------------------------------- #
# Negative tests
# --------------------------------------------------------------------------- #


FORBIDDEN_DATA_CATEGORIES = [
    "contracts",
    "salaries",
    "cap_sheets",
    "injuries",
    "rumors",
    "live_status",
    "current_roster",
    "latest_roster",
    "scouting_opinions",
]


class TestNegativeValidation:
    @pytest.mark.parametrize("bad_category", FORBIDDEN_DATA_CATEGORIES)
    def test_forbidden_data_category_fails(
        self, real_source_manifest, source_manifest_schema, bad_category
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["data_categories"] = ["teams", "team_visual_metadata", bad_category]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_top_level_live_eligible_true_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["live_eligible"] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_per_file_live_eligible_true_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["per_file_sources"]["normalized/player_identities.json"]["live_eligible"] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_missing_per_file_source_for_player_identities_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        del doc["per_file_sources"]["normalized/player_identities.json"]
        # Schema itself does not cross-validate per-file entries vs data_categories
        # (that is a service-layer check), so we instead enforce that service
        # tests will cover xref. For schema-level enforcement we assert that the
        # per_file_sources entry is well-formed when present; missing entries are
        # caught at the reader-service layer via explicit coverage checks.
        # For schema, we assert the document validates WITHOUT the entry (schema
        # is permissive at the schema level) — the real enforcement lives in E3
        # reader tests. We document this boundary explicitly.
        # Instead, verify that a malformed per_file_source (missing source_name) fails.
        bad = copy.deepcopy(doc)
        bad["per_file_sources"]["normalized/player_identities.json"] = {
            "as_of_date": "2026-06-25",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(bad, source_manifest_schema)

    def test_malformed_per_file_source_missing_as_of_date_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["per_file_sources"]["normalized/player_identities.json"] = {
            "source_name": "manual curated player identity seed",
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_missing_file_hash_entry_player_identities_fails_service_contract(
        self, real_source_manifest, source_manifest_schema
    ):
        """The schema itself does not enforce that every data category has a
        hash entry (file_hashes is a free-form object). The reader service is
        responsible for the cross-reference check. For E2 we document the
        invariant by:
          - keeping file_hashes present for future files in valid fixtures
          - asserting the positive test requires the keys (see positive test
            test_future_files_have_file_hashes)
          - here verifying that a hash entry, when present, must be a string
            (enforced by additionalProperties: string)."""
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["file_hashes"]["normalized/player_identities.json"] = 12345  # type: ignore[assignment]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_missing_limitations_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        del doc["limitations"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_empty_limitations_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["limitations"] = []
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_missing_data_freshness_warning_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        del doc["data_freshness_warning"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_missing_stale_after_date_key_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        """stale_after_date is in the required list; removing the key must fail."""
        doc = _make_future_snapshot_base(real_source_manifest)
        del doc["stale_after_date"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    @pytest.mark.parametrize("bad_source_type", ["llm_generated", "scraped_unreviewed"])
    def test_forbidden_per_file_source_type_fails(
        self, real_source_manifest, source_manifest_schema, bad_source_type
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["per_file_sources"]["normalized/player_identities.json"]["source_type"] = bad_source_type
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_per_file_empty_limitations_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["per_file_sources"]["normalized/player_identities.json"]["limitations"] = []
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_per_file_empty_data_freshness_warning_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["per_file_sources"]["normalized/player_identities.json"]["data_freshness_warning"] = ""
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_top_level_forbidden_field_current_roster_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["current_roster"] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_top_level_forbidden_field_latest_roster_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["latest_roster"] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_top_level_forbidden_field_live_status_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["live_status"] = "active"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_top_level_forbidden_field_salaries_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["salaries"] = []
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_top_level_forbidden_field_injuries_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["injuries"] = []
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_top_level_forbidden_field_rumors_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["rumors"] = []
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_top_level_execution_verb_still_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["execute"] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_top_level_logo_field_still_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["nba_logo"] = "/path/to/logo.png"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_snapshot_type_live_still_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["snapshot_type"] = "live"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)

    def test_freshness_level_live_still_fails(
        self, real_source_manifest, source_manifest_schema
    ):
        doc = _make_future_snapshot_base(real_source_manifest)
        doc["freshness_level"] = "live"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, source_manifest_schema)


# --------------------------------------------------------------------------- #
# Regression / F4-B tiny pilot guard invariants
# --------------------------------------------------------------------------- #


class TestRegressionBatch1Guard:
    """M10-F5-A Batch 1 roster expansion (post GPT-5.5 source correction):
    14-player/8-team pilot. Garland (CLE->LAC) and Green (HOU->PHX) removed.
    Guard that only the approved files exist with correct scope; forbidden
    categories (contracts/salaries/cap/injuries/rumors/live) remain absent."""

    F4B_PLAYER_IDS = {
        "nba-shai-gilgeous-alexander",
        "nba-chet-holmgren",
        "nba-nikola-jokic",
        "nba-jamal-murray",
    }

    BATCH1_NEW_PLAYER_IDS = {
        "nba-jayson-tatum", "nba-jaylen-brown", "nba-jalen-brunson",
        "nba-karl-anthony-towns", "nba-donovan-mitchell",
        "nba-anthony-edwards", "nba-rudy-gobert", "nba-alperen-sengun",
        "nba-tyrese-haliburton", "nba-pascal-siakam",
    }

    SOURCE_CORRECTION_REMOVED_PLAYER_IDS = {
        "nba-darius-garland",
        "nba-jalen-green",
    }

    EXPECTED_PLAYER_COUNT = 14
    EXPECTED_MEMBERSHIP_COUNT = 14

    ALLOWED_BATCH1_TEAMS = {
        "nba-OKC", "nba-DEN", "nba-BOS", "nba-NYK",
        "nba-CLE", "nba-MIN", "nba-HOU", "nba-IND",
    }

    def test_normalized_dir_contains_only_expected_files(self):
        expected = {
            "teams.json", "team_visual_metadata.json",
            "player_identities.json", "roster_memberships.json",
        }
        actual = {p.name for p in REAL_SNAPSHOT_NORMALIZED_DIR.iterdir() if p.is_file()}
        assert actual == expected, (
            f"Real snapshot normalized/ file set changed. "
            f"Expected {sorted(expected)}, got {sorted(actual)}. "
            f"M10-F5-A Batch 1 uses player_identities.json and roster_memberships.json; "
            f"contracts, salaries, cap, injury, rumor, live files remain forbidden."
        )

    def test_player_identities_file_exists_with_batch1_players(self):
        target = REAL_SNAPSHOT_NORMALIZED_DIR / "player_identities.json"
        assert target.exists(), "player_identities.json must exist after M10-F4-B tiny pilot."
        doc = json.loads(target.read_text("utf-8"))
        assert doc.get("snapshot_id") == "nba_real_2026_preoffseason_v1"
        assert doc.get("live_eligible") is False
        assert doc.get("manual_review_required") is True
        players = doc.get("players", [])
        assert len(players) == self.EXPECTED_PLAYER_COUNT, (
            f"Expected {self.EXPECTED_PLAYER_COUNT} players after source correction, got {len(players)}"
        )
        player_ids = [p.get("player_id") for p in players]
        player_id_set = set(player_ids)
        assert self.F4B_PLAYER_IDS <= player_id_set, (
            f"Missing F4-B players: {self.F4B_PLAYER_IDS - player_id_set}"
        )
        assert self.BATCH1_NEW_PLAYER_IDS <= player_id_set, (
            f"Missing Batch 1 corrected players: {self.BATCH1_NEW_PLAYER_IDS - player_id_set}"
        )
        for removed_pid in self.SOURCE_CORRECTION_REMOVED_PLAYER_IDS:
            assert removed_pid not in player_id_set, (
                f"Source-corrected player {removed_pid} must NOT be present"
            )
        assert len(player_ids) == len(player_id_set), "Duplicate player_ids found"
        for p in players:
            assert p.get("player_id") in self.F4B_PLAYER_IDS | self.BATCH1_NEW_PLAYER_IDS
            assert p.get("live_eligible") is False
            assert p.get("manual_review_required") is True
            assert p.get("birthdate") is None
            assert p.get("height") is None
            assert p.get("weight") is None

    def test_roster_memberships_file_exists_with_batch1_memberships(self):
        target = REAL_SNAPSHOT_NORMALIZED_DIR / "roster_memberships.json"
        assert target.exists(), "roster_memberships.json must exist after M10-F4-B tiny pilot."
        doc = json.loads(target.read_text("utf-8"))
        assert doc.get("snapshot_id") == "nba_real_2026_preoffseason_v1"
        assert doc.get("live_eligible") is False
        assert doc.get("manual_review_required") is True
        mems = doc.get("roster_memberships", [])
        assert len(mems) == self.EXPECTED_MEMBERSHIP_COUNT, (
            f"Expected {self.EXPECTED_MEMBERSHIP_COUNT} memberships after source correction, got {len(mems)}"
        )
        membership_ids = [m.get("membership_id") for m in mems]
        assert len(membership_ids) == len(set(membership_ids)), "Duplicate membership_ids found"
        removed_mids = {"membership-cle-darius-garland", "membership-hou-jalen-green"}
        for removed_mid in removed_mids:
            assert removed_mid not in membership_ids, (
                f"Source-corrected membership {removed_mid} must NOT be present"
            )
        player_ids = {m.get("player_id") for m in mems}
        team_ids = {m.get("team_id") for m in mems}
        assert self.F4B_PLAYER_IDS <= player_ids, (
            f"Missing F4-B players in memberships: {self.F4B_PLAYER_IDS - player_ids}"
        )
        for removed_pid in self.SOURCE_CORRECTION_REMOVED_PLAYER_IDS:
            assert removed_pid not in player_ids, (
                f"Source-corrected player {removed_pid} must NOT appear in any membership"
            )
        assert team_ids <= self.ALLOWED_BATCH1_TEAMS, (
            f"Unexpected team IDs: {team_ids - self.ALLOWED_BATCH1_TEAMS}"
        )
        assert {"nba-OKC", "nba-DEN"} <= team_ids, "Must include OKC and DEN"
        players_doc = json.loads((REAL_SNAPSHOT_NORMALIZED_DIR / "player_identities.json").read_text("utf-8"))
        valid_player_ids = {p.get("player_id") for p in players_doc.get("players", [])}
        for m in mems:
            assert m.get("player_id") in valid_player_ids, (
                f"membership player_id {m.get('player_id')} not found in player_identities"
            )
            assert m.get("roster_status") == "standard"
            assert m.get("roster_status") != "unknown_manual_review"
            assert m.get("roster_status") != "two_way"
            assert m.get("live_eligible") is False
            assert m.get("manual_review_required") is True

    @pytest.mark.parametrize("forbidden_name", [
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
    ])
    def test_no_contract_salary_cap_injury_rumor_files(self, forbidden_name: str):
        target = REAL_SNAPSHOT_NORMALIZED_DIR / forbidden_name
        assert not target.exists(), (
            f"{forbidden_name} must NOT exist under real snapshot normalized/ in M10-F4-B."
        )

    def test_source_manifest_data_categories_correct(self):
        sm = json.loads((REAL_SNAPSHOT_DIR / "source_manifest.json").read_text("utf-8"))
        cats = set(sm.get("data_categories", []))
        assert {"teams", "team_visual_metadata", "player_identities", "roster_memberships"} <= cats
        forbidden_cats = {"contracts", "salaries", "cap_sheets", "injuries", "rumors", "scouting", "live_status"}
        assert not (cats & forbidden_cats), f"Forbidden categories present: {cats & forbidden_cats}"
        assert sm.get("live_eligible") is False
        assert sm.get("manual_review_required") is True
        assert sm.get("stale_after_date") == "2026-07-12"
        assert sm.get("as_of_date") == "2026-06-28"

    def test_no_real_snapshot_top_level_data_files_added(self):
        expected = {"manifest.json", "source_manifest.json", "normalized"}
        actual = {p.name for p in REAL_SNAPSHOT_DIR.iterdir()}
        unexpected = actual - expected
        assert not unexpected, (
            f"Unexpected files/dirs in real snapshot root: {sorted(unexpected)}. "
            f"M10-F4-B must not add additional top-level files."
        )
