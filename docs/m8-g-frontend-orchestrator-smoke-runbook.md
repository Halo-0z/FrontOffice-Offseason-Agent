# M8-G Frontend Orchestrator Smoke Runbook

## 1. 当前基线

- **HEAD**: `180c09f` — *Add M8-F frontend wiring summary*
- **Latest implementation commit**: `c74e523` — *Wire frontend to orchestrator preview API*
- **Current summary tag**: `m8f-frontend-wiring-summary`（points at 180c09f）
- **Frontend wiring tag**: `m8f-frontend-orchestrator-api-wiring`（points at c74e523）
- **origin/main**: 已同步
- **工作区**: 运行本 runbook 前应 `git status --short` 为空

M8-F 完成后，前端 signing / trade 两条主路径优先走 `POST /api/agent/orchestrate-preview`，hold 维持旧路径，旧 API 作为 fallback 保留，产品语言已完成降噪。

---

## 2. 这个 runbook 是干嘛的

这是一份**人工 smoke 检查清单**，给新接手或做了前端大改的人用。

按下面步骤一步步点，你就能判断 M8-F 封口后的前端 Agent 页面有没有被后续改动破坏：

- signing（签约推荐）是否还优先走 orchestrator；
- trade（模拟交易）是否还优先走 orchestrator；
- hold（严格预算/暂不行动）是否仍走旧 proposal-preview；
- fallback 链路是否仍然可用；
- 主界面是否还保持"用户语言"，没有重新漏出 PASS / payload / metadata 这类工程字段；
- "只读预览 / 需要人工确认"的安全语义有没有被误改成"已执行/已批准"。

本 runbook 只做**人工验收**，不替代自动化测试（自动化测试见第 12 节）。

---

## 3. 启动后端

打开一个 PowerShell 窗口，运行：

```powershell
cd D:\FrontOffice-Offseason-Agent
D:\anaconda\python.exe -m uvicorn backend.app.api:app --host 127.0.0.1 --port 8000 --reload
```

看到 `Uvicorn running on http://127.0.0.1:8000` 即启动成功。保持窗口开着。

### 快速健康检查（可选）

浏览器打开 http://127.0.0.1:8000/api/health ，应返回 JSON，`status` 字段为 `"ok"`。

---

## 4. 启动前端

再开一个 PowerShell 窗口，运行：

```powershell
cd D:\FrontOffice-Offseason-Agent\frontend
$env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npx next dev --port 3000
```

看到 `Ready in ...` 且 `Local: http://localhost:3000` 即前端启动。

浏览器打开：

> http://localhost:3000/offseason

页面应加载出"休赛期方案生成工作台"，左侧有三个场景选项，一个"生成休赛期方案"按钮，右侧初始状态为空。

打开浏览器 DevTools → Network 面板，勾选"Preserve log"，准备观察请求。

---

## 5. Signing Smoke（签约推荐）

### 5.1 操作步骤

1. 场景选择：选中第一个（"签约推荐" / "Signing"，$20M 预算充足）。
2. 点击 **"生成休赛期方案"** 按钮。
3. 等待 2-3 秒，观察页面和 Network。

### 5.2 页面应当显示

- [ ] 数据来源卡片显示"前台助手 · 演示数据"或同类"通过前台助手生成"标识，**不**显示"已通过备用预览方式"。
- [ ] 卡片顶部出现 **"只读预览"**（Read-only preview）徽章。
- [ ] 关键指标中有 **"需要人工确认"**（Human approval: Required）。
- [ ] 右侧"方案生成过程"卡片按顺序显示 5 个步骤，文案类似：
  1. 理解你的补强位置、预算和目标
  2. 在可用自由球员中匹配合适人选
  3. 核对薪资上限、签约规则和阵容限制
  4. 整理推荐理由和可能的风险
  5. 预览已生成，需要你确认后才会签约
- [ ] "补强位置"单元格显示类似 **"中锋：现有 0，目标 2（优先级：高）。"**（中文）或 **"Center: current 0, target 2 (priority: High)."**（英文）。
- [ ] 推荐卡片正文描述签约预览（例如"以 $XX 签下 XX，补强中锋位置"），不暗示已真实签约。
- [ ] 底部或区块中有"演示数据，不代表真实 NBA 数据"的免责声明。

### 5.3 主界面禁止出现

以下词汇**不应**在主界面（不展开任何"查看技术详情"/"查看完整审计详情"时）出现：

- [ ] **PASS**（应显示"通过"）
- [ ] **C: have 0, target 2**（应映射为"中锋：现有 0，目标 2"）
- [ ] **intent=signing_preview** / **signing_preview**（作为原始字符串）
- [ ] **orchestrator**
- [ ] **preview_payload**
- [ ] **metadata**
- [ ] **validation_result**
- [ ] **tool_name**
- [ ] **transaction_id** / **action_id** / **evidence_id**（原始 ID 串）
- [ ] 花括号包裹的 raw JSON（`{...}` 整块）
- [ ] **"已执行签约"** / **"已完成签约"** / **"已签约"**（误导性执行文案）
- [ ] **"自动批准"** / **"已提交"** / **"自动执行"**

### 5.4 Network 确认

在 DevTools Network 面板应看到：

- [ ] 一条 `POST /api/agent/orchestrate-preview` 请求，状态 200。
- [ ] 该请求 body 的 `intent` 字段为 `"signing_preview"`。
- [ ] **不应**出现 `POST /api/offseason/proposal-preview`（orchestrator 成功时不走旧路径）。
- [ ] **不应**出现任何 `/api/agent/execute` 或类似写操作端点（本项目没有这类端点）。

---

## 6. Trade Smoke（模拟交易）

### 6.1 操作步骤

1. 刷新页面回到初始状态（或点"重新生成"）。
2. 场景选择：选中第二个（"模拟交易" / "Trade Preview"）。
3. 点击 **"生成休赛期方案"** 按钮。
4. 等待 2-3 秒，观察页面和 Network。

### 6.2 页面应当显示

- [ ] 数据来源卡片显示"前台助手 · 演示数据"。
- [ ] 顶部出现 **"只读预览"** 徽章。
- [ ] 关键指标中有 **"规则检查：通过"** 和 **"薪资配平：通过"**。
- [ ] 关键指标中有 **"人工确认：需要"**。
- [ ] 右侧"方案生成过程"显示 5 个步骤，第 5 步文案类似"预览已生成，需要你确认后才会采取任何行动"。
- [ ] 交易资产区：
  - [ ] 两队各自的球员卡片上方用徽章标注 **"送出"** / "Sending out" 和 **"得到"** / "Receiving"（**不是** IN / OUT）。
  - [ ] 资产类型显示 **"球员合同"** / "Player contract"（**不是** PLAYER_CONTRACT）。
- [ ] 薪资配平卡片：两个球队卡片徽章都显示"通过" / "Pass"（**不是** PASS），规则文案显示"规则：得到薪资 ≤ 送出薪资 × 125% + $100,000（样例规则，非真实 CBA）"。
- [ ] 两队交易后视图：
  - [ ] 薪资 impact 显示类似"DEM-ATL 交易后总薪资 $78,000,000，薪资空间 $..."（**不是** "post-trade total salary" / "cap_space" 连写）。
  - [ ] 字段使用"薪资空间"/"总薪资"/"距奢侈税线"等中文产品词，或对应 plain English。
- [ ] 底部显示"演示数据"免责声明（**不是** "sample/demo" 原样）。

### 6.3 主界面禁止出现

- [ ] **PASS** / **FAIL**（必须是"通过/未通过"）
- [ ] **PLAYER_CONTRACT**
- [ ] **IN** / **OUT** 作为资产方向标签
- [ ] **post-trade total salary** / **total_salary** / **cap_space** / **tax_distance**（snake_case 或英文硬编码）
- [ ] **players with starter**（必须是"首发级球员"/"Starter-level players"等产品语言）
- [ ] **sample/demo** 原样连写
- [ ] **payload** / **metadata** / **validation_result** / **tool_name**
- [ ] **"已执行交易"** / **"交易已完成"** / **"自动提交"**（误导性执行文案）

### 6.4 Network 确认

- [ ] 一条 `POST /api/agent/orchestrate-preview`，状态 200。
- [ ] body 的 `intent` 为 `"trade_preview_demo"`。
- [ ] 不应出现 `POST /api/offseason/trade-preview-demo`（orchestrator 成功时不走旧路径）。

---

## 7. Hold Smoke（严格预算 / 暂不行动）

### 7.1 操作步骤

1. 刷新页面回到初始状态。
2. 场景选择：选中第三个（"严格预算" / "Strict-Budget Fallback"，$15M 预算受限）。
3. 点击 **"生成休赛期方案"** 按钮。
4. 等待 2-3 秒，观察页面和 Network。

### 7.2 页面应当显示

- [ ] 结果表达 **"暂不行动 / 保持观察 / 预算受限"** 的语义（例如"预算受限：建议暂不行动"或"Recommendation: hold"）。
- [ ] 推荐动作区显示 HOLD 类型动作，而不是 SIGNING / TRADE。
- [ ] 原因文案解释找不到合适候选人（例如"没有自由球员符合预算"）。
- [ ] 仍然显示"只读预览"和"需要人工确认"。
- [ ] 不出现签约球员卡片、交易资产卡片、交易后薪资图等"推荐执行"的视觉。

### 7.3 主界面禁止出现

- [ ] 不应把 HOLD 结果渲染成"推荐签约"或"推荐交易"。
- [ ] 不应出现"已执行"/"已批准"/"已提交"等误导性文案。

### 7.4 Network 确认

- [ ] 应该看到 `POST /api/offseason/proposal-preview`（hold 仍走旧路径）。
- [ ] **不应**看到 `POST /api/agent/orchestrate-preview`（hold 尚未迁移 orchestrator）。

> 注：这是 M8-F 刻意保留的行为——orchestrator hold 返回的是薄阻断 payload，无法直接喂给现有 ProposalViewer，迁移需要单独做 payload 适配。

---

## 8. Fallback Smoke（后端不可用）

这一项是**可选**的（会让后端暂时失败），做完前三项再做。

### 8.1 操作步骤

1. 刷新页面回到初始状态。
2. **停掉后端 uvicorn**（在后端 PowerShell 窗口按 Ctrl+C）。
3. 场景选到"签约推荐"。
4. 点击"生成休赛期方案"。

### 8.2 页面应当显示

- [ ] 页面**不崩溃**、不白屏、不无限 loading。
- [ ] 数据来源卡片应切换到"本地备用演示数据" / "Offline fallback"或类似文案。
- [ ] 应看到用户能懂的 fallback 提示，例如：**"前台助手暂时不可用，已使用备用预览方式"**（或最终连备用也失败时的"前台助手暂时不可用，备用预览方式也失败：..."）。
- [ ] 仍然能看到签约预览结果（来自本地 static sample），仍然有"只读预览/需要人工确认"语义。
- [ ] 不应把 fallback 渲染成"交易失败"/"系统错误"/"已执行失败交易"。

### 8.3 恢复后端

测试完 fallback 后，重新启动后端：

```powershell
cd D:\FrontOffice-Offseason-Agent
D:\anaconda\python.exe -m uvicorn backend.app.api:app --host 127.0.0.1 --port 8000 --reload
```

刷新页面，状态应恢复到"前台助手 · 演示数据"。

---

## 9. 技术详情规则

"查看技术详情"、"查看交易审计详情"、"查看完整审计详情"等折叠区（ `<details>` 元素）展开后：

- [ ] **可以**出现原始字段：`tool_name`、`inputs_summary`、`outputs_summary`、`technical_details`、`evidence_ids`、`transaction_id`、`validation_status`、`PASS`/`FAIL` 等。
- [ ] 对象/数组应 pretty-print 或用列表展示，**不**能直接打印 `[object Object]`。
- [ ] 但**主界面**（折叠区未展开时的默认可见区域）必须严格遵守第 5.3 / 6.3 / 7.3 节的禁忌词清单。

一句话原则：**主界面说人话，折叠区留给开发者。**

---

## 10. 通过标准（Checklist）

全部满足才算通过：

| # | 检查项 | 结果 |
|---|--------|------|
| 1 | signing 场景 Network 发出 `POST /api/agent/orchestrate-preview`（intent=signing_preview） | ☐ |
| 2 | trade 场景 Network 发出 `POST /api/agent/orchestrate-preview`（intent=trade_preview_demo） | ☐ |
| 3 | hold 场景 Network 发出 `POST /api/offseason/proposal-preview`（不走 orchestrator） | ☐ |
| 4 | 主界面无任何工程字段泄漏（PASS/PLAYER_CONTRACT/IN/OUT/payload/metadata/validation_result/tool_name/sample-demo 原样等） | ☐ |
| 5 | "只读预览" / "需要人工确认"语义在三个场景都保留 | ☐ |
| 6 | 补强位置显示"中锋：现有 0，目标 2"这种产品语言（不是 "C: have 0, target 2"） | ☐ |
| 7 | 页面不白屏、不抛 JS 异常、不无限 loading（可用 DevTools Console 确认） | ☐ |
| 8 | 没有误导性执行文案（"已执行"/"已完成"/"自动批准"/"已提交"/"自动执行"） | ☐ |
| 9 | 后端停掉时 signing/trade 仍能 fallback 到本地样例，页面不崩溃 | ☐ |

如果 1-8 全过、9（fallback）可过可不过但失败时必须有用户能懂的提示，就可以认为 M8-F 前端状态正常。

---

## 11. 失败时怎么处理

### 11.1 页面 500 / 白屏 / 编译错误

- 先关掉前端 `next dev`，删除 `.next` 目录，重启：
  ```powershell
  cd D:\FrontOffice-Offseason-Agent\frontend
  Remove-Item -Recurse -Force .next -ErrorAction SilentlyContinue
  npx next dev --port 3000
  ```
- 检查 Node 版本（仓库使用 Next.js 14，建议 Node 18+）。
- 检查 `$env:NEXT_PUBLIC_API_BASE_URL` 是否正确设置为 `http://127.0.0.1:8000`。

### 11.2 Network 请求路径不对

| 现象 | 排查点 |
|------|--------|
| signing/trade 没走 orchestrator，直接走了旧 API | 检查 [page.tsx](file:///D:/FrontOffice-Offseason-Agent/frontend/app/offseason/page.tsx) 的 `handleGenerate` 函数，确认 signings/trade 分支先调用 `fetchOrchestratorPreview`，失败才 fallback。 |
| hold 走了 orchestrator | hold 不应走 orchestrator；检查是否误改了 handleGenerate 中 hold 分支。 |
| 完全没发请求 | 检查按钮点击事件是否绑定 handleGenerate，是否有 JS 报错（DevTools Console）。 |

### 11.3 主界面出现工程词（PASS / payload / PLAYER_CONTRACT 等）

优先检查以下三个文件的展示层 mapping：

1. [page.tsx](file:///D:/FrontOffice-Offseason-Agent/frontend/app/offseason/page.tsx)：
   - `sanitizeStepSummary`（trace 步骤摘要里的 PASS/allowlist/intent=xxx 替换）
   - `mapStepSummary`（jargon 检测 + fallback 文案）
   - `translateMatchedNeed`（"C: have 0, target 2" → "中锋：现有 0，目标 2"）
   - `getUserFacingValidationStatus`（PASS/FAIL/WARNING/BLOCKED 映射）
   - 关键指标单元格是否直接渲染 `firstAction?.matched_need` 这类原始字段
2. [TradePreviewViewer.tsx](file:///D:/FrontOffice-Offseason-Agent/frontend/components/TradePreviewViewer.tsx)：
   - `translateCapImpactSummary` / `translateRosterImpactSummary` / `translateDepthImpactSummary`（summary 文本翻译）
   - AssetCard 是否用 `t.outBadge`/`t.inBadge`/`t.playerContractType` 而非原始值
   - 薪资配平卡片徽章是否用 `t.passBadge`/`t.failBadge` 而非硬编码 "PASS"/"FAIL"
   - `needLevelLabel` / `priorityLabel` 是否做了 high/medium/low 映射
3. [i18n.ts](file:///D:/FrontOffice-Offseason-Agent/frontend/data/i18n.ts)：
   - trade 字段标签应是 plain English（"Transaction ID"、"Asset type"），不能退回 snake_case
   - 徽章、免责文案等是否还有 "sample/demo" 连写

### 11.4 后端 API 报错

- 先看 uvicorn 控制台的 Python traceback。
- 跑后端测试定位回归：
  ```powershell
  cd D:\FrontOffice-Offseason-Agent
  D:\anaconda\python.exe -m pytest backend/app/tests/test_agent_orchestrator_api.py -q
  D:\anaconda\python.exe -m pytest backend/app/tests/test_api_endpoints.py -q
  ```
  M8-F 封口时这两套测试是 **30 passed** + **22 passed**。如果有新增失败，先回到最近的 green commit。

### 11.5 类型或构建错误

```powershell
cd D:\FrontOffice-Offseason-Agent\frontend
npm run typecheck
npm run build
```

两个都必须 0 error 通过。Next.js 会报未使用变量警告可以接受，但 TypeScript error 不可以。

---

## 12. 后续注意事项

- **不要直接删除旧 API**。`/api/offseason/proposal-preview` 和 `/api/offseason/trade-preview-demo` 仍是 fallback 层和 hold 场景的唯一通道。
- **不要贸然迁移 orchestrator hold**。orchestrator hold 返回薄阻断 payload，不包含 actions/evaluation/depth_chart；迁移前需单独设计 payload 适配层。
- **不要接 LLM**。所有建议、评估、文案都来自确定性代码和预置 i18n；要接 LLM 必须先过 M9 LLM Integration Design Gate，不允许在本代码里直接加模型调用。
- **不要接真实 NBA API**。所有球员/薪资数据来自仓库 snapshot/demo JSON；要接真实数据必须先过 Data Expansion Gate，明确数据来源、freshness、用户可见标识。
- **不要新增 execute / apply / commit / mutate 能力**。orchestrator 端点是 preview-only，永远返回 `requires_human_approval: true`；前端不允许出现任何"执行交易""确认签约""提交"按钮触发写操作。
- **后续每次前端大改（改卡片结构、改 trace 渲染、改 fallback 链路、加新场景）都要跑一遍本 runbook**，作为合并前的人工门禁。

---

## 13. 相关文档

- [M8-F Frontend Orchestrator API Wiring Summary](file:///D:/FrontOffice-Offseason-Agent/docs/m8-f-frontend-orchestrator-wiring-summary.md)
- [M8-E5 Orchestrator API Smoke Runbook](file:///D:/FrontOffice-Offseason-Agent/docs/m8-e5-orchestrator-api-smoke-runbook.md)（后端 API 层烟测）
- [M8-E Agent Orchestrator Handoff](file:///D:/FrontOffice-Offseason-Agent/docs/m8-e-agent-orchestrator-handoff.md)（orchestrator 后端设计）
- [Final API Console Smoke Runbook](file:///D:/FrontOffice-Offseason-Agent/docs/final-api-console-smoke-runbook.md)（M7 时代的旧烟测，保留参考）
