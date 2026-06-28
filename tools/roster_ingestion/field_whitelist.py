"""Field allowlist (whitelist) for roster ingestion normalization.

M10-F6-B: The normalizer uses an explicit allowlist approach: only fields
listed in ALLOWED_PLAYER_FIELDS and ALLOWED_MEMBERSHIP_FIELDS can appear in
normalized output. Any field from the provider not on the allowlist is
dropped. This prevents forbidden fields (salary, contract, injury, depth,
etc.) from leaking through even if the provider adds them to responses.

Forbidden fields are documented for reference but the primary enforcement is
the allowlist — not a blocklist.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List


ALLOWED_PLAYER_FIELDS: FrozenSet[str] = frozenset({
    "player_id",
    "display_name",
    "first_name",
    "last_name",
    "position",
    "birthdate",
    "height",
    "weight",
    "source_type",
    "source_name",
    "source_url",
    "source_retrieved_at",
    "confidence",
    "live_eligible",
    "manual_review_required",
    "stale_after_date",
    "limitations",
    "snapshot_id",
    "as_of_date",
    "data_freshness_warning",
    "notes",
})

ALLOWED_MEMBERSHIP_FIELDS: FrozenSet[str] = frozenset({
    "membership_id",
    "player_id",
    "team_id",
    "roster_status",
    "source_type",
    "source_name",
    "source_url",
    "source_retrieved_at",
    "confidence",
    "live_eligible",
    "manual_review_required",
    "stale_after_date",
    "limitations",
    "snapshot_id",
    "as_of_date",
    "data_freshness_warning",
    "notes",
})

FORBIDDEN_PROVIDER_FIELDS: FrozenSet[str] = frozenset({
    "salary", "salaries", "contract", "contracts", "cap_hold",
    "guarantee", "guarantee_amount", "cap_sheet", "cap_sheets",
    "injury", "injuries", "injury_status", "medical", "medical_status",
    "health", "availability", "real_time_availability", "active_now",
    "rumor", "rumors", "scouting_opinion", "scouting_opinions",
    "live_status", "current_roster", "latest_roster", "latest_data",
    "live_data", "current_salaries", "real_time_data",
    "depth_chart", "projected_depth_chart", "minutes_projection",
    "minutes", "role_projection", "trade_eligibility",
    "starter", "bench_role", "rotation_role",
    "headshot", "headshot_url", "player_image", "photo_url",
    "social_media", "agent", "agent_representation",
    "execute", "apply", "commit", "mutate", "write", "persist",
    "save", "delete", "update", "submit", "auto_execute", "auto_approve",
})

ALLOWED_ROSTER_STATUSES: FrozenSet[str] = frozenset({
    "standard",
    "two_way",
})

FORBIDDEN_ROSTER_STATUS_DEFAULTS: FrozenSet[str] = frozenset({
    "unknown",
    "active",
    "inactive",
    "suspended",
    "injured",
    "waived",
    "traded",
    "free_agent",
    "",
    "n/a",
    "none",
})


def filter_player_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    """Return only allowlisted fields from a player record.

    Any field not in ALLOWED_PLAYER_FIELDS is dropped. This is the primary
    defense against forbidden field leakage.
    """
    return {k: v for k, v in record.items() if k in ALLOWED_PLAYER_FIELDS}


def filter_membership_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    """Return only allowlisted fields from a membership record."""
    return {k: v for k, v in record.items() if k in ALLOWED_MEMBERSHIP_FIELDS}


def detect_forbidden_fields(record: Dict[str, Any], label: str) -> List[str]:
    """Return list of forbidden field keys found in a record (for error reporting).

    This is a secondary check; the primary enforcement is filter_*_fields().
    """
    found: List[str] = []
    for k in record:
        kl = str(k).lower()
        if kl in FORBIDDEN_PROVIDER_FIELDS:
            found.append(k)
    return found
