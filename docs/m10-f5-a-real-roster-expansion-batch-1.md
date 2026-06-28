# M10-F5-A: Real Roster Expansion — Batch 1

## 1. Batch 1 Scope

Batch 1 expands the real player identity + roster membership dataset from the M10-F4-B tiny pilot (2 teams / 4 players) to 8 teams. This is the first incremental batch in the 30-team real roster expansion.

Goal: Add verified real players for 6 additional teams (BOS, NYK, CLE, MIN, HOU, IND) while preserving the existing F4-B pilot players (OKC, DEN). All data remains frozen/as-of identity + roster membership only.

**GPT-5.5 source correction patch (2026-06-28):** After initial submission, ChatGPT acceptance was held. GPT-5.5 performed a source correction review and confirmed that two players had incorrect team affiliations per NBA.com and ESPN:
- **Darius Garland (nba-darius-garland)** — was listed as CLE; NBA.com and ESPN both confirm current affiliation is LA Clippers
- **Jalen Green (nba-jalen-green)** — was listed as HOU; NBA.com and ESPN both confirm current affiliation is Phoenix Suns

Both players were **removed** (not reassigned). No replacement players were added to compensate. CLE now has 1 player (Donovan Mitchell), HOU now has 1 player (Alperen Sengun).

## 2. Teams Attempted

| Team | Team ID | Players Attempted |
|------|---------|-------------------|
| Boston Celtics | nba-BOS | Jayson Tatum, Jaylen Brown |
| New York Knicks | nba-NYK | Jalen Brunson, Karl-Anthony Towns |
| Cleveland Cavaliers | nba-CLE | Donovan Mitchell, Darius Garland *(Garland removed post-review)* |
| Minnesota Timberwolves | nba-MIN | Anthony Edwards, Rudy Gobert |
| Houston Rockets | nba-HOU | Alperen Sengun, Jalen Green *(Green removed post-review)* |
| Indiana Pacers | nba-IND | Tyrese Haliburton, Pascal Siakam |

## 3. Teams Landed

All 6 attempted teams landed, but CLE and HOU were reduced to 1 player each after GPT-5.5 source correction removed Garland and Green respectively:

- **nba-BOS** — 2 players (Jayson Tatum, Jaylen Brown)
- **nba-NYK** — 2 players (Jalen Brunson, Karl-Anthony Towns)
- **nba-MIN** — 2 players (Anthony Edwards, Rudy Gobert)
- **nba-CLE** — 1 player (Donovan Mitchell)
- **nba-HOU** — 1 player (Alperen Sengun)
- **nba-IND** — 2 players (Tyrese Haliburton, Pascal Siakam)

Plus the original 2 teams from F4-B (OKC, DEN) with 4 players preserved.

**Total after Batch 1 (post source correction): 8 teams / 14 players / 14 memberships**

Per-team counts: OKC:2, DEN:2, BOS:2, NYK:2, CLE:1, MIN:2, HOU:1, IND:2 = 14.

## 4. Teams Skipped / HOLD Reason

None of the 6 target teams were skipped. CLE and HOU landed with 1 player each (rather than 2) after source correction removed players with incorrect team affiliations. No replacement players were added; teams are intentionally left with <2 players to maintain data integrity rather than adding unverified players.

Selection criteria was intentionally conservative: only franchise-cornerstone players on confirmed long-term standard contracts were added. Role players, bench players, two-way players, and players with uncertain contract status were excluded to maintain data quality.

## 5. Player Count Before/After

| Metric | Before (F4-B) | After F5-A Batch 1 (pre-correction) | After GPT-5.5 source correction (final) |
|--------|---------------|-------------------------------------|----------------------------------------|
| Players | 4 | 16 | **14** |
| Memberships | 4 | 16 | **14** |
| Teams with roster data | 2 (OKC, DEN) | 8 (OKC, DEN, BOS, NYK, CLE, MIN, HOU, IND) | 8 (same) |
| Distinct positions used | G, C, FC | G, C, FC, F, GF | G, C, FC, F, GF (same) |

Removed players: nba-darius-garland (CLE->LAC), nba-jalen-green (HOU->PHX).
Removed memberships: membership-cle-darius-garland, membership-hou-jalen-green.

## 6. Membership Count Before/After

All memberships use `roster_status: "standard"`. No two-way contracts were added due to insufficient dual-source confirmation. No replacement memberships were added to compensate for removed entries.

## 7. Source Verification Method

Dual-source verification was performed for each player using publicly accessible web pages:

**Primary sources:**
1. NBA.com player pages (where player IDs were confirmed)
2. NBA.com team roster pages (https://www.nba.com/{team}/roster)

**Secondary cross-verification sources:**
3. ESPN team rosters and player pages
4. China Daily sports coverage (for confirmed game photos showing player-team affiliation)
5. NetEase sports player profiles (current team confirmation)
6. Chinese sports media (Toutiao, Hupu, Gelonghui) for 2025-26 season game reports confirming player-team affiliation during the season

**GPT-5.5 source correction (2026-06-28):**
After initial submission, GPT-5.5 re-verified player-team affiliations against NBA.com and ESPN and confirmed two errors:
- Darius Garland currently listed on LA Clippers, not Cleveland Cavaliers
- Jalen Green currently listed on Phoenix Suns, not Houston Rockets

Per strict KEEP/REMOVE directive, both were removed without adding replacements.

**Verification criteria:**
- Each player must be confirmed as a member of their team via at least 2 independent public sources
- Players must be on standard NBA contracts (not two-way, Exhibit 10, training camp, or unsigned)
- Players with injury reports were noted but injury status is NOT stored in our data
- Birthdate/height/weight were intentionally left null for speed, consistent with F4-B pilot convention
- Source corrections override prior "long-term contract/should still be on team" heuristics — current NBA.com/ESPN affiliation is the ground truth

## 8. Source URL Summary

### NBA.com Player Pages (confirmed IDs):
- Donovan Mitchell: https://www.nba.com/player/1628378/donovan-mitchell
- Rudy Gobert: https://www.nba.com/player/203497/rudy-gobert
- Karl-Anthony Towns: https://www.nba.com/player/1626157/karl-anthony-towns
- Shai Gilgeous-Alexander: https://www.nba.com/player/1628983/shai-gilgeous-alexander (F4-B preserved)
- Chet Holmgren: https://www.nba.com/player/1631096/chet-holmgren (F4-B preserved)
- Nikola Jokic: https://www.nba.com/player/203999/nikola-jokic (F4-B preserved)
- Jamal Murray: https://www.nba.com/player/1627750/jamal-murray (F4-B preserved)

### NBA.com Team Roster Pages (used as source for players without confirmed individual page IDs):
- Boston Celtics: https://www.nba.com/celtics/roster (Tatum, Brown)
- New York Knicks: https://www.nba.com/knicks/roster (Brunson)
- Cleveland Cavaliers: https://www.nba.com/cavaliers/roster (Mitchell; Garland removed post-correction)
- Minnesota Timberwolves: https://www.nba.com/timberwolves/roster (Edwards)
- Houston Rockets: https://www.nba.com/rockets/roster (Sengun; Green removed post-correction)
- Indiana Pacers: https://www.nba.com/pacers/roster (Haliburton, Siakam)
- Oklahoma City Thunder: https://www.nba.com/thunder/roster (F4-B preserved)
- Denver Nuggets: https://www.nba.com/nuggets/roster (F4-B preserved)

### Secondary Cross-Verification URLs:
- China Daily: Haliburton + Siakam Pacers elimination game photo (2025-05)
- NetEase Sports: Pascal Siakam player profile confirming IND affiliation

## 9. Data Fields Included

### player_identities.json:
- player_id (string, `nba-first-last` format)
- display_name, first_name, last_name
- position (G/F/C/FC/GF per schema enum)
- source_name, source_url, source_type
- as_of_date, snapshot_id
- manual_review_required (true), live_eligible (false)
- data_freshness_warning
- limitations (array)
- notes (array)

### roster_memberships.json:
- membership_id (string, `membership-{team}-{player}` format)
- team_id (nba-XXX format)
- player_id (cross-reference)
- roster_status ("standard" only for Batch 1)
- source_name, source_url, source_type
- as_of_date, snapshot_id
- manual_review_required (true), live_eligible (false)
- data_freshness_warning
- limitations (array)

## 10. Data Fields Explicitly Excluded

The following fields are **NOT** present in any data file:

- salary / salaries / contract / contracts / cap_hold / guarantee_amount
- cap_sheet / cap_sheets
- injury / injuries / injury_status / medical / medical_status / health
- rumors / rumor / scouting_opinion / scouting_opinions
- live_status / availability / real_time_availability / active_now
- current_roster / latest_roster / latest_data / live_data / current_salaries / real_time_data
- projected_depth_chart / depth_chart / minutes_projection / role_projection
- trade_eligibility
- execute / apply / commit / mutate / write / persist / save / delete / update / submit / auto_execute / auto_approve
- headshot / headshot_url / player_image / photo_url
- birthdate / height / weight (intentionally null for all players)

Forbidden files confirmed absent:
- contracts.json
- salaries.json
- cap_sheet.json / cap_sheets.json
- injuries.json
- rumors.json
- scouting_opinions.json
- live_status.json

## 11. Source Manifest Hash Summary

SHA-256 hashes in source_manifest.json (final, post source correction):

| File | Hash |
|------|------|
| normalized/teams.json | sha256:5b1e388bb2b7506832e7fbb0a06e105b9478d4a5caea9fe9514032bd22dc5fbb (unchanged) |
| normalized/team_visual_metadata.json | sha256:96274923a688fd05b2c1092487767d462620036dd6605abc0d3d800d6fb3bb8c (unchanged) |
| normalized/player_identities.json | sha256:7dfb3c79d2b18122468ce4bd13189cb69a72a6a766ca36302419c973cef6026f (post-correction) |
| normalized/roster_memberships.json | sha256:eb66e528c6d26087f404f808f1caedff0a637e542e67ae7574f58956d051fa32 (post-correction) |

Metadata updates:
- created_by: "m10-f5a-batch1-source-correction"
- reviewed_by: "m10-f5a-gpt55-source-correction"
- source_pack_version (in manifest.json): "m10-f5a-batch1-correction-v1"
- data_categories preserved: ["teams", "team_visual_metadata", "player_identities", "roster_memberships"]
- stale_after_date preserved: "2026-07-12"

## 12. Test Results

### Test Group 1 (F reader only):
```
96 passed
```

### Test Group 2 (E schema + F reader):
```
581 passed
```

### Test Group 3 (Full M10 suite):
```
833 passed
```

Key test migrations performed:
- `TestTinyPilotSmoke` renamed to `TestBatch1ExpandedRosterSmoke`
- Exact count assertions: 14 players / 14 memberships (post source correction)
- Explicit non-presence assertions for removed IDs (nba-darius-garland, nba-jalen-green, membership-cle-darius-garland, membership-hou-jalen-green)
- F4-B subset presence checks preserved
- BATCH1 corrected player presence checks (only the 10 new players that survived correction)
- Added duplicate player_id detection
- Added duplicate membership_id detection
- Added team_id whitelist check (must be in {OKC, DEN, BOS, NYK, CLE, MIN, HOU, IND})
- Added roster_status whitelist check (must be "standard" only; no unknown_manual_review, no two_way)
- Added birthdate/height/weight null checks for ALL players
- Added position enum validation for ALL players
- Forbidden field/file isolation guards preserved and strengthened
- API/frontend/Agent/NL/trade/signing import guards preserved

## 13. Known Limitations

1. **Not full rosters**: Most teams have only 2 players (franchise cornerstones); CLE and HOU have 1 player each after source correction. Full 15-18 man rosters are deferred to future batches.
2. **No replacement players added**: CLE and HOU were intentionally left with 1 player each rather than adding unverified alternatives to "round out" the batch. Data integrity is prioritized over symmetry.
3. **Birthdate/height/weight null**: These optional identity fields are intentionally null for speed, consistent with F4-B convention.
4. **Position resolution**: Jaylen Brown classified as GF (Guard-Forward) due to dual-position listing; Chet Holmgren's FC classification from F4-B preserved despite position conflict documentation.
5. **No two-way contracts**: All memberships are standard contracts; two-way players require additional source verification not performed in this batch.
6. **Stale window**: Data is frozen as-of 2026-06-28 with stale_after_date of 2026-07-12. Offseason transactions after this date are not reflected.
7. **No automated scraping**: All data was manually curated and verified. No runtime API integration or scraping scripts were created.
8. **Non-official colors preserved**: Team visual metadata uses non-official UI accent colors only, not official brand colors.
9. **Source URL limitations**: For players without confirmed NBA.com individual page IDs, team roster pages are used as source_url. These are specific public pages (not homepages) but do not deep-link to individual player profiles.
10. **Source correction lesson**: Initial verification relied on Chinese sports media recap reports that can lag transactions; future batches must verify current NBA.com/ESPN affiliation directly for every player before adding.

## 14. Next Batch Recommendation

**Batch 2 recommendations:**

1. **Add more players per team** (target 3-4 per team): Expand existing teams from current counts toward 3-5 players, but only add players whose current NBA.com/ESPN team affiliation is directly verified.
2. **Prioritize direct NBA.com player page verification**: For every new player, confirm NBA.com player page shows the expected team before adding. Do not rely on recap articles or pre-trade reports.
3. **Add 6 more teams**: Consider Western Conference contenders and notable franchises, with same source verification rigor:
   - nba-GSW Golden State Warriors
   - nba-LAL Los Angeles Lakers
   - nba-DAL Dallas Mavericks
   - nba-MIL Milwaukee Bucks
   - nba-PHX Phoenix Suns
   - nba-SAS San Antonio Spurs
4. **Do not backfill Garland/Green replacements**: The removed players can be re-added in a future batch under their correct teams (LAC for Garland, PHX for Green) when those teams are covered.
5. **Consider adding two-way contracts** once dual-source verification methodology is refined.
6. **Consider populating birthdate** for at least high-profile players where sources are in complete agreement.

## 15. Final Conclusion

M10-F5-A Batch 1 (post GPT-5.5 source correction) expands the real roster dataset from 2 teams/4 players to 8 teams/14 players while maintaining all isolation guarantees, schema compliance, and data quality standards. Two players (Darius Garland, Jalen Green) with incorrect team affiliations were removed per GPT-5.5 review; no replacement players were added. CLE and HOU intentionally land with 1 player each. All tests pass. No forbidden data categories (salary/contract/cap/injury/scouting/rumor/live) were introduced. No API/frontend/Agent/NL/trade/signing code was modified. The corrected expansion is ready for ChatGPT re-acceptance review.
