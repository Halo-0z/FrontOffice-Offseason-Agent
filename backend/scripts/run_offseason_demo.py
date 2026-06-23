"""CLI demo script for FrontOffice-Offseason-Agent (M5-A).

This script is a **deterministic CLI demo**. It is NOT an MCP server,
NOT an MCP client, NOT an LLM agent, and NOT an OpenAI function-calling
harness. It does not call any LLM and does not touch the network.

It runs the full deterministic backend pipeline
(``run_goal_and_build_proposal`` -> ``evaluate_structured_proposal``)
for a demo ``OffseasonGoal`` and prints the result as a human-readable
text brief or a stable JSON payload. It does NOT write any output
file, does NOT approve transactions, and does NOT mutate any data
file.

Run from repo root:

    python backend/scripts/run_offseason_demo.py
    python backend/scripts/run_offseason_demo.py --target-position C --max-salary 20000000
    python backend/scripts/run_offseason_demo.py --format json
    python backend/scripts/run_offseason_demo.py --team-id DEM-ATL --objective "Add frontcourt help"

Exit codes:

- 0: demo ran successfully.
- 1: argument error or unknown team / runtime error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


# --------------------------------------------------------------------------- #
# Repo-root discovery
# --------------------------------------------------------------------------- #
# The script must be runnable from the repo root (and ideally from
# anywhere). We walk up from this file to find a directory that
# contains both ``backend/`` and ``data/`` — that is the repo root.
# We then insert it into ``sys.path`` so ``import backend.app...``
# works regardless of the current working directory.


def _find_repo_root() -> Path:
    """Walk up from this script to find the repo root.

    The repo root is the directory that contains both ``backend/`` and
    ``data/``. Falls back to the script's parents if not found.
    """
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "backend").is_dir() and (parent / "data").is_dir():
            return parent
    # Fallback: assume 3 levels up (backend/scripts/run_offseason_demo.py).
    return here.parents[2]


_REPO_ROOT = _find_repo_root()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_DATA_DIR = _REPO_ROOT / "data"


# --------------------------------------------------------------------------- #
# Default demo goal
# --------------------------------------------------------------------------- #

_DEFAULT_TEAM_ID = "DEM-ATL"
_DEFAULT_OBJECTIVE = "Add frontcourt help"
_DEFAULT_TARGET_POSITIONS: Tuple[str, ...] = ("C",)
_DEFAULT_MAX_SALARY = 20_000_000
_DEFAULT_MAX_CANDIDATES = 2
_DEFAULT_EVIDENCE_QUERY = "center need cap flexibility"


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #


def _parse_target_positions(raw: Optional[str]) -> Tuple[str, ...]:
    """Parse a comma-separated or repeated ``--target-position`` value.

    Accepts inputs like ``"C"`` or ``"C,PF"`` or ``"C, PF"``. Returns
    a tuple of uppercased position strings. Empty input returns an
    empty tuple (no filter).
    """
    if not raw:
        return ()
    parts = [p.strip().upper() for p in raw.split(",")]
    return tuple(p for p in parts if p)


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="run_offseason_demo.py",
        description=(
            "FrontOffice-Offseason-Agent deterministic CLI demo. "
            "Runs the full backend pipeline (proposal builder + "
            "evaluator) for a demo OffseasonGoal and prints the "
            "result as text or JSON. Sample data only — not a real "
            "NBA prediction."
        ),
    )
    parser.add_argument(
        "--team-id",
        default=_DEFAULT_TEAM_ID,
        help=f"Team id (default: {_DEFAULT_TEAM_ID}).",
    )
    parser.add_argument(
        "--objective",
        default=_DEFAULT_OBJECTIVE,
        help=f'Offseason objective string (default: "{_DEFAULT_OBJECTIVE}").',
    )
    parser.add_argument(
        "--target-position",
        default=None,
        help=(
            "Target position filter. Can be a single position (e.g. 'C') "
            "or comma-separated (e.g. 'C,PF'). May be repeated. "
            "Default: C."
        ),
    )
    parser.add_argument(
        "--max-salary",
        type=int,
        default=_DEFAULT_MAX_SALARY,
        help=f"Max salary cap for free-agent candidates (default: {_DEFAULT_MAX_SALARY}).",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=_DEFAULT_MAX_CANDIDATES,
        help=f"Max number of candidates to keep (default: {_DEFAULT_MAX_CANDIDATES}).",
    )
    parser.add_argument(
        "--evidence-query",
        default=_DEFAULT_EVIDENCE_QUERY,
        help=f'Evidence search query (default: "{_DEFAULT_EVIDENCE_QUERY}").',
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format: 'text' (default) or 'json'.",
    )
    return parser


def _collect_target_positions(
    args: argparse.Namespace,
) -> Tuple[str, ...]:
    """Collect target positions from ``--target-position``.

    The flag may be repeated (argparse stores the last value by
    default; we accept the last value and split on commas). If not
    provided, falls back to the default ``("C",)``.
    """
    raw = args.target_position
    if raw is None:
        return _DEFAULT_TARGET_POSITIONS
    return _parse_target_positions(raw)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint. Returns the exit code."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    # Lazily import the backend so argument errors don't trigger heavy
    # imports.
    try:
        from backend.app.models.agent import OffseasonGoal
        from backend.app.services.cap_sheet_service import (
            TeamNotFoundError,
        )
        from backend.app.services.proposal_viewer import (
            build_demo_brief,
            build_demo_payload,
        )
    except ImportError as exc:
        print(f"ERROR: failed to import backend modules: {exc}", file=sys.stderr)
        return 1

    target_positions = _collect_target_positions(args)

    goal = OffseasonGoal(
        team_id=args.team_id,
        objective=args.objective,
        target_positions=target_positions,
        max_salary=args.max_salary,
        max_candidates=args.max_candidates,
        evidence_query=args.evidence_query,
    )

    try:
        if args.format == "json":
            payload = build_demo_payload(goal, _DATA_DIR)
            print(json.dumps(payload, sort_keys=True, indent=2))
        else:
            brief = build_demo_brief(goal, _DATA_DIR)
            print(brief)
    except TeamNotFoundError as exc:
        print(f"ERROR: unknown team_id: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — surface any runtime error clearly
        print(f"ERROR: demo run failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
