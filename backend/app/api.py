"""Minimal backend API layer for the Agent Console (M7-A).

This module exposes a small FastAPI app with deterministic, read-only
endpoints that wrap the existing backend services. It is the HTTP
bridge the frontend will call in M7-B (replacing the static payload
files). In M7-A only the backend API + tests are added; the frontend
keeps reading static payloads.

Endpoints:

- ``GET  /api/health``                       — liveness + sample_data flag
- ``POST /api/offseason/proposal-preview``   — wraps ``build_demo_payload``
- ``GET  /api/offseason/trade-preview-demo`` — wraps trade demo payload
- ``GET  /api/offseason/scenarios``          — lists supported demo modes
- ``POST /api/agent/orchestrate-preview``    — wraps the preview-only
  orchestrator stub (M8-E5-B)

Guardrails (same as the rest of the project):

- No LLM call. No MCP. No external NBA API. No network.
- No database. No writes to ``data/`` files.
- Every response keeps ``requires_human_approval=true`` and
  ``sample_data=true``.
- A PASS / RECOMMENDED status never approves a transaction.
- The API layer only orchestrates existing services; it does NOT
  re-implement business rules.

Run dev server (not required for tests):

    uvicorn backend.app.api:app --reload

Run tests:

    python -m pytest backend/app/tests/test_api_endpoints.py
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Repo-root / data-dir discovery
# --------------------------------------------------------------------------- #
# Walk up from this file to find a directory that contains both
# ``backend/`` and ``data/``. That is the repo root. We resolve it at
# import time so endpoints can pass a stable ``data_dir`` to the
# existing services.


def _find_repo_root() -> Path:
    """Walk up from this module to find the repo root."""
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "backend").is_dir() and (parent / "data").is_dir():
            return parent
    # Fallback: backend/app/api.py -> repo root is 3 levels up.
    return here.parents[3]


_REPO_ROOT = _find_repo_root()
_DATA_DIR = _REPO_ROOT / "data"


# --------------------------------------------------------------------------- #
# Request models
# --------------------------------------------------------------------------- #
# Pydantic models give us request validation for free. The field names
# match the existing ``OffseasonGoal`` dataclass so the mapping is
# trivial. ``target_positions`` accepts the 5 demo positions (PG/SG/SF/PF/C);
# anything else is rejected with a 422.


_VALID_POSITIONS = {"PG", "SG", "SF", "PF", "C"}


class ProposalPreviewRequest(BaseModel):
    """Request body for ``POST /api/offseason/proposal-preview``.

    Field names mirror ``OffseasonGoal`` so the API layer is a thin
    adapter. All fields are validated by Pydantic; position values are
    additionally checked against the demo position set.
    """

    team_id: str = Field(..., min_length=1, description="Demo team id, e.g. DEM-ATL.")
    objective: str = Field(..., min_length=1, description="Free-form objective string.")
    target_positions: List[str] = Field(
        default_factory=list,
        description="Position filter (PG/SG/SF/PF/C). Empty = no filter.",
    )
    max_salary: Optional[int] = Field(
        default=None, ge=0, description="Max salary cap for FA candidates. None = no filter."
    )
    max_candidates: int = Field(
        default=2, ge=1, le=10, description="Max number of FA candidates to keep."
    )
    evidence_query: Optional[str] = Field(
        default=None, description="Free-text evidence search query."
    )


class AgentOrchestratePreviewRequest(BaseModel):
    """Request body for ``POST /api/agent/orchestrate-preview`` (M8-E5-B).

    Thin adapter over :class:`AgentOrchestratorRequest`. The API layer
    does NOT re-implement intent routing, signing/trade logic, or salary
    validation — it delegates entirely to
    ``backend.app.services.agent_orchestrator.orchestrate_preview()``.

    ``metadata`` is recursively scanned for forbidden mutation-semantic
    keys (execute, apply, commit, mutate, write, persist, etc.); any
    occurrence results in HTTP 400.
    """

    intent: str = Field(
        ...,
        min_length=1,
        description="Allowlisted intent: signing_preview | trade_preview_demo | hold.",
    )
    team_id: Optional[str] = Field(
        default=None, description="Team id for signing_preview runs."
    )
    locale: Optional[str] = Field(default=None, description="Locale hint (reserved).")
    objective: Optional[str] = Field(
        default=None, description="Objective string for signing_preview."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional caller metadata. Forbidden keys cause HTTP 400.",
    )


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #


app = FastAPI(
    title="FrontOffice-Offseason-Agent API",
    description=(
        "Minimal deterministic backend API for the offseason Agent "
        "Console. Sample/simulation data only. No LLM, no MCP, no "
        "external NBA API. Every response is a preview that requires "
        "human approval."
    ),
    version="0.7.0",
)


# --------------------------------------------------------------------------- #
# CORS (M7-B)
# --------------------------------------------------------------------------- #
# The Next.js dev server runs on localhost:3000 while the FastAPI dev
# server runs on localhost:8000, so browser fetches are cross-origin.
# We allow only the two local dev origins — never "*" — so the API
# stays reachable for local development without opening it up to any
# origin. This is middleware only; it does not change any business
# logic or endpoint behavior.

_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)


@app.get("/api/health")
def health() -> Dict[str, Any]:
    """Liveness probe + data source metadata.

    Returns a small deterministic JSON object. The legacy fields
    (``status``, ``sample_data``, ``service``) are always present and
    unchanged. M8-C1/C2 adds additive data-source metadata
    (``data_mode``, ``active_data_source``, ``snapshot_id``, etc.) so
    the frontend / ops can see whether the backend is running in demo
    mode or snapshot mode.

    In default demo mode (no env vars set), the response is::

        {
            "status": "ok",
            "sample_data": true,
            "service": "frontoffice-offseason-agent",
            "data_mode": "demo",
            "active_data_source": "demo",
            "snapshot_id": null,
            "snapshot_valid": null,
            "snapshot_is_fixture": null,
            "snapshot_type": null,
            "snapshot_warnings": [],
            "fallback_reason": null,
            "strict_snapshot": false
        }
    """
    # Lazy import so importing this module does not pull in the
    # snapshot loader graph at import time.
    from backend.app.services.data_source_resolver import (
        build_data_source_metadata,
    )

    base = {
        "status": "ok",
        "sample_data": True,
        "service": "frontoffice-offseason-agent",
    }
    # ``build_data_source_metadata`` may flip ``sample_data`` to False
    # when a real snapshot is active, and may flip ``status`` to
    # ``degraded`` in strict-snapshot failure mode. We merge the
    # metadata on top of the base so the additive fields are always
    # present, and the base fields are overridden only when the
    # resolver has a more accurate value.
    metadata = build_data_source_metadata()
    active_status = metadata.get("fallback_reason")
    # When the resolver reports a degraded state (strict snapshot
    # failure), surface it in the top-level ``status``.
    if metadata.get("data_mode") == "snapshot" and active_status is not None:
        base["status"] = "degraded"
    # When a real snapshot is active, sample_data is False.
    if metadata.get("data_mode") == "snapshot" and active_status is None:
        base["sample_data"] = False
    base.update(metadata)
    return base


@app.get("/api/offseason/scenarios")
def list_scenarios() -> Dict[str, Any]:
    """List the demo scenarios the API supports.

    This is a static descriptor the frontend can use to render mode
    cards. It does not call any backend service.
    """
    return {
        "sample_data": True,
        "scenarios": [
            {
                "id": "signing_recommendation",
                "label": "Signing recommendation",
                "description": (
                    "$20M budget — preview a center signing that passes "
                    "rule checks."
                ),
                "endpoint": "/api/offseason/proposal-preview",
                "method": "POST",
                "example_request": {
                    "team_id": "DEM-ATL",
                    "objective": "Add frontcourt help",
                    "target_positions": ["C"],
                    "max_salary": 20000000,
                    "max_candidates": 2,
                    "evidence_query": "center need cap flexibility",
                },
            },
            {
                "id": "strict_budget_hold",
                "label": "Strict-budget hold",
                "description": (
                    "$15M budget — no FA fits, system returns HOLD."
                ),
                "endpoint": "/api/offseason/proposal-preview",
                "method": "POST",
                "example_request": {
                    "team_id": "DEM-ATL",
                    "objective": "Add frontcourt help",
                    "target_positions": ["C"],
                    "max_salary": 15000000,
                    "max_candidates": 2,
                    "evidence_query": "center need cap flexibility",
                },
            },
            {
                "id": "trade_preview_demo",
                "label": "Trade preview demo",
                "description": (
                    "Fixed two-team trade preview (DEM-ATL <-> DEM-PDX). "
                    "Returns salary matching, roster impact, depth chart."
                ),
                "endpoint": "/api/offseason/trade-preview-demo",
                "method": "GET",
                "example_request": None,
            },
        ],
    }


@app.post("/api/offseason/proposal-preview")
def proposal_preview(req: ProposalPreviewRequest) -> Dict[str, Any]:
    """Generate an offseason proposal preview.

    Wraps the existing deterministic pipeline
    (``run_goal_and_build_proposal`` -> ``evaluate_structured_proposal``
    -> ``build_demo_payload``). The response schema matches the CLI
    ``run_offseason_demo.py --format json`` output so M7-B can swap the
    static payload for this endpoint without frontend reshaping.

    - ``max_salary=20000000`` -> RECOMMENDED + SIGNING
    - ``max_salary=15000000`` -> NO_ACTION + HOLD
    - ``requires_human_approval`` is always ``true``.
    - ``sample_data`` is always ``true``.
    - Unknown ``team_id`` -> 400.
    - Invalid position in ``target_positions`` -> 400.
    """
    # Validate positions up front so we return a clear 400 instead of
    # letting the backend service raise a opaque error.
    normalized_positions: List[str] = []
    for pos in req.target_positions:
        up = pos.strip().upper()
        if up not in _VALID_POSITIONS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"invalid target_position '{pos}'. "
                    f"Must be one of {sorted(_VALID_POSITIONS)}."
                ),
            )
        normalized_positions.append(up)

    # Lazy import so importing this module does not pull in the full
    # backend graph at import time (keeps FastAPI app construction cheap).
    from backend.app.models.agent import OffseasonGoal
    from backend.app.services.cap_sheet_service import TeamNotFoundError
    from backend.app.services.proposal_viewer import build_demo_payload

    goal = OffseasonGoal(
        team_id=req.team_id,
        objective=req.objective,
        target_positions=tuple(normalized_positions),
        max_salary=req.max_salary,
        max_candidates=req.max_candidates,
        evidence_query=req.evidence_query,
    )

    try:
        payload = build_demo_payload(goal, _DATA_DIR)
    except TeamNotFoundError as exc:
        raise HTTPException(status_code=400, detail=f"unknown team_id: {exc}") from exc
    except ValueError as exc:
        # Defensive: any value error from the backend surfaces as 400.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # M8-E2: attach an additive agent_trace to the payload. The trace
    # is a user-facing projection of the deterministic pipeline; it
    # does NOT change the recommendation, the validation verdict, or
    # the human-approval guardrail. It only adds a new top-level key.
    from backend.app.services.agent_trace_builder import (
        build_proposal_agent_trace,
    )

    payload["agent_trace"] = build_proposal_agent_trace(
        goal_team_id=req.team_id,
        goal_objective=req.objective,
        payload=payload,
    )
    return payload


@app.get("/api/offseason/trade-preview-demo")
def trade_preview_demo() -> Dict[str, Any]:
    """Return the fixed demo two-team trade preview.

    Returns the same deterministic payload as
    ``python backend/scripts/run_trade_preview_demo.py --format json``.
    The implementation reuses the script's
    ``build_trade_preview_payload`` so the API and CLI never drift.

    - ``transaction_id`` is ``tx-trade-demo-001``.
    - ``validation_result.status`` is ``PASS``.
    - ``requires_human_approval`` is always ``true``.
    - ``sample_data`` is always ``true``.
    - Does NOT approve, execute, or persist the trade.
    """
    # Import the CLI script's payload builder. The script lives under
    # backend/scripts and is importable as a module because pytest runs
    # with the repo root on sys.path (and the script itself inserts the
    # repo root into sys.path at import time).
    import sys

    scripts_dir = _REPO_ROOT / "backend" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from run_trade_preview_demo import build_trade_preview_payload  # type: ignore[import-not-found]

    payload = build_trade_preview_payload(_DATA_DIR)

    # M8-E2: attach an additive agent_trace to the trade payload. The
    # trace is a user-facing projection; it does NOT change the trade
    # assets, the salary-matching result, or the human-approval
    # guardrail. It only adds a new top-level key.
    from backend.app.services.agent_trace_builder import (
        build_trade_agent_trace,
    )

    payload["agent_trace"] = build_trade_agent_trace(payload)
    return payload


# --------------------------------------------------------------------------- #
# Metadata forbidden-key guard
# --------------------------------------------------------------------------- #


_METADATA_FORBIDDEN_KEYS = frozenset({
    "execute",
    "executed",
    "apply",
    "applied",
    "commit",
    "committed",
    "mutate",
    "mutated",
    "write",
    "persist",
    "approve_transaction",
    "execute_transaction",
    "execute_signing",
    "roster_update",
    "contract_update",
    "snapshot_write",
})

# Short root verbs that are forbidden regardless of naming convention
# (camelCase / snake_case). These are checked as substring tokens after
# splitting on underscores and camelCase boundaries.
_FORBIDDEN_ROOTS = frozenset({
    "execute", "executed", "apply", "applied",
    "commit", "committed", "mutate", "mutated",
    "write", "persist",
})


def _split_key_tokens(key: str) -> list[str]:
    """Split a key into tokens, handling both snake_case and camelCase.

    Examples:
        "execute_transaction" -> ["execute", "transaction"]
        "CommitTransaction"  -> ["commit", "transaction"]
        "EXECUTE"            -> ["execute"]
        "snapshot_write"     -> ["snapshot", "write"]
    """
    # Insert underscores before uppercase letters that follow a lowercase
    # letter or that are followed by a lowercase letter (handles "HTMLParser"
    # style sequences).
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", key)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return [t.lower() for t in s.replace("-", "_").split("_") if t]


def _find_forbidden_metadata_key(obj: Any, _path: str = "") -> Optional[str]:
    """Recursively scan a metadata object for forbidden keys.

    Returns the dotted path of the first forbidden key found, or ``None``
    if the metadata is clean. Lists and nested dicts are both traversed.

    Matching is case-insensitive and supports both snake_case and camelCase
    keys. A key is forbidden if:
    - Its lowercased form exactly matches a forbidden key; OR
    - After splitting on underscores, any token equals a forbidden root verb.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            key_lower = str(k).lower()
            path_here = f"{_path}.{k}" if _path else str(k)
            # Exact match against the full forbidden set
            if key_lower in _METADATA_FORBIDDEN_KEYS:
                return path_here
            # Token-based match for camelCase / compound names
            tokens = _split_key_tokens(str(k))
            for token in tokens:
                if token in _FORBIDDEN_ROOTS:
                    return path_here
            found = _find_forbidden_metadata_key(v, path_here)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found = _find_forbidden_metadata_key(v, f"{_path}[{i}]")
            if found is not None:
                return found
    return None


# --------------------------------------------------------------------------- #
# Agent orchestrator endpoint (M8-E5-B)
# --------------------------------------------------------------------------- #


@app.post("/api/agent/orchestrate-preview")
def agent_orchestrate_preview(req: AgentOrchestratePreviewRequest) -> Dict[str, Any]:
    """Preview-only agent orchestration endpoint (M8-E5-B).

    Thin HTTP adapter that:

    1. Recursively validates ``req.metadata`` has no forbidden
       mutation-semantic keys (returns 400 if any found).
    2. Builds an ``AgentOrchestratorRequest`` from the HTTP body.
    3. Delegates entirely to
       ``backend.app.services.agent_orchestrator.orchestrate_preview()``.
    4. Returns ``AgentOrchestratorResult.to_dict()`` directly — no
       reshaping, no verdict override, no re-validation, no extra keys.

    Hard guardrails (enforced by the service layer and by tests):

    - Only allowlisted intents (``signing_preview``,
      ``trade_preview_demo``, ``hold``) produce preview results;
      unsupported intents are blocked by the service (hold/blocked),
      never guessed.
    - ``requires_human_approval`` is always ``true`` in the response.
    - No execute/apply/commit/mutate/write/persist capability is
      exposed through this endpoint.
    - No data file is mutated.
    - Salary validation verdicts are not recomputed or overridden.
    """
    forbidden_path = _find_forbidden_metadata_key(req.metadata)
    if forbidden_path is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"metadata contains forbidden mutation-semantic key at "
                f"'{forbidden_path}'. This endpoint is preview-only and "
                f"does not support execute/apply/commit/mutate/write/persist."
            ),
        )

    from backend.app.models.agent_orchestrator import AgentOrchestratorRequest
    from backend.app.services.agent_orchestrator import orchestrate_preview

    orch_req = AgentOrchestratorRequest(
        intent=req.intent,
        team_id=req.team_id,
        locale=req.locale,
        objective=req.objective,
        metadata=dict(req.metadata),
    )

    result = orchestrate_preview(orch_req, _DATA_DIR)
    return result.to_dict()
