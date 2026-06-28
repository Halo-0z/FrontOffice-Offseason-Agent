"""Provider contract (Protocol) for roster API adapters.

M10-F6-B: Defines the interface that all provider adapters (Sportradar,
SportsDataIO, fake/fixture, etc.) must implement. F6-B ships only with a
fake in-memory provider; real providers are F6-C+ and require an authorized
API key.

Design rules:
- No imports of requests/httpx/aiohttp/urllib at module level.
- The protocol never performs network I/O itself; concrete implementations
  may do so only in F6-C+ when an authorized key is present.
- F6-B fake provider returns hardcoded in-memory fixtures only.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Protocol, runtime_checkable

from tools.roster_ingestion.models import (
    ProviderMetadata,
    ProviderTeamRoster,
)


@runtime_checkable
class RosterProvider(Protocol):
    """Protocol for authorized roster API providers.

    Implementations fetch roster data from a single provider and return
    ProviderTeamRoster objects. In F6-B, only the FakeProvider implements
    this protocol; real HTTP-backed providers come in F6-C+ when an
    authorized API key is available.
    """

    @property
    def provider_name(self) -> str:
        """Unique provider identifier (e.g. 'sportradar', 'sportsdataio', 'fake')."""
        ...

    def fetch_team_roster(
        self,
        team_id: str,
    ) -> ProviderTeamRoster:
        """Fetch the roster for a single team.

        Args:
            team_id: The NBA team ID in nba-XXX format (e.g. 'nba-GSW').

        Returns:
            A ProviderTeamRoster with the team's players as raw provider records.
        """
        ...

    def fetch_all_team_rosters(
        self,
        team_ids: Optional[List[str]] = None,
    ) -> Dict[str, ProviderTeamRoster]:
        """Fetch rosters for multiple teams.

        Args:
            team_ids: List of team IDs to fetch. If None, the provider may
                return all available teams.

        Returns:
            Dict mapping team_id -> ProviderTeamRoster.
        """
        ...

    def get_metadata(self) -> ProviderMetadata:
        """Return provider-level metadata for this fetch session."""
        ...
