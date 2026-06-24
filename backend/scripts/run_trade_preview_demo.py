"""CLI demo script for trade preview (M6-D).

This script is a **deterministic CLI demo** of the existing
``trade_simulator.preview_trade`` pipeline. It is NOT an MCP server,
NOT an MCP client, NOT an LLM agent, and NOT an OpenAI function-calling
harness. It does not call any LLM and does not touch the network.

It constructs a fixed demo two-team trade using existing sample data
in ``data/players.json`` / ``data/contracts.json``, runs it through
``trade_simulator.preview_trade`` (which internally calls
``transaction_rule_engine.validate_trade`` first), and prints the
result as a human-readable text brief or a stable JSON payload.

The demo trade:

    DEM-ATL sends pl-002 (Demo Player Bravo, SG, $22M) -> DEM-PDX
    DEM-PDX sends pl-007 (Demo Player Golf,  C,  $26M) -> DEM-ATL

This trade passes the MVP salary-matching rule for both teams
(incoming <= outgoing * 1.25 + 100_000) and gives DEM-ATL a Center
(their target position in the offseason goal). Neither player has a
no-trade clause.

The script does NOT write any output file, does NOT approve the
trade, and does NOT mutate any data file. ``requires_human_approval``
is always ``True``.

Run from repo root:

    python backend/scripts/run_trade_preview_demo.py
    python backend/scripts/run_trade_preview_demo.py --format json

Exit codes:

- 0: demo ran successfully.
- 1: argument error or runtime error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from dataclasses import is_dataclass
from enum import Enum


# --------------------------------------------------------------------------- #
# Repo-root discovery
# --------------------------------------------------------------------------- #
# Same pattern as run_offseason_demo.py: walk up from this file to find
# a directory that contains both ``backend/`` and ``data/``.


def _find_repo_root() -> Path:
    """Walk up from this script to find the repo root."""
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        if (parent / "backend").is_dir() and (parent / "data").is_dir():
            return parent
    return here.parents[2]


_REPO_ROOT = _find_repo_root()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_DATA_DIR = _REPO_ROOT / "data"


# --------------------------------------------------------------------------- #
# Demo trade definition
# --------------------------------------------------------------------------- #
# Fixed demo trade. Uses existing sample data — no data file mutation.

_DEMO_TRANSACTION_ID = "tx-trade-demo-001"
_DEMO_TEAM_A = "DEM-ATL"
_DEMO_TEAM_B = "DEM-PDX"
_DEMO_EVIDENCE_IDS = ("ev-007",)  # "Demo market: center market thin"


def _build_demo_trade():
    """Build the fixed demo ``TradeTransaction``.

    DEM-ATL sends pl-002 (SG, $22M) to DEM-PDX.
    DEM-PDX sends pl-007 (C, $26M) to DEM-ATL.

    Salaries come from ``data/contracts.json`` (ct-002 and ct-007).
    Neither player has a no-trade clause. The trade passes MVP salary
    matching for both teams.
    """
    from backend.app.models.transaction import (
        AssetType,
        TradeTransaction,
        TransactionAsset,
        TransactionType,
    )

    # pl-002: Demo Player Bravo, SG, DEM-ATL, salary $22M (ct-002)
    # pl-007: Demo Player Golf,  C,  DEM-PDX, salary $26M (ct-007)
    outgoing_from_a = (
        TransactionAsset(
            player_id="pl-002",
            contract_id="ct-002",
            salary=22_000_000,
            from_team_id=_DEMO_TEAM_A,
            to_team_id=_DEMO_TEAM_B,
            asset_type=AssetType.PLAYER_CONTRACT,
        ),
    )
    outgoing_from_b = (
        TransactionAsset(
            player_id="pl-007",
            contract_id="ct-007",
            salary=26_000_000,
            from_team_id=_DEMO_TEAM_B,
            to_team_id=_DEMO_TEAM_A,
            asset_type=AssetType.PLAYER_CONTRACT,
        ),
    )

    return TradeTransaction(
        transaction_id=_DEMO_TRANSACTION_ID,
        transaction_type=TransactionType.TWO_TEAM_TRADE,
        team_a_id=_DEMO_TEAM_A,
        team_b_id=_DEMO_TEAM_B,
        outgoing_from_a=outgoing_from_a,
        outgoing_from_b=outgoing_from_b,
        evidence_ids=_DEMO_EVIDENCE_IDS,
        requires_human_approval=True,
        sample_data=True,
    )


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #


def _enum_to_str(obj: Any) -> Any:
    """Convert enums to their string value; pass through other primitives."""
    if isinstance(obj, Enum):
        return obj.value
    return obj


def _serialize_asset(asset) -> Dict[str, Any]:
    """Serialize a ``TransactionAsset`` to a JSON-stable dict."""
    return {
        "player_id": asset.player_id,
        "contract_id": asset.contract_id,
        "salary": asset.salary,
        "from_team_id": asset.from_team_id,
        "to_team_id": asset.to_team_id,
        "asset_type": _enum_to_str(asset.asset_type),
    }


def _serialize_issue(issue) -> Dict[str, Any]:
    """Serialize a ``ValidationIssue`` to a JSON-stable dict."""
    return {
        "code": issue.code,
        "message": issue.message,
        "severity": _enum_to_str(issue.severity),
        "field": issue.field,
    }


def _serialize_cap_summary(summary) -> Optional[Dict[str, Any]]:
    """Serialize a ``CapSheetSummary`` to a JSON-stable dict."""
    if summary is None:
        return None
    return {
        "team_id": summary.team_id,
        "season": summary.season,
        "roster_count": summary.roster_count,
        "total_salary": summary.total_salary,
        "cap_space": summary.cap_space,
        "tax_distance": summary.tax_distance,
        "first_apron_distance": summary.first_apron_distance,
        "second_apron_distance": summary.second_apron_distance,
    }


def _serialize_validation_result(vr) -> Dict[str, Any]:
    """Serialize a ``ValidationResult`` to a JSON-stable dict."""
    return {
        "transaction_id": vr.transaction_id,
        "transaction_type": _enum_to_str(vr.transaction_type),
        "status": _enum_to_str(vr.status),
        "is_valid": vr.is_valid,
        "issues": [_serialize_issue(i) for i in vr.issues],
        "warnings": [_serialize_issue(w) for w in vr.warnings],
        "cap_summary_before": _serialize_cap_summary(vr.cap_summary_before),
        "cap_summary_after": _serialize_cap_summary(vr.cap_summary_after),
        "evidence_ids": list(vr.evidence_ids),
        "requires_human_approval": vr.requires_human_approval,
        "limitations": list(vr.limitations),
    }


def _serialize_position_need(need) -> Dict[str, Any]:
    """Serialize a ``PositionNeed`` to a JSON-stable dict."""
    return {
        "position": _enum_to_str(need.position),
        "current_count": need.current_count,
        "target_count": need.target_count,
        "priority": _enum_to_str(need.priority),
        "reason": need.reason,
    }


def _serialize_roster_need_report(report) -> Optional[Dict[str, Any]]:
    """Serialize a ``RosterNeedReport`` to a JSON-stable dict."""
    if report is None:
        return None
    return {
        "team_id": report.team_id,
        "roster_count": report.roster_count,
        "needs": [_serialize_position_need(n) for n in report.needs],
        "strengths": [_enum_to_str(s) for s in report.strengths],
        "limitations": list(report.limitations),
    }


def _serialize_depth_chart_slot(slot) -> Dict[str, Any]:
    """Serialize a ``DepthChartSlot`` to a JSON-stable dict."""
    starter = None
    if slot.starter is not None:
        starter = {
            "player_id": slot.starter.player_id,
            "name": slot.starter.name,
            "team_id": slot.starter.team_id,
            "position": _enum_to_str(slot.starter.position),
            "role": slot.starter.role,
            "salary": slot.starter.salary,
            "sample_data": slot.starter.sample_data,
        }
    backups = [
        {
            "player_id": p.player_id,
            "name": p.name,
            "team_id": p.team_id,
            "position": _enum_to_str(p.position),
            "role": p.role,
            "salary": p.salary,
            "sample_data": p.sample_data,
        }
        for p in slot.backups
    ]
    return {
        "position": _enum_to_str(slot.position),
        "starter": starter,
        "backups": backups,
        "need_level": _enum_to_str(slot.need_level),
    }


def _serialize_depth_chart(chart) -> Optional[Dict[str, Any]]:
    """Serialize a ``ProjectedDepthChart`` to a JSON-stable dict."""
    if chart is None:
        return None
    return {
        "team_id": chart.team_id,
        "slots": [_serialize_depth_chart_slot(s) for s in chart.slots],
        "roster_count": chart.roster_count,
        "limitations": list(chart.limitations),
    }


def _serialize_trade_transaction(tx) -> Dict[str, Any]:
    """Serialize the original ``TradeTransaction`` for display."""
    return {
        "transaction_id": tx.transaction_id,
        "transaction_type": _enum_to_str(tx.transaction_type),
        "team_a_id": tx.team_a_id,
        "team_b_id": tx.team_b_id,
        "outgoing_from_a": [_serialize_asset(a) for a in tx.outgoing_from_a],
        "outgoing_from_b": [_serialize_asset(a) for a in tx.outgoing_from_b],
        "evidence_ids": list(tx.evidence_ids),
        "requires_human_approval": tx.requires_human_approval,
        "sample_data": tx.sample_data,
    }


def build_trade_preview_payload(data_dir: Path | str = "data") -> Dict[str, Any]:
    """Build a stable JSON-serializable trade preview payload.

    Constructs the demo trade, runs ``trade_simulator.preview_trade``,
    and serializes the full result. Does NOT call any LLM, does NOT use
    MCP, does NOT write to disk, does NOT approve the trade.
    """
    from backend.app.services.trade_simulator import preview_trade

    trade = _build_demo_trade()
    preview = preview_trade(trade, data_dir)

    # Compute salary matching summary for display.
    out_a_salary = sum(a.salary for a in trade.outgoing_from_a)
    out_b_salary = sum(a.salary for a in trade.outgoing_from_b)
    in_a_salary = out_b_salary  # incoming to A = outgoing from B
    in_b_salary = out_a_salary  # incoming to B = outgoing from A

    salary_matching = {
        "rule": "incoming <= outgoing * 1.25 + 100000",
        "team_a": {
            "team_id": trade.team_a_id,
            "outgoing_salary": out_a_salary,
            "incoming_salary": in_a_salary,
            "threshold": int(out_a_salary * 1.25) + 100_000,
            "passed": in_a_salary <= out_a_salary * 1.25 + 100_000,
        },
        "team_b": {
            "team_id": trade.team_b_id,
            "outgoing_salary": out_b_salary,
            "incoming_salary": in_b_salary,
            "threshold": int(out_b_salary * 1.25) + 100_000,
            "passed": in_b_salary <= out_b_salary * 1.25 + 100_000,
        },
    }

    # Roster impact summary (team A focus, matching preview_trade behavior).
    roster_impact_summary = None
    if preview.roster_need_after is not None:
        needs_count = len(preview.roster_need_after.needs)
        strengths_count = len(preview.roster_need_after.strengths)
        roster_impact_summary = (
            f"Team A ({trade.team_a_id}) post-trade roster: "
            f"{preview.roster_need_after.roster_count} players, "
            f"{needs_count} position need(s), "
            f"{strengths_count} position strength(s)."
        )

    # Depth chart impact summary.
    depth_chart_impact_summary = None
    if preview.depth_chart_after is not None:
        filled_slots = sum(
            1 for s in preview.depth_chart_after.slots if s.starter is not None
        )
        depth_chart_impact_summary = (
            f"Team A ({trade.team_a_id}) post-trade depth chart: "
            f"{filled_slots}/{len(preview.depth_chart_after.slots)} "
            f"positions with a starter."
        )

    # Cap impact summary.
    cap_impact_summary = None
    if preview.cap_summary_after is not None:
        cap_impact_summary = (
            f"Team A ({trade.team_a_id}) post-trade total_salary: "
            f"${preview.cap_summary_after.total_salary:,}, "
            f"cap_space: ${preview.cap_summary_after.cap_space:,}."
        )

    return {
        "trade_transaction": _serialize_trade_transaction(trade),
        "preview": {
            "transaction_id": preview.transaction_id,
            "validation_result": _serialize_validation_result(
                preview.validation_result
            ),
            "roster_need_after": _serialize_roster_need_report(
                preview.roster_need_after
            ),
            "depth_chart_after": _serialize_depth_chart(
                preview.depth_chart_after
            ),
            "cap_summary_after": _serialize_cap_summary(
                preview.cap_summary_after
            ),
            "requires_human_approval": preview.requires_human_approval,
            "limitations": list(preview.limitations),
        },
        "salary_matching": salary_matching,
        "roster_impact_summary": roster_impact_summary,
        "depth_chart_impact_summary": depth_chart_impact_summary,
        "cap_impact_summary": cap_impact_summary,
        "requires_human_approval": preview.requires_human_approval,
        "sample_data": True,
    }


# --------------------------------------------------------------------------- #
# Text brief
# --------------------------------------------------------------------------- #


def build_trade_preview_brief(data_dir: Path | str = "data") -> str:
    """Build a deterministic text brief for the trade preview demo."""
    payload = build_trade_preview_payload(data_dir)
    tx = payload["trade_transaction"]
    pv = payload["preview"]
    vr = pv["validation_result"]
    sm = payload["salary_matching"]

    lines: List[str] = []
    lines.append(
        "============================================================"
    )
    lines.append(
        " FrontOffice-Offseason-Agent  |  TRADE PREVIEW (sample data)"
    )
    lines.append(
        "============================================================"
    )
    lines.append("")
    lines.append(f"transaction_id        : {tx['transaction_id']}")
    lines.append(f"transaction_type      : {tx['transaction_type']}")
    lines.append(f"team_a_id             : {tx['team_a_id']}")
    lines.append(f"team_b_id             : {tx['team_b_id']}")
    lines.append(f"validation status     : {vr['status']}")
    lines.append(f"is_valid              : {vr['is_valid']}")
    lines.append(
        f"requires_human_approval: {pv['requires_human_approval']}"
    )
    lines.append(f"sample_data           : {payload['sample_data']}")
    lines.append("")

    lines.append("--- Outgoing from A (to B) ---")
    for a in tx["outgoing_from_a"]:
        lines.append(
            f"  player_id={a['player_id']}  salary=${a['salary']:,}  "
            f"asset_type={a['asset_type']}"
        )
    lines.append("")
    lines.append("--- Outgoing from B (to A) ---")
    for a in tx["outgoing_from_b"]:
        lines.append(
            f"  player_id={a['player_id']}  salary=${a['salary']:,}  "
            f"asset_type={a['asset_type']}"
        )
    lines.append("")

    lines.append("--- Salary Matching ---")
    lines.append(f"  rule: {sm['rule']}")
    for side in ("team_a", "team_b"):
        s = sm[side]
        lines.append(
            f"  {s['team_id']}: outgoing=${s['outgoing_salary']:,}  "
            f"incoming=${s['incoming_salary']:,}  "
            f"threshold=${s['threshold']:,}  passed={s['passed']}"
        )
    lines.append("")

    lines.append("--- Validation Issues ---")
    if vr["issues"]:
        for i, iss in enumerate(vr["issues"]):
            lines.append(
                f"  [{i}] code={iss['code']}  severity={iss['severity']}  "
                f"field={iss['field']}"
            )
            lines.append(f"       {iss['message']}")
    else:
        lines.append("  (no issues)")
    lines.append("")

    if vr["warnings"]:
        lines.append("--- Warnings ---")
        for w in vr["warnings"]:
            lines.append(f"  code={w['code']}  {w['message']}")
        lines.append("")

    if payload["roster_impact_summary"]:
        lines.append("--- Roster Impact ---")
        lines.append(f"  {payload['roster_impact_summary']}")
        lines.append("")

    if payload["depth_chart_impact_summary"]:
        lines.append("--- Depth Chart Impact ---")
        lines.append(f"  {payload['depth_chart_impact_summary']}")
        lines.append("")

    if payload["cap_impact_summary"]:
        lines.append("--- Cap Impact ---")
        lines.append(f"  {payload['cap_impact_summary']}")
        lines.append("")

    lines.append("--- Limitations ---")
    for i, lim in enumerate(pv["limitations"]):
        lines.append(f"  [{i}] {lim}")
    lines.append("")

    lines.append(
        "------------------------------------------------------------"
    )
    lines.append(
        " End of trade preview  |  preview only  |  requires human approval"
    )
    lines.append(
        "------------------------------------------------------------"
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="run_trade_preview_demo.py",
        description=(
            "FrontOffice-Offseason-Agent trade preview CLI demo. "
            "Constructs a fixed demo two-team trade using existing "
            "sample data, runs it through trade_simulator.preview_trade, "
            "and prints the result as text or JSON. Sample data only "
            "— not a real NBA prediction, not an approved transaction."
        ),
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format: 'text' (default) or 'json'.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint. Returns the exit code."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        if args.format == "json":
            payload = build_trade_preview_payload(_DATA_DIR)
            print(json.dumps(payload, sort_keys=True, indent=2))
        else:
            brief = build_trade_preview_brief(_DATA_DIR)
            print(brief)
    except Exception as exc:  # noqa: BLE001 — surface any runtime error clearly
        print(f"ERROR: trade preview demo failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
