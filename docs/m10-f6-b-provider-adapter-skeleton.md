# M10-F6-B: Provider Adapter Skeleton

## 1. Scope

F6-B builds the provider adapter skeleton for authorized/offline roster API ingestion. This is a tooling-only milestone: it creates the package structure, provider contract (Protocol), field allowlist, normalizer, and a fake in-memory fixture provider for testing. **No real API calls, no API keys, no network access, no raw snapshots, and no normalized data files are produced.**

The skeleton is an offline data production tool. It lives under `tools/roster_ingestion/` to clearly separate it from the runtime backend. The backend service (`player_roster_metadata_reader.py`) continues to read only frozen disk snapshots and has zero awareness of this tooling.

## 2. What Was Added

### New package: `tools/roster_ingestion/`

| File | Purpose |
|------|---------|
| `__init__.py` | Package init; exports public API (models, protocol, fake provider, normalizer). |
| `models.py` | Frozen dataclasses for `ProviderMetadata`, `ProviderPlayerRecord`, `ProviderTeamRoster`, `ProviderRosterSnapshot`, and error types (`UnknownRosterStatusError`, `PlayerIdCollisionError`, `MembershipIdCollisionError`, `ForbiddenFieldLeakageError`, `TeamNotInScopeError`, `PlayerXrefError`). |
| `provider_contract.py` | `RosterProvider` Protocol defining `provider_name`, `fetch_team_roster()`, `fetch_all_team_rosters()`, and `get_metadata()`. Uses `@runtime_checkable` for isinstance verification. |
| `field_whitelist.py` | Explicit allowlists (`ALLOWED_PLAYER_FIELDS`, `ALLOWED_MEMBERSHIP_FIELDS`), forbidden field reference set (`FORBIDDEN_PROVIDER_FIELDS`), allowed roster statuses, and helper functions (`filter_player_fields`, `filter_membership_fields`, `detect_forbidden_fields`). Uses **allowlist** enforcement, not blocklist. |
| `normalizer.py` | `normalize_snapshot()` function that converts a `ProviderRosterSnapshot` into `(players_doc, memberships_doc)` Python dicts. Handles slug generation, collision disambiguation, roster_status mapping, team scope validation, player↔membership xref, and hard errors on unknown status. Does NOT write files. |
| `fake_provider.py` | `FakeRosterProvider` — an in-memory fixture implementation of `RosterProvider`. Returns hardcoded fake teams/players covering all required test scenarios. No network, no keys, no disk I/O. |

### New test file: `backend/app/tests/test_m10f6_roster_ingestion_adapter.py`

46 tests covering:
- Isolation: no HTTP imports, no API keys, no writes to `data/snapshots/`
- Provider contract: FakeRosterProvider satisfies `RosterProvider` Protocol
- Field whitelist: allowlists contain no forbidden keys; forbidden fields are documented
- Happy path: correct counts, stable slugs, status mapping, null optional fields, governance flags
- Forbidden field leakage: extra_fields with salary/injury/depth are NOT in normalized output
- Unknown roster status: fails closed with `UnknownRosterStatusError`, never defaults to standard
- Collision detection: same-named players get disambiguated; duplicate pids/mids are caught
- Team scope validation: out-of-scope team_ids raise `TeamNotInScopeError`
- Pure function: normalizer does not mutate input or write to disk
- Fake provider scenario coverage: standard, two_way, unknown_status, forbidden fields, collision
- Backend service isolation: services must not import `tools.roster_ingestion`

### New documentation: this file

## 3. What Was NOT Added

- **No API key**: No `.env` file, no key in code, no reads from `SPORTRADAR_NBA_API_KEY` / `SPORTSDATAIO_NBA_API_KEY`.
- **No network calls**: No `requests`, `httpx`, `aiohttp`, or `urllib` imports anywhere in `tools/roster_ingestion/`. Tests never make HTTP requests.
- **No raw snapshots**: No files under `data/snapshots/**/raw/`.
- **No normalized roster data**: `player_identities.json` and `roster_memberships.json` remain at F5-A state (14 players / 8 teams).
- **No backend modifications**: `backend/app/api.py`, `backend/app/services/`, `backend/app/snapshot_loader.py`, `backend/app/models/` are untouched.
- **No frontend modifications**: `frontend/` is untouched.
- **No schema modifications**: Schemas under `schema/` are untouched (F6-A design gate noted a small schema patch is recommended for F6-D to add `authorized_api_snapshot` source_type, but that is deferred).
- **No API endpoints**: No new routes.
- **No Agent/NL/trade/signing changes**: Those modules are untouched.
- **No salary/contract/cap/injury/scouting/rumor/live data**: Zero forbidden fields are introduced.
- **No dependency changes**: `requirements.txt`, `pyproject.toml` are untouched.

## 4. Provider Contract Summary

```python
class RosterProvider(Protocol):
    @property
    def provider_name(self) -> str: ...
    def fetch_team_roster(self, team_id: str) -> ProviderTeamRoster: ...
    def fetch_all_team_rosters(self, team_ids: list[str] | None) -> dict[str, ProviderTeamRoster]: ...
    def get_metadata(self) -> ProviderMetadata: ...
```

The contract is intentionally minimal. Real providers (Sportradar, SportsDataIO) will implement this protocol in F6-C+ when an authorized API key is available. The fake provider in F6-B is the only implementation and uses purely in-memory fixtures.

## 5. Field Whitelist Summary

The normalizer constructs player and membership records using **explicit field-by-field assembly**. Only fields listed in `ALLOWED_PLAYER_FIELDS` and `ALLOWED_MEMBERSHIP_FIELDS` can appear in normalized output. After assembly, the normalizer runs a second check: any key not in the allowlist raises `ForbiddenFieldLeakageError`. Additionally, `detect_forbidden_fields` provides defense-in-depth by scanning for known forbidden keys.

**Player allowlist:** player_id, display_name, first_name, last_name, position, birthdate, height, weight, source_type, source_name, source_url, source_retrieved_at, confidence, live_eligible, manual_review_required, stale_after_date, limitations, snapshot_id, as_of_date, data_freshness_warning, notes.

**Membership allowlist:** membership_id, player_id, team_id, roster_status, source_type, source_name, source_url, source_retrieved_at, confidence, live_eligible, manual_review_required, stale_after_date, limitations, snapshot_id, as_of_date, data_freshness_warning, notes.

Forbidden fields (salary, contract, cap, injury, medical, rumor, scouting, live_status, availability, depth_chart, minutes, role_projection, trade_eligibility, starter, headshot, social_media, agent, mutation verbs, current/latest naming) are never assigned in the normalizer and are explicitly excluded from the allowlists.

## 6. Roster Status Mapping

| Provider raw value | Normalized |
|---|---|
| `standard`, `active`, `full`, `signed`, `regular` | `standard` |
| `two-way`, `two_way`, `twoway`, `two-way-contract` | `two_way` |
| Anything else (empty, `unknown`, `inactive`, `injured`, custom strings) | **Fail closed** (`UnknownRosterStatusError`) |

The normalizer **never defaults unknown status to `standard`**. Any unmappable status aborts the entire normalization. This is the fail-closed behavior required by F6-A.

## 7. Player ID Collision Guard

- Base slug: `nba-{first}-{last}` (lowercased, non-alnum collapsed to dashes)
- If a collision is detected, a numeric disambiguator is appended: `nba-{first}-{last}-2`, `nba-{first}-{last}-3`, etc.
- If a collision persists after disambiguation, `PlayerIdCollisionError` is raised.
- Membership IDs are derived as `membership-{team3lower}-{player-slug-without-nba-prefix}` and are also checked for duplicates.

## 8. Fake Provider Purpose

`FakeRosterProvider` exists solely to test the skeleton offline. It returns three fake teams:

| Team | Players | Scenario |
|---|---|---|
| `nba-FAK` | Test Alpha (standard, with forbidden extra_fields), Test Beta (two_way) | Normal path + forbidden field leakage |
| `nba-FB2` | Test Gamma (unknown_status) | Unknown roster_status fail-closed |
| `nba-FC3` | Test Alpha (standard, same name as FAK player) | Name collision / disambiguation |

Fake provider data is **not real NBA data**. It uses synthetic player names ("Test Alpha/Beta/Gamma") and is never written to disk. It must not be presented as current/live roster data.

## 9. Testing Evidence

### F6-B adapter tests:
```
46 passed
```

### Regression test results are documented in the final test run section of the handoff.

## 10. Why F6-C Is Still HOLD

F6-B provides the adapter skeleton with zero data landing. The next milestone, F6-C (Authorized Raw Snapshot Capture), is still **HOLD** because:

- No authorized API key exists in this environment.
- Without a key, the fetch script must fail closed (per F6-A design).
- Raw snapshot files must not be fabricated or scraped from unauthorized sources.

F6-C requires:
1. A valid `SPORTRADAR_NBA_API_KEY` (preferred) or `SPORTSDATAIO_NBA_API_KEY`
2. License review completed
3. Offline fetch script that reads key from env only (no CLI key passing, no .env)
4. Raw response files stored under `data/snapshots/nba_real_2026_preoffseason_v1/raw/authorized_roster_api/{provider}/{as_of_date}/`
5. No normalized landing until raw snapshot is reviewed

## 11. Next Step

**Immediate next: F6-C requires an authorized provider key.**

Until a key is acquired:
- F6-C (raw snapshot capture) remains HOLD.
- F6-D (30-team normalized roster) remains HOLD.
- Manual Batch 2 expansion remains PAUSED per F6-A decision matrix.

The F6-B skeleton is ready for future provider adapter implementations to plug into `RosterProvider` Protocol without any changes to the backend runtime.
