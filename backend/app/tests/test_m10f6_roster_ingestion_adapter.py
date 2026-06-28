"""Tests for M10-F6-B Provider Adapter Skeleton.

These tests verify:
- Fake provider returns fixture rosters without network/keys
- RosterProvider Protocol is satisfied by FakeRosterProvider
- Normalizer only outputs allowlisted fields
- Forbidden fields do NOT leak into normalized output
- Unknown roster_status fails closed (never defaults to standard)
- Duplicate player_id / membership_id collision guard works
- Membership xref integrity
- team_id scope validation
- live_eligible=false, manual_review_required=true, birthdate/height/weight=null
- No writes to data/snapshots/
- No HTTP imports in tools/roster_ingestion
- No API key reads, no network calls
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any, Dict, Set

import pytest

from tools.roster_ingestion import (
    FakeRosterProvider,
    ForbiddenFieldLeakageError,
    MembershipIdCollisionError,
    PlayerIdCollisionError,
    PlayerXrefError,
    ProviderMetadata,
    ProviderPlayerRecord,
    ProviderRosterSnapshot,
    ProviderTeamRoster,
    RosterIngestionError,
    RosterProvider,
    TeamNotInScopeError,
    UnknownRosterStatusError,
    normalize_snapshot,
)
from tools.roster_ingestion.field_whitelist import (
    ALLOWED_MEMBERSHIP_FIELDS,
    ALLOWED_PLAYER_FIELDS,
    FORBIDDEN_PROVIDER_FIELDS,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_SNAPSHOTS_DIR = REPO_ROOT / "data" / "snapshots"


# --------------------------------------------------------------------------- #
# Isolation / no-network / no-key tests
# --------------------------------------------------------------------------- #


class TestAdapterIsolation:
    """Verify no network imports, no API keys, no data writes."""

    def test_no_requests_import_in_tools(self) -> None:
        """tools/roster_ingestion must not import requests/httpx/aiohttp/urllib."""
        pkg_dir = REPO_ROOT / "tools" / "roster_ingestion"
        for py_file in pkg_dir.glob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            for forbidden in ("import requests", "import httpx", "import aiohttp",
                              "from requests", "from httpx", "from aiohttp",
                              "import urllib.request", "from urllib.request",
                              "import urllib3", "from urllib3"):
                assert forbidden not in source, (
                    f"{py_file.name} contains forbidden network import: {forbidden}"
                )

    def test_no_api_key_env_read_in_tools_init(self) -> None:
        """tools/roster_ingestion must not read SPORTRADAR/SPORTSDATAIO keys at import."""
        for key in ("SPORTRADAR_NBA_API_KEY", "SPORTSDATAIO_NBA_API_KEY"):
            os.environ.pop(key, None)
        import tools.roster_ingestion
        importlib.reload(tools.roster_ingestion)
        import tools.roster_ingestion.normalizer
        importlib.reload(tools.roster_ingestion.normalizer)
        import tools.roster_ingestion.fake_provider
        importlib.reload(tools.roster_ingestion.fake_provider)

    def test_pytest_does_not_require_api_key(self) -> None:
        """The test suite must run without any API keys set."""
        for key in ("SPORTRADAR_NBA_API_KEY", "SPORTSDATAIO_NBA_API_KEY"):
            assert os.environ.get(key) is None, (
                f"API key {key} must not be set during tests"
            )

    def test_normalizer_does_not_write_to_data_snapshots(self, tmp_path: Path) -> None:
        """normalize_snapshot is a pure function; it must not write to disk."""
        fp = FakeRosterProvider()
        snap = fp.build_snapshot(team_ids=["nba-FAK"])
        before = set()
        if DATA_SNAPSHOTS_DIR.is_dir():
            for p in DATA_SNAPSHOTS_DIR.rglob("*"):
                if p.is_file():
                    before.add(str(p))
        _p, _m = normalize_snapshot(snap)
        after = set()
        if DATA_SNAPSHOTS_DIR.is_dir():
            for p in DATA_SNAPSHOTS_DIR.rglob("*"):
                if p.is_file():
                    after.add(str(p))
        assert before == after, "normalize_snapshot must not write to data/snapshots"


# --------------------------------------------------------------------------- #
# Provider contract tests
# --------------------------------------------------------------------------- #


class TestProviderContract:
    """Verify FakeRosterProvider satisfies the RosterProvider Protocol."""

    def test_fake_provider_is_roster_provider(self) -> None:
        fp = FakeRosterProvider()
        assert isinstance(fp, RosterProvider)

    def test_provider_name(self) -> None:
        fp = FakeRosterProvider()
        assert fp.provider_name == "fake_fixture"

    def test_get_metadata(self) -> None:
        fp = FakeRosterProvider()
        meta = fp.get_metadata()
        assert isinstance(meta, ProviderMetadata)
        assert meta.provider_name == "fake_fixture"
        assert meta.as_of_date == "2026-06-28"
        assert meta.access_date == "2026-06-28"
        assert meta.stale_after_date == "2026-07-28"

    def test_fetch_team_roster(self) -> None:
        fp = FakeRosterProvider()
        roster = fp.fetch_team_roster("nba-FAK")
        assert isinstance(roster, ProviderTeamRoster)
        assert roster.team_id == "nba-FAK"
        assert len(roster.players) == 2

    def test_fetch_team_roster_missing_raises(self) -> None:
        fp = FakeRosterProvider()
        with pytest.raises(KeyError):
            fp.fetch_team_roster("nba-NOPE")

    def test_fetch_all_team_rosters_default(self) -> None:
        fp = FakeRosterProvider()
        all_rosters = fp.fetch_all_team_rosters()
        assert len(all_rosters) == 3
        assert "nba-FAK" in all_rosters
        assert "nba-FB2" in all_rosters
        assert "nba-FC3" in all_rosters

    def test_fetch_all_team_rosters_with_ids(self) -> None:
        fp = FakeRosterProvider()
        rosters = fp.fetch_all_team_rosters(team_ids=["nba-FAK"])
        assert len(rosters) == 1
        assert "nba-FAK" in rosters

    def test_build_snapshot(self) -> None:
        fp = FakeRosterProvider()
        snap = fp.build_snapshot(team_ids=["nba-FAK"])
        assert isinstance(snap, ProviderRosterSnapshot)
        assert len(snap.team_rosters) == 1
        assert isinstance(snap.metadata, ProviderMetadata)


# --------------------------------------------------------------------------- #
# Field whitelist / forbidden field tests
# --------------------------------------------------------------------------- #


class TestFieldWhitelist:
    """Verify the allowlist blocks forbidden fields."""

    FORBIDDEN_KEYS_SAMPLE: Set[str] = {
        "salary", "contract", "cap_sheet", "injury", "medical",
        "rumor", "scouting_opinion", "live_status", "depth_chart",
        "minutes_projection", "role_projection", "trade_eligibility",
        "current_roster", "latest_roster", "live_data",
    }

    def test_allowed_player_fields_no_forbidden(self) -> None:
        overlap = ALLOWED_PLAYER_FIELDS & self.FORBIDDEN_KEYS_SAMPLE
        assert not overlap, f"Forbidden keys in player allowlist: {overlap}"

    def test_allowed_membership_fields_no_forbidden(self) -> None:
        overlap = ALLOWED_MEMBERSHIP_FIELDS & self.FORBIDDEN_KEYS_SAMPLE
        assert not overlap, f"Forbidden keys in membership allowlist: {overlap}"

    def test_no_salary_contract_cap_in_allowed(self) -> None:
        for f in ALLOWED_PLAYER_FIELDS | ALLOWED_MEMBERSHIP_FIELDS:
            fl = f.lower()
            assert "salary" not in fl
            assert "contract" not in fl
            assert "cap" not in fl
            assert "injury" not in fl

    def test_forbidden_provider_fields_contains_key_domains(self) -> None:
        for key in ("salary", "contract", "injury", "rumor", "scouting_opinion",
                     "live_status", "depth_chart", "trade_eligibility"):
            assert key in FORBIDDEN_PROVIDER_FIELDS


# --------------------------------------------------------------------------- #
# Normalizer tests: happy path
# --------------------------------------------------------------------------- #


class TestNormalizerHappyPath:
    """Normalizer produces correct output for valid fixture data."""

    @pytest.fixture()
    def valid_snapshot(self) -> ProviderRosterSnapshot:
        fp = FakeRosterProvider()
        return fp.build_snapshot(team_ids=["nba-FAK"])

    def test_returns_two_dicts(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        players_doc, memberships_doc = normalize_snapshot(valid_snapshot)
        assert isinstance(players_doc, dict)
        assert isinstance(memberships_doc, dict)

    def test_player_count(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        players_doc, memberships_doc = normalize_snapshot(valid_snapshot)
        assert len(players_doc["players"]) == 2
        assert len(memberships_doc["roster_memberships"]) == 2

    def test_player_ids_are_stable_slugs(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        players_doc, _ = normalize_snapshot(valid_snapshot)
        pids = {p["player_id"] for p in players_doc["players"]}
        assert pids == {"nba-test-alpha", "nba-test-beta"}

    def test_membership_ids_are_stable(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        _, memberships_doc = normalize_snapshot(valid_snapshot)
        mids = {m["membership_id"] for m in memberships_doc["roster_memberships"]}
        assert mids == {"membership-fak-test-alpha", "membership-fak-test-beta"}

    def test_roster_status_mapping(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        _, memberships_doc = normalize_snapshot(valid_snapshot)
        statuses = {m["membership_id"]: m["roster_status"]
                    for m in memberships_doc["roster_memberships"]}
        assert statuses["membership-fak-test-alpha"] == "standard"
        assert statuses["membership-fak-test-beta"] == "two_way"

    def test_birthdate_height_weight_null(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        players_doc, _ = normalize_snapshot(valid_snapshot)
        for p in players_doc["players"]:
            assert p["birthdate"] is None
            assert p["height"] is None
            assert p["weight"] is None

    def test_live_eligible_false(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        players_doc, memberships_doc = normalize_snapshot(valid_snapshot)
        for p in players_doc["players"]:
            assert p["live_eligible"] is False
        for m in memberships_doc["roster_memberships"]:
            assert m["live_eligible"] is False
        assert players_doc["live_eligible"] is False
        assert memberships_doc["live_eligible"] is False

    def test_manual_review_required_true(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        players_doc, memberships_doc = normalize_snapshot(valid_snapshot)
        for p in players_doc["players"]:
            assert p["manual_review_required"] is True
        for m in memberships_doc["roster_memberships"]:
            assert m["manual_review_required"] is True
        assert players_doc["manual_review_required"] is True
        assert memberships_doc["manual_review_required"] is True

    def test_only_allowlisted_fields_in_players(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        players_doc, _ = normalize_snapshot(valid_snapshot)
        for p in players_doc["players"]:
            extra = set(p.keys()) - ALLOWED_PLAYER_FIELDS
            assert not extra, f"Non-allowlisted fields in player {p['player_id']}: {extra}"

    def test_only_allowlisted_fields_in_memberships(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        _, memberships_doc = normalize_snapshot(valid_snapshot)
        for m in memberships_doc["roster_memberships"]:
            extra = set(m.keys()) - ALLOWED_MEMBERSHIP_FIELDS
            assert not extra, f"Non-allowlisted fields in membership {m['membership_id']}: {extra}"

    def test_forbidden_fields_not_in_output(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        """Even though fake provider's Test Alpha has salary/injury/depth in extra_fields,
        they must NOT appear in normalized output."""
        players_doc, memberships_doc = normalize_snapshot(valid_snapshot)
        for p in players_doc["players"]:
            for fk in FORBIDDEN_PROVIDER_FIELDS:
                assert fk not in p, (
                    f"Forbidden field '{fk}' leaked into player {p['player_id']}"
                )
        for m in memberships_doc["roster_memberships"]:
            for fk in FORBIDDEN_PROVIDER_FIELDS:
                assert fk not in m, (
                    f"Forbidden field '{fk}' leaked into membership {m['membership_id']}"
                )

    def test_membership_xref_integrity(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        players_doc, memberships_doc = normalize_snapshot(valid_snapshot)
        pids = {p["player_id"] for p in players_doc["players"]}
        for m in memberships_doc["roster_memberships"]:
            assert m["player_id"] in pids, (
                f"Membership {m['membership_id']} xref to unknown player {m['player_id']}"
            )
            assert m["team_id"] == "nba-FAK"

    def test_data_freshness_warning_present(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        players_doc, memberships_doc = normalize_snapshot(valid_snapshot)
        assert "not current/live" in players_doc["data_freshness_warning"]
        assert "not current/live" in memberships_doc["data_freshness_warning"]

    def test_stale_after_date_present(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        players_doc, _ = normalize_snapshot(valid_snapshot)
        assert players_doc["stale_after_date"] == "2026-07-28"

    def test_limitations_present(self, valid_snapshot: ProviderRosterSnapshot) -> None:
        players_doc, _ = normalize_snapshot(valid_snapshot)
        assert "no_salary" in players_doc["limitations"]
        assert "no_contract" in players_doc["limitations"]
        assert "not_live" in players_doc["limitations"]


# --------------------------------------------------------------------------- #
# Unknown roster_status -> fail closed
# --------------------------------------------------------------------------- #


class TestUnknownRosterStatus:
    """Unknown roster_status must NEVER default to standard; fail closed."""

    def test_unknown_status_raises_hard_error(self) -> None:
        fp = FakeRosterProvider()
        snap = fp.build_snapshot(team_ids=["nba-FB2"])
        with pytest.raises(UnknownRosterStatusError) as exc_info:
            normalize_snapshot(snap)
        assert "Test Gamma" in str(exc_info.value)
        assert "unknown_status" in str(exc_info.value)

    def test_unknown_status_prevents_partial_output(self) -> None:
        """If any player has unknown status, the entire normalization fails."""
        fp = FakeRosterProvider()
        snap = fp.build_snapshot(team_ids=["nba-FAK", "nba-FB2"])
        with pytest.raises(UnknownRosterStatusError):
            normalize_snapshot(snap)

    def test_empty_status_raw_raises(self) -> None:
        meta = ProviderMetadata(
            provider_name="test",
            endpoint_docs_url="https://example.com",
            access_date="2026-06-28",
            as_of_date="2026-06-28",
            license_note="test",
            stale_after_date="2026-07-28",
        )
        bad_player = ProviderPlayerRecord(
            provider_player_id="bp-1",
            first_name="Bad",
            last_name="Status",
            display_name="Bad Status",
            position="G",
            roster_status_raw="",
            extra_fields={},
        )
        bad_team = ProviderTeamRoster(
            team_id="nba-BAD",
            provider_team_id="bad-1",
            team_name="Bad Team",
            players=[bad_player],
        )
        snap = ProviderRosterSnapshot(metadata=meta, team_rosters=[bad_team])
        with pytest.raises(UnknownRosterStatusError):
            normalize_snapshot(snap, allowed_team_ids={"nba-BAD"})


# --------------------------------------------------------------------------- #
# Collision / duplicate detection tests
# --------------------------------------------------------------------------- #


class TestCollisionDetection:
    """Duplicate player_id / membership_id must be detected."""

    def test_name_collision_gets_disambiguator(self) -> None:
        """Two players with same first+last name on different teams get disambiguated."""
        fp = FakeRosterProvider()
        snap = fp.build_snapshot(team_ids=["nba-FAK", "nba-FC3"])
        players_doc, memberships_doc = normalize_snapshot(snap)
        pids = {p["player_id"] for p in players_doc["players"]}
        assert "nba-test-alpha" in pids
        assert "nba-test-alpha-2" in pids
        assert len(pids) == 3

    def test_explicit_duplicate_player_id_raises(self) -> None:
        """If normalizer produces same pid after disambiguation, raise hard error."""
        meta = ProviderMetadata(
            provider_name="test",
            endpoint_docs_url="https://example.com",
            access_date="2026-06-28",
            as_of_date="2026-06-28",
            license_note="test",
            stale_after_date="2026-07-28",
        )
        players = [
            ProviderPlayerRecord(
                provider_player_id="tp-1",
                first_name="Same",
                last_name="Name",
                display_name="Same Name 1",
                position="G",
                roster_status_raw="standard",
            ),
            ProviderPlayerRecord(
                provider_player_id="tp-2",
                first_name="Same",
                last_name="Name",
                display_name="Same Name 2",
                position="F",
                roster_status_raw="standard",
            ),
            ProviderPlayerRecord(
                provider_player_id="tp-3",
                first_name="Same",
                last_name="Name",
                display_name="Same Name 3",
                position="C",
                roster_status_raw="standard",
            ),
        ]
        team1 = ProviderTeamRoster(
            team_id="nba-TA", provider_team_id="ta-1", team_name="Team A",
            players=players[:2],
        )
        team2 = ProviderTeamRoster(
            team_id="nba-TB", provider_team_id="tb-1", team_name="Team B",
            players=[players[2]],
        )
        snap = ProviderRosterSnapshot(metadata=meta, team_rosters=[team1, team2])
        pdoc, _ = normalize_snapshot(snap, allowed_team_ids={"nba-TA", "nba-TB"})
        pids = [p["player_id"] for p in pdoc["players"]]
        assert len(pids) == 3
        assert len(set(pids)) == 3
        assert "nba-same-name" in pids
        assert "nba-same-name-2" in pids
        assert "nba-same-name-3" in pids

    def test_team_scope_validation(self) -> None:
        """Teams not in allowed_team_ids raise TeamNotInScopeError."""
        fp = FakeRosterProvider()
        snap = fp.build_snapshot(team_ids=["nba-FAK"])
        with pytest.raises(TeamNotInScopeError):
            normalize_snapshot(snap, allowed_team_ids={"nba-ONLY"})


# --------------------------------------------------------------------------- #
# Pure function / no-side-effect tests
# --------------------------------------------------------------------------- #


class TestNormalizerSideEffects:
    """normalize_snapshot must be a pure function (no mutation, no I/O)."""

    def test_normalizer_does_not_mutate_provider_snapshot(self) -> None:
        fp = FakeRosterProvider()
        snap = fp.build_snapshot(team_ids=["nba-FAK"])
        import copy
        snap_copy = copy.deepcopy(snap)
        normalize_snapshot(snap)
        assert snap == snap_copy, "normalize_snapshot must not mutate its input"

    def test_normalizer_returns_python_dicts_not_files(self) -> None:
        fp = FakeRosterProvider()
        snap = fp.build_snapshot(team_ids=["nba-FAK"])
        p, m = normalize_snapshot(snap)
        assert isinstance(p, dict)
        assert isinstance(m, dict)
        assert isinstance(p["players"], list)
        assert isinstance(m["roster_memberships"], list)


# --------------------------------------------------------------------------- #
# Fake provider fixture scenario coverage
# --------------------------------------------------------------------------- #


class TestFakeProviderScenarios:
    """Verify the fake provider covers all required scenarios."""

    def test_fake_has_standard_player(self) -> None:
        fp = FakeRosterProvider()
        roster = fp.fetch_team_roster("nba-FAK")
        statuses = {p.roster_status_raw for p in roster.players}
        assert "standard" in statuses

    def test_fake_has_two_way_player(self) -> None:
        fp = FakeRosterProvider()
        roster = fp.fetch_team_roster("nba-FAK")
        statuses = {p.roster_status_raw for p in roster.players}
        assert "two-way" in statuses

    def test_fake_has_unknown_status_player(self) -> None:
        fp = FakeRosterProvider()
        roster = fp.fetch_team_roster("nba-FB2")
        assert any(p.roster_status_raw == "unknown_status" for p in roster.players)

    def test_fake_has_player_with_forbidden_extra_fields(self) -> None:
        fp = FakeRosterProvider()
        roster = fp.fetch_team_roster("nba-FAK")
        alpha = next(p for p in roster.players if p.last_name == "Alpha")
        assert "salary" in alpha.extra_fields
        assert "injury_status" in alpha.extra_fields
        assert "depth_chart_position" in alpha.extra_fields
        assert "scouting_report" in alpha.extra_fields

    def test_fake_has_collision_case(self) -> None:
        fp = FakeRosterProvider()
        r1 = fp.fetch_team_roster("nba-FAK")
        r2 = fp.fetch_team_roster("nba-FC3")
        alpha1 = next(p for p in r1.players if p.last_name == "Alpha")
        alpha2 = next(p for p in r2.players if p.last_name == "Alpha")
        assert alpha1.first_name == alpha2.first_name
        assert alpha1.last_name == alpha2.last_name


# --------------------------------------------------------------------------- #
# Backend service isolation (no imports from tools into backend services)
# --------------------------------------------------------------------------- #


class TestBackendServiceIsolation:
    """Backend app services must NOT import tools.roster_ingestion."""

    def test_backend_services_no_tools_import(self) -> None:
        services_dir = REPO_ROOT / "backend" / "app" / "services"
        for py_file in services_dir.glob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            assert "tools.roster_ingestion" not in source, (
                f"{py_file.name} must not import from tools.roster_ingestion "
                f"(ingestion is an offline tool, not a runtime dependency)"
            )

    def test_no_runtime_fetch_in_service(self) -> None:
        """player_roster_metadata_reader.py must not contain HTTP client usage."""
        reader_path = REPO_ROOT / "backend" / "app" / "services" / "player_roster_metadata_reader.py"
        source = reader_path.read_text(encoding="utf-8")
        for forbidden in ("requests.get", "httpx.", "aiohttp.", "urllib.request",
                          "urlopen", "fetch_http", "http://", "https://"):
            assert forbidden not in source, (
                f"Backend reader must not contain runtime HTTP: {forbidden}"
            )
