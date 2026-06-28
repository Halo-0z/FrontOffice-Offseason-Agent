"""Data models for the roster ingestion provider adapter skeleton.

M10-F6-B: Offline provider adapter skeleton for authorized roster API ingestion.
These models represent raw/provider-side data structures before normalization.
They are intentionally decoupled from the normalized schema and the backend
read model to keep the ingestion pipeline an offline production tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ProviderMetadata:
    """Provider-level metadata for a roster snapshot capture."""

    provider_name: str
    endpoint_docs_url: str
    access_date: str
    as_of_date: str
    license_note: str
    stale_after_date: str


@dataclass(frozen=True)
class ProviderPlayerRecord:
    """A single player record as returned by a provider API.

    This is the raw-ish representation. It may contain extra fields from the
    provider (salary, injury, depth, etc.) that the normalizer MUST discard.
    """

    provider_player_id: str
    first_name: str
    last_name: str
    display_name: str
    position: Optional[str]
    roster_status_raw: str
    extra_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderTeamRoster:
    """A single team's roster from the provider."""

    team_id: str
    provider_team_id: str
    team_name: str
    players: List[ProviderPlayerRecord]
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderRosterSnapshot:
    """A full snapshot containing multiple team rosters from one provider fetch."""

    metadata: ProviderMetadata
    team_rosters: List[ProviderTeamRoster]


class RosterIngestionError(Exception):
    """Base error for roster ingestion failures (hard error)."""


class UnknownRosterStatusError(RosterIngestionError):
    """Raised when a provider roster_status_raw cannot be safely mapped."""


class PlayerIdCollisionError(RosterIngestionError):
    """Raised when slug generation produces a duplicate player_id."""


class MembershipIdCollisionError(RosterIngestionError):
    """Raised when membership_id generation produces a duplicate."""


class ForbiddenFieldLeakageError(RosterIngestionError):
    """Raised when normalized output would contain a forbidden field."""


class TeamNotInScopeError(RosterIngestionError):
    """Raised when a team_id is not in the allowed scope set."""


class PlayerXrefError(RosterIngestionError):
    """Raised when a membership references a player_id not in the normalized set."""
