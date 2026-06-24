"""CLI script to validate a snapshot bundle (M8-B Core).

This script is a **deterministic CLI validator**. It is NOT an MCP
server, NOT an MCP client, NOT an LLM agent, and NOT an OpenAI
function-calling harness. It does not call any LLM and does not touch
the network.

It runs ``validate_snapshot`` on a snapshot bundle directory and
prints the result as JSON. It does NOT write any output file, does NOT
approve transactions, and does NOT mutate any data file.

Usage:

    python backend/scripts/validate_snapshot.py --path <snapshot_dir>
    python backend/scripts/validate_snapshot.py --snapshot-id <id> [--data-root <dir>]

Exit codes:

- 0: snapshot is valid (no fatal errors).
- 1: snapshot is invalid (one or more fatal errors) or a runtime error
  occurred.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence


# --------------------------------------------------------------------------- #
# Repo-root discovery (same pattern as run_offseason_demo.py)
# --------------------------------------------------------------------------- #


def _find_repo_root() -> Path:
    """Walk up from this script to find the repo root."""
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "backend").is_dir() and (parent / "data").is_dir():
            return parent
    return here.parents[2]


_REPO_ROOT = _find_repo_root()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate an M8-B snapshot bundle directory.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--path",
        type=Path,
        help="Direct path to the snapshot directory.",
    )
    group.add_argument(
        "--snapshot-id",
        type=str,
        help="Snapshot ID to resolve under --data-root.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Data root for snapshot resolution (default: data/snapshots).",
    )
    return parser


def _resolve_snapshot_dir(args: argparse.Namespace) -> Path:
    """Resolve the snapshot directory from CLI args."""
    if args.path is not None:
        return args.path.resolve()

    # --snapshot-id path
    from backend.app.services.snapshot_loader import resolve_snapshot_dir

    return resolve_snapshot_dir(args.snapshot_id, args.data_root)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    try:
        snapshot_dir = _resolve_snapshot_dir(args)
    except Exception as exc:
        print(json.dumps({"error": str(exc), "is_valid": False}, indent=2))
        return 1

    from backend.app.services.snapshot_validator import validate_snapshot

    result = validate_snapshot(snapshot_dir)

    output = {
        "snapshot_id": result.snapshot_id,
        "manifest_status": result.manifest_status,
        "is_valid": result.is_valid,
        "errors": list(result.errors),
        "warnings": list(result.warnings),
        "row_counts": dict(result.row_counts),
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))

    return 0 if result.is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
