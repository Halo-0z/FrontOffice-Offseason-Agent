"""Tests for ``cap_sheet_service`` (M1).

These tests validate the deterministic cap sheet model and service. They
do NOT exercise M2 transaction legality logic; ``apply_signing_preview``
is a pure preview that does not decide whether a signing is legal.

Coverage:

1. ``SalaryCapConfig`` loads from ``data/cap_config.json``.
2. All 3 demo teams load as ``TeamCapSheet``.
3. ``total_salary`` is the sum of contract salaries.
4. ``cap_space == salary_cap - total_salary``.
5. ``luxury_tax`` / ``first_apron`` / ``second_apron`` distances are correct.
6. ``apply_signing_preview`` returns a new object and does not mutate input.
7. ``team_id`` not in ``teams.json`` raises ``TeamNotFoundError``.
8. Cap config numbers come from data, not from service-level hardcoding.
9. M0 smoke tests still pass (covered by ``test_m0_skeleton.py``).

Run:

    python -m pytest backend/app/tests/test_cap_sheet_service.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.models.cap import (
    CapSheetSummary,
    PlayerContract,
    SalaryCapConfig,
    TeamCapSheet,
)
from backend.app.services import cap_sheet_service as svc
from backend.app.services.cap_sheet_service import (
    CapConfigMissingError,
    CapSheetError,
    TeamNotFoundError,
    apply_signing_preview,
    load_cap_config,
    load_contracts,
    load_team_cap_sheet,
    summarize_cap_sheet,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


# --------------------------------------------------------------------------- #
# 1. SalaryCapConfig loads
# --------------------------------------------------------------------------- #


def test_load_cap_config_returns_expected_fields() -> None:
    cfg = load_cap_config(DATA_DIR)
    assert isinstance(cfg, SalaryCapConfig)
    assert cfg.season == "2025-2026"
    # Sanity: all monetary fields are positive integers.
    for field_name in (
        "salary_cap",
        "luxury_tax",
        "first_apron",
        "second_apron",
        "minimum_salary",
        "mid_level_exception",
    ):
        value = getattr(cfg, field_name)
        assert isinstance(value, int)
        assert value > 0, f"{field_name} should be positive"
    # Ordering invariants a real CBA would also enforce.
    assert cfg.salary_cap < cfg.luxury_tax < cfg.first_apron < cfg.second_apron
    assert cfg.roster_min < cfg.roster_max


# --------------------------------------------------------------------------- #
# 2. All 3 demo teams load
# --------------------------------------------------------------------------- #


def test_load_team_cap_sheet_for_all_demo_teams() -> None:
    team_ids = sorted(svc.iter_team_ids(DATA_DIR))
    assert team_ids == ["DEM-ATL", "DEM-CHI", "DEM-PDX"]
    for team_id in team_ids:
        sheet = load_team_cap_sheet(team_id, DATA_DIR)
        assert isinstance(sheet, TeamCapSheet)
        assert sheet.team_id == team_id
        assert sheet.season == "2025-2026"
        # Each demo team has at least 3 contracts (M1 data requirement).
        assert len(sheet.contracts) >= 3, (
            f"{team_id} should have >= 3 contracts, got {len(sheet.contracts)}"
        )
        # Every contract on the sheet belongs to that team.
        assert all(c.team_id == team_id for c in sheet.contracts)


# --------------------------------------------------------------------------- #
# 3. total_salary is correct
# --------------------------------------------------------------------------- #


def test_total_salary_is_sum_of_contract_salaries() -> None:
    sheet = load_team_cap_sheet("DEM-ATL", DATA_DIR)
    expected_total = sum(c.salary for c in sheet.contracts)
    summary = summarize_cap_sheet(sheet)
    assert summary.total_salary == expected_total
    # Sanity check on a known demo figure: ATL has 28M + 22M + 18M + 6M = 74M.
    assert expected_total == 74_000_000


# --------------------------------------------------------------------------- #
# 4. cap_space == salary_cap - total_salary
# --------------------------------------------------------------------------- #


def test_cap_space_equals_salary_cap_minus_total_salary() -> None:
    for team_id in svc.iter_team_ids(DATA_DIR):
        sheet = load_team_cap_sheet(team_id, DATA_DIR)
        summary = summarize_cap_sheet(sheet)
        assert summary.cap_space == sheet.cap_config.salary_cap - summary.total_salary
        assert summary.roster_count == len(sheet.contracts)


# --------------------------------------------------------------------------- #
# 5. apron / tax distances are correct
# --------------------------------------------------------------------------- #


def test_apron_and_tax_distances_are_correct() -> None:
    sheet = load_team_cap_sheet("DEM-ATL", DATA_DIR)
    summary = summarize_cap_sheet(sheet)
    cfg = sheet.cap_config
    assert summary.tax_distance == cfg.luxury_tax - summary.total_salary
    assert summary.first_apron_distance == cfg.first_apron - summary.total_salary
    assert summary.second_apron_distance == cfg.second_apron - summary.total_salary
    # ATL total = 74M, so all distances should be positive (team is under).
    assert summary.tax_distance > 0
    assert summary.first_apron_distance > 0
    assert summary.second_apron_distance > 0
    # And the ordering should match the cap config ordering.
    assert (
        summary.cap_space < summary.tax_distance < summary.first_apron_distance
        < summary.second_apron_distance
    )


# --------------------------------------------------------------------------- #
# 6. apply_signing_preview is pure
# --------------------------------------------------------------------------- #


def test_apply_signing_preview_returns_new_object_and_does_not_mutate_input() -> None:
    sheet = load_team_cap_sheet("DEM-ATL", DATA_DIR)
    original_contracts = sheet.contracts
    original_count = len(sheet.contracts)

    new_contract = PlayerContract(
        contract_id="ct-preview-001",
        player_id="pl-preview-001",
        team_id="DEM-ATL",
        salary=10_000_000,
        years_remaining=2,
        guaranteed=True,
        sample_data=True,
    )
    previewed = apply_signing_preview(sheet, new_contract)

    # New object, not the same instance.
    assert previewed is not sheet
    # Input sheet is unchanged.
    assert sheet.contracts == original_contracts
    assert len(sheet.contracts) == original_count
    # Previewed sheet has the new contract appended.
    assert len(previewed.contracts) == original_count + 1
    assert previewed.contracts[-1] == new_contract
    # And the cap math reflects the new salary.
    before = summarize_cap_sheet(sheet)
    after = summarize_cap_sheet(previewed)
    assert after.total_salary == before.total_salary + 10_000_000
    assert after.cap_space == before.cap_space - 10_000_000


def test_apply_signing_preview_rejects_mismatched_team_id() -> None:
    sheet = load_team_cap_sheet("DEM-ATL", DATA_DIR)
    wrong_team_contract = PlayerContract(
        contract_id="ct-preview-002",
        player_id="pl-preview-002",
        team_id="DEM-PDX",  # different team
        salary=5_000_000,
        years_remaining=1,
        guaranteed=True,
        sample_data=True,
    )
    with pytest.raises(CapSheetError):
        apply_signing_preview(sheet, wrong_team_contract)


def test_team_cap_sheet_is_immutable() -> None:
    """Frozen dataclass: attribute assignment must raise."""
    sheet = load_team_cap_sheet("DEM-ATL", DATA_DIR)
    with pytest.raises(Exception):
        sheet.team_id = "DEM-CHI"  # type: ignore[misc]
    with pytest.raises(Exception):
        sheet.contracts = ()  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# 7. team_id not found raises TeamNotFoundError
# --------------------------------------------------------------------------- #


def test_load_team_cap_sheet_raises_for_unknown_team_id() -> None:
    with pytest.raises(TeamNotFoundError) as exc_info:
        load_team_cap_sheet("DOES-NOT-EXIST", DATA_DIR)
    msg = str(exc_info.value)
    assert "DOES-NOT-EXIST" in msg
    # Error message should mention known team ids to aid debugging.
    assert "DEM-ATL" in msg


# --------------------------------------------------------------------------- #
# 8. Cap config numbers come from data, not hardcoded
# --------------------------------------------------------------------------- #


def test_cap_config_numbers_match_data_file_not_hardcoded() -> None:
    cfg = load_cap_config(DATA_DIR)
    # Read the raw JSON and confirm the service did not substitute its own values.
    with (DATA_DIR / "cap_config.json").open(encoding="utf-8") as fh:
        raw = json.load(fh)["cap_config"]
    assert cfg.salary_cap == raw["salary_cap"]
    assert cfg.luxury_tax == raw["luxury_tax"]
    assert cfg.first_apron == raw["first_apron"]
    assert cfg.second_apron == raw["second_apron"]
    assert cfg.roster_min == raw["roster_min"]
    assert cfg.roster_max == raw["roster_max"]
    assert cfg.minimum_salary == raw["minimum_salary"]
    assert cfg.mid_level_exception == raw["mid_level_exception"]

    # If we mutate the data file in a tmp copy, the service must reflect it.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        # Copy all data files.
        for name in ("cap_config.json", "teams.json", "contracts.json"):
            (tmp_dir / name).write_text(
                (DATA_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
            )
        # Mutate cap_config.json with a clearly different salary_cap.
        modified = json.loads((tmp_dir / "cap_config.json").read_text(encoding="utf-8"))
        modified["cap_config"]["salary_cap"] = 99_999_999
        (tmp_dir / "cap_config.json").write_text(
            json.dumps(modified), encoding="utf-8"
        )
        cfg2 = load_cap_config(tmp_dir)
        assert cfg2.salary_cap == 99_999_999, (
            "service must read salary_cap from data, not hardcode it"
        )


def test_load_cap_config_raises_when_missing_or_malformed() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        # No cap_config.json at all.
        with pytest.raises(CapConfigMissingError):
            load_cap_config(tmp_dir)
        # Malformed: missing required field.
        (tmp_dir / "cap_config.json").write_text(
            json.dumps({"cap_config": {"season": "x"}}), encoding="utf-8"
        )
        with pytest.raises(CapConfigMissingError):
            load_cap_config(tmp_dir)


# --------------------------------------------------------------------------- #
# Bonus: load_contracts sanity
# --------------------------------------------------------------------------- #


def test_load_contracts_returns_all_demo_contracts() -> None:
    contracts = load_contracts(DATA_DIR)
    assert len(contracts) >= 12  # 12 demo contracts
    assert all(isinstance(c, PlayerContract) for c in contracts)
    # At least 3 distinct teams represented.
    teams = {c.team_id for c in contracts}
    assert teams == {"DEM-ATL", "DEM-PDX", "DEM-CHI"}


def test_summary_is_deterministic_across_calls() -> None:
    sheet = load_team_cap_sheet("DEM-PDX", DATA_DIR)
    s1 = summarize_cap_sheet(sheet)
    s2 = summarize_cap_sheet(sheet)
    assert s1 == s2
    assert isinstance(s1, CapSheetSummary)


# --------------------------------------------------------------------------- #
# 10. Default data_dir resolves to <repo_root>/data regardless of cwd
# --------------------------------------------------------------------------- #


def test_default_data_dir_works_from_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """``load_cap_config()`` with no args must find ``data/cap_config.json``
    when the cwd is the repo root."""
    monkeypatch.chdir(REPO_ROOT)
    cfg = load_cap_config()  # no data_dir arg
    assert cfg.salary_cap == 140_000_000
    sheet = load_team_cap_sheet("DEM-ATL")  # no data_dir arg
    summary = summarize_cap_sheet(sheet)
    assert summary.total_salary == 74_000_000


def test_default_data_dir_does_not_resolve_to_drive_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If cwd is ``D:\\`` (or any drive root), the default ``data`` dir must
    NOT resolve to ``D:\\data``. It must resolve to ``<repo_root>/data``."""
    drive_root = Path(REPO_ROOT.anchor)  # e.g. "D:\\"
    if not drive_root.exists():
        pytest.skip("drive root not available on this platform")
    monkeypatch.chdir(drive_root)
    cfg = load_cap_config()  # no data_dir arg
    assert cfg.salary_cap == 140_000_000
    # And the internal resolver must point at the repo, not the drive root.
    from backend.app.services.cap_sheet_service import _resolve_data_dir, _find_repo_root

    resolved = _resolve_data_dir("data")
    assert resolved == (REPO_ROOT / "data").resolve()
    assert resolved != (drive_root / "data").resolve()
    assert _find_repo_root() == REPO_ROOT.resolve()


def test_default_data_dir_works_from_arbitrary_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Default ``data`` dir must resolve to repo root/data from any cwd."""
    monkeypatch.chdir(tmp_path)
    cfg = load_cap_config()  # no data_dir arg
    assert cfg.season == "2025-2026"


# --------------------------------------------------------------------------- #
# 11. Absolute tmp_path still supported
# --------------------------------------------------------------------------- #


def test_load_cap_config_accepts_absolute_tmp_path(tmp_path: Path) -> None:
    """An absolute ``data_dir`` (e.g. pytest ``tmp_path``) must be used as-is."""
    import json as _json

    cfg_file = tmp_path / "cap_config.json"
    cfg_file.write_text(
        _json.dumps(
            {
                "cap_config": {
                    "season": "2099-2099",
                    "salary_cap": 1,
                    "luxury_tax": 2,
                    "first_apron": 3,
                    "second_apron": 4,
                    "roster_min": 1,
                    "roster_max": 2,
                    "minimum_salary": 1,
                    "mid_level_exception": 1,
                }
            }
        ),
        encoding="utf-8",
    )
    cfg = load_cap_config(data_dir=tmp_path)
    assert cfg.season == "2099-2099"
    assert cfg.salary_cap == 1


# --------------------------------------------------------------------------- #
# 12. Cross-import-path: importing as ``app.services.cap_sheet_service``
#     from the backend cwd must work (subprocess isolation).
# --------------------------------------------------------------------------- #


def test_service_importable_as_app_services_from_backend_cwd() -> None:
    """Running ``python -c "from app.services.cap_sheet_service import ..."``
    with cwd=backend must succeed and read repo-root data.

    This validates that the service uses package-relative imports and
    that the default data_dir resolver anchors at the repo root, not at
    the cwd.
    """
    import subprocess
    import sys

    backend_dir = REPO_ROOT / "backend"
    code = (
        "from app.services.cap_sheet_service import "
        "load_cap_config, load_team_cap_sheet, summarize_cap_sheet; "
        "c = load_cap_config(); "
        "s = summarize_cap_sheet(load_team_cap_sheet('DEM-ATL')); "
        "print(c.salary_cap); print(s.total_salary)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["140000000", "74000000"], (
        f"unexpected output: {lines!r}\nstderr={result.stderr}"
    )


def test_service_importable_as_backend_app_services_from_repo_root_cwd() -> None:
    """Running ``python -c "from backend.app.services.cap_sheet_service import ..."``
    with cwd=repo_root must succeed and read repo-root data."""
    import subprocess
    import sys

    code = (
        "from backend.app.services.cap_sheet_service import "
        "load_cap_config, load_team_cap_sheet, summarize_cap_sheet; "
        "c = load_cap_config(); "
        "s = summarize_cap_sheet(load_team_cap_sheet('DEM-ATL')); "
        "print(c.salary_cap); print(s.total_salary)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"subprocess failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    assert lines == ["140000000", "74000000"], (
        f"unexpected output: {lines!r}\nstderr={result.stderr}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
