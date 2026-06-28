# M10-F6-E Free / Trial Provider Evaluation

## Verdict: HOLD for production F6-C raw capture using free/trial sources.

- **No truly suitable free production source was found.** No free or trial-tier API provides the combination of authorization clarity, complete 30-team coverage, explicit standard/two_way semantics, and permission to save/derive data that production raw snapshot capture requires.
- **Free/trial sources may support internal evaluation or experimental validation only.** They are useful for verifying adapter shape, endpoint structure, and response schemas — but their data, terms, or stability do not qualify them as authoritative production roster sources.
- **Production raw capture still requires a paid/authorized source with explicit storage and derivative-data permission.** This evaluation confirms that F6-C production raw capture remains gated on obtaining a Sportradar or SportsDataIO paid/authorized agreement.

This document is a docs-only evaluation gate. It does not connect to any API, does not create any raw snapshots, and does not modify any code, schema, or data files.

---

## 1. Current Sealed State

| Milestone | Status | Summary |
|---|---|---|
| M10-F5-A | Sealed | 14 players / 14 memberships / 8 teams (Batch 1 post source correction; Garland→LAC, Green→PHX removed) |
| M10-F6-A | Sealed | Authorized API Ingestion Design Gate — CONDITIONAL GO |
| M10-F6-B | Sealed | Provider adapter skeleton (tools/roster_ingestion/ with Protocol, allowlist, normalizer, fake provider; 46 tests) |
| M10-F6-C | Sealed | Key Readiness Checklist — HOLD until authorized key exists |
| M10-F6-D-prep | Sealed | Source manifest schema minimal patch (source_type enum + optional provider metadata + secret safety; 100 source lineage tests; 918 total M10 regression tests pass) |
| Authorized provider key | **Does not exist** in this environment |
| F6-C production raw capture | **HOLD** |
| F6-D normalized 30-team landing | **HOLD** |

The repo currently has only F5-A sealed data (14 players / 8 teams), an offline ingestion skeleton, schema readiness for future authorized lineage, and zero network-capable code in the backend or tools.

---

## 2. Provider Comparison Summary

Evaluation covers providers identified in the F6-A design gate plus other commonly cited free/trial NBA roster APIs. "Free/trial" includes permanently free tiers, time-limited trials, freemium models, and unofficial clients.

| Provider | Free/trial exists | Key required | Credit card required (known) | Roster endpoint | 30-team coverage | Data type | standard/two_way | Raw save / derived permission | Rate/quota | F6-C production suitability |
|---|---|---|---|---|---|---|---|---|---|---|
| **Sportradar** (paid agreement) | Trial/sandbox exists | Yes | Often required for trial | NBA Team Profile (v8) returns team info + full roster | Yes (all 30 teams via team profile loop) | Real official data on paid tier; trial may have limited/sample/rate-restricted data | Paid: likely present; trial: needs verification | Paid: requires license review; trial: evaluation-only, storage/derivative rights unclear | Trial: strict quota & QPS; paid: contractual | **GO** (paid/authorized only); **CONDITIONAL GO** for experimental adapter validation with trial (no normalized landing); **HOLD** for production on free trial |
| **SportsDataIO** | Free trial exists | Yes | Often required for trial | NBA Teams/Players/Rosters endpoints | Yes (teams + rosters endpoints) | Realistic/real data on paid; free tier may return scrambled, partial, delayed, or sample data per tier | Paid: likely; trial: uncertain, two-way may not be explicit | Paid: requires license review; free trial: terms typically limit storage/redistribution; scrambled data must not be treated as authoritative | Free tier: daily/monthly caps; paid: contractual | **CONDITIONAL GO** (paid after license/field review); **HOLD** on free trial |
| **BALLDONTLIE** | Free tier exists; some endpoints paid | Yes (free key) | No for free tier | `active_players`/players endpoint; team rosters may require paid GOAT tier | Limited on free tier (active_players may list players but team-roster mapping semantics unclear) | Aggregate/non-official; not an NBA-authorized data source | Unclear/absent — no explicit two-way contract semantics; roster status is "active" style only | Free tier: standard API terms; redistribution/derivative rights for checked-in snapshots unclear; not an authoritative source | Free: rate-limited; paid: higher caps | **HOLD** for production; **CONDITIONAL GO** for F6-C-alt experimental shape validation only (no normalized landing) |
| **nba_api / stats.nba.com** | Free (no key) | No (Unofficial Python client; no key) | N/A | `commonteamroster` / CommonTeamRoster endpoint returns roster-like data | Yes (30 teams via loop) | Real NBA stats data but accessed through unofficial client; endpoint stability and ToS ambiguous | `ROSTERSTATUS` field exists but semantics are undocumented; two-way distinction not guaranteed | Unofficial client; NBA.com terms of service do not explicitly authorize storage/redistribution of responses for third-party snapshots; endpoint may change without notice | No hard quota but aggressive rate-limiting/blocking possible; no SLA | **REJECT** for production 30-team ingest; **CONDITIONAL GO** for research/prototype only under separate experimental gate (no production landing) |
| **API-Sports** (api-sports.io / RapiAPI) | Free tier exists (limited calls) | Yes (RapiAPI key) | No for free tier | NBA teams/players endpoints | Yes via teams/players endpoints | Aggregate data source; not NBA-authorized | No explicit two-way semantics; contract/roster status limited | RapiAPI free tier terms typically restrict commercial use and redistribution; paid plan needed for production use | Free: very low daily cap (~100 calls/day on free plan) | **REJECT** for production F6-C |
| **TheSportsDB** | Free tier exists (test key) | Yes (test key `3` or free API key) | No | Lookup team/player endpoints; roster endpoints | Partial/free-tier data quality varies; community-maintained | Community/aggregate; not authoritative; missing players/teams common | Absent — no two-way or contract status fields | Free tier: non-commercial/demo use implied; production storage/derivative rights not granted | Free: rate-limited; metadata incomplete | **REJECT** for production F6-C |
| **Statorium** | Free/freemium exists | Yes | Unclear | NBA teams/rosters endpoints | Advertised but data completeness unverified; smaller provider | Aggregate; authorization status unclear | Uncertain | Terms not reviewed; no clear redistribution grant | Unknown | **REJECT** for production F6-C without dedicated license/source gate |
| **AllSportsAPI / other free NBA APIs** | Various | Varies | Varies | Varies | Varies | Generally aggregate/non-official | Generally absent | Generally unclear | Varies | **REJECT** for production F6-C without provider-specific license/source gate |

Legend:
- **GO**: Approved for production F6-C raw capture subject to readiness checklist.
- **CONDITIONAL GO**: Usable for limited/experimental purposes only with explicit non-production scope.
- **HOLD**: Not approved; requires further authorization, license review, or paid agreement before use.
- **REJECT**: Not suitable for production; should not be used for authoritative roster capture even in trial form.

---

## 3. Sportradar Conclusion

**Strongest technical fit for production.**

- Sportradar's NBA v8 API includes a Team Profile endpoint that returns team metadata plus the full active roster, matching the F6-B adapter contract design.
- The provider is a recognized official sports data partner with clear documentation and stable endpoint design.
- A trial/sandbox key may allow validating adapter behavior (endpoint shape, response schema, player-record structure, 30-team iteration) if the trial endpoint is accessible.
- **However**, free trial or internal evaluation terms are **not sufficient** to capture raw responses into the repository as production source data unless the license explicitly permits offline storage, derivative works (normalized roster files), and redistribution within this project's scope.
- Production F6-C raw capture requires a **paid/authorized agreement** or written permission explicitly granting storage, snapshotting, and derived normalized file creation.
- **F6-C production: HOLD without paid/authorized agreement.**
- **F6-C experimental (adapter-shape validation): CONDITIONAL GO** only if the activity is explicitly internal/evaluation-only, no raw files are committed to the repository, and no normalized roster landing is attempted. Any experimental fetch must not write to `data/snapshots/`.

---

## 4. SportsDataIO Conclusion

**Potential secondary source; not approved on free trial.**

- SportsDataIO offers a free trial and has documented NBA teams, players, and rosters endpoints.
- The free trial tier may return scrambled, realistic-looking but not fully accurate data (a common pattern across sports-data free tiers to protect paid value). Such data must not be treated as authoritative roster facts.
- The free tier is useful for **integration shape testing only** — verifying that the adapter can parse the response structure, iterate teams, and map basic fields — but must never produce normalized data that lands in `data/snapshots/normalized/`.
- A paid subscription, after license review confirming storage, snapshot, and derivative-data rights, and after field-mapping review (for forbidden-domain filtering per F6-B allowlist), may be a viable path.
- standard/two_way distinction on SportsDataIO needs verification from the paid-tier response schema; if not explicit, all ambiguous statuses must be HOLD per F6-A fail-closed rule.
- **F6-C production: HOLD on free trial.** CONDITIONAL GO for paid subscription after license and field review.

---

## 5. BALLDONTLIE Conclusion

**Experimental shape-validation only; not an authoritative source.**

- BALLDONTLIE offers a free tier with an API key and lists active NBA players.
- Full team-roster endpoint (mapping players to teams with contract status) may require the paid GOAT tier or a trial; free-tier roster semantics are not clearly documented.
- It is an aggregate/non-official source — not an NBA-authorized data provider — and must not be treated as authoritative.
- There is no explicit standard/two_way contract status field in the free API; the data model uses active/inactive style flags that do not align with the F6 roster_status enum.
- Can serve as an **F6-C-alt experimental source** for adapter development (parsing practice, schema shape) but:
  - Must be explicitly marked non-authoritative
  - Must not produce normalized files in `data/snapshots/normalized/`
  - Must not be presented as a production roster source
- **Not approved for production raw capture or normalized landing.**

---

## 6. nba_api / stats.nba.com Conclusion

**Research/prototype only; production 30-team ingest HOLD.**

- The `nba_api` Python client is free, requires no key, and exposes the `commonteamroster` (CommonTeamRoster) endpoint which can return roster-like data for all 30 teams.
- It is an **unofficial client** for NBA.com stats endpoints. The NBA.com terms of service, endpoint stability, and authorization boundaries are insufficient for production data capture:
  - Endpoints can change or be blocked without notice
  - No SLA, no rate-limit guarantee
  - Terms do not explicitly authorize third-party storage/redistribution of responses
  - `ROSTERSTATUS` field exists but is undocumented and may not reliably distinguish two-way contracts from standard contracts
- Using nba_api for production would violate the F6-A core principle that authorized/offline ingestion must be based on an authorized source with clear license and storage rights.
- It is acceptable for personal research, prototyping, or verifying adapter parsing logic — but any such use must be under a **separate non-production experimental source gate** and must never produce normalized data that lands in the repository's production snapshot path.
- **Production 30-team ingest: HOLD (effectively REJECT for production).**

---

## 7. Other Candidates

**API-Sports, TheSportsDB, Statorium, AllSportsAPI, and similar free/freemium NBA APIs do not beat Sportradar or SportsDataIO on the combination of authorization clarity, complete roster endpoint semantics, 30-team coverage, and standard/two-way distinction:**

- Most are aggregate/community-sourced with no official NBA licensing
- Free tiers have tight rate limits (e.g., ~100 calls/day on API-Sports free plan) that would impede a reliable 30-team fetch loop
- Roster status semantics (standard vs two_way) are generally absent
- License/redistribution/derivative terms are typically restrictive or vague on free tiers
- Data quality varies; missing players, incorrect team assignments, and delayed transactions are common

**None of these providers enter production F6-C without a dedicated provider-specific license/source gate** (analogous to F6-A but scoped to that provider). Without such a gate, they are rejected for production use.

---

## 8. Decision Matrix

| Scenario | Decision |
|---|---|
| Production F6-C raw capture using free/trial sources | **HOLD** — no free/trial source is approved for production raw snapshot capture into the repository |
| F6-C-alt experimental capture (adapter validation only) using trial/free endpoints | **CONDITIONAL GO** — only if explicitly marked non-production, non-authoritative, no raw files committed, no normalized landing, no data used as roster facts |
| F6-D normalized 30-team roster landing from any free/trial source | **HOLD** — no free/trial source can produce authoritative normalized roster data |
| Paid/authorized Sportradar agreement acquired | **GO** (preferred path) — proceed to F6-C raw capture after key readiness checklist passes |
| Paid/authorized SportsDataIO subscription acquired | **CONDITIONAL GO** — proceed to F6-C after license review, field-mapping review, and confirmation that standard/two_way semantics are present in the response |
| BALLDONTLIE / nba_api used for experimental adapter testing | **CONDITIONAL GO** for local/experimental use only; no repository data landing; must be isolated from production snapshot paths |
| Other free APIs (API-Sports, TheSportsDB, etc.) used for production | **REJECT** — do not use without dedicated license/source gate |
| Manual Batch 2 expansion (more hand-curated players) | **PAUSED** per F6-A decision matrix; prioritize authorized path over further manual expansion |

---

## 9. Risks

Using free/trial sources for production ingest carries the following risks, each of which this evaluation explicitly guards against:

1. **License overreach.** Free-tier terms rarely grant rights to store API responses long-term, create derivative normalized files, or redistribute data in a public GitHub repository. Using such data could violate provider terms.
2. **Storing trial data beyond permitted use.** Even when trials return real data, trial terms often limit use to evaluation. Committing trial responses as production raw snapshots would violate those terms.
3. **Scrambled data mistaken as real.** Some providers (notably SportsDataIO free tier) return scrambled or synthetic data on trial tiers. Treating such data as authoritative would reintroduce the exact correctness problem that motivated F6 (remember Garland/Green).
4. **Key leakage.** Free-tier keys are still credentials. Even free keys must follow the F6-C security rules (env-only, no CLI passing, no URLs with keys written to disk, redaction). Free keys do not reduce the need for secret hygiene.
5. **Unofficial endpoint instability.** nba_api and similar unofficial clients can break without notice when the upstream site changes. Production snapshots cannot depend on endpoints with no stability guarantee.
6. **Lack of standard/two_way semantics.** Most free and aggregate sources do not explicitly distinguish two-way contracts from standard contracts. Silently mapping missing/ambiguous status to "standard" would violate the F6-A fail-closed rule.
7. **Aggregate/non-official sources treated as authoritative.** Community-maintained or aggregate APIs may contain stale, incorrect, or incomplete roster data. Authoring them as authoritative snapshots in this repo would repeat the source-correctness failure mode of F5-A.

---

## 10. Next Recommended Path

1. **Do not use free/trial APIs for production 30-team roster ingest.** None of the evaluated free/trial sources meet the bar for F6-C production raw capture.
2. **Apply for or obtain paid/authorized access** to Sportradar (preferred) or SportsDataIO (secondary after license review). The readiness checklist in F6-C and the schema patch in F6-D-prep are already in place to support this path as soon as a key is acquired.
3. **If no key is available, stop production ingest work here.** The F6-B adapter skeleton, F6-C readiness checklist, and F6-D-prep schema patch are forward-compatible and ready. No further data production work should proceed without an authorized key.
4. **Optional F6-C-alt experimental gate:** If local adapter-shape validation against free/trial endpoints is desired (e.g., to test the RosterProvider Protocol implementation against a real HTTP response shape), this must be done under a separate explicitly non-production experimental gate:
   - No raw files written to `data/snapshots/`
   - No normalized files written
   - No modification to production source_manifest
   - Experimental code must be clearly marked as non-authoritative
   - Any experimental fetch must be local-only; nothing committed
5. **Keep the current F5-A 14-player snapshot as the only sealed real roster data** until an authorized source is secured and F6-C/D proceed through review.

---

## 11. Final Conclusion

- **No free production source is approved.** Every free or trial-tier provider evaluated fails at least one critical requirement for production raw capture: missing authorization, ambiguous terms, scrambled data, absent two-way semantics, restrictive rate limits, or unstable unofficial endpoints.
- **F6-C production raw capture remains HOLD.** The gate from F6-C (authorized key required) is reaffirmed. Free/trial keys do not satisfy this gate.
- **F6-D normalized 30-team roster remains HOLD.** Without an authorized raw snapshot, no normalized 30-team landing can proceed.
- **Free/trial provider evaluation is now documented** in this file for future decision-making. When a paid/authorized key is acquired, F6-C raw capture can proceed immediately using the existing F6-B skeleton, F6-C readiness checklist, and F6-D-prep schema patch — no further prep is required from a tooling/schema standpoint.
- The repository remains sealed at F5-A data + F6-B/F6-C/F6-D-prep tooling/docs, with 918 M10 regression tests passing and no network-capable code in the runtime path.
