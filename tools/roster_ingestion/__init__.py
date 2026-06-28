"""Authorized/offline roster ingestion tooling.

M10-F6: Offline provider adapter skeleton for authorized roster API ingestion.
This package contains the provider contract, field allowlist, normalizer,
and a fake in-memory provider for testing. It is an offline data production
tool — NOT a runtime dependency of the backend service.

Key modules:
- models: Data classes for provider-side records and errors.
- provider_contract: RosterProvider Protocol.
- field_whitelist: Allowlist of fields permitted in normalized output.
- normalizer: Converts provider records to normalized candidate dicts.
- fake_provider: In-memory fixture provider for offline testing.

No HTTP imports (requests/httpx/aiohttp/urllib) exist in this package.
No API keys are read or required for F6-B.
"""

from tools.roster_ingestion.models import (
    ForbiddenFieldLeakageError,
    MembershipIdCollisionError,
    PlayerIdCollisionError,
    PlayerXrefError,
    ProviderMetadata,
    ProviderPlayerRecord,
    ProviderRosterSnapshot,
    ProviderTeamRoster,
    RosterIngestionError,
    TeamNotInScopeError,
    UnknownRosterStatusError,
)
from tools.roster_ingestion.provider_contract import RosterProvider
from tools.roster_ingestion.fake_provider import FakeRosterProvider
from tools.roster_ingestion.normalizer import normalize_snapshot

__all__ = [
    "ProviderMetadata",
    "ProviderPlayerRecord",
    "ProviderRosterSnapshot",
    "ProviderTeamRoster",
    "RosterProvider",
    "FakeRosterProvider",
    "normalize_snapshot",
    "RosterIngestionError",
    "UnknownRosterStatusError",
    "PlayerIdCollisionError",
    "MembershipIdCollisionError",
    "ForbiddenFieldLeakageError",
    "TeamNotInScopeError",
    "PlayerXrefError",
]
