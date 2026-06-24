"""Data source resolver (M8-C1/C2 Snapshot Mode Backend Wiring Foundation).

This module is the **single source of truth** for "what data source is
the backend currently using?". It reads environment variables, decides
whether the backend is in ``demo`` mode or ``snapshot`` mode, and —
when snapshot mode is requested — tries to load + validate a snapshot
bundle using the M8-B ``snapshot_loader`` / ``snapshot_validator``.

Important: this module is **additive only** in M8-C1/C2. It does NOT
wire snapshot data into ``proposal-preview`` / ``trade-preview-demo``
/ the agent orchestrator. Those integrations are deferred to M8-C3+.
The only consumer of this module right now is ``/api/health``, which
adds data-source metadata to its response.

Environment variables
---------------------

- ``DATA_MODE``: ``demo`` | ``snapshot``. Default ``demo``. An invalid
  value falls back to ``demo`` with a ``fallback_reason``.
- ``DATA_SNAPSHOT_ID``: snapshot id to load when ``DATA_MODE=snapshot``.
- ``DATA_ROOT``: snapshot root directory. Default
  ``<repo_root>/data/snapshots``. Tests typically point this at
  ``backend/app/tests/fixtures/snapshots``.
- ``STRICT_SNAPSHOT``: ``true`` | ``false``. Default ``false``. When
  ``true``, a snapshot failure does NOT fall back to demo — the
  resolver returns ``status=degraded`` instead.
- ``SNAPSHOT_ALLOW_TEST_FIXTURE``: ``true`` | ``false``. Default
  ``false``. When ``false``, a snapshot whose ``snapshot_type`` is
  ``test_fixture`` is rejected (cannot be used as "real" data).

Behavior matrix
---------------

| DATA_MODE  | snapshot_id | fixture | strict | allow_fixture | result                  |
|------------|-------------|---------|--------|---------------|-------------------------|
| unset/demo | n/a         | n/a     | n/a    | n/a           | demo, ok                |
| invalid    | n/a         | n/a     | n/a    | n/a           | demo, ok (fallback)     |
| snapshot   | missing     | n/a     | false  | n/a           | demo, ok (fallback)     |
| snapshot   | missing     | n/a     | true   | n/a           | snapshot, degraded      |
| snapshot   | valid       | yes     | n/a    | true          | snapshot, ok            |
| snapshot   | valid       | yes     | n/a    | false         | demo/degraded (reject)  |
| snapshot   | invalid     | n/a     | false  | n/a           | demo, ok (fallback)     |
| snapshot   | invalid     | n/a     | true   | n/a           | snapshot, degraded      |

Caching
-------

The resolver caches the ``ActiveDataSource`` after the first
``resolve_active_data_source()`` call so repeated ``/api/health``
requests don't re-read the snapshot from disk. Tests call
``reset_resolver_cache()`` (with ``monkeypatch``-ed env) to isolate
scenarios.

Milestone: M8-C1/C2 (Snapshot Mode Backend Wiring Foundation).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from backend.app.services.snapshot_loader import (
    SnapshotBundle,
    SnapshotError,
    SnapshotLoadError,
    SnapshotNotFoundError,
    SnapshotValidationError,
    load_snapshot,
)
from backend.app.services.snapshot_validator import (
    SnapshotValidationResult,
    validate_snapshot,
)


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class DataMode(str, Enum):
    """The data mode the backend is running in."""

    DEMO = "demo"
    SNAPSHOT = "snapshot"


class DataSourceStatus(str, Enum):
    """The health status of the active data source."""

    OK = "ok"
    FALLBACK_DEMO = "fallback_demo"
    DEGRADED = "degraded"


# --------------------------------------------------------------------------- #
# Config + result dataclasses
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DataModeConfig:
    """Parsed environment configuration for the data source.

    Attributes:
        requested_mode: What the env asked for (``demo`` / ``snapshot``).
            Invalid values are normalized to ``demo`` here; the
            ``fallback_reason`` on ``ActiveDataSource`` records why.
        snapshot_id: The snapshot id to load (``DATA_SNAPSHOT_ID``).
        data_root: The snapshot root directory (``DATA_ROOT``).
        strict_snapshot: Whether snapshot failures should NOT fall back
            to demo (``STRICT_SNAPSHOT``).
        allow_test_fixture: Whether ``snapshot_type=test_fixture`` is
            accepted (``SNAPSHOT_ALLOW_TEST_FIXTURE``).
        env_fallback_reason: When the env value was invalid, a short
            reason string. ``None`` when the env was valid or unset.
    """

    requested_mode: DataMode
    snapshot_id: Optional[str]
    data_root: Path
    strict_snapshot: bool
    allow_test_fixture: bool
    env_fallback_reason: Optional[str]


@dataclass(frozen=True)
class ActiveDataSource:
    """The resolved, currently-active data source.

    This is the cached result of ``resolve_active_data_source()``. It
    is consumed by ``/api/health`` and (in future milestones) by the
    business endpoints.

    Attributes:
        requested_mode: What the env asked for.
        data_mode: The effective data mode after resolution. When
            snapshot fails and we fall back, this is ``demo``.
        status: ``ok`` | ``fallback_demo`` | ``degraded``.
        sample_data: ``True`` when the active source is demo/sample
            data; ``False`` when a real snapshot is active.
        active_data_source: A short label, e.g. ``"demo"`` or
            ``"snapshot:valid_m8b_small"`` or ``"demo(fallback)"``.
        snapshot_id: The snapshot id, or ``None``.
        snapshot_valid: ``True`` / ``False`` when a snapshot was
            attempted; ``None`` when no snapshot was loaded.
        snapshot_is_fixture: ``True`` when the loaded snapshot is a
            test fixture; ``None`` when no snapshot was loaded.
        snapshot_type: The ``snapshot_type`` from the manifest, or
            ``None``.
        snapshot_warnings: Warnings from the snapshot validator.
        snapshot_errors: Errors from the snapshot validator (when the
            snapshot failed validation).
        fallback_reason: A short reason when the resolver fell back to
            demo or went degraded; ``None`` when everything is ok.
        strict_snapshot: Whether strict mode was on.
        data_root: The snapshot root directory.
    """

    requested_mode: DataMode
    data_mode: DataMode
    status: DataSourceStatus
    sample_data: bool
    active_data_source: str
    snapshot_id: Optional[str]
    snapshot_valid: Optional[bool]
    snapshot_is_fixture: Optional[bool]
    snapshot_type: Optional[str]
    snapshot_warnings: Tuple[str, ...] = field(default_factory=tuple)
    snapshot_errors: Tuple[str, ...] = field(default_factory=tuple)
    fallback_reason: Optional[str] = None
    strict_snapshot: bool = False
    data_root: Optional[Path] = None
    # The loaded bundle, if any. Private — callers should use the
    # metadata fields above, not poke at the bundle directly. Kept as
    # Any to avoid leaking the SnapshotBundle type into every consumer.
    _bundle: Optional[Any] = field(default=None, repr=False, compare=False)


# --------------------------------------------------------------------------- #
# Repo-root / default data dir
# --------------------------------------------------------------------------- #


def _find_repo_root() -> Path:
    """Walk up from this module to find the repo root."""
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "backend").is_dir() and (parent / "data").is_dir():
            return parent
    return here.parents[3]


_REPO_ROOT = _find_repo_root()


def get_demo_data_dir() -> Path:
    """Return the demo data directory (``<repo_root>/data``)."""
    return _REPO_ROOT / "data"


def _default_snapshot_root() -> Path:
    """Return the default snapshot root (``<repo_root>/data/snapshots``)."""
    return _REPO_ROOT / "data" / "snapshots"


# --------------------------------------------------------------------------- #
# Env parsing
# --------------------------------------------------------------------------- #


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _parse_bool(name: str, default: bool = False) -> bool:
    """Parse a boolean env var. Returns ``default`` when unset."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    val = raw.strip().lower()
    if val in _TRUE_VALUES:
        return True
    if val in _FALSE_VALUES:
        return False
    # Unrecognized value -> default (lenient).
    return default


def resolve_data_mode_from_env() -> DataModeConfig:
    """Parse the data-source env vars into a ``DataModeConfig``.

    This function does NOT do any IO. It only reads env vars and
    normalizes them. ``resolve_active_data_source()`` is the one that
    loads the snapshot (if requested).
    """
    raw_mode = os.environ.get("DATA_MODE", "").strip().lower()
    env_fallback_reason: Optional[str] = None

    if raw_mode == "" or raw_mode == DataMode.DEMO.value:
        requested_mode = DataMode.DEMO
    elif raw_mode == DataMode.SNAPSHOT.value:
        requested_mode = DataMode.SNAPSHOT
    else:
        # Invalid value -> demo fallback.
        requested_mode = DataMode.DEMO
        env_fallback_reason = (
            f"DATA_MODE='{raw_mode}' is invalid; expected 'demo' or "
            f"'snapshot'. Falling back to demo."
        )

    snapshot_id = os.environ.get("DATA_SNAPSHOT_ID") or None
    if snapshot_id is not None:
        snapshot_id = snapshot_id.strip() or None

    data_root_raw = os.environ.get("DATA_ROOT")
    if data_root_raw:
        data_root = Path(data_root_raw)
    else:
        data_root = _default_snapshot_root()

    strict_snapshot = _parse_bool("STRICT_SNAPSHOT", default=False)
    allow_test_fixture = _parse_bool(
        "SNAPSHOT_ALLOW_TEST_FIXTURE", default=False
    )

    return DataModeConfig(
        requested_mode=requested_mode,
        snapshot_id=snapshot_id,
        data_root=data_root,
        strict_snapshot=strict_snapshot,
        allow_test_fixture=allow_test_fixture,
        env_fallback_reason=env_fallback_reason,
    )


# --------------------------------------------------------------------------- #
# Active data source resolution (with cache)
# --------------------------------------------------------------------------- #

_CACHE: Optional[ActiveDataSource] = None


def reset_resolver_cache() -> None:
    """Clear the cached ``ActiveDataSource``.

    Intended for tests that ``monkeypatch`` env vars and need a fresh
    resolution. Not meant to be called in production.
    """
    global _CACHE
    _CACHE = None


def _build_demo_active(
    config: DataModeConfig,
    fallback_reason: Optional[str] = None,
    snapshot_id: Optional[str] = None,
    snapshot_valid: Optional[bool] = None,
    snapshot_errors: Optional[Tuple[str, ...]] = None,
    snapshot_warnings: Optional[Tuple[str, ...]] = None,
) -> ActiveDataSource:
    """Build an ``ActiveDataSource`` for demo mode (possibly a fallback)."""
    if fallback_reason is not None:
        status = DataSourceStatus.FALLBACK_DEMO
        active_label = "demo(fallback)"
    else:
        status = DataSourceStatus.OK
        active_label = "demo"

    return ActiveDataSource(
        requested_mode=config.requested_mode,
        data_mode=DataMode.DEMO,
        status=status,
        sample_data=True,
        active_data_source=active_label,
        snapshot_id=snapshot_id,
        snapshot_valid=snapshot_valid,
        snapshot_is_fixture=None,
        snapshot_type=None,
        snapshot_warnings=snapshot_warnings or (),
        snapshot_errors=snapshot_errors or (),
        fallback_reason=fallback_reason,
        strict_snapshot=config.strict_snapshot,
        data_root=config.data_root,
    )


def _build_degraded(
    config: DataModeConfig,
    fallback_reason: str,
    snapshot_id: Optional[str] = None,
    snapshot_valid: Optional[bool] = None,
    snapshot_errors: Optional[Tuple[str, ...]] = None,
    snapshot_warnings: Optional[Tuple[str, ...]] = None,
) -> ActiveDataSource:
    """Build a ``degraded`` ``ActiveDataSource`` (strict mode failure)."""
    return ActiveDataSource(
        requested_mode=config.requested_mode,
        data_mode=DataMode.SNAPSHOT,
        status=DataSourceStatus.DEGRADED,
        sample_data=True,  # degraded still reports sample_data=true (no real data loaded)
        active_data_source="degraded",
        snapshot_id=snapshot_id,
        snapshot_valid=snapshot_valid,
        snapshot_is_fixture=None,
        snapshot_type=None,
        snapshot_warnings=snapshot_warnings or (),
        snapshot_errors=snapshot_errors or (),
        fallback_reason=fallback_reason,
        strict_snapshot=config.strict_snapshot,
        data_root=config.data_root,
    )


def _build_snapshot_ok(
    config: DataModeConfig,
    bundle: SnapshotBundle,
) -> ActiveDataSource:
    """Build an ``ok`` ``ActiveDataSource`` for a successfully loaded snapshot."""
    snapshot_type = bundle.manifest.get("snapshot_type")
    is_fixture = snapshot_type == "test_fixture"
    return ActiveDataSource(
        requested_mode=config.requested_mode,
        data_mode=DataMode.SNAPSHOT,
        status=DataSourceStatus.OK,
        sample_data=False,
        active_data_source=f"snapshot:{bundle.snapshot_id}",
        snapshot_id=bundle.snapshot_id,
        snapshot_valid=True,
        snapshot_is_fixture=is_fixture,
        snapshot_type=snapshot_type,
        snapshot_warnings=tuple(bundle.validation_result.warnings),
        snapshot_errors=(),
        fallback_reason=None,
        strict_snapshot=config.strict_snapshot,
        data_root=config.data_root,
        _bundle=bundle,
    )


def _try_load_snapshot(
    config: DataModeConfig,
) -> Tuple[
    Optional[SnapshotBundle],
    Optional[str],  # fallback_reason (None = no fallback needed)
    Optional[Tuple[str, ...]],  # errors
    Optional[Tuple[str, ...]],  # warnings
]:
    """Try to load + validate the snapshot.

    Returns ``(bundle, fallback_reason, errors, warnings)``. When
    ``bundle`` is ``None``, the snapshot could not be loaded and
    ``fallback_reason`` explains why.
    """
    if config.snapshot_id is None:
        return (
            None,
            "DATA_MODE=snapshot but DATA_SNAPSHOT_ID is not set.",
            None,
            None,
        )

    try:
        bundle = load_snapshot(
            config.snapshot_id,
            data_root=config.data_root,
            validate=True,
        )
    except SnapshotNotFoundError:
        return (
            None,
            f"snapshot '{config.snapshot_id}' not found under {config.data_root}.",
            None,
            None,
        )
    except SnapshotValidationError as exc:
        return (
            None,
            f"snapshot '{config.snapshot_id}' failed validation.",
            tuple(exc.result.errors),
            tuple(exc.result.warnings),
        )
    except (SnapshotLoadError, SnapshotError) as exc:
        return (
            None,
            f"snapshot '{config.snapshot_id}' could not be loaded: {exc}.",
            None,
            None,
        )

    # Loaded successfully. Check the test-fixture policy.
    snapshot_type = bundle.manifest.get("snapshot_type")
    is_fixture = snapshot_type == "test_fixture"
    if is_fixture and not config.allow_test_fixture:
        return (
            None,
            (
                f"snapshot '{config.snapshot_id}' is a test_fixture "
                f"but SNAPSHOT_ALLOW_TEST_FIXTURE=false."
            ),
            None,
            None,
        )

    return (bundle, None, None, None)


def resolve_active_data_source(force_reload: bool = False) -> ActiveDataSource:
    """Resolve the active data source.

    This is the main entry point. It parses env vars, optionally loads
    the snapshot, and returns an ``ActiveDataSource``. The result is
    cached; pass ``force_reload=True`` or call
    ``reset_resolver_cache()`` to re-resolve.
    """
    global _CACHE
    if _CACHE is not None and not force_reload:
        return _CACHE

    config = resolve_data_mode_from_env()

    # 1. Invalid DATA_MODE -> demo fallback.
    if config.env_fallback_reason is not None:
        _CACHE = _build_demo_active(
            config, fallback_reason=config.env_fallback_reason
        )
        return _CACHE

    # 2. Demo mode (explicit or unset).
    if config.requested_mode == DataMode.DEMO:
        _CACHE = _build_demo_active(config)
        return _CACHE

    # 3. Snapshot mode.
    bundle, fallback_reason, errors, warnings = _try_load_snapshot(config)

    if bundle is not None:
        # Snapshot loaded ok.
        _CACHE = _build_snapshot_ok(config, bundle)
        return _CACHE

    # Snapshot failed. Decide fallback vs degraded.
    if config.strict_snapshot:
        _CACHE = _build_degraded(
            config,
            fallback_reason=fallback_reason or "snapshot failed (strict mode).",
            snapshot_id=config.snapshot_id,
            snapshot_valid=False,
            snapshot_errors=errors,
            snapshot_warnings=warnings,
        )
    else:
        _CACHE = _build_demo_active(
            config,
            fallback_reason=fallback_reason,
            snapshot_id=config.snapshot_id,
            snapshot_valid=False,
            snapshot_errors=errors,
            snapshot_warnings=warnings,
        )
    return _CACHE


# --------------------------------------------------------------------------- #
# Metadata builder (for /api/health)
# --------------------------------------------------------------------------- #


def build_data_source_metadata() -> Dict[str, Any]:
    """Build the additive data-source metadata dict for ``/api/health``.

    Returns a dict with keys: ``data_mode``, ``active_data_source``,
    ``snapshot_id``, ``snapshot_valid``, ``snapshot_is_fixture``,
    ``snapshot_type``, ``snapshot_warnings``, ``fallback_reason``,
    ``strict_snapshot``.
    """
    active = resolve_active_data_source()
    return {
        "data_mode": active.data_mode.value,
        "active_data_source": active.active_data_source,
        "snapshot_id": active.snapshot_id,
        "snapshot_valid": active.snapshot_valid,
        "snapshot_is_fixture": active.snapshot_is_fixture,
        "snapshot_type": active.snapshot_type,
        "snapshot_warnings": list(active.snapshot_warnings),
        "fallback_reason": active.fallback_reason,
        "strict_snapshot": active.strict_snapshot,
    }


# --------------------------------------------------------------------------- #
# Accessors
# --------------------------------------------------------------------------- #


def get_snapshot_bundle_if_loaded() -> Optional[SnapshotBundle]:
    """Return the loaded ``SnapshotBundle``, or ``None``.

    In M8-C1/C2 this is only used by tests. The business endpoints do
    NOT call this yet — they keep reading demo data. M8-C3+ will wire
    snapshot data into the business flow.
    """
    active = resolve_active_data_source()
    bundle = getattr(active, "_bundle", None)
    if bundle is None:
        return None
    # Defensive: only return if it's actually a SnapshotBundle.
    if isinstance(bundle, SnapshotBundle):
        return bundle
    return None
