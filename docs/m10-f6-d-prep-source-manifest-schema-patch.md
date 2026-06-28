# M10-F6-D-prep-B: Source Manifest Schema Minimal Patch

## 1. Patch Scope

This is a minimal, backward-compatible patch to `schema/source_manifest_schema.json` (and corresponding tests/docs) to enable clean expression of future authorized API raw snapshot lineage and derived normalized lineage in `source_manifest.json`.

This patch:
- Adds two new `source_type` enum values to per-file source entries
- Adds optional provider-metadata fields to per-file source entries
- Adds explicit secret/credential field-name blocking at both top-level and per-file level
- Does NOT require any existing data migration
- Does NOT create raw snapshots or normalized roster data
- Does NOT change player/roster normalized schemas
- Does NOT introduce network dependencies or API keys

All changes are schema + tests + docs only.

## 2. Why source_manifest_schema Needed a Patch

F6-A (design gate), F6-B (adapter skeleton), and F6-C (key readiness checklist) established that future authorized API ingestion will produce two categories of files in `source_manifest`:

1. **Raw provider response files** under `raw/authorized_roster_api/{provider}/{as_of_date}/` — these need to record provider identity, endpoint template (key-redacted), access date, license/redaction notes, and secret-scan status.
2. **Derived normalized files** (`normalized/player_identities.json`, `normalized/roster_memberships.json`) — these need to record which raw files they were derived from and carry the same governance flags.

The existing schema (M10-E2) could not express `source_type=authorized_api_snapshot` or `source_type=authorized_provider_reference`, and had no fields for provider name, endpoint metadata, lineage pointers, or secret-scan confirmation. Without this patch, future F6-C raw snapshots and F6-D normalized rosters would have to overload `manual_curated` or `public_reference`, losing provenance precision.

## 3. Why Normalized Schemas Were Not Changed

`schema/player_identities_schema.json` and `schema/roster_memberships_schema.json` are intentionally **not** modified in this patch because:

- The field allowlist for player/membership records is already sufficient to carry identity + roster membership data from any source.
- The F6-B normalizer already enforces the allowlist and produces records that conform to the existing schemas.
- Adding provider-specific fields (like `provider_player_id`) to normalized records would require a separate, deliberate schema milestone with its own design review.
- Per-file source lineage belongs in `source_manifest.json`, not embedded in every player/membership record. The existing pattern (source metadata in manifest, data in normalized files) is preserved.
- `schema/real_snapshot_manifest_schema.json` is also untouched because it governs manifest.json (frozen snapshot description) and does not track per-file lineage.

## 4. New source_type Values and Semantics

| source_type | Used for | Semantics |
|---|---|---|
| `manual_curated` | Existing F4-B/F5-A manual entries | Human-curated from public sources (unchanged) |
| `public_reference` | Existing public reference entries | Publicly available reference pages (unchanged) |
| `league_roster` | Existing league roster entries | League-published roster info (unchanged) |
| `manual_non_official_ui` | Existing non-official UI metadata | Manually chosen non-official accent colors (unchanged) |
| **`authorized_api_snapshot`** | **Raw provider response files** | File is a verbatim (key-redacted) API response from an authorized provider (e.g. Sportradar, SportsDataIO). Carries provider_name, endpoint_template (no key), access_date, license notes, key-redaction notes, no_secret_in_raw flag, secret_scan_status. |
| **`authorized_provider_reference`** | **Normalized files derived from authorized raw snapshots** | File is derived from one or more `authorized_api_snapshot` raw files. Carries provider_name, derived_from_raw_files (array of relative paths), as_of_date, stale_after_date, governance flags. |

Existing values are preserved; no old data needs migration.

## 5. Optional Provider Metadata Fields

All new fields are **optional** (not added to `required`), so old `source_manifest.json` files remain valid without modification:

| Field | Type | Purpose |
|---|---|---|
| `source_reference` | string \| null | Per-file source reference (added for parity with top-level; was missing at per-file level) |
| `provider_name` | string | Provider identifier, e.g. `"sportradar"` or `"sportsdataio"` |
| `provider_endpoint_docs_url` | string (uri format) | Link to provider endpoint documentation (template, not key-bearing URL) |
| `endpoint_template` | string | Endpoint URL with `{placeholders}`, **no API key**. Example: `https://api.sportradar.com/nba/trial/v8/en/teams/{team_id}/profile.json` |
| `access_date` | string (date) | Date the raw fetch was performed (YYYY-MM-DD) |
| `stale_after_date` | string \| null (date) | Per-file stale date (mirrors top-level) |
| `license_notes` | string | Per-file license attribution |
| `key_redaction_notes` | string | How API key was redacted (e.g. "header auth used; key not in URL") |
| `no_secret_in_raw` | boolean | Confirmation that raw file contains no key/token/secret |
| `secret_scan_status` | string | Status of secret scan: `"passed"`, `"failed"`, `"skipped"` |
| `derived_from_raw_files` | array of strings (unique) | Relative paths of raw files this normalized entry is derived from |

## 6. Raw vs Normalized Lineage Design

**Raw file entry** (`source_type=authorized_api_snapshot`):
- Points to a file under `raw/authorized_roster_api/{provider}/{as_of_date}/`
- Carries `provider_name`, `provider_endpoint_docs_url`, `endpoint_template` (key-free)
- Carries `access_date` (fetch date), `as_of_date` (snapshot date), `stale_after_date`
- Carries `license_notes`, `key_redaction_notes`
- Carries `no_secret_in_raw=true`, `secret_scan_status="passed"`
- Carries `manual_review_required=true`, `live_eligible=false`
- Carries limitations and `data_freshness_warning`

**Normalized derived entry** (`source_type=authorized_provider_reference`):
- Points to `normalized/player_identities.json` or `normalized/roster_memberships.json`
- Carries `provider_name` (who the data came from)
- Carries `derived_from_raw_files=[relative raw file paths]` to establish provenance chain
- Carries `as_of_date`, `stale_after_date`
- Carries `no_secret_in_raw=true`, `manual_review_required=true`, `live_eligible=false`
- Does NOT carry endpoint_template or key_redaction_notes (those belong to the raw entry)

This design cleanly separates raw capture (F6-C) from normalized landing (F6-D): raw files have full provider lineage; normalized files point back to their raw sources.

## 7. Secret/Key Safety Design

This patch adds multiple layers of defense against secret/credential leakage in source_manifest:

1. **`additionalProperties: false`** at both top-level and per-file: any field not explicitly listed in `properties` is rejected. This automatically blocks `api_key`, `token`, `secret`, etc.
2. **Explicit `propertyNames` forbidden list** at per-file level: enumerates secret field names (`api_key`, `apikey`, `key`, `authorization`, `auth`, `token`, `access_token`, `auth_token`, `bearer_token`, `subscription_key`, `secret`, `password`, `credentials`) plus the existing forbidden domains (salary, contract, injury, live, execution verbs). Provides clearer error messages than `additionalProperties:false` alone.
3. **Extended top-level `propertyNames` forbidden list**: adds the same secret field names to the top-level block.
4. **No secret fields in properties**: `api_key`, `token`, `secret`, etc. are never added to the `properties` object, so they can never be valid.
5. **Test-level string scan helper**: `_scan_strings_for_secrets()` recursively scans all string values for patterns like `api_key=`, `SPORTRADAR_NBA_API_KEY`, `sk_`, `bearer`, `token=`, ensuring even accidental embedding in legitimate fields (URLs, notes) is caught.

## 8. Tests Added

New tests appended to `backend/app/tests/test_m10e_source_lineage_schema.py`:

- **Guard A** (`test_current_f5a_source_manifest_still_valid`): Existing F5-A source_manifest.json validates against patched schema (no forced migration).
- **Guard B** (`test_authorized_raw_source_entry_validates`): In-memory fixture with `authorized_api_snapshot` raw entry validates and carries correct fields.
- **Guard C** (`test_authorized_derived_normalized_entries_validate`): In-memory fixture with `authorized_provider_reference` entries for both normalized files validates.
- **Guard D** (`test_new_source_type_enum_accepted`): Both new source_type values accepted by parametrized test.
- **Guard E** (`test_per_file_secret_field_rejected_by_schema`): 13 secret-like field names parametrized; each causes ValidationError at per-file level.
- **Guard E-top** (`test_top_level_secret_field_rejected_by_schema`): Same secret field names cause ValidationError at top level.
- **Guard F** (`test_raw_fixture_strings_contain_no_secret_patterns`): String-scan helper verifies no secret patterns appear in any string value of the fixture.
- **Guard F-url** (`test_endpoint_template_has_no_key_query_param`): endpoint_template contains `{team_id}` placeholder and no `api_key=`.
- **Guard G** (`test_player_identities_schema_has_no_authorized_source_type`): player_identities_schema.json is verified to not contain F6-D markers (not modified).
- **Guard G** (`test_roster_memberships_schema_has_no_authorized_source_type`): roster_memberships_schema.json is verified to not contain F6-D markers (not modified).
- **Guard G** (`test_real_snapshot_manifest_schema_has_no_authorized_source_type`): real_snapshot_manifest_schema.json is verified unmodified.
- **Guard G** (`test_no_raw_files_created_under_data`): Asserts `data/snapshots/.../raw/` directory does not exist.
- **Guard G** (`test_no_new_normalized_data_files`): Asserts player_identities/roster_memberships still contain 14 players/14 memberships (F5-A sealed state).

Additionally, existing parametrized tests for `source_type` enum were updated to include the two new values.

Total: **100 passed** in `test_m10e_source_lineage_schema.py`.

## 9. What Remains HOLD

- **F6-C Raw Snapshot Capture**: Still HOLD until an authorized provider key (Sportradar or SportsDataIO) is acquired. This schema patch enables F6-C to record lineage correctly but does not perform any fetch.
- **F6-D 30-team Normalized Roster**: Still HOLD until F6-C raw snapshot capture is complete and raw files are reviewed. No normalized 30-team data is produced in this patch.
- **Manual Batch 2 expansion**: Still PAUSED per F6-A decision matrix.

## 10. Forbidden Areas Unchanged

This patch does NOT modify:
- `backend/app/services/**`
- `backend/app/api.py`
- `backend/app/snapshot_loader.py`
- `backend/app/models/**`
- `frontend/**`
- `Agent/orchestrator`
- `NL preview`
- `trade/signing logic`
- `data/**` (no files added or modified)
- `tools/**` (F6-B adapter skeleton untouched)
- `schema/player_identities_schema.json`
- `schema/roster_memberships_schema.json`
- `schema/real_snapshot_manifest_schema.json`
- `README.md`, requirements, pyproject

## 11. Next Recommended Step

- **If no key is available**: Stay at HOLD. This schema patch is forward-compatible and ready for whenever a key is acquired. No further code or data changes are needed until then.
- **If an authorized key exists**: Proceed to **M10-F6-C Raw Snapshot Capture** as a separate task:
  - Implement a real provider adapter conforming to the F6-B `RosterProvider` Protocol
  - Fetch raw responses for 30 teams using header-based auth (key from env only)
  - Write raw files to `data/snapshots/nba_real_2026_preoffseason_v1/raw/authorized_roster_api/{provider}/{as_of_date}/`
  - Run secret scan on raw files
  - Do NOT normalize, do NOT modify `player_identities.json`/`roster_memberships.json`
  - After raw capture, submit for review (ChatGPT/GPT-5.5) before any F6-D normalization

## 12. Testing Evidence

```
test_m10e_source_lineage_schema.py: 100 passed
```

Full M10 metadata regression results are documented in the handoff report.
