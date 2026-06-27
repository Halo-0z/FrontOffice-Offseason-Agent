# M10-D1: Backend Real Snapshot Metadata Read Model

## 1. M10-D1 目标

M10-D1 为 FrontOffice-Offseason-Agent 后端增加一个**只读**的 real snapshot metadata read model，让前端（M10-D2 及以后）能够通过稳定的 HTTP contract 获取 curated real snapshot 的元数据：

- snapshot 身份信息（snapshot_id / snapshot_type / season / as_of_date）
- 新鲜度与来源声明（freshness_label / data_freshness_warning / source_name / limitations）
- 安全标志（live_eligible=false / manual_review_required=true / no_official_branding=true）
- 30 支球队的基础身份信息（team_id / city / name / abbreviation / conference / division）
- 每队合并后的 non-official UI accent visual metadata（accent_color / secondary_accent_color / badge_style / no_official_branding=true）

M10-D1 不切换默认数据源，不影响 demo snapshot，不返回 roster/contracts/salaries/cap sheet/logo。

## 2. 为什么先做 backend read model，不先做 frontend

M10-D Design Gate（GPT-5.5）选择路线 A — Backend Read Model First，原因：

1. **稳定 contract 优先**：前端 selector/badge 需要一个稳定、schema 校验过、hash 校验过的 JSON contract。如果前端直接读 `data/snapshots/nba_real_2026_preoffseason_v1/`，会绕过所有后端校验并与文件系统路径耦合。
2. **安全边界集中**：M9 guardrail（禁止 execute/apply/commit/mutate/write/persist/save/delete/update/submit，禁止 live/current/latest 数据声明）必须在后端集中执行，不能依赖前端"自觉"。
3. **hard error 语义**：real snapshot 缺失/schema 不匹配/hash 不匹配/交叉引用不一致必须返回 hard error，不能静默 fallback 到 demo — 这个语义只能在 service 层强约束。
4. **DTO 投影**：raw source_manifest 包含 file_hashes / per_file_sources / schema_version 等内部字段，不能直接暴露给前端；需要一个只读 service 做安全投影。

前端 badge/selector（M10-D2）只需要消费一个 GET endpoint，不需要理解 snapshot 文件布局、JSON Schema 或 hash 校验。

## 3. Endpoint 说明

```
GET /api/snapshots/metadata?snapshot_mode=real_snapshot
```

- HTTP 方法：**GET**（只读）
- Query 参数：`snapshot_mode`（必填）
- 唯一允许值：`real_snapshot`
- 不接受任何 body
- 不新增任何 POST / PUT / PATCH / DELETE mutation endpoint

响应是一个 JSON 对象，见下文第 7 节。

## 4. snapshot_mode=real_snapshot 显式启用

snapshot_mode 是必填 query 参数。任何非 `real_snapshot` 的值都被显式拒绝：

| snapshot_mode | HTTP 状态码 |
|---|---|
| 缺失 | 422（FastAPI Query(...) 必填校验）|
| `""` 空字符串 | 400 |
| `demo` | 400（显式拒绝，不 fallback）|
| `live` | 400（显式拒绝）|
| `current` | 400（显式拒绝）|
| `latest` | 400（显式拒绝）|
| 任意其他字符串 | 400 |

这个"显式 opt-in"设计确保：

- 任何调用方都必须**有意识地**选择 real snapshot，而不会意外触发。
- `demo` / `live` / `current` / `latest` 这些危险模式在到达 service 之前就被 HTTP 层拒绝，不会产生任何 I/O。
- service 函数 `load_real_snapshot_metadata()` 在做任何磁盘操作前先检查 mode，形成双层防护。

## 5. Demo 默认不变

M10-D1 对现有系统的默认行为零影响：

- `/api/health` 返回不变；默认仍然 `data_mode="demo"`, `sample_data=true`。
- `/api/offseason/proposal-preview`、`/api/offseason/trade-preview-demo`、`/api/agent/orchestrate-preview`、`/api/agent/classify-intent`、`/api/agent/natural-language-preview` 的行为完全不变，仍然使用 demo 数据。
- `snapshot_loader.py` **未被修改**。它继续加载 demo historical snapshot（含 contracts/cap 数据）；与 M10-D1 的 metadata reader 完全独立。
- `data_source_resolver.py` **未被修改**。
- 默认环境变量不做任何修改；real snapshot 不会被自动激活。

前端未来（M10-D2+）如需使用 real metadata，必须**显式**调用 `/api/snapshots/metadata?snapshot_mode=real_snapshot`，并在 UI 上清楚展示 `data_freshness_warning`、`freshness_label=frozen`、`live_eligible=false`、`manual_review_required=true`。

## 6. Hard error，不 fallback demo

Service 在以下任何情况都抛 `RealSnapshotMetadataError` 子类（HTTP 层映射为 500），**绝不**静默 fallback 到 demo snapshot：

| 场景 | 错误类型 |
|---|---|
| real snapshot 目录不存在 | `RealSnapshotNotFoundError` |
| `manifest.json` 缺失 | `RealSnapshotNotFoundError` |
| `source_manifest.json` 缺失 | `RealSnapshotNotFoundError` |
| `normalized/teams.json` 缺失 | `RealSnapshotNotFoundError` |
| `normalized/team_visual_metadata.json` 缺失 | `RealSnapshotNotFoundError` |
| JSON 文件解析失败（非法 JSON） | `RealSnapshotSchemaError` |
| 任一文件 JSON Schema 校验失败 | `RealSnapshotSchemaError` |
| `source_manifest.file_hashes` 中缺少 `normalized/teams.json` 条目 | `RealSnapshotHashError` |
| `source_manifest.file_hashes` 中缺少 `normalized/team_visual_metadata.json` 条目 | `RealSnapshotHashError` |
| 文件实际 SHA-256 与 file_hashes 记录不匹配 | `RealSnapshotHashError` |
| `live_eligible` 不为 false | `RealSnapshotSchemaError` |
| `manual_review_required` 不为 true | `RealSnapshotSchemaError` |
| visual metadata 中出现 teams.json 没有的 team_id | `RealSnapshotCrossReferenceError` |
| teams.json 中的 team_id 在 visual metadata 中缺失 | `RealSnapshotCrossReferenceError` |
| abbreviation 在 teams.json 与 visual metadata 中不一致 | `RealSnapshotCrossReferenceError` |
| 合并后 teams 数量不等于 30 | `RealSnapshotCrossReferenceError` |
| visual metadata 某条 `no_official_branding != true` | `RealSnapshotCrossReferenceError` |

测试显式验证：即便 demo snapshot 存在于 `data/snapshots/`，real snapshot 损坏或缺失也必须 hard error，不返回 demo。

## 7. Response 字段说明

### 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `snapshot_id` | string | `"nba_real_2026_preoffseason_v1"` |
| `snapshot_mode` | string | 固定 `"real_snapshot"`（非 live/current/latest）|
| `snapshot_type` | string | 来自 manifest.json，如 `"nba_real_preoffseason"` |
| `season` | string | 如 `"2025-26"` |
| `as_of_date` | string | `"2026-06-25"` |
| `freshness_label` | string | 来自 source_manifest（当前为 `"frozen"`）|
| `data_freshness_warning` | string | 必须向用户展示的 frozen 数据警告 |
| `source_name` | string | 例如 `"manual curated offseason metadata seed"` / `"manual non-official UI accent palette"` 组合投影 |
| `manual_review_required` | boolean | 固定 `true` |
| `live_eligible` | boolean | 固定 `false` |
| `no_official_branding` | boolean | 固定 `true`（来自 visual metadata 顶层）|
| `data_categories` | string[] | 当前包含 `"teams"`, `"team_visual_metadata"` |
| `limitations` | string[] | 非官方/无 logo/无 cap 数据等限制说明 |
| `teams` | object[] | 30 支球队，见下文 |

### teams[] 每条

| 字段 | 类型 | 说明 |
|---|---|---|
| `team_id` | string | 如 `"nba-LAL"`，以 `nba-` 前缀开头 |
| `city` | string | 如 `"Los Angeles"` |
| `name` | string | 如 `"Lakers"` |
| `abbreviation` | string | 3 字母大写，如 `"LAL"` |
| `conference` | string | `"East"` / `"West"` |
| `division` | string | 如 `"Pacific"` |
| `visual_metadata` | object | 见下文 |

### teams[].visual_metadata

| 字段 | 类型 | 说明 |
|---|---|---|
| `accent_color` | string | hex `#RRGGBB`，non-official UI accent |
| `secondary_accent_color` | string | hex `#RRGGBB`，non-official UI accent |
| `badge_style` | string | `"abbreviation_badge"` / `"neutral_badge"` / `"conference_badge"` |
| `no_official_branding` | boolean | 固定 `true` |

### 禁止字段（defence-in-depth）

API endpoint 在返回前做递归扫描，以下字段任一层级出现都会触发 HTTP 500（防御性）：

- 数据字段：`roster` / `players` / `contracts` / `salaries` / `cap_sheet` / `free_agents` / `draft_assets`
- Logo/branding：`logo_path` / `logo_url` / `official_logo` / `nba_logo` / `team_logo` / `mascot_image` / `official_branding` / `official_colors` / `brand_colors` / `pantone` / `brand_guidelines`
- Execution：`execute` / `apply` / `commit` / `mutate` / `write` / `persist` / `save` / `delete` / `update` / `submit` / `auto_execute` / `auto_approve`
- 内部字段：`file_hashes` / `per_file_sources`（file path、source_url、schema_version 也不暴露）

service 投影中不会生成这些字段；递归扫描是最后一道防线。

## 8. 不返回 roster/contracts/salaries/logo/official branding

M10-D1 的 read model 只读 4 个 JSON 文件：

- `manifest.json`
- `source_manifest.json`
- `normalized/teams.json`
- `normalized/team_visual_metadata.json`

它**不**读取：

- 任何 `players.json` / `contracts.json` / `cap_sheet*.json` / `free_agents.json` / `draft_assets.json` / `rosters.json`（这些文件在 real snapshot 中目前根本不存在）
- 任何图片文件（.png/.svg/.webp）
- 任何 brand guideline / Pantone / logo 数据
- 任何外部 API、LLM、网络资源

normalized/ 目录当前**只**包含 `teams.json` 和 `team_visual_metadata.json` 两个文件。service 不会遍历目录寻找额外文件。

测试覆盖：

- normalized/ 目录文件集合断言（只 2 个 JSON 文件）。
- response 递归扫描 30+ 个禁止字段名。
- source_manifest 中 `data_categories` 必须只包含 `"teams"` 和 `"team_visual_metadata"`（无 `"rosters"`, `"contracts"` 等）。
- snapshot_loader.py 未被修改的静态检查。

## 9. 不接 Agent / LLM / 交易签约决策

M10-D1 endpoint 显式不参与任何决策链路：

- 不接入 `agent_orchestrator`、`agent_intent_classifier`、`agent_natural_language_preview`、`proposal_builder`、`trade_simulator`、`transaction_rule_engine`。
- 不调用任何 LLM、MCP、外部 NBA API、网络。
- 不提供 execute/apply/commit/mutate/write 能力，所有 mutation 路径在 API 层 + metadata guard 中双重禁止。
- `/api/snapshots/metadata` 是 GET-only。OpenAPI 校验该路径只有 `get` 方法。
- `requires_human_approval` 语义与本 endpoint 无关（本 endpoint 不产出交易/签约提案）；它仅返回静态元数据。

Agent / natural-language-preview / orchestrator 现有 guardrail 测试（M9）继续全部通过，不被 M10-D1 影响。

## 10. 测试说明

测试文件：`backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py`

**Service 正向（14 个）：**
- 成功加载 real snapshot metadata
- 返回 30 队
- 每队包含完整 identity 字段
- 每队 visual_metadata 包含 accent/secondary_accent/badge_style/no_official_branding
- 顶层 `no_official_branding=true`
- `live_eligible=false`
- `as_of_date`/`freshness_label`/`data_freshness_warning` 存在
- `data_categories` 同时包含 teams 和 team_visual_metadata
- source_name 包含 non-official 语义
- `manual_review_required=true`
- limitations 包含 non-official disclaimer
- season / snapshot_type 存在

**API 正向（6 个）：**
- GET 200
- snapshot_mode=real_snapshot
- 30 队
- 所有要求的顶层字段存在
- 不暴露 raw source_manifest 内部字段（file_hashes/per_file_sources/source_url/schema_version）
- 递归扫描 30+ 禁止字段名全部通过

**API 负向（8 个）：**
- 缺 snapshot_mode 返回 4xx
- 空 snapshot_mode 返回 4xx
- snapshot_mode=demo/live/current/latest/foo 全部 400
- POST 方法 405/404

**Hard error（11 个，使用 tmp_path 隔离副本）：**
- wrong mode 在 IO 之前抛 RealSnapshotModeError
- snapshot 目录不存在 → NotFoundError
- teams.json / visual_metadata.json / manifest.json / source_manifest.json 缺失 → NotFoundError
- teams.json schema 损坏 → SchemaError 或 HashError
- teams.json 字节级篡改 → HashError
- visual_metadata 出现 nba-ZZZ 未知 team_id（重新签名 hash 绕过 hash 校验）→ CrossReferenceError
- visual_metadata 删除一条（重新签名 hash）→ SchemaError/CrossReferenceError
- abbreviation 不匹配（重新签名 hash）→ CrossReferenceError
- real 缺失但 demo 存在 → NotFoundError（不 fallback）
- real 损坏但 demo 存在 → MetadataError（不 fallback）

**回归（6 个）：**
- demo snapshot 文件集合与 M10-B/C1/C2 完全一致
- normalized/teams.json SHA-256 与 M10-C1 封口 hash 一致（`5b1e388bb2b7...`）
- snapshot_loader.py 未被修改、未 import real_snapshot_metadata_reader
- /api/snapshots/ 下不存在 execute/apply/write/commit/mutate/update/delete POST/PUT endpoint
- OpenAPI 中 `/api/snapshots/metadata` 只有 `get` 方法
- response 顶层不存在 live/current/latest/live_data/current_roster 字段，且 live_eligible=false

**完整回归测试还包括：**
- M10-B `test_m10_real_snapshot_schema.py`（48 个）
- M10-C1 `test_m10c_team_metadata.py`（62 个）
- M10-C2 `test_m10c_team_visual_metadata.py`（95 个）
- M9 `test_agent_guardrails.py` / `test_agent_orchestrator_api.py` / `test_agent_natural_language_preview_api.py` / `test_api_endpoints.py`

## 11. M10-D2 frontend selector/badge 后续如何消费该 endpoint

M10-D2（Frontend team selector + abbreviation badge）消费 `/api/snapshots/metadata?snapshot_mode=real_snapshot` 时必须遵守：

1. **显式调用**：前端只能通过该 GET endpoint 获取 team 列表，不能直接 fetch `data/snapshots/...` 文件，也不能硬编码 30 队列表。
2. **展示安全标志**：UI 必须清晰展示 `data_freshness_warning`、`freshness_label`、`live_eligible=false`、`manual_review_required=true`。
3. **Visual metadata = UI 区分色**：`accent_color` / `secondary_accent_color` 只能用于 abbreviation badge / neutral badge / 界面区分，绝不能被称为 "team colors"、"official colors"、"brand colors" 或 "NBA colors"。必须展示 non-official 语义。
4. **Neutral fallback**：如果未来某队 visual metadata 暂时缺失（例如新增 expansion 队但 visual metadata 尚未录入），前端必须有 neutral badge fallback（例如使用中性灰 badge_style=neutral_badge），不能因为 visual metadata 缺失而崩溃。schema 层当前强约束 30 条都有 visual metadata，但前端仍需防御式编程。
5. **只读**：前端不能假设存在任何写入或切换 endpoint；所有 team selection 仅在前端状态中保持，不触发任何后端 mutation。
6. **不扩展 response**：前端不应在 response 中寻找 roster/contracts/salary 字段——这些字段在当前 endpoint 中不存在，未来也不会通过这个 endpoint 暴露（会走 M10-E 以后的独立、带更严 gate 的 read model）。
7. **错误处理**：如果 endpoint 返回 5xx（hard error），前端应展示"real snapshot metadata currently unavailable"的降级 UI，不应静默切回 demo 数据的 roster/contract 视图。
