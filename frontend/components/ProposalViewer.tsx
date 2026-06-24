"use client";

/**
 * ProposalViewer — M6-C bilingual (Chinese-first) user-facing viewer.
 *
 * Two-layer design:
 *   1. User summary layer (plain Chinese/English: what the system
 *      recommends, why, what checks ran, what risks remain, why human
 *      approval is still required).
 *   2. Audit trail layer (all professional fields preserved: action_id,
 *      transaction_id, tool_call_trace, evidence_ids, evaluation issues,
 *      remediation, etc.).
 *
 * The `lang` prop controls UI copy language. Default is "zh". The
 * underlying payload values (RECOMMENDED / PASS / NO_ACTION / HOLD /
 * tool_name / evidence_id / action_id) stay in English for traceability,
 * but every code/badge is paired with a Chinese explanation.
 *
 * Display only. No API calls, no LLM, no MCP, no data mutation, no
 * transaction approval. All data is sample / simulation JSON.
 *
 * Milestone: M6-C (Chinese-first / bilingual patch).
 */

import type {
  DemoPayload,
  ProposalAction,
  ProposalRisk,
  ProposalEvidenceRef,
  ToolCallRecord,
  EvaluationIssue,
} from "../data/demoProposalPayload";
import {
  copy,
  type Lang,
  formatSalary,
  formatBool,
  orNa,
  orNone,
  evidenceIdsText,
} from "../data/i18n";

interface ProposalViewerProps {
  payload: DemoPayload;
  lang: Lang;
  /**
   * "report" (default): all sections rendered inline as a long report.
   * "console": user-readable layers (summary, status cards, actions,
   *   why, limitations) render inline; audit-heavy layers (tool trace,
   *   evidence, risks, evaluation issues, proposal field grid, raw
   *   limitations) collapse into a <details> "View audit details"
   *   block so the console output stays scannable.
   */
  variant?: "report" | "console";
}

// ---- Helpers ----

function statusValueClass(status: string): string {
  if (["RECOMMENDED", "PASS", "SUCCESS"].includes(status))
    return "status-card__value--ok";
  if (["PARTIAL", "NO_ACTION", "WARNING", "FALLBACK"].includes(status))
    return "status-card__value--warn";
  if (["BLOCKED", "FAIL", "FAILED"].includes(status))
    return "status-card__value--bad";
  return "";
}

function riskLevelClass(level: string): string {
  const l = level.toUpperCase();
  if (l === "HIGH") return "risk-card--high";
  if (l === "MEDIUM") return "risk-card--medium";
  if (l === "LOW") return "risk-card--low";
  return "";
}

function severityClass(severity: string): string {
  if (severity === "INFO") return "issue-item--info";
  return "";
}

// ---- Action plain-language summary ----

function actionPlainSummary(action: ProposalAction, lang: Lang): string {
  if (action.action_type === "HOLD") {
    return copy.actionsSection.holdPlain[lang];
  }
  if (action.action_type === "SIGNING" && action.player_name) {
    const pos = action.position ? action.position : "";
    const sal = action.salary !== null ? formatSalary(action.salary, lang) : "";
    if (lang === "zh") {
      return copy.actionsSection.signingPlain.zh
        .replace("{salary}", sal)
        .replace("{player}", action.player_name)
        .replace("{position}", pos);
    }
    const posEn = pos ? ` ${pos}` : "";
    return copy.actionsSection.signingPlain.en
      .replace("{salary}", sal)
      .replace("{player}", action.player_name)
      .replace("{position}", posEn);
  }
  if (action.action_type === "TRADE" && action.player_name) {
    return copy.actionsSection.tradePlain[lang].replace(
      "{player}",
      action.player_name,
    );
  }
  return copy.actionsSection.genericPlain[lang].replace(
    "{type}",
    action.action_type.toLowerCase(),
  );
}

// ---- Sub-components ----

function StatusCard({
  label,
  value,
  explain,
  valueClass = "",
  lang,
}: {
  label: string;
  value: string;
  explain: string;
  valueClass?: string;
  lang: Lang;
}) {
  return (
    <div className="status-card">
      <p className="status-card__label">{label}</p>
      <p className={`status-card__value ${valueClass}`}>{value}</p>
      <p className="status-card__explain" lang={lang}>{explain}</p>
    </div>
  );
}

function Field({
  label,
  value,
  mono = false,
  muted = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  muted?: boolean;
}) {
  const cls = [
    "field__value",
    mono ? "field__value--mono" : "",
    muted ? "field__value--muted" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className="field">
      <p className="field__label">{label}</p>
      <p className={cls}>{value}</p>
    </div>
  );
}

function ActionCard({ action, lang }: { action: ProposalAction; lang: Lang }) {
  const isHold = action.action_type === "HOLD";
  const f = copy.fields;
  return (
    <div className="action-card">
      <div className="action-card__header">
        <span
          className={`action-card__type ${isHold ? "action-card__type--hold" : ""}`}
        >
          {action.action_type}
        </span>
        <span className="action-card__plain" lang={lang}>
          {actionPlainSummary(action, lang)}
        </span>
        <span className={`badge ${action.is_valid ? "badge--ok" : "badge--warn"}`}>
          {action.validation_status}
        </span>
      </div>
      <div className="action-card__body">
        <div className="field-grid">
          <Field label={f.player_name[lang]} value={orNa(action.player_name, lang)} />
          <Field label={f.position[lang]} value={orNa(action.position, lang)} />
          <Field label={f.salary[lang]} value={formatSalary(action.salary, lang)} />
          <Field
            label={f.years[lang]}
            value={action.years !== null ? String(action.years) : copy.empty.na[lang]}
          />
          <Field label={f.is_valid[lang]} value={formatBool(action.is_valid, lang)} />
          <Field
            label={f.requires_human_approval[lang]}
            value={formatBool(action.requires_human_approval, lang)}
          />
          <Field
            label={f.fit_score[lang]}
            value={
              action.fit_score !== null
                ? action.fit_score.toFixed(4)
                : copy.empty.na[lang]
            }
          />
          <Field label={f.matched_need[lang]} value={orNa(action.matched_need, lang)} />
          <Field
            label={f.transaction_id[lang]}
            value={orNa(action.transaction_id, lang)}
            mono
          />
          <Field label={f.action_id[lang]} value={action.action_id} mono />
          <Field label={f.team_id[lang]} value={action.team_id} mono />
          <Field
            label={f.evidence_ids[lang]}
            value={evidenceIdsText(action.evidence_ids, lang)}
            mono
          />
          <Field
            label={f.cap_impact_summary[lang]}
            value={action.cap_impact_summary}
          />
          <Field
            label={f.roster_impact_summary[lang]}
            value={action.roster_impact_summary}
          />
          <Field
            label={f.depth_chart_impact_summary[lang]}
            value={action.depth_chart_impact_summary}
          />
        </div>
        {action.limitations.length > 0 && (
          <div style={{ marginTop: "var(--space-sm)" }}>
            <p className="field__label">{copy.actionsSection.actionLimitations[lang]}</p>
            <ul
              style={{
                margin: "4px 0 0",
                paddingLeft: "1.1rem",
                fontSize: "0.82rem",
                color: "var(--ink-soft)",
              }}
            >
              {action.limitations.map((lim, i) => (
                <li key={i} style={{ marginBottom: 2 }}>
                  {lim}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

function RiskCard({ risk, lang }: { risk: ProposalRisk; lang: Lang }) {
  const plain =
    copy.risksSection.plain[risk.code]?.[lang] ??
    copy.risksSection.fallbackPlain[lang];
  return (
    <div className={`risk-card ${riskLevelClass(risk.level)}`}>
      <p className="risk-card__plain" lang={lang}>{plain}</p>
      <p
        className="risk-card__summary"
        style={{
          fontSize: "0.85rem",
          color: "var(--ink-soft)",
          margin: "0 0 4px",
        }}
      >
        {risk.summary}
      </p>
      <span className="risk-card__code">
        {copy.risksSection.plain[risk.code] ? `${copy.fields.code[lang]}: ${risk.code}` : risk.code}{" "}
        · {copy.fields.level[lang]}: {risk.level} · {copy.fields.evidence_ids[lang]}:{" "}
        {evidenceIdsText(risk.evidence_ids, lang)}
      </span>
    </div>
  );
}

function EvidenceItem({
  evidence,
  lang,
}: {
  evidence: ProposalEvidenceRef;
  lang: Lang;
}) {
  return (
    <div className="evidence-item">
      <p className="evidence-item__title">{evidence.title}</p>
      <p className="evidence-item__meta">
        {copy.fields.source[lang]}: {evidence.source} ·{" "}
        {copy.fields.evidence_type[lang]}: {evidence.evidence_type} ·{" "}
        {copy.fields.sample_data[lang]}:{" "}
        {evidence.sample_data
          ? copy.evidenceSection.sampleYes[lang]
          : copy.evidenceSection.sampleNo[lang]}
      </p>
      <span className="evidence-item__id">
        {copy.fields.evidence_id[lang]}: {evidence.evidence_id}
      </span>
    </div>
  );
}

function ToolTraceItem({ trace, lang }: { trace: ToolCallRecord; lang: Lang }) {
  const plain =
    copy.auditSection.toolLabels[trace.tool_name]?.[lang] ?? trace.tool_name;
  const f = copy.fields;
  return (
    <li className="audit-item">
      <div className="audit-item__head">
        <span className="audit-item__plain" lang={lang}>{plain}</span>
        <span
          className={`badge ${trace.status === "SUCCESS" ? "badge--ok" : trace.status === "FALLBACK" ? "badge--warn" : "badge--bad"}`}
        >
          {trace.status}
        </span>
      </div>
      <p className="audit-item__tech">{trace.tool_name}</p>
      <p className="audit-item__detail">
        <strong>{f.input_summary[lang]}:</strong> {trace.input_summary}
      </p>
      <p className="audit-item__detail">
        <strong>{f.output_summary[lang]}:</strong> {trace.output_summary}
      </p>
      {trace.fallback_reason && (
        <span className="audit-item__fallback">
          {copy.auditSection.fallbackPrefix[lang]}
          {trace.fallback_reason}
        </span>
      )}
      <p className="audit-item__detail">
        <strong>{f.evidence_ids[lang]}:</strong>{" "}
        {evidenceIdsText(trace.evidence_ids, lang)}
      </p>
    </li>
  );
}

function IssueItem({ issue, lang }: { issue: EvaluationIssue; lang: Lang }) {
  const f = copy.fields;
  return (
    <div className={`issue-item ${severityClass(issue.severity)}`}>
      <div className="issue-item__head">
        <span
          className={`badge ${issue.severity === "INFO" ? "badge--info" : issue.severity === "WARNING" ? "badge--warn" : "badge--bad"}`}
        >
          {issue.severity}
        </span>
        <span className="issue-item__code">{issue.code}</span>
      </div>
      <p className="issue-item__summary">{issue.summary}</p>
      {issue.remediation && (
        <p className="issue-item__remediation">
          {copy.evaluationSection.remediationPrefix[lang]}
          {issue.remediation}
        </p>
      )}
      <p className="audit-item__detail" style={{ marginTop: 4 }}>
        <strong>{f.action_id[lang]}:</strong> {orNone(issue.action_id, lang)} ·{" "}
        <strong>{f.evidence_ids[lang]}:</strong>{" "}
        {evidenceIdsText(issue.evidence_ids, lang)}
      </p>
    </div>
  );
}

// ---- Main component ----

export default function ProposalViewer({
  payload,
  lang,
  variant = "report",
}: ProposalViewerProps) {
  const { proposal, evaluation, actions, evidence, tool_trace, limitations } =
    payload;
  const isConsole = variant === "console";

  const isNoAction = proposal.status === "NO_ACTION";
  const proposalExplain =
    copy.statusCards.proposalExplain[proposal.status]?.[lang] ??
    (lang === "zh" ? "详见审计追踪。" : "See audit trail for details.");
  const evaluationExplain =
    copy.statusCards.evaluationExplain[evaluation.status]?.[lang] ??
    (lang === "zh" ? "详见审计追踪。" : "See audit trail for details.");

  const firstAction = actions[0];
  const summaryHeadline = isNoAction
    ? copy.summary.strictHeadline[lang]
    : copy.summary.defaultHeadline[lang];
  const summaryBody = isNoAction
    ? copy.summary.strictBody[lang]
    : copy.summary.defaultBody[lang]
        .replace(
          "{player}",
          firstAction?.player_name ?? (lang === "zh" ? "一名中锋" : "a center"),
        )
        .replace(
          "{salary}",
          formatSalary(firstAction?.salary ?? null, lang),
        );

  return (
    <div lang={lang}>
      {/* Approval boundary banner — suppressed in console mode (page-level safety-bar covers this) */}
      {!isConsole && (
        <div className="approval-banner">
          <strong>{copy.approvalBanner.strong[lang]}</strong>{" "}
          {copy.approvalBanner.body[lang]}
        </div>
      )}

      {/* User-facing summary block — suppressed in console mode (page-level decision-summary covers this) */}
      {!isConsole && (
        <div className={`summary-block ${isNoAction ? "summary-block--hold" : ""}`}>
          <p className="summary-headline">{summaryHeadline}</p>
          <p className="summary-body">{summaryBody}</p>
        </div>
      )}

      {/* Status cards — suppressed in console mode (page-level indicator-grid covers this) */}
      {!isConsole && (
        <div className="status-grid">
          <StatusCard
            label={copy.statusCards.proposalLabel[lang]}
            value={proposal.status}
            explain={proposalExplain}
            valueClass={statusValueClass(proposal.status)}
            lang={lang}
          />
          <StatusCard
            label={copy.statusCards.evaluationLabel[lang]}
            value={evaluation.status}
            explain={evaluationExplain}
            valueClass={statusValueClass(evaluation.status)}
            lang={lang}
          />
        <StatusCard
          label={copy.statusCards.approvalLabel[lang]}
          value={formatBool(proposal.requires_human_approval, lang)}
          explain={
            proposal.requires_human_approval
              ? copy.statusCards.approvalYes[lang]
              : copy.statusCards.approvalNo[lang]
          }
          valueClass={proposal.requires_human_approval ? "status-card__value--warn" : ""}
          lang={lang}
        />
        <StatusCard
          label={copy.statusCards.sampleLabel[lang]}
          value={formatBool(proposal.sample_data, lang)}
          explain={
            proposal.sample_data
              ? copy.statusCards.sampleYes[lang]
              : copy.statusCards.sampleNo[lang]
          }
          valueClass={proposal.sample_data ? "status-card__value--warn" : ""}
          lang={lang}
        />
        </div>
      )}

      {/* How the system reached this result — compact in console mode */}
      {isConsole ? (
        <details className="audit-details" style={{ marginTop: "var(--space-sm)" }}>
          <summary>
            {copy.howSection.title[lang]}
          </summary>
          <ol
            style={{
              margin: 0,
              paddingLeft: "1.2rem",
              fontSize: "0.88rem",
              color: "var(--ink)",
              lineHeight: 1.7,
            }}
          >
            {copy.howSection.steps.map((step, i) => (
              <li key={i} value={i + 1}>
                {step[lang]}
              </li>
            ))}
          </ol>
          {/* Recommended actions — inside collapsed details in console mode */}
          <section className="section" style={{ marginTop: "var(--space-sm)" }}>
            <h2 className="section__title">{copy.actionsSection.title[lang]}</h2>
            <p className="section__hint">{copy.actionsSection.hint[lang]}</p>
            {actions.map((action) => (
              <ActionCard key={action.action_id} action={action} lang={lang} />
            ))}
          </section>
          <AuditSections
            proposal={proposal}
            evaluation={evaluation}
            evidence={evidence}
            tool_trace={tool_trace}
            limitations={limitations}
            isNoAction={isNoAction}
            lang={lang}
          />
        </details>
      ) : (
        <>
          {/* How the system reached this result */}
          <section className="section">
            <h2 className="section__title">{copy.howSection.title[lang]}</h2>
            <p className="section__hint">{copy.howSection.hint[lang]}</p>
            <ol
              style={{
                margin: 0,
                paddingLeft: "1.2rem",
                fontSize: "0.92rem",
                color: "var(--ink)",
                lineHeight: 1.8,
              }}
            >
              {copy.howSection.steps.map((step, i) => (
                <li key={i} value={i + 1}>
                  {step[lang]}
                </li>
              ))}
            </ol>
          </section>

          {/* Recommended actions */}
          <section className="section">
            <h2 className="section__title">{copy.actionsSection.title[lang]}</h2>
            <p className="section__hint">{copy.actionsSection.hint[lang]}</p>
            {actions.map((action) => (
              <ActionCard key={action.action_id} action={action} lang={lang} />
            ))}
          </section>

          {/* Audit-heavy sections */}
          <AuditSections
            proposal={proposal}
            evaluation={evaluation}
            evidence={evidence}
            tool_trace={tool_trace}
            limitations={limitations}
            isNoAction={isNoAction}
            lang={lang}
          />
        </>
      )}

      {/* What this demo does not do (limitations, user-friendly) */}
      <section className="section">
        <h2 className="section__title">{copy.limitationsSection.title[lang]}</h2>
        <p className="section__hint">{copy.limitationsSection.hint[lang]}</p>
        <div className="limitations-grid">
          {copy.limitationsSection.items.map((item, i) => (
            <div className="limitation" key={i}>
              <p className="limitation__title">{item.title[lang]}</p>
              <p className="limitation__explain">{item.explain[lang]}</p>
            </div>
          ))}
        </div>

        {/* All limitations (audit) — in console mode this lives inside
            the collapsed <details> above via AuditSections, so only
            render here in report mode. */}
        {!isConsole && (
          <div style={{ marginTop: "var(--space-md)" }}>
            <p
              className="field__label"
              style={{ marginBottom: 4 }}
            >
              {copy.limitationsSection.auditTitle[lang]}
            </p>
            <ul
              style={{
                margin: 0,
                paddingLeft: "1.1rem",
                fontSize: "0.82rem",
                color: "var(--ink-soft)",
                lineHeight: 1.7,
              }}
            >
              {limitations.map((lim, i) => (
                <li key={i} style={{ marginBottom: 2 }}>
                  {lim}
                </li>
              ))}
              {evaluation.limitations.map((lim, i) => (
                <li key={`ev-${i}`} style={{ marginBottom: 2 }}>
                  {lim}
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  );
}

// ---- Audit sections (risks / evidence / fallback / evaluation issues /
//      tool trace / proposal field grid / raw limitations) ----
//      Rendered inline in "report" variant and inside a collapsed
//      <details> in "console" variant. Field completeness is identical.

function AuditSections({
  proposal,
  evaluation,
  evidence,
  tool_trace,
  limitations,
  isNoAction,
  lang,
}: {
  proposal: DemoPayload["proposal"];
  evaluation: DemoPayload["evaluation"];
  evidence: DemoPayload["evidence"];
  tool_trace: DemoPayload["tool_trace"];
  limitations: DemoPayload["limitations"];
  isNoAction: boolean;
  lang: Lang;
}) {
  return (
    <>
      {/* Risks */}
      <section className="section">
        <h2 className="section__title">{copy.risksSection.title[lang]}</h2>
        <p className="section__hint">{copy.risksSection.hint[lang]}</p>
        {proposal.risks.map((risk, i) => (
          <RiskCard key={`${risk.code}-${i}`} risk={risk} lang={lang} />
        ))}
      </section>

      {/* Evidence */}
      <section className="section">
        <h2 className="section__title">{copy.evidenceSection.title[lang]}</h2>
        <p className="section__hint">{copy.evidenceSection.hint[lang]}</p>
        {evidence.map((ev) => (
          <EvidenceItem key={ev.evidence_id} evidence={ev} lang={lang} />
        ))}
      </section>

      {/* Fallback reasons (strict-budget scenario) */}
      {proposal.fallback_reasons.length > 0 && (
        <section className="section">
          <h2 className="section__title">{copy.fallbackSection.title[lang]}</h2>
          <p className="section__hint">
            {isNoAction
              ? `${copy.fallbackSection.strictExplain[lang]} ${copy.fallbackSection.hint[lang]}`
              : copy.fallbackSection.hint[lang]}
          </p>
          <ul className="fallback-list">
            {proposal.fallback_reasons.map((reason, i) => (
              <li key={i}>{reason}</li>
            ))}
          </ul>
        </section>
      )}

      {/* Evaluation issues & remediation */}
      <section className="section">
        <h2 className="section__title">{copy.evaluationSection.title[lang]}</h2>
        <p className="section__hint">{copy.evaluationSection.hint[lang]}</p>

        {evaluation.issues.length === 0 ? (
          <p style={{ fontSize: "0.88rem", color: "var(--ink-soft)" }}>
            {copy.evaluationSection.noIssues[lang]}
          </p>
        ) : (
          evaluation.issues.map((issue, i) => (
            <IssueItem key={`${issue.code}-${i}`} issue={issue} lang={lang} />
          ))
        )}

        {/* Passed / failed / warnings check lists */}
        <div
          style={{
            marginTop: "var(--space-sm)",
            fontSize: "0.82rem",
            color: "var(--ink-soft)",
          }}
        >
          <p style={{ margin: "4px 0" }}>
            <strong>{copy.evaluationSection.passedChecks[lang]}:</strong>{" "}
            {evaluation.passed_checks.length > 0
              ? evaluation.passed_checks.join(", ")
              : copy.empty.none[lang]}
          </p>
          <p style={{ margin: "4px 0" }}>
            <strong>{copy.evaluationSection.failedChecks[lang]}:</strong>{" "}
            {evaluation.failed_checks.length > 0
              ? evaluation.failed_checks.join(", ")
              : copy.empty.none[lang]}
          </p>
          <p style={{ margin: "4px 0" }}>
            <strong>{copy.evaluationSection.warnings[lang]}:</strong>{" "}
            {evaluation.warnings.length > 0
              ? evaluation.warnings.join(", ")
              : copy.empty.none[lang]}
          </p>
        </div>
      </section>

      {/* Audit trail: tool call trace */}
      <section className="section">
        <h2 className="section__title">{copy.auditSection.title[lang]}</h2>
        <p className="section__hint">{copy.auditSection.hint[lang]}</p>
        <ul className="audit-list">
          {tool_trace.map((trace, i) => (
            <ToolTraceItem key={`${trace.tool_name}-${i}`} trace={trace} lang={lang} />
          ))}
        </ul>
      </section>

      {/* Proposal-level audit details */}
      <section className="section">
        <h2 className="section__title">{copy.proposalAudit.title[lang]}</h2>
        <div className="field-grid">
          <Field
            label={copy.fields.proposal_id[lang]}
            value={proposal.proposal_id}
            mono
          />
          <Field label={copy.fields.team_id[lang]} value={proposal.team_id} mono />
          <Field label={copy.fields.objective[lang]} value={proposal.objective} />
          <Field label={copy.fields.status[lang]} value={proposal.status} />
          <Field
            label={copy.fields.requires_human_approval[lang]}
            value={formatBool(proposal.requires_human_approval, lang)}
          />
          <Field
            label={copy.fields.sample_data[lang]}
            value={formatBool(proposal.sample_data, lang)}
          />
          <Field
            label={copy.fields.cap_summary[lang]}
            value={proposal.cap_summary}
          />
          <Field
            label={copy.fields.roster_need_summary[lang]}
            value={proposal.roster_need_summary}
          />
          <Field
            label={copy.fields.depth_chart_summary[lang]}
            value={proposal.depth_chart_summary}
          />
          <Field
            label={copy.fields.fallback_reasons[lang]}
            value={
              proposal.fallback_reasons.length > 0
                ? proposal.fallback_reasons.join(" | ")
                : copy.empty.none[lang]
            }
          />
        </div>
      </section>

      {/* Raw limitations audit list */}
      <section className="section">
        <p className="field__label" style={{ marginBottom: 4 }}>
          {copy.limitationsSection.auditTitle[lang]}
        </p>
        <ul
          style={{
            margin: 0,
            paddingLeft: "1.1rem",
            fontSize: "0.82rem",
            color: "var(--ink-soft)",
            lineHeight: 1.7,
          }}
        >
          {limitations.map((lim, i) => (
            <li key={i} style={{ marginBottom: 2 }}>
              {lim}
            </li>
          ))}
          {evaluation.limitations.map((lim, i) => (
            <li key={`ev-${i}`} style={{ marginBottom: 2 }}>
              {lim}
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
