"""Fake (in-memory fixture) roster provider for F6-B skeleton testing.

M10-F6-B: This provider returns hardcoded fixture data only. It never makes
network requests, never reads API keys, and never touches disk. It is used
exclusively to test the normalizer and provider contract offline.

Fixture scenarios covered:
- Normal standard-contract player
- Two-way contract player
- Unknown/ambiguous roster_status (should fail closed in normalizer)
- Provider records that include forbidden fields (salary, injury, depth, etc.)
  to verify the normalizer's allowlist strips them
- Name collision scenario (two players with same first+last name slug)
"""

from __future__ import annotations

from typing import Dict, List, Optional

from tools.roster_ingestion.models import (
    ProviderMetadata,
    ProviderPlayerRecord,
    ProviderRosterSnapshot,
    ProviderTeamRoster,
)
from tools.roster_ingestion.provider_contract import RosterProvider


_FAKE_METADATA = ProviderMetadata(
    provider_name="fake_fixture",
    endpoint_docs_url="https://example.com/fake-provider-docs",
    access_date="2026-06-28",
    as_of_date="2026-06-28",
    license_note="Fake fixture data for offline testing only; not real NBA data.",
    stale_after_date="2026-07-28",
)


def _make_fake_rosters() -> Dict[str, ProviderTeamRoster]:
    """Build fake fixture rosters covering all test scenarios."""
    return {
        "nba-FAK": ProviderTeamRoster(
            team_id="nba-FAK",
            provider_team_id="fak-001",
            team_name="Fake Team One",
            players=[
                ProviderPlayerRecord(
                    provider_player_id="fp-001",
                    first_name="Test",
                    last_name="Alpha",
                    display_name="Test Alpha",
                    position="G",
                    roster_status_raw="standard",
                    extra_fields={
                        "source_url": "https://example.com/fake/alpha",
                        "salary": 5000000,
                        "injury_status": "healthy",
                        "depth_chart_position": "starter",
                        "jersey_number": 1,
                        "scouting_report": "good shooter",
                    },
                ),
                ProviderPlayerRecord(
                    provider_player_id="fp-002",
                    first_name="Test",
                    last_name="Beta",
                    display_name="Test Beta",
                    position="F",
                    roster_status_raw="two-way",
                    extra_fields={
                        "source_url": "https://example.com/fake/beta",
                        "contract_years": 2,
                        "guarantee_amount": 500000,
                    },
                ),
            ],
        ),
        "nba-FB2": ProviderTeamRoster(
            team_id="nba-FB2",
            provider_team_id="fb2-002",
            team_name="Fake Team Two",
            players=[
                ProviderPlayerRecord(
                    provider_player_id="fp-003",
                    first_name="Test",
                    last_name="Gamma",
                    display_name="Test Gamma",
                    position="C",
                    roster_status_raw="unknown_status",
                    extra_fields={
                        "source_url": "https://example.com/fake/gamma",
                    },
                ),
            ],
        ),
        "nba-FC3": ProviderTeamRoster(
            team_id="nba-FC3",
            provider_team_id="fc3-003",
            team_name="Fake Collision Team",
            players=[
                ProviderPlayerRecord(
                    provider_player_id="fp-004",
                    first_name="Test",
                    last_name="Alpha",
                    display_name="Test Alpha (FC3)",
                    position="G",
                    roster_status_raw="standard",
                    extra_fields={
                        "source_url": "https://example.com/fake/alpha2",
                    },
                ),
            ],
        ),
    }


class FakeRosterProvider:
    """In-memory fake roster provider for offline skeleton testing.

    Returns hardcoded fixture data. Never makes network calls, never reads
    API keys, never touches the filesystem.
    """

    def __init__(self) -> None:
        self._rosters: Dict[str, ProviderTeamRoster] = _make_fake_rosters()

    @property
    def provider_name(self) -> str:
        return "fake_fixture"

    def get_metadata(self) -> ProviderMetadata:
        return _FAKE_METADATA

    def fetch_team_roster(self, team_id: str) -> ProviderTeamRoster:
        if team_id not in self._rosters:
            raise KeyError(f"Fake provider has no fixture for team '{team_id}'")
        return self._rosters[team_id]

    def fetch_all_team_rosters(
        self,
        team_ids: Optional[List[str]] = None,
    ) -> Dict[str, ProviderTeamRoster]:
        if team_ids is None:
            return dict(self._rosters)
        result: Dict[str, ProviderTeamRoster] = {}
        for tid in team_ids:
            if tid not in self._rosters:
                raise KeyError(f"Fake provider has no fixture for team '{tid}'")
            result[tid] = self._rosters[tid]
        return result

    def build_snapshot(
        self,
        team_ids: Optional[List[str]] = None,
    ) -> ProviderRosterSnapshot:
        """Convenience method to build a full ProviderRosterSnapshot."""
        rosters = self.fetch_all_team_rosters(team_ids)
        return ProviderRosterSnapshot(
            metadata=self.get_metadata(),
            team_rosters=list(rosters.values()),
        )
