"use client";

/**
 * Offseason Agent Console page -- two-column command center layout.
 *
 * Layout: LEFT SIDEBAR (260px, nav + session) | RIGHT MAIN (3-column grid: input | decision+proposal | pipeline+indicators+metrics)
 *
 * API-first behavior: clicking generate calls the local backend API first;
 * if the backend is unavailable, falls back to local static sample payloads.
 *
 * Guardrails: unchanged.
 * Language: Chinese default, toggle to English.
 */

import React, { useCallback, useEffect, useState } from "react";
import ProposalViewer from "../../components/ProposalViewer";
import TradePreviewViewer from "../../components/TradePreviewViewer";
import { scenarios } from "../../data/demoProposalPayload";
import { demoTradePayload } from "../../data/demoTradePreviewPayload";
import { copy, type Lang, formatSalary } from "../../data/i18n";
import {
  ApiError,
  API_BASE_URL,
  DEMO_PROPOSAL_REQUESTS,
  fetchProposalPreview,
  fetchTradePreviewDemo,
  fetchHealth,
  type HealthResponse,
  type ProposalPreviewParams,
} from "../../lib/apiClient";
import type { DemoPayload } from "../../data/demoProposalPayload";
import type { DemoTradePayload } from "../../data/demoTradePreviewPayload";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Mode = "signing" | "hold" | "trade";
type RunState = "idle" | "running" | "complete";
type DataSource = "idle" | "api" | "fallback";

/**
 * Health state. `online=false` means the backend was unreachable and
 * the page is using local fallback samples. When `online=true`, the
 * additive fields mirror the backend `/api/health` response
 * (M8-C1/C2). The `kind` discriminator drives the user-friendly data
 * source card: "demo" | "snapshot" | "offline".
 */
interface HealthState {
  online: boolean;
  status: string;
  sample: boolean;
  kind: "demo" | "snapshot" | "offline";
  dataMode?: string | null;
  activeDataSource?: string | null;
  snapshotId?: string | null;
  snapshotValid?: boolean | null;
  snapshotIsFixture?: boolean | null;
  snapshotType?: string | null;
  snapshotWarnings?: string[] | null;
  fallbackReason?: string | null;
  strictSnapshot?: boolean | null;
}

interface RunResult {
  mode: Mode;
  source: "api" | "fallback";
  fallbackReason?: string;
  proposal: DemoPayload | null;
  trade: DemoTradePayload | null;
}

// ---------------------------------------------------------------------------
// Helpers (unchanged from original)
// ---------------------------------------------------------------------------

function modeToScenarioId(mode: Mode): string {
  return mode === "signing" ? "default" : "strict-budget";
}

function getStaticFallback(mode: Mode): {
  proposal: DemoPayload | null;
  trade: DemoTradePayload | null;
} {
  if (mode === "trade") {
    return { proposal: null, trade: demoTradePayload };
  }
  const scenarioId = modeToScenarioId(mode);
  const scenario = scenarios.find((s) => s.id === scenarioId);
  return { proposal: scenario?.payload ?? null, trade: null };
}

function explainApiError(err: ApiError, lang: Lang): string {
  const kind = err.kind;
  if (lang === "zh") {
    switch (kind) {
      case "network":
        return `无法连接后端 API（${err.url}）。请确认 uvicorn 已启动。`;
      case "timeout":
        return `后端 API 请求超时（${err.url}）。`;
      case "non-2xx":
        return `后端 API 返回非 2xx 状态码（${err.status ?? "?"} ${err.url}）。`;
      case "invalid-json":
        return `后端 API 返回的 JSON 无法解析（${err.url}）。`;
      default:
        return `后端 API 调用失败：${err.message}`;
    }
  }
  switch (kind) {
    case "network":
      return `Cannot reach backend API (${err.url}). Is uvicorn running?`;
    case "timeout":
      return `Backend API request timed out (${err.url}).`;
    case "non-2xx":
      return `Backend API returned non-2xx status (${err.status ?? "?"} ${err.url}).`;
    case "invalid-json":
      return `Backend API returned invalid JSON (${err.url}).`;
    default:
      return `Backend API call failed: ${err.message}`;
  }
}

// ---------------------------------------------------------------------------
// Nav SVG icons
// ---------------------------------------------------------------------------

function NavIconHome() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  );
}

function NavIconConsole() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <rect width="7" height="9" x="3" y="3" rx="1" />
      <rect width="7" height="5" x="14" y="3" rx="1" />
      <rect width="7" height="9" x="14" y="12" rx="1" />
      <rect width="7" height="5" x="3" y="16" rx="1" />
    </svg>
  );
}

function NavIconCapSheet() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <path d="M12 3v18" />
      <rect width="18" height="18" x="3" y="3" rx="2" />
      <path d="M3 9h18" />
      <path d="M3 15h18" />
    </svg>
  );
}

function NavIconDepthChart() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z" />
      <path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65" />
      <path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65" />
    </svg>
  );
}

function NavIconSettings() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg className="console-pipeline-step__icon" viewBox="0 0 24 24" fill="none" stroke="var(--success-600)" strokeWidth="2.5">
      <path d="M20 6 9 17l-5-5" />
    </svg>
  );
}

function CircleIcon() {
  return (
    <svg className="console-pipeline-step__icon" viewBox="0 0 24 24" fill="none" stroke="var(--muted-foreground)" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
    </svg>
  );
}

function ChevronDownIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polygon points="6 3 20 12 6 21 6 3" />
    </svg>
  );
}

function ShieldIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--brand-700)" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function OffseasonPage() {
  // -- State --
  const [lang, setLang] = useState<Lang>("zh");
  const [mode, setMode] = useState<Mode>("signing");
  const [runState, setRunState] = useState<RunState>("idle");
  const [result, setResult] = useState<RunResult | null>(null);
  const [dataSource, setDataSource] = useState<DataSource>("idle");
  const [healthState, setHealthState] = useState<HealthState>({
    online: false,
    status: "offline",
    sample: true,
    kind: "offline",
  });
  const [activeNav, setActiveNav] = useState<string>("console");

  // -- Health check on mount --
  // Derive `kind` from the additive metadata: snapshot mode when
  // data_mode === "snapshot" and the backend is online; demo mode
  // otherwise. Offline when the fetch fails.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const health: HealthResponse = await fetchHealth();
        if (!cancelled) {
          const kind: HealthState["kind"] =
            health.data_mode === "snapshot" ? "snapshot" : "demo";
          setHealthState({
            online: true,
            status: health.status,
            sample: health.sample_data,
            kind,
            dataMode: health.data_mode ?? null,
            activeDataSource: health.active_data_source ?? null,
            snapshotId: health.snapshot_id ?? null,
            snapshotValid: health.snapshot_valid ?? null,
            snapshotIsFixture: health.snapshot_is_fixture ?? null,
            snapshotType: health.snapshot_type ?? null,
            snapshotWarnings: health.snapshot_warnings ?? null,
            fallbackReason: health.fallback_reason ?? null,
            strictSnapshot: health.strict_snapshot ?? null,
          });
          setDataSource("idle");
        }
      } catch {
        if (!cancelled) {
          setHealthState({
            online: false,
            status: "offline",
            sample: true,
            kind: "offline",
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // -- Generate proposal (API first, fallback to sample) --
  const handleGenerate = useCallback(async () => {
    if (runState === "running") return;
    setRunState("running");

    const currentMode = mode;
    let apiResult: RunResult;

    try {
      if (currentMode === "trade") {
        const trade = await fetchTradePreviewDemo();
        apiResult = { mode: currentMode, source: "api", proposal: null, trade };
      } else {
        const params: ProposalPreviewParams =
          currentMode === "signing"
            ? DEMO_PROPOSAL_REQUESTS.signing
            : DEMO_PROPOSAL_REQUESTS.hold;
        const proposal = await fetchProposalPreview(params);
        apiResult = { mode: currentMode, source: "api", proposal, trade: null };
      }
      setDataSource("api");
    } catch (err) {
      const fallback = getStaticFallback(currentMode);
      const reason =
        err instanceof ApiError
          ? explainApiError(err, lang)
          : err instanceof Error
            ? err.message
            : String(err);
      apiResult = {
        mode: currentMode,
        source: "fallback",
        fallbackReason: reason,
        proposal: fallback.proposal,
        trade: fallback.trade,
      };
      setDataSource("fallback");
    }

    setResult(apiResult);
    setRunState("complete");
  }, [runState, mode, lang]);

  // -- Reset when mode changes --
  useEffect(() => {
    if (result !== null && result.mode !== mode) {
      setRunState("idle");
      setResult(null);
      setDataSource("idle");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  // -- Copy references --
  const c = copy.console;
  const cm = copy.consoleModes;
  const ds = copy.dataSource;
  const db = copy.dashboard;
  const cs = copy.consoleShell;

  // -- Derived values --
  const isTrade = result?.mode === "trade";
  const isHold = !isTrade && result?.proposal?.proposal.status === "NO_ACTION";

  const completedSteps =
    runState === "complete" && result
      ? isTrade
        ? result.trade?.preview.validation_result.issues.length === 0
          ? 7
          : 5
        : 7
      : 0;

  const steps =
    result?.mode === "trade"
      ? [
          { zh: "读取两队薪资空间", en: "Read both teams' cap space" },
          { zh: "构造交易资产", en: "Build trade assets" },
          { zh: "检查薪资配平", en: "Check salary matching" },
          { zh: "检查阵容人数", en: "Check roster count" },
          { zh: "生成交易后阵容", en: "Build post-trade roster" },
          { zh: "生成交易后深度图", en: "Build post-trade depth chart" },
          { zh: "运行安全检查", en: "Run guardrail checks" },
        ]
      : c.steps;

  // -- Nav items with icons --
  const navItems = [
    { id: "home", label: cs.navHome, icon: <NavIconHome /> },
    { id: "console", label: cs.navConsole, icon: <NavIconConsole /> },
    { id: "capsheet", label: cs.navCapSheet, icon: <NavIconCapSheet /> },
    { id: "depthchart", label: cs.navDepthChart, icon: <NavIconDepthChart /> },
    { id: "settings", label: cs.navSettings, icon: <NavIconSettings /> },
  ];

  // -- Modes array --
  const modes = [
    { id: "signing" as Mode, label: cm.signing.label, amount: "$20M" },
    { id: "hold" as Mode, label: cm.hold.label, amount: "$15M" },
    { id: "trade" as Mode, label: cm.trade.label, amount: lang === "zh" ? "模拟" : "Sim" },
  ];

  // -- Mode label for session card --
  const modeLabel =
    mode === "trade"
      ? cm.trade.label[lang]
      : mode === "hold"
        ? cm.hold.label[lang]
        : cm.signing.label[lang];

  // -- Budget label for session card --
  const budgetLabel = mode === "trade" ? "\u2014" : mode === "hold" ? "$15M" : "$20M";

  // -- Status label for session card --
  const statusLabel =
    runState === "running"
      ? cs.statusRunning[lang]
      : runState === "complete"
        ? cs.statusComplete[lang]
        : cs.statusIdle[lang];

  // -- Derived values for column 2 --
  const firstAction = result?.proposal?.actions[0];
  const fitScore = firstAction?.fit_score ?? 0;
  const fitScoreDisplay = (fitScore * 100).toFixed(0);
  const capImpactPercent = firstAction?.salary
    ? Math.min(100, Math.round((firstAction.salary / 20000000) * 100))
    : 0;
  const riskLevel = firstAction
    ? result?.proposal?.proposal.risks.some((r: { level: string }) => r.level === "HIGH")
      ? "HIGH"
      : result?.proposal?.proposal.risks.some((r: { level: string }) => r.level === "MEDIUM")
        ? "MEDIUM"
        : "LOW"
    : "\u2014";

  // -- Indicator rows --
  // M8-D4: replaced engineering jargon (Real NBA Data: false, Data Type:
  // snapshot, Manual Review: true) with plain-language rows driven by
  // the current data source kind. The data type / completeness /
  // needs-review / auto-execute / current-use rows are all user-facing.
  const ud = copy.userData;
  const dataTypeValue =
    healthState.kind === "snapshot"
      ? ud.indicatorDataTypeSnapshot
      : healthState.kind === "demo"
        ? ud.indicatorDataTypeDemo
        : ud.indicatorDataTypeOffline;
  const completenessValue =
    healthState.kind === "snapshot"
      ? ud.indicatorCompletenessSnapshot
      : healthState.kind === "demo"
        ? ud.indicatorCompletenessDemo
        : ud.indicatorCompletenessOffline;
  const needsReviewValue =
    healthState.kind === "snapshot" ? ud.indicatorNeedsReviewYes : ud.indicatorNeedsReviewNo;
  const currentUseValue =
    healthState.kind === "snapshot"
      ? ud.indicatorCurrentUseSnapshot
      : healthState.kind === "demo"
        ? ud.indicatorCurrentUseDemo
        : ud.indicatorCurrentUseOffline;

  const indicatorRows =
    runState === "complete" && result
      ? [
          {
            label: { zh: "提案状态", en: "Proposal" },
            value: { zh: result.proposal?.proposal.status ?? "\u2014", en: result.proposal?.proposal.status ?? "\u2014" },
            ok: ["RECOMMENDED", "PASS"].includes(result.proposal?.proposal.status ?? ""),
          },
          {
            label: { zh: "评估状态", en: "Evaluation" },
            value: { zh: result.proposal?.evaluation.status ?? "\u2014", en: result.proposal?.evaluation.status ?? "\u2014" },
            ok: result.proposal?.evaluation.status === "PASS",
          },
          {
            label: { zh: "人工确认", en: "Approval" },
            value: { zh: result.proposal?.proposal.requires_human_approval ? "需要" : "不需要", en: result.proposal?.proposal.requires_human_approval ? "Required" : "Not required" },
            ok: !result.proposal?.proposal.requires_human_approval,
          },
          {
            label: ud.indicatorDataType,
            value: dataTypeValue,
            ok: healthState.kind === "snapshot",
          },
          {
            label: ud.indicatorCompleteness,
            value: completenessValue,
            ok: false,
          },
          {
            label: ud.indicatorNeedsReview,
            value: needsReviewValue,
            ok: healthState.kind !== "snapshot",
          },
          {
            label: ud.indicatorAutoExecute,
            value: ud.indicatorAutoExecuteNo,
            ok: true,
          },
          {
            label: ud.indicatorCurrentUse,
            value: currentUseValue,
            ok: false,
          },
        ]
      : [];

  return (
    <div className="console-shell" lang={lang}>
      {/* ================================================================ */}
      {/* LEFT SIDEBAR (260px)                                             */}
      {/* ================================================================ */}
      <aside className="console-sidebar">
        {/* Brand: FO mark + "FrontOffice" */}
        <div className="sidebar-brand">
          <div className="sidebar-brand__mark">FO</div>
          <span className="sidebar-brand__name">FrontOffice</span>
          <div className="sidebar-brand__divider" />
        </div>

        {/* Navigation */}
        <nav className="sidebar-nav">
          {navItems.map((item, idx) => (
            <React.Fragment key={item.id}>
              <button
                type="button"
                className={`sidebar-nav__item ${activeNav === item.id ? "sidebar-nav__item--active" : ""}`}
                onClick={() => setActiveNav(item.id)}
              >
                {item.icon}
                {item.label[lang]}
              </button>
              {idx === 3 && <div className="sidebar-nav__separator" />}
            </React.Fragment>
          ))}
        </nav>

        {/* Session context card */}
        <div className="sidebar-session">
          <div className="sidebar-session__card">
            <span className="sidebar-session__title">{cs.sessionTitle[lang]}</span>
            <div className="sidebar-session__rows">
              <div className="sidebar-session__row">
                <span className="sidebar-session__label">{cs.sessionTeam[lang]}</span>
                <span className="sidebar-session__value">DEM (亚特兰大)</span>
              </div>
              <div className="sidebar-session__row">
                <span className="sidebar-session__label">{cs.sessionMode[lang]}</span>
                <span className="sidebar-session__value">{modeLabel}</span>
              </div>
              <div className="sidebar-session__row">
                <span className="sidebar-session__label">{cs.sessionBudget[lang]}</span>
                <span className="sidebar-session__value">{budgetLabel}</span>
              </div>
              <div className="sidebar-session__row">
                <span className={`console-status-dot console-status-dot--${runState}`} />
                <span
                  className="sidebar-session__value"
                  style={{
                    color:
                      runState === "complete"
                        ? "var(--success-600)"
                        : runState === "running"
                          ? "var(--warn-500)"
                          : "var(--muted-foreground)",
                  }}
                >
                  {statusLabel}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Footer: lang switch + version */}
        <div className="sidebar-footer">
          <div className="lang-switch" role="group" aria-label={copy.langSwitch.ariaLabel[lang]}>
            <button
              type="button"
              className={`lang-switch__btn ${lang === "zh" ? "lang-switch__btn--active" : ""}`}
              onClick={() => setLang("zh")}
              aria-pressed={lang === "zh"}
            >
              {copy.langSwitch.zh[lang]}
            </button>
            <button
              type="button"
              className={`lang-switch__btn ${lang === "en" ? "lang-switch__btn--active" : ""}`}
              onClick={() => setLang("en")}
              aria-pressed={lang === "en"}
            >
              {copy.langSwitch.en[lang]}
            </button>
          </div>
          <span className="sidebar-version">v1.0 样例</span>
        </div>
      </aside>

      {/* ================================================================ */}
      {/* RIGHT MAIN AREA                                                  */}
      {/* ================================================================ */}
      <main className="console-main">
        <div className="console-main__inner">
          {/* ROW 1: Header strip */}
          <div className="console-header">
            <div style={{ display: "flex", alignItems: "baseline", gap: "8px" }}>
              <span className="console-header__eyebrow">{cs.workspaceEyebrow[lang]}</span>
              <h1 className="console-header__title">{cs.workspaceTitle[lang]}</h1>
            </div>
            <span className="console-read-only-badge">
              <ShieldIcon />
              <span>{cs.readOnlyBadge[lang]}</span>
            </span>
          </div>

          {/* Fallback banner (only when API failed) */}
          {runState === "complete" && result?.source === "fallback" && (
            <div className="fallback-banner" role="alert">
              <strong>{ds.fallbackBanner[lang]}</strong>
              {result.fallbackReason && <p>{result.fallbackReason}</p>}
            </div>
          )}

          {/* ROW 2: Three-column grid */}
          <div className="console-grid">
            {/* COLUMN 1: Input configuration */}
            <section className="console-input-card">
              <div className="console-input-card__header">
                <h2 className="console-input-card__title">{c.inputTitle[lang]}</h2>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 9, color: "var(--muted-foreground)" }}>配置面板</span>
              </div>
              <div className="console-input-card__body">
                {/* 2x2 grid */}
                <div className="console-field-grid">
                  <div className="console-field">
                    <label className="console-field__label">{c.fieldTeam[lang]}</label>
                    <div className="console-field__input">{c.teamDemAtl[lang]}</div>
                  </div>
                  <div className="console-field">
                    <label className="console-field__label">{c.fieldObjective[lang]}</label>
                    <div className="console-field__input">{c.objectiveValue[lang]}</div>
                  </div>
                  <div className="console-field">
                    <label className="console-field__label">{c.fieldPosition[lang]}</label>
                    <div className="console-field__input">{c.positionValue[lang]}</div>
                  </div>
                  <div className="console-field">
                    <label className="console-field__label">{c.fieldCandidates[lang]}</label>
                    <div className="console-field__input">{c.candidatesValue[lang]}</div>
                  </div>
                </div>
                {/* Evidence query */}
                <div className="console-field">
                  <label className="console-field__label">{c.fieldEvidenceQuery[lang]}</label>
                  <div className="console-field__input">{c.evidenceQueryValue[lang]}</div>
                </div>
                {/* 3 mode cards -- compact, no descriptions */}
                <div className="console-mode-grid">
                  {modes.map((m) => (
                    <div
                      key={m.id}
                      className={`console-mode-card ${mode === m.id ? "console-mode-card--active" : ""}`}
                      onClick={() => {
                        setMode(m.id as Mode);
                        setRunState("idle");
                        setResult(null);
                      }}
                    >
                      <span className="console-mode-card__label">{m.label[lang]}</span>
                      <span className="console-mode-card__amount">{m.amount}</span>
                    </div>
                  ))}
                </div>
                {/* Generate button */}
                <div className="console-generate-row">
                  <button
                    type="button"
                    className="console-generate-btn"
                    onClick={handleGenerate}
                    disabled={runState === "running"}
                  >
                    <PlayIcon />
                    {runState === "complete" ? c.regenerateBtn[lang] : c.generateBtn[lang]}
                  </button>
                  <span className={`console-status-dot console-status-dot--${runState}`} />
                  <span className="console-status-text">
                    {runState === "idle"
                      ? c.stateIdle[lang]
                      : runState === "running"
                        ? ds.loadingApi[lang]
                        : c.stateComplete[lang]}
                  </span>
                </div>
              </div>
            </section>

            {/* COLUMN 2: Decision summary + Proposal detail */}
            <div style={{ display: "flex", flexDirection: "column", gap: "12px", minWidth: 0 }}>
              {runState === "complete" && result ? (
                isTrade && result.trade ? (
                  <>
                    {/* Trade matchup strip */}
                    <div className="console-matchup-strip">
                      <span className="console-matchup-strip__team">{result.trade.trade_transaction.team_a_id}</span>
                      <span className="console-matchup-strip__arrow">&#8644;</span>
                      <span className="console-matchup-strip__team">{result.trade.trade_transaction.team_b_id}</span>
                    </div>
                    {/* Trade details -- render TradePreviewViewer in console mode */}
                    <div className="console-proposal-card" style={{ flex: 1 }}>
                      <TradePreviewViewer payload={result.trade} lang={lang} variant="console" />
                    </div>
                  </>
                ) : result.proposal ? (
                  <>
                    {/* Decision summary -- dynamic from payload */}
                    <div className={`console-decision-summary ${isHold ? "console-decision-summary--hold" : ""}`}>
                      <p className="console-decision-summary__headline">
                        {isHold
                          ? db.decisionSummaryHold[lang]
                          : (() => {
                              const act = result.proposal!.actions[0];
                              if (act?.player_name && act?.salary != null) {
                                return lang === "zh"
                                  ? `推荐签约：${act.player_name}，${formatSalary(act.salary, lang)}/年`
                                  : `Recommended signing: ${act.player_name}, ${formatSalary(act.salary, lang)}/yr`;
                              }
                              return db.decisionSummarySigning[lang];
                            })()}
                      </p>
                      <p className="console-decision-summary__body">
                        {isHold ? db.decisionSummaryHoldBody[lang] : db.decisionSummarySigningBody[lang]}
                      </p>
                    </div>

                    {/* Proposal detail card -- compact */}
                    <div className="console-proposal-card">
                      <div className="console-proposal-card__header">
                        <h2 className="console-proposal-card__title">
                          {lang === "zh" ? "签约方案详情" : "Signing Details"}
                        </h2>
                        <span className="console-proposal-card__badge">
                          {firstAction?.action_type ?? "SIGNING"}
                        </span>
                      </div>
                      <div className="console-proposal-card__body">
                        {/* Player row */}
                        <div className="console-player-row">
                          <div className="console-player-avatar">
                            {firstAction?.position?.charAt(0) ?? "C"}
                          </div>
                          <div className="console-player-info">
                            <span className="console-player-name">
                              {firstAction?.player_name ?? "\u2014"}
                            </span>
                            <span className="console-player-meta">
                              {firstAction?.position ?? "\u2014"} &middot;{" "}
                              {formatSalary(firstAction?.salary ?? null, lang)}/yr &middot;{" "}
                              {firstAction?.years ?? "\u2014"}yr
                            </span>
                          </div>
                        </div>
                        {/* 3x2 metric grid */}
                        <div className="console-metric-grid">
                          <div className="console-metric-cell">
                            <span className="console-metric-cell__label">fit_score</span>
                            <span className="console-metric-cell__value console-metric-cell__value--ok">
                              {firstAction?.fit_score?.toFixed(2) ?? "\u2014"}
                            </span>
                          </div>
                          <div className="console-metric-cell">
                            <span className="console-metric-cell__label">matched_need</span>
                            <span className="console-metric-cell__value">
                              {firstAction?.matched_need ?? "\u2014"}
                            </span>
                          </div>
                          <div className="console-metric-cell">
                            <span className="console-metric-cell__label">cap_impact</span>
                            <span className="console-metric-cell__value">{capImpactPercent}%</span>
                          </div>
                          <div className="console-metric-cell">
                            <span className="console-metric-cell__label">risk_level</span>
                            <span className="console-metric-cell__value console-metric-cell__value--ok">
                              {riskLevel}
                            </span>
                          </div>
                          <div className="console-metric-cell">
                            <span className="console-metric-cell__label">salary_rules</span>
                            <span className="console-metric-cell__value console-metric-cell__value--ok">
                              {firstAction?.validation_status ?? "\u2014"}
                            </span>
                          </div>
                          <div className="console-metric-cell">
                            <span className="console-metric-cell__label">evidence</span>
                            <span className="console-metric-cell__value">
                              {firstAction?.evidence_ids?.length ?? 0} src
                            </span>
                          </div>
                        </div>
                        {/* Collapsible audit details -- renders full ProposalViewer inside */}
                        <details className="console-audit-toggle">
                          <summary>
                            <ChevronDownIcon />
                            {lang === "zh" ? "查看完整审计详情" : "View full audit details"}
                          </summary>
                          <ProposalViewer payload={result.proposal} lang={lang} variant="console" />
                        </details>
                      </div>
                    </div>
                  </>
                ) : null
              ) : (
                /* Empty state -- centered in column 2 */
                <div className="console-empty">
                  <p>{db.emptyState[lang]}</p>
                </div>
              )}
            </div>

            {/* COLUMN 3: Pipeline + Indicators + Key metrics */}
            <div style={{ display: "flex", flexDirection: "column", gap: "12px", minWidth: 0 }}>
              {/* M8-D4: User-friendly data source card.
                  Engineering fields (snapshot_id, snapshot_type,
                  manual_review_required, etc.) are hidden by default
                  and only surface in a collapsed "technical details"
                  section below the plain-language summary. */}
              <div className={`console-datasource-card console-datasource-card--${healthState.kind}`}>
                <div className="console-datasource-card__header">
                  <span
                    className={`console-datasource-card__dot console-datasource-card__dot--${healthState.kind}`}
                  />
                  <span className="console-datasource-card__title">{ud.cardTitle[lang]}</span>
                </div>
                <div className="console-datasource-card__body">
                  {/* Headline: the data source name in plain language */}
                  <p className="console-datasource-card__headline">
                    {healthState.kind === "snapshot"
                      ? ud.snapshotTitle[lang]
                      : healthState.kind === "demo"
                        ? ud.demoTitle[lang]
                        : ud.offlineTitle[lang]}
                  </p>
                  {/* Description line */}
                  <p className="console-datasource-card__desc">
                    {healthState.kind === "snapshot"
                      ? ud.snapshotDescription[lang]
                      : healthState.kind === "demo"
                        ? ud.demoDescription[lang]
                        : ud.offlineDescription[lang]}
                  </p>

                  {/* Snapshot-specific rows: coverage + source + use case */}
                  {healthState.kind === "snapshot" && (
                    <>
                      <div className="console-datasource-card__row">
                        <span className="console-datasource-card__label">{ud.coverageLabel[lang]}</span>
                        <span className="console-datasource-card__value">{ud.snapshotCoverageGswPhx[lang]}</span>
                      </div>
                      <div className="console-datasource-card__row">
                        <span className="console-datasource-card__label">{ud.sourceLabel[lang]}</span>
                        <span className="console-datasource-card__value">{ud.snapshotSourcePublic[lang]}</span>
                      </div>
                      <div className="console-datasource-card__row">
                        <span className="console-datasource-card__label">{ud.useCaseLabel[lang]}</span>
                        <span className="console-datasource-card__value">{ud.snapshotUseCase[lang]}</span>
                      </div>
                    </>
                  )}

                  {/* Demo-specific rows: coverage + source + use case */}
                  {healthState.kind === "demo" && (
                    <>
                      <div className="console-datasource-card__row">
                        <span className="console-datasource-card__label">{ud.coverageLabel[lang]}</span>
                        <span className="console-datasource-card__value">{ud.demoCoverage[lang]}</span>
                      </div>
                      <div className="console-datasource-card__row">
                        <span className="console-datasource-card__label">{ud.sourceLabel[lang]}</span>
                        <span className="console-datasource-card__value">{ud.demoSource[lang]}</span>
                      </div>
                      <div className="console-datasource-card__row">
                        <span className="console-datasource-card__label">{ud.useCaseLabel[lang]}</span>
                        <span className="console-datasource-card__value">{ud.demoUseCase[lang]}</span>
                      </div>
                    </>
                  )}

                  {/* Status row (always shown) */}
                  <div className="console-datasource-card__row">
                    <span className="console-datasource-card__label">{ud.statusLabel[lang]}</span>
                    <span className="console-datasource-card__value">
                      {healthState.kind === "snapshot"
                        ? ud.snapshotStatus[lang]
                        : healthState.kind === "demo"
                          ? ud.demoStatus[lang]
                          : ud.offlineStatus[lang]}
                    </span>
                  </div>

                  {/* Note row (always shown, content varies by kind) */}
                  <p className="console-datasource-card__note">
                    {healthState.kind === "snapshot"
                      ? ud.snapshotNote[lang]
                      : healthState.kind === "demo"
                        ? ud.demoNote[lang]
                        : ud.offlineDescription[lang]}
                  </p>

                  {/* Snapshot-only: not-live disclaimer + sample explainer */}
                  {healthState.kind === "snapshot" && (
                    <p className="console-datasource-card__note console-datasource-card__note--soft">
                      {ud.snapshotNotLive[lang]}
                    </p>
                  )}
                  {healthState.kind === "snapshot" && (
                    <p className="console-datasource-card__note console-datasource-card__note--soft">
                      {ud.snapshotSampleExplainer[lang]}
                    </p>
                  )}
                </div>

                {/* Collapsible technical details (developer-facing, hidden by default).
                    Engineering fields go here, NOT in the main card body. */}
                <details className="console-datasource-card__tech">
                  <summary>
                    <ChevronDownIcon />
                    {ud.techDetailsToggle[lang]}
                  </summary>
                  <div className="console-datasource-card__tech-body">
                    <p className="console-datasource-card__tech-hint">{ud.techDetailsHint[lang]}</p>
                    <div className="console-datasource-card__tech-row">
                      <span className="console-datasource-card__tech-label">{ud.techFieldDataMode[lang]}</span>
                      <span className="console-datasource-card__tech-value">
                        {healthState.dataMode ?? ud.techFieldEmpty[lang]}
                      </span>
                    </div>
                    <div className="console-datasource-card__tech-row">
                      <span className="console-datasource-card__tech-label">{ud.techFieldSnapshotId[lang]}</span>
                      <span className="console-datasource-card__tech-value">
                        {healthState.snapshotId ?? ud.techFieldEmpty[lang]}
                      </span>
                    </div>
                    <div className="console-datasource-card__tech-row">
                      <span className="console-datasource-card__tech-label">{ud.techFieldSnapshotType[lang]}</span>
                      <span className="console-datasource-card__tech-value">
                        {healthState.snapshotType ?? ud.techFieldEmpty[lang]}
                      </span>
                    </div>
                    <div className="console-datasource-card__tech-row">
                      <span className="console-datasource-card__tech-label">{ud.techFieldSampleData[lang]}</span>
                      <span className="console-datasource-card__tech-value">
                        {String(healthState.sample)}
                      </span>
                    </div>
                    <div className="console-datasource-card__tech-row">
                      <span className="console-datasource-card__tech-label">{ud.techFieldSnapshotValid[lang]}</span>
                      <span className="console-datasource-card__tech-value">
                        {healthState.snapshotValid === null
                          ? ud.techFieldEmpty[lang]
                          : String(healthState.snapshotValid)}
                      </span>
                    </div>
                    <div className="console-datasource-card__tech-row">
                      <span className="console-datasource-card__tech-label">{ud.techFieldStrictSnapshot[lang]}</span>
                      <span className="console-datasource-card__tech-value">
                        {String(healthState.strictSnapshot ?? false)}
                      </span>
                    </div>
                    <div className="console-datasource-card__tech-row">
                      <span className="console-datasource-card__tech-label">{ud.techFieldWarningsCount[lang]}</span>
                      <span className="console-datasource-card__tech-value">
                        {healthState.snapshotWarnings?.length ?? 0}
                      </span>
                    </div>
                    <div className="console-datasource-card__tech-row">
                      <span className="console-datasource-card__tech-label">{ud.techFieldActiveDataSource[lang]}</span>
                      <span className="console-datasource-card__tech-value">
                        {healthState.activeDataSource ?? ud.techFieldEmpty[lang]}
                      </span>
                    </div>
                    <div className="console-datasource-card__tech-row">
                      <span className="console-datasource-card__tech-label">{ud.techFieldFallbackReason[lang]}</span>
                      <span className="console-datasource-card__tech-value">
                        {healthState.fallbackReason ?? ud.techFieldEmpty[lang]}
                      </span>
                    </div>
                    <div className="console-datasource-card__tech-row">
                      <span className="console-datasource-card__tech-label">API</span>
                      <span className="console-datasource-card__tech-value">{API_BASE_URL}</span>
                    </div>
                  </div>
                </details>
              </div>

              {/* Pipeline */}
              <div className="console-pipeline-card">
                <p className="console-pipeline-card__title">{cs.inspectorPipeline[lang]}</p>
                <div className="console-pipeline-card__list">
                  {steps.map((step, i) => (
                    <div
                      key={i}
                      className={`console-pipeline-step ${i < completedSteps ? "console-pipeline-step--done" : ""}`}
                    >
                      {i < completedSteps ? <CheckIcon /> : <CircleIcon />}
                      <span className="console-pipeline-step__label">{step[lang]}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Indicators -- only when complete */}
              {runState === "complete" && result && (
                <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  {indicatorRows.map((row, i) => (
                    <div
                      key={i}
                      className={`console-indicator-row ${row.ok ? "console-indicator-row--ok" : "console-indicator-row--warn"}`}
                    >
                      <span className="console-indicator-row__label">{row.label[lang]}</span>
                      <span
                        className={`console-indicator-row__value ${row.ok ? "console-indicator-row__value--ok" : "console-indicator-row__value--warn"}`}
                      >
                        {row.value[lang]}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Key metrics -- only when complete and signing/hold mode */}
              {runState === "complete" && result?.proposal && (
                <div className="console-key-metrics">
                  <p className="console-key-metrics__title">{cs.inspectorKeyMetrics[lang]}</p>
                  <div className="console-key-metrics__body">
                    {/* Fit score large */}
                    <div className="console-fit-score">
                      <span className="console-fit-score__label">fit_score</span>
                      <span className="console-fit-score__value">{fitScoreDisplay}</span>
                    </div>
                    {/* Cap impact bar */}
                    <div className="console-cap-bar">
                      <div className="console-cap-bar__header">
                        <span className="console-cap-bar__label">cap_impact</span>
                        <span className="console-cap-bar__value">{capImpactPercent}%</span>
                      </div>
                      <div className="console-cap-bar__track">
                        <div
                          className="console-cap-bar__fill"
                          style={{ width: `${Math.min(capImpactPercent, 100)}%` }}
                        />
                      </div>
                    </div>
                    {/* Risk badge */}
                    <div className="console-risk-badge">
                      <span
                        className="console-risk-badge__label"
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 9,
                          fontWeight: 600,
                          textTransform: "uppercase",
                          color: "var(--muted-foreground)",
                        }}
                      >
                        risk_level
                      </span>
                      <span
                        className={`console-risk-badge__pill console-risk-badge__pill--${riskLevel.toLowerCase()}`}
                      >
                        {riskLevel}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Trade-specific key metrics */}
              {runState === "complete" && result?.trade && (
                <div className="console-key-metrics">
                  <p className="console-key-metrics__title">{cs.inspectorKeyMetrics[lang]}</p>
                  <div className="console-key-metrics__body">
                    <div className="console-indicator-row console-indicator-row--ok">
                      <span className="console-indicator-row__label">validation</span>
                      <span className="console-indicator-row__value console-indicator-row__value--ok">PASS</span>
                    </div>
                    <div className="console-indicator-row console-indicator-row--ok">
                      <span className="console-indicator-row__label">salary_match</span>
                      <span className="console-indicator-row__value console-indicator-row__value--ok">PASS</span>
                    </div>
                    <div className="console-indicator-row console-indicator-row--warn">
                      <span className="console-indicator-row__label">human_approval</span>
                      <span className="console-indicator-row__value console-indicator-row__value--warn">
                        {lang === "zh" ? "需要" : "Required"}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {/* Data disclaimer (M8-D4: content adapts to data source kind) */}
              <div style={{ fontSize: 10, color: "var(--muted-foreground)", lineHeight: 1.4, padding: "4px 0" }}>
                {healthState.kind === "snapshot"
                  ? ud.snapshotNotLive[lang]
                  : lang === "zh"
                    ? "这些球队、球员、薪资和交易结果是 sample/demo 数据，不代表真实 NBA 数据。"
                    : "All data is sample/demo, not real NBA data."}
              </div>
            </div>
          </div>
          {/* end console-grid */}

          {/* Footer */}
          <footer style={{ padding: "6px 0 0", borderTop: "1px solid var(--border)", flexShrink: 0 }}>
            <p
              style={{
                margin: 0,
                fontFamily: "var(--font-serif)",
                fontSize: 10,
                lineHeight: 1.3,
                color: "var(--muted-foreground)",
                textAlign: "center",
              }}
            >
              FrontOffice Agent 仅供研究与教育用途。所有数据为样例数据。
            </p>
          </footer>
        </div>
      </main>
    </div>
  );
}
