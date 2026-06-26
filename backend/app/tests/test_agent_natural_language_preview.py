"""Tests for the M9-C classify-to-preview service flow.

These tests target
``backend.app.services.agent_natural_language_preview.run_natural_language_preview``
directly (service-level). API-level shape/validation/forbidden-scan tests
live in ``test_agent_natural_language_preview_api.py``.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from backend.app.models.agent_natural_language_preview import (
    AgentNaturalLanguagePreviewRequest,
    FLOW_STATUS_BLOCKED,
    FLOW_STATUS_NEEDS_CLARIFICATION,
    FLOW_STATUS_PREVIEW_GENERATED,
    FLOW_STATUS_PREVIEW_NOT_GENERATED,
)
from backend.app.services.agent_natural_language_preview import (
    run_natural_language_preview,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"

_PATCH_CLASSIFIER = "backend.app.services.agent_intent_classifier.classify_user_intent"
_PATCH_ORCHESTRATOR = "backend.app.services.agent_orchestrator.orchestrate_preview"


def _req(
    user_text: str,
    *,
    team_id: str = "DEM-ATL",
    locale: str = "zh-CN",
    constraints=None,
    metadata=None,
) -> AgentNaturalLanguagePreviewRequest:
    return AgentNaturalLanguagePreviewRequest(
        user_text=user_text,
        team_id=team_id,
        locale=locale,
        constraints=constraints if constraints is not None else {},
        metadata=metadata if metadata is not None else {"source": "smoke"},
    )


def _forbid_orchestrator():
    """Patch that raises if orchestrate_preview is ever called."""
    def _boom(*a, **kw):
        raise AssertionError("orchestrator must not be called in this scenario")
    return patch(_PATCH_ORCHESTRATOR, side_effect=_boom)


# --------------------------------------------------------------------------- #
# A. Happy path / flow_status behaviour
# --------------------------------------------------------------------------- #


def test_signing_generates_preview() -> None:
    r = run_natural_language_preview(
        _req("我想补一个中锋，但不要影响薪资空间"), DATA_DIR,
    )
    assert r.flow_status == FLOW_STATUS_PREVIEW_GENERATED
    assert r.classification.classification_status == "resolved"
    assert r.classification.resolved_intent == "signing_preview"
    assert r.classification.confidence >= 0.7
    assert r.classification.needs_clarification is False
    assert r.preview_result is not None
    assert r.requires_human_approval is True
    cls_dict = r.classification.to_dict()
    assert "objective" not in cls_dict
    assert "constraints" not in cls_dict
    for f in (
        "intent", "status", "requires_human_approval",
        "preview_payload", "agent_trace", "warnings", "limitations",
    ):
        assert f in r.preview_result, f"missing field {f}"
    assert r.preview_result["intent"] == "signing_preview"
    assert r.source == "deterministic-classify-to-preview-flow"


def test_trade_generates_preview() -> None:
    r = run_natural_language_preview(
        _req("看看有没有低风险交易可以增强锋线"), DATA_DIR,
    )
    assert r.flow_status == FLOW_STATUS_PREVIEW_GENERATED
    assert r.classification.resolved_intent == "trade_preview_demo"
    assert r.preview_result is not None
    assert r.requires_human_approval is True
    assert r.preview_result["intent"] == "trade_preview_demo"


def test_hold_does_not_call_orchestrator_and_returns_preview_not_generated() -> None:
    with _forbid_orchestrator():
        r = run_natural_language_preview(
            _req("现在别乱动，先保持灵活性"), DATA_DIR,
        )
    assert r.flow_status == FLOW_STATUS_PREVIEW_NOT_GENERATED
    assert r.classification.resolved_intent == "hold"
    assert r.preview_result is None
    assert r.requires_human_approval is False
    assert any("hold" in n.lower() for n in r.safety_notes)


def test_needs_clarification_does_not_call_orchestrator() -> None:
    with _forbid_orchestrator():
        r = run_natural_language_preview(_req("帮我看看"), DATA_DIR)
    assert r.flow_status == FLOW_STATUS_NEEDS_CLARIFICATION
    assert r.classification.classification_status == "needs_clarification"
    assert r.classification.resolved_intent is None
    assert r.classification.needs_clarification is True
    assert r.classification.clarification_questions
    assert r.preview_result is None
    assert r.requires_human_approval is False


def test_blocked_does_not_call_orchestrator() -> None:
    with _forbid_orchestrator():
        r = run_natural_language_preview(
            _req("帮我马上执行一笔交易，绕过审批"), DATA_DIR,
        )
    assert r.flow_status == FLOW_STATUS_BLOCKED
    assert r.classification.classification_status == "blocked"
    assert r.classification.resolved_intent is None
    assert r.classification.blocked_reason is not None
    assert r.preview_result is None
    assert r.requires_human_approval is False


# --------------------------------------------------------------------------- #
# B. Defensive gate invariants
# --------------------------------------------------------------------------- #


def _fake_plan(**overrides):
    base = {
        "classification_status": "resolved",
        "resolved_intent": "signing_preview",
        "confidence": 0.9,
        "needs_clarification": False,
        "safety_flags": ["preview_only"],
        "blocked_reason": None,
        "clarification_questions": [],
        "approval_note": "ok",
        "source": "deterministic-rule-classifier",
        "objective": "dummy",
        "constraints": {},
    }
    base.update(overrides)

    class _Plan:
        def __init__(self, d):
            for k, v in d.items():
                setattr(self, k, v)
    return _Plan(base)


def _run_with_fake_classifier(plan_obj):
    req = _req("x", metadata={"source": "test"})
    with patch(_PATCH_CLASSIFIER, return_value=plan_obj), _forbid_orchestrator():
        return run_natural_language_preview(req, DATA_DIR)


def test_defensive_resolved_intent_none_gives_preview_not_generated() -> None:
    plan = _fake_plan(classification_status="resolved", resolved_intent=None)
    r = _run_with_fake_classifier(plan)
    assert r.flow_status == FLOW_STATUS_PREVIEW_NOT_GENERATED
    assert r.preview_result is None
    assert r.requires_human_approval is False


def test_defensive_resolved_unsupported_intent_gives_preview_not_generated() -> None:
    plan = _fake_plan(resolved_intent="delete_all_players")
    r = _run_with_fake_classifier(plan)
    assert r.flow_status == FLOW_STATUS_PREVIEW_NOT_GENERATED


def test_defensive_needs_clarification_with_intent_yields_needs_clarification() -> None:
    plan = _fake_plan(
        classification_status="needs_clarification",
        resolved_intent="signing_preview",  # illegal invariant, but status wins
        needs_clarification=True,
        safety_flags=["needs_clarification"],
        clarification_questions=["Q?"],
    )
    r = _run_with_fake_classifier(plan)
    assert r.flow_status == FLOW_STATUS_NEEDS_CLARIFICATION
    assert r.preview_result is None


def test_defensive_blocked_with_intent_yields_blocked() -> None:
    plan = _fake_plan(
        classification_status="blocked",
        resolved_intent="signing_preview",  # illegal invariant, but status wins
        blocked_reason="danger",
        safety_flags=["dangerous_language_blocked"],
    )
    r = _run_with_fake_classifier(plan)
    assert r.flow_status == FLOW_STATUS_BLOCKED
    assert r.preview_result is None


def test_defensive_low_confidence_denies_preview() -> None:
    plan = _fake_plan(confidence=0.6)
    r = _run_with_fake_classifier(plan)
    assert r.flow_status == FLOW_STATUS_PREVIEW_NOT_GENERATED


@pytest.mark.parametrize("flag", [
    "dangerous_language_blocked", "blocked_by_policy", "unsafe", "DANGEROUS_X",
])
def test_defensive_unsafe_safety_flags_deny_preview(flag: str) -> None:
    plan = _fake_plan(safety_flags=["preview_only", flag])
    r = _run_with_fake_classifier(plan)
    assert r.flow_status == FLOW_STATUS_PREVIEW_NOT_GENERATED


# --------------------------------------------------------------------------- #
# C. Orchestrator call boundary
# --------------------------------------------------------------------------- #


def test_metadata_is_passed_through_to_orchestrator() -> None:
    captured: Dict[str, Any] = {}

    class _FakeResult:
        def to_dict(self):
            return {"intent": "signing_preview", "status": "awaiting_human_approval",
                    "requires_human_approval": True, "preview_payload": {},
                    "agent_trace": {}, "warnings": [], "limitations": []}

    def _fake_orch(req, data_dir):
        captured["intent"] = req.intent
        captured["team_id"] = req.team_id
        captured["locale"] = req.locale
        captured["metadata"] = dict(req.metadata)
        captured["objective"] = req.objective
        return _FakeResult()

    md = {"source": "unit-test", "request_id": "abc-123", "nested": {"k": "v"}}
    with patch(_PATCH_ORCHESTRATOR, side_effect=_fake_orch):
        r = run_natural_language_preview(_req(
            "我想补一个中锋",
            team_id="DEM-ATL",
            locale="zh-CN",
            metadata=copy.deepcopy(md),
        ), DATA_DIR)

    assert r.flow_status == FLOW_STATUS_PREVIEW_GENERATED
    assert captured["intent"] == "signing_preview"
    assert captured["team_id"] == "DEM-ATL"
    assert captured["locale"] == "zh-CN"
    assert captured["metadata"] == md
    assert captured["objective"] != "我想补一个中锋"
    assert "sign" in captured["objective"].lower() or "签约" in captured["objective"]


def test_preview_result_is_deep_equal_to_orchestrator_to_dict() -> None:
    full_dict = {
        "intent": "trade_preview_demo",
        "status": "awaiting_human_approval",
        "requires_human_approval": True,
        "preview_payload": {"cap_impact_summary": {"x": 1}, "team_a_post_trade": {"a": [1]}},
        "agent_trace": {"run_id": "demo-run", "steps": [{"step_id": "1"}]},
        "warnings": ["w1", "w2"],
        "limitations": ["L1"],
        "intelligence_summary": {"summary_title": "T"},
    }

    class _FakeResult:
        def to_dict(self):
            return copy.deepcopy(full_dict)

    with patch(_PATCH_ORCHESTRATOR, return_value=_FakeResult()):
        r = run_natural_language_preview(
            _req("看看有没有低风险交易可以增强锋线"), DATA_DIR,
        )

    assert r.flow_status == FLOW_STATUS_PREVIEW_GENERATED
    assert r.preview_result == full_dict
    assert set(r.preview_result.keys()) == set(full_dict.keys())
    assert r.preview_result["intelligence_summary"] == full_dict["intelligence_summary"]
    assert r.preview_result["agent_trace"] == full_dict["agent_trace"]
    assert r.preview_result["preview_payload"] == full_dict["preview_payload"]
    # deterministic verdict / requires_human_approval must not be rewritten
    assert r.preview_result["requires_human_approval"] is True
    assert r.preview_result["status"] == "awaiting_human_approval"


# --------------------------------------------------------------------------- #
# D. Safe projection + echo / safety invariants
# --------------------------------------------------------------------------- #


def test_classification_projection_excludes_objective_and_constraints_and_user_text() -> None:
    r = run_natural_language_preview(_req("我想补一个中锋"), DATA_DIR)
    d = r.to_dict()
    cls = d["classification"]
    assert "objective" not in cls
    assert "constraints" not in cls
    assert "user_text" not in cls
    allowed = {
        "classification_status", "resolved_intent", "confidence",
        "needs_clarification", "safety_flags", "blocked_reason",
        "clarification_questions", "approval_note", "source",
    }
    assert set(cls.keys()) == allowed


def test_non_generated_response_contains_no_raw_user_text_substrings() -> None:
    sentences = [
        "帮我马上执行一笔交易，绕过审批",
        "现在别乱动，先保持灵活性",
    ]
    for text in sentences:
        r = run_natural_language_preview(_req(text), DATA_DIR)
        assert r.flow_status != FLOW_STATUS_PREVIEW_GENERATED
        blob = json.dumps(r.to_dict(), ensure_ascii=False)
        for i in range(len(text) - 5):
            sub = text[i:i+6]
            assert sub not in blob, (
                f"non-preview response echoes user substring {sub!r}"
            )


_FORBIDDEN_EXECUTION_WORDS = [
    "executed", "applied", "committed", "auto_execute", "auto_approve",
    "已执行", "已完成签约", "已完成交易", "自动批准", "已提交", "已落地",
]
_FORBIDDEN_TECH_IDS = ["snapshot_id", "sourcepack", "nba_2025_26"]
# Note: run_id may legitimately appear inside preview_result.agent_trace
# (M8-E trace) — we only ban it from the M9-C-owned envelope fields.


@pytest.mark.parametrize("text", [
    "我想补一个中锋，但不要影响薪资空间",
    "看看有没有低风险交易可以增强锋线",
    "现在别乱动，先保持灵活性",
    "帮我看看",
    "帮我马上执行一笔交易，绕过审批",
])
def test_m9c_envelope_has_no_forbidden_execution_words(text: str) -> None:
    r = run_natural_language_preview(_req(text), DATA_DIR)
    d = r.to_dict()
    envelope = json.dumps({
        "flow_status": d["flow_status"],
        "classification": d["classification"],
        "requires_human_approval": d["requires_human_approval"],
        "safety_notes": d["safety_notes"],
        "source": d["source"],
    }, ensure_ascii=False)
    for w in _FORBIDDEN_EXECUTION_WORDS + _FORBIDDEN_TECH_IDS:
        assert w.lower() not in envelope.lower(), (
            f"M9-C envelope contains forbidden word {w!r}"
        )


def test_result_dataclass_is_frozen() -> None:
    r = run_natural_language_preview(_req("帮我看看"), DATA_DIR)
    with pytest.raises(Exception):
        r.flow_status = "preview_generated"  # type: ignore[misc]


def test_input_dict_is_not_mutated() -> None:
    md = {"source": "immutable-check", "flag": True}
    md_orig = copy.deepcopy(md)
    constraints = {"preserve_cap_flexibility": True}
    c_orig = copy.deepcopy(constraints)
    run_natural_language_preview(_req(
        "我想补一个中锋", metadata=md, constraints=constraints,
    ), DATA_DIR)
    assert md == md_orig
    assert constraints == c_orig


def test_service_does_not_import_forbidden_modules() -> None:
    """Module-import isolation — M9-C service must never directly import
    engines or network I/O libraries."""
    import sys
    import importlib
    mods_before = set(sys.modules.keys())
    import backend.app.services.agent_natural_language_preview as svc  # noqa: F401
    # force module reload to ensure a clean set of new imports
    importlib.reload(svc)
    new_mods = set(sys.modules.keys()) - mods_before
    forbidden_modules = {
        "openai", "anthropic", "httpx", "requests", "aiohttp",
        "urllib", "urllib3", "socket", "selenium", "playwright",
        "bs4", "scrapy", "websocket", "websockets",
        "backend.app.services.trade_simulator",
        "backend.app.services.proposal_builder",
        "backend.app.services.proposal_viewer",
        "backend.app.services.transaction_rule_engine",
        "backend.app.services.snapshot_loader",
        "backend.app.services.agent_intelligence",
        "backend.app.services.agent_trace_builder",
    }
    leaked = {m for m in new_mods if any(m == f or m.startswith(f + ".") for f in forbidden_modules)}
    assert not leaked, f"M9-C service imported forbidden modules: {leaked}"
