"use client";

/**
 * RealSnapshotTeamSelector (M10-D2)
 *
 * Additive, read-only explorer for real snapshot team metadata.
 * Calls GET /api/snapshots/metadata?snapshot_mode=real_snapshot via
 * getRealSnapshotMetadata() and renders:
 *   - idle/loading/ready/error states
 *   - a searchable team list with non-official UI accent abbreviation badges
 *   - a selected-team detail card with safety disclaimers
 *
 * Boundaries (enforced here AND by backend tests):
 *   - read-only: no mutation calls, no POST/PUT/DELETE
 *   - selection is LOCAL UI STATE only — it is NOT propagated to signing/
 *     trade/hold/natural-language-preview
 *   - error state is terminal; we NEVER fall back to demo data and relabel
 *     it as real
 *   - badges use accent_color / secondary_accent_color only as UI accents;
 *     no logo images, and no restricted-copy strings are used anywhere
 *   - neutral fallback (#6B7280 gray) if a color is missing or malformed
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  getRealSnapshotMetadata,
  type RealSnapshotMetadataResponse,
  type RealSnapshotTeamMetadata,
} from "../lib/apiClient";
import { copy, type Lang } from "../data/i18n";

type LoadState = "idle" | "loading" | "ready" | "error";

const HEX_COLOR_RE = /^#[0-9A-Fa-f]{6}$/;
const NEUTRAL_ACCENT = "#6B7280";
const NEUTRAL_SECONDARY = "#9CA3AF";

function safeHexColor(value: unknown, fallback: string): string {
  if (typeof value === "string" && HEX_COLOR_RE.test(value)) return value;
  return fallback;
}

function pickReadableTextColor(bg: string): string {
  const hex = bg.replace("#", "");
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6 ? "#111827" : "#FFFFFF";
}

interface AbbreviationBadgeProps {
  abbr: string;
  accent: string;
  secondary: string;
}

function AbbreviationBadge({ abbr, accent, secondary }: AbbreviationBadgeProps) {
  const bg = safeHexColor(accent, NEUTRAL_ACCENT);
  const border = safeHexColor(secondary, NEUTRAL_SECONDARY);
  const fg = pickReadableTextColor(bg);
  return (
    <span
      className="rs-abbreviation-badge"
      style={{ background: bg, color: fg, borderColor: border }}
      aria-label={`abbreviation ${abbr}`}
    >
      {abbr}
    </span>
  );
}

export interface RealSnapshotTeamSelectorProps {
  lang: Lang;
}

export default function RealSnapshotTeamSelector({ lang }: RealSnapshotTeamSelectorProps) {
  const t = copy.realSnapshot;
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [data, setData] = useState<RealSnapshotMetadataResponse | null>(null);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const [query, setQuery] = useState<string>("");

  const load = useCallback(async () => {
    setLoadState("loading");
    setErrorMessage(null);
    try {
      const resp = await getRealSnapshotMetadata();
      setData(resp);
      setLoadState("ready");
      if (!selectedTeamId && resp.teams.length > 0) {
        setSelectedTeamId(resp.teams[0].team_id);
      }
    } catch (err) {
      setData(null);
      setLoadState("error");
      setErrorMessage(
        err instanceof ApiError
          ? `${err.kind}: ${err.message}${err.status ? ` (HTTP ${err.status})` : ""}`
          : err instanceof Error
            ? err.message
            : String(err),
      );
    }
  }, [selectedTeamId]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredTeams: RealSnapshotTeamMetadata[] = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    const teams = [...data.teams].sort((a, b) =>
      a.abbreviation.localeCompare(b.abbreviation),
    );
    if (!q) return teams;
    return teams.filter((team) => {
      const hay = `${team.city} ${team.name} ${team.abbreviation} ${team.conference} ${team.division}`.toLowerCase();
      return hay.includes(q);
    });
  }, [data, query]);

  const selectedTeam: RealSnapshotTeamMetadata | null = useMemo(() => {
    if (!data || !selectedTeamId) return null;
    return data.teams.find((t) => t.team_id === selectedTeamId) ?? null;
  }, [data, selectedTeamId]);

  const freshnessText = useMemo(() => {
    if (!data) return "";
    return t.freshness[lang].replace("{date}", data.as_of_date);
  }, [data, lang, t.freshness]);

  const teamCountText = useMemo(() => {
    const n = filteredTeams.length;
    return t.teamCount[lang].replace("{n}", String(n));
  }, [filteredTeams.length, lang, t.teamCount]);

  return (
    <div className="console-real-snapshot-card">
      <div className="console-real-snapshot-card__header">
        <div>
          <p className="console-real-snapshot-card__eyebrow">{t.panelEyebrow[lang]}</p>
          <p className="console-real-snapshot-card__title">{t.panelTitle[lang]}</p>
        </div>
        <span className="console-real-snapshot-card__badge">
          {data ? t.notLive[lang] : "…"}
        </span>
      </div>

      <p className="console-real-snapshot-card__note">{t.readOnlyNote[lang]}</p>
      <p className="console-real-snapshot-card__note">{t.safetyNote[lang]}</p>

      {loadState === "loading" && (
        <p className="console-real-snapshot-card__status">{t.stateLoading[lang]}</p>
      )}

      {loadState === "error" && (
        <div className="console-real-snapshot-card__error" role="alert">
          <p className="console-real-snapshot-card__error-title">{t.stateError[lang]}</p>
          {errorMessage && (
            <p className="console-real-snapshot-card__error-detail">{errorMessage}</p>
          )}
          <p className="console-real-snapshot-card__note">{t.errorHint[lang]}</p>
          <button type="button" className="console-real-snapshot-card__retry" onClick={load}>
            {t.retry[lang]}
          </button>
        </div>
      )}

      {loadState === "ready" && data && (
        <>
          <div className="console-real-snapshot-card__meta">
            <span className="console-real-snapshot-card__meta-item">{freshnessText}</span>
            <span className="console-real-snapshot-card__meta-item">
              {t.fieldFreshness[lang]}: {data.freshness_label}
            </span>
            {data.manual_review_required && (
              <span className="console-real-snapshot-card__meta-item console-real-snapshot-card__meta-item--warn">
                {t.manualReview[lang]}
              </span>
            )}
            {data.no_official_branding && (
              <span className="console-real-snapshot-card__meta-item">
                {t.noOfficialBranding[lang]}
              </span>
            )}
          </div>

          <p className="console-real-snapshot-card__warning">{t.warning[lang]}</p>

          <input
            type="text"
            className="console-real-snapshot-card__search"
            placeholder={t.searchPlaceholder[lang]}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label={t.searchPlaceholder[lang]}
          />
          <p className="console-real-snapshot-card__count">{teamCountText}</p>

          <div className="console-real-snapshot-card__list" role="listbox" aria-label={t.panelTitle[lang]}>
            {filteredTeams.map((team) => {
              const vm = team.visual_metadata;
              const isSelected = selectedTeamId === team.team_id;
              return (
                <button
                  key={team.team_id}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  className={`console-real-snapshot-card__team ${isSelected ? "console-real-snapshot-card__team--selected" : ""}`}
                  onClick={() => setSelectedTeamId(team.team_id)}
                >
                  <AbbreviationBadge
                    abbr={team.abbreviation}
                    accent={vm?.accent_color}
                    secondary={vm?.secondary_accent_color}
                  />
                  <span className="console-real-snapshot-card__team-name">
                    {team.city} {team.name}
                  </span>
                  <span className="console-real-snapshot-card__team-conf">
                    {team.conference === "East" ? t.conferenceEast[lang] : t.conferenceWest[lang]}
                  </span>
                </button>
              );
            })}
            {filteredTeams.length === 0 && (
              <p className="console-real-snapshot-card__empty">—</p>
            )}
          </div>

          <div className="console-real-snapshot-card__detail">
            <p className="console-real-snapshot-card__detail-title">{t.selectedTitle[lang]}</p>
            {selectedTeam ? (
              <div className="console-real-snapshot-card__detail-body">
                <div className="console-real-snapshot-card__detail-head">
                  <AbbreviationBadge
                    abbr={selectedTeam.abbreviation}
                    accent={selectedTeam.visual_metadata?.accent_color}
                    secondary={selectedTeam.visual_metadata?.secondary_accent_color}
                  />
                  <span className="console-real-snapshot-card__detail-name">
                    {selectedTeam.city} {selectedTeam.name}
                  </span>
                </div>
                <div className="console-real-snapshot-card__detail-grid">
                  <span className="console-real-snapshot-card__detail-label">{t.fieldAbbr[lang]}</span>
                  <span>{selectedTeam.abbreviation}</span>
                  <span className="console-real-snapshot-card__detail-label">{t.fieldConference[lang]}</span>
                  <span>{selectedTeam.conference === "East" ? t.conferenceEast[lang] : t.conferenceWest[lang]}</span>
                  <span className="console-real-snapshot-card__detail-label">{t.fieldDivision[lang]}</span>
                  <span>{selectedTeam.division}</span>
                  <span className="console-real-snapshot-card__detail-label">{t.fieldMode[lang]}</span>
                  <span>{data.snapshot_mode}</span>
                  <span className="console-real-snapshot-card__detail-label">{t.fieldAsOf[lang]}</span>
                  <span>{data.as_of_date}</span>
                </div>
                <p className="console-real-snapshot-card__accent-note">
                  {t.accentDisclaimer[lang]}
                </p>
              </div>
            ) : (
              <p className="console-real-snapshot-card__empty">{t.noneSelected[lang]}</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
