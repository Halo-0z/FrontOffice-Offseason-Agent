"""Tests for ``/api/health`` data-source metadata (M8-C1/C2).

Coverage:

1. default health preserves status/sample_data/service
2. default health has new data_mode etc. fields
3. snapshot valid fixture health metadata is correct
4. invalid snapshot non-strict health fallback is correct
5. invalid snapshot strict health degraded is correct
6. existing scenarios/proposal/trade endpoints still pass in demo mode

Run:

    python -m pytest backend/app/tests/test_api_health_datasource.py -v
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api import app
from backend.app.services.data_source_resolver import reset_resolver_cache

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "backend" / "app" / "tests" / "fixtures" / "snapshots"


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


@pytest.fixture()
def client() -> TestClient:
    """A TestClient for the FastAPI app."""
    return TestClient(app)


# --------------------------------------------------------------------------- #
# Tests: default demo health
# --------------------------------------------------------------------------- #


def test_default_health_preserves_legacy_fields(client: TestClient) -> None:
    """The legacy fields status/sample_data/service must be present."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["sample_data"] is True
    assert body["service"] == "frontoffice-offseason-agent"


def test_default_health_has_datasource_fields(client: TestClient) -> None:
    """The new additive data-source fields must be present in demo mode."""
    resp = client.get("/api/health")
    body = resp.json()
    assert body["data_mode"] == "demo"
    assert body["active_data_source"] == "demo"
    assert body["snapshot_id"] is None
    assert body["snapshot_valid"] is None
    assert body["snapshot_is_fixture"] is None
    assert body["snapshot_type"] is None
    assert body["snapshot_warnings"] == []
    assert body["fallback_reason"] is None
    assert body["strict_snapshot"] is False


# --------------------------------------------------------------------------- #
# Tests: snapshot valid fixture health
# --------------------------------------------------------------------------- #


def test_snapshot_valid_fixture_health_metadata(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When a valid snapshot fixture is active, health must reflect it."""
    _set_snapshot_env(monkeypatch, allow_fixture=True)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["sample_data"] is False
    assert body["data_mode"] == "snapshot"
    assert body["active_data_source"] == "snapshot:valid_m8b_small"
    assert body["snapshot_id"] == "valid_m8b_small"
    assert body["snapshot_valid"] is True
    assert body["snapshot_is_fixture"] is True
    assert body["snapshot_type"] == "test_fixture"
    assert body["fallback_reason"] is None


# --------------------------------------------------------------------------- #
# Tests: invalid snapshot non-strict (fallback)
# --------------------------------------------------------------------------- #


def test_invalid_snapshot_non_strict_health_fallback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid snapshot + non-strict -> health shows demo fallback."""
    _set_snapshot_env(
        monkeypatch,
        snapshot_id="invalid_bad_salary",
        allow_fixture=True,
        strict=False,
    )
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    # Fallback to demo.
    assert body["status"] == "ok"
    assert body["sample_data"] is True
    assert body["data_mode"] == "demo"
    assert body["active_data_source"] == "demo(fallback)"
    assert body["snapshot_id"] == "invalid_bad_salary"
    assert body["snapshot_valid"] is False
    assert body["fallback_reason"] is not None
    assert "failed validation" in body["fallback_reason"]


# --------------------------------------------------------------------------- #
# Tests: invalid snapshot strict (degraded)
# --------------------------------------------------------------------------- #


def test_invalid_snapshot_strict_health_degraded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invalid snapshot + strict -> health shows degraded."""
    _set_snapshot_env(
        monkeypatch,
        snapshot_id="invalid_bad_salary",
        allow_fixture=True,
        strict=True,
    )
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    # Degraded: status is degraded, data_mode is still snapshot.
    assert body["status"] == "degraded"
    assert body["data_mode"] == "snapshot"
    assert body["snapshot_id"] == "invalid_bad_salary"
    assert body["snapshot_valid"] is False
    assert body["fallback_reason"] is not None
    assert "failed validation" in body["fallback_reason"]


# --------------------------------------------------------------------------- #
# Tests: existing endpoints still work in demo mode
# --------------------------------------------------------------------------- #


def test_scenarios_endpoint_still_works_in_demo_mode(
    client: TestClient
) -> None:
    """The scenarios endpoint must still return the demo scenarios."""
    resp = client.get("/api/offseason/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_data"] is True
    assert len(body["scenarios"]) == 3


def test_proposal_preview_still_works_in_demo_mode(
    client: TestClient
) -> None:
    """The proposal-preview endpoint must still work in demo mode."""
    resp = client.post(
        "/api/offseason/proposal-preview",
        json={
            "team_id": "DEM-ATL",
            "objective": "Add frontcourt help",
            "target_positions": ["C"],
            "max_salary": 20000000,
            "max_candidates": 2,
            "evidence_query": "center need cap flexibility",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["proposal"]["status"] == "RECOMMENDED"
    assert body["sample_data"] is True


def test_trade_preview_demo_still_works_in_demo_mode(
    client: TestClient
) -> None:
    """The trade-preview-demo endpoint must still work in demo mode."""
    resp = client.get("/api/offseason/trade-preview-demo")
    assert resp.status_code == 200
    body = resp.json()
    assert body["trade_transaction"]["transaction_id"] == "tx-trade-demo-001"
    assert body["sample_data"] is True


# --------------------------------------------------------------------------- #
# Tests: snapshot mode does NOT break business endpoints
# --------------------------------------------------------------------------- #


def test_business_endpoints_still_work_in_snapshot_mode(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even when snapshot mode is active, the business endpoints must
    still return demo data (M8-C1/C2 does NOT wire snapshot into the
    business flow)."""
    _set_snapshot_env(monkeypatch, allow_fixture=True)
    # Health should show snapshot mode.
    health = client.get("/api/health").json()
    assert health["data_mode"] == "snapshot"
    # But proposal-preview still returns demo data.
    resp = client.post(
        "/api/offseason/proposal-preview",
        json={
            "team_id": "DEM-ATL",
            "objective": "Add frontcourt help",
            "target_positions": ["C"],
            "max_salary": 20000000,
            "max_candidates": 2,
            "evidence_query": "center need cap flexibility",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    # M8-C1/C2: business endpoints still use demo data.
    assert body["sample_data"] is True
    assert body["proposal"]["status"] == "RECOMMENDED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
