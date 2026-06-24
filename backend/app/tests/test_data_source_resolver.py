"""Tests for ``data_source_resolver`` (M8-C1/C2).

Coverage:

1. env unset -> demo mode
2. DATA_MODE=demo -> demo mode
3. DATA_MODE invalid -> fallback demo + reason
4. DATA_MODE=snapshot no id non-strict -> fallback demo
5. DATA_MODE=snapshot no id strict -> degraded
6. DATA_MODE=snapshot valid fixture allow_fixture=true -> snapshot ok
7. DATA_MODE=snapshot valid fixture allow_fixture=false -> fallback/degraded
8. DATA_MODE=snapshot invalid fixture non-strict -> fallback demo
9. DATA_MODE=snapshot invalid fixture strict -> degraded
10. reset_resolver_cache works
11. build_data_source_metadata returns expected keys

Run:

    python -m pytest backend/app/tests/test_data_source_resolver.py -v
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.app.services.data_source_resolver import (
    ActiveDataSource,
    DataMode,
    DataModeConfig,
    DataSourceStatus,
    build_data_source_metadata,
    get_demo_data_dir,
    get_snapshot_bundle_if_loaded,
    reset_resolver_cache,
    resolve_active_data_source,
    resolve_data_mode_from_env,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "backend" / "app" / "tests" / "fixtures" / "snapshots"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _reset_cache_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the resolver cache + clear all data-source env vars before
    every test, so tests are fully isolated."""
    reset_resolver_cache()
    for var in (
        "DATA_MODE",
        "DATA_SNAPSHOT_ID",
        "DATA_ROOT",
        "STRICT_SNAPSHOT",
        "SNAPSHOT_ALLOW_TEST_FIXTURE",
    ):
        monkeypatch.delenv(var, raising=False)
    yield
    reset_resolver_cache()


def _set_snapshot_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    snapshot_id: str = "valid_m8b_small",
    strict: bool = False,
    allow_fixture: bool = True,
    data_root: Path = FIXTURES_DIR,
) -> None:
    """Helper to set the snapshot-mode env vars."""
    monkeypatch.setenv("DATA_MODE", "snapshot")
    monkeypatch.setenv("DATA_SNAPSHOT_ID", snapshot_id)
    monkeypatch.setenv("DATA_ROOT", str(data_root))
    monkeypatch.setenv("STRICT_SNAPSHOT", "true" if strict else "false")
    monkeypatch.setenv(
        "SNAPSHOT_ALLOW_TEST_FIXTURE", "true" if allow_fixture else "false"
    )


# --------------------------------------------------------------------------- #
# Tests: env parsing
# --------------------------------------------------------------------------- #


def test_env_unset_returns_demo_mode() -> None:
    """When no env vars are set, the resolver must return demo mode."""
    config = resolve_data_mode_from_env()
    assert config.requested_mode == DataMode.DEMO
    assert config.snapshot_id is None
    assert config.strict_snapshot is False
    assert config.allow_test_fixture is False
    assert config.env_fallback_reason is None


def test_data_mode_demo_returns_demo_mode() -> None:
    """DATA_MODE=demo must return demo mode."""
    os.environ["DATA_MODE"] = "demo"
    config = resolve_data_mode_from_env()
    assert config.requested_mode == DataMode.DEMO
    assert config.env_fallback_reason is None


def test_data_mode_invalid_returns_demo_with_fallback_reason() -> None:
    """An invalid DATA_MODE value must fall back to demo with a reason."""
    os.environ["DATA_MODE"] = "production"
    config = resolve_data_mode_from_env()
    assert config.requested_mode == DataMode.DEMO
    assert config.env_fallback_reason is not None
    assert "production" in config.env_fallback_reason


def test_data_mode_snapshot_parses_snapshot_id() -> None:
    """DATA_MODE=snapshot must parse the snapshot id."""
    os.environ["DATA_MODE"] = "snapshot"
    os.environ["DATA_SNAPSHOT_ID"] = "my_snap"
    config = resolve_data_mode_from_env()
    assert config.requested_mode == DataMode.SNAPSHOT
    assert config.snapshot_id == "my_snap"


def test_strict_snapshot_env_parses_true() -> None:
    """STRICT_SNAPSHOT=true must parse to True."""
    os.environ["STRICT_SNAPSHOT"] = "true"
    config = resolve_data_mode_from_env()
    assert config.strict_snapshot is True


def test_allow_test_fixture_env_parses_true() -> None:
    """SNAPSHOT_ALLOW_TEST_FIXTURE=true must parse to True."""
    os.environ["SNAPSHOT_ALLOW_TEST_FIXTURE"] = "true"
    config = resolve_data_mode_from_env()
    assert config.allow_test_fixture is True


# --------------------------------------------------------------------------- #
# Tests: resolve_active_data_source
# --------------------------------------------------------------------------- #


def test_env_unset_active_source_is_demo_ok() -> None:
    """No env -> demo mode, status ok, sample_data true."""
    active = resolve_active_data_source()
    assert active.data_mode == DataMode.DEMO
    assert active.status == DataSourceStatus.OK
    assert active.sample_data is True
    assert active.active_data_source == "demo"
    assert active.snapshot_id is None
    assert active.fallback_reason is None


def test_data_mode_demo_active_source_is_demo_ok() -> None:
    """DATA_MODE=demo -> demo mode, status ok."""
    os.environ["DATA_MODE"] = "demo"
    active = resolve_active_data_source()
    assert active.data_mode == DataMode.DEMO
    assert active.status == DataSourceStatus.OK
    assert active.fallback_reason is None


def test_data_mode_invalid_active_source_falls_back_to_demo() -> None:
    """Invalid DATA_MODE -> demo fallback with a reason."""
    os.environ["DATA_MODE"] = "production"
    active = resolve_active_data_source()
    assert active.data_mode == DataMode.DEMO
    assert active.status == DataSourceStatus.FALLBACK_DEMO
    assert active.fallback_reason is not None
    assert "production" in active.fallback_reason


def test_snapshot_no_id_non_strict_falls_back_to_demo() -> None:
    """DATA_MODE=snapshot + no id + non-strict -> demo fallback."""
    os.environ["DATA_MODE"] = "snapshot"
    os.environ["STRICT_SNAPSHOT"] = "false"
    active = resolve_active_data_source()
    assert active.data_mode == DataMode.DEMO
    assert active.status == DataSourceStatus.FALLBACK_DEMO
    assert active.fallback_reason is not None
    assert "DATA_SNAPSHOT_ID" in active.fallback_reason


def test_snapshot_no_id_strict_is_degraded() -> None:
    """DATA_MODE=snapshot + no id + strict -> degraded."""
    os.environ["DATA_MODE"] = "snapshot"
    os.environ["STRICT_SNAPSHOT"] = "true"
    active = resolve_active_data_source()
    assert active.data_mode == DataMode.SNAPSHOT
    assert active.status == DataSourceStatus.DEGRADED
    assert active.fallback_reason is not None


def test_snapshot_valid_fixture_allow_fixture_true_is_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DATA_MODE=snapshot + valid fixture + allow_fixture=true -> snapshot ok."""
    _set_snapshot_env(monkeypatch, allow_fixture=True)
    active = resolve_active_data_source()
    assert active.data_mode == DataMode.SNAPSHOT
    assert active.status == DataSourceStatus.OK
    assert active.sample_data is False
    assert active.snapshot_id == "valid_m8b_small"
    assert active.snapshot_valid is True
    assert active.snapshot_is_fixture is True
    assert active.snapshot_type == "test_fixture"
    assert active.fallback_reason is None
    assert active.active_data_source == "snapshot:valid_m8b_small"


def test_snapshot_valid_fixture_allow_fixture_false_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DATA_MODE=snapshot + valid fixture + allow_fixture=false -> fallback.

    A test_fixture must NOT be loaded when
    SNAPSHOT_ALLOW_TEST_FIXTURE=false.
    """
    _set_snapshot_env(monkeypatch, allow_fixture=False, strict=False)
    active = resolve_active_data_source()
    assert active.data_mode == DataMode.DEMO
    assert active.status == DataSourceStatus.FALLBACK_DEMO
    assert active.fallback_reason is not None
    assert "test_fixture" in active.fallback_reason


def test_snapshot_valid_fixture_allow_fixture_false_strict_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DATA_MODE=snapshot + valid fixture + allow_fixture=false + strict
    -> degraded (no fallback)."""
    _set_snapshot_env(monkeypatch, allow_fixture=False, strict=True)
    active = resolve_active_data_source()
    assert active.data_mode == DataMode.SNAPSHOT
    assert active.status == DataSourceStatus.DEGRADED
    assert active.fallback_reason is not None


def test_snapshot_invalid_fixture_non_strict_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DATA_MODE=snapshot + invalid fixture + non-strict -> demo fallback."""
    _set_snapshot_env(
        monkeypatch,
        snapshot_id="invalid_bad_salary",
        allow_fixture=True,
        strict=False,
    )
    active = resolve_active_data_source()
    assert active.data_mode == DataMode.DEMO
    assert active.status == DataSourceStatus.FALLBACK_DEMO
    assert active.snapshot_valid is False
    assert active.fallback_reason is not None
    assert "failed validation" in active.fallback_reason
    assert len(active.snapshot_errors) > 0


def test_snapshot_invalid_fixture_strict_is_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DATA_MODE=snapshot + invalid fixture + strict -> degraded."""
    _set_snapshot_env(
        monkeypatch,
        snapshot_id="invalid_bad_salary",
        allow_fixture=True,
        strict=True,
    )
    active = resolve_active_data_source()
    assert active.data_mode == DataMode.SNAPSHOT
    assert active.status == DataSourceStatus.DEGRADED
    assert active.snapshot_valid is False
    assert active.fallback_reason is not None
    assert len(active.snapshot_errors) > 0


# --------------------------------------------------------------------------- #
# Tests: caching
# --------------------------------------------------------------------------- #


def test_resolve_active_data_source_caches_result() -> None:
    """The second call must return the cached object (identity)."""
    first = resolve_active_data_source()
    second = resolve_active_data_source()
    assert first is second


def test_force_reload_re_resolves() -> None:
    """force_reload=True must re-resolve even when cached."""
    first = resolve_active_data_source()
    second = resolve_active_data_source(force_reload=True)
    # Different object instances (cache was bypassed).
    assert first is not second
    # But same logical values.
    assert first.data_mode == second.data_mode


def test_reset_resolver_cache_clears_cache() -> None:
    """reset_resolver_cache must clear the cache."""
    first = resolve_active_data_source()
    reset_resolver_cache()
    second = resolve_active_data_source()
    assert first is not second


# --------------------------------------------------------------------------- #
# Tests: metadata + accessors
# --------------------------------------------------------------------------- #


def test_build_data_source_metadata_returns_expected_keys() -> None:
    """build_data_source_metadata must return all expected keys."""
    metadata = build_data_source_metadata()
    expected_keys = {
        "data_mode",
        "active_data_source",
        "snapshot_id",
        "snapshot_valid",
        "snapshot_is_fixture",
        "snapshot_type",
        "snapshot_warnings",
        "fallback_reason",
        "strict_snapshot",
    }
    assert set(metadata.keys()) == expected_keys


def test_build_data_source_metadata_default_demo() -> None:
    """In default demo mode, metadata must have demo values."""
    metadata = build_data_source_metadata()
    assert metadata["data_mode"] == "demo"
    assert metadata["active_data_source"] == "demo"
    assert metadata["snapshot_id"] is None
    assert metadata["snapshot_valid"] is None
    assert metadata["snapshot_is_fixture"] is None
    assert metadata["snapshot_type"] is None
    assert metadata["snapshot_warnings"] == []
    assert metadata["fallback_reason"] is None
    assert metadata["strict_snapshot"] is False


def test_get_snapshot_bundle_if_loaded_returns_none_in_demo_mode() -> None:
    """In demo mode, no bundle is loaded."""
    resolve_active_data_source()
    assert get_snapshot_bundle_if_loaded() is None


def test_get_snapshot_bundle_if_loaded_returns_bundle_in_snapshot_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In snapshot mode with a valid fixture, the bundle is available."""
    _set_snapshot_env(monkeypatch, allow_fixture=True)
    resolve_active_data_source()
    bundle = get_snapshot_bundle_if_loaded()
    assert bundle is not None
    assert bundle.snapshot_id == "valid_m8b_small"


def test_get_demo_data_dir_returns_repo_data_dir() -> None:
    """get_demo_data_dir must return <repo_root>/data."""
    data_dir = get_demo_data_dir()
    assert data_dir.is_dir()
    assert (data_dir / "players.json").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
