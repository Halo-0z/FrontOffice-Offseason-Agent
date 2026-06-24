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
    """Liveness probe.

    Returns a small deterministic JSON object. ``sample_data`` is
    always ``true`` — this API only serves demo/simulation data.
    """
    return {
        "status": "ok",
        "sample_data": True,
        "service": "frontoffice-offseason-agent",
    }


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

    return build_trade_preview_payload(_DATA_DIR)
