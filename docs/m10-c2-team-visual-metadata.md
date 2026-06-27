# M10-C2: Safe Team Visual Metadata

## 1. M10-C2 目标

M10-C2 在 M10-C1 的 30 队 team identity 数据基础上，新增**非官方 UI accent visual metadata**，用于未来 abbreviation badge / neutral badge / UI 区分色渲染。

M10-C2 提供：
- 独立的 `normalized/team_visual_metadata.json` 文件（不塞在 teams.json 里）
- 每个队的 accent_color / secondary_accent_color（hex #RRGGBB）
- badge_style 提示（abbreviation_badge / neutral_badge / conference_badge）
- 每个条目和顶层的 `no_official_branding: true` 标志
- 每个条目和顶层的 `source_name: "manual non-official UI accent palette"` 标志

M10-C2 **明确不提供**：
- 真实 NBA 或球队 logo 文件
- 官方球队颜色 / brand colors / Pantone 色值
- 官方品牌手册数据
- roster / players / contracts / salaries / cap sheets

## 2. 为什么不改 teams.json

GPT-5.5 在 M10-C1 Review + M10-C2 Design Gate 中明确建议：

1. **职责分离原则**：`teams.json` 是公开事实性 team identity（team_id/city/name/abbreviation/conference/division），visual metadata 是人工选择的 UI 调色板，二者数据来源和语义不同。
2. **避免文件耦合**：identity 数据相对稳定（联盟扩军/搬迁才会变），但 visual palette 未来可能根据 UI 设计需求迭代调整，独立文件可以独立更新、独立 hash 校验。
3. **品牌安全边界**：把颜色数据放在独立文件并显式标注 `no_official_branding: true`，比在 teams.json 里加颜色字段更容易在 schema 层和 reviewer 层明确区分"事实数据"和"UI 派生数据"。
4. **Loader 按需加载**：未来 loader 可以选择只加载 teams.json（identity only），也可以加载 visual metadata 用于 UI 渲染，不需要加载所有字段。

因此 M10-C2 新增独立文件 `normalized/team_visual_metadata.json`，不修改 `normalized/teams.json`。

## 3. 为什么新建 team_visual_metadata.json

独立文件的设计要点：

- **顶层有 `no_official_branding: true`** — 显式否认官方背书
- **顶层 `source_name` 固定为 `"manual non-official UI accent palette"`** — schema 用 `const` 强制
- **每个 entry 同样带 `no_official_branding: true` 和 `source_name`** — 单条级别也可以独立审计
- **使用 `accent_color` / `secondary_accent_color` 命名** — 明确是 UI accent，不是 primary/secondary brand colors
- **字段命名禁止 primary_color / secondary_color / brand_color / official_color / pantone / brand_guidelines**
- **Schema 在顶层和 entry 级别双重 `additionalProperties: false` + `propertyNames` 黑名单**

## 4. non-official UI accent colors 的定义

"non-official UI accent color" 的语义：

- 这是**手动选择的 UI 界面区分色**，用于 abbreviation badge 的背景色或边框色，帮助用户在列表/对比视图中快速区分不同球队。
- 这些颜色**大致接近球迷对球队的普遍色彩认知**（Boston 偏绿、LA Lakers 偏紫/金等），便于认知。
- 这些颜色**不是**官方品牌色值，**不是**从官方品牌手册或 Pantone 规格中提取的精确色值，**不**代表 NBA 或球队官方认可。
- 这些颜色**只用于 UI 区分**，不用于商品、不用于官方素材、不用于任何暗示 NBA/球队背书的场景。
- 如果未来需要精确的品牌色（目前不需要），必须经过单独的品牌/法务评审，且必须放在不同的文件/字段中，不能复用 accent_color。

## 5. 为什么不叫 official colors / brand colors

命名选择的考量：

| 禁止命名 | 原因 |
|----------|------|
| `primary_color` / `secondary_color` | 暗示官方品牌 primary/secondary 色 |
| `brand_color` / `official_color` | 直接声称品牌/官方来源 |
| `pantone` | Pantone 是商标，且是精确色彩规格体系 |
| `brand_guidelines` | 引用官方品牌手册 |
| `official_colors` / `brand_colors` | 复数形式同样暗示官方/品牌 |

使用 `accent_color` / `secondary_accent_color` 配合 `no_official_branding: true`，语义上明确是 UI 辅助色，不是品牌资产声明。

## 6. 新增 schema 字段说明

### 顶层字段 (`schema/team_visual_metadata_schema.json`)

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `visual_metadata` | array | 是 | minItems=30, maxItems=30 | 30 个 team visual 条目 |
| `source_name` | string | 是 | const: "manual non-official UI accent palette" | 显式声明来源是手动非官方调色板 |
| `as_of_date` | string | 是 | pattern YYYY-MM-DD | 调色板定义日期 |
| `manual_review_required` | boolean | 是 | const: true | 必须人工审核 |
| `no_official_branding` | boolean | 是 | const: true | 显式否认官方背书/品牌 |

### team visual entry 字段

| 字段 | 类型 | 必填 | 约束 | 说明 |
|------|------|------|------|------|
| `team_id` | string | 是 | pattern `^nba-[A-Z]{3}$` | 必须对应 teams.json 中的 team_id |
| `abbreviation` | string | 是 | pattern `^[A-Z]{3}$` | 必须对应 teams.json 中的 abbreviation |
| `accent_color` | string | 是 | pattern `^#[0-9A-Fa-f]{6}$` | 主要 UI accent 色（非官方） |
| `secondary_accent_color` | string | 是 | pattern `^#[0-9A-Fa-f]{6}$` | 次要 UI accent 色（非官方） |
| `badge_style` | string | 是 | enum: abbreviation_badge / neutral_badge / conference_badge | Badge 渲染提示 |
| `source_name` | string | 是 | const: "manual non-official UI accent palette" | 每条独立标注来源 |
| `as_of_date` | string | 是 | pattern YYYY-MM-DD | 每条独立标注日期 |
| `manual_review_required` | boolean | 是 | const: true | 每条独立标注审核要求 |
| `no_official_branding` | boolean | 是 | const: true | 每条独立否认官方背书 |

### 禁止字段（双层禁止）

**Logo/branding（11 个）：** logo_path, logo_url, official_logo, nba_logo, team_logo, mascot_image, official_branding, official_colors, brand_colors, pantone, brand_guidelines

**Color-naming traps（4 个）：** primary_color, secondary_color, brand_color, official_color

**Roster/data（5 个）：** roster, players, contracts, salaries, cap_sheet

**Execution verbs（12 个）：** execute, apply, commit, mutate, write, persist, save, delete, update, submit, auto_execute, auto_approve

**Live/current hints（6 个）：** current_roster, live_salaries, latest_data, live_data, current_salaries, real_time_data

`additionalProperties: false` 在顶层和 entry 级别同时生效，兜底拒绝所有未声明字段。

## 7. source_manifest 更新说明

### schema/source_manifest_schema.json
- `data_categories` items enum 增加 `"team_visual_metadata"`

### data/snapshots/nba_real_2026_preoffseason_v1/source_manifest.json
- `schema_version` 更新为 `m10-c2-v1`
- `source_name` 更新为复合来源（NBA.com public team pages + manual non-official palette）
- `license_notes` 增加 visual metadata 非官方声明
- `freshness_label` 更新为包含 non-official UI accent colors
- `data_freshness_warning` 更新为说明 accent colors 非官方、非 brand colors
- `limitations` 增加 3 条：visual metadata 使用 non-official UI accent colors、无 logo/official branding/Pantone、无官方背书
- `data_categories` 从 `["teams"]` 更新为 `["teams", "team_visual_metadata"]`
- `per_file_sources` 增加 `"normalized/team_visual_metadata.json"` 条目，source_name 为 "manual non-official UI accent palette"，source_url 为 null
- `file_hashes` 增加 team_visual_metadata.json 的 SHA-256
- `allowed_usage` 和 `redistribution_notes` 增加 accent colors 非官方声明
- `created_by` / `reviewed_by` 更新为 m10-c2
- `live_eligible` 保持 false
- `freshness_level` 保持 frozen
- `validation_status` 保持 provisional
- `manual_review_required` 保持 true

**per_file_sources 路径选择**：继续使用 `normalized/teams.json` 风格的相对 snapshot 根目录路径（带 `normalized/` 前缀），与 M10-C1 保持一致。

### manifest.json
- **不修改**。manifest.json 的 teams 数组已包含全部 30 个 team_id，visual metadata 通过 team_id 关联，不需要在 manifest 中新增字段。

## 8. 不含 logo / roster / contracts / salaries / cap sheet

M10-C2 严格禁止：

- **Logo 文件**：无 .png/.svg/.webp；schema 禁止所有 logo 字段名
- **Roster/players**：无 roster/players 字段；无球员名单
- **Contracts/salaries/cap sheets**：无 contracts/salaries/cap_sheet 字段；无合同/薪资/cap 数据
- **Free agents / draft assets**：无相关文件
- **Official branding / Pantone / brand guidelines**：schema 禁止字段名；source_manifest 文本中仅作为否定声明出现（"NOT official brand colors", "NOT Pantone specifications"）

未来 UI 只能使用：
- Abbreviation badge（三字母缩写 + accent_color 背景）
- Neutral fallback badge（当无 visual metadata 或需要降级时）
- Conference badge（东西部颜色区分）

## 9. M9 安全边界不变

M10-C2 不改变 M9 确立的任何安全边界：

- **不自动执行交易/签约**：无 execute/apply/commit/mutate/write 字段或 endpoint
- **不新增 mutation endpoint**：不改 backend API
- **不接真实 LLM**：不调用 LLM API
- **不接真实 NBA API**：visual metadata 是手动选择的 UI 调色板，非 API 数据
- **不破坏 natural-language-preview safety gate**：不改 preview/gate 逻辑
- **不改变 human approval**：manual_review_required 始终为 true
- **demo mode 默认**：demo snapshot 未被修改；real_snapshot mode 必须显式启用
- **不宣称 live/current/latest**：live_eligible=false, freshness_level=frozen

## 10. 测试说明

`backend/app/tests/test_m10c_team_visual_metadata.py` 包含测试用例，分为三类：

### 正向测试（18 个）
- team_visual_metadata.json 通过 schema
- visual_metadata 数量 = 30
- team_id 集合与 teams.json 完全一致
- 每个 abbreviation 与 teams.json 对应 team 匹配
- accent_color 全部为合法 #RRGGBB hex
- secondary_accent_color 全部为合法 #RRGGBB hex
- badge_style 全部在 enum 内
- manual_review_required 所有条目和顶层均为 true
- no_official_branding 所有条目和顶层均为 true
- source_name 所有条目和顶层均为 "manual non-official UI accent palette"
- as_of_date 所有条目和顶层均为 "2026-06-25"
- source_manifest.data_categories 包含 "team_visual_metadata"
- source_manifest.per_file_sources 包含 normalized/team_visual_metadata.json
- source_manifest.file_hashes 包含 normalized/team_visual_metadata.json
- SHA-256 hash 实际值与 source_manifest 记录一致
- source_manifest 通过更新后的 source_manifest_schema
- freshness 安全字段（live_eligible=false, freshness_level=frozen, validation_status=provisional, manual_review_required=true）

### 负向测试（32 个，含参数化）
- 缺 team_id → 失败
- team_id 格式错误（"ATL" 无 nba- 前缀）→ 失败
- abbreviation 格式错误（"xx" 小写+短）→ 失败
- accent_color 格式错误（"red", "#FFF"）→ 失败
- secondary_accent_color 格式错误（"rgb(0,0,0)"）→ 失败
- badge_style 非 enum → 失败
- no_official_branding=false（entry 级别）→ 失败
- no_official_branding=false（顶层）→ 失败
- manual_review_required=false（entry 级别）→ 失败
- manual_review_required=false（顶层）→ 失败
- 6 个 logo 字段在 entry 级别 → 失败（参数化）
- 6 个 logo 字段在顶层 → 失败（参数化）
- 5 个 branding 字段在 entry 级别（official_branding, official_colors, brand_colors, pantone, brand_guidelines）→ 失败（参数化）
- 5 个 branding 字段在顶层 → 失败（参数化）
- 4 个 color-naming 陷阱字段（primary_color, secondary_color, brand_color, official_color）→ 失败（参数化）
- 5 个 roster/contract/salary 字段 → 失败（参数化）
- 12 个 execution verb 字段 → 失败（参数化）
- 6 个 live/current 字段 → 失败（参数化）
- entry 级别额外字段 → 失败
- 顶层额外字段 → 失败
- visual_metadata 数量 29 → 失败
- visual_metadata 数量 31 → 失败
- Cross-reference: unknown team_id 语义检测
- Cross-reference: abbreviation 不匹配语义检测

### 回归测试（5 个，+ 既有测试）
- demo snapshot 8 个文件存在
- demo snapshot 文件集合未变化
- normalized/teams.json SHA-256 未变化（M10-C2 没有修改它）
- source_manifest 中 teams.json hash 仍然是 M10-C1 的值
- source_manifest 包含 non-official 免责声明和 no logos 声明
- M10-B 48 个测试全部通过
- M10-C1 62 个测试全部通过

合计 **205 个测试**（M10-B 48 + M10-C1 62 + M10-C2 95）。

## 11. 后续 M10-D 可使用 visual metadata，也必须支持 neutral fallback

后续里程碑（loader 实现、前端渲染）使用 visual metadata 时必须遵守：

1. **neutral fallback 必须支持**：当 visual metadata 缺失、hash 校验失败、或用户偏好 reduced color/grayscale 时，必须使用 neutral badge（灰底黑字或系统默认色），不得崩溃或显示错误。
2. **abbreviation 始终显示**：badge 核心是三字母缩写，accent color 只是辅助区分，不得只用色块无文字。
3. **no_official_branding 语义必须在 UI/intelligence_summary/agent_trace 中体现**：如果未来 UI 展示球队卡片，需要在合适位置（tooltip、about page、data source 说明）标注"colors are non-official UI accents, not NBA/team official colors"。
4. **不得将 accent_color 用于 logo 渲染**：颜色不能用于"着色"官方 logo 图片，因为根本不存在 logo 文件。
5. **M10-C2 不改 loader**：loader 对 team_visual_metadata.json 的加载和校验留待后续里程碑。
