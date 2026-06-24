"use client";

/**
 * Root page (/) — M6-C bilingual (Chinese-first).
 *
 * Minimal entry point that links to the static offseason viewer at
 * /offseason. Default language is Chinese; a toggle in the top-right
 * switches UI copy to English. No API calls, no data fetching, no
 * styling frameworks.
 *
 * Milestone: M6-C (Chinese-first / bilingual patch).
 */

import { useState } from "react";
import Link from "next/link";
import { copy, type Lang } from "../data/i18n";

export default function HomePage() {
  const [lang, setLang] = useState<Lang>("zh");

  return (
    <main className="home-page" lang={lang}>
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

      <h1 className="home-title">{copy.root.title[lang]}</h1>
      <p className="home-subtitle">{copy.root.subtitle[lang]}</p>
      <p className="home-description">{copy.root.description[lang]}</p>

      <p style={{ margin: "var(--space-md) 0 0" }}>
        <Link href="/offseason" className="home-cta">
          {copy.root.cta[lang]}
        </Link>
      </p>

      <p className="home-footer">{copy.root.footer[lang]}</p>
    </main>
  );
}
