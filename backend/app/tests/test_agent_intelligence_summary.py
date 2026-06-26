"""Tests for the M9-A deterministic Agent Intelligence Summary adapter.

These tests enforce:

- The orchestrator returns an ``intelligence_summary`` for every intent.
- Old response fields (intent/status/requires_human_approval/preview_payload/
  agent_trace/warnings/limitations) are unchanged.
- ``preview_payload`` is byte-for-byte identical (deep-equal) between
  pre-summary and post-summary code paths (proved via deepcopy +
  json.dumps sort_keys round-trip).
- Summary is driven by ``status``, not by ``intent``: a signing/trade
  intent that ends in hold/blocked produces a hold/blocked summary, not
  a recommendation.
- Blocked results say "安全拦截" and never claim a plan was generated.
- Forbidden execution / live-data / technical-ID snippets never appear
  in the summary.
- The intelligence module imports no LLM / network / scraping / browser
  libraries and never calls transaction_rule_engine / trade_simulator /
  snapshot_loader.
- Calling build_intelligence_summary does not mutate any data file or
  fixture snapshot.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.app.models.agent_intelligence import AgentIntelligenceSummary
from backend.app.models.agent_orchestrator import (
    AgentOrchestratorRequest,
    AgentOrchestratorResult,
    OrchestratorIntent,
    OrchestratorStatus,
)
from backend.app.services.agent_intelligence import build_intelligence_summary
from backend.app.services.agent_orchestrator import orchestrate_preview


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_DIR = _REPO_ROOT / "data"
_FIXTURE_SNAPSHOT_DIR = _REPO_ROOT / "backend" / "app" / "tests" / "fixtures" / "snapshots"


# --------------------------------------------------------------------------- #
# Forbidden-snippet constants
# --------------------------------------------------------------------------- #

_EN_FORBIDDEN = {
    "executed",
    "applied",
    "committed",
    "auto_execute",
    "auto_approve",
    "live",
    "current",
    "real-time",
    "real time",
}

_ZH_FORBIDDEN = {
    "已执行",
    "已完成签约",
    "已完成交易",
    "自动批准",
    "已提交",
    "已落地",
    "实时",
    "最新",
    "当前阵容",
    "当前薪资",
}

_TECH_ID_FORBIDDEN = {
    "run_id",
    "snapshot_id",
    "sourcepack",
    "nba_2025_26",
}

_EXECUTION_SEMANTICS_FORBIDDEN = {
    "executed",
    "applied",
    "committed",
    "auto_execute",
    "auto_approve",
    "已执行",
    "已完成签约",
    "已完成交易",
    "自动批准",
    "已提交",
    "已落地",
}


def _summary_blob(summary: AgentIntelligenceSummary) -> str:
    """Flatten every string/list field of a summary into one searchable blob."""
    d = summary.to_dict()
    parts: List[str] = []
    for v in d.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend(str(x) for x in v)
        elif isinstance(v, dict):
            parts.append(json.dumps(v, ensure_ascii=False, sort_keys=True))
    return " | ".join(parts).lower()


def _hash_data_files(paths: List[Path]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for p in paths:
        if p.exists() and p.is_file():
            out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        elif p.exists() and p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    out[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


# --------------------------------------------------------------------------- #
# 1. Summary always present, old fields preserved
# --------------------------------------------------------------------------- #


def test_orchestrator_returns_intelligence_summary_for_all_intents() -> None:
    for intent in (
        OrchestratorIntent.SIGNING_PREVIEW.value,
        OrchestratorIntent.TRADE_PREVIEW_DEMO.value,
        OrchestratorIntent.HOLD.value,
        "execute_trade",
    ):
        req = AgentOrchestratorRequest(intent=intent, team_id="DEM-ATL")
        result = orchestrate_preview(req, _DATA_DIR)
        assert result.intelligence_summary is not None, (
            f"intent={intent!r} missing intelligence_summary"
        )
        assert isinstance(result.intelligence_summary, AgentIntelligenceSummary)
        d = result.to_dict()
        assert "intelligence_summary" in d
        for old_field in (
            "intent",
            "status",
            "requires_human_approval",
            "preview_payload",
            "agent_trace",
            "warnings",
            "limitations",
        ):
            assert old_field in d, f"old field {old_field!r} missing after M9-A"


def test_result_constructs_without_intelligence_summary_for_backward_compat() -> None:
    """Backward-compat: omitting intelligence_summary must still work and
    to_dict() must not include the key."""
    r = AgentOrchestratorResult(
        intent="signing_preview",
        status="awaiting_human_approval",
        requires_human_approval=True,
        preview_payload={"actions": []},
        agent_trace={"steps": []},
    )
    assert r.intelligence_summary is None
    d = r.to_dict()
    assert "intelligence_summary" not in d
    # Adding a summary works too.
    r2 = AgentOrchestratorResult(
        intent="hold",
        status="hold",
        requires_human_approval=True,
        preview_payload={"status": "hold"},
        agent_trace={"steps": []},
        intelligence_summary=AgentIntelligenceSummary(
            summary_title="t",
            plain_language_summary="p",
            deterministic_verdict="v",
        ),
    )
    assert r2.to_dict()["intelligence_summary"]["summary_title"] == "t"


def test_intelligence_summary_is_json_serializable() -> None:
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.SIGNING_PREVIEW.value, team_id="DEM-ATL"
    )
    result = orchestrate_preview(req, _DATA_DIR)
    d = result.to_dict()
    # Must round-trip through json without error.
    serialized = json.dumps(d, ensure_ascii=False, sort_keys=True)
    back = json.loads(serialized)
    assert "intelligence_summary" in back
    assert back["intelligence_summary"]["source"] == "deterministic-fake-adapter"


# --------------------------------------------------------------------------- #
# 2. preview_payload is deep-equal before/after summary
# --------------------------------------------------------------------------- #


def test_intelligence_summary_does_not_mutate_preview_payload_signing() -> None:
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.SIGNING_PREVIEW.value,
        team_id="DEM-ATL",
        objective="补强大个子",
    )
    result = orchestrate_preview(req, _DATA_DIR)
    # We cannot re-run a "pre-summary" code path in this branch; instead we
    # deepcopy the payload and confirm the summary builder does not mutate
    # a payload it is given (deep-equal after build_intelligence_summary).
    payload_copy = copy.deepcopy(result.preview_payload)
    build_intelligence_summary(
        intent=result.intent,
        status=result.status,
        requires_human_approval=result.requires_human_approval,
        preview_payload=payload_copy,
        agent_trace=result.agent_trace,
        warnings=list(result.warnings),
        limitations=list(result.limitations),
    )
    assert json.dumps(payload_copy, ensure_ascii=False, sort_keys=True) == (
        json.dumps(result.preview_payload, ensure_ascii=False, sort_keys=True)
    ), "build_intelligence_summary must not mutate preview_payload (signing)"


def test_intelligence_summary_does_not_mutate_preview_payload_trade() -> None:
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.TRADE_PREVIEW_DEMO.value,
    )
    result = orchestrate_preview(req, _DATA_DIR)
    payload_copy = copy.deepcopy(result.preview_payload)
    build_intelligence_summary(
        intent=result.intent,
        status=result.status,
        requires_human_approval=result.requires_human_approval,
        preview_payload=payload_copy,
        agent_trace=result.agent_trace,
        warnings=list(result.warnings),
        limitations=list(result.limitations),
    )
    assert json.dumps(payload_copy, ensure_ascii=False, sort_keys=True) == (
        json.dumps(result.preview_payload, ensure_ascii=False, sort_keys=True)
    ), "build_intelligence_summary must not mutate preview_payload (trade)"


def test_intelligence_summary_does_not_mutate_preview_payload_hold() -> None:
    req = AgentOrchestratorRequest(intent=OrchestratorIntent.HOLD.value)
    result = orchestrate_preview(req, _DATA_DIR)
    payload_copy = copy.deepcopy(result.preview_payload)
    build_intelligence_summary(
        intent=result.intent,
        status=result.status,
        requires_human_approval=result.requires_human_approval,
        preview_payload=payload_copy,
        agent_trace=result.agent_trace,
        warnings=list(result.warnings),
        limitations=list(result.limitations),
    )
    assert json.dumps(payload_copy, ensure_ascii=False, sort_keys=True) == (
        json.dumps(result.preview_payload, ensure_ascii=False, sort_keys=True)
    ), "build_intelligence_summary must not mutate preview_payload (hold)"


def test_intelligence_summary_does_not_mutate_preview_payload_blocked() -> None:
    req = AgentOrchestratorRequest(intent="execute_trade")
    result = orchestrate_preview(req, _DATA_DIR)
    payload_copy = copy.deepcopy(result.preview_payload)
    build_intelligence_summary(
        intent=result.intent,
        status=result.status,
        requires_human_approval=result.requires_human_approval,
        preview_payload=payload_copy,
        agent_trace=result.agent_trace,
        warnings=list(result.warnings),
        limitations=list(result.limitations),
    )
    assert json.dumps(payload_copy, ensure_ascii=False, sort_keys=True) == (
        json.dumps(result.preview_payload, ensure_ascii=False, sort_keys=True)
    ), "build_intelligence_summary must not mutate preview_payload (blocked)"


# --------------------------------------------------------------------------- #
# 3. Status drives the summary, not intent
# --------------------------------------------------------------------------- #


def test_summary_follows_status_not_intent_when_blocked() -> None:
    """Even with a signing_preview intent, if status is blocked the summary
    must say "安全拦截" and NOT be a signing recommendation."""
    summary = build_intelligence_summary(
        intent="signing_preview",
        status="blocked",
        requires_human_approval=True,
        preview_payload={"hold_reason": "mock blocked"},
        agent_trace={"steps": []},
        warnings=[],
        limitations=[],
    )
    blob = _summary_blob(summary)
    assert "拦截" in blob or "blocked" in blob.lower()
    assert "签约" not in blob or "未生成" in blob or "未在 allowlist" in blob
    # Must not recommend any player/team/amount.
    for bad in ("推荐签约", "签下", "补强方案", "应该签下"):
        assert bad not in blob, (
            f"blocked summary must not contain signing-recommendation text {bad!r}"
        )


def test_summary_follows_status_not_intent_when_hold() -> None:
    """A trade_preview_demo intent that ends in hold must produce a hold summary,
    not a trade recommendation."""
    summary = build_intelligence_summary(
        intent="trade_preview_demo",
        status="hold",
        requires_human_approval=True,
        preview_payload={"hold_reason": "预算不足", "status": "hold"},
        agent_trace={"steps": []},
        warnings=[],
        limitations=[],
    )
    blob = _summary_blob(summary)
    assert "暂不行动" in blob or "hold" in blob.lower()
    for bad in ("双方交易", "交易方案", "推荐交易", "↔"):
        assert bad not in blob, (
            f"hold summary must not contain trade-recommendation text {bad!r}"
        )


# --------------------------------------------------------------------------- #
# 4. Blocked / unsupported intent specifics
# --------------------------------------------------------------------------- #


def test_blocked_summary_says_intercepted_no_plan_no_player_reco() -> None:
    req = AgentOrchestratorRequest(intent="execute_trade")
    result = orchestrate_preview(req, _DATA_DIR)
    assert result.status == OrchestratorStatus.BLOCKED.value
    s = result.intelligence_summary
    assert s is not None
    blob = _summary_blob(s)
    assert "拦截" in blob or "安全" in blob
    # Must NOT claim a trade/signing plan was generated.
    for bad in (
        "已生成交易方案",
        "已生成签约方案",
        "交易方案",
        "补强方案",
        "推荐交易",
        "推荐签约",
        "executed",
        "applied",
        "committed",
        "auto_execute",
        "auto_approve",
        "已执行",
        "已落地",
        "已提交",
        "自动批准",
    ):
        assert bad.lower() not in blob, (
            f"blocked summary must not contain {bad!r}"
        )


def test_blocked_summary_mentions_read_only_and_human_approval() -> None:
    req = AgentOrchestratorRequest(intent="execute_trade")
    result = orchestrate_preview(req, _DATA_DIR)
    s = result.intelligence_summary
    assert s is not None
    # approval_note must state read-only / human approval.
    assert "只读" in s.approval_note or "人工" in s.approval_note
    # The source must be the deterministic fake adapter.
    assert s.source == "deterministic-fake-adapter"
    # The outer result must still require human approval.
    assert result.requires_human_approval is True


# --------------------------------------------------------------------------- #
# 5. Forbidden-word guard on summary text
# --------------------------------------------------------------------------- #


def _all_intents_results():
    intents = [
        OrchestratorIntent.SIGNING_PREVIEW.value,
        OrchestratorIntent.TRADE_PREVIEW_DEMO.value,
        OrchestratorIntent.HOLD.value,
        "execute_trade",
        "sign_player_automatically",
    ]
    return [
        orchestrate_preview(AgentOrchestratorRequest(intent=intent, team_id="DEM-ATL"), _DATA_DIR)
        for intent in intents
    ]


def test_summary_contains_no_english_forbidden_words() -> None:
    for r in _all_intents_results():
        s = r.intelligence_summary
        assert s is not None
        blob = _summary_blob(s)
        for w in _EN_FORBIDDEN:
            assert w not in blob, (
                f"[{r.intent}/{r.status}] forbidden english word {w!r} in summary blob"
            )


def test_summary_contains_no_chinese_forbidden_words() -> None:
    for r in _all_intents_results():
        s = r.intelligence_summary
        assert s is not None
        blob = _summary_blob(s)
        for w in _ZH_FORBIDDEN:
            assert w not in blob, (
                f"[{r.intent}/{r.status}] forbidden chinese word {w!r} in summary blob"
            )


def test_summary_contains_no_technical_ids() -> None:
    for r in _all_intents_results():
        s = r.intelligence_summary
        assert s is not None
        blob = _summary_blob(s)
        for w in _TECH_ID_FORBIDDEN:
            assert w not in blob, (
                f"[{r.intent}/{r.status}] technical id {w!r} leaked into summary"
            )


def test_summary_contains_no_execution_semantics_even_with_tricky_input() -> None:
    """Sanitize passthrough: even if a caller injects forbidden words via
    warnings/hold_reason, the summary must not surface them verbatim."""
    tricky_payloads = [
        {
            "intent": "signing_preview",
            "status": "awaiting_human_approval",
            "preview_payload": {
                "actions": [
                    {
                        "action_type": "signing",
                        "player_name": "Demo FA Quebec",
                        "position": "C",
                        "salary": 1000000,
                        "years": 1,
                        "is_valid": True,
                        "validation_status": "PASS",
                        "matched_need": "当前阵容缺中锋（live data, real-time）",
                        "cap_impact_summary": "current cap impact is executed automatically",
                    }
                ]
            },
            "warnings": ["auto_execute will be applied", "live NBA feed"],
        },
        {
            "intent": "trade_preview_demo",
            "status": "awaiting_human_approval",
            "preview_payload": {
                "trade_transaction": {
                    "team_a_id": "DEM-ATL",
                    "team_b_id": "DEM-PDX",
                    "outgoing_from_a": [],
                    "outgoing_from_b": [],
                },
                "preview": {"validation_result": {"status": "PASS", "is_valid": True}},
                "cap_impact_summary": "已执行committed实时数据",
            },
            "warnings": ["run_id=nba_2025_26 sourcepack snapshot_id=xyz"],
        },
        {
            "intent": "hold",
            "status": "hold",
            "preview_payload": {
                "hold_reason": "当前薪资空间不足，实时最新数据已提交",
                "status": "hold",
            },
            "warnings": [],
        },
        {
            "intent": "signing_preview",
            "status": "blocked",
            "preview_payload": {"hold_reason": "auto_execute is not allowed"},
            "warnings": [],
        },
    ]
    for tc in tricky_payloads:
        s = build_intelligence_summary(
            intent=tc["intent"],
            status=tc["status"],
            requires_human_approval=True,
            preview_payload=tc["preview_payload"],
            agent_trace={"steps": []},
            warnings=tc["warnings"],
            limitations=[],
        )
        blob = _summary_blob(s)
        for w in (
            _EN_FORBIDDEN | _ZH_FORBIDDEN | _TECH_ID_FORBIDDEN | _EXECUTION_SEMANTICS_FORBIDDEN
        ):
            assert w not in blob, (
                f"[tricky/{tc['intent']}/{tc['status']}] forbidden {w!r} leaked: ...{blob[max(0,blob.find(w)-20):blob.find(w)+30]}"
            )


# --------------------------------------------------------------------------- #
# 6. Source field and content rules
# --------------------------------------------------------------------------- #


def test_summary_source_is_deterministic_fake_adapter() -> None:
    for r in _all_intents_results():
        assert r.intelligence_summary.source == "deterministic-fake-adapter"


def test_summary_mentions_historical_or_demo_limitations() -> None:
    """Every summary must disclose demo/historical data and read-only
    nature — no silent claim of being live."""
    for r in _all_intents_results():
        s = r.intelligence_summary
        assert s is not None
        lim_blob = " ".join(s.data_limitations)
        assert (
            ("演示" in lim_blob or "历史" in lim_blob or "样本" in lim_blob or "sample" in lim_blob.lower())
        ), f"[{r.intent}/{r.status}] data_limitations must disclose demo/historical"
        assert "只读" in s.approval_note or "人工" in s.approval_note


# --------------------------------------------------------------------------- #
# 7. No forbidden imports in the intelligence module
# --------------------------------------------------------------------------- #


_INTELLIGENCE_MODULES = [
    "backend.app.services.agent_intelligence",
    "backend.app.models.agent_intelligence",
]

_FORBIDDEN_IMPORTS = [
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
]


def _module_source(module_name: str) -> str:
    mod = importlib.import_module(module_name)
    return Path(mod.__file__).read_text(encoding="utf-8")


@pytest.mark.parametrize("module_name", _INTELLIGENCE_MODULES)
def test_intelligence_modules_have_no_forbidden_imports(module_name: str) -> None:
    src = _module_source(module_name)
    for name in _FORBIDDEN_IMPORTS:
        assert f"import {name}" not in src and f"from {name}" not in src, (
            f"{module_name} must not import {name!r}"
        )


# --------------------------------------------------------------------------- #
# 8. Intelligence module must not call deterministic engines
# --------------------------------------------------------------------------- #


def test_intelligence_service_does_not_import_deterministic_engines() -> None:
    """agent_intelligence must not import transaction_rule_engine /
    trade_simulator / snapshot_loader — it only reads already-built
    preview_payload/trace/warnings/limitations."""
    src = _module_source("backend.app.services.agent_intelligence")
    for mod in (
        "transaction_rule_engine",
        "trade_simulator",
        "snapshot_loader",
        "proposal_builder",
        "proposal_evaluator",
        "evidence_service",
    ):
        assert f"import {mod}" not in src and f"from {mod}" not in src, (
            f"agent_intelligence must not import {mod!r}"
        )


# --------------------------------------------------------------------------- #
# 9. No data file mutation from build_intelligence_summary
# --------------------------------------------------------------------------- #


def test_build_intelligence_summary_does_not_modify_data_files() -> None:
    targets: List[Path] = []
    for name in ("players.json", "contracts.json", "teams.json"):
        p = _DATA_DIR / name
        if p.exists():
            targets.append(p)
    if _FIXTURE_SNAPSHOT_DIR.exists():
        for f in _FIXTURE_SNAPSHOT_DIR.rglob("*"):
            if f.is_file():
                targets.append(f)
    snap_dir = _DATA_DIR / "snapshots"
    if snap_dir.exists():
        for f in snap_dir.rglob("*"):
            if f.is_file():
                targets.append(f)
    before = _hash_data_files(targets)

    # Call build_intelligence_summary directly for every status.
    build_intelligence_summary(
        intent="signing_preview",
        status="awaiting_human_approval",
        requires_human_approval=True,
        preview_payload={
            "actions": [
                {
                    "action_type": "signing",
                    "player_name": "X",
                    "position": "C",
                    "salary": 1,
                    "years": 1,
                    "is_valid": True,
                    "validation_status": "PASS",
                }
            ]
        },
        agent_trace={"steps": []},
        warnings=[],
        limitations=[],
    )
    build_intelligence_summary(
        intent="trade_preview_demo",
        status="awaiting_human_approval",
        requires_human_approval=True,
        preview_payload={
            "trade_transaction": {"team_a_id": "A", "team_b_id": "B"},
            "preview": {"validation_result": {"status": "PASS", "is_valid": True}},
        },
        agent_trace={"steps": []},
        warnings=[],
        limitations=[],
    )
    build_intelligence_summary(
        intent="hold",
        status="hold",
        requires_human_approval=True,
        preview_payload={"status": "hold", "hold_reason": "x"},
        agent_trace={"steps": []},
        warnings=[],
        limitations=[],
    )
    build_intelligence_summary(
        intent="execute_trade",
        status="blocked",
        requires_human_approval=True,
        preview_payload={"hold_reason": "blocked"},
        agent_trace={"steps": []},
        warnings=[],
        limitations=[],
    )

    after = _hash_data_files(targets)
    assert before == after, (
        "build_intelligence_summary must not mutate data files or fixture snapshots"
    )


# --------------------------------------------------------------------------- #
# 10. AgentIntelligenceSummary shape
# --------------------------------------------------------------------------- #


def test_summary_field_shape_matches_contract() -> None:
    req = AgentOrchestratorRequest(
        intent=OrchestratorIntent.SIGNING_PREVIEW.value, team_id="DEM-ATL"
    )
    s = orchestrate_preview(req, _DATA_DIR).intelligence_summary
    assert s is not None
    expected_fields = {
        "summary_title",
        "plain_language_summary",
        "deterministic_verdict",
        "evidence_summary",
        "risk_summary",
        "approval_note",
        "data_limitations",
        "next_review_questions",
        "source",
    }
    assert set(s.to_dict().keys()) == expected_fields
    assert isinstance(s.evidence_summary, list)
    assert isinstance(s.risk_summary, list)
    assert isinstance(s.data_limitations, list)
    assert isinstance(s.next_review_questions, list)
    assert isinstance(s.summary_title, str)
    assert isinstance(s.plain_language_summary, str)
    assert isinstance(s.deterministic_verdict, str)
    assert isinstance(s.approval_note, str)
