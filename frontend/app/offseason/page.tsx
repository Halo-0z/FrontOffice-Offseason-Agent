"use client";

/**
 * Offseason Agent Console page — M6-C console patch.
 *
 * Reframes /offseason from a static report into an interactive Agent
 * Console: the user picks a budget ($20M or $15M), clicks "generate",
 * a short setTimeout simulates an agent run, a progress timeline marks
 * all steps complete, and the corresponding static sample payload is
 * shown in the output region. Audit details are collapsed below.
 *
 * Static interaction only:
 *   - no fetch, no API call, no network
 *   - switches between two existing payloads in demoProposalPayload.ts
 *   - does not modify payload content
 *
 * Default language is Chinese; a toggle in the top-right switches UI
 * copy to English.
 *
 * Milestone: M6-C (Agent Console interaction patch).
 */

import { useEffect, useState } from "react";
import ProposalViewer from "../../components/ProposalViewer";
import { scenarios } from "../../data/demoProposalPayload";
import { copy, type Lang } from "../../data/i18n";

type BudgetChoice = "20M" | "15M";
type RunState = "idle" | "running" | "complete";

function budgetToScenarioId(budget: BudgetChoice): string {
  return budget === "20M" ? "default" : "strict-budget";
}

export default function OffseasonPage() {
  const [lang, setLang] = useState<Lang>("zh");
  const [budget, setBudget] = useState<BudgetChoice>("20M");
  const [runState, setRunState] = useState<RunState>("idle");
  const [completedBudget, setCompletedBudget] = useState<BudgetChoice | null>(
    null,
  );

  // The payload shown in the output region only appears after the user
  // clicks generate and the simulated run completes.
  const completedScenarioId =
    completedBudget !== null ? budgetToScenarioId(completedBudget) : null;
  const completedScenario =
    scenarios.find((s) => s.id === completedScenarioId) ?? null;

  function handleGenerate() {
    if (runState === "running") return;
    setRunState("running");
    // Simulate a short agent run. No real async work, no API call.
    window.setTimeout(() => {
      setCompletedBudget(budget);
      setRunState("complete");
    }, 450);
  }

  // Reset to idle when the user changes the budget so they re-generate.
  useEffect(() => {
    if (completedBudget !== null && completedBudget !== budget) {
      setRunState("idle");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [budget]);

  const c = copy.console;
  const isStrict = completedScenario?.id === "strict-budget";

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

        {/* Budget radio cards (replaces scenario tabs) */}
        <p className="console-field__label" style={{ marginBottom: 6 }}>
          {c.fieldBudget[lang]}
        </p>
        <div className="budget-cards" role="radiogroup" aria-label={c.fieldBudget[lang]}>
          <label
            className={`budget-card ${budget === "20M" ? "budget-card--selected" : ""}`}
          >
            <input
              type="radio"
              name="budget"
              value="20M"
              checked={budget === "20M"}
              onChange={() => setBudget("20M")}
            />
            <p className="budget-card__amount">$20M</p>
            <p className="budget-card__desc">{c.budgetOption20[lang]}</p>
          </label>
          <label
            className={`budget-card ${budget === "15M" ? "budget-card--selected" : ""}`}
          >
            <input
              type="radio"
              name="budget"
              value="15M"
              checked={budget === "15M"}
              onChange={() => setBudget("15M")}
            />
            <p className="budget-card__amount">$15M</p>
            <p className="budget-card__desc">{c.budgetOption15[lang]}</p>
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
            {c.steps.map((step, i) => {
              const stepState =
                runState === "complete"
                  ? "done"
                  : runState === "running"
                    ? i < c.steps.length - 1
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
      {runState === "complete" && completedScenario ? (
        <section className="output-region" aria-label={c.outputTitle[lang]}>
          <h2 className="section__title">{c.outputTitle[lang]}</h2>
          <p
            className={`output-headline ${isStrict ? "output-headline--hold" : ""}`}
          >
            {isStrict ? c.outputStrict[lang] : c.outputDefault[lang]}
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
              ? "选择预算后点击「生成休赛期方案」查看系统建议。"
              : "Pick a budget and click \"Generate offseason plan\" to see the system recommendation."}
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
        </p>
      </footer>
    </main>
  );
}
