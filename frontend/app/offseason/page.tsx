"use client";

/**
 * Offseason Agent Console page — M7-B API-first three-mode console.
 *
 * Three scenario modes:
 *   1. "signing"  — $20M budget, default recommendation (SIGNING)
 *   2. "hold"     — $15M budget, strict-budget fallback (HOLD)
 *   3. "trade"    — two-team trade preview (PASS, post-trade depth chart)
 *
 * API-first behavior (M7-B):
 *   - Clicking "generate" calls the local FastAPI backend (M7-A).
 *   - signing/hold -> POST /api/offseason/proposal-preview
 *   - trade        -> GET  /api/offseason/trade-preview-demo
 *   - On any API failure (network, timeout, non-2xx, invalid JSON),
 *     the page falls back to the existing static sample payloads and
 *     shows a clear "backend unavailable" banner.
 *   - The page never crashes on API failure.
 *
 * Guardrails (unchanged from M6-D):
 *   - sample / simulation data only
 *   - no real NBA API, no LLM, no MCP
 *   - preview only — never approves or executes a transaction
 *   - no data writes
 *   - requires_human_approval is always true
 *
 * Default language is Chinese; a toggle in the top-right switches UI
 * copy to English.
 *
 * Milestone: M7-B (Frontend API Integration).
 */

import { useCallback, useEffect, useState } from "react";
import ProposalViewer from "../../components/ProposalViewer";
import TradePreviewViewer from "../../components/TradePreviewViewer";
import { scenarios } from "../../data/demoProposalPayload";
import { demoTradePayload } from "../../data/demoTradePreviewPayload";
import { copy, type Lang } from "../../data/i18n";
import {
  ApiError,
  DEMO_PROPOSAL_REQUESTS,
  fetchProposalPreview,
  fetchTradePreviewDemo,
  type ProposalPreviewParams,
} from "../../lib/apiClient";
import type { DemoPayload } from "../../data/demoProposalPayload";
import type { DemoTradePayload } from "../../data/demoTradePreviewPayload";

type Mode = "signing" | "hold" | "trade";
type RunState = "idle" | "running" | "complete";
/** Where the currently-displayed payload came from. */
type DataSource = "api" | "fallback";

interface RunResult {
  mode: Mode;
  source: DataSource;
  /** Present when source === "fallback" to explain why API failed. */
  fallbackReason?: string;
  /** Proposal payload (signing/hold modes). */
  proposal: DemoPayload | null;
  /** Trade payload (trade mode). */
  trade: DemoTradePayload | null;
}

function modeToScenarioId(mode: Mode): string {
  return mode === "signing" ? "default" : "strict-budget";
}

/**
 * Look up the static fallback payload for a mode. Used when the API
 * call fails. The static payloads are never deleted — they are the
 * safety net that keeps the page working offline.
 */
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

/** Human-readable reason for an ApiError, localized. */
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

export default function OffseasonPage() {
  const [lang, setLang] = useState<Lang>("zh");
  const [mode, setMode] = useState<Mode>("signing");
  const [runState, setRunState] = useState<RunState>("idle");
  const [result, setResult] = useState<RunResult | null>(null);

  /**
   * Generate handler: API-first with static fallback.
   *
   * Flow:
   *   1. Enter "running" state.
   *   2. Call the appropriate API endpoint for the current mode.
   *   3a. On success: store the API payload with source="api".
   *   3b. On any failure: store the static fallback payload with
   *       source="fallback" and a human-readable reason. The page
   *       never crashes.
   *   4. Enter "complete" state.
   */
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
    } catch (err) {
      // Fallback path: API failed for any reason. Use the static
      // payload so the page keeps working. Never rethrow.
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
    }

    setResult(apiResult);
    setRunState("complete");
  }, [runState, mode, lang]);

  // Reset to idle when the user changes the mode so they re-generate.
  // This prevents showing a stale result from a different mode.
  useEffect(() => {
    if (result !== null && result.mode !== mode) {
      setRunState("idle");
      setResult(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const c = copy.console;
  const cm = copy.consoleModes;
  const ds = copy.dataSource;
  const isHold = result?.mode !== "trade" && result?.proposal?.proposal.status === "NO_ACTION";

  // Progress steps differ slightly for trade mode.
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

  return (
    <main className="page" lang={lang}>
      {/* Language switcher */}
      <div className="page-header-row">
        <div
          className="lang-switch"
          role="group"
          aria-label={copy.langSwitch.ariaLabel[lang]}
        >
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
      </div>

      {/* Hero */}
      <header className="hero">
        <p className="hero-eyebrow">{copy.hero.eyebrow[lang]}</p>
        <h1 className="hero-title">{copy.hero.title[lang]}</h1>
        <p className="hero-lede">{copy.hero.lede[lang]}</p>
        <div className="hero-badges">
          <span className="badge badge--warn">{copy.hero.badges.sample[lang]}</span>
          <span className="badge badge--info">{copy.hero.badges.preview[lang]}</span>
          <span className="badge badge--bad">{copy.hero.badges.approval[lang]}</span>
          <span className="badge">{copy.hero.badges.noPrediction[lang]}</span>
          <span className="badge">{copy.hero.badges.noExecution[lang]}</span>
          <span className="badge badge--accent">{copy.hero.badges.noExternal[lang]}</span>
        </div>
      </header>

      {/* Approval boundary banner */}
      <div className="approval-banner">
        <strong>{copy.approvalBanner.strong[lang]}</strong>{" "}
        {copy.approvalBanner.body[lang]}
      </div>

      {/* Agent input panel */}
      <section className="console-panel" aria-label={c.inputTitle[lang]}>
        <h2 className="console-panel__title">{c.inputTitle[lang]}</h2>
        <p className="console-panel__hint">{c.inputHint[lang]}</p>

        <div className="console-fields">
          <div>
            <p className="console-field__label">{c.fieldTeam[lang]}</p>
            <p className="console-field__value">{c.teamDemAtl[lang]}</p>
          </div>
          <div>
            <p className="console-field__label">{c.fieldObjective[lang]}</p>
            <p className="console-field__value">{c.objectiveValue[lang]}</p>
          </div>
          <div>
            <p className="console-field__label">{c.fieldPosition[lang]}</p>
            <p className="console-field__value">{c.positionValue[lang]}</p>
          </div>
          <div>
            <p className="console-field__label">{c.fieldCandidates[lang]}</p>
            <p className="console-field__value">{c.candidatesValue[lang]}</p>
          </div>
          <div>
            <p className="console-field__label">{c.fieldEvidenceQuery[lang]}</p>
            <p className="console-field__value">{c.evidenceQueryValue[lang]}</p>
          </div>
        </div>

        {/* Mode radio cards (three modes) */}
        <p className="console-field__label" style={{ marginBottom: 6 }}>
          {lang === "zh" ? "场景模式" : "Scenario mode"}
        </p>
        <div className="mode-cards" role="radiogroup" aria-label={lang === "zh" ? "场景模式" : "Scenario mode"}>
          <label
            className={`mode-card ${mode === "signing" ? "mode-card--selected" : ""}`}
          >
            <input
              type="radio"
              name="mode"
              value="signing"
              checked={mode === "signing"}
              onChange={() => setMode("signing")}
            />
            <p className="mode-card__label">{cm.signing.label[lang]}</p>
            <p className="mode-card__desc">{cm.signing.desc[lang]}</p>
          </label>
          <label
            className={`mode-card ${mode === "hold" ? "mode-card--selected" : ""}`}
          >
            <input
              type="radio"
              name="mode"
              value="hold"
              checked={mode === "hold"}
              onChange={() => setMode("hold")}
            />
            <p className="mode-card__label">{cm.hold.label[lang]}</p>
            <p className="mode-card__desc">{cm.hold.desc[lang]}</p>
          </label>
          <label
            className={`mode-card ${mode === "trade" ? "mode-card--selected" : ""}`}
          >
            <input
              type="radio"
              name="mode"
              value="trade"
              checked={mode === "trade"}
              onChange={() => setMode("trade")}
            />
            <p className="mode-card__label">{cm.trade.label[lang]}</p>
            <p className="mode-card__desc">{cm.trade.desc[lang]}</p>
          </label>
        </div>

        {/* Generate button + run state */}
        <div>
          <button
            type="button"
            className="generate-btn"
            onClick={handleGenerate}
            disabled={runState === "running"}
          >
            {runState === "complete"
              ? c.regenerateBtn[lang]
              : c.generateBtn[lang]}
          </button>
          <span
            className={`console-state console-state--${runState}`}
            aria-live="polite"
          >
            <span className="console-state__dot" aria-hidden="true" />
            <span>
              {c.stateLabel[lang]}:{" "}
              {runState === "idle"
                ? c.stateIdle[lang]
                : runState === "running"
                  ? ds.loadingApi[lang]
                  : c.stateComplete[lang]}
            </span>
          </span>
        </div>
      </section>

      {/* Progress timeline (only visible after first generate) */}
      {runState !== "idle" && (
        <section className="section" aria-label={c.progressTitle[lang]}>
          <h2 className="section__title">{c.progressTitle[lang]}</h2>
          <p className="section__hint">{c.progressHint[lang]}</p>
          <ol className="progress-timeline">
            {steps.map((step, i) => {
              const stepState =
                runState === "complete"
                  ? "done"
                  : runState === "running"
                    ? i < steps.length - 1
                      ? "done"
                      : "running"
                    : "";
              return (
                <li
                  key={i}
                  className={`progress-step ${stepState ? `progress-step--${stepState}` : ""}`}
                >
                  {step[lang]}
                </li>
              );
            })}
          </ol>
        </section>
      )}

      {/* Data source indicator (only after a run completes) */}
      {runState === "complete" && result && (
        <div
          className={`data-source-badge data-source-badge--${result.source}`}
          role="status"
        >
          {result.source === "api" ? ds.apiLabel[lang] : ds.fallbackLabel[lang]}
        </div>
      )}

      {/* Fallback banner (only when API failed and we fell back) */}
      {runState === "complete" && result?.source === "fallback" && (
        <div className="fallback-banner" role="alert">
          <strong>{ds.fallbackBanner[lang]}</strong>
          {result.fallbackReason && (
            <p className="fallback-banner__reason">
              {ds.fallbackReason[lang]}
              {result.fallbackReason}
            </p>
          )}
        </div>
      )}

      {/* Output region */}
      {runState === "complete" && result?.mode === "trade" && result.trade ? (
        <section className="output-region" aria-label={copy.trade.outputHeadline[lang]}>
          <h2 className="section__title">{copy.console.outputTitle[lang]}</h2>
          <p className="output-headline">{copy.trade.outputHeadline[lang]}</p>
          <TradePreviewViewer payload={result.trade} lang={lang} />
        </section>
      ) : runState === "complete" && result?.proposal ? (
        <section className="output-region" aria-label={c.outputTitle[lang]}>
          <h2 className="section__title">{c.outputTitle[lang]}</h2>
          <p
            className={`output-headline ${isHold ? "output-headline--hold" : ""}`}
          >
            {isHold ? c.outputStrict[lang] : c.outputDefault[lang]}
          </p>
          <ProposalViewer
            payload={result.proposal}
            lang={lang}
            variant="console"
          />
        </section>
      ) : (
        <section className="output-region">
          <p className="console-empty">
            {lang === "zh"
              ? "选择场景模式后点击「生成休赛期方案」查看系统建议。"
              : "Pick a scenario mode and click \"Generate offseason plan\" to see the system recommendation."}
          </p>
        </section>
      )}

      {/* Footer */}
      <footer className="footer">
        <p>{copy.footer.body[lang]}</p>
        <p>
          {copy.footer.payloadSource[lang]}
          <code>
            python backend/scripts/run_offseason_demo.py --format json
          </code>
          {"  ·  "}
          <code>
            python backend/scripts/run_trade_preview_demo.py --format json
          </code>
          {"  ·  "}
          <code>
            uvicorn backend.app.api:app --reload
          </code>
        </p>
      </footer>
    </main>
  );
}
