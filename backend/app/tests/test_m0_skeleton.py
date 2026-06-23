"""M0 skeleton smoke test.

This test only validates the M0 project skeleton. It does NOT exercise
any M1/M2/M3/M4 business logic. It checks:

- data JSON files exist and are non-empty
- README.md contains the simulation disclaimer
- key backend service files exist
- tests live under backend/app/tests, not backend/tests

Run:

    python -m pytest backend/app/tests/test_m0_skeleton.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Repo root is two levels up from this file:
# backend/app/tests/test_m0_skeleton.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
BACKEND_DIR = REPO_ROOT / "backend"


def _load_json(filename: str) -> dict:
    path = DATA_DIR / filename
    assert path.exists(), f"missing data file: {path}"
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_data_files_exist_and_non_empty() -> None:
    """Each data JSON file must exist and contain a non-empty core array/object."""
    required = [
        "teams.json",
        "players.json",
        "contracts.json",
        "free_agents.json",
        "evidence_notes.json",
    ]
    for name in required:
        data = _load_json(name)
        assert isinstance(data, dict), f"{name} must be a JSON object"
        assert data.get("sample_data") is True, (
            f"{name} must declare sample_data=true (demo/simulation only)"
        )

    # Core arrays must be non-empty.
    assert len(_load_json("teams.json")["teams"]) >= 3, "need >= 3 demo teams"
    assert len(_load_json("players.json")["players"]) >= 8, "need >= 8 demo players"
    assert len(_load_json("contracts.json")["contracts"]) >= 8, "need >= 8 demo contracts"
    assert len(_load_json("free_agents.json")["free_agents"]) >= 5, "need >= 5 demo free agents"
    assert (
        len(_load_json("evidence_notes.json")["evidence_notes"]) >= 5
    ), "need >= 5 demo evidence notes"


def test_readme_contains_simulation_disclaimer() -> None:
    readme = REPO_ROOT / "README.md"
    assert readme.exists(), "README.md missing"
    text = readme.read_text(encoding="utf-8")
    expected = "This is a simulation/planning tool, not a source of confirmed NBA transactions."
    assert expected in text, "README.md must contain the simulation disclaimer"


def test_key_backend_services_exist() -> None:
    rule_engine = BACKEND_DIR / "app" / "services" / "transaction_rule_engine.py"
    offseason_agent = BACKEND_DIR / "app" / "services" / "offseason_agent.py"
    assert rule_engine.exists(), f"missing {rule_engine}"
    assert offseason_agent.exists(), f"missing {offseason_agent}"


def test_tests_live_under_backend_app_tests() -> None:
    app_tests_dir = BACKEND_DIR / "app" / "tests"
    assert app_tests_dir.exists(), "backend/app/tests directory must exist"
    assert (app_tests_dir / "__init__.py").exists(), "backend/app/tests/__init__.py missing"


def test_old_backend_tests_directory_removed() -> None:
    legacy = BACKEND_DIR / "tests"
    assert not legacy.exists(), (
        "backend/tests must be removed; tests now live under backend/app/tests"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
