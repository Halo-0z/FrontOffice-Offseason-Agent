"use client";

/**
 * Offseason Agent Console page — M6-D three-mode console.
 *
 * Three scenario modes:
 *   1. "signing"  — $20M budget, default recommendation (SIGNING)
 *   2. "hold"     — $15M budget, strict-budget fallback (HOLD)
 *   3. "trade"    — two-team trade preview (PASS, post-trade depth chart)
 *
 * The user picks a mode, clicks "generate", a short setTimeout simulates
 * an agent run, a progress timeline marks all steps complete, and the
 * corresponding static sample payload is shown in the output region.
 * Audit details are collapsed below.
 *
 * Static interaction only:
 *   - no fetch, no API call, no network
 *   - switches between three existing static payloads
 *   - does not modify payload content
 *
 * Default language is Chinese; a toggle in the top-right switches UI
 * copy to English.
 *
 * Milestone: M6-D (Static Trade Preview Scenario).
 */

import { useEffect, useState } from "react";
import ProposalViewer from "../../components/ProposalViewer";
import TradePreviewViewer from "../../components/TradePreviewViewer";
import { scenarios } from "../../data/demoProposalPayload";
import { demoTradePayload } from "../../data/demoTradePreviewPayload";
import { copy, type Lang } from "../../data/i18n";

type Mode = "signing" | "hold" | "trade";
type RunState = "idle" | "running" | "complete";

function modeToScenarioId(mode: Mode): string {
  return mode === "signing" ? "default" : "strict-budget";
}

export default function OffseasonPage() {
  const [lang, setLang] = useState<Lang>("zh");
  const [mode, setMode] = useState<Mode>("signing");
  const [runState, setRunState] = useState<RunState>("idle");
  const [completedMode, setCompletedMode] = useState<Mode | null>(null);

  // The payload shown in the output region only appears after the user
  // clicks generate and the simulated run completes.
  const completedScenarioId =
    completedMode !== null && completedMode !== "trade"
      ? modeToScenarioId(completedMode)
      : null;
  const completedScenario =
    scenarios.find((s) => s.id === completedScenarioId) ?? null;
  const completedTrade =
    completedMode === "trade" ? demoTradePayload : null;

  function handleGenerate() {
    if (runState === "running") return;
    setRunState("running");
    // Simulate a short agent run. No real async work, no API call.
    window.setTimeout(() => {
      setCompletedMode(mode);
      setRunState("complete");
    }, 450);
  }

  // Reset to idle when the user changes the mode so they re-generate.
  useEffect(() => {
    if (completedMode !== null && completedMode !== mode) {
      setRunState("idle");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const c = copy.console;
  const cm = copy.consoleModes;
  const isHold = completedScenario?.id === "strict-budget";

  // Progress steps differ slightly for trade mode.
  const steps =
    completedMode === "trade"
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
                  ? c.stateRunning[lang]
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

      {/* Output region */}
      {runState === "complete" && completedMode === "trade" && completedTrade ? (
        <section className="output-region" aria-label={copy.trade.outputHeadline[lang]}>
          <h2 className="section__title">{copy.console.outputTitle[lang]}</h2>
          <p className="output-headline">{copy.trade.outputHeadline[lang]}</p>
          <TradePreviewViewer payload={completedTrade} lang={lang} />
        </section>
      ) : runState === "complete" && completedScenario ? (
        <section className="output-region" aria-label={c.outputTitle[lang]}>
          <h2 className="section__title">{c.outputTitle[lang]}</h2>
          <p
            className={`output-headline ${isHold ? "output-headline--hold" : ""}`}
          >
            {isHold ? c.outputStrict[lang] : c.outputDefault[lang]}
          </p>
          <ProposalViewer
            payload={completedScenario.payload}
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
        </p>
      </footer>
    </main>
  );
}
