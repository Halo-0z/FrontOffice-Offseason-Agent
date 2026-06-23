/**
 * Static demo proposal payloads for the M6-A frontend viewer.
 *
 * These payloads are **snapshots** of the CLI JSON output produced by:
 *
 *   python backend/scripts/run_offseason_demo.py --format json
 *   python backend/scripts/run_offseason_demo.py \
 *     --target-position C --max-salary 15000000 --max-candidates 2 \
 *     --format json
 *
 * They are **sample / simulation data**. They are NOT real NBA data,
 * NOT real predictions, and NOT approved transactions. Every action
 * is a preview that requires human approval.
 *
 * The frontend viewer does NOT call any backend API, does NOT call any
 * LLM, does NOT use MCP, and does NOT mutate any data. It only renders
 * these static payloads for demonstration.
 *
 * Milestone: M6-A.
 */

export interface ProposalEvidenceRef {
  evidence_id: string;
  title: string;
  source: string;
  evidence_type: string;
  sample_data: boolean;
}

export interface ProposalRisk {
  code: string;
  level: string;
  summary: string;
  evidence_ids: string[];
}

export interface ProposalAction {
  action_id: string;
  action_type: string;
  team_id: string;
  transaction_id: string | null;
  player_id: string | null;
  player_name: string | null;
  position: string | null;
  salary: number | null;
  years: number | null;
  validation_status: string;
  is_valid: boolean;
  requires_human_approval: boolean;
  fit_score: number | null;
  matched_need: string | null;
  cap_impact_summary: string;
  roster_impact_summary: string;
  depth_chart_impact_summary: string;
  evidence_ids: string[];
  limitations: string[];
}

export interface ToolCallRecord {
  tool_name: string;
  status: string;
  input_summary: string;
  output_summary: string;
  fallback_reason: string | null;
  evidence_ids: string[];
}

export interface StructuredProposal {
  proposal_id: string;
  team_id: string;
  objective: string;
  status: string;
  recommended_actions: ProposalAction[];
  risks: ProposalRisk[];
  evidence_refs: ProposalEvidenceRef[];
  tool_call_trace: ToolCallRecord[];
  cap_summary: string;
  roster_need_summary: string;
  depth_chart_summary: string;
  fallback_reasons: string[];
  limitations: string[];
  requires_human_approval: boolean;
  sample_data: boolean;
}

export interface EvaluationIssue {
  code: string;
  severity: string;
  summary: string;
  action_id: string | null;
  evidence_ids: string[];
  remediation: string;
}

export interface ProposalEvaluation {
  proposal_id: string;
  team_id: string;
  status: string;
  issues: EvaluationIssue[];
  passed_checks: string[];
  failed_checks: string[];
  warnings: string[];
  limitations: string[];
  sample_data: boolean;
}

export interface DemoPayload {
  proposal: StructuredProposal;
  evaluation: ProposalEvaluation;
  actions: ProposalAction[];
  evidence: ProposalEvidenceRef[];
  tool_trace: ToolCallRecord[];
  limitations: string[];
  requires_human_approval: boolean;
  sample_data: boolean;
}

export interface ScenarioMeta {
  id: string;
  label: string;
  description: string;
  max_salary: number;
  payload: DemoPayload;
}

// ----------------------------------------------------------------------- //
// Default scenario: DEM-ATL, target C, max salary 20M -> RECOMMENDED + PASS
// ----------------------------------------------------------------------- //

const defaultPayload: DemoPayload = {
  proposal: {
    proposal_id: "prop-DEM-ATL-add-frontcourt-help",
    team_id: "DEM-ATL",
    objective: "Add frontcourt help",
    status: "RECOMMENDED",
    recommended_actions: [
      {
        action_id: "act-0-m4b-preview-0-fa-005",
        action_type: "SIGNING",
        team_id: "DEM-ATL",
        transaction_id: "m4b-preview-0-fa-005",
        player_id: "fa-005",
        player_name: "Demo FA Quebec",
        position: "C",
        salary: 18000000,
        years: 1,
        validation_status: "PASS",
        is_valid: true,
        requires_human_approval: true,
        fit_score: 0.7781,
        matched_need: "C: have 0, target 2 (priority=high)",
        cap_impact_summary: "after: total_salary=92000000, cap_space=48000000",
        roster_impact_summary:
          "roster_count=5, needs=[PG:1/2(medium), SG:1/2(medium), SF:1/2(medium), PF:1/2(medium), C:1/2(medium)]",
        depth_chart_impact_summary:
          "PG:pl-001/medium,SG:pl-002/medium,SF:pl-003/medium,PF:pl-004/medium,C:fa-005/medium",
        evidence_ids: ["ev-001", "ev-005"],
        limitations: [
          "MVP preview: in-memory only, never writes to data files.",
          "Post-transaction depth chart uses the same heuristic as current depth chart.",
          "Trade preview does not simulate multi-year contract decay.",
          "A passed preview still requires human approval before any state change.",
        ],
      },
    ],
    risks: [
      {
        code: "sample_data",
        level: "LOW",
        summary:
          "Proposal is built from DEMO/SAMPLE/SIMULATION data; not real NBA data.",
        evidence_ids: [],
      },
    ],
    evidence_refs: [
      {
        evidence_id: "ev-005",
        title: "Demo risk: second apron",
        source: "demo-cap-note",
        evidence_type: "cap_context",
        sample_data: true,
      },
      {
        evidence_id: "ev-007",
        title: "Demo market: center market thin",
        source: "demo-market-note",
        evidence_type: "market_context",
        sample_data: true,
      },
      {
        evidence_id: "ev-003",
        title: "Demo cap space check",
        source: "demo-cap-note",
        evidence_type: "cap_context",
        sample_data: true,
      },
      {
        evidence_id: "ev-008",
        title: "Demo transaction: minimum signing fits cap",
        source: "demo-front-office-note",
        evidence_type: "transaction_context",
        sample_data: true,
      },
      {
        evidence_id: "ev-001",
        title: "Demo need: starting PG",
        source: "demo-scouting-note",
        evidence_type: "roster_context",
        sample_data: true,
      },
    ],
    tool_call_trace: [
      {
        tool_name: "cap_sheet_service.summarize_cap_sheet",
        status: "SUCCESS",
        input_summary: "team_id=DEM-ATL",
        output_summary:
          "total_salary=74000000,cap_space=66000000,roster_count=4",
        fallback_reason: null,
        evidence_ids: [],
      },
      {
        tool_name: "roster_need_service.evaluate_roster_needs",
        status: "SUCCESS",
        input_summary: "team_id=DEM-ATL",
        output_summary: "roster_count=4,needs=[C,PG,SG,SF,PF]",
        fallback_reason: null,
        evidence_ids: [],
      },
      {
        tool_name: "depth_chart_projector.project_current_depth_chart",
        status: "SUCCESS",
        input_summary: "team_id=DEM-ATL",
        output_summary: "PG:pl-001,SG:pl-002,SF:pl-003,PF:pl-004,C:None",
        fallback_reason: null,
        evidence_ids: [],
      },
      {
        tool_name: "free_agent_service.rank_free_agents_for_team",
        status: "SUCCESS",
        input_summary:
          "team_id=DEM-ATL,target_positions=('C',),max_salary=20000000,max_candidates=2",
        output_summary: "1 fits=[fa-005:0.778]",
        fallback_reason: null,
        evidence_ids: [],
      },
      {
        tool_name: "trade_simulator.preview_signing",
        status: "SUCCESS",
        input_summary:
          "player_id=fa-005,salary=18000000,type=SIMPLE_FA_SIGNING",
        output_summary: "tx=m4b-preview-0-fa-005,is_valid=True",
        fallback_reason: null,
        evidence_ids: ["ev-001", "ev-005"],
      },
      {
        tool_name: "evidence_service.search_evidence",
        status: "SUCCESS",
        input_summary:
          "query='center need cap flexibility',team_id=DEM-ATL",
        output_summary: "matched=5,missing=0",
        fallback_reason: null,
        evidence_ids: [],
      },
    ],
    cap_summary:
      "total_salary=74000000, cap_space=66000000, tax_distance=96000000, roster_count=4",
    roster_need_summary:
      "roster_count=4, needs=[C:0/2(high), PG:1/2(medium), SG:1/2(medium), SF:1/2(medium), PF:1/2(medium)]",
    depth_chart_summary:
      "PG:pl-001/medium,SG:pl-002/medium,SF:pl-003/medium,PF:pl-004/medium,C:None/high",
    fallback_reasons: [],
    limitations: [
      "M4-C deterministic structured proposal builder only.",
      "No LLM call.",
      "No MCP server/client.",
      "No external NBA API or live salary data.",
      "All actions are previews and require human approval.",
      "Proposal is derived from sample/simulation data.",
      "M4-B deterministic local tool orchestration only.",
      "All transaction outputs are previews and require human approval.",
    ],
    requires_human_approval: true,
    sample_data: true,
  },
  evaluation: {
    proposal_id: "prop-DEM-ATL-add-frontcourt-help",
    team_id: "DEM-ATL",
    status: "PASS",
    issues: [
      {
        code: "sample_data_only",
        severity: "INFO",
        summary:
          "Proposal is built from DEMO/SAMPLE/SIMULATION data; not real NBA data.",
        action_id: null,
        evidence_ids: [],
        remediation: "No action needed; informational note.",
      },
    ],
    passed_checks: [
      "human_approval_guardrail",
      "validation_guardrail",
      "evidence_guardrail",
      "tool_trace_guardrail",
      "fallback_consistency_guardrail",
      "sample_data_guardrail",
    ],
    failed_checks: [],
    warnings: [],
    limitations: [
      "M4-D deterministic proposal evaluation only.",
      "No LLM call.",
      "No MCP.",
      "No external NBA API or live salary data.",
      "Evaluation does not approve transactions.",
    ],
    sample_data: true,
  },
  actions: [
    {
      action_id: "act-0-m4b-preview-0-fa-005",
      action_type: "SIGNING",
      team_id: "DEM-ATL",
      transaction_id: "m4b-preview-0-fa-005",
      player_id: "fa-005",
      player_name: "Demo FA Quebec",
      position: "C",
      salary: 18000000,
      years: 1,
      validation_status: "PASS",
      is_valid: true,
      requires_human_approval: true,
      fit_score: 0.7781,
      matched_need: "C: have 0, target 2 (priority=high)",
      cap_impact_summary: "after: total_salary=92000000, cap_space=48000000",
      roster_impact_summary:
        "roster_count=5, needs=[PG:1/2(medium), SG:1/2(medium), SF:1/2(medium), PF:1/2(medium), C:1/2(medium)]",
      depth_chart_impact_summary:
        "PG:pl-001/medium,SG:pl-002/medium,SF:pl-003/medium,PF:pl-004/medium,C:fa-005/medium",
      evidence_ids: ["ev-001", "ev-005"],
      limitations: [
        "MVP preview: in-memory only, never writes to data files.",
        "Post-transaction depth chart uses the same heuristic as current depth chart.",
        "Trade preview does not simulate multi-year contract decay.",
        "A passed preview still requires human approval before any state change.",
      ],
    },
  ],
  evidence: [
    {
      evidence_id: "ev-005",
      title: "Demo risk: second apron",
      source: "demo-cap-note",
      evidence_type: "cap_context",
      sample_data: true,
    },
    {
      evidence_id: "ev-007",
      title: "Demo market: center market thin",
      source: "demo-market-note",
      evidence_type: "market_context",
      sample_data: true,
    },
    {
      evidence_id: "ev-003",
      title: "Demo cap space check",
      source: "demo-cap-note",
      evidence_type: "cap_context",
      sample_data: true,
    },
    {
      evidence_id: "ev-008",
      title: "Demo transaction: minimum signing fits cap",
      source: "demo-front-office-note",
      evidence_type: "transaction_context",
      sample_data: true,
    },
    {
      evidence_id: "ev-001",
      title: "Demo need: starting PG",
      source: "demo-scouting-note",
      evidence_type: "roster_context",
      sample_data: true,
    },
  ],
  tool_trace: [
    {
      tool_name: "cap_sheet_service.summarize_cap_sheet",
      status: "SUCCESS",
      input_summary: "team_id=DEM-ATL",
      output_summary:
        "total_salary=74000000,cap_space=66000000,roster_count=4",
      fallback_reason: null,
      evidence_ids: [],
    },
    {
      tool_name: "roster_need_service.evaluate_roster_needs",
      status: "SUCCESS",
      input_summary: "team_id=DEM-ATL",
      output_summary: "roster_count=4,needs=[C,PG,SG,SF,PF]",
      fallback_reason: null,
      evidence_ids: [],
    },
    {
      tool_name: "depth_chart_projector.project_current_depth_chart",
      status: "SUCCESS",
      input_summary: "team_id=DEM-ATL",
      output_summary: "PG:pl-001,SG:pl-002,SF:pl-003,PF:pl-004,C:None",
      fallback_reason: null,
      evidence_ids: [],
    },
    {
      tool_name: "free_agent_service.rank_free_agents_for_team",
      status: "SUCCESS",
      input_summary:
        "team_id=DEM-ATL,target_positions=('C',),max_salary=20000000,max_candidates=2",
      output_summary: "1 fits=[fa-005:0.778]",
      fallback_reason: null,
      evidence_ids: [],
    },
    {
      tool_name: "trade_simulator.preview_signing",
      status: "SUCCESS",
      input_summary:
        "player_id=fa-005,salary=18000000,type=SIMPLE_FA_SIGNING",
      output_summary: "tx=m4b-preview-0-fa-005,is_valid=True",
      fallback_reason: null,
      evidence_ids: ["ev-001", "ev-005"],
    },
    {
      tool_name: "evidence_service.search_evidence",
      status: "SUCCESS",
      input_summary:
        "query='center need cap flexibility',team_id=DEM-ATL",
      output_summary: "matched=5,missing=0",
      fallback_reason: null,
      evidence_ids: [],
    },
  ],
  limitations: [
    "M4-C deterministic structured proposal builder only.",
    "No LLM call.",
    "No MCP server/client.",
    "No external NBA API or live salary data.",
    "All actions are previews and require human approval.",
    "Proposal is derived from sample/simulation data.",
    "M4-B deterministic local tool orchestration only.",
    "All transaction outputs are previews and require human approval.",
    "M5-A deterministic proposal viewer / CLI demo only.",
    "No MCP.",
    "Demo uses sample/simulation data, not real NBA predictions.",
  ],
  requires_human_approval: true,
  sample_data: true,
};

// ----------------------------------------------------------------------- //
// Strict-budget scenario: max salary 15M -> NO_ACTION + HOLD + fallback
// ----------------------------------------------------------------------- //

const strictBudgetPayload: DemoPayload = {
  proposal: {
    proposal_id: "prop-DEM-ATL-add-frontcourt-help",
    team_id: "DEM-ATL",
    objective: "Add frontcourt help",
    status: "NO_ACTION",
    recommended_actions: [
      {
        action_id: "act-0-hold-DEM-ATL",
        action_type: "HOLD",
        team_id: "DEM-ATL",
        transaction_id: null,
        player_id: null,
        player_name: null,
        position: null,
        salary: null,
        years: null,
        validation_status: "NOT_VALIDATED",
        is_valid: false,
        requires_human_approval: true,
        fit_score: null,
        matched_need: null,
        cap_impact_summary: "No action; no candidates matched.",
        roster_impact_summary: "No action; roster unchanged.",
        depth_chart_impact_summary: "No action; depth chart unchanged.",
        evidence_ids: [],
        limitations: [
          "No free-agent candidates matched the goal constraints.",
        ],
      },
    ],
    risks: [
      {
        code: "no_matching_candidate",
        level: "HIGH",
        summary:
          "No free-agent candidates matched the goal constraints (target_positions / max_salary / max_candidates).",
        evidence_ids: [],
      },
      {
        code: "sample_data",
        level: "LOW",
        summary:
          "Proposal is built from DEMO/SAMPLE/SIMULATION data; not real NBA data.",
        evidence_ids: [],
      },
    ],
    evidence_refs: [
      {
        evidence_id: "ev-005",
        title: "Demo risk: second apron",
        source: "demo-cap-note",
        evidence_type: "cap_context",
        sample_data: true,
      },
      {
        evidence_id: "ev-007",
        title: "Demo market: center market thin",
        source: "demo-market-note",
        evidence_type: "market_context",
        sample_data: true,
      },
      {
        evidence_id: "ev-003",
        title: "Demo cap space check",
        source: "demo-cap-note",
        evidence_type: "cap_context",
        sample_data: true,
      },
      {
        evidence_id: "ev-008",
        title: "Demo transaction: minimum signing fits cap",
        source: "demo-front-office-note",
        evidence_type: "transaction_context",
        sample_data: true,
      },
      {
        evidence_id: "ev-001",
        title: "Demo need: starting PG",
        source: "demo-scouting-note",
        evidence_type: "roster_context",
        sample_data: true,
      },
    ],
    tool_call_trace: [
      {
        tool_name: "cap_sheet_service.summarize_cap_sheet",
        status: "SUCCESS",
        input_summary: "team_id=DEM-ATL",
        output_summary:
          "total_salary=74000000,cap_space=66000000,roster_count=4",
        fallback_reason: null,
        evidence_ids: [],
      },
      {
        tool_name: "roster_need_service.evaluate_roster_needs",
        status: "SUCCESS",
        input_summary: "team_id=DEM-ATL",
        output_summary: "roster_count=4,needs=[C,PG,SG,SF,PF]",
        fallback_reason: null,
        evidence_ids: [],
      },
      {
        tool_name: "depth_chart_projector.project_current_depth_chart",
        status: "SUCCESS",
        input_summary: "team_id=DEM-ATL",
        output_summary: "PG:pl-001,SG:pl-002,SF:pl-003,PF:pl-004,C:None",
        fallback_reason: null,
        evidence_ids: [],
      },
      {
        tool_name: "free_agent_service.rank_free_agents_for_team",
        status: "FALLBACK",
        input_summary:
          "team_id=DEM-ATL,target_positions=('C',),max_salary=15000000,max_candidates=2",
        output_summary: "0 fits",
        fallback_reason: "No free-agent candidates after filtering.",
        evidence_ids: [],
      },
      {
        tool_name: "trade_simulator.preview_signing",
        status: "FALLBACK",
        input_summary: "no free-agent candidates",
        output_summary: "0 previews",
        fallback_reason: "Skipped: no free-agent candidates to preview.",
        evidence_ids: [],
      },
      {
        tool_name: "evidence_service.search_evidence",
        status: "SUCCESS",
        input_summary:
          "query='center need cap flexibility',team_id=DEM-ATL",
        output_summary: "matched=5,missing=0",
        fallback_reason: null,
        evidence_ids: [],
      },
    ],
    cap_summary:
      "total_salary=74000000, cap_space=66000000, tax_distance=96000000, roster_count=4",
    roster_need_summary:
      "roster_count=4, needs=[C:0/2(high), PG:1/2(medium), SG:1/2(medium), SF:1/2(medium), PF:1/2(medium)]",
    depth_chart_summary:
      "PG:pl-001/medium,SG:pl-002/medium,SF:pl-003/medium,PF:pl-004/medium,C:None/high",
    fallback_reasons: [
      "free_agent_service.rank_free_agents_for_team: No free-agent candidates after filtering.",
      "trade_simulator.preview_signing: Skipped: no free-agent candidates to preview.",
      "free_agent_service returned no candidates after filtering; signing_previews is empty.",
    ],
    limitations: [
      "M4-C deterministic structured proposal builder only.",
      "No LLM call.",
      "No MCP server/client.",
      "No external NBA API or live salary data.",
      "All actions are previews and require human approval.",
      "Proposal is derived from sample/simulation data.",
      "M4-B deterministic local tool orchestration only.",
      "All transaction outputs are previews and require human approval.",
      "free_agent_service returned no candidates after filtering; signing_previews is empty.",
    ],
    requires_human_approval: true,
    sample_data: true,
  },
  evaluation: {
    proposal_id: "prop-DEM-ATL-add-frontcourt-help",
    team_id: "DEM-ATL",
    status: "PASS",
    issues: [
      {
        code: "sample_data_only",
        severity: "INFO",
        summary:
          "Proposal is built from DEMO/SAMPLE/SIMULATION data; not real NBA data.",
        action_id: null,
        evidence_ids: [],
        remediation: "No action needed; informational note.",
      },
    ],
    passed_checks: [
      "human_approval_guardrail",
      "validation_guardrail",
      "evidence_guardrail",
      "tool_trace_guardrail",
      "fallback_consistency_guardrail",
      "sample_data_guardrail",
    ],
    failed_checks: [],
    warnings: [],
    limitations: [
      "M4-D deterministic proposal evaluation only.",
      "No LLM call.",
      "No MCP.",
      "No external NBA API or live salary data.",
      "Evaluation does not approve transactions.",
    ],
    sample_data: true,
  },
  actions: [
    {
      action_id: "act-0-hold-DEM-ATL",
      action_type: "HOLD",
      team_id: "DEM-ATL",
      transaction_id: null,
      player_id: null,
      player_name: null,
      position: null,
      salary: null,
      years: null,
      validation_status: "NOT_VALIDATED",
      is_valid: false,
      requires_human_approval: true,
      fit_score: null,
      matched_need: null,
      cap_impact_summary: "No action; no candidates matched.",
      roster_impact_summary: "No action; roster unchanged.",
      depth_chart_impact_summary: "No action; depth chart unchanged.",
      evidence_ids: [],
      limitations: [
        "No free-agent candidates matched the goal constraints.",
      ],
    },
  ],
  evidence: [
    {
      evidence_id: "ev-005",
      title: "Demo risk: second apron",
      source: "demo-cap-note",
      evidence_type: "cap_context",
      sample_data: true,
    },
    {
      evidence_id: "ev-007",
      title: "Demo market: center market thin",
      source: "demo-market-note",
      evidence_type: "market_context",
      sample_data: true,
    },
    {
      evidence_id: "ev-003",
      title: "Demo cap space check",
      source: "demo-cap-note",
      evidence_type: "cap_context",
      sample_data: true,
    },
    {
      evidence_id: "ev-008",
      title: "Demo transaction: minimum signing fits cap",
      source: "demo-front-office-note",
      evidence_type: "transaction_context",
      sample_data: true,
    },
    {
      evidence_id: "ev-001",
      title: "Demo need: starting PG",
      source: "demo-scouting-note",
      evidence_type: "roster_context",
      sample_data: true,
    },
  ],
  tool_trace: [
    {
      tool_name: "cap_sheet_service.summarize_cap_sheet",
      status: "SUCCESS",
      input_summary: "team_id=DEM-ATL",
      output_summary:
        "total_salary=74000000,cap_space=66000000,roster_count=4",
      fallback_reason: null,
      evidence_ids: [],
    },
    {
      tool_name: "roster_need_service.evaluate_roster_needs",
      status: "SUCCESS",
      input_summary: "team_id=DEM-ATL",
      output_summary: "roster_count=4,needs=[C,PG,SG,SF,PF]",
      fallback_reason: null,
      evidence_ids: [],
    },
    {
      tool_name: "depth_chart_projector.project_current_depth_chart",
      status: "SUCCESS",
      input_summary: "team_id=DEM-ATL",
      output_summary: "PG:pl-001,SG:pl-002,SF:pl-003,PF:pl-004,C:None",
      fallback_reason: null,
      evidence_ids: [],
    },
    {
      tool_name: "free_agent_service.rank_free_agents_for_team",
      status: "FALLBACK",
      input_summary:
        "team_id=DEM-ATL,target_positions=('C',),max_salary=15000000,max_candidates=2",
      output_summary: "0 fits",
      fallback_reason: "No free-agent candidates after filtering.",
      evidence_ids: [],
    },
    {
      tool_name: "trade_simulator.preview_signing",
      status: "FALLBACK",
      input_summary: "no free-agent candidates",
      output_summary: "0 previews",
      fallback_reason: "Skipped: no free-agent candidates to preview.",
      evidence_ids: [],
    },
    {
      tool_name: "evidence_service.search_evidence",
      status: "SUCCESS",
      input_summary:
        "query='center need cap flexibility',team_id=DEM-ATL",
      output_summary: "matched=5,missing=0",
      fallback_reason: null,
      evidence_ids: [],
    },
  ],
  limitations: [
    "M4-C deterministic structured proposal builder only.",
    "No LLM call.",
    "No MCP server/client.",
    "No external NBA API or live salary data.",
    "All actions are previews and require human approval.",
    "Proposal is derived from sample/simulation data.",
    "M4-B deterministic local tool orchestration only.",
    "All transaction outputs are previews and require human approval.",
    "free_agent_service returned no candidates after filtering; signing_previews is empty.",
    "M5-A deterministic proposal viewer / CLI demo only.",
    "No MCP.",
    "Demo uses sample/simulation data, not real NBA predictions.",
  ],
  requires_human_approval: true,
  sample_data: true,
};

export const scenarios: ScenarioMeta[] = [
  {
    id: "default",
    label: "Default Recommendation",
    description:
      "DEM-ATL, target C, max salary $20M, max 2 candidates. Produces a RECOMMENDED proposal with a SIGNING action that passes validation.",
    max_salary: 20000000,
    payload: defaultPayload,
  },
  {
    id: "strict-budget",
    label: "Strict-Budget Fallback",
    description:
      "DEM-ATL, target C, max salary $15M, max 2 candidates. No free agent fits the budget; produces a NO_ACTION proposal with a HOLD action and a no_matching_candidate risk.",
    max_salary: 15000000,
    payload: strictBudgetPayload,
  },
];
