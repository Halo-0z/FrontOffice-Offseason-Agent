"""Normalizer: converts provider raw records to normalized candidate dicts.

M10-F6-B: Converts ProviderRosterSnapshot output into Python dicts/lists that
match the structure of player_identities.json and roster_memberships.json.
This module does NOT write files; it returns Python objects only. File I/O
and hash/source_manifest updates are F6-D concerns.

Key safety properties:
- Allowlist-only field output (see field_whitelist.py).
- Unknown roster_status causes hard error (fail closed), never silently defaulted.
- Duplicate player_id / membership_id detection with collision guard.
- Player-to-membership cross-reference integrity.
- birthdate/height/weight forced to null in F6-B (no real data).
- live_eligible forced to false; manual_review_required forced to true.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from tools.roster_ingestion.field_whitelist import (
    ALLOWED_MEMBERSHIP_FIELDS,
    ALLOWED_PLAYER_FIELDS,
    ALLOWED_ROSTER_STATUSES,
    FORBIDDEN_ROSTER_STATUS_DEFAULTS,
    detect_forbidden_fields,
)
from tools.roster_ingestion.models import (
    ForbiddenFieldLeakageError,
    MembershipIdCollisionError,
    PlayerIdCollisionError,
    PlayerXrefError,
    ProviderRosterSnapshot,
    RosterIngestionError,
    TeamNotInScopeError,
    UnknownRosterStatusError,
)


_POSITION_MAP: Dict[str, str] = {
    "G": "G",
    "GUARD": "G",
    "PG": "PG",
    "SG": "SG",
    "F": "F",
    "FORWARD": "F",
    "SF": "SF",
    "PF": "PF",
    "C": "C",
    "CENTER": "C",
    "F-C": "FC",
    "FC": "FC",
    "C-F": "FC",
    "CF": "FC",
    "G-F": "GF",
    "GF": "GF",
    "F-G": "GF",
    "FG": "GF",
}

_VALID_POSITIONS: Set[str] = {"PG", "SG", "SF", "PF", "C", "G", "F", "FC", "GF"}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(name: str) -> str:
    """Convert a player name to a stable slug: lowercase, non-alnum -> dash."""
    cleaned = _SLUG_RE.sub("-", name.lower().strip())
    cleaned = cleaned.strip("-")
    return cleaned


def _make_player_id(first_name: str, last_name: str, disambiguator: Optional[str] = None) -> str:
    """Generate a stable player_id slug.

    Format: nba-{first}-{last} with optional disambiguator suffix.
    """
    first_slug = _slugify(first_name)
    last_slug = _slugify(last_name)
    base = f"nba-{first_slug}-{last_slug}"
    if disambiguator:
        base = f"{base}-{_slugify(disambiguator)}"
    return base


def _make_membership_id(team_id: str, player_id: str) -> str:
    """Generate a stable membership_id from team and player slugs."""
    team_slug = team_id.replace("nba-", "").lower()
    player_slug = player_id.replace("nba-", "", 1)
    return f"membership-{team_slug}-{player_slug}"


def _map_position(raw: Optional[str]) -> Optional[str]:
    """Map provider position string to normalized position enum value.

    Returns None if position cannot be mapped (caller decides handling).
    """
    if raw is None:
        return None
    normalized = raw.strip().upper().replace(" ", "-")
    return _POSITION_MAP.get(normalized)


def _map_roster_status(raw_status: str) -> Optional[str]:
    """Map provider roster status to normalized roster_status.

    Returns:
        'standard', 'two_way', or None if the status cannot be safely mapped.
        Unknown statuses return None (caller must fail closed; never default).
    """
    if raw_status is None:
        return None
    s = raw_status.strip().lower()
    if not s:
        return None
    if s in FORBIDDEN_ROSTER_STATUS_DEFAULTS:
        return None
    if s in ("standard", "active", "active-standard", "full", "signed", "regular"):
        return "standard"
    if s in ("two_way", "two-way", "twoway", "two_way_contract", "two-way-contract"):
        return "two_way"
    return None


def _build_player_identity(
    player_id: str,
    first_name: str,
    last_name: str,
    display_name: str,
    position: Optional[str],
    source_name: str,
    source_url: Optional[str],
    source_type: str,
    as_of_date: str,
    source_retrieved_at: str,
    stale_after_date: str,
    snapshot_id: str,
    data_freshness_warning: str,
    limitations: List[str],
    confidence: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a normalized player identity record (allowlisted fields only)."""
    record: Dict[str, Any] = {
        "player_id": player_id,
        "display_name": display_name,
        "first_name": first_name,
        "last_name": last_name,
        "position": position if position in _VALID_POSITIONS else "G",
        "birthdate": None,
        "height": None,
        "weight": None,
        "source_name": source_name,
        "source_url": source_url,
        "source_type": source_type,
        "source_retrieved_at": source_retrieved_at,
        "as_of_date": as_of_date,
        "snapshot_id": snapshot_id,
        "manual_review_required": True,
        "live_eligible": False,
        "stale_after_date": stale_after_date,
        "data_freshness_warning": data_freshness_warning,
        "limitations": list(limitations),
    }
    if confidence is not None:
        record["confidence"] = confidence
    else:
        record["confidence"] = "provider_sourced_requires_manual_review"

    forbidden = detect_forbidden_fields(record, f"player '{player_id}'")
    if forbidden:
        raise ForbiddenFieldLeakageError(
            f"Forbidden fields in normalized player '{player_id}': {forbidden}"
        )

    extra = set(record.keys()) - ALLOWED_PLAYER_FIELDS
    if extra:
        raise ForbiddenFieldLeakageError(
            f"Non-allowlisted fields in normalized player '{player_id}': {sorted(extra)}"
        )

    return record


def _build_membership(
    membership_id: str,
    player_id: str,
    team_id: str,
    roster_status: str,
    source_name: str,
    source_url: Optional[str],
    source_type: str,
    as_of_date: str,
    source_retrieved_at: str,
    stale_after_date: str,
    snapshot_id: str,
    data_freshness_warning: str,
    limitations: List[str],
    confidence: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a normalized roster membership record (allowlisted fields only)."""
    record: Dict[str, Any] = {
        "membership_id": membership_id,
        "player_id": player_id,
        "team_id": team_id,
        "roster_status": roster_status,
        "source_name": source_name,
        "source_url": source_url,
        "source_type": source_type,
        "source_retrieved_at": source_retrieved_at,
        "as_of_date": as_of_date,
        "snapshot_id": snapshot_id,
        "manual_review_required": True,
        "live_eligible": False,
        "stale_after_date": stale_after_date,
        "data_freshness_warning": data_freshness_warning,
        "limitations": list(limitations),
    }
    if confidence is not None:
        record["confidence"] = confidence
    else:
        record["confidence"] = "provider_sourced_requires_manual_review"

    forbidden = detect_forbidden_fields(record, f"membership '{membership_id}'")
    if forbidden:
        raise ForbiddenFieldLeakageError(
            f"Forbidden fields in normalized membership '{membership_id}': {forbidden}"
        )

    extra = set(record.keys()) - ALLOWED_MEMBERSHIP_FIELDS
    if extra:
        raise ForbiddenFieldLeakageError(
            f"Non-allowlisted fields in normalized membership '{membership_id}': {sorted(extra)}"
        )

    return record


def normalize_snapshot(
    snapshot: ProviderRosterSnapshot,
    allowed_team_ids: Optional[Set[str]] = None,
    source_type: str = "manual_curated",
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Normalize a ProviderRosterSnapshot into (players_doc, memberships_doc).

    This function returns Python dicts only. It does NOT write to disk.
    F6-C/D will handle file output, hashing, and source_manifest updates.

    Args:
        snapshot: A ProviderRosterSnapshot from a provider adapter.
        allowed_team_ids: If provided, only these team_ids are accepted; teams
            not in this set raise TeamNotInScopeError. If None, all teams in
            the snapshot are accepted.
        source_type: The source_type value to stamp on normalized records.
            Must be one of the schema-allowed values. F6-B uses 'manual_curated'
            until schema adds 'authorized_api_snapshot'.

    Returns:
        (players_doc, memberships_doc) as Python dicts matching the structure
        of player_identities.json and roster_memberships.json respectively.

    Raises:
        UnknownRosterStatusError: A player has an unmappable roster_status_raw.
        PlayerIdCollisionError: Two players map to the same player_id.
        MembershipIdCollisionError: Two memberships map to the same membership_id.
        TeamNotInScopeError: A team is not in allowed_team_ids.
        ForbiddenFieldLeakageError: Normalized output would contain forbidden fields.
        PlayerXrefError: Internal xref failure (should not happen if code is correct).
    """
    meta = snapshot.metadata
    snapshot_id = "f6b_fixture_snapshot"
    warning = (
        f"Frozen as-of {meta.as_of_date} provider ingestion fixture only; "
        f"not current/live NBA data; do not use for trade/signing recommendations."
    )
    limitations = [
        "identity_only",
        "roster_membership_only",
        "not_live",
        "no_contract",
        "no_salary",
        "no_cap",
        "no_injury",
        "no_depth_chart",
    ]

    players: List[Dict[str, Any]] = []
    memberships: List[Dict[str, Any]] = []
    seen_player_ids: Set[str] = set()
    seen_membership_ids: Set[str] = set()
    slug_attempts: Dict[str, int] = {}

    for team_roster in snapshot.team_rosters:
        tid = team_roster.team_id

        if allowed_team_ids is not None and tid not in allowed_team_ids:
            raise TeamNotInScopeError(
                f"Team '{tid}' not in allowed scope set"
            )

        for prec in team_roster.players:
            mapped_status = _map_roster_status(prec.roster_status_raw)
            if mapped_status is None:
                raise UnknownRosterStatusError(
                    f"Cannot safely map roster_status_raw='{prec.roster_status_raw}' "
                    f"for player '{prec.display_name}' on {tid}. "
                    f"Fail closed: unknown status must HOLD for manual review."
                )
            if mapped_status not in ALLOWED_ROSTER_STATUSES:
                raise UnknownRosterStatusError(
                    f"Mapped status '{mapped_status}' for '{prec.display_name}' "
                    f"is not in allowed roster statuses {sorted(ALLOWED_ROSTER_STATUSES)}"
                )

            position = _map_position(prec.position)
            if position is None:
                position = "G"

            pid = _make_player_id(prec.first_name, prec.last_name)
            if pid in seen_player_ids:
                collision_key = f"{prec.first_name.lower()}:{prec.last_name.lower()}"
                attempt = slug_attempts.get(collision_key, 1) + 1
                slug_attempts[collision_key] = attempt
                pid = _make_player_id(prec.first_name, prec.last_name, disambiguator=str(attempt))
                if pid in seen_player_ids:
                    raise PlayerIdCollisionError(
                        f"Player_id collision for '{prec.display_name}': "
                        f"slug '{pid}' already exists after disambiguation"
                    )

            mid = _make_membership_id(tid, pid)
            if mid in seen_membership_ids:
                raise MembershipIdCollisionError(
                    f"Membership_id collision: '{mid}' already exists"
                )

            player_source_url = prec.extra_fields.get("source_url")
            player_record = _build_player_identity(
                player_id=pid,
                first_name=prec.first_name,
                last_name=prec.last_name,
                display_name=prec.display_name,
                position=position,
                source_name=f"{meta.provider_name} team roster API",
                source_url=player_source_url,
                source_type=source_type,
                as_of_date=meta.as_of_date,
                source_retrieved_at=meta.access_date,
                stale_after_date=meta.stale_after_date,
                snapshot_id=snapshot_id,
                data_freshness_warning=warning,
                limitations=limitations,
            )

            membership_record = _build_membership(
                membership_id=mid,
                player_id=pid,
                team_id=tid,
                roster_status=mapped_status,
                source_name=f"{meta.provider_name} team roster API",
                source_url=player_source_url,
                source_type=source_type,
                as_of_date=meta.as_of_date,
                source_retrieved_at=meta.access_date,
                stale_after_date=meta.stale_after_date,
                snapshot_id=snapshot_id,
                data_freshness_warning=warning,
                limitations=[
                    "membership_only",
                    "not_live",
                    "no_contract",
                    "no_salary",
                    "no_cap",
                    "no_injury",
                    "no_depth_chart",
                ],
            )

            seen_player_ids.add(pid)
            seen_membership_ids.add(mid)
            players.append(player_record)
            memberships.append(membership_record)

    for m in memberships:
        if m["player_id"] not in seen_player_ids:
            raise PlayerXrefError(
                f"Membership '{m['membership_id']}' references non-existent player_id "
                f"'{m['player_id']}'"
            )

    players_doc = {
        "schema_version": "m10-f6b-skeleton-v1",
        "snapshot_id": snapshot_id,
        "as_of_date": meta.as_of_date,
        "generated_at": f"{meta.access_date}T00:00:00Z",
        "source_name": f"{meta.provider_name} authorized roster API (offline fixture)",
        "source_url": meta.endpoint_docs_url,
        "source_type": source_type,
        "manual_review_required": True,
        "live_eligible": False,
        "stale_after_date": meta.stale_after_date,
        "data_freshness_warning": warning,
        "limitations": list(limitations),
        "players": players,
    }

    memberships_doc = {
        "schema_version": "m10-f6b-skeleton-v1",
        "snapshot_id": snapshot_id,
        "as_of_date": meta.as_of_date,
        "generated_at": f"{meta.access_date}T00:00:00Z",
        "source_name": f"{meta.provider_name} authorized roster API (offline fixture)",
        "source_url": meta.endpoint_docs_url,
        "source_type": source_type,
        "manual_review_required": True,
        "live_eligible": False,
        "stale_after_date": meta.stale_after_date,
        "data_freshness_warning": warning,
        "limitations": [
            "membership_only",
            "not_live",
            "no_contract",
            "no_salary",
            "no_cap",
            "no_injury",
            "no_depth_chart",
        ],
        "roster_memberships": memberships,
    }

    return players_doc, memberships_doc
