/**
 * Static demo trade preview payload for the M6-D / M7-C frontend.
 *
 * This payload is a **snapshot** of the CLI JSON output produced by:
 *
 *   python backend/scripts/run_trade_preview_demo.py --format json
 *
 * It is **sample / simulation data**. It is NOT real NBA data,
 * NOT a real prediction, and NOT an approved transaction. The trade
 * is a PREVIEW only — `requires_human_approval` is always `true`.
 *
 * The demo trade:
 *   DEM-ATL sends pl-002 (Demo Player Bravo, SG, $22M) -> DEM-PDX
 *   DEM-PDX sends pl-007 (Demo Player Golf,  C,  $26M) -> DEM-ATL
 *
 * This trade PASSES the MVP salary-matching rule for both teams and
 * gives DEM-ATL a Center (their target position). Neither player has
 * a no-trade clause.
 *
 * M7-C: the payload now includes `team_a_post_trade` and
 * `team_b_post_trade` blocks, each containing the team's post-trade
 * cap summary (before + after), roster need, depth chart, and impact
 * summaries. The legacy top-level `roster_impact_summary` /
 * `depth_chart_impact_summary` / `cap_impact_summary` fields are kept
 * (they describe Team A) for backward compatibility.
 *
 * Milestone: M6-D (Static Trade Preview Scenario) / M7-C (Team B full
 * trade preview).
 */

// ---- Types ----

export interface TransactionAssetData {
  player_id: string;
  contract_id: string | null;
  salary: number;
  from_team_id: string | null;
  to_team_id: string | null;
  asset_type: string;
}

export interface TradeTransactionData {
  transaction_id: string;
  transaction_type: string;
  team_a_id: string;
  team_b_id: string;
  outgoing_from_a: TransactionAssetData[];
  outgoing_from_b: TransactionAssetData[];
  evidence_ids: string[];
  requires_human_approval: boolean;
  sample_data: boolean;
}

export interface ValidationIssueData {
  code: string;
  message: string;
  severity: string;
  field: string | null;
}

export interface CapSummaryData {
  team_id: string;
  season: string;
  roster_count: number;
  total_salary: number;
  cap_space: number;
  tax_distance: number;
  first_apron_distance: number;
  second_apron_distance: number;
}

export interface ValidationResultData {
  transaction_id: string;
  transaction_type: string;
  status: string;
  is_valid: boolean;
  issues: ValidationIssueData[];
  warnings: ValidationIssueData[];
  cap_summary_before: CapSummaryData | null;
  cap_summary_after: CapSummaryData | null;
  team_b_cap_summary_before: CapSummaryData | null;
  team_b_cap_summary_after: CapSummaryData | null;
  evidence_ids: string[];
  requires_human_approval: boolean;
  limitations: string[];
}

export interface PositionNeedData {
  position: string;
  current_count: number;
  target_count: number;
  priority: string;
  reason: string;
}

export interface RosterNeedReportData {
  team_id: string;
  roster_count: number;
  needs: PositionNeedData[];
  strengths: string[];
  limitations: string[];
}

export interface RosterPlayerData {
  player_id: string;
  name: string;
  team_id: string;
  position: string;
  role: string;
  salary: number | null;
  sample_data: boolean;
}

export interface DepthChartSlotData {
  position: string;
  starter: RosterPlayerData | null;
  backups: RosterPlayerData[];
  need_level: string;
}

export interface DepthChartData {
  team_id: string;
  slots: DepthChartSlotData[];
  roster_count: number;
  limitations: string[];
}

export interface TradePreviewData {
  transaction_id: string;
  validation_result: ValidationResultData;
  roster_need_after: RosterNeedReportData | null;
  depth_chart_after: DepthChartData | null;
  cap_summary_after: CapSummaryData | null;
  team_b_roster_need_after: RosterNeedReportData | null;
  team_b_depth_chart_after: DepthChartData | null;
  team_b_cap_summary_after: CapSummaryData | null;
  requires_human_approval: boolean;
  limitations: string[];
}

export interface SalaryMatchingSide {
  team_id: string;
  outgoing_salary: number;
  incoming_salary: number;
  threshold: number;
  passed: boolean;
}

export interface SalaryMatchingData {
  rule: string;
  team_a: SalaryMatchingSide;
  team_b: SalaryMatchingSide;
}

/**
 * Per-team post-trade preview block (M7-C). Both Team A and Team B
 * use this shape so the viewer can render them with the same component.
 */
export interface TeamPostTradeData {
  team_id: string;
  cap_summary_before: CapSummaryData | null;
  cap_summary_after: CapSummaryData | null;
  roster_need_after: RosterNeedReportData | null;
  depth_chart_after: DepthChartData | null;
  roster_impact_summary: string | null;
  depth_chart_impact_summary: string | null;
  cap_impact_summary: string | null;
}

export interface DemoTradePayload {
  trade_transaction: TradeTransactionData;
  preview: TradePreviewData;
  salary_matching: SalaryMatchingData;
  team_a_post_trade: TeamPostTradeData;
  team_b_post_trade: TeamPostTradeData;
  /** Legacy Team A-only summaries (kept for backward compatibility). */
  roster_impact_summary: string | null;
  depth_chart_impact_summary: string | null;
  cap_impact_summary: string | null;
  requires_human_approval: boolean;
  sample_data: boolean;
}

// ---- Static payload snapshot ----

export const demoTradePayload: DemoTradePayload = {
  trade_transaction: {
    transaction_id: "tx-trade-demo-001",
    transaction_type: "TWO_TEAM_TRADE",
    team_a_id: "DEM-ATL",
    team_b_id: "DEM-PDX",
    outgoing_from_a: [
      {
        player_id: "pl-002",
        contract_id: "ct-002",
        salary: 22000000,
        from_team_id: "DEM-ATL",
        to_team_id: "DEM-PDX",
        asset_type: "PLAYER_CONTRACT",
      },
    ],
    outgoing_from_b: [
      {
        player_id: "pl-007",
        contract_id: "ct-007",
        salary: 26000000,
        from_team_id: "DEM-PDX",
        to_team_id: "DEM-ATL",
        asset_type: "PLAYER_CONTRACT",
      },
    ],
    evidence_ids: ["ev-007"],
    requires_human_approval: true,
    sample_data: true,
  },
  preview: {
    transaction_id: "tx-trade-demo-001",
    validation_result: {
      transaction_id: "tx-trade-demo-001",
      transaction_type: "TWO_TEAM_TRADE",
      status: "PASS",
      is_valid: true,
      issues: [],
      warnings: [],
      cap_summary_before: {
        team_id: "DEM-ATL",
        season: "2025-2026",
        roster_count: 4,
        total_salary: 74000000,
        cap_space: 66000000,
        tax_distance: 96000000,
        first_apron_distance: 104000000,
        second_apron_distance: 115000000,
      },
      cap_summary_after: {
        team_id: "DEM-ATL",
        season: "2025-2026",
        roster_count: 4,
        total_salary: 78000000,
        cap_space: 62000000,
        tax_distance: 92000000,
        first_apron_distance: 100000000,
        second_apron_distance: 111000000,
      },
      team_b_cap_summary_before: {
        team_id: "DEM-PDX",
        season: "2025-2026",
        roster_count: 4,
        total_salary: 74000000,
        cap_space: 66000000,
        tax_distance: 96000000,
        first_apron_distance: 104000000,
        second_apron_distance: 115000000,
      },
      team_b_cap_summary_after: {
        team_id: "DEM-PDX",
        season: "2025-2026",
        roster_count: 4,
        total_salary: 70000000,
        cap_space: 70000000,
        tax_distance: 100000000,
        first_apron_distance: 108000000,
        second_apron_distance: 119000000,
      },
      evidence_ids: ["ev-007"],
      requires_human_approval: true,
      limitations: [
        "MVP salary matching rule: incoming <= outgoing * 1.25 + 100000. Not the real NBA CBA.",
        "Apron hard caps are NOT enforced in M2; apron crossings are warnings only.",
        "No Bird rights, no sign-and-trade rules, no draft-pick value rules in M2.",
        "Only two-team trades are supported.",
      ],
    },
    roster_need_after: {
      team_id: "DEM-ATL",
      roster_count: 4,
      needs: [
        {
          position: "SG",
          current_count: 0,
          target_count: 2,
          priority: "high",
          reason: "SG: have 0, target 2, short 2 (priority=high).",
        },
        {
          position: "PG",
          current_count: 1,
          target_count: 2,
          priority: "medium",
          reason: "PG: have 1, target 2, short 1 (priority=medium).",
        },
        {
          position: "SF",
          current_count: 1,
          target_count: 2,
          priority: "medium",
          reason: "SF: have 1, target 2, short 1 (priority=medium).",
        },
        {
          position: "PF",
          current_count: 1,
          target_count: 2,
          priority: "medium",
          reason: "PF: have 1, target 2, short 1 (priority=medium).",
        },
        {
          position: "C",
          current_count: 1,
          target_count: 2,
          priority: "medium",
          reason: "C: have 1, target 2, short 1 (priority=medium).",
        },
      ],
      strengths: [],
      limitations: [
        "Demo roster-need heuristic: target=2 per position. Not a scouting model.",
        "Computed on an in-memory preview roster.",
      ],
    },
    depth_chart_after: {
      team_id: "DEM-ATL",
      slots: [
        {
          position: "PG",
          starter: {
            player_id: "pl-001",
            name: "Demo Player Alpha",
            team_id: "DEM-ATL",
            position: "PG",
            role: "starter",
            salary: 28000000,
            sample_data: true,
          },
          backups: [],
          need_level: "medium",
        },
        {
          position: "SG",
          starter: null,
          backups: [],
          need_level: "high",
        },
        {
          position: "SF",
          starter: {
            player_id: "pl-003",
            name: "Demo Player Charlie",
            team_id: "DEM-ATL",
            position: "SF",
            role: "starter",
            salary: 18000000,
            sample_data: true,
          },
          backups: [],
          need_level: "medium",
        },
        {
          position: "PF",
          starter: {
            player_id: "pl-004",
            name: "Demo Player Delta",
            team_id: "DEM-ATL",
            position: "PF",
            role: "bench",
            salary: 6000000,
            sample_data: true,
          },
          backups: [],
          need_level: "medium",
        },
        {
          position: "C",
          starter: {
            player_id: "pl-007",
            name: "Demo Player Golf",
            team_id: "DEM-ATL",
            position: "C",
            role: "starter",
            salary: 26000000,
            sample_data: true,
          },
          backups: [],
          need_level: "medium",
        },
      ],
      roster_count: 4,
      limitations: [
        "Demo depth chart: starter = first player at position, backups = rest.",
        "Does not consider player quality, minutes, or scheme fit.",
        "Does not project post-transaction depth charts (M3-B will).",
      ],
    },
    cap_summary_after: {
      team_id: "DEM-ATL",
      season: "2025-2026",
      roster_count: 4,
      total_salary: 78000000,
      cap_space: 62000000,
      tax_distance: 92000000,
      first_apron_distance: 100000000,
      second_apron_distance: 111000000,
    },
    team_b_roster_need_after: {
      team_id: "DEM-PDX",
      roster_count: 4,
      needs: [
        {
          position: "SF",
          current_count: 0,
          target_count: 2,
          priority: "high",
          reason: "SF: have 0, target 2, short 2 (priority=high).",
        },
        {
          position: "C",
          current_count: 0,
          target_count: 2,
          priority: "high",
          reason: "C: have 0, target 2, short 2 (priority=high).",
        },
        {
          position: "PG",
          current_count: 1,
          target_count: 2,
          priority: "medium",
          reason: "PG: have 1, target 2, short 1 (priority=medium).",
        },
        {
          position: "PF",
          current_count: 1,
          target_count: 2,
          priority: "medium",
          reason: "PF: have 1, target 2, short 1 (priority=medium).",
        },
      ],
      strengths: ["SG"],
      limitations: [
        "Demo roster-need heuristic: target=2 per position. Not a scouting model.",
        "Computed on an in-memory preview roster.",
      ],
    },
    team_b_depth_chart_after: {
      team_id: "DEM-PDX",
      slots: [
        {
          position: "PG",
          starter: {
            player_id: "pl-005",
            name: "Demo Player Echo",
            team_id: "DEM-PDX",
            position: "PG",
            role: "starter",
            salary: 30000000,
            sample_data: true,
          },
          backups: [],
          need_level: "medium",
        },
        {
          position: "SG",
          starter: {
            player_id: "pl-006",
            name: "Demo Player Foxtrot",
            team_id: "DEM-PDX",
            position: "SG",
            role: "bench",
            salary: 4000000,
            sample_data: true,
          },
          backups: [
            {
              player_id: "pl-002",
              name: "Demo Player Bravo",
              team_id: "DEM-PDX",
              position: "SG",
              role: "starter",
              salary: 22000000,
              sample_data: true,
            },
          ],
          need_level: "low",
        },
        {
          position: "SF",
          starter: null,
          backups: [],
          need_level: "high",
        },
        {
          position: "PF",
          starter: {
            player_id: "pl-008",
            name: "Demo Player Hotel",
            team_id: "DEM-PDX",
            position: "PF",
            role: "starter",
            salary: 14000000,
            sample_data: true,
          },
          backups: [],
          need_level: "medium",
        },
        {
          position: "C",
          starter: null,
          backups: [],
          need_level: "high",
        },
      ],
      roster_count: 4,
      limitations: [
        "Demo depth chart: starter = first player at position, backups = rest.",
        "Does not consider player quality, minutes, or scheme fit.",
        "Does not project post-transaction depth charts (M3-B will).",
      ],
    },
    team_b_cap_summary_after: {
      team_id: "DEM-PDX",
      season: "2025-2026",
      roster_count: 4,
      total_salary: 70000000,
      cap_space: 70000000,
      tax_distance: 100000000,
      first_apron_distance: 108000000,
      second_apron_distance: 119000000,
    },
    requires_human_approval: true,
    limitations: [
      "MVP preview: in-memory only, never writes to data files.",
      "Post-transaction depth chart uses the same heuristic as current depth chart.",
      "Trade preview does not simulate multi-year contract decay.",
      "A passed preview still requires human approval before any state change.",
    ],
  },
  salary_matching: {
    rule: "incoming <= outgoing * 1.25 + 100000",
    team_a: {
      team_id: "DEM-ATL",
      outgoing_salary: 22000000,
      incoming_salary: 26000000,
      threshold: 27600000,
      passed: true,
    },
    team_b: {
      team_id: "DEM-PDX",
      outgoing_salary: 26000000,
      incoming_salary: 22000000,
      threshold: 32600000,
      passed: true,
    },
  },
  team_a_post_trade: {
    team_id: "DEM-ATL",
    cap_summary_before: {
      team_id: "DEM-ATL",
      season: "2025-2026",
      roster_count: 4,
      total_salary: 74000000,
      cap_space: 66000000,
      tax_distance: 96000000,
      first_apron_distance: 104000000,
      second_apron_distance: 115000000,
    },
    cap_summary_after: {
      team_id: "DEM-ATL",
      season: "2025-2026",
      roster_count: 4,
      total_salary: 78000000,
      cap_space: 62000000,
      tax_distance: 92000000,
      first_apron_distance: 100000000,
      second_apron_distance: 111000000,
    },
    roster_need_after: {
      team_id: "DEM-ATL",
      roster_count: 4,
      needs: [
        {
          position: "SG",
          current_count: 0,
          target_count: 2,
          priority: "high",
          reason: "SG: have 0, target 2, short 2 (priority=high).",
        },
        {
          position: "PG",
          current_count: 1,
          target_count: 2,
          priority: "medium",
          reason: "PG: have 1, target 2, short 1 (priority=medium).",
        },
        {
          position: "SF",
          current_count: 1,
          target_count: 2,
          priority: "medium",
          reason: "SF: have 1, target 2, short 1 (priority=medium).",
        },
        {
          position: "PF",
          current_count: 1,
          target_count: 2,
          priority: "medium",
          reason: "PF: have 1, target 2, short 1 (priority=medium).",
        },
        {
          position: "C",
          current_count: 1,
          target_count: 2,
          priority: "medium",
          reason: "C: have 1, target 2, short 1 (priority=medium).",
        },
      ],
      strengths: [],
      limitations: [
        "Demo roster-need heuristic: target=2 per position. Not a scouting model.",
        "Computed on an in-memory preview roster.",
      ],
    },
    depth_chart_after: {
      team_id: "DEM-ATL",
      slots: [
        {
          position: "PG",
          starter: {
            player_id: "pl-001",
            name: "Demo Player Alpha",
            team_id: "DEM-ATL",
            position: "PG",
            role: "starter",
            salary: 28000000,
            sample_data: true,
          },
          backups: [],
          need_level: "medium",
        },
        {
          position: "SG",
          starter: null,
          backups: [],
          need_level: "high",
        },
        {
          position: "SF",
          starter: {
            player_id: "pl-003",
            name: "Demo Player Charlie",
            team_id: "DEM-ATL",
            position: "SF",
            role: "starter",
            salary: 18000000,
            sample_data: true,
          },
          backups: [],
          need_level: "medium",
        },
        {
          position: "PF",
          starter: {
            player_id: "pl-004",
            name: "Demo Player Delta",
            team_id: "DEM-ATL",
            position: "PF",
            role: "bench",
            salary: 6000000,
            sample_data: true,
          },
          backups: [],
          need_level: "medium",
        },
        {
          position: "C",
          starter: {
            player_id: "pl-007",
            name: "Demo Player Golf",
            team_id: "DEM-ATL",
            position: "C",
            role: "starter",
            salary: 26000000,
            sample_data: true,
          },
          backups: [],
          need_level: "medium",
        },
      ],
      roster_count: 4,
      limitations: [
        "Demo depth chart: starter = first player at position, backups = rest.",
        "Does not consider player quality, minutes, or scheme fit.",
        "Does not project post-transaction depth charts (M3-B will).",
      ],
    },
    roster_impact_summary:
      "Team (DEM-ATL) post-trade roster: 4 players, 5 position need(s), 0 position strength(s).",
    depth_chart_impact_summary:
      "Team (DEM-ATL) post-trade depth chart: 4/5 positions with a starter.",
    cap_impact_summary:
      "Team (DEM-ATL) post-trade total_salary: $78,000,000, cap_space: $62,000,000.",
  },
  team_b_post_trade: {
    team_id: "DEM-PDX",
    cap_summary_before: {
      team_id: "DEM-PDX",
      season: "2025-2026",
      roster_count: 4,
      total_salary: 74000000,
      cap_space: 66000000,
      tax_distance: 96000000,
      first_apron_distance: 104000000,
      second_apron_distance: 115000000,
    },
    cap_summary_after: {
      team_id: "DEM-PDX",
      season: "2025-2026",
      roster_count: 4,
      total_salary: 70000000,
      cap_space: 70000000,
      tax_distance: 100000000,
      first_apron_distance: 108000000,
      second_apron_distance: 119000000,
    },
    roster_need_after: {
      team_id: "DEM-PDX",
      roster_count: 4,
      needs: [
        {
          position: "SF",
          current_count: 0,
          target_count: 2,
          priority: "high",
          reason: "SF: have 0, target 2, short 2 (priority=high).",
        },
        {
          position: "C",
          current_count: 0,
          target_count: 2,
          priority: "high",
          reason: "C: have 0, target 2, short 2 (priority=high).",
        },
        {
          position: "PG",
          current_count: 1,
          target_count: 2,
          priority: "medium",
          reason: "PG: have 1, target 2, short 1 (priority=medium).",
        },
        {
          position: "PF",
          current_count: 1,
          target_count: 2,
          priority: "medium",
          reason: "PF: have 1, target 2, short 1 (priority=medium).",
        },
      ],
      strengths: ["SG"],
      limitations: [
        "Demo roster-need heuristic: target=2 per position. Not a scouting model.",
        "Computed on an in-memory preview roster.",
      ],
    },
    depth_chart_after: {
      team_id: "DEM-PDX",
      slots: [
        {
          position: "PG",
          starter: {
            player_id: "pl-005",
            name: "Demo Player Echo",
            team_id: "DEM-PDX",
            position: "PG",
            role: "starter",
            salary: 30000000,
            sample_data: true,
          },
          backups: [],
          need_level: "medium",
        },
        {
          position: "SG",
          starter: {
            player_id: "pl-006",
            name: "Demo Player Foxtrot",
            team_id: "DEM-PDX",
            position: "SG",
            role: "bench",
            salary: 4000000,
            sample_data: true,
          },
          backups: [
            {
              player_id: "pl-002",
              name: "Demo Player Bravo",
              team_id: "DEM-PDX",
              position: "SG",
              role: "starter",
              salary: 22000000,
              sample_data: true,
            },
          ],
          need_level: "low",
        },
        {
          position: "SF",
          starter: null,
          backups: [],
          need_level: "high",
        },
        {
          position: "PF",
          starter: {
            player_id: "pl-008",
            name: "Demo Player Hotel",
            team_id: "DEM-PDX",
            position: "PF",
            role: "starter",
            salary: 14000000,
            sample_data: true,
          },
          backups: [],
          need_level: "medium",
        },
        {
          position: "C",
          starter: null,
          backups: [],
          need_level: "high",
        },
      ],
      roster_count: 4,
      limitations: [
        "Demo depth chart: starter = first player at position, backups = rest.",
        "Does not consider player quality, minutes, or scheme fit.",
        "Does not project post-transaction depth charts (M3-B will).",
      ],
    },
    roster_impact_summary:
      "Team (DEM-PDX) post-trade roster: 4 players, 4 position need(s), 1 position strength(s).",
    depth_chart_impact_summary:
      "Team (DEM-PDX) post-trade depth chart: 3/5 positions with a starter.",
    cap_impact_summary:
      "Team (DEM-PDX) post-trade total_salary: $70,000,000, cap_space: $70,000,000.",
  },
  roster_impact_summary:
    "Team (DEM-ATL) post-trade roster: 4 players, 5 position need(s), 0 position strength(s).",
  depth_chart_impact_summary:
    "Team (DEM-ATL) post-trade depth chart: 4/5 positions with a starter.",
  cap_impact_summary:
    "Team (DEM-ATL) post-trade total_salary: $78,000,000, cap_space: $62,000,000.",
  requires_human_approval: true,
  sample_data: true,
};
