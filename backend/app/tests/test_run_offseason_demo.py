"""Tests for the CLI demo script ``run_offseason_demo.py`` (M5-A).

These tests verify that:

- The script runs successfully with default args (exit code 0).
- ``--format text`` output contains a recognizable proposal header.
- ``--format json`` output is valid JSON with the expected keys.
- ``--target-position C`` works.
- A strict-budget scenario outputs NO_ACTION or HOLD.
- An unknown team produces a non-zero exit code with a clear error.
- The script does not mutate any data file.
- The script does not call LLM / MCP.

Run tests:

    python -m pytest backend/app/tests/test_run_offseason_demo.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "run_offseason_demo.py"
PYTHON = sys.executable


def _run_script(*args: str) -> subprocess.CompletedProcess:
    """Run the CLI demo script with the given args and return the
    completed process."""
    cmd = [PYTHON, str(SCRIPT_PATH), *args]
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


# --------------------------------------------------------------------------- #
# Success path tests
# --------------------------------------------------------------------------- #


def test_script_default_run_succeeds() -> None:
    """The script must run successfully with default args (exit 0)."""
    result = _run_script()
    assert result.returncode == 0, (
        f"script failed: stdout={result.stdout!r}, stderr={result.stderr!r}"
    )
    assert len(result.stdout) > 0


def test_script_text_format_contains_header() -> None:
    """``--format text`` output must contain a recognizable proposal
    header (e.g. 'Structured Proposal' or 'FrontOffice-Offseason-Agent'
    or 'proposal status')."""
    result = _run_script("--format", "text")
    assert result.returncode == 0
    assert "FrontOffice-Offseason-Agent" in result.stdout
    assert "proposal status" in result.stdout.lower()
    assert "DEM-ATL" in result.stdout


def test_script_json_format_is_valid_json() -> None:
    """``--format json`` output must be valid JSON."""
    result = _run_script("--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)


def test_script_json_contains_expected_keys() -> None:
    """The JSON payload must contain proposal / evaluation / actions /
    evidence / tool_trace keys."""
    result = _run_script("--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "proposal" in payload
    assert "evaluation" in payload
    assert "actions" in payload
    assert "evidence" in payload
    assert "tool_trace" in payload
    # Proposal sub-structure.
    proposal = payload["proposal"]
    assert "team_id" in proposal
    assert "status" in proposal
    assert "recommended_actions" in proposal
    assert "risks" in proposal
    assert "evidence_refs" in proposal
    assert "tool_call_trace" in proposal
    # Evaluation sub-structure.
    evaluation = payload["evaluation"]
    assert "status" in evaluation
    assert "issues" in evaluation


def test_script_target_position_c_works() -> None:
    """``--target-position C`` must run successfully and produce a
    proposal with at least one action (RECOMMENDED)."""
    result = _run_script(
        "--target-position", "C",
        "--max-salary", "20000000",
        "--max-candidates", "2",
        "--format", "json",
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    proposal = payload["proposal"]
    assert proposal["team_id"] == "DEM-ATL"
    assert proposal["status"] == "RECOMMENDED"
    actions = payload["actions"]
    assert len(actions) > 0
    # The first action should be a SIGNING for a center.
    assert actions[0]["action_type"] == "SIGNING"
    assert actions[0]["position"] == "C"


def test_script_strict_budget_outputs_no_action_or_hold() -> None:
    """A strict-budget scenario (max_salary=15M) must output NO_ACTION
    or a HOLD action."""
    result = _run_script(
        "--target-position", "C",
        "--max-salary", "15000000",
        "--max-candidates", "2",
        "--format", "json",
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    proposal = payload["proposal"]
    # fa-005 (C, 18M) is filtered out at 15M, so we expect NO_ACTION.
    assert proposal["status"] in ("NO_ACTION", "PARTIAL")
    actions = payload["actions"]
    risks = proposal["risks"]
    has_hold = any(a["action_type"] == "HOLD" for a in actions)
    has_no_match_risk = any(r["code"] == "no_matching_candidate" for r in risks)
    assert has_hold or has_no_match_risk


def test_script_text_format_contains_human_approval_and_sample_data() -> None:
    """The text output must mention ``requires_human_approval`` and
    ``sample_data`` (the demo must not pretend to be a real prediction)."""
    result = _run_script("--format", "text")
    assert result.returncode == 0
    assert "requires_human_approval" in result.stdout
    assert "sample_data" in result.stdout
    assert "True" in result.stdout


def test_script_text_output_contains_limitations() -> None:
    """The text output must contain the MVP limitations (no LLM, no
    MCP, sample data, preview only)."""
    result = _run_script("--format", "text")
    assert result.returncode == 0
    assert "Limitations" in result.stdout
    assert "No LLM call" in result.stdout
    assert "No MCP" in result.stdout


# --------------------------------------------------------------------------- #
# Error path tests
# --------------------------------------------------------------------------- #


def test_script_unknown_team_returns_nonzero() -> None:
    """An unknown team_id must produce a non-zero exit code with a
    clear error message."""
    result = _run_script("--team-id", "UNKNOWN-TEAM-XYZ")
    assert result.returncode != 0
    assert "ERROR" in result.stderr or "ERROR" in result.stdout
    assert "UNKNOWN-TEAM-XYZ" in result.stderr or "UNKNOWN-TEAM-XYZ" in result.stdout


def test_script_unknown_team_mentions_known_teams() -> None:
    """The error message for an unknown team should mention the known
    team ids so the user knows what to use."""
    result = _run_script("--team-id", "UNKNOWN-TEAM-XYZ")
    assert result.returncode != 0
    combined = result.stderr + result.stdout
    assert "DEM-ATL" in combined


# --------------------------------------------------------------------------- #
# No-mutation tests
# --------------------------------------------------------------------------- #


def test_script_does_not_mutate_players_json() -> None:
    """Running the script must not mutate ``data/players.json``."""
    path = DATA_DIR / "players.json"
    before = path.read_bytes()
    _run_script()
    after = path.read_bytes()
    assert before == after


def test_script_does_not_mutate_contracts_json() -> None:
    """Running the script must not mutate ``data/contracts.json``."""
    path = DATA_DIR / "contracts.json"
    before = path.read_bytes()
    _run_script()
    after = path.read_bytes()
    assert before == after


def test_script_does_not_mutate_free_agents_json() -> None:
    """Running the script must not mutate ``data/free_agents.json``."""
    path = DATA_DIR / "free_agents.json"
    before = path.read_bytes()
    _run_script()
    after = path.read_bytes()
    assert before == after


def test_script_does_not_mutate_evidence_notes_json() -> None:
    """Running the script must not mutate ``data/evidence_notes.json``."""
    path = DATA_DIR / "evidence_notes.json"
    before = path.read_bytes()
    _run_script()
    after = path.read_bytes()
    assert before == after


# --------------------------------------------------------------------------- #
# Determinism tests
# --------------------------------------------------------------------------- #


def test_script_json_output_is_deterministic() -> None:
    """Two consecutive ``--format json`` runs must produce identical
    output."""
    r1 = _run_script("--format", "json")
    r2 = _run_script("--format", "json")
    assert r1.returncode == 0
    assert r2.returncode == 0
    assert r1.stdout == r2.stdout


def test_script_text_output_is_deterministic() -> None:
    """Two consecutive ``--format text`` runs must produce identical
    output."""
    r1 = _run_script("--format", "text")
    r2 = _run_script("--format", "text")
    assert r1.returncode == 0
    assert r2.returncode == 0
    assert r1.stdout == r2.stdout


# --------------------------------------------------------------------------- #
# No LLM / MCP tests
# --------------------------------------------------------------------------- #


def test_script_does_not_call_llm_or_mcp() -> None:
    """The script must not import or expose any LLM / MCP client. We
    verify by inspecting the script source for forbidden imports."""
    script_source = SCRIPT_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "import openai",
        "from openai",
        "import anthropic",
        "from anthropic",
        "import mcp",
        "from mcp",
    )
    for forbidden in forbidden_imports:
        assert forbidden not in script_source, (
            f"script must not contain {forbidden!r}"
        )


def test_script_does_not_use_network_calls() -> None:
    """The script must not make network calls. We verify by inspecting
    the source for forbidden network-related calls."""
    script_source = SCRIPT_PATH.read_text(encoding="utf-8")
    forbidden_calls = (
        "requests.get",
        "requests.post",
        "urllib.request",
        "http.client",
        "socket.connect",
    )
    for forbidden in forbidden_calls:
        assert forbidden not in script_source, (
            f"script must not contain {forbidden!r}"
        )
