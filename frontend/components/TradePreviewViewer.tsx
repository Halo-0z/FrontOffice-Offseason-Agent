"use client";

/**
 * TradePreviewViewer — M6-D bilingual trade preview viewer.
 *
 * Two-layer design (mirrors ProposalViewer):
 *   1. User summary layer (plain Chinese/English: trade teams, outgoing
 *      / incoming assets, rule check result, post-trade roster / depth
 *      chart impact, risks, why human approval is still required).
 *   2. Audit trail layer (all professional fields preserved:
 *      transaction_id, validation issues, salary matching details, cap
 *      summary before/after, full depth chart slots, roster need report,
 *      raw limitations).
 *
 * Display only. No API calls, no LLM, no MCP, no data mutation, no
 * transaction approval. All data is sample / simulation JSON.
 *
 * Milestone: M6-D (Static Trade Preview Scenario).
 */

import type {
  DemoTradePayload,
  TransactionAssetData,
  CapSummaryData,
  ValidationIssueData,
  DepthChartSlotData,
  PositionNeedData,
} from "../data/demoTradePreviewPayload";
import { copy, type Lang, formatSalary, formatBool } from "../data/i18n";

interface TradePreviewViewerProps {
  payload: DemoTradePayload;
  lang: Lang;
}

// ---- Helpers ----

function statusClass(status: string): string {
  if (status === "PASS") return "status-card__value--ok";
  if (status === "WARNING") return "status-card__value--warn";
  if (status === "FAIL") return "status-card__value--bad";
  return "";
}

function needLevelClass(level: string): string {
  const l = level.toLowerCase();
  if (l === "high") return "depth-slot--high";
  if (l === "medium") return "depth-slot--medium";
  return "depth-slot--low";
}

function priorityClass(priority: string): string {
  const p = priority.toLowerCase();
  if (p === "high") return "need-item--high";
  if (p === "medium") return "need-item--medium";
  return "need-item--low";
}

// ---- Sub-components ----

function AssetCard({
  asset,
  lang,
  direction,
}: {
  asset: TransactionAssetData;
  lang: Lang;
  direction: "out" | "in";
}) {
  const t = copy.trade;
  return (
    <div className={`trade-asset ${direction === "out" ? "trade-asset--out" : "trade-asset--in"}`}>
      <div className="trade-asset__head">
        <span className="trade-asset__player">{asset.player_id}</span>
        <span className={`badge ${direction === "out" ? "badge--warn" : "badge--ok"}`}>
          {direction === "out" ? "OUT" : "IN"}
        </span>
      </div>
      <div className="field-grid">
        <div className="field">
          <p className="field__label">{t.contractId[lang]}</p>
          <p className="field__value field__value--mono">{asset.contract_id ?? copy.empty.na[lang]}</p>
        </div>
        <div className="field">
          <p className="field__label">{copy.fields.salary[lang]}</p>
          <p className="field__value">{formatSalary(asset.salary, lang)}</p>
        </div>
        <div className="field">
          <p className="field__label">{t.fromTeam[lang]}</p>
          <p className="field__value field__value--mono">{asset.from_team_id ?? copy.empty.na[lang]}</p>
        </div>
        <div className="field">
          <p className="field__label">{t.toTeam[lang]}</p>
          <p className="field__value field__value--mono">{asset.to_team_id ?? copy.empty.na[lang]}</p>
        </div>
        <div className="field">
          <p className="field__label">{t.assetType[lang]}</p>
          <p className="field__value field__value--mono">{asset.asset_type}</p>
        </div>
      </div>
    </div>
  );
}

function CapSummaryCard({
  summary,
  lang,
  label,
}: {
  summary: CapSummaryData;
  lang: Lang;
  label: string;
}) {
  const t = copy.trade;
  return (
    <div className="cap-summary-card">
      <p className="cap-summary-card__label">{label}</p>
      <div className="field-grid">
        <div className="field">
          <p className="field__label">{t.totalSalary[lang]}</p>
          <p className="field__value">{formatSalary(summary.total_salary, lang)}</p>
        </div>
        <div className="field">
          <p className="field__label">{t.capSpace[lang]}</p>
          <p className="field__value">{formatSalary(summary.cap_space, lang)}</p>
        </div>
        <div className="field">
          <p className="field__label">{t.taxDistance[lang]}</p>
          <p className="field__value">{formatSalary(summary.tax_distance, lang)}</p>
        </div>
        <div className="field">
          <p className="field__label">{t.firstApronDistance[lang]}</p>
          <p className="field__value">{formatSalary(summary.first_apron_distance, lang)}</p>
        </div>
        <div className="field">
          <p className="field__label">{t.secondApronDistance[lang]}</p>
          <p className="field__value">{formatSalary(summary.second_apron_distance, lang)}</p>
        </div>
        <div className="field">
          <p className="field__label">{t.rosterCount[lang]}</p>
          <p className="field__value">{summary.roster_count}</p>
        </div>
      </div>
    </div>
  );
}

function DepthChartTable({ slots, lang }: { slots: DepthChartSlotData[]; lang: Lang }) {
  const t = copy.trade;
  return (
    <div className="depth-chart-table">
      <table className="depth-chart-table__table">
        <thead>
          <tr>
            <th>{t.position[lang]}</th>
            <th>{t.starter[lang]}</th>
            <th>{t.backups[lang]}</th>
            <th>{t.needLevel[lang]}</th>
          </tr>
        </thead>
        <tbody>
          {slots.map((slot) => (
            <tr key={slot.position} className={needLevelClass(slot.need_level)}>
              <td className="depth-chart-table__pos">{slot.position}</td>
              <td>
                {slot.starter ? (
                  <span>
                    {slot.starter.name}{" "}
                    <span className="depth-chart-table__meta">
                      ({slot.starter.player_id})
                    </span>
                  </span>
                ) : (
                  <span className="depth-chart-table__empty">{copy.empty.none[lang]}</span>
                )}
              </td>
              <td>
                {slot.backups.length > 0
                  ? slot.backups.map((b) => b.name).join(", ")
                  : copy.empty.none[lang]}
              </td>
              <td>
                <span className={`badge badge--${slot.need_level === "high" ? "bad" : slot.need_level === "medium" ? "warn" : "ok"}`}>
                  {slot.need_level}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RosterNeedList({ needs, lang }: { needs: PositionNeedData[]; lang: Lang }) {
  const t = copy.trade;
  if (needs.length === 0) return null;
  return (
    <ul className="roster-need-list">
      {needs.map((need) => (
        <li key={need.position} className={`need-item ${priorityClass(need.priority)}`}>
          <span className="need-item__pos">{need.position}</span>
          <span className="need-item__detail">
            {t.currentCount[lang]}: {need.current_count} / {t.targetCount[lang]}: {need.target_count}
          </span>
          <span className={`badge badge--${need.priority === "high" ? "bad" : need.priority === "medium" ? "warn" : "ok"}`}>
            {need.priority}
          </span>
        </li>
      ))}
    </ul>
  );
}

function IssueList({ issues, lang, emptyText }: { issues: ValidationIssueData[]; lang: Lang; emptyText: string }) {
  if (issues.length === 0) {
    return <p className="audit-empty">{emptyText}</p>;
  }
  return (
    <ul className="issue-list">
      {issues.map((iss, i) => (
        <li key={i} className={`issue-item ${iss.severity === "INFO" ? "issue-item--info" : iss.severity === "WARNING" ? "issue-item--warn" : "issue-item--bad"}`}>
          <div className="issue-item__head">
            <span className={`badge ${iss.severity === "FAIL" ? "badge--bad" : "badge--warn"}`}>
              {iss.severity}
            </span>
            <span className="issue-item__code">{iss.code}</span>
          </div>
          <p className="issue-item__summary">{iss.message}</p>
          {iss.field && (
            <p className="issue-item__meta">field: {iss.field}</p>
          )}
        </li>
      ))}
    </ul>
  );
}

// ---- Audit sections (collapsible) ----

function TradeAuditSections({ payload, lang }: { payload: DemoTradePayload; lang: Lang }) {
  const t = copy.trade;
  const tx = payload.trade_transaction;
  const vr = payload.preview.validation_result;
  const sm = payload.salary_matching;

  return (
    <div className="audit-sections">
      {/* Transaction details */}
      <section className="audit-block">
        <h4 className="audit-block__title">{t.transactionId[lang]}</h4>
        <div className="field-grid">
          <div className="field">
            <p className="field__label">{t.transactionId[lang]}</p>
            <p className="field__value field__value--mono">{tx.transaction_id}</p>
          </div>
          <div className="field">
            <p className="field__label">{t.transactionType[lang]}</p>
            <p className="field__value field__value--mono">{tx.transaction_type}</p>
          </div>
          <div className="field">
            <p className="field__label">{t.validationStatus[lang]}</p>
            <p className="field__value field__value--mono">{vr.status}</p>
          </div>
          <div className="field">
            <p className="field__label">{t.isValid[lang]}</p>
            <p className="field__value">{formatBool(vr.is_valid, lang)}</p>
          </div>
        </div>
      </section>

      {/* Validation issues */}
      <section className="audit-block">
        <h4 className="audit-block__title">{copy.evaluationSection.title[lang]}</h4>
        <p className="audit-block__sub">{copy.evaluationSection.failedChecks[lang]}</p>
        <IssueList issues={vr.issues} lang={lang} emptyText={t.noIssues[lang]} />
        <p className="audit-block__sub" style={{ marginTop: 8 }}>{copy.evaluationSection.warnings[lang]}</p>
        <IssueList issues={vr.warnings} lang={lang} emptyText={t.noWarnings[lang]} />
      </section>

      {/* Salary matching details */}
      <section className="audit-block">
        <h4 className="audit-block__title">{t.salaryMatchTitle[lang]}</h4>
        <p className="audit-block__sub">{sm.rule}</p>
        <div className="salary-match-detail">
          <div className="salary-match-side">
            <p className="salary-match-side__team">{sm.team_a.team_id}</p>
            <div className="field-grid">
              <div className="field">
                <p className="field__label">{t.outgoingSalary[lang]}</p>
                <p className="field__value">{formatSalary(sm.team_a.outgoing_salary, lang)}</p>
              </div>
              <div className="field">
                <p className="field__label">{t.incomingSalary[lang]}</p>
                <p className="field__value">{formatSalary(sm.team_a.incoming_salary, lang)}</p>
              </div>
              <div className="field">
                <p className="field__label">{t.threshold[lang]}</p>
                <p className="field__value">{formatSalary(sm.team_a.threshold, lang)}</p>
              </div>
              <div className="field">
                <p className="field__label">{t.passed[lang]}</p>
                <p className="field__value">{formatBool(sm.team_a.passed, lang)}</p>
              </div>
            </div>
          </div>
          <div className="salary-match-side">
            <p className="salary-match-side__team">{sm.team_b.team_id}</p>
            <div className="field-grid">
              <div className="field">
                <p className="field__label">{t.outgoingSalary[lang]}</p>
                <p className="field__value">{formatSalary(sm.team_b.outgoing_salary, lang)}</p>
              </div>
              <div className="field">
                <p className="field__label">{t.incomingSalary[lang]}</p>
                <p className="field__value">{formatSalary(sm.team_b.incoming_salary, lang)}</p>
              </div>
              <div className="field">
                <p className="field__label">{t.threshold[lang]}</p>
                <p className="field__value">{formatSalary(sm.team_b.threshold, lang)}</p>
              </div>
              <div className="field">
                <p className="field__label">{t.passed[lang]}</p>
                <p className="field__value">{formatBool(sm.team_b.passed, lang)}</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Cap summary before / after */}
      {vr.cap_summary_before && vr.cap_summary_after && (
        <section className="audit-block">
          <h4 className="audit-block__title">{t.capBefore[lang]} / {t.capAfter[lang]}</h4>
          <div className="cap-summary-grid">
            <CapSummaryCard summary={vr.cap_summary_before} lang={lang} label={t.capBefore[lang]} />
            <CapSummaryCard summary={vr.cap_summary_after} lang={lang} label={t.capAfter[lang]} />
          </div>
        </section>
      )}

      {/* Depth chart after */}
      {payload.preview.depth_chart_after && (
        <section className="audit-block">
          <h4 className="audit-block__title">{t.depthChartAfter[lang]}</h4>
          <DepthChartTable slots={payload.preview.depth_chart_after.slots} lang={lang} />
        </section>
      )}

      {/* Roster need after */}
      {payload.preview.roster_need_after && (
        <section className="audit-block">
          <h4 className="audit-block__title">{t.rosterNeedAfter[lang]}</h4>
          <RosterNeedList needs={payload.preview.roster_need_after.needs} lang={lang} />
        </section>
      )}

      {/* Raw limitations */}
      <section className="audit-block">
        <h4 className="audit-block__title">{copy.fields.limitations[lang]}</h4>
        <ul className="audit-limitations">
          {payload.preview.limitations.map((lim, i) => (
            <li key={i}>{lim}</li>
          ))}
          {payload.preview.validation_result.limitations.map((lim, i) => (
            <li key={`vr-${i}`}>{lim}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}

// ---- Main component ----

export default function TradePreviewViewer({ payload, lang }: TradePreviewViewerProps) {
  const t = copy.trade;
  const tx = payload.trade_transaction;
  const vr = payload.preview.validation_result;
  const sm = payload.salary_matching;

  const statusBadgeClass =
    vr.status === "PASS" ? "badge--ok" : vr.status === "WARNING" ? "badge--warn" : "badge--bad";

  const outputLine =
    vr.status === "PASS"
      ? t.outputPass[lang]
      : vr.status === "WARNING"
        ? t.outputWarn[lang]
        : t.outputFail[lang];

  return (
    <div lang={lang}>
      {/* Approval boundary banner */}
      <div className="approval-banner">
        <strong>{copy.approvalBanner.strong[lang]}</strong>{" "}
        {t.boundary[lang]}
      </div>

      {/* Summary block */}
      <div className="summary-block">
        <p className="summary-headline">{t.outputHeadline[lang]}</p>
        <p className="summary-body">{outputLine}</p>
      </div>

      {/* Status cards */}
      <div className="status-grid">
        <div className="status-card">
          <p className="status-card__label">{t.validationStatus[lang]}</p>
          <p className={`status-card__value ${statusClass(vr.status)}`}>{vr.status}</p>
          <p className="status-card__explain" lang={lang}>{outputLine}</p>
        </div>
        <div className="status-card">
          <p className="status-card__label">{t.isValid[lang]}</p>
          <p className={`status-card__value ${vr.is_valid ? "status-card__value--ok" : "status-card__value--bad"}`}>
            {formatBool(vr.is_valid, lang)}
          </p>
          <p className="status-card__explain" lang={lang}>
            {vr.is_valid
              ? copy.statusCards.evaluationExplain.PASS[lang]
              : copy.statusCards.evaluationExplain.FAIL[lang]}
          </p>
        </div>
        <div className="status-card">
          <p className="status-card__label">{copy.statusCards.approvalLabel[lang]}</p>
          <p className="status-card__value status-card__value--warn">{formatBool(payload.requires_human_approval, lang)}</p>
          <p className="status-card__explain" lang={lang}>{copy.statusCards.approvalYes[lang]}</p>
        </div>
        <div className="status-card">
          <p className="status-card__label">{copy.statusCards.sampleLabel[lang]}</p>
          <p className="status-card__value status-card__value--ok">{formatBool(payload.sample_data, lang)}</p>
          <p className="status-card__explain" lang={lang}>{copy.statusCards.sampleYes[lang]}</p>
        </div>
      </div>

      {/* Trade teams */}
      <section className="section">
        <h3 className="section__title">{t.teamsTitle[lang]}</h3>
        <div className="trade-teams">
          <div className="trade-team">
            <span className="trade-team__label">A</span>
            <span className="trade-team__id">{tx.team_a_id}</span>
          </div>
          <span className="trade-arrow" aria-hidden="true">⇄</span>
          <div className="trade-team">
            <span className="trade-team__label">B</span>
            <span className="trade-team__id">{tx.team_b_id}</span>
          </div>
        </div>
      </section>

      {/* Trade assets */}
      <section className="section">
        <h3 className="section__title">{t.assetsTitle[lang]}</h3>
        <div className="trade-assets-grid">
          <div className="trade-assets-column">
            <p className="trade-assets-column__title">{t.outgoingFromA[lang]} / {t.incomingToB[lang]}</p>
            {tx.outgoing_from_a.map((a, i) => (
              <AssetCard key={i} asset={a} lang={lang} direction="out" />
            ))}
          </div>
          <div className="trade-assets-column">
            <p className="trade-assets-column__title">{t.outgoingFromB[lang]} / {t.incomingToA[lang]}</p>
            {tx.outgoing_from_b.map((a, i) => (
              <AssetCard key={i} asset={a} lang={lang} direction="in" />
            ))}
          </div>
        </div>
      </section>

      {/* Salary matching summary (user-readable) */}
      <section className="section">
        <h3 className="section__title">{t.salaryMatchTitle[lang]}</h3>
        <p className="section__hint">{sm.rule}</p>
        <div className="salary-match-grid">
          <div className={`salary-match-card ${sm.team_a.passed ? "salary-match-card--ok" : "salary-match-card--bad"}`}>
            <p className="salary-match-card__team">{sm.team_a.team_id}</p>
            <p className="salary-match-card__detail">
              {t.outgoingSalary[lang]}: {formatSalary(sm.team_a.outgoing_salary, lang)} →{" "}
              {t.incomingSalary[lang]}: {formatSalary(sm.team_a.incoming_salary, lang)}
            </p>
            <span className={`badge ${sm.team_a.passed ? "badge--ok" : "badge--bad"}`}>
              {sm.team_a.passed ? "PASS" : "FAIL"}
            </span>
          </div>
          <div className={`salary-match-card ${sm.team_b.passed ? "salary-match-card--ok" : "salary-match-card--bad"}`}>
            <p className="salary-match-card__team">{sm.team_b.team_id}</p>
            <p className="salary-match-card__detail">
              {t.outgoingSalary[lang]}: {formatSalary(sm.team_b.outgoing_salary, lang)} →{" "}
              {t.incomingSalary[lang]}: {formatSalary(sm.team_b.incoming_salary, lang)}
            </p>
            <span className={`badge ${sm.team_b.passed ? "badge--ok" : "badge--bad"}`}>
              {sm.team_b.passed ? "PASS" : "FAIL"}
            </span>
          </div>
        </div>
      </section>

      {/* Post-trade impact */}
      <section className="section">
        <h3 className="section__title">{t.impactTitle[lang]}</h3>
        <div className="impact-grid">
          {payload.roster_impact_summary && (
            <div className="impact-card">
              <p className="impact-card__label">{t.rosterImpactLabel[lang]}</p>
              <p className="impact-card__body">{payload.roster_impact_summary}</p>
            </div>
          )}
          {payload.depth_chart_impact_summary && (
            <div className="impact-card">
              <p className="impact-card__label">{t.depthChartImpactLabel[lang]}</p>
              <p className="impact-card__body">{payload.depth_chart_impact_summary}</p>
            </div>
          )}
          {payload.cap_impact_summary && (
            <div className="impact-card">
              <p className="impact-card__label">{t.capImpactLabel[lang]}</p>
              <p className="impact-card__body">{payload.cap_impact_summary}</p>
            </div>
          )}
        </div>
      </section>

      {/* Why human approval is still required */}
      <section className="section">
        <h3 className="section__title">{t.whyApprovalTitle[lang]}</h3>
        <div className="approval-reminder">
          <p>{t.whyApprovalBody[lang]}</p>
        </div>
      </section>

      {/* Risks */}
      <section className="section">
        <h3 className="section__title">{t.risksTitle[lang]}</h3>
        <ul className="risk-list">
          <li className="risk-card risk-card--medium">
            <p className="risk-card__plain" lang={lang}>{t.riskSgGap[lang]}</p>
          </li>
          <li className="risk-card risk-card--low">
            <p className="risk-card__plain" lang={lang}>{t.riskSalaryUp[lang]}</p>
          </li>
          <li className="risk-card risk-card--medium">
            <p className="risk-card__plain" lang={lang}>{t.riskTeamBDeferred[lang]}</p>
          </li>
          <li className="risk-card risk-card--low">
            <p className="risk-card__plain" lang={lang}>{t.riskSampleData[lang]}</p>
          </li>
        </ul>
      </section>

      {/* Collapsible audit details */}
      <details className="audit-details">
        <summary>{t.auditToggle[lang]}</summary>
        <p className="audit-details__hint">{t.auditToggleHint[lang]}</p>
        <TradeAuditSections payload={payload} lang={lang} />
      </details>
    </div>
  );
}
