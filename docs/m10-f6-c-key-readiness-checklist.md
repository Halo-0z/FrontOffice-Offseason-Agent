# M10-F6-C Key Readiness Checklist

## Verdict: HOLD for raw snapshot capture until authorized provider key exists.

- Without an authorized API key: F6-C raw snapshot capture **cannot proceed**.
- With only nba_api / stats.nba.com: **not acceptable** for production 30-team ingest; suitable for research/prototyping only.
- With a Sportradar or SportsDataIO authorized key: F6-C **may proceed** for raw snapshot capture only — no normalized roster landing in F6-C.

This document is a readiness checklist only. It does not capture any data, does not connect to any API, and does not modify any code or data files.

---

## 1. Current Sealed State

| Item | Status |
|------|--------|
| M10-F5-A manual roster expansion Batch 1 | Sealed — 14 players / 14 memberships / 8 teams |
| M10-F6-A authorized roster API ingestion design gate | Sealed — CONDITIONAL GO |
| M10-F6-B provider adapter skeleton | Sealed — offline skeleton only |
| Real provider adapter (Sportradar/SportsDataIO) | **Does not exist** |
| Raw API response snapshots | **Do not exist** under `data/snapshots/**/raw/` |
| Normalized 30-team roster (`player_identities.json` / `roster_memberships.json`) | **Still at F5-A** (14 players / 8 teams) |
| API key in repo / env / .env | **Does not exist** |
| Network-capable code in `tools/roster_ingestion/` | **Does not exist** (no requests/httpx/aiohttp/urllib) |
| Backend runtime HTTP dependency | **Does not exist** |

The repo currently has only the offline ingestion skeleton (`tools/roster_ingestion/` with Protocol, allowlist, normalizer, fake provider) and 46 passing fixture-only tests. No real provider adapter exists. No raw or normalized data beyond F5-A exists.

---

## 2. What "Key Readiness" Means

Key readiness means **all** of the following conditions are met **before** any code that makes a real HTTP call is written or executed. F6-C raw snapshot capture is gated on every single item below.

### 2.1 Provider Readiness

- [ ] **Provider selected:** Sportradar (preferred) or SportsDataIO is chosen as the primary source.
- [ ] **License reviewed:** Provider terms permit offline snapshot processing, data storage in checked-in raw files, and use within this project's scope (personal/offline basketball simulation tool). License does not require runtime API calls for end users.
- [ ] **Authorized API key exists locally:** A valid, paid/authorized key is available in the operator's environment. The key is **not** stored in the repo, not in any tracked file, not in shell history.
- [ ] **Key must not appear in:** git history, repo files, log output, pytest output, raw snapshot files, manifest, source_manifest, URLs written to disk, error messages.
- [ ] **nba_api / stats.nba.com is not selected as primary:** These endpoints are acceptable for research/prototyping only and are not approved for production 30-team ingest per F6-A decision matrix.

### 2.2 Endpoint Readiness

- [ ] **Roster/team profile endpoint confirmed:** The provider's NBA Team Profile (or equivalent) endpoint is documented and accessible.
- [ ] **30-team coverage confirmed:** The endpoint supports iterating over all 30 NBA team IDs to fetch complete rosters.
- [ ] **Player identity fields returned:** The response includes player first name, last name, position, and a stable provider-side player identifier.
- [ ] **Roster membership returned:** The response associates each player with a team (the team whose profile is being fetched).
- [ ] **standard / two_way distinction assessed:** It is known whether the provider explicitly indicates two-way contract status.
  - If the provider explicitly marks two-way players, map to `two_way`.
  - If the provider explicitly marks standard/active players, map to `standard`.
  - **If the provider does not clearly distinguish status, all ambiguous players must be HOLD.** Unknown roster_status must never default to `standard`. This is the fail-closed rule established in F6-A/F6-B.
- [ ] **Endpoint documentation captured:** The doc URL or reference is saved for source_manifest attribution (the template URL, not a key-bearing URL).

### 2.3 Fetch Scope Readiness

F6-C is **raw snapshot capture only**. The following hard scope rules apply:

- [ ] **Raw only:** Only raw API response JSON files are produced.
- [ ] **No normalized landing:** `player_identities.json` is **not** modified in F6-C.
- [ ] **No normalized landing:** `roster_memberships.json` is **not** modified in F6-C.
- [ ] **No backend changes:** `backend/app/services/`, `backend/app/api.py`, `backend/app/snapshot_loader.py`, `backend/app/models/` are **not** modified.
- [ ] **No runtime dependency:** The backend service continues to read only frozen disk snapshots. No HTTP client is imported in any backend module.
- [ ] **No frontend/Agent/NL/trade/signing changes:** These surfaces remain untouched.

### 2.4 Security Readiness

- [ ] **Key is read from environment variable only:**
  - Sportradar: `SPORTRADAR_NBA_API_KEY`
  - SportsDataIO: `SPORTSDATAIO_NBA_API_KEY`
- [ ] **No CLI key passing:** The fetch script must not accept `--api-key` as a command-line argument (prevents shell history exposure).
- [ ] **No `.env` file committed:** If a local `.env` is used for convenience, it must be in `.gitignore` and never staged.
- [ ] **No key-bearing URLs on disk:** Any URL written to raw files, source_manifest, or docs must have the key redacted. Prefer header-based authentication over query-parameter keys so URLs are intrinsically key-free.
- [ ] **Fail closed on missing key:** If the env var is absent, the fetch script exits non-zero, creates no files, modifies nothing.
- [ ] **Fail closed on HTTP errors:** Non-200 responses, rate-limit responses, and malformed JSON must abort the fetch rather than writing partial/corrupt raw files.

---

## 3. F6-C Allowed Scope Once Key Exists

When a valid authorized key exists and all readiness conditions above are met, F6-C may produce:

**Allowed:**
- Raw API response snapshot files (verbatim JSON, key-redacted)
- Source capture documentation (fetch notes, endpoint observations, field mapping notes)
- Raw file SHA-256 hashes (computed but not yet written to source_manifest until manifest schema/strategy is reviewed)
- Documentation updates (this checklist, handoff docs)

**Still prohibited in F6-C:**
- `player_identities.json` normalization / update
- `roster_memberships.json` normalization / update
- Full 30-team normalized roster landing
- New API endpoints in the backend
- Frontend UI changes
- Backend app services runtime fetch logic
- Agent/orchestrator wiring
- NL preview integration
- Trade/signing logic changes
- Salary / contract / cap / injury / medical / rumor / scouting / live / depth_chart / minutes / role_projection / trade_eligibility data in any normalized file

---

## 4. Raw Snapshot Path Plan

When F6-C proceeds, raw files must be stored under:

```
data/snapshots/nba_real_2026_preoffseason_v1/raw/authorized_roster_api/{provider}/{as_of_date}/
```

Where:
- `{provider}` is `sportradar` or `sportsdataio` (lowercase, no spaces).
- `{as_of_date}` is an ISO date string (e.g., `2026-06-28`) representing the frozen snapshot date.

Path rules:
- [ ] **No key in filenames:** Filenames are team-derived (e.g., `team_BOS.json`, `roster_1610612738.json`) and must never contain an API key.
- [ ] **No secret in file contents:** Before writing, scan the response body for any echo of the key (some providers echo keys back); redact if found.
- [ ] **Full response body preserved:** The raw file should contain the provider's JSON response verbatim (after key redaction), so F6-D normalization and future re-reviews can audit the source.
- [ ] **Forbidden fields in raw are acceptable (in F6-C):** It is expected that provider responses include salary, injury, depth chart, and other forbidden domains. F6-C only saves raw. F6-D (normalization) will use the field allowlist to discard forbidden fields. The presence of forbidden fields in a raw file is **not** a reason to redact or withhold the raw snapshot; it is a reason to confirm the allowlist works before normalizing.
- [ ] **Each raw file must be hashed:** SHA-256 hash of the raw file (post-redaction, post-write) is recorded for source_manifest integrity verification (actual source_manifest update is deferred to F6-D per the schema review note in F6-A).
- [ ] **One directory per provider per as_of_date:** Re-fetching on a later date creates a new directory; old raw snapshots are immutable.

---

## 5. Preflight Checklist

Run through this checklist immediately before executing the F6-C raw fetch. Every box must be checked. If any box cannot be checked, **stop**.

- [ ] Provider selected (Sportradar or SportsDataIO)
- [ ] Provider license reviewed and acceptable for offline snapshot use
- [ ] API key available locally in environment variable — confirmed not in repo, not in any tracked file
- [ ] Env var name confirmed (`SPORTRADAR_NBA_API_KEY` or `SPORTSDATAIO_NBA_API_KEY`)
- [ ] Endpoint documentation URL captured (template URL, no key)
- [ ] 30-team fetch loop plan documented (team ID list, order, delay between requests)
- [ ] Rate limit / QPS known; appropriate delay configured to avoid quota/ban
- [ ] Raw file output path chosen and matches the plan in Section 4
- [ ] Key redaction plan confirmed (header auth preferred; query-param keys scrubbed from URLs and logs)
- [ ] Scope understood: F6-C is raw-only — no normalized file writes
- [ ] No runtime dependency introduced: backend services are untouched, no HTTP imports in `backend/`
- [ ] Review gate acknowledged: after raw capture, output is submitted for review (ChatGPT/GPT-5.5) **before** any F6-D normalization work begins

---

## 6. Stop Conditions

**Immediately stop F6-C** if any of the following are discovered during preparation or execution:

1. **API key missing or inaccessible.** The required env var is unset or empty.
2. **Provider license unclear or insufficient.** Cannot confirm that storing raw snapshots is permitted.
3. **Endpoint does not return roster membership.** The response does not associate players with teams.
4. **Endpoint cannot cover 30 teams.** Some teams are missing, IDs don't map, or pagination/loop is incomplete.
5. **Browser login / cookie required.** The endpoint demands session auth that cannot be satisfied with the API key alone.
6. **Key leakage risk detected.** A URL, log line, error message, or raw file would contain the key. Stop and fix redaction before proceeding.
7. **Tool attempts to write normalized roster.** If the fetch script modifies `player_identities.json` or `roster_memberships.json`, stop immediately — that is F6-D scope, not F6-C.
8. **Tool attempts to wire into backend runtime.** If code imports a roster provider into `backend/app/`, stop immediately.
9. **Forbidden fields appear in attempted normalized output.** If normalization is attempted (should not happen in F6-C) and fields like salary/contract/injury/live/depth are being included, stop.
10. **Network error / rate-limit / malformed response that would produce partial raw files.** Fail closed; do not write partial snapshots.

---

## 7. Handoff to F6-C Raw Snapshot Capture

When all readiness conditions are satisfied and an authorized key exists, a separate task must be opened:

**Task name:** M10-F6-C Raw Snapshot Capture

That task must:
- Use the skeleton from F6-B (`tools/roster_ingestion/`) to implement a real provider adapter conforming to `RosterProvider` Protocol
- Read the API key from environment variable only (no CLI args, no .env committed)
- Implement bounded fetch with rate-limit-aware delays for all 30 teams
- Write **only raw** response files to `data/snapshots/nba_real_2026_preoffseason_v1/raw/authorized_roster_api/{provider}/{as_of_date}/`
- Redact keys from all output (headers preferred over query-param auth)
- **Not** modify `player_identities.json`
- **Not** modify `roster_memberships.json`
- **Not** modify any file under `backend/app/services/`, `backend/app/api.py`, `backend/app/models/`, `frontend/`
- **Not** introduce network calls into backend tests
- Compute SHA-256 hashes of raw files for future source_manifest use
- After raw capture is complete, stop and hand off for review:
  - Raw files checked in
  - Capture notes documented
  - Field observations recorded (especially any standard/two_way ambiguity, forbidden fields present in raw, unexpected response shapes)
  - Submitted to ChatGPT/GPT-5.5 review before any F6-D normalization decision

Only after raw snapshot review is approved can F6-D (30-team normalized roster) be considered.

---

## 8. Final Conclusion

- **At this moment, no authorized provider key exists in this environment.**
- **M10-F6-C raw snapshot capture remains HOLD.**
- This document is strictly a readiness checklist. It creates no code, no data, no network dependency, no key, and no raw files.
- The next step depends entirely on acquiring an authorized Sportradar or SportsDataIO API key and completing license review.
- If a key becomes available, execute the preflight checklist (Section 5); do not proceed if any item is unchecked.
- Without an authorized key, production 30-team roster ingest does not continue. Manual Batch 2 expansion remains paused per F6-A decision matrix. The repo remains sealed at F6-B with the offline skeleton, 46 passing adapter tests, F5-A 14-player data, and full M10 regression (879 tests) passing.
