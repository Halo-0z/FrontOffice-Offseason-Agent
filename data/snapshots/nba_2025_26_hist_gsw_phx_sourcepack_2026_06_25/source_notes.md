# Snapshot Source Notes: nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25

## What this is

This is a **2025-26 historical source-backed snapshot**. It is NOT a
2026 offseason current roster, NOT a 2026-27 projected snapshot, and
NOT a fully verified legal/cap truth. It is the first small
provisional source-backed NBA snapshot used to validate the real data
pipeline end-to-end.

- **snapshot_id**: `nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25`
- **snapshot_type**: `historical_source_backed`
- **season**: `2025-2026`
- **source_pack_version**: `m8-d-v2`
- **as_of_date**: `2026-06-25` (web verification date)
- **sample_data**: `false`
- **manual_review_required**: `true`

## Scope

Only two teams (Golden State Warriors, Phoenix Suns), only 10 players,
only 9 contracts. This is deliberately small. It cannot be used to
compute a complete team payroll.

## Source distinction: NBA.com official vs third-party

- **NBA.com official**: The salary cap / luxury tax / apron values in
  `cap_config.json` come from the NBA.com official 2025-26 salary cap
  announcement. These are the authoritative league-wide cap figures.
- **Spotrac / Basketball Reference (third-party)**: All player contract
  salaries in `contracts.json` are third-party organized data. They are
  NOT the official NBA contract registry. They reflect 2025-26 cap hit
  as reported by the source pack, but option/guarantee/NTC fields are
  not confirmed against the actual contract documents.

## Contract data caveats

- All contract rows are **third-party organized data** from the source
  pack (`Spotrac 2025-26 contract/cap table`). Every contract row has
  `manual_review_required=true`.
- `salary` represents the **2025-26 cap hit**, not the full contract
  value.
- `years_remaining` is defined by the source pack as the number of
  years remaining **after the current (2025-26) season ends**. This is
  a flattened representation, not the full contract season-by-season
  breakdown.
- `no_trade_clause=false` is a **schema conservative default**. It does
  NOT mean the player has been legally confirmed to lack a no-trade
  clause. NTC status requires contract-level legal review and is not
  verifiable from third-party salary tables.
- `guaranteed`, `player_option`, `team_option` fields are likewise
  third-party interpretations and require manual review against actual
  contract documents.

## Devin Booker extension

Devin Booker's future extension is **flattened** into the
`years_remaining` field in this snapshot. The flat schema does not
separately model the extension vs. the existing contract. This
requires manual review to separate the base contract from the
extension.

## Dillon Brooks

Dillon Brooks is included in `players.json` but is **intentionally
excluded** from `contracts.json`. The source pack flagged a cap hit /
incentive / base salary mapping conflict for his contract. The
contract row is withheld pending manual confirmation of the correct
2025-26 cap hit figure. Do not infer his salary from this snapshot.

## minimum_salary

The `minimum_salary` value in `cap_config.json` uses the
**zero-years-of-service minimum salary** as an MVP scalar approximation.
The actual NBA minimum salary scales by years of service. This scalar
requires manual review for any per-player minimum-salary calculation.

## roster_min

`roster_min=14` requires CBA confirmation. The exact minimum roster
size rule and its interaction with hardship exceptions and two-way
contracts is not fully modeled here.

## Not a transaction source

This snapshot is **not a confirmed transaction source** and **not a
complete CBA/legal truth**. It must not be used as the sole basis for
approving or executing a real transaction. All outputs derived from
this snapshot require human approval and manual verification against
primary sources.

## Only 10 players / 9 contracts

This snapshot contains only 10 players and 9 contracts. It is not a
full roster. Do not use it to compute complete team payroll, cap
space, or tax position — many roster spots and contracts are missing.
