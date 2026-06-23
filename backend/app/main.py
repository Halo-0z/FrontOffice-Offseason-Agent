"""Backend entrypoint for FrontOffice-Offseason-Agent.

M0 placeholder. A future milestone (M4/M5) will wire this up as a small
FastAPI (or similar) app exposing the offseason agent workflow to the
frontend. For now it only prints a banner so the module is importable.

Run (future):

    python -m backend.app.main
"""

from __future__ import annotations


def main() -> int:
    """M0 placeholder entrypoint. Does not start a server."""
    print("FrontOffice-Offseason-Agent backend (M0 skeleton).")
    print("No server, no LLM, no business logic yet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
