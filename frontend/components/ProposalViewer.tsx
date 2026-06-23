"use client";

/**
 * ProposalViewer
 *
 * M6-A static frontend proposal viewer. Renders a DemoPayload (from
 * frontend/data/demoProposalPayload.ts) as a human-readable brief with
 * status cards, recommended actions, risks, evidence, tool call trace,
 * fallback reasons, and limitations.
 *
 * This component is **display only**. It does NOT call any backend API,
 * does NOT call any LLM, does NOT use MCP, does NOT approve transactions,
 * and does NOT mutate any data. All data is sample / simulation JSON.
 *
 * Milestone: M6-A.
 */

import type {
  DemoPayload,
  ProposalAction,
  ProposalRisk,
  ProposalEvidenceRef,
  ToolCallRecord,
} from "../data/demoProposalPayload";

interface ProposalViewerProps {
  payload: DemoPayload;
}

const sectionStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  padding: 16,
  borderRadius: 8,
  marginTop: 16,
};

const cardStyle: React.CSSProperties = {
  border: "1px solid #e0e0e0",
  padding: 12,
  borderRadius: 6,
  background: "#fafafa",
};

const labelStyle: React.CSSProperties = {
  color: "#666",
  fontSize: 12,
  textTransform: "uppercase",
  letterSpacing: 0.5,
};

const valueStyle: React.CSSProperties = {
  fontSize: 14,
  marginTop: 4,
};

const statusColors: Record<string, string> = {
  RECOMMENDED: "#16a34a",
  PARTIAL: "#ca8a04",
  BLOCKED: "#dc2626",
  NO_ACTION: "#ca8a04",
  PASS: "#16a34a",
  WARNING: "#ca8a04",
  FAIL: "#dc2626",
  SUCCESS: "#16a34a",
  FALLBACK: "#ca8a04",
  FAILED: "#dc2626",
  HIGH: "#dc2626",
  MEDIUM: "#ca8a04",
  LOW: "#16a34a",
  INFO: "#2563eb",
};

function statusColor(status: string): string {
  return statusColors[status] ?? "#666";
}

function formatSalary(salary: number | null): string {
  if (salary === null) return "—";
  return `$${salary.toLocaleString("en-US")}`;
}

function formatBool(value: boolean): string {
  return value ? "Yes" : "No";
}

function StatusCard({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div style={cardStyle}>
      <div style={labelStyle}>{label}</div>
      <div
        style={{
          ...valueStyle,
          fontSize: 18,
          fontWeight: 600,
          color: highlight ? statusColor(value) : "#111",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function ActionCard({ action }: { action: ProposalAction }) {
  return (
    <div style={{ ...cardStyle, marginTop: 8 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
        }}
      >
        <strong>{action.action_type}</strong>
        <span
          style={{
            padding: "2px 8px",
            borderRadius: 4,
            fontSize: 12,
            color: statusColor(action.validation_status),
            border: `1px solid ${statusColor(action.validation_status)}`,
          }}
        >
          {action.validation_status}
        </span>
      </div>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 8,
          fontSize: 13,
        }}
      >
        <div>
          <span style={labelStyle}>player_name</span>
          <div style={valueStyle}>{action.player_name ?? "—"}</div>
        </div>
        <div>
          <span style={labelStyle}>position</span>
          <div style={valueStyle}>{action.position ?? "—"}</div>
        </div>
        <div>
          <span style={labelStyle}>salary</span>
          <div style={valueStyle}>{formatSalary(action.salary)}</div>
        </div>
        <div>
          <span style={labelStyle}>fit_score</span>
          <div style={valueStyle}>
            {action.fit_score !== null
              ? action.fit_score.toFixed(4)
              : "—"}
          </div>
        </div>
        <div>
          <span style={labelStyle}>is_valid</span>
          <div style={valueStyle}>{formatBool(action.is_valid)}</div>
        </div>
        <div>
          <span style={labelStyle}>requires_human_approval</span>
          <div style={valueStyle}>
            {formatBool(action.requires_human_approval)}
          </div>
        </div>
        <div style={{ gridColumn: "1 / -1" }}>
          <span style={labelStyle}>matched_need</span>
          <div style={valueStyle}>{action.matched_need ?? "—"}</div>
        </div>
        <div style={{ gridColumn: "1 / -1" }}>
          <span style={labelStyle}>cap_impact</span>
          <div style={valueStyle}>{action.cap_impact_summary}</div>
        </div>
        <div style={{ gridColumn: "1 / -1" }}>
          <span style={labelStyle}>roster_impact</span>
          <div style={valueStyle}>{action.roster_impact_summary}</div>
        </div>
        <div style={{ gridColumn: "1 / -1" }}>
          <span style={labelStyle}>depth_chart_impact</span>
          <div style={valueStyle}>{action.depth_chart_impact_summary}</div>
        </div>
        {action.evidence_ids.length > 0 && (
          <div style={{ gridColumn: "1 / -1" }}>
            <span style={labelStyle}>evidence_ids</span>
            <div style={valueStyle}>{action.evidence_ids.join(", ")}</div>
          </div>
        )}
        {action.limitations.length > 0 && (
          <div style={{ gridColumn: "1 / -1" }}>
            <span style={labelStyle}>action limitations</span>
            <ul style={{ margin: "4px 0", paddingLeft: 20, fontSize: 12 }}>
              {action.limitations.map((lim, i) => (
                <li key={i}>{lim}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function RiskRow({ risk }: { risk: ProposalRisk }) {
  return (
    <tr style={{ borderBottom: "1px solid #eee" }}>
      <td style={{ padding: "6px 8px", fontFamily: "monospace", fontSize: 13 }}>
        {risk.code}
      </td>
      <td
        style={{
          padding: "6px 8px",
          color: statusColor(risk.level),
          fontWeight: 600,
          fontSize: 13,
        }}
      >
        {risk.level}
      </td>
      <td style={{ padding: "6px 8px", fontSize: 13 }}>{risk.summary}</td>
    </tr>
  );
}

function EvidenceRow({ evidence }: { evidence: ProposalEvidenceRef }) {
  return (
    <tr style={{ borderBottom: "1px solid #eee" }}>
      <td style={{ padding: "6px 8px", fontFamily: "monospace", fontSize: 13 }}>
        {evidence.evidence_id}
      </td>
      <td style={{ padding: "6px 8px", fontSize: 13 }}>{evidence.title}</td>
      <td style={{ padding: "6px 8px", fontSize: 13, color: "#666" }}>
        {evidence.source}
      </td>
      <td style={{ padding: "6px 8px", fontSize: 13, color: "#666" }}>
        {evidence.evidence_type}
      </td>
      <td
        style={{
          padding: "6px 8px",
          fontSize: 12,
          color: evidence.sample_data ? "#16a34a" : "#dc2626",
        }}
      >
        {evidence.sample_data ? "sample" : "real"}
      </td>
    </tr>
  );
}

function ToolTraceRow({ trace }: { trace: ToolCallRecord }) {
  return (
    <tr style={{ borderBottom: "1px solid #eee" }}>
      <td style={{ padding: "6px 8px", fontFamily: "monospace", fontSize: 12 }}>
        {trace.tool_name}
      </td>
      <td
        style={{
          padding: "6px 8px",
          color: statusColor(trace.status),
          fontWeight: 600,
          fontSize: 12,
        }}
      >
        {trace.status}
      </td>
      <td style={{ padding: "6px 8px", fontSize: 12, color: "#666" }}>
        {trace.input_summary}
      </td>
      <td style={{ padding: "6px 8px", fontSize: 12, color: "#666" }}>
        {trace.output_summary}
      </td>
      <td style={{ padding: "6px 8px", fontSize: 12, color: "#ca8a04" }}>
        {trace.fallback_reason ?? "—"}
      </td>
    </tr>
  );
}

export default function ProposalViewer({ payload }: ProposalViewerProps) {
  const { proposal, evaluation, actions, evidence, tool_trace, limitations } =
    payload;

  return (
    <div>
      {/* Status Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 12,
          marginTop: 16,
        }}
      >
        <StatusCard
          label="proposal status"
          value={proposal.status}
          highlight
        />
        <StatusCard
          label="evaluation status"
          value={evaluation.status}
          highlight
        />
        <StatusCard
          label="requires_human_approval"
          value={formatBool(proposal.requires_human_approval)}
        />
        <StatusCard
          label="sample_data"
          value={formatBool(proposal.sample_data)}
        />
      </div>

      {/* Scenario Summary */}
      <section style={sectionStyle}>
        <h3 style={{ margin: "0 0 8px 0" }}>Scenario Summary</h3>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 8,
            fontSize: 13,
          }}
        >
          <div>
            <span style={labelStyle}>team_id</span>
            <div style={valueStyle}>{proposal.team_id}</div>
          </div>
          <div>
            <span style={labelStyle}>objective</span>
            <div style={valueStyle}>{proposal.objective}</div>
          </div>
          <div>
            <span style={labelStyle}>proposal_id</span>
            <div style={valueStyle} style={{ fontFamily: "monospace" }}>
              {proposal.proposal_id}
            </div>
          </div>
          <div>
            <span style={labelStyle}>target_position</span>
            <div style={valueStyle}>C</div>
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <span style={labelStyle}>cap_summary</span>
            <div style={valueStyle}>{proposal.cap_summary}</div>
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <span style={labelStyle}>roster_need_summary</span>
            <div style={valueStyle}>{proposal.roster_need_summary}</div>
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <span style={labelStyle}>depth_chart_summary</span>
            <div style={valueStyle}>{proposal.depth_chart_summary}</div>
          </div>
        </div>
      </section>

      {/* Recommended Actions */}
      <section style={sectionStyle}>
        <h3 style={{ margin: "0 0 8px 0" }}>
          Recommended Actions (preview only)
        </h3>
        {actions.length === 0 ? (
          <p style={{ color: "#888" }}>No actions.</p>
        ) : (
          actions.map((action) => (
            <ActionCard key={action.action_id} action={action} />
          ))
        )}
      </section>

      {/* Risks */}
      <section style={sectionStyle}>
        <h3 style={{ margin: "0 0 8px 0" }}>Risks</h3>
        {proposal.risks.length === 0 ? (
          <p style={{ color: "#888" }}>No risks.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #ddd", textAlign: "left" }}>
                <th style={{ padding: "6px 8px", fontSize: 12 }}>code</th>
                <th style={{ padding: "6px 8px", fontSize: 12 }}>level</th>
                <th style={{ padding: "6px 8px", fontSize: 12 }}>summary</th>
              </tr>
            </thead>
            <tbody>
              {proposal.risks.map((risk, i) => (
                <RiskRow key={i} risk={risk} />
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Evidence */}
      <section style={sectionStyle}>
        <h3 style={{ margin: "0 0 8px 0" }}>Evidence</h3>
        {evidence.length === 0 ? (
          <p style={{ color: "#888" }}>No evidence.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #ddd", textAlign: "left" }}>
                <th style={{ padding: "6px 8px", fontSize: 12 }}>evidence_id</th>
                <th style={{ padding: "6px 8px", fontSize: 12 }}>title</th>
                <th style={{ padding: "6px 8px", fontSize: 12 }}>source</th>
                <th style={{ padding: "6px 8px", fontSize: 12 }}>type</th>
                <th style={{ padding: "6px 8px", fontSize: 12 }}>data</th>
              </tr>
            </thead>
            <tbody>
              {evidence.map((ev, i) => (
                <EvidenceRow key={i} evidence={ev} />
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Tool Call Trace */}
      <section style={sectionStyle}>
        <h3 style={{ margin: "0 0 8px 0" }}>Tool Call Trace</h3>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #ddd", textAlign: "left" }}>
              <th style={{ padding: "6px 8px", fontSize: 12 }}>tool_name</th>
              <th style={{ padding: "6px 8px", fontSize: 12 }}>status</th>
              <th style={{ padding: "6px 8px", fontSize: 12 }}>input</th>
              <th style={{ padding: "6px 8px", fontSize: 12 }}>output</th>
              <th style={{ padding: "6px 8px", fontSize: 12 }}>fallback</th>
            </tr>
          </thead>
          <tbody>
            {tool_trace.map((trace, i) => (
              <ToolTraceRow key={i} trace={trace} />
            ))}
          </tbody>
        </table>
      </section>

      {/* Fallback Reasons */}
      <section style={sectionStyle}>
        <h3 style={{ margin: "0 0 8px 0" }}>Fallback Reasons</h3>
        {proposal.fallback_reasons.length === 0 ? (
          <p style={{ color: "#888" }}>No fallback reasons.</p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13 }}>
            {proposal.fallback_reasons.map((reason, i) => (
              <li key={i} style={{ marginBottom: 4 }}>
                {reason}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Evaluation */}
      <section style={sectionStyle}>
        <h3 style={{ margin: "0 0 8px 0" }}>Evaluation</h3>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr 1fr",
            gap: 8,
            fontSize: 13,
            marginBottom: 12,
          }}
        >
          <div>
            <span style={labelStyle}>passed_checks</span>
            <div style={valueStyle}>{evaluation.passed_checks.length}</div>
          </div>
          <div>
            <span style={labelStyle}>failed_checks</span>
            <div style={valueStyle}>{evaluation.failed_checks.length}</div>
          </div>
          <div>
            <span style={labelStyle}>warnings</span>
            <div style={valueStyle}>{evaluation.warnings.length}</div>
          </div>
        </div>
        {evaluation.issues.length > 0 && (
          <div>
            <span style={labelStyle}>issues</span>
            <ul style={{ margin: "4px 0", paddingLeft: 20, fontSize: 12 }}>
              {evaluation.issues.map((issue, i) => (
                <li key={i} style={{ marginBottom: 4 }}>
                  <span
                    style={{
                      color: statusColor(issue.severity),
                      fontWeight: 600,
                    }}
                  >
                    [{issue.severity}]
                  </span>{" "}
                  <span style={{ fontFamily: "monospace" }}>
                    {issue.code}
                  </span>
                  : {issue.summary}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {/* Limitations */}
      <section style={sectionStyle}>
        <h3 style={{ margin: "0 0 8px 0" }}>Limitations</h3>
        <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13 }}>
          {limitations.map((lim, i) => (
            <li key={i} style={{ marginBottom: 4 }}>
              {lim}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
