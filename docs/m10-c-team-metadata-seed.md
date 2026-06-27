# M10-C1: 30 Team List Metadata Seed

## 1. M10-C1 目标

M10-C1 在 M10-B schema 基础上，首次向 `nba_real_2026_preoffseason_v1` real snapshot 中填充**公开事实性** 30 队 team identity 数据。

M10-C1 **只做**：
- 定义 `normalized/teams.json` 的 JSON Schema
- 填入 30 队 team_id / city / name / abbreviation / conference / division
- 更新 manifest.json 和 source_manifest.json 以反映数据变更
- 添加 schema 自校验 + 负向 + 回归测试

M10-C1 **不做**：
- 不导入球员名单、roster、contracts、salaries、cap sheets、free agents、draft assets
- 不导入 team colors / primary_color / secondary_color
- 不导入 team logos / 任何图片资源
- 不改 loader / backend API / frontend
- 不接真实 NBA API
- 不抓取网站
- 不接 LLM

## 2. 为什么 C1 只做 team list，不做 colors

GLM-5.2 在 M10-B Review 中明确建议将 M10-C 拆分为 C1（team list）和 C2（team visual metadata / safe colors）：

- **Team identity（队名、缩写、分区）是公开事实性信息**，无版权/商标风险，可以直接作为后续所有数据的 anchor（team_id 是 contracts/roster/salaries 的外键）。
- **Team colors 涉及品牌视觉资产**：primary/secondary color 的选择需要谨慎验证，某些色值可能与球队商标强关联；M10-A 已经明确"先做 abbreviation badge / fallback badge，不直接使用真实 NBA logo"，colors 同理应该单独评审安全的 neutral palette 方案。
- **先让 team list 落位**可以让后续 loader 开发、roster/contract schema 设计有稳定的 team_id 基础，不必等待 colors 方案定稿。

因此 M10-C1 先完成 team list seed，M10-C2 再考虑 team visual metadata。

## 3. 新增/修改文件说明

### 新增文件

| 路径 | 说明 |
|------|------|
| `schema/teams_schema.json` | `normalized/teams.json` 的 JSON Schema (Draft 2020-12) |
| `data/snapshots/nba_real_2026_preoffseason_v1/normalized/teams.json` | 30 队 team identity 数据 |
| `backend/app/tests/test_m10c_team_metadata.py` | Schema 正向/负向/回归测试 |
| `docs/m10-c-team-metadata-seed.md` | 本文档 |

### 修改文件

| 路径 | 变更 |
|------|------|
| `data/snapshots/nba_real_2026_preoffseason_v1/manifest.json` | teams 数组从 `[]` 更新为 30 个 `nba-XXX`；source_name/source_url/source_pack_version/description/limitations 更新为反映 teams 数据 |
| `data/snapshots/nba_real_2026_preoffseason_v1/source_manifest.json` | data_categories 从 `[]` 改为 `["teams"]`；新增 per_file_sources entry；新增 file_hashes SHA-256；source_name/source_url/license_notes/freshness_label/freshness_policy/data_freshness_warning/limitations/created_by/reviewed_by 更新为反映 teams 数据 |

### 未修改

- `schema/source_manifest_schema.json` — M10-B 封口，不改
- `schema/real_snapshot_manifest_schema.json` — M10-B 封口，不改
- `backend/app/tests/test_m10_real_snapshot_schema.py` — M10-B 测试，不改（回归测试确保仍然全部通过）
- demo snapshot 目录 `nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25/` — 不改
- frontend, backend API, snapshot_loader.py, 其他 loader 代码 — 不改
- M9 已封口模块 — 不改

## 4. teams_schema 字段说明

### 顶层字段 (`schema/teams_schema.json`)

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `teams` | array | 是 | minItems=30, maxItems=30 | 30 个 team object |
| `source_name` | string | 是 | minLength=1 | 数据来源名称 |
| `source_url` | string \| null | 是 | — | 数据来源 URL 或 null |
| `as_of_date` | string | 是 | pattern `^[0-9]{4}-[0-9]{2}-[0-9]{2}$` | 数据截止日期 YYYY-MM-DD |
| `manual_review_required` | boolean | 是 | const: true | 所有 curated real 数据必须人工审核 |

### team object 字段

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `team_id` | string | 是 | pattern `^nba-[A-Z]{3}$` | 格式 `nba-XXX`，如 `nba-GSW` |
| `city` | string | 是 | minLength=1 | 城市/市场名（如 "Golden State", "LA"） |
| `name` | string | 是 | minLength=1 | 队昵称（如 "Warriors", "Trail Blazers"） |
| `abbreviation` | string | 是 | pattern `^[A-Z]{3}$` | 三字母缩写 |
| `conference` | string | 是 | enum: "East" \| "West" | 东西部 |
| `division` | string | 是 | enum: Atlantic / Central / Southeast / Northwest / Pacific / Southwest | 六大赛区 |

### 禁止字段（通过 `propertyNames` + `not: { enum: [...] }` 在顶层和 team 级别同时禁止）

**Logo/branding：** `logo_path`, `logo_url`, `official_logo`, `nba_logo`, `team_logo`, `mascot_image`

**Colors：** `primary_color`, `secondary_color`, `colors`

**Roster/contract/salary：** `roster`, `players`, `contracts`, `salaries`, `cap_sheet`

**Execution verbs：** `execute`, `apply`, `commit`, `mutate`, `write`, `persist`, `save`, `delete`, `update`, `submit`, `auto_execute`, `auto_approve`

**Live/current 暗示：** `current_roster`, `live_salaries`, `latest_data`, `live_data`, `current_salaries`, `real_time_data`

**additionalProperties: false** 在顶层和 team 级别同时生效，任何未声明字段都会被拒绝。

## 5. 30 队数据说明

`normalized/teams.json` 包含以下 30 队，按联盟排序惯例排列：

| Abbr | City | Name | Conference | Division |
|------|------|------|------------|----------|
| ATL | Atlanta | Hawks | East | Southeast |
| BOS | Boston | Celtics | East | Atlantic |
| BKN | Brooklyn | Nets | East | Atlantic |
| CHA | Charlotte | Hornets | East | Southeast |
| CHI | Chicago | Bulls | East | Central |
| CLE | Cleveland | Cavaliers | East | Central |
| DAL | Dallas | Mavericks | West | Southwest |
| DEN | Denver | Nuggets | West | Northwest |
| DET | Detroit | Pistons | East | Central |
| GSW | Golden State | Warriors | West | Pacific |
| HOU | Houston | Rockets | West | Southwest |
| IND | Indiana | Pacers | East | Central |
| LAC | LA | Clippers | West | Pacific |
| LAL | Los Angeles | Lakers | West | Pacific |
| MEM | Memphis | Grizzlies | West | Southwest |
| MIA | Miami | Heat | East | Southeast |
| MIL | Milwaukee | Bucks | East | Central |
| MIN | Minnesota | Timberwolves | West | Northwest |
| NOP | New Orleans | Pelicans | West | Southwest |
| NYK | New York | Knicks | East | Atlantic |
| OKC | Oklahoma City | Thunder | West | Northwest |
| ORL | Orlando | Magic | East | Southeast |
| PHI | Philadelphia | 76ers | East | Atlantic |
| PHX | Phoenix | Suns | West | Pacific |
| POR | Portland | Trail Blazers | West | Northwest |
| SAC | Sacramento | Kings | West | Pacific |
| SAS | San Antonio | Spurs | West | Southwest |
| TOR | Toronto | Raptors | East | Atlantic |
| UTA | Utah | Jazz | West | Northwest |
| WAS | Washington | Wizards | East | Southeast |

**关于城市名的特别说明：**
- LAC（Clippers）使用 "LA" 而非 "Los Angeles" 以区分 LAL（Lakers），这符合 NBA 官方惯例。
- GSW 使用 "Golden State" 而非 "San Francisco"，符合官方名称。
- NOP 使用 "New Orleans"（而非 "New Orleans/Oklahoma City" 等历史名称）。

### 顶层 metadata

```json
{
  "source_name": "NBA.com official public team pages",
  "source_url": "https://www.nba.com/teams",
  "as_of_date": "2026-06-25",
  "manual_review_required": true
}
```

## 6. manifest / source_manifest 更新说明

### manifest.json

- `source_name` 更新为 "NBA.com official public team pages"（与 teams.json 一致）
- `source_url` 更新为 `https://www.nba.com/teams`（从 null 改为公开 URL）
- `source_pack_version` 更新为 `m10-c1-v1`
- `teams` 数组从空 `[]` 更新为 30 个 `nba-XXX` ID
- `description` 更新为反映 teams-only 数据
- `limitations` 更新为明确列出不含 roster/contract/salary/logo

### source_manifest.json

per_file_sources 使用 **`normalized/teams.json`**（相对于 snapshot 根目录的路径，带 `normalized/` 前缀）而非 `teams.json`。这样做的原因：

1. 与 file_hashes 保持路径一致性（都用相对 snapshot 根目录的路径）
2. 未来如果有 `teams.json` 在其他层级（如 `raw/`），可以避免 key 冲突
3. 路径语义清晰，loader 可以直接拼接 snapshot_dir + key 找到文件

具体更新：
- `schema_version` 保持 `m10-b-v1`（schema 未变，只是填了数据）
- `source_name`/`source_url` 更新为 NBA.com teams page
- `license_notes` 更新为说明 team identity 是公开事实信息，不包含 logo/player/contract/salary
- `freshness_label` 更新为 "Pre-offseason team list (as of 2026-06-25)"
- `freshness_level` 保持 `frozen`（不是 live）
- `live_eligible` 保持 `false`
- `stale_after_date` 保持 `null`
- `data_freshness_warning` 更新为说明当前包含 30 队 team identity，不包含 roster/contract/salary/logo
- `data_categories` 从 `[]` 更新为 `["teams"]`
- `per_file_sources` 新增 `normalized/teams.json` 条目，包含 source_name/source_url/as_of_date
- `file_hashes` 新增 `normalized/teams.json` 的 SHA-256
- `validation_status` 保持 `provisional`（数据仅为 teams，不是完整 snapshot）
- `allowed_usage`/`redistribution_notes` 保持非商业演示 / source review 语义
- `created_by`/`reviewed_by` 更新为 m10-c1

### manual_review_required 一致性

`manual_review_required` 在三个文件中均为 `true`：
- `manifest.json` — const: true（由 real_snapshot_manifest_schema 强制）
- `source_manifest.json` — true
- `normalized/teams.json` — const: true（由 teams_schema 强制）

## 7. 不含 logo / colors / roster / contracts / salaries

M10-C1 严格禁止以下内容：

- **Logo 文件：** 无 .png/.svg/.webp 文件；schema 禁止 logo_path/logo_url/official_logo/nba_logo/team_logo/mascot_image 字段
- **Colors：** 无 primary_color/secondary_color/colors 字段；M10-C2 才考虑 safe colors 方案
- **Roster/players：** 无 roster/players 字段；无球员名单
- **Contracts/salaries/cap sheets：** 无 contracts/salaries/cap_sheet 字段；无合同/薪资/cap 数据
- **Free agents / draft assets：** 本 snapshot 中暂无相关文件
- **额外 normalized 数据文件：** 只新增了 teams.json，无其他 normalized/*.json

前端展示未来只能使用 abbreviation badge（三字母缩写）+ fallback color，不能使用真实 NBA logo 或官方配色。

## 8. M9 安全边界不变

M10-C1 不改变 M9 确立的任何安全边界：

- **不自动执行交易：** 无 execute/apply/commit/mutate/write/persist/save/delete/update/submit 字段或 endpoint
- **不自动签约：** 同上，无 auto_execute/auto_approve
- **不新增 mutation endpoint：** 不改 backend API
- **不接真实 LLM：** 不调用 LLM API
- **不接真实 NBA API：** 数据来自公开事实信息，非 API 调用；source_url 仅为引用页
- **不破坏 natural-language-preview safety gate：** 不改 preview/gate 逻辑
- **不改变 human approval：** manual_review_required 始终为 true
- **demo mode 默认：** 不改 demo snapshot；real_snapshot mode 必须显式启用（未来 loader 实现时）

## 9. 测试说明

`backend/app/tests/test_m10c_team_metadata.py` 包含 62 个测试用例，分为三类：

### 正向测试（20 个）

- `teams.json` 通过 `teams_schema.json` 校验
- teams 数量 = 30
- team_id 唯一
- abbreviation 唯一
- conference 仅含 East/West，且两者都存在
- division 仅含 6 个合法 division，且全部存在
- 每个 team object 字段集恰好为 {team_id, city, name, abbreviation, conference, division}
- 30 个预期 team_id 全部存在（无缺失、无多余）
- `manifest.json` 通过 `real_snapshot_manifest_schema.json`
- `source_manifest.json` 通过 `source_manifest_schema.json`
- source_manifest.data_categories 包含 "teams"
- source_manifest.per_file_sources 包含 "normalized/teams.json" 键
- source_manifest.file_hashes 包含 "normalized/teams.json" 键
- teams.json 实际 SHA-256 与 file_hashes 记录一致
- manifest.teams 数组有 30 个条目
- manifest.teams 与 teams.json 中 team_id 集合一致
- live_eligible 保持 false
- freshness_level 保持 frozen
- 三个文件（teams.json, source_manifest.json, manifest.json）中 manual_review_required 均为 true

### 负向测试（22 个）

- 缺 team_id → 失败
- abbreviation 小写（"gsw"）→ 失败
- conference = "North" → 失败
- division = "Midwest" → 失败
- 6 个 logo 字段在 team 级别 → 失败（参数化）
- 6 个 logo 字段在顶层 → 失败（参数化）
- 3 个 color 字段（primary_color, secondary_color, colors）→ 失败（参数化）
- 5 个 roster/contract/salary 字段 → 失败（参数化）
- team 级别额外字段 → 失败
- 顶层额外字段 → 失败
- manual_review_required = false → 失败
- teams 数量 29（少一个）→ 失败
- teams 数量 31（多一个）→ 失败
- team_id 格式错误（"ATL" 缺少 "nba-" 前缀）→ 失败
- sample_data = true → 失败（顶层不允许 sample_data 字段）

### 回归测试（20 个，含 M10-B 原有）

M10-C1 测试文件内：
- demo snapshot 8 个文件存在
- demo snapshot 文件集合未变化
- demo manifest 仍通过 real_snapshot_manifest_schema.json
- 更新后的 real snapshot source_manifest 和 manifest 仍通过 M10-B schema

M10-C1 要求运行时同时执行 M10-B 原有的 48 个测试（确保不回归），合计 **110 个测试**。

## 10. 后续 M10-C2 才考虑 colors

M10-C2（后续里程碑）才考虑 team visual metadata：

- 评估 safe/neutral color palette（不直接使用 NBA 官方精确色值）
- abbreviation badge 渲染规范（三字母 + 安全 fallback 色）
- 仍然禁止真实 logo 文件
- colors 字段加入 teams_schema 前需要单独的 design review + 品牌风险评估
- colors 加入前 schema 需要更新版本号并添加 review gate

M10-C1 完成后，下一合理步骤可能是：
- M10-C2：safe team colors + abbreviation badge 规范（不含 logo）
- 或 M10-D：roster/player identity schema（不含真实 stats/contracts）
- 或 M10-E：contract/salary schema（接真实 salary 数据源前先定义 schema）

具体顺序由 design gate 决定，不在 C1 范围内。
