# M10-B Real Snapshot Schema + source_manifest Schema

> M10-B 定义 curated real NBA snapshot 的 schema 和 placeholder fixture，为后续 M10-C（30 队 metadata seed）到 M10-H（final handoff）提供契约基础。M10-B 只做 schema/docs/fixture/test，不导入真实 NBA 数据，不改 loader，不改前端，不改 API。

**Date:** 2026-06-27
**Baseline:** HEAD `b8f596d` (tag `m10a-real-data-team-branding-review-patch`)
**Scope:** Schema definitions + placeholder fixture + schema validation tests. No frontend, no backend business logic, no data import, no logo files. No commit/tag/push.

---

## 1. M10-B 目标

M10-B 的核心目标是为未来真实 NBA snapshot 定义 **schema 契约**，使得后续 milestone（M10-C 到 M10-G）在导入数据时有明确的字段、类型、枚举、禁止项约束。

M10-B **不做**：

- ❌ 不导入真实 NBA 球员名单
- ❌ 不导入真实合同/薪资数据
- ❌ 不导入真实 cap sheet
- ❌ 不修改 `snapshot_loader.py` 或任何 loader 代码
- ❌ 不修改 backend API 端点
- ❌ 不修改 frontend 组件
- ❌ 不添加真实球队 logo 文件
- ❌ 不修改 demo snapshot 目录中的任何文件

M10-B **做**：

- ✅ 定义 `source_manifest.json` 的 JSON Schema（来源、freshness、授权、validation 治理）
- ✅ 定义 `manifest.json` 对 curated real snapshot 的 JSON Schema 扩展（向后兼容）
- ✅ 创建 placeholder fixture（空的 real snapshot 目录骨架，仅含 metadata，无真实数据）
- ✅ 编写 schema 正向/负向自校验测试
- ✅ 验证 demo snapshot 目录未被修改

---

## 2. 与 M10-A 的关系

M10-B 落实 M10-A Design Gate（含 GLM-5.2 Review Patch）的以下约束：

| M10-A 章节 | M10-B 落实 |
|------------|-----------|
| Section 5：source_manifest 设计 | `schema/source_manifest_schema.json` 定义全部基础字段 |
| Section 15.2：Demo snapshot 身份锁定 | Placeholder fixture 不触碰 demo 目录；测试验证 demo 文件未被修改 |
| Section 15.3：Freshness 治理字段 | `freshness_level`/`stale_after_date`/`live_eligible`/`freshness_policy`/`data_freshness_warning` 全部在 schema 中 |
| Section 15.4：source_manifest 必补字段 | `schema_version`/`data_categories`/`per_file_sources`/`allowed_usage`/`redistribution_notes`/`file_hashes`/`reviewed_by`/`review_date`/`freshness_policy`/`manual_review_required` 全部在 schema 中 |
| Section 15.5：Freshness 禁止文案 | schema 禁止 `current_roster`/`live_salaries`/`latest_data`/`live_data`/`current_salaries`/`real_time_data` 字段名 |
| Section 15.6：Real snapshot 缺失/损坏 hard error | schema 定义了 structural validity；hard error 行为将由未来 loader 实现，M10-B 只定义契约 |
| Section 15.7：agent_trace/intelligence_summary 数据来源 | schema 中的 `data_freshness_warning`/`snapshot_id`/`as_of_date`/`freshness_label` 为 trace/summary 提供数据源 |
| Section 15.8：Loader 不得写 demo 目录 | 测试验证 demo snapshot 文件集合未变化 |
| Section 15.9：Logo/branding 防线 | schema 禁止 `logo_path`/`logo_url`/`official_logo`/`nba_logo`/`team_logo`/`mascot_image` 字段 |
| Section 15.10：M9 安全边界补充 | schema 禁止 execute/apply/commit/mutate/write/persist/save/delete/update/submit/auto_execute/auto_approve 字段；`live_eligible` 恒为 `false` |

---

## 3. 文件结构

M10-B 新增以下文件：

```
schema/
├── source_manifest_schema.json           # source_manifest.json 的 JSON Schema (Draft 2020-12)
└── real_snapshot_manifest_schema.json    # manifest.json 对 curated real snapshot 的 Schema 扩展

data/snapshots/
└── nba_real_2026_preoffseason_v1/
    ├── source_manifest.json              # Placeholder（无真实数据，仅 metadata）
    └── manifest.json                     # Placeholder（空 teams/limitations，无 normalized/ 数据文件）

backend/app/tests/
└── test_m10_real_snapshot_schema.py      # Schema 正向/负向/回归测试（48 tests）

docs/
└── m10-b-real-snapshot-schema.md         # 本文档
```

**两个 schema 文件的设计决策：**

`source_manifest_schema.json` 和 `real_snapshot_manifest_schema.json` 保持为两个独立文件，原因是：
- `manifest.json` 是 M8 以来就存在的快照元数据文件，所有 snapshot（demo/historical/test/real）都有，需要保持向后兼容。
- `source_manifest.json` 是 M10 新增的来源治理文件，专注于 license/freshness/validation/per-file sources，是 manifest 的治理扩展。
- 两者职责不同：manifest 描述"这是什么数据"，source_manifest 描述"数据从哪来、能否信任、有多新鲜、如何合法使用"。
- 分离后，未来 demo snapshot 如果要添加 source_manifest 也可以独立添加，不影响现有 manifest 解析逻辑。

---

## 4. source_manifest Schema 字段表

### 4.1 source_manifest_schema.json 字段总表

| 字段 | 类型 | 必填 | 示例值 | 用途 |
|------|------|------|--------|------|
| `snapshot_id` | string | ✅ | `"nba_real_2026_preoffseason_v1"` | 唯一快照标识，匹配目录名 |
| `schema_version` | string | ✅ | `"m10-b-v1"` | source_manifest schema 版本 |
| `season` | string (YYYY-YYYY) | ✅ | `"2025-2026"` | 赛季标识 |
| `snapshot_type` | enum | ✅ | `"curated_real"` | 快照类型，枚举值：`curated_real`/`demo`/`historical_source_backed`/`test_fixture`。禁止 `live`/`realtime` |
| `as_of_date` | string (YYYY-MM-DD) | ✅ | `"2026-06-25"` | 数据截止日期 |
| `generated_at` | string (ISO 8601) | ✅ | `"2026-06-27T00:00:00Z"` | 快照生成时间 |
| `source_name` | string | ✅ | `"Spotrac 2025-26 contract/cap table"` | 主要数据来源名称 |
| `source_url` | string \| null | ❌ | `"https://..."` \| `null` | 来源 URL（如有公开页面） |
| `source_reference` | string \| null | ❌ | `null` | 来源参考（无 URL 时） |
| `license_notes` | string | ✅ | `"Publicly available data..."` | 许可和使用条款说明 |
| `freshness_label` | string | ✅ | `"Pre-offseason freeze (as of 2026-06-25)"` | 人类可读的新鲜度标签 |
| `freshness_level` | enum | ✅ | `"frozen"` | 新鲜度等级：`frozen`/`stale`/`active_snapshot`/`archived`。**禁止 `live`** |
| `freshness_policy` | string | ✅ | `"Static curated snapshot; no auto-refresh..."` | 解释为什么不是 live/current |
| `live_eligible` | boolean (const:false) | ✅ | `false` | 是否可称为 live/current。**M10 恒为 false** |
| `stale_after_date` | string \| null | ❌ | `null` \| `"2026-09-01"` | 过期日期；过期后 UI 显示 stale warning |
| `data_freshness_warning` | string | ✅ | `"This snapshot reflects...not live data."` | 可直接给 UI/trace/summary 引用的警告文案 |
| `limitations` | string[] | ✅ | `["Not live data", "Manual review required"]` | 数据局限性列表 |
| `data_categories` | enum[] | ✅ | `[]` \| `["teams", "contracts"]` | 包含的数据类别：teams/players/rosters/contracts/cap_config/cap_sheets/free_agents/draft_assets/evidence_notes。placeholder 可为空数组 |
| `per_file_sources` | object | ✅ | `{}` | 每个文件的独立来源记录（teams/contracts 可能来自不同来源）。placeholder 可为空对象 |
| `allowed_usage` | string | ✅ | `"Non-commercial demonstration..."` | 允许的使用方式 |
| `redistribution_notes` | string | ✅ | `"Data derived from publicly available sources..."` | 再分发限制（GitHub 发布用） |
| `file_hashes` | object | ✅ | `{}` | 每个 normalized 文件的 SHA-256 hash（防篡改）。placeholder 可为空对象 |
| `created_by` | string | ✅ | `"m10-curated-import-v1"` | 创建者标识 |
| `validation_status` | enum | ✅ | `"provisional"` | 验证状态：`provisional`/`partially_validated`/`validated` |
| `replaces_snapshot_id` | string \| null | ❌ | `null` | 前一版本 snapshot_id |
| `reviewed_by` | string | ✅ | `"m10-b-schema-gate"` | 审核者标识 |
| `review_date` | string (YYYY-MM-DD) | ✅ | `"2026-06-27"` | 审核日期 |
| `manual_review_required` | boolean | ✅ | `true` | 是否需人工复核；必须与 manifest.json 保持一致 |

### 4.2 负向约束（schema 自动拒绝）

Schema 通过 `additionalProperties: false` 和 `propertyNames` 黑名单实现以下字段名禁止：

**执行/变更动词字段（禁止）：**
`execute`, `apply`, `commit`, `mutate`, `write`, `persist`, `save`, `delete`, `update`, `submit`, `auto_execute`, `auto_approve`

**Live/current 暗示字段（禁止）：**
`current_roster`, `live_salaries`, `latest_data`, `live_data`, `current_salaries`, `real_time_data`

**Logo/branding 字段（禁止）：**
`logo_path`, `logo_url`, `official_logo`, `nba_logo`, `team_logo`, `mascot_image`

此外：
- `live_eligible` 只能是 `false`（`const: false`）
- `freshness_level` 枚举中不包含 `live`
- `snapshot_type` 枚举中不包含 `live` 或 `realtime`

### 4.3 real_snapshot_manifest_schema.json 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `snapshot_id` | string | ✅ | 唯一标识 |
| `snapshot_type` | enum | ✅ | 禁止 live/realtime |
| `season` | string | ✅ | 赛季 YYYY-YYYY |
| `source_name` | string | ✅ | 主要来源名称 |
| `source_url` | string \| null | ❌ | 来源 URL |
| `source_pack_version` | string \| null | ❌ | source pack 版本 |
| `as_of_date` | string (YYYY-MM-DD) | ✅ | 数据截止日期 |
| `generated_at` | string | ✅ | ISO 8601 生成时间 |
| `sample_data` | boolean | ✅ | 是否为样例数据 |
| `manual_review_required` | boolean (const:true) | ✅ | 所有 curated real snapshot 必须为 true |
| `teams` | string[] | ✅ | 队 ID 列表（格式 `nba-[A-Z]{3}`）；placeholder 可为空 |
| `description` | string | ❌ | 描述文本 |
| `limitations` | string[] | ✅ | 局限性列表 |

---

## 5. manifest.json 与 source_manifest.json 的关系

两个文件共存于每个 snapshot 目录，职责分离：

| 维度 | manifest.json | source_manifest.json |
|------|---------------|---------------------|
| 存在时间 | M8 以来一直存在 | M10 新增 |
| 核心职责 | 描述"这是什么数据"（ID、类型、赛季、队列表） | 描述"数据从哪来、能否信任、有多新鲜、如何合法使用" |
| 字段特点 | 保持向后兼容，不删除旧字段 | 治理扩展：license/freshness/per-file sources/hashes/review |
| 消费者 | snapshot_loader、snapshot_validator（现有逻辑） | 未来 loader、UI freshness display、agent_trace、intelligence_summary |
| 对 demo snapshot | 已有，格式不变 | 未来可选添加（M10 不修改 demo snapshot） |
| 对 real snapshot | 必须有，符合 real_snapshot_manifest_schema | 必须有，符合 source_manifest_schema |

**一致性约束：**

- `snapshot_id` 必须一致
- `season` 必须一致
- `as_of_date` 必须一致
- `manual_review_required` 必须一致（两个文件中都是 `true`）
- `snapshot_type` 必须使用同一枚举值

现有 demo snapshot 的 manifest.json 不需要修改。它的字段已经满足 real_snapshot_manifest_schema 的必填约束，向后兼容。

---

## 6. snapshot_mode / snapshot_role 约定

M10-A Section 15.2 已锁定，M10-B 重申：

- **`snapshot_type` / `sample_data`** 描述的是**数据来源性质**（这个数据是 demo 还是 curated real，是否来自样例）。
- **`snapshot_mode`** 描述的是**应用运行模式**（系统当前以 demo 还是 real 模式运行）。
- 二者**不是同一个字段，不要混用**。一个 snapshot 可以 `sample_data=false` 但同时被作为 demo mode 的数据实例加载。

**模式规则（M10-B 定义契约，不修改 loader）：**

| 规则 | 说明 |
|------|------|
| Demo mode 永远默认 | 系统启动默认加载 demo snapshot（现有 GSW+PHX historical/source-backed snapshot） |
| Real mode 显式启用 | 切换到 real_snapshot mode 需要显式操作（环境变量/URL 参数/UI 切换器，M10-D 决定） |
| Demo 不被覆盖 | real snapshot 不修改 demo snapshot 目录的任何文件 |
| Loader 未来返回 snapshot_mode | M10-B 只定义契约，不改 loader；未来 loader 加载后返回 `snapshot_mode` 字段 |
| 当前 demo mode 继续使用现有 snapshot | `data/snapshots/nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25/` 继续作为 demo mode 的数据实例 |

M10-B 不改 loader 代码，只定义接口契约。loader 修改在 M10-C 或之后按需进行。

---

## 7. Real Snapshot 缺失/损坏行为

M10-A Section 15.6 已锁定。M10-B 定义 schema 层面的结构有效性契约。未来 loader 实现时必须遵守：

- 如果用户显式启用 real_snapshot mode，但 real snapshot **缺失、损坏、或 schema 不匹配**，系统必须 **hard error**。
- **不允许静默 fallback 到 demo mode**——因为静默 fallback 会让用户以为看到真实数据，实际看到 demo。
- 错误响应必须明确说明：real snapshot 不可用（缺失/损坏/schema 不匹配），提示用户切回 demo mode 或修复 real snapshot。
- 错误响应中不得出现 demo 数据内容，不得假装成功。

M10-B 的 schema validation 测试确保：当 source_manifest 或 manifest 不符合 schema 时，结构性校验会失败，为未来 loader 的 hard error 行为提供基础。

---

## 8. Freshness 防误导

所有 real snapshot 必须通过 schema 强制要求以下 freshness 字段：

- **`as_of_date`**：数据截止日期（必填）
- **`freshness_label`**：人类可读的新鲜度标签（必填）
- **`data_freshness_warning`**：可直接给 UI/trace/summary 引用的警告文案（必填）
- **`freshness_level`**：新鲜度等级枚举，禁止 `live`（必填）
- **`live_eligible`**：恒为 `false`（const 约束）
- **`stale_after_date`**：过期日期（可选，过期后 UI 须显示 stale warning）
- **`freshness_policy`**：解释为什么不是 live/current（必填）

**禁止文案（中英文，适用于 UI/agent_trace/intelligence_summary/demo 话术/reviewer 文档）：**

| ❌ 英文禁止 | ❌ 中文禁止 |
|------------|------------|
| current roster | 最新阵容 |
| live salaries | 当前薪资 |
| latest NBA data | 最新 NBA 数据 |
| real-time data | 实时数据 / 今日数据 |
| up-to-date | 截至目前最新 |
| executed/applied/committed | 已落地/已生效 |
| current lineup | 当前名单/现役实时阵容 |

以上字段名也被 schema 的 `propertyNames` 黑名单直接禁止，无法出现在 source_manifest 或 manifest 中。

---

## 9. Logo / Branding 防线

Schema 层面的品牌/商标防线：

1. **不允许 logo 字段名**：`logo_path`、`logo_url`、`official_logo`、`nba_logo`、`team_logo`、`mascot_image` 被 schema `propertyNames` 黑名单直接禁止。
2. **不创建 logo 文件**：M10-B 不添加任何 .png/.svg/.webp logo 资产文件。
3. **Placeholder fixture 不含 visual metadata**：M10-B 的 placeholder 甚至不含 team color 数据，M10-C 才会引入 teams metadata（含 abbreviation/colors，不含 logo）。
4. **未来 team metadata 策略**：M10-C 及之后只能做 abbreviation badge / fallback badge / color stripe，不使用真实 logo；team color 仅作为非官方 UI 区分色；不复制官方字体、不复制官方视觉系统、不做 logo grid、不使用 mascot 插画。
5. **未来真实 logo 前提**：若 owner 提供真实 logo，必须随附 license 文件（grantor/scope/term/territory/allowed_usage/no official endorsement）。

---

## 10. M9 安全边界

M10-B 不修改任何已封口的安全边界。Schema 层面额外强化：

| 安全边界 | M10-B 保障方式 |
|----------|---------------|
| 不自动执行交易 | schema 禁止 execute/apply/commit/mutate/write 字段名；无 execute 端点 |
| 不自动执行签约 | 同上；preview-only 原则不变 |
| 不新增 execute/apply/commit/mutate/write endpoint | M10-B 不修改 API；schema 禁止变更动词字段名 |
| 不接真实 LLM | M10-B 不涉及任何 LLM 代码；无新增网络库依赖 |
| 不接真实 NBA API | M10-B 是 schema/docs，无网络调用；placeholder 不含真实数据 |
| 不破坏 natural-language-preview safety gate | M10-B 不修改分类器、安全门或 orchestrator |
| 不改变 human approval | M10-B 不修改 requires_human_approval 逻辑 |
| 不修改 demo snapshot | 测试验证 demo 文件集合未变化 |
| live_eligible 恒为 false | schema `const: false` 强制 |
| snapshot_type 不得为 live/realtime | schema enum 限制 + propertyNames 黑名单 |

---

## 11. 测试说明

测试文件：[test_m10_real_snapshot_schema.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/tests/test_m10_real_snapshot_schema.py)

运行命令：

```powershell
D:\anaconda\python.exe -m pytest backend/app/tests/test_m10_real_snapshot_schema.py -v
```

### 正向测试（7 个）

| 测试 | 验证内容 |
|------|---------|
| `test_placeholder_source_manifest_passes` | Placeholder source_manifest.json 通过 schema 校验 |
| `test_placeholder_real_manifest_passes` | Placeholder manifest.json 通过 schema 校验 |
| `test_live_eligible_false_passes` | `live_eligible=false` 通过 |
| `test_freshness_level_enum_passes[frozen/stale/active_snapshot/archived]` | 四个合法 freshness_level 值全部通过（参数化，4 个用例） |

### 负向测试（26 个）

| 测试 | 验证内容 |
|------|---------|
| `test_missing_required_field_fails` | 缺少必填字段（snapshot_id）失败 |
| `test_live_eligible_true_fails` | `live_eligible=true` 被 const 约束拒绝 |
| `test_freshness_level_live_fails` | `freshness_level="live"` 被 enum 拒绝 |
| `test_snapshot_type_live_or_realtime_fails_source_manifest[live/realtime]` | snapshot_type=live/realtime 被 enum 拒绝（source_manifest，2 个用例） |
| `test_snapshot_type_live_or_realtime_fails_real_manifest[live/realtime]` | snapshot_type=live/realtime 被 enum 拒绝（manifest，2 个用例） |
| `test_execution_field_name_fails[execute/apply/commit/mutate/write/persist/save/delete/update/submit/auto_execute/auto_approve]` | 12 个执行/变更动词字段名被 propertyNames 黑名单拒绝（12 个用例） |
| `test_logo_field_name_fails[logo_path/logo_url/official_logo/nba_logo/team_logo/mascot_image]` | 6 个 logo 字段名被 propertyNames 黑名单拒绝（6 个用例） |
| `test_live_current_field_name_fails[current_roster/live_salaries/latest_data/live_data/current_salaries/real_time_data]` | 6 个 live/current 字段名被 propertyNames 黑名单拒绝（6 个用例） |
| `test_manual_review_required_false_fails_real_manifest` | real manifest 中 `manual_review_required=false` 被 const 拒绝 |

### 回归测试（9 个）

| 测试 | 验证内容 |
|------|---------|
| `test_demo_snapshot_file_exists_and_readable[...]` | 8 个 demo snapshot 文件存在且可读（8 个用例） |
| `test_demo_snapshot_file_count_unchanged` | demo snapshot 目录文件集合未变化（没有新增/删除/重命名文件） |

**总计：48 个测试用例，全部通过。**

---

## 12. 封口标准

M10-B 封口需满足：

- [x] `schema/source_manifest_schema.json` 覆盖 M10-A Section 5 + Section 15 全部字段
- [x] `schema/real_snapshot_manifest_schema.json` 定义 curated real manifest 格式，向后兼容
- [x] Placeholder fixture 存在且通过 schema 校验（无真实 NBA 数据）
- [x] 48 个 schema 测试全部通过
- [x] Demo snapshot 目录文件集合未变化
- [x] 未修改 frontend/backend API/loader 代码
- [x] 未添加 logo 文件
- [x] 文档覆盖全部 11 个要求章节

通过 M10-B 后，建议进入 M10-C（30 队 team metadata seed，不含 logo）。
