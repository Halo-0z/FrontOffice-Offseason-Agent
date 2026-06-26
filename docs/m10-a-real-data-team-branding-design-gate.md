# M10-A Real NBA Data + Team Branding Expansion — Design Gate

> 本文档是 M10 新阶段的设计闸门文档（docs-only）。M10 不是 M9 的小补丁，而是一个引入真实 NBA 数据来源和 30 队展示的新阶段，需要在设计阶段就明确风险、边界、拆分路线和安全红线。本文档不包含任何代码变更、数据变更或 frontend/backend 修改。

**Date:** 2026-06-27
**Baseline:** HEAD `4051f12` (tag `m9f-agent-ux-final-handoff`)
**Scope:** Docs-only design gate. No code, no data, no frontend, no backend changes. No commit/tag/push.

---

## 1. M10 为什么是新阶段

M8/M9 阶段已完成的核心工作是 **preview-only Agent safety chain**：

- M8-E：后端 preview-only orchestrator、agent_trace、guardrails、human approval
- M9-A：deterministic/fake intelligence_summary（不接 LLM，不调网络）
- M9-B：自然语言意图分类器（signing/trade/hold/needs_clarification/blocked）
- M9-C：classify → safety gate → maybe preview 组合端点
- M9-D：前端 `/offseason` 自然语言输入入口（五状态 + error）
- M9-E：前端 smoke verification
- M9-F：Agent UX final handoff

M9 封口时的系统状态：
- 默认使用 demo/historical snapshot（GSW + PHX 两队）
- 只读 preview，保留 human approval
- 确定性规则引擎为事实来源，自然语言不覆盖 verdict
- 无 execute/apply/commit/mutate/write 端点

M10 要触碰的是 **真实 NBA 数据** 和 **30 队展示**，以及 **球队 branding（logo/队徽/颜色）**，这会引入两类 M9 阶段不存在的风险：

1. **Data freshness 风险**：真实数据有时效性。一旦引入"真实"标签，用户会自然假设数据是 current/live 的。如果数据是手工导入的静态 snapshot，必须明确标注 as_of_date 和 freshness_label，防止误导。
2. **Logo / 商标 / 授权风险**：NBA 球队 logo、队徽、昵称字体等视觉资产属于 NBA Properties 和各球队的商标/版权资产。未经授权将真实 logo 文件放入 repo 或在产品中展示，存在 IP 风险。

因此 M10 不能塞进 M9 Final Handoff 里当作一个小补丁，也不能直接跳到实现阶段——必须先过 Design Gate，把数据治理策略、来源元数据规范、双模式机制、branding 策略、milestone 拆分、安全边界全部写清楚。

---

## 2. M10 总原则

M10 遵循五条"先做/不做"原则，按优先级排列：

| # | 原则 | 说明 |
|---|------|------|
| 1 | **先做 snapshot，不做 live** | M10 所有真实数据都以 versioned snapshot 形式存在，不做 runtime 抓取、不做实时 API 调用、不做自动刷新。Live provider adapter 是未来阶段的事，不属于 M10-A/B。 |
| 2 | **先做 source metadata，不做大规模真实数据** | 在导入任何真实数据之前，先定义 source_manifest schema、freshness_label、license_notes、validation_status 等元数据字段，确保每个数据点都可追溯。 |
| 3 | **先做双模式，不覆盖 demo** | 永远保留 demo mode 作为默认模式；real_snapshot mode 必须显式启用。Demo 数据不被 real 数据覆盖，demo snapshot 目录不被修改或删除。 |
| 4 | **先做 freshness label，不宣称 current/live** | 所有真实 snapshot 必须在 UI 显著位置显示 data_mode、as_of_date、freshness_label、source_name。除非有可验证的授权来源 + 自动刷新机制 + 更新时间戳，否则禁止在任何文案中使用 "current roster"、"live salaries"、"latest NBA data" 等表述。 |
| 5 | **先做 abbreviation + fallback badge，不直接使用真实 NBA logo** | M10 早期不引入真实球队 logo 文件。球队视觉标识使用缩写徽章（abbreviation badge）、球队颜色条（color stripe）、文字 monogram 或 fallback badge。如果未来要使用真实 logo，必须由项目 owner 提供合法授权资产。 |

---

## 3. 数据分层设计

M10 定义四层数据架构，从下到上：

### Layer 1: Demo Snapshot（当前默认模式，永远保留）

- 路径：`data/snapshots/demo_offseason_v1/`（或沿用现有 `nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25/` 作为 demo snapshot 的具体实例）
- 用途：默认演示模式，M8/M9 已封口的所有功能基于此层
- 特点：
  - 永远可用，永远不被 real 数据覆盖
  - 包含 GSW + PHX 两队的 demo/historical 数据
  - 所有测试默认基于此层运行
  - `sample_data=true`（或当前 snapshot 的 `sample_data=false, manual_review_required=true` 标识，保持现状）
  - UI 必须显示 "演示数据 / Demo data" 标签

### Layer 2: Curated Real Snapshot（M10 核心目标）

- 路径：`data/snapshots/nba_real_2026_preoffseason_v1/normalized/`
- 用途：手工/合法来源导入的真实 NBA 数据 snapshot
- 特点：
  - 从公开可查、合法授权的来源手工整理（如 NBA.com 官方公开页面、Spotrac/Basketball Reference 等公开数据，遵循各站 robots.txt 和使用条款）
  - 每个 snapshot 附带 `source_manifest.json`，记录来源、日期、许可、限制
  - `manual_review_required=true`，所有合同/薪资数据标注 uncertainty note
  - 不包含未核验来源的 current roster 或 live 状态数据
  - M10-B 定义 schema，M10-E/F 逐步填充数据
  - UI 必须显示数据模式、日期、来源、freshness_label

### Layer 3: Versioned Real Snapshot

- 路径：每次更新创建新目录，如 `nba_real_2026_preoffseason_v2/`、`nba_real_2026_offseason_v1/`
- 用途：数据更新时不覆盖旧 snapshot，保留历史版本
- 特点：
  - 新版本 → 新目录，不修改旧目录内容
  - manifest 中包含 `replaces_snapshot_id` 字段指向前一版本
  - Loader 通过 snapshot_id 加载指定版本，默认加载最新 validated 版本
  - 支持回滚：如果新数据有问题，loader 配置可切回旧 snapshot_id
  - 旧 snapshot 目录保留，不删除

### Layer 4: Live Provider Adapter（未来阶段，不属于 M10-A/M10-B）

- 用途：未来如果接入实时数据 provider，必须通过 adapter 层
- 前置条件（全部满足才考虑）：
  - 有合法的数据授权/API key
  - 有 cache 策略（不每次请求都打 provider）
  - 有 rate limit 控制
  - 有 freshness policy（标注数据有多"新鲜"）
  - 有 fallback 到 snapshot 的机制
  - 有明确的 error handling
- M10 不实现此层，仅在设计中预留接口位置。

---

## 4. 推荐数据路径结构

建议在 `data/snapshots/` 下使用以下目录结构：

```
data/snapshots/
├── demo_offseason_v1/                          # Layer 1: Demo snapshot（永远保留）
│   ├── manifest.json
│   ├── source_notes.md
│   └── normalized/
│       ├── teams.json
│       ├── players.json
│       ├── rosters.json
│       ├── contracts.json
│       ├── cap_config.json
│       ├── cap_sheets.json
│       ├── free_agents.json
│       └── evidence_notes.json
│
├── nba_real_2026_preoffseason_v1/              # Layer 2/3: Curated real snapshot (v1)
│   ├── source_manifest.json                    # M10-B 新增：来源元数据
│   ├── manifest.json
│   ├── source_notes.md
│   └── normalized/
│       ├── teams.json                          # 30 队 metadata（含 conference/division/colors）
│       ├── players.json
│       ├── rosters.json                        # 按优先级逐步填充
│       ├── contracts.json
│       ├── cap_config.json
│       ├── cap_sheets.json
│       ├── free_agents.json
│       └── evidence_notes.json
│
└── nba_real_2026_preoffseason_v2/              # Layer 3: 未来版本（不覆盖 v1）
    └── ...
```

**为什么使用 versioned snapshot，而不是覆盖 demo 数据：**

1. **可回滚**：新版本有问题时可以一键切回旧版本。
2. **可追溯**：每个 snapshot 是一个不可变的时间切片，agent_trace 中的 data_source_label 可以精确指向某个 snapshot_id。
3. **测试稳定**：测试固定引用某个 snapshot_id，不会因为数据更新而意外失败。
4. **Demo 不受影响**：demo snapshot 永远在独立目录，real 数据的导入不会破坏 demo 模式。
5. **合规审计**：每个 snapshot 有独立的 source_manifest，可以回答"这个数据从哪来、什么时候导入的、有什么许可限制"。

---

## 5. source_manifest 设计

M10-B 需要为 curated real snapshot 定义 `source_manifest.json` schema。每个 real snapshot 目录必须包含此文件。建议字段如下：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `snapshot_id` | string | ✅ | 唯一标识，如 `"nba_real_2026_preoffseason_v1"` |
| `season` | string | ✅ | 赛季标识，如 `"2025-2026"` 或 `"2026-2027"` |
| `snapshot_type` | string | ✅ | 如 `"curated_real"`、`"demo"`、`"historical_source_backed"` |
| `as_of_date` | string (YYYY-MM-DD) | ✅ | 数据截止日期 |
| `generated_at` | string (ISO 8601) | ✅ | snapshot 生成时间 |
| `source_name` | string | ✅ | 数据来源名称，如 `"Spotrac 2025-26 contract/cap table"`、`"NBA.com official public roster pages"` |
| `source_url` | string \| null | ❌ | 来源 URL（如果有公开页面） |
| `source_reference` | string \| null | ❌ | 来源参考（如果没有直接 URL，如出版物名称、页面标题） |
| `license_notes` | string | ✅ | 许可/使用条款说明，如 `"Publicly available data for non-commercial demonstration purposes; third-party data requiring manual review"` |
| `freshness_label` | string | ✅ | 新鲜度标签，如 `"Pre-offseason freeze (as of 2026-06-25)"`、`"Post-draft pre-FA"` |
| `limitations` | string[] | ✅ | 数据局限性列表，如 `["Not live data", "Manual review required for salaries", "Third-party contract data may contain errors", "Does not reflect post-snapshot transactions"]` |
| `created_by` | string | ✅ | 创建者标识，如 `"m10-curated-import-v1"`、`"manual-seed-by-operator"` |
| `validation_status` | string | ✅ | 验证状态：`"provisional"`（导入后未完全验证）、`"partially_validated"`（部分字段已验证）、`"validated"`（全部字段已交叉验证） |
| `replaces_snapshot_id` | string \| null | ❌ | 如果是更新版本，指向前一版本 snapshot_id |
| `data_freshness_warning` | string | ✅ | 前端直接展示的新鲜度警告文案，如 `"This snapshot reflects roster/salary state as of 2026-06-25 and does not include transactions after that date."` |

**与现有 manifest.json 的关系：**
- `source_manifest.json` 是 M10 新增的扩展元数据文件，专注于来源和新鲜度治理。
- 现有的 `manifest.json` 保留其现有字段（snapshot_id, season, snapshot_type, sample_data, manual_review_required, as_of_date, teams, source_pack_version, limitations），不删除现有字段以保持兼容性。
- M10-B 决定是否将 source_manifest 的字段合并进 manifest 或保持独立文件——Design Gate 倾向保持独立文件，避免修改现有 manifest 解析逻辑。

---

## 6. 数据优先级

M10 按以下优先级逐步引入真实数据。低优先级数据在高优先级数据完成验证前不应开始。

| 优先级 | 数据类型 | 说明 | M10 milestone |
|--------|----------|------|---------------|
| P0 | **Team list** | 30 队基本信息：team_id、city、name、abbreviation、conference（East/West）、division | M10-C |
| P0 | **Team visual metadata** | primary/secondary colors（hex）、abbreviation（如 GSW/LAL/BOS）、conference/division grouping——不含 logo 文件 | M10-C |
| P1 | **Roster** | 每队球员名单：player_id、name、position、jersey_number（如公开可查） | M10-E |
| P2 | **Contracts / Salaries** | 球员合同信息：年限、薪资、选项、保障比例——必须标注来源和 uncertainty note | M10-F |
| P2 | **Cap sheet** | 每队薪资汇总：total_salary、cap_hold、dead_money、cap_space 计算 | M10-F |
| P3 | **Free agents** | 自由球员列表：player_id、name、position、previous_team、FA type（UFA/RFA/ETO） | M10-G（如果时间允许） |
| P4 | **Draft assets** | 选秀权信息：year、round、team（含 protections 标注为 TBD/complex，不做复杂保护逻辑） | M10 之后或 M10-G 末 |

### M10 暂时不碰的数据

以下数据在 M10 阶段明确排除：

| 数据类型 | 排除原因 |
|----------|----------|
| Live injury status（实时伤病状态） | 需要实时数据源，且伤病状态变化频繁，snapshot 模式无法保证 freshness |
| Betting odds（博彩赔率） | 法律/合规风险高，与前台决策支持的核心功能无关 |
| Real-time transactions（实时交易/签约更新） | 需要 live data feed，snapshot 模式做不到 |
| Live box scores（实时比赛数据） | 需要 live API，与休赛期决策场景无关 |
| Player tracking data（球员追踪数据） | 需要付费 API，大幅超出 demo 项目范围 |
| 未授权薪资数据库整包导入 | 版权风险，只从公开来源手工 curated，不整包导入第三方付费数据库 |
| 复杂 draft pick protections（复杂选秀权保护条款） | 如"前10保护转前5保护转2029次轮"等复杂逻辑，当前 trade simulator 不需要 |
| 真实球队 logo 文件（PNG/SVG/WebP） | 商标/版权风险，M10 只做 abbreviation badge 和 color stripe |
| 未核验来源的 current roster | 如果不能标注来源和 as_of_date，就不导入 |

---

## 7. Demo + Real 双模式

M10 必须实现 demo mode 和 real_snapshot mode 的双模式机制：

### 模式规则

| 规则 | 说明 |
|------|------|
| **Demo mode 默认** | 系统启动时默认加载 demo snapshot（现有 GSW+PHX 数据），和 M9 封口行为完全一致 |
| **Real mode 显式启用** | 切换到 real_snapshot mode 需要显式操作（环境变量 `SNAPSHOT_MODE=real`、URL 参数、或 UI 中的 data mode 切换器——M10-D 决定具体方式） |
| **Demo 不被覆盖** | real snapshot 的导入永远不会修改 demo snapshot 目录中的任何文件 |
| **Loader 返回 snapshot_mode** | snapshot loader 在加载数据后必须返回 `snapshot_mode` 字段（`"demo"` 或 `"real"`），随 API 响应一起返回给前端 |
| **UI 固定显示 data_mode** | 前端页面顶部或侧边栏固定区域必须显示：data_mode badge（"演示数据"或"真实数据快照"）、as_of_date、freshness_label、source_name |
| **测试验证 demo 不变** | M10 所有 milestone 的测试必须验证：当 snapshot_mode=demo 时，输出与 M9 封口时完全一致（或在允许的误差范围内），即 demo mode 的 regression test |

### API 兼容性要求

- 现有 GET `/api/health` 返回的 data source metadata 需要增加 `snapshot_mode`、`as_of_date`、`freshness_label` 字段，但不删除现有字段。
- 所有现有 preview API（proposal-preview、trade-preview-demo、orchestrate-preview、natural-language-preview）在 demo mode 下行为不变。
- 在 real_snapshot mode 下，preview 功能基于 real snapshot 数据运行，但安全边界不变（只读 preview、requires_human_approval=true、无 execute 端点）。

---

## 8. Freshness 防误导规则

这是 M10 最重要的防误导规则。只要涉及真实数据，前端必须固定展示以下信息：

### 必须显示的信息

| 信息 | 位置 | 示例 |
|------|------|------|
| **数据模式** | 固定可见 badge | "演示数据 / Demo data" 或 "真实数据快照 / Real data snapshot" |
| **数据日期（as_of_date）** | 固定可见 | "数据截止：2026-06-25" |
| **赛季** | 固定可见 | "2025-26 赛季" |
| **来源（source_name）** | 固定可见或 tooltip | "来源：Spotrac 2025-26 contract/cap table" |
| **不是 live 数据的声明** | 固定可见 | "此快照为静态数据，不反映快照日期后的交易/签约" |

### 禁止文案（除非满足全部前提条件）

以下文案在 UI 文案、intelligence_summary、agent_trace、API 响应的任何面向用户字段中**禁止出现**，除非同时满足：(1) 有可验证的数据来源，(2) 有明确的更新时间戳，(3) 有合法授权，(4) 有自动刷新机制：

| ❌ 禁止文案 | 原因 |
|------------|------|
| "current roster"（当前阵容） | snapshot 是静态时间切片，不等于"当前" |
| "live salaries"（实时薪资） | 不是实时数据 |
| "latest NBA data"（最新 NBA 数据） | "latest" 暗示 live/current |
| "real-time"（实时） | snapshot 不是实时的 |
| "up-to-date"（最新/截至目前） | 同上 |
| "现在的 XXX 队" | 暗示数据是 current |
| "已经交易到/已经签约到" | 暗示操作已发生 |
| "NBA 官方数据" | 除非有 NBA 官方授权，否则不能暗示官方背书 |

如果需要表达数据的时效性，使用以下安全表述：

| ✅ 安全表述 |
|------------|
| "数据截止 2026-06-25"（明确日期） |
| "2025-26 赛季休赛期前快照"（明确时间窗口） |
| "基于公开来源手工整理"（明确来源性质） |
| "此快照不包含 2026-06-25 之后的交易/签约"（明确局限） |
| "演示数据"（demo mode 下） |

---

## 9. Team Branding / Logo 策略

这是 M10 的第二个核心风险领域。

### 核心立场：不建议直接使用真实 NBA logo

NBA 球队 logo、队徽、昵称字体、吉祥物形象等视觉资产属于 NBA Properties, Inc. 和各球队的知识产权。未经明确授权将这些 logo 文件放入开源 repo 或在产品中公开展示，存在商标侵权和版权风险。即使是"小尺寸 favicon"或"低分辨率缩略图"也不例外。

### M10 早期策略（M10-A 到 M10-G）

M10 早期阶段（在获得合法授权之前），球队视觉标识只使用以下**无商标风险**的方式：

| 方式 | 说明 | 示例 |
|------|------|------|
| **Abbreviation badge** | 使用球队 2-3 字母缩写的文字徽章，纯色背景 + 缩写文字 | GSW 在蓝色圆形背景上的白字 |
| **Team color stripe** | 使用球队主色/辅助色作为色条或色块标识，不包含 logo 图形 | 勇士队蓝金配色条 |
| **Text monogram** | 使用城市名+队名的纯文字标识，不使用官方字体 | "Golden State Warriors" 用系统字体排版 |
| **Fallback badge** | 统一风格的占位徽章（如圆形/盾形背景 + 缩写），所有队使用相同模板 | 类似 Olympics 国家代码徽章的风格 |

具体颜色值（primary/secondary hex）在 M10-C 的 team metadata seed 中定义，颜色值来源于公开可查的球队品牌指南（如球队官方网站使用的颜色），仅作为色块背景使用，不构成商标使用。

### 如果未来要使用真实 logo 的前提条件

如果项目 owner 未来决定使用真实球队 logo，必须满足以下全部条件：

1. Owner 确认拥有合法授权（NBA 授权、球队授权、或使用明确标注可非商业使用的资源）
2. Logo 资产由 owner 亲自提供，不是 AI 从网上爬取
3. License 文件随 logo 一起放入 repo，明确授权范围
4. Logo 文件存放在独立目录（如 `assets/teams/logos/`），并有 README 说明授权来源
5. 不在 UI 中暗示 NBA 官方背书（除非确实有官方授权）

### 明确禁止

- ❌ 把从 Google 图片/维基百科/NBA 官网下载的 logo 文件放入 repo
- ❌ 使用 AI 生成"类似 NBA logo"的队徽（可能产生衍生商标风险）
- ❌ 在 repo 中包含未确认授权的 .png/.svg/.webp logo 文件
- ❌ 在 UI 中使用 NBA 官方字体（如 NBA Lakers 字体等可能受保护的字体）

---

## 10. 30 队前端展示策略

M10-D 需要在前端添加 30 队选择和展示能力，但要控制范围，不做大规模 UI redesign。

### 建议做的（M10-D 范围内）

| 功能 | 说明 |
|------|------|
| **Team selector** | 球队选择器（下拉列表或侧边栏列表），让用户选择要查看/操作的球队 |
| **East / West grouping** | 球队按东部/西部联盟分组展示 |
| **Conference/Division metadata** | 显示球队所属联盟和分区（如 "Pacific Division, Western Conference"） |
| **Abbreviation badge** | 每个球队显示缩写徽章（无 logo，纯文字+色块） |
| **Fallback badge** | 统一风格的占位徽章 |
| **Data freshness label 固定可见** | 页面固定位置显示 data_mode、as_of_date、freshness_label |
| **Demo/real mode badge 固定可见** | 清晰标注当前数据模式 |

### 不要做的（超出 M10 范围）

| 功能 | 不做的原因 |
|------|-----------|
| 30 队完整 dashboard | 大幅超出 scope，每队一个完整面板需要大量设计工作 |
| Logo grid（logo 墙） | logo 风险 + 大规模 UI redesign |
| Live stats cards（实时数据卡片） | 没有 live 数据源，也不应该暗示 live |
| 大规模 UI redesign | M10 是数据扩展，不是视觉改版，现有 `/offseason` 布局基本保持不变 |
| 球队对比页面 | 功能扩展，可在 M10 之后考虑 |
| 球队新闻/社交媒体 feed | 需要外部 API，超出范围 |

---

## 11. M10 Milestone 拆分

M10 拆分为 8 个 milestone，每个 milestone 可测试、可回滚、可独立封口：

| Milestone | 名称 | 内容 | 交付物 |
|-----------|------|------|--------|
| **M10-A** | Docs-only Design Gate | 本文档。明确风险、边界、分层、路线、安全红线 | `docs/m10-a-real-data-team-branding-design-gate.md` |
| **M10-B** | Real Snapshot Schema + source_manifest schema | 定义 curated real snapshot 的目录结构、source_manifest.json schema、manifest.json 扩展字段、loader 需要返回的 snapshot_mode 字段。不填充实际数据。 | Schema 文档、source_manifest 示例文件、loader 接口定义 |
| **M10-C** | 30 队 team metadata seed（不含 logo） | 导入 30 队基本 metadata：team_id、city、name、abbreviation、conference、division、primary/secondary colors（hex）。不含 logo 文件。 | `normalized/teams.json`（30 队）、team metadata seed 脚本/数据 |
| **M10-D** | Frontend team selector + fallback badge | 前端添加球队选择器（East/West 分组）、abbreviation/fallback badge、固定的 data_mode + freshness_label 显示区域。旧按钮和自然语言入口保持可用。 | 前端 team selector 组件、badge 组件、freshness label 组件 |
| **M10-E** | Curated roster snapshot | 导入 30 队球员名单（player_id、name、position），标注来源和 as_of_date。验证 loader 能正确加载。 | `normalized/players.json`、`normalized/rosters.json`（30 队基础阵容）、数据验证测试 |
| **M10-F** | Curated salaries/contracts snapshot | 导入球员合同和薪资数据，每笔合同标注 source_name、uncertainty_note、manual_review_required。导入 cap_config 和基础 cap_sheet。 | `normalized/contracts.json`、`normalized/cap_config.json`、`normalized/cap_sheets.json`、薪资验证测试 |
| **M10-G** | Real snapshot validation + smoke | 全量验证：demo mode 输出不变、real mode 数据可加载、preview 功能在 real mode 下正常运行、freshness label 正确显示、无执行类误导文案、API smoke tests、浏览器 smoke tests。 | Smoke runbook 文档、验证报告 |
| **M10-H** | Final real-data handoff | 最终交接文档：覆盖 demo+real 双模式的 demo operator 话术、reviewer checklist、安全边界确认、已知限制。 | `docs/m10-h-real-data-final-handoff.md` |

### 每个 milestone 的通用要求

- 每个 milestone 开始前有明确的 scope 定义
- 每个 milestone 结束后有可运行的 smoke tests 或验证步骤
- 每个 milestone 不破坏前一个 milestone 的已封口功能
- 每个 milestone 保持 demo mode 默认行为不变
- 如果某个 milestone 引入了风险或问题，可以回滚到前一个 milestone tag

---

## 12. 分工建议

| 角色 | 职责 |
|------|------|
| **GPT-5.5（架构师）** | 数据分层架构设计、source_manifest schema 定义、snapshot loader 接口设计、source/freshness policy 制定、milestone 拆分评审 |
| **GLM-5.2（审稿人）** | Schema review（字段一致性、兼容性检查）、风险审稿（IP/授权风险、freshness 误导风险）、跨文档一致性审查（确保 M10 文档不与 M8/M9 已封口规则冲突） |
| **Doubao（实现者）** | 小范围确定性实现：docs 撰写、seed 数据整理（30 队 metadata）、smoke tests 编写、前端 badge/selector 组件实现（M10-D 范围内，不做 redesign） |
| **ChatGPT（验收者）** | 最终验收 gate：确认每个 milestone 的交付物符合设计、安全边界未被突破、demo mode 回归测试通过、无误导文案、做出 commit/tag 决策 |

---

## 13. 绝对不能破的 M9 边界

M10 是数据扩展和展示扩展，**不是安全边界的修改**。以下 M9 已封口的安全边界在 M10 全部 milestone 中必须继续遵守，一条都不能破：

| # | 安全边界 | 说明 |
|---|----------|------|
| 1 | **不自动执行交易** | 没有任何代码路径会自动提交交易到任何真实系统 |
| 2 | **不自动执行签约** | 没有任何代码路径会自动签约自由球员 |
| 3 | **不让自然语言覆盖 deterministic verdict** | 自然语言输入只用于意图分类和解释，规则引擎和交易模拟器的结论不可被覆盖 |
| 4 | **不绕过 salary/trade validation** | 所有 preview 必须经过 salary rule engine 和 trade simulator 验证 |
| 5 | **不修改真实 roster/contracts/cap/snapshot** | 后端永远不写入 data/ 目录；real snapshot 是只读的 |
| 6 | **不把 snapshot 说成 live/current** | 所有快照标注 as_of_date 和 freshness_label，禁止暗示实时性 |
| 7 | **不把 demo 数据说成真实 NBA 数据** | Demo mode 明确标注"演示数据" |
| 8 | **不接未授权 logo** | 真实 logo 文件不放入 repo，不使用未授权视觉资产 |
| 9 | **不新增 execute/apply/commit/mutate/write endpoint** | 所有 API 端点保持 preview-only |
| 10 | **不破坏 M9 natural-language-preview safety gate** | 分类器、安全门、五状态处理逻辑保持不变 |
| 11 | **不改变 human approval** | 所有 signing/trade preview 继续保持 requires_human_approval=true |
| 12 | **不接真实 LLM** | 不引入 OpenAI/Anthropic/任何模型 API 调用 |
| 13 | **不做 runtime scraping/crawling** | 所有 real 数据通过手工 curated snapshot 导入，不做运行时网络抓取 |

---

## 14. 最终结论

**M10 is worth pursuing, but it must start as a data governance and source-metadata project, not a visual-logo or live-data project.**

M10 值得做。30 队展示和更真实的数据源会让这个休赛期决策支持 Agent 更有实用性和演示价值。但前提是：

1. **先治理数据，再展示数据。** source_manifest、freshness_label、validation_status 是基础设施，不是可选项。
2. **先保护 demo，再引入 real。** Demo mode 永远默认、永远可用、永远不被覆盖。
3. **先用 abbreviation/badge，再考虑 logo。** Logo 是 IP 雷区，M10 不碰真实 logo 文件，abbreviation badge + color stripe 足够表达球队身份。
4. **先做 snapshot，再想 live。** Live data 是未来的事，M10 只做 versioned static snapshot。
5. **安全边界一条不破。** M9 的 preview-only、human approval、deterministic verdict、no-execute 原则在 M10 中继续生效。

通过 M10-A Design Gate 后，建议进入 M10-B（Real Snapshot Schema + source_manifest schema 定义）。M10-B 仍然是 schema/docs 工作，不引入真实数据，不修改 frontend/backend 业务逻辑。
