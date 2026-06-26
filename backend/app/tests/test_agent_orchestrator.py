"""Tests for the M8-E5 preview-only Agent Orchestrator Stub.

These tests enforce the hard guardrails for the service-only
orchestrator:

- Only allowlisted intents are accepted.
- Every result has ``requires_human_approval=True``.
- No execute/apply/commit/mutate/write capability is exposed.
- Deterministic validation verdicts are not overwritten.
- Trace steps are stable in order (intake -> route -> preview ->
  summarize -> approval).
- Demo/sample/historical data is never labeled as current/live.
- Missing data / errors fall back to hold (never crash, never guess).
- Data files are not mutated.
- No LLM / MCP / network / scraping imports are present.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

from backend.app.models.agent_orchestrator import (
    AgentOrchestratorRequest,
    AgentOrchestratorResult,
    OrchestratorIntent,
    OrchestratorStatus,
)
from backend.app.services.agent_orchestrator import orchestrate_preview


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_DIR = _REPO_ROOT / "data"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


_FORBIDDEN_CAPABILITIES = {
    "execute",
    "executed",
    "apply",
    "applied",
    "commit",
    "committed",
    "mutate",
    "mutated",
    "write_snapshot",
    "modify_roster",
    "modify_contract",
    "auto_sign",
    "auto_trade",
}

_FORBIDDEN_LIVE_LABELS = {"current nba", "live nba", "real-time nba", "real time nba"}


def _walk(obj: Any, path: str = "") -> None:
    """Yield (path, key, value) for every leaf in a nested structure."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            yield p, k, v
            yield from _walk(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            p = f"{path}[{i}]"
            yield from _walk(v, p)


# --------------------------------------------------------------------------- #
# Basic happy-path tests
# --------------------------------------------------------------------------- #


def test_signing_preview_returns_preview_only_result() -> None:
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.SIGNING_PREVIEW.value,
        team_id="DEM-ATL",
        objective="补强大个子位置",
    )
    result = orchestrate_preview(req, _DATA_DIR)

    assert isinstance(result, AgentOrchestratorResult)
    assert result.intent == "signing_preview"
    assert result.status == OrchestratorStatus.AWAITING_HUMAN_APPROVAL.value
    assert result.requires_human_approval is True
    assert result.preview_payload is not None
    assert "proposal" in result.preview_payload or "actions" in result.preview_payload
    assert result.agent_trace is not None
    # M9-A: additive intelligence_summary must be present
    assert result.intelligence_summary is not None
    assert result.intelligence_summary.source == "deterministic-fake-adapter"


def test_trade_preview_demo_returns_preview_only_result() -> None:
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.TRADE_PREVIEW_DEMO.value,
    )
    result = orchestrate_preview(req, _DATA_DIR)

    assert isinstance(result, AgentOrchestratorResult)
    assert result.intent == "trade_preview_demo"
    assert result.status == OrchestratorStatus.AWAITING_HUMAN_APPROVAL.value
    assert result.requires_human_approval is True
    assert result.preview_payload is not None
    assert "trade_transaction" in result.preview_payload
    assert "preview" in result.preview_payload
    assert result.agent_trace is not None
    # M9-A: additive intelligence_summary must be present
    assert result.intelligence_summary is not None
    assert result.intelligence_summary.source == "deterministic-fake-adapter"


def test_hold_returns_hold_result() -> None:
    req = AgentOrchestratorRequest(intent=OrchestratorIntent.HOLD.value)
    result = orchestrate_preview(req, _DATA_DIR)

    assert isinstance(result, AgentOrchestratorResult)
    assert result.intent == "hold"
    assert result.status == OrchestratorStatus.HOLD.value
    assert result.requires_human_approval is True
    assert result.preview_payload is not None
    assert result.preview_payload.get("status") == "hold"
    # M9-A: additive intelligence_summary must be present (hold summary)
    assert result.intelligence_summary is not None
    assert "暂不行动" in result.intelligence_summary.summary_title


def test_unsupported_intent_is_blocked_not_guessed() -> None:
    """Free-form / unknown intents must be blocked, never routed to signing/trade."""
    bad_intents = [
        "execute_trade",
        "sign_player_automatically",
        "do_something_cool",
        "",
        "SIGNING",
        "trade",
        "auto_execute",
    ]
    for intent in bad_intents:
        req = AgentOrchestratorRequest(intent=intent)
        result = orchestrate_preview(req, _DATA_DIR)
        assert result.status == OrchestratorStatus.BLOCKED.value, (
            f"intent={intent!r} should be blocked, got {result.status}"
        )
        assert result.requires_human_approval is True
        assert result.preview_payload.get("hold_reason") is not None
        # Must NOT have called signing/trade preview: no proposal/trade_transaction keys.
        assert "proposal" not in result.preview_payload
        assert "trade_transaction" not in result.preview_payload
        # M9-A: blocked results still carry an intelligence_summary that says
        # "安全拦截" and does not claim any plan was generated.
        assert result.intelligence_summary is not None
        blob = " ".join(
            [
                result.intelligence_summary.summary_title,
                result.intelligence_summary.plain_language_summary,
                result.intelligence_summary.deterministic_verdict,
            ]
        )
        assert "拦截" in blob or "blocked" in blob.lower()
        assert "补强方案" not in blob
        assert "双方交易" not in blob


# --------------------------------------------------------------------------- #
# Human-approval guardrail
# --------------------------------------------------------------------------- #


def test_all_results_require_human_approval() -> None:
    for intent in (
        OrchestratorIntent.SIGNING_PREVIEW.value,
        OrchestratorIntent.TRADE_PREVIEW_DEMO.value,
        OrchestratorIntent.HOLD.value,
        "some_garbage",
    ):
        req = AgentOrchestratorRequest(intent=intent, team_id="DEM-ATL")
        result = orchestrate_preview(req, _DATA_DIR)
        assert result.requires_human_approval is True
        assert result.agent_trace["requires_human_approval"] is True
        # Also check the inner preview_payload for signing/trade paths.
        inner = result.preview_payload
        if "requires_human_approval" in inner:
            assert inner["requires_human_approval"] is True


# --------------------------------------------------------------------------- #
# No execution / mutation capability
# --------------------------------------------------------------------------- #


def test_result_has_no_forbidden_execution_capabilities() -> None:
    for intent in (
        OrchestratorIntent.SIGNING_PREVIEW.value,
        OrchestratorIntent.TRADE_PREVIEW_DEMO.value,
        OrchestratorIntent.HOLD.value,
    ):
        req = AgentOrchestratorRequest(intent=intent, team_id="DEM-ATL")
        result = orchestrate_preview(req, _DATA_DIR)
        result_dict = result.to_dict()
        serialized = json.dumps(result_dict, ensure_ascii=False).lower()
        for forbidden in (
            "auto_executed",
            "transaction_executed",
            "signed_automatically",
            "trade_executed",
            "mutation_performed",
            "wrote_snapshot",
            "roster_modified",
            "contracts_modified",
        ):
            assert forbidden not in serialized, (
                f"forbidden text {forbidden!r} present in {intent} result"
            )


def test_trace_step_5_technical_details_confirm_no_mutation() -> None:
    """Step 5 (request_human_approval) must explicitly state no mutation."""
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.SIGNING_PREVIEW.value, team_id="DEM-ATL"
    )
    result = orchestrate_preview(req, _DATA_DIR)
    steps = result.agent_trace["steps"]
    step5 = steps[4]
    assert step5["tool_name"] == "request_human_approval"
    td = step5["technical_details"]
    assert td.get("auto_execution_performed") is False
    assert td.get("roster_mutated") is False
    assert td.get("contracts_mutated") is False
    assert td.get("snapshot_written") is False


def test_orchestrator_module_has_no_forbidden_imports() -> None:
    """The orchestrator module must not import LLM/MCP/network/scraping libs."""
    import backend.app.services.agent_orchestrator as orch_mod

    source = Path(orch_mod.__file__).read_text(encoding="utf-8")
    forbidden_imports = [
        "openai",
        "anthropic",
        "mcp",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "selenium",
        "playwright",
        "bs4",
        "beautifulsoup",
        "scrapy",
    ]
    for name in forbidden_imports:
        assert f"import {name}" not in source and f"from {name}" not in source, (
            f"orchestrator must not import {name!r}"
        )


@pytest.mark.parametrize(
    "module_path",
    [
        "backend.app.services.agent_intelligence",
        "backend.app.models.agent_intelligence",
    ],
)
def test_intelligence_modules_have_no_forbidden_imports(module_path: str) -> None:
    """M9-A: intelligence modules must not import LLM/MCP/network libs,
    and must not import the deterministic engines (they only read already-
    built result fields)."""
    import importlib

    mod = importlib.import_module(module_path)
    source = Path(mod.__file__).read_text(encoding="utf-8")
    forbidden_imports = [
        "openai",
        "anthropic",
        "mcp",
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "socket",
        "selenium",
        "playwright",
        "bs4",
        "beautifulsoup",
        "scrapy",
        "websocket",
        "transaction_rule_engine",
        "trade_simulator",
        "snapshot_loader",
    ]
    for name in forbidden_imports:
        assert f"import {name}" not in source and f"from {name}" not in source, (
            f"{module_path} must not import {name!r}"
        )


def test_orchestrator_exposes_no_execute_entrypoint() -> None:
    """The orchestrator module must not expose execute/apply/commit functions."""
    import backend.app.services.agent_orchestrator as orch_mod

    for forbidden_name in (
        "execute_signing",
        "execute_trade",
        "apply_transaction",
        "commit_transaction",
        "mutate_roster",
        "write_snapshot",
    ):
        assert not hasattr(orch_mod, forbidden_name), (
            f"orchestrator must not expose {forbidden_name!r}"
        )


# --------------------------------------------------------------------------- #
# Deterministic verdict preservation
# --------------------------------------------------------------------------- #


def test_orchestrator_does_not_change_signing_validation_verdict() -> None:
    """The orchestrator must preserve the deterministic validation status."""
    from backend.app.services.proposal_viewer import build_demo_payload
    from backend.app.models.agent import OffseasonGoal

    goal = OffseasonGoal(
        team_id="DEM-ATL",
        objective="补强大个子位置",
        target_positions=(),
    )
    direct_payload = build_demo_payload(goal, _DATA_DIR)
    direct_statuses = [
        a.get("validation_status") for a in direct_payload.get("actions", [])
    ]

    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.SIGNING_PREVIEW.value,
        team_id="DEM-ATL",
        objective="补强大个子位置",
    )
    result = orchestrate_preview(req, _DATA_DIR)
    orch_actions = result.preview_payload.get("actions", [])
    orch_statuses = [a.get("validation_status") for a in orch_actions]

    assert orch_statuses == direct_statuses, (
        "orchestrator must not modify signing validation_status values"
    )


def test_orchestrator_does_not_change_trade_validation_verdict() -> None:
    """The orchestrator must preserve the deterministic trade validation result."""
    scripts_dir = _REPO_ROOT / "backend" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from run_trade_preview_demo import build_trade_preview_payload  # type: ignore

    direct_payload = build_trade_preview_payload(_DATA_DIR)
    direct_vr = direct_payload["preview"]["validation_result"]

    req = AgentOrchestratorRequest(intent=OrchestratorIntent.TRADE_PREVIEW_DEMO.value)
    result = orchestrate_preview(req, _DATA_DIR)
    orch_vr = result.preview_payload["preview"]["validation_result"]

    assert orch_vr["status"] == direct_vr["status"]
    assert orch_vr["is_valid"] == direct_vr["is_valid"]
    assert orch_vr["issues"] == direct_vr["issues"]


# --------------------------------------------------------------------------- #
# Trace step stability
# --------------------------------------------------------------------------- #


def test_trace_steps_have_stable_order_and_names() -> None:
    """All 5 orchestrator steps must be present in the contracted order."""
    expected = [
        ("orch-step-1-intake", "intake_request"),
        ("orch-step-2-route", "route_intent"),
        # step3 id differs by intent; check via sequence
        ("orch-step-5-approval", "request_human_approval"),
    ]

    for intent in (
        OrchestratorIntent.SIGNING_PREVIEW.value,
        OrchestratorIntent.TRADE_PREVIEW_DEMO.value,
        OrchestratorIntent.HOLD.value,
    ):
        req = AgentOrchestratorRequest(intent=intent, team_id="DEM-ATL")
        result = orchestrate_preview(req, _DATA_DIR)
        steps = result.agent_trace["steps"]
        assert len(steps) == 5, f"{intent} should have exactly 5 trace steps"

        # Check sequence numbers 1..5
        for i, step in enumerate(steps, start=1):
            assert step["sequence"] == i

        # Check fixed steps 1, 2, 5
        assert steps[0]["step_id"] == expected[0][0]
        assert steps[0]["tool_name"] == expected[0][1]
        assert steps[1]["step_id"] == expected[1][0]
        assert steps[1]["tool_name"] == expected[1][1]
        assert steps[4]["step_id"] == expected[2][0]
        assert steps[4]["tool_name"] == expected[2][1]
        assert steps[4]["requires_human_review"] is True

        # Step 3 tool_name: must be run_deterministic_preview or hold_without_execution
        assert steps[2]["tool_name"] in (
            "run_deterministic_preview",
            "hold_without_execution",
        )
        # Step 4
        assert steps[3]["tool_name"] == "summarize_validation_and_evidence"


def test_trace_final_message_is_read_only_disclaimer() -> None:
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.SIGNING_PREVIEW.value, team_id="DEM-ATL"
    )
    result = orchestrate_preview(req, _DATA_DIR)
    assert "只读" in result.agent_trace["final_message"]
    assert "不会自动执行" in result.agent_trace["final_message"]


# --------------------------------------------------------------------------- #
# Data labeling (demo/sample/historical, never live)
# --------------------------------------------------------------------------- #


def test_demo_data_label_not_misrepresented_as_live() -> None:
    for intent in (
        OrchestratorIntent.SIGNING_PREVIEW.value,
        OrchestratorIntent.TRADE_PREVIEW_DEMO.value,
    ):
        req = AgentOrchestratorRequest(intent=intent, team_id="DEM-ATL")
        result = orchestrate_preview(req, _DATA_DIR)
        result_dict = result.to_dict()
        serialized = json.dumps(result_dict, ensure_ascii=False).lower()

        # It IS marked as sample/demo/historical.
        has_sample_label = (
            "sample_data" in serialized
            or "演示数据" in result_dict["agent_trace"].get("data_source_label", "")
            or "历史数据样本" in result_dict["agent_trace"].get("data_source_label", "")
        )
        assert has_sample_label, f"{intent} result missing demo/sample label"

        # It must NOT be labeled as current/live/real-time NBA.
        for label in _FORBIDDEN_LIVE_LABELS:
            assert label not in serialized, (
                f"{intent} result must not be labeled as {label!r}"
            )


def test_orchestrator_limitations_mention_preview_only() -> None:
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.SIGNING_PREVIEW.value, team_id="DEM-ATL"
    )
    result = orchestrate_preview(req, _DATA_DIR)
    limitations_text = " ".join(result.limitations).lower()
    assert "no autonomous transaction execution" in limitations_text
    assert "preview" in limitations_text or "read-only" in limitations_text
    assert "no llm" in limitations_text
    assert "no mcp" in limitations_text


# --------------------------------------------------------------------------- #
# Fallback / missing-data behavior
# --------------------------------------------------------------------------- #


def test_invalid_team_id_falls_back_to_hold_not_crash() -> None:
    """An invalid team_id should result in hold/blocked, not an exception."""
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.SIGNING_PREVIEW.value,
        team_id="FAKE-TEAM-999",
    )
    result = orchestrate_preview(req, _DATA_DIR)
    # Either hold (fallback) or awaiting_human_approval (if the underlying
    # pipeline already has fallback logic). Either way it must NOT raise,
    # and must still require human approval.
    assert result.requires_human_approval is True
    assert result.status in (
        OrchestratorStatus.HOLD.value,
        OrchestratorStatus.AWAITING_HUMAN_APPROVAL.value,
        OrchestratorStatus.BLOCKED.value,
    )
    assert isinstance(result.preview_payload, dict)


# --------------------------------------------------------------------------- #
# Data-file immutability
# --------------------------------------------------------------------------- #


def _hash_data_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_orchestrator_does_not_modify_data_files() -> None:
    data_files = [
        _DATA_DIR / "players.json",
        _DATA_DIR / "contracts.json",
        _DATA_DIR / "teams.json",
    ]
    before = {p.name: _hash_data_file(p) for p in data_files if p.exists()}

    for intent in (
        OrchestratorIntent.SIGNING_PREVIEW.value,
        OrchestratorIntent.TRADE_PREVIEW_DEMO.value,
        OrchestratorIntent.HOLD.value,
    ):
        req = AgentOrchestratorRequest(intent=intent, team_id="DEM-ATL")
        orchestrate_preview(req, _DATA_DIR)

    after = {p.name: _hash_data_file(p) for p in data_files if p.exists()}
    assert before == after, "orchestrator must not mutate data/*.json files"


# --------------------------------------------------------------------------- #
# Frozen result immutability
# --------------------------------------------------------------------------- #


def test_result_dataclass_is_frozen() -> None:
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.SIGNING_PREVIEW.value, team_id="DEM-ATL"
    )
    result = orchestrate_preview(req, _DATA_DIR)
    with pytest.raises(Exception):
        result.requires_human_approval = False


def test_trace_steps_contract_tool_names() -> None:
    """Verify step 3 tool names per intent."""
    # signing_preview -> run_deterministic_preview
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.SIGNING_PREVIEW.value, team_id="DEM-ATL"
    )
    assert (
        orchestrate_preview(req, _DATA_DIR)
        .agent_trace["steps"][2]["tool_name"]
        == "run_deterministic_preview"
    )

    # trade_preview_demo -> run_deterministic_preview
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.TRADE_PREVIEW_DEMO.value
    )
    assert (
        orchestrate_preview(req, _DATA_DIR)
        .agent_trace["steps"][2]["tool_name"]
        == "run_deterministic_preview"
    )

    # hold -> hold_without_execution
    req = AgentOrchestratorRequest(intent=OrchestratorIntent.HOLD.value)
    assert (
        orchestrate_preview(req, _DATA_DIR)
        .agent_trace["steps"][2]["tool_name"]
        == "hold_without_execution"
    )

    # unsupported -> hold_without_execution (blocked)
    req = AgentOrchestratorRequest(intent="nonsense_intent")
    step3 = orchestrate_preview(req, _DATA_DIR).agent_trace["steps"][2]
    assert step3["tool_name"] == "hold_without_execution"
    assert step3["status"] == "blocked"


# --------------------------------------------------------------------------- #
# Serialization round-trip
# --------------------------------------------------------------------------- #


def test_to_dict_is_json_serializable() -> None:
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.SIGNING_PREVIEW.value,
        team_id="DEM-ATL",
        objective="test",
    )
    result = orchestrate_preview(req, _DATA_DIR)
    d = result.to_dict()
    # Must be JSON-serializable without errors.
    serialized = json.dumps(d, ensure_ascii=False)
    assert len(serialized) > 0
    # And the deserialized form still requires human approval.
    reparsed = json.loads(serialized)
    assert reparsed["requires_human_approval"] is True
    assert reparsed["agent_trace"]["requires_human_approval"] is True
