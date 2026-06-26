/**
 * Bilingual copy dictionary for the M6-C frontend (zh / en).
 *
 * Default language is Chinese (`zh`). A language switcher in the page
 * header toggles to English (`en`). Only UI copy is translated — the
 * underlying demo payload (codes, tool_names, evidence_ids, status
 * badges like RECOMMENDED / PASS / NO_ACTION / HOLD) stays in its
 * original English form so the audit trail remains traceable.
 *
 * No i18n library. No dependency changes. Just a plain object indexed
 * by `Lang`, accessed as `copy.section.key[lang]`.
 *
 * Milestone: M6-C (Chinese-first / bilingual patch).
 */

export type Lang = "zh" | "en";

export interface Bilingual {
  zh: string;
  en: string;
}

export const copy = {
  // ---- Language switcher ----
  langSwitch: {
    zh: { zh: "中文", en: "中文" } as Bilingual,
    en: { zh: "English", en: "English" } as Bilingual,
    ariaLabel: { zh: "语言切换", en: "Language switcher" } as Bilingual,
  },

  // ---- Root page (/) ----
  root: {
    title: { zh: "FrontOffice-Offseason-Agent", en: "FrontOffice-Offseason-Agent" } as Bilingual,
    subtitle: {
      zh: "NBA 休赛期前台决策工作流演示",
      en: "NBA Offseason Front-Office Decision Workflow Demo",
    } as Bilingual,
    description: {
      zh: "进入工作台后可以选择预算并生成 demo 方案，预览系统如何检查薪资、阵容、候选人和规则。使用样例数据，只生成预览，不会执行交易，所有动作都需要人工确认。",
      en: "Enter the console to pick a budget and generate a demo plan, previewing how the system checks cap, roster, candidates, and rules. Sample data only. Preview only. Requires human approval.",
    } as Bilingual,
    cta: {
      zh: "进入休赛期方案生成工作台 →",
      en: "Enter the offseason plan console →",
    } as Bilingual,
    footer: {
      zh: "无 LLM · 无 MCP · 无外部 NBA API · 不修改数据",
      en: "No LLM · No MCP · No external NBA API · No data mutation",
    } as Bilingual,
  },

  // ---- /offseason Hero (Agent Console framing) ----
  hero: {
    eyebrow: { zh: "Offseason Plan Console", en: "Offseason Plan Console" } as Bilingual,
    title: { zh: "休赛期方案生成工作台", en: "Offseason Plan Console" } as Bilingual,
    lede: {
      zh: "选择目标和预算，预览系统会如何检查薪资、阵容需求、候选人和规则，最后生成一个可审计的休赛期方案。API 优先演示：点击生成会优先调用本地后端 API；如果后端未启动，会自动显示本地静态样例结果。",
      en: "Pick a target and budget, then preview how the system checks cap space, roster needs, candidates, and rules to produce an auditable offseason plan. API-first demo: generation calls the local backend API first; if the backend is unavailable, the page falls back to local sample payloads.",
    } as Bilingual,
    badges: {
      sample: { zh: "样例数据", en: "sample data" } as Bilingual,
      preview: { zh: "仅供预览", en: "preview only" } as Bilingual,
      approval: { zh: "需要人工确认", en: "requires human approval" } as Bilingual,
      noPrediction: { zh: "不是真实 NBA 预测", en: "no real NBA prediction" } as Bilingual,
      noExecution: { zh: "不执行交易", en: "no transaction execution" } as Bilingual,
      noExternal: { zh: "无 LLM · 无 MCP · 无外部 API", en: "no LLM · no MCP · no external API" } as Bilingual,
    },
  },

  // ---- Agent Console: input panel, generate button, progress timeline ----
  console: {
    // Input panel
    inputTitle: { zh: "方案设置", en: "Plan settings" } as Bilingual,
    inputHint: {
      zh: "API 优先演示：点击生成会优先调用本地后端 API；如果后端未启动，会自动显示本地静态样例结果。",
      en: "API-first demo: generation calls the local backend API first; if the backend is unavailable, the page falls back to local sample payloads.",
    } as Bilingual,
    fieldTeam: { zh: "球队", en: "Team" } as Bilingual,
    fieldObjective: { zh: "目标", en: "Objective" } as Bilingual,
    fieldPosition: { zh: "目标位置", en: "Target position" } as Bilingual,
    fieldBudget: { zh: "薪资上限", en: "Salary cap limit" } as Bilingual,
    fieldCandidates: { zh: "最多候选人", en: "Max candidates" } as Bilingual,
    fieldEvidenceQuery: { zh: "证据查询", en: "Evidence query" } as Bilingual,
    budgetOption20: {
      zh: "$20M：预算充足，生成推荐签约",
      en: "$20M: budget available — recommend a signing",
    } as Bilingual,
    budgetOption15: {
      zh: "$15M：预算受限，生成 HOLD",
      en: "$15M: budget too tight — hold",
    } as Bilingual,
    teamDemAtl: { zh: "DEM-ATL（demo）", en: "DEM-ATL (demo)" } as Bilingual,
    objectiveValue: { zh: "补强前场 / Add frontcourt help", en: "Add frontcourt help" } as Bilingual,
    positionValue: { zh: "中锋 (C)", en: "Center (C)" } as Bilingual,
    candidatesValue: { zh: "2", en: "2" } as Bilingual,
    evidenceQueryValue: { zh: "center need cap flexibility", en: "center need cap flexibility" } as Bilingual,

    // Generate button + run states
    generateBtn: { zh: "生成休赛期方案", en: "Generate offseason plan" } as Bilingual,
    regenerateBtn: { zh: "重新生成", en: "Regenerate" } as Bilingual,
    stateIdle: { zh: "待机", en: "idle" } as Bilingual,
    stateRunning: { zh: "运行中…", en: "running…" } as Bilingual,
    stateComplete: { zh: "已完成", en: "complete" } as Bilingual,
    stateLabel: { zh: "状态", en: "State" } as Bilingual,

    // Progress timeline
    progressTitle: { zh: "Agent 执行步骤", en: "Agent execution steps" } as Bilingual,
    progressHint: {
      zh: "以下是 Agent 按顺序执行的检查流程。点击生成后，前端会优先调用本地后端 API；如果后端不可用，会回退到本地静态样例。",
      en: "The agent runs these checks in order. After clicking generate, the frontend calls the local backend API first; if the backend is unavailable, it falls back to local static samples.",
    } as Bilingual,
    steps: [
      { zh: "读取薪资空间", en: "Read cap space" } as Bilingual,
      { zh: "评估阵容需求", en: "Evaluate roster needs" } as Bilingual,
      { zh: "匹配自由球员", en: "Match free agents" } as Bilingual,
      { zh: "生成签约方案", en: "Generate signing plan" } as Bilingual,
      { zh: "薪资规则检查", en: "Salary rule check" } as Bilingual,
      { zh: "风险评估", en: "Risk assessment" } as Bilingual,
      { zh: "生成预览", en: "Build preview" } as Bilingual,
    ] as Bilingual[],

    // Output region
    outputTitle: { zh: "系统建议", en: "System recommendation" } as Bilingual,
    outputDefault: {
      zh: "建议签约：预算充足，系统找到一个中锋补强预览。",
      en: "Recommend a signing: budget available, the system found a center preview.",
    } as Bilingual,
    outputStrict: {
      zh: "建议暂不行动：预算受限，系统没有找到匹配候选人。",
      en: "Recommend holding: budget too tight, no matching candidate found.",
    } as Bilingual,
    whyTitle: { zh: "为什么是这个结果", en: "Why this result" } as Bilingual,

    // Audit details (collapsible)
    auditToggle: { zh: "查看审计详情", en: "View audit details" } as Bilingual,
    auditToggleHint: {
      zh: "展开后可查看完整工具调用追踪、证据、风险、检查 issue 和所有限制说明。",
      en: "Expand to see the full tool call trace, evidence, risks, evaluation issues, and all limitations.",
    } as Bilingual,
  } as const,

  // ---- Scenario tabs ----
  scenarios: {
    default: {
      label: { zh: "默认推荐", en: "Default Recommendation" } as Bilingual,
      sub: { zh: "预算充足：预览一个中锋签约方案。", en: "Budget available — preview a center signing." } as Bilingual,
      description: {
        zh: "DEM-ATL，目标位置 C，薪资上限 $20M，最多 2 名候选人。生成一个 RECOMMENDED 方案，包含一个通过校验的 SIGNING 动作。",
        en: "DEM-ATL, target C, max salary $20M, max 2 candidates. Produces a RECOMMENDED proposal with a SIGNING action that passes validation.",
      } as Bilingual,
    },
    "strict-budget": {
      label: { zh: "严格预算", en: "Strict-Budget Fallback" } as Bilingual,
      sub: { zh: "预算受限：找不到合适候选人，建议暂不行动。", en: "Budget too tight — hold instead of forcing a move." } as Bilingual,
      description: {
        zh: "DEM-ATL，目标位置 C，薪资上限 $15M，最多 2 名候选人。没有自由球员符合预算；生成一个 NO_ACTION 方案，包含 HOLD 动作和 no_matching_candidate 风险。",
        en: "DEM-ATL, target C, max salary $15M, max 2 candidates. No free agent fits the budget; produces a NO_ACTION proposal with a HOLD action and a no_matching_candidate risk.",
      } as Bilingual,
    },
  },

  // ---- Approval banner ----
  approvalBanner: {
    strong: { zh: "仅供预览 —— 需要人工确认。", en: "Preview only — requires human approval." } as Bilingual,
    body: {
      zh: "前端页面不会批准、执行或修改任何交易。检查通过不代表交易批准。",
      en: "The frontend viewer does not approve, mutate, or execute transactions. Evaluation PASS does not approve a transaction.",
    } as Bilingual,
  },

  // ---- Summary block ----
  summary: {
    defaultHeadline: {
      zh: "预算可用：系统找到一个中锋签约预览。",
      en: "Budget available — the system found a center signing preview.",
    } as Bilingual,
    strictHeadline: {
      zh: "预算受限：系统没有找到符合条件的候选人，因此建议暂不行动，而不是强行操作。",
      en: "Budget too tight — the system recommends holding instead of forcing a move.",
    } as Bilingual,
    defaultBody: {
      zh: "系统预览了以 {salary} / 1 年签下 {player} 的方案。该预览通过了规则检查，但在任何变动之前仍必须由人工确认。",
      en: "The system previewed signing {player} at {salary} for one year. The preview passed rule checks, but a person must still approve before anything changes.",
    } as Bilingual,
    strictBody: {
      zh: "因为预算上限是 $15M，而匹配的中锋候选人薪资高于这个限制，所以系统跳过签约预览并返回 HOLD。不会对阵容做任何改动。",
      en: "Because the budget limit is $15M and the matching center candidate is above that limit, the system skips the signing preview and returns HOLD. No roster change is proposed.",
    } as Bilingual,
  },

  // ---- Status cards ----
  statusCards: {
    proposalLabel: { zh: "方案状态", en: "proposal status" } as Bilingual,
    evaluationLabel: { zh: "检查结果", en: "evaluation status" } as Bilingual,
    approvalLabel: { zh: "人工确认", en: "requires_human_approval" } as Bilingual,
    sampleLabel: { zh: "数据来源", en: "sample_data" } as Bilingual,
    proposalExplain: {
      RECOMMENDED: {
        zh: "系统找到了一个符合当前限制的候选预览。",
        en: "The system found a preview candidate that fits the current constraints.",
      } as Bilingual,
      PARTIAL: {
        zh: "系统找到了一些候选人，但并非所有检查都顺利通过。",
        en: "The system found some candidates, but not all checks passed cleanly.",
      } as Bilingual,
      BLOCKED: {
        zh: "系统找到了候选人，但校验阻止了推荐。",
        en: "The system found candidates, but validation blocked the recommendation.",
      } as Bilingual,
      NO_ACTION: {
        zh: "当前预算和位置条件下没有匹配候选人。",
        en: "No candidate matched the current budget and position filters.",
      } as Bilingual,
    } as Record<string, Bilingual>,
    evaluationExplain: {
      PASS: {
        zh: "方案通过了安全检查，但这不代表交易已经批准。",
        en: "The proposal passed guardrail checks, but this does not approve a transaction.",
      } as Bilingual,
      WARNING: {
        zh: "方案通过但有警告 —— 需要人工复核被标记的项目。",
        en: "The proposal passed with warnings — a person should review the flagged items.",
      } as Bilingual,
      FAIL: {
        zh: "方案未通过一项或多项安全检查，不能直接使用。",
        en: "The proposal failed one or more guardrail checks and must not be used as-is.",
      } as Bilingual,
    } as Record<string, Bilingual>,
    approvalYes: {
      zh: "是。这只是预览，最终必须由人确认。",
      en: "Yes. A person must review and approve before anything changes.",
    } as Bilingual,
    approvalNo: {
      zh: "否。",
      en: "No.",
    } as Bilingual,
    sampleYes: {
      zh: "使用样例 / 模拟数据，不是实时 NBA 数据。",
      en: "This uses demo data, not live NBA data.",
    } as Bilingual,
    sampleNo: {
      zh: "使用真实数据。",
      en: "Uses real data.",
    } as Bilingual,
  },

  // ---- "How the system reached this result" ----
  howSection: {
    title: { zh: "为什么系统会给出这个结果？", en: "How the system reached this result" } as Bilingual,
    hint: {
      zh: "系统按以下顺序运行了一组确定性工具，每一步都可追溯。",
      en: "The system ran a fixed sequence of deterministic tools. Each step is traceable in the audit trail below.",
    } as Bilingual,
    steps: [
      { zh: "检查球队薪资空间", en: "Checked team cap space" } as Bilingual,
      { zh: "分析阵容缺口", en: "Checked roster needs" } as Bilingual,
      { zh: "生成当前深度图", en: "Built current depth chart" } as Bilingual,
      { zh: "筛选自由球员候选人", en: "Ranked free-agent candidates" } as Bilingual,
      { zh: "预览签约是否符合规则", en: "Previewed signing feasibility" } as Bilingual,
      { zh: "检索本地样例证据", en: "Retrieved local sample evidence" } as Bilingual,
      { zh: "运行安全检查", en: "Ran evaluation guardrails" } as Bilingual,
    ] as Bilingual[],
  },

  // ---- Recommended actions ----
  actionsSection: {
    title: { zh: "推荐动作", en: "Recommended Actions" } as Bilingual,
    hint: {
      zh: "每个动作先给出白话结论，再展示完整字段。所有动作都只是预览。",
      en: "Each action shows a plain-language summary first, then full fields. Every action is preview only.",
    } as Bilingual,
    signingPlain: {
      zh: "签约预览：以 {salary} 签下 {player}，补强{position}位置。",
      en: "Preview signing: {player} as a{position} for {salary}.",
    } as Bilingual,
    holdPlain: {
      zh: "当前不建议操作：预算限制下没有匹配候选人，阵容保持不变。",
      en: "No move recommended: keep the roster unchanged because no candidate matched the budget.",
    } as Bilingual,
    tradePlain: {
      zh: "交易预览：涉及 {player}。",
      en: "Preview trade involving {player}.",
    } as Bilingual,
    genericPlain: {
      zh: "预览 {type} 动作。",
      en: "Preview {type} action.",
    } as Bilingual,
    actionLimitations: { zh: "动作限制说明", en: "action limitations" } as Bilingual,
  },

  // ---- Field labels (audit details) ----
  fields: {
    action_id: { zh: "动作 ID", en: "action_id" } as Bilingual,
    action_type: { zh: "动作类型", en: "action_type" } as Bilingual,
    team_id: { zh: "球队", en: "team_id" } as Bilingual,
    player_name: { zh: "球员", en: "player_name" } as Bilingual,
    position: { zh: "位置", en: "position" } as Bilingual,
    salary: { zh: "薪资", en: "salary" } as Bilingual,
    years: { zh: "年限", en: "years" } as Bilingual,
    validation_status: { zh: "规则状态", en: "validation_status" } as Bilingual,
    is_valid: { zh: "是否有效", en: "is_valid" } as Bilingual,
    requires_human_approval: { zh: "是否需要人工确认", en: "requires_human_approval" } as Bilingual,
    fit_score: { zh: "匹配分", en: "fit_score" } as Bilingual,
    matched_need: { zh: "匹配的阵容需求", en: "matched_need" } as Bilingual,
    transaction_id: { zh: "交易预览 ID", en: "transaction_id" } as Bilingual,
    cap_impact_summary: { zh: "薪资空间影响", en: "cap_impact_summary" } as Bilingual,
    roster_impact_summary: { zh: "阵容影响", en: "roster_impact_summary" } as Bilingual,
    depth_chart_impact_summary: { zh: "深度图影响", en: "depth_chart_impact_summary" } as Bilingual,
    evidence_ids: { zh: "关联证据", en: "evidence_ids" } as Bilingual,
    limitations: { zh: "限制说明", en: "limitations" } as Bilingual,
    // Tool trace fields
    tool_name: { zh: "工具名", en: "tool_name" } as Bilingual,
    status: { zh: "状态", en: "status" } as Bilingual,
    input_summary: { zh: "输入摘要", en: "input_summary" } as Bilingual,
    output_summary: { zh: "输出摘要", en: "output_summary" } as Bilingual,
    fallback_reason: { zh: "兜底原因", en: "fallback_reason" } as Bilingual,
    // Risk fields
    code: { zh: "风险代码", en: "code" } as Bilingual,
    level: { zh: "风险等级", en: "level" } as Bilingual,
    summary: { zh: "说明", en: "summary" } as Bilingual,
    // Evidence fields
    title: { zh: "标题", en: "title" } as Bilingual,
    source: { zh: "来源", en: "source" } as Bilingual,
    evidence_type: { zh: "类型", en: "evidence_type" } as Bilingual,
    sample_data: { zh: "样例数据", en: "sample_data" } as Bilingual,
    evidence_id: { zh: "证据 ID", en: "evidence_id" } as Bilingual,
    // Evaluation issue fields
    severity: { zh: "严重程度", en: "severity" } as Bilingual,
    remediation: { zh: "处理建议", en: "remediation" } as Bilingual,
    // Proposal-level fields
    proposal_id: { zh: "方案 ID", en: "proposal_id" } as Bilingual,
    objective: { zh: "目标", en: "objective" } as Bilingual,
    cap_summary: { zh: "薪资空间概览", en: "cap_summary" } as Bilingual,
    roster_need_summary: { zh: "阵容需求概览", en: "roster_need_summary" } as Bilingual,
    depth_chart_summary: { zh: "深度图概览", en: "depth_chart_summary" } as Bilingual,
    fallback_reasons: { zh: "兜底原因列表", en: "fallback_reasons" } as Bilingual,
  } as Record<string, Bilingual>,

  // ---- Empty value placeholders ----
  empty: {
    na: { zh: "不适用", en: "N/A" } as Bilingual,
    none: { zh: "无", en: "(none)" } as Bilingual,
    noEvidence: { zh: "无关联证据", en: "No linked evidence" } as Bilingual,
    noAction: { zh: "不执行操作", en: "No action" } as Bilingual,
  },

  // ---- Bool formatting ----
  bool: {
    yes: { zh: "是", en: "Yes" } as Bilingual,
    no: { zh: "否", en: "No" } as Bilingual,
  },

  // ---- Risks section ----
  risksSection: {
    title: { zh: "风险与提醒", en: "Risks" } as Bilingual,
    hint: {
      zh: "每个风险先给白话解释，再展示原始代码和等级。",
      en: "Each risk shows a plain-language explanation first, then the original code and level.",
    } as Bilingual,
    plain: {
      sample_data: {
        zh: "这个结果使用的是样例 / 模拟数据，不是实时 NBA 数据。",
        en: "This result uses demo/sample data, not live NBA data.",
      } as Bilingual,
      no_matching_candidate: {
        zh: "当前预算和位置条件下没有找到匹配候选人。",
        en: "The current budget and position filters did not match any candidate.",
      } as Bilingual,
      validation_failed: {
        zh: "至少有一个动作没有通过规则引擎的校验。",
        en: "At least one action did not pass the rule engine's validation.",
      } as Bilingual,
      evidence_missing: {
        zh: "方案引用的部分证据无法找到。",
        en: "Some evidence referenced by the proposal could not be found.",
      } as Bilingual,
      cap_pressure: {
        zh: "该动作让球队接近或超过薪资上限阈值。",
        en: "The action pushes the team close to or past a salary cap threshold.",
      } as Bilingual,
    } as Record<string, Bilingual>,
    fallbackPlain: {
      zh: "详见下方说明。",
      en: "See summary for details.",
    } as Bilingual,
  },

  // ---- Evidence section ----
  evidenceSection: {
    title: { zh: "使用了哪些样例证据？", en: "Evidence" } as Bilingual,
    hint: {
      zh: "这里的证据是系统读取的本地样例说明，用来解释为什么产生这个结果。它不是实时新闻，也不是官方交易消息。",
      en: "Evidence here means local sample notes used to explain the result. It is not live news or an official transaction source.",
    } as Bilingual,
    sampleYes: { zh: "样例数据", en: "sample data" } as Bilingual,
    sampleNo: { zh: "真实数据", en: "real data" } as Bilingual,
  },

  // ---- Evaluation issues section ----
  evaluationSection: {
    title: { zh: "安全检查与修复建议", en: "Evaluation Issues & Remediation" } as Bilingual,
    hint: {
      zh: "这里的检查只判断方案是否可以安全展示，不代表交易已经批准。",
      en: "Evaluation here means safety / consistency checks. It does not approve a transaction.",
    } as Bilingual,
    passedChecks: { zh: "通过的检查", en: "Passed checks" } as Bilingual,
    failedChecks: { zh: "未通过的检查", en: "Failed checks" } as Bilingual,
    warnings: { zh: "警告", en: "Warnings" } as Bilingual,
    noIssues: { zh: "没有需要展示的 issue（仅含 INFO 级别提示）。", en: "No issues to display (only INFO-level notes)." } as Bilingual,
    remediationPrefix: { zh: "处理建议：", en: "Remediation: " } as Bilingual,
  },

  // ---- Fallback reasons section ----
  fallbackSection: {
    title: { zh: "兜底原因", en: "Fallback Reasons" } as Bilingual,
    hint: {
      zh: "严格预算场景下，系统没有推荐任何动作。以下是具体原因。",
      en: "In the strict-budget scenario the system did not recommend any action. These are the specific reasons.",
    } as Bilingual,
    strictExplain: {
      zh: "因为预算上限是 $15M，而匹配的中锋候选人薪资高于这个限制，所以系统跳过签约预览并返回 HOLD。",
      en: "Because the budget limit is $15M and the matching center candidate is above that limit, the system skips the signing preview and returns HOLD.",
    } as Bilingual,
  },

  // ---- Limitations section ----
  limitationsSection: {
    title: { zh: "这个演示不会做什么", en: "What this demo does not do" } as Bilingual,
    hint: {
      zh: "以下是安全边界。这些边界由后端测试和前端文案共同保证。",
      en: "These are the safety boundaries, enforced by backend tests and frontend copy.",
    } as Bilingual,
    items: [
      {
        title: { zh: "不会自动批准交易", en: "No auto-approval" } as Bilingual,
        explain: {
          zh: "所有动作都需要人工确认，系统不会自动批准任何交易。",
          en: "Every action requires human approval. The system never auto-approves a transaction.",
        } as Bilingual,
      },
      {
        title: { zh: "不会修改真实阵容", en: "No data mutation" } as Bilingual,
        explain: {
          zh: "前端和后端都不会写入 data/ 下的 JSON 文件。",
          en: "Neither frontend nor backend writes to the JSON files under data/.",
        } as Bilingual,
      },
      {
        title: { zh: "不会调用实时 NBA 数据", en: "No external NBA API" } as Bilingual,
        explain: {
          zh: "所有数据来自本地样例 JSON，不联网。",
          en: "All data comes from local sample JSON. No network calls.",
        } as Bilingual,
      },
      {
        title: { zh: "不会调用 LLM", en: "No LLM" } as Bilingual,
        explain: {
          zh: "不调用 OpenAI / Anthropic / 任何大模型 API。",
          en: "No OpenAI / Anthropic / any LLM API calls.",
        } as Bilingual,
      },
      {
        title: { zh: "不会调用 MCP", en: "No MCP" } as Bilingual,
        explain: {
          zh: "不使用 MCP server / client。",
          en: "No MCP server or client.",
        } as Bilingual,
      },
      {
        title: { zh: "使用样例 / 模拟数据", en: "Sample data only" } as Bilingual,
        explain: {
          zh: "球员、合同、自由球员、证据全部是演示数据。",
          en: "Players, contracts, free agents, and evidence are all demo data.",
        } as Bilingual,
      },
      {
        title: { zh: "所有动作都只是预览", en: "Preview only" } as Bilingual,
        explain: {
          zh: "不会执行任何真实交易操作。",
          en: "No real transaction is executed.",
        } as Bilingual,
      },
      {
        title: { zh: "所有动作都需要人工确认", en: "Requires human approval" } as Bilingual,
        explain: {
          zh: "前端页面不会批准、执行或修改任何交易。",
          en: "The frontend viewer does not approve, mutate, or execute transactions.",
        } as Bilingual,
      },
    ] as { title: Bilingual; explain: Bilingual }[],
    auditTitle: { zh: "完整限制说明（审计）", en: "All limitations (audit)" } as Bilingual,
  },

  // ---- Audit trail (tool trace) ----
  auditSection: {
    title: { zh: "审计追踪：系统实际调用了哪些工具", en: "Audit Trail: Tool Call Trace" } as Bilingual,
    hint: {
      zh: "每个工具先给白话标签，再展示原始工具名和输入输出。evidence_ids 为空时显示「无关联证据」。",
      en: "Each tool shows a plain-language label first, then the original tool name and I/O. Empty evidence_ids show as (none).",
    } as Bilingual,
    toolLabels: {
      "cap_sheet_service.summarize_cap_sheet": {
        zh: "检查球队薪资空间",
        en: "Checked team salary / cap situation",
      } as Bilingual,
      "roster_need_service.evaluate_roster_needs": {
        zh: "分析阵容位置需求",
        en: "Found roster position needs",
      } as Bilingual,
      "depth_chart_projector.project_current_depth_chart": {
        zh: "生成当前深度图",
        en: "Built current depth chart",
      } as Bilingual,
      "free_agent_service.rank_free_agents_for_team": {
        zh: "排序自由球员候选人",
        en: "Ranked matching free agents",
      } as Bilingual,
      "trade_simulator.preview_signing": {
        zh: "预览签约是否可行",
        en: "Previewed whether a signing is valid",
      } as Bilingual,
      "evidence_service.search_evidence": {
        zh: "检索本地样例证据",
        en: "Retrieved local sample evidence",
      } as Bilingual,
    } as Record<string, Bilingual>,
    fallbackPrefix: { zh: "兜底：", en: "Fallback: " } as Bilingual,
  },

  // ---- Proposal-level audit details ----
  proposalAudit: {
    title: { zh: "方案完整字段（审计）", en: "Proposal Details (audit)" } as Bilingual,
  },

  // ---- Agent Console: scenario mode cards (M6-D) ----
  consoleModes: {
    signing: {
      label: { zh: "签约推荐", en: "Signing" } as Bilingual,
      desc: {
        zh: "$20M 预算：预览一个中锋签约方案。",
        en: "$20M budget: preview a center signing.",
      } as Bilingual,
    },
    hold: {
      label: { zh: "预算受限", en: "Strict Budget" } as Bilingual,
      desc: {
        zh: "$15M 预算：找不到候选人，建议暂不行动。",
        en: "$15M budget: no candidate fits, hold.",
      } as Bilingual,
    },
    trade: {
      label: { zh: "模拟交易", en: "Trade Preview" } as Bilingual,
      desc: {
        zh: "预览一笔两队交易，检查薪资配平、阵容人数和交易后深度图变化。",
        en: "Preview a two-team trade: salary matching, roster count, and post-trade depth chart.",
      } as Bilingual,
    },
  } as const,

  // ---- Trade preview scenario (M6-D) ----
  trade: {
    // Output headline
    outputHeadline: {
      zh: "交易预览：系统检查了一笔两队交易，并展示规则结果和交易后阵容影响。",
      en: "Trade preview: the system checked a two-team trade and shows the rule result and post-trade roster impact.",
    } as Bilingual,
    outputPass: {
      zh: "交易通过规则检查：薪资配平满足，阵容人数未超限。",
      en: "Trade passed rule checks: salary matching satisfied, roster count within limit.",
    } as Bilingual,
    outputWarn: {
      zh: "交易通过但有警告 —— 需要人工复核被标记的项目。",
      en: "Trade passed with warnings — a person should review the flagged items.",
    } as Bilingual,
    outputFail: {
      zh: "交易未通过规则检查 —— 不能直接使用。",
      en: "Trade failed rule checks — must not be used as-is.",
    } as Bilingual,

    // Approval boundary
    boundary: {
      zh: "这只是交易预览，不会批准、执行或写入任何交易。",
      en: "This is a trade preview only. It does not approve, execute, or persist any transaction.",
    } as Bilingual,

    // Sections
    teamsTitle: { zh: "交易双方", en: "Trade teams" } as Bilingual,
    assetsTitle: { zh: "交易资产", en: "Trade assets" } as Bilingual,
    outgoingFromA: { zh: "DEM-ATL 送出", en: "Outgoing from DEM-ATL" } as Bilingual,
    outgoingFromB: { zh: "DEM-PDX 送出", en: "Outgoing from DEM-PDX" } as Bilingual,
    incomingToA: { zh: "DEM-ATL 得到", en: "Incoming to DEM-ATL" } as Bilingual,
    incomingToB: { zh: "DEM-PDX 得到", en: "Incoming to DEM-PDX" } as Bilingual,

    ruleCheckTitle: { zh: "规则检查结果", en: "Rule check result" } as Bilingual,
    salaryMatchTitle: { zh: "薪资配平检查", en: "Salary matching" } as Bilingual,
    rosterCheckTitle: { zh: "阵容人数检查", en: "Roster count check" } as Bilingual,

    impactTitle: { zh: "交易后影响", en: "Post-trade impact" } as Bilingual,
    rosterImpactLabel: { zh: "阵容影响", en: "Roster impact" } as Bilingual,
    depthChartImpactLabel: { zh: "深度图影响", en: "Depth chart impact" } as Bilingual,
    capImpactLabel: { zh: "薪资空间影响", en: "Cap impact" } as Bilingual,

    // M7-C: Two-team post-trade view
    twoTeamViewTitle: { zh: "两队交易后视图", en: "Two-team post-trade view" } as Bilingual,
    twoTeamViewHint: {
      zh: "系统同时计算了两队交易后的薪资、阵容需求和深度图。",
      en: "The system calculates post-trade cap, roster needs, and depth chart for both teams.",
    } as Bilingual,
    teamPostTradeTitle: {
      zh: "交易后影响（{team}）",
      en: "Post-trade impact ({team})",
    } as Bilingual,
    teamSectionTitle: {
      zh: "{team} 交易后详情",
      en: "{team} post-trade details",
    } as Bilingual,

    whyApprovalTitle: { zh: "为什么仍需人工确认", en: "Why human approval is still required" } as Bilingual,
    whyApprovalBody: {
      zh: "即使交易通过了规则检查，这仍然只是预览。系统不会自动批准任何交易，所有变动都必须由人工确认后才能执行。",
      en: "Even though the trade passed rule checks, this is still a preview. The system never auto-approves a trade — every change must be confirmed by a person before execution.",
    } as Bilingual,

    risksTitle: { zh: "风险与提醒", en: "Risks" } as Bilingual,
    riskSgGap: {
      zh: "送出 SG 后，DEM-ATL 的 SG 位置出现空缺（深度图显示 SG 无首发）。",
      en: "After sending out the SG, DEM-ATL has no starter at SG (depth chart shows SG empty).",
    } as Bilingual,
    riskSalaryUp: {
      zh: "交易后 DEM-ATL 总薪资上升 $4M（$74M → $78M），但仍在薪资帽以下。",
      en: "Post-trade DEM-ATL total salary rises by $4M ($74M → $78M), but stays under the cap.",
    } as Bilingual,
    riskTeamBCGap: {
      zh: "送出 C（pl-007）后，DEM-PDX 的 C 位出现空缺（深度图显示 C 无首发）。",
      en: "After sending out C (pl-007), DEM-PDX has no starter at C (depth chart shows C empty).",
    } as Bilingual,
    riskTeamBSalaryDown: {
      zh: "交易后 DEM-PDX 总薪资下降 $4M（$74M → $70M），薪资空间更宽裕。",
      en: "Post-trade DEM-PDX total salary drops by $4M ($74M → $70M), freeing cap space.",
    } as Bilingual,
    riskSampleData: {
      zh: "所有球员、合同和薪资均为样例 / 模拟数据，不是真实 NBA 数据。",
      en: "All players, contracts, and salaries are sample / simulation data, not real NBA data.",
    } as Bilingual,

    // Audit details
    auditToggle: { zh: "查看交易审计详情", en: "View trade audit details" } as Bilingual,
    auditToggleHint: {
      zh: "展开后可查看 transaction_id、validation issues、薪资配平明细、cap summary、深度图原始字段和所有限制说明。",
      en: "Expand to see transaction_id, validation issues, salary matching details, cap summary, raw depth chart fields, and all limitations.",
    } as Bilingual,

    // Field labels specific to trade (M8-F2b: plain English, not snake_case)
    transactionId: { zh: "交易预览 ID", en: "Transaction ID" } as Bilingual,
    transactionType: { zh: "交易类型", en: "Transaction type" } as Bilingual,
    validationStatus: { zh: "规则状态", en: "Rule check" } as Bilingual,
    isValid: { zh: "是否通过", en: "Passed" } as Bilingual,
    playerId: { zh: "球员 ID", en: "Player ID" } as Bilingual,
    contractId: { zh: "合同 ID", en: "Contract ID" } as Bilingual,
    assetType: { zh: "资产类型", en: "Asset type" } as Bilingual,
    fromTeam: { zh: "送出方", en: "From" } as Bilingual,
    toTeam: { zh: "接收方", en: "To" } as Bilingual,
    outgoingSalary: { zh: "送出薪资", en: "Sending salary" } as Bilingual,
    incomingSalary: { zh: "得到薪资", en: "Receiving salary" } as Bilingual,
    threshold: { zh: "配平阈值", en: "Matching threshold" } as Bilingual,
    passed: { zh: "是否配平", en: "Salary match" } as Bilingual,
    capBefore: { zh: "交易前薪资概览", en: "Before trade" } as Bilingual,
    capAfter: { zh: "交易后薪资概览", en: "After trade" } as Bilingual,
    totalSalary: { zh: "总薪资", en: "Total salary" } as Bilingual,
    capSpace: { zh: "薪资空间", en: "Cap space" } as Bilingual,
    taxDistance: { zh: "距奢侈税线", en: "Tax line distance" } as Bilingual,
    firstApronDistance: { zh: "距第一土豪线", en: "First apron distance" } as Bilingual,
    secondApronDistance: { zh: "距第二土豪线", en: "Second apron distance" } as Bilingual,
    rosterCount: { zh: "阵容人数", en: "Roster count" } as Bilingual,
    depthChartAfter: { zh: "交易后深度图", en: "Post-trade depth chart" } as Bilingual,
    rosterNeedAfter: { zh: "交易后阵容需求", en: "Post-trade roster needs" } as Bilingual,
    position: { zh: "位置", en: "Position" } as Bilingual,
    starter: { zh: "首发", en: "Starter" } as Bilingual,
    backups: { zh: "替补", en: "Backups" } as Bilingual,
    needLevel: { zh: "需求等级", en: "Need level" } as Bilingual,
    priority: { zh: "优先级", en: "Priority" } as Bilingual,
    currentCount: { zh: "当前人数", en: "Current count" } as Bilingual,
    targetCount: { zh: "目标人数", en: "Target count" } as Bilingual,
    noIssues: { zh: "没有未通过的检查。", en: "No issues — all checks passed." } as Bilingual,
    noWarnings: { zh: "没有警告。", en: "No warnings." } as Bilingual,
    // M8-F2b: direction badges for asset cards
    outBadge: { zh: "送出", en: "Sending out" } as Bilingual,
    inBadge: { zh: "得到", en: "Receiving" } as Bilingual,
    passBadge: { zh: "通过", en: "Pass" } as Bilingual,
    failBadge: { zh: "未通过", en: "Fail" } as Bilingual,
    // M8-F2b: asset type mapping
    playerContractType: { zh: "球员合同", en: "Player contract" } as Bilingual,
    // M8-F2b: priority/need level user-facing labels
    priorityHigh: { zh: "高", en: "High" } as Bilingual,
    priorityMedium: { zh: "中", en: "Medium" } as Bilingual,
    priorityLow: { zh: "低", en: "Low" } as Bilingual,
  } as const,

  // ---- Data source / fallback indicators (M7-B) ----
  dataSource: {
    apiLabel: { zh: "当前数据来源：后端 API", en: "Data source: backend API" } as Bilingual,
    fallbackLabel: {
      zh: "当前数据来源：本地 fallback 样例",
      en: "Data source: local fallback sample",
    } as Bilingual,
    fallbackBanner: {
      zh: "后端 API 不可用，当前显示本地静态样例结果。",
      en: "Backend API unavailable; showing local static sample payload.",
    } as Bilingual,
    fallbackReason: {
      zh: "原因：",
      en: "Reason: ",
    } as Bilingual,
    loadingApi: { zh: "正在调用后端 API…", en: "Calling backend API…" } as Bilingual,
  },

  // ---- Footer ----
  footer: {
    body: {
      zh: "API 优先前端：优先调用本地后端 API，后端不可用时回退到本地静态样例。无 LLM、无 MCP、无外部 NBA API、不修改数据。所有动作都只是预览，需要人工确认。",
      en: "API-first frontend: calls the local backend API first, falls back to local static samples when the backend is unavailable. No LLM, no MCP, no external NBA API, no data mutation. Every action is a preview that requires human approval.",
    } as Bilingual,
    payloadSource: { zh: "数据来源：", en: "Payload source: " } as Bilingual,
  },
  // ---- M8-D1: Dashboard polish ----
  dashboard: {
    // Data source status card
    datasourceTitle: { zh: "数据源状态", en: "Data source status" } as Bilingual,
    backendOnline: { zh: "后端在线", en: "Backend online" } as Bilingual,
    backendOffline: { zh: "后端 API 不可用", en: "Backend API unavailable" } as Bilingual,
    currentData: { zh: "当前使用", en: "Current data" } as Bilingual,
    demoData: { zh: "演示数据", en: "Demo data" } as Bilingual,
    sampleData: { zh: "样例数据", en: "Sample data" } as Bilingual,
    fallbackData: { zh: "本地静态样例", en: "Local static sample" } as Bilingual,
    apiAddr: { zh: "API 地址", en: "API address" } as Bilingual,
    demoDataWarn: {
      zh: "这些球队、球员、薪资和交易结果均为演示数据，不代表真实 NBA 数据。",
      en: "All teams, players, salaries, and trade results are demo data — not real NBA data.",
    } as Bilingual,
    offlineWarn: {
      zh: "正在使用本地静态 fallback 样例。请确认 uvicorn 已启动。",
      en: "Using local static fallback samples. Please confirm uvicorn is running.",
    } as Bilingual,

    // Safety bar
    safetyBarTitle: {
      zh: "只读预览 —— 需要人工确认",
      en: "Read-only preview — requires human approval",
    } as Bilingual,
    safetyBarBody: {
      zh: "系统不会自动执行交易、签约或阵容变更。所有方案只用于预览，必须由人工确认后才可执行。",
      en: "The system does not automatically execute trades, signings, or roster changes. All plans are for preview only and must be confirmed by a person before execution.",
    } as Bilingual,

    // Decision summary
    decisionSummarySigning: {
      zh: "建议：可以预览，但不能自动执行",
      en: "Recommendation: can preview, but cannot auto-execute",
    } as Bilingual,
    decisionSummarySigningBody: {
      zh: "系统找到一个通过规则检查的签约预览；该方案仍需人工确认，且当前数据不是正式 NBA 数据。",
      en: "The system found a signing preview that passed rule checks; the plan still requires human approval, and the current data is not official NBA data.",
    } as Bilingual,
    decisionSummaryHold: {
      zh: "建议：暂不行动",
      en: "Recommendation: hold",
    } as Bilingual,
    decisionSummaryHoldBody: {
      zh: "预算受限，系统没有找到符合条件的候选人。阵容保持不变。当前数据不是正式 NBA 数据。",
      en: "Budget too tight — no matching candidate found. Roster stays unchanged. Current data is not official NBA data.",
    } as Bilingual,
    decisionSummaryTrade: {
      zh: "交易预览：系统检查了一笔两队交易",
      en: "Trade preview: the system checked a two-team trade",
    } as Bilingual,
    decisionSummaryTradeBody: {
      zh: "系统检查了一笔两队交易，并展示规则结果和交易后阵容影响。这只是预览，不会修改任何 roster state。",
      en: "The system checked a two-team trade and shows rule results and post-trade roster impact. This is preview only — no roster state is modified.",
    } as Bilingual,
    tradeIndicatorHeadline: {
      zh: "交易检查结果与指标概览",
      en: "Trade check results & indicator overview",
    } as Bilingual,
    tradeIndicatorBody: {
      zh: "以下指标卡展示规则验证、薪资匹配、人工确认要求和数据来源状态。详细交易资产和两队影响见下方。",
      en: "The indicator cards below show rule validation, salary matching, human approval requirement, and data source status. Detailed trade assets and two-team impact are shown below.",
    } as Bilingual,

    // Indicator cards
    realNbaLabel: { zh: "真实 NBA 数据", en: "Real NBA data" } as Bilingual,
    realNbaNo: { zh: "否", en: "No" } as Bilingual,
    realNbaExplain: {
      zh: "使用 sample/demo 数据",
      en: "Using sample/demo data",
    } as Bilingual,

    // Safety boundary
    safetyBoundaryTitle: { zh: "查看安全边界", en: "View safety boundary" } as Bilingual,
    safetyBoundaryHint: {
      zh: "展开后可查看系统不会做什么、所有限制和安全边界说明。",
      en: "Expand to see what the system does not do, all limitations, and safety boundary details.",
    } as Bilingual,

    // Empty state
    emptyState: {
      zh: "选择场景模式后点击「生成休赛期方案」查看系统建议。",
      en: "Pick a scenario mode and click \"Generate offseason plan\" to see the system recommendation.",
    } as Bilingual,
  } as const,

  // ---- M8-D1: Console Shell layout ----
  consoleShell: {
    // Sidebar navigation
    navHome: { zh: "首页", en: "Home" } as Bilingual,
    navConsole: { zh: "休赛期控制台", en: "Offseason Console" } as Bilingual,
    navCapSheet: { zh: "薪资表", en: "Cap Sheet" } as Bilingual,
    navDepthChart: { zh: "深度图", en: "Depth Chart" } as Bilingual,
    navSettings: { zh: "设置", en: "Settings" } as Bilingual,
    // Sidebar session context
    sessionTitle: { zh: "当前会话", en: "Current session" } as Bilingual,
    sessionTeam: { zh: "球队", en: "Team" } as Bilingual,
    sessionMode: { zh: "模式", en: "Mode" } as Bilingual,
    sessionBudget: { zh: "预算", en: "Budget" } as Bilingual,
    sessionStatus: { zh: "状态", en: "Status" } as Bilingual,
    statusRunning: { zh: "运行中", en: "Running" } as Bilingual,
    statusIdle: { zh: "待机", en: "Idle" } as Bilingual,
    statusComplete: { zh: "已完成", en: "Complete" } as Bilingual,
    // Workspace header
    workspaceTitle: { zh: "Offseason Console", en: "Offseason Console" } as Bilingual,
    workspaceEyebrow: { zh: "休赛期决策", en: "Offseason Decision" } as Bilingual,
    readOnlyBadge: { zh: "只读预览", en: "Read-only preview" } as Bilingual,
    // Inspector sections (M8-F2: Pipeline retitled to user-facing "生成进度")
    inspectorPipeline: { zh: "生成进度", en: "Generation progress" } as Bilingual,
    inspectorIndicators: { zh: "状态指标", en: "Status indicators" } as Bilingual,
    inspectorKeyMetrics: { zh: "关键指标", en: "Key metrics" } as Bilingual,
    inspectorDataSource: { zh: "数据来源", en: "Data source" } as Bilingual,
    // Trade console specific
    tradeMatchup: { zh: "交易对阵", en: "Trade matchup" } as Bilingual,
    tradeSendReceive: { zh: "送出 / 得到", en: "Send / receive" } as Bilingual,
    tradePostImpact: { zh: "交易后影响", en: "Post-trade impact" } as Bilingual,
    tradeWhyApproval: { zh: "为什么仍需人工确认", en: "Why human approval is needed" } as Bilingual,
    // Fit score display (M8-F2: English labels are plain-language, not snake_case)
    fitScoreLabel: { zh: "匹配分", en: "Fit score" } as Bilingual,
    capImpactLabel: { zh: "薪资占用", en: "Cap impact" } as Bilingual,
    riskLevelLabel: { zh: "风险等级", en: "Risk level" } as Bilingual,
    // Inspector indicator labels
    indicatorProposalStatus: { zh: "方案状态", en: "Proposal status" } as Bilingual,
    indicatorEvaluation: { zh: "检查结果", en: "Evaluation" } as Bilingual,
    indicatorHumanApproval: { zh: "人工确认", en: "Human approval" } as Bilingual,
    indicatorDataType: { zh: "数据类型", en: "Data type" } as Bilingual,
    indicatorRealNba: { zh: "真实 NBA", en: "Real NBA" } as Bilingual,
    // Inspector trade indicators
    indicatorValidationStatus: { zh: "验证状态", en: "Validation status" } as Bilingual,
    indicatorSalaryMatch: { zh: "薪资配平", en: "Salary match" } as Bilingual,
  } as const,

  // ---- M8-D4: User-friendly data source display ----
  // Plain-language copy for the data source status card. Engineering
  // fields (snapshot_id, snapshot_type, manual_review_required, etc.)
  // are hidden by default and only surfaced in a collapsed "technical
  // details" section. The main card speaks to a non-technical user.
  userData: {
    // Card title + labels
    cardTitle: { zh: "当前数据", en: "Current Data" } as Bilingual,
    coverageLabel: { zh: "覆盖球队", en: "Coverage" } as Bilingual,
    sourceLabel: { zh: "数据来源", en: "Source" } as Bilingual,
    statusLabel: { zh: "状态", en: "Status" } as Bilingual,
    noteLabel: { zh: "注意", en: "Note" } as Bilingual,
    useCaseLabel: { zh: "适合用途", en: "Best for" } as Bilingual,

    // Demo mode (backend online, DATA_MODE unset/demo)
    demoTitle: { zh: "演示数据", en: "Demo Data" } as Bilingual,
    demoDescription: {
      zh: "用于功能演示，不代表真实 NBA 阵容或薪资",
      en: "For feature demos — does not represent real NBA rosters or salaries",
    } as Bilingual,
    demoStatus: { zh: "可用", en: "Available" } as Bilingual,
    demoCoverage: { zh: "示例球队", en: "Sample teams" } as Bilingual,
    demoSource: { zh: "内置示例", en: "Built-in samples" } as Bilingual,
    demoUseCase: { zh: "功能演示", en: "Feature demos" } as Bilingual,
    demoNote: {
      zh: "所有球员、球队、薪资均为模拟数据。",
      en: "All players, teams, and salaries are simulated.",
    } as Bilingual,

    // Snapshot mode (backend online, DATA_MODE=snapshot, valid snapshot)
    snapshotTitle: { zh: "2025-26 赛季历史数据", en: "2025-26 Season Historical Data" } as Bilingual,
    snapshotDescription: {
      zh: "从公开来源整理的固定历史数据样本",
      en: "A fixed historical sample organized from public sources",
    } as Bilingual,
    snapshotStatus: { zh: "可用于演示和验证", en: "Ready for demo & validation" } as Bilingual,
    snapshotCoverageGswPhx: { zh: "勇士、太阳", en: "Warriors, Suns" } as Bilingual,
    snapshotSourcePublic: {
      zh: "NBA.com / Spotrac 等公开来源",
      en: "NBA.com / Spotrac and other public sources",
    } as Bilingual,
    snapshotUseCase: {
      zh: "演示、验证真实数据管线、查看样例决策",
      en: "Demos, validating the real-data pipeline, sample decisions",
    } as Bilingual,
    snapshotNote: {
      zh: "部分薪资和合同细节仍需人工复核，结果不会自动执行交易或签约。",
      en: "Some salary and contract details still need manual review; results never auto-execute trades or signings.",
    } as Bilingual,
    snapshotNotLive: {
      zh: "这不是实时联网数据，只是一份固定的 2025-26 历史样本，方便稳定演示。",
      en: "This is not live data — just a fixed 2025-26 historical sample for stable demos.",
    } as Bilingual,
    snapshotSampleExplainer: {
      zh: "“历史数据样本”是从公开来源整理下来的一份固定数据版本，用来保证演示和测试结果可复现。",
      en: "A \"historical sample\" is a fixed dataset organized from public sources, used to keep demos and tests reproducible.",
    } as Bilingual,

    // Offline mode (backend unreachable)
    offlineTitle: { zh: "本地备用演示数据", en: "Local Backup Demo Data" } as Bilingual,
    offlineDescription: {
      zh: "后端暂时不可用，页面正在使用前端内置示例",
      en: "Backend temporarily unavailable — page is using built-in samples",
    } as Bilingual,
    offlineStatus: { zh: "离线备用", en: "Offline fallback" } as Bilingual,

    // Collapsible technical details (developer-facing, hidden by default)
    techDetailsToggle: { zh: "查看技术详情", en: "View technical details" } as Bilingual,
    techDetailsHint: {
      zh: "以下为开发者调试用字段，普通用户无需关注。",
      en: "Developer debug fields below — not needed for normal use.",
    } as Bilingual,
    techFieldDataMode: { zh: "data_mode", en: "data_mode" } as Bilingual,
    techFieldSnapshotId: { zh: "snapshot_id", en: "snapshot_id" } as Bilingual,
    techFieldSnapshotType: { zh: "snapshot_type", en: "snapshot_type" } as Bilingual,
    techFieldSampleData: { zh: "sample_data", en: "sample_data" } as Bilingual,
    techFieldWarningsCount: { zh: "warnings count", en: "warnings count" } as Bilingual,
    techFieldActiveDataSource: { zh: "active_data_source", en: "active_data_source" } as Bilingual,
    techFieldSnapshotValid: { zh: "snapshot_valid", en: "snapshot_valid" } as Bilingual,
    techFieldStrictSnapshot: { zh: "strict_snapshot", en: "strict_snapshot" } as Bilingual,
    techFieldFallbackReason: { zh: "fallback_reason", en: "fallback_reason" } as Bilingual,
    techFieldEmpty: { zh: "（空）", en: "(empty)" } as Bilingual,

    // User-friendly inspector indicators (replaces engineering jargon)
    indicatorDataType: { zh: "数据类型", en: "Data type" } as Bilingual,
    indicatorDataTypeDemo: { zh: "演示数据", en: "Demo data" } as Bilingual,
    indicatorDataTypeSnapshot: { zh: "历史真实数据样本", en: "Historical real-data sample" } as Bilingual,
    indicatorDataTypeOffline: { zh: "本地备用", en: "Local backup" } as Bilingual,
    indicatorCompleteness: { zh: "是否完整", en: "Completeness" } as Bilingual,
    indicatorCompletenessDemo: { zh: "示例样本", en: "Sample" } as Bilingual,
    indicatorCompletenessSnapshot: { zh: "小范围样本", en: "Small sample" } as Bilingual,
    indicatorCompletenessOffline: { zh: "示例样本", en: "Sample" } as Bilingual,
    indicatorNeedsReview: { zh: "是否需复核", en: "Needs review" } as Bilingual,
    indicatorNeedsReviewYes: { zh: "需要", en: "Yes" } as Bilingual,
    indicatorNeedsReviewNo: { zh: "不适用", en: "N/A" } as Bilingual,
    indicatorAutoExecute: { zh: "是否会自动执行", en: "Auto-executes" } as Bilingual,
    indicatorAutoExecuteNo: { zh: "不会", en: "No" } as Bilingual,
    indicatorCurrentUse: { zh: "当前用途", en: "Current use" } as Bilingual,
    indicatorCurrentUseDemo: { zh: "功能演示", en: "Feature demo" } as Bilingual,
    indicatorCurrentUseSnapshot: { zh: "演示 / 验证", en: "Demo / validation" } as Bilingual,
    indicatorCurrentUseOffline: { zh: "离线演示", en: "Offline demo" } as Bilingual,
  } as const,

  // ---- M8-E3: Agent execution trace card ----
  // Plain-language copy for the right-side Inspector card that shows
  // the agent's step-by-step execution chain returned by the backend.
  // Engineering fields (tool_name, technical_details, raw inputs/outputs)
  // are hidden by default in a collapsed <details> section. The main
  // card speaks to a non-technical user.
  agentTrace: {
    // Card title + subtitle  (M8-F2: renamed to plain-language "方案生成过程")
    cardTitle: { zh: "方案生成过程", en: "How this preview was built" } as Bilingual,
    cardSubtitle: {
      zh: "下面是从理解需求到生成预览、等待你确认的完整过程。",
      en: "This shows how the preview was built, from understanding your request to awaiting your confirmation.",
    } as Bilingual,

    // Empty state (no proposal/trade run yet)
    emptyState: {
      zh: "运行一次签约建议或交易预览后，这里会显示助手执行链路。",
      en: "Run a signing recommendation or trade preview to see the assistant steps.",
    } as Bilingual,

    // Fallback when API didn't return agent_trace
    fallbackTitle: { zh: "未返回助手链路", en: "No assistant trace" } as Bilingual,
    fallbackBody: {
      zh: "当前结果没有返回助手链路，页面仍显示原有预览。",
      en: "This result did not include an assistant trace, so the original preview is still shown.",
    } as Bilingual,

    // Empty steps
    emptySteps: {
      zh: "助手链路为空，但预览结果仍可查看。",
      en: "The assistant trace is empty, but the preview result is still available.",
    } as Bilingual,

    // Run-level summary labels
    labelCurrentState: { zh: "当前状态", en: "Current state" } as Bilingual,
    labelDataSource: { zh: "数据来源", en: "Data source" } as Bilingual,
    labelHumanApproval: { zh: "需要人工确认", en: "Human approval" } as Bilingual,
    labelFinalMessage: { zh: "结束提示", en: "Final note" } as Bilingual,

    // Human approval values
    approvalRequired: { zh: "需要", en: "Required" } as Bilingual,
    approvalNotRequired: { zh: "不需要", en: "Not required" } as Bilingual,

    // Step-level labels
    labelEvidence: { zh: "证据", en: "Evidence" } as Bilingual,
    labelWarnings: { zh: "提醒", en: "Warnings" } as Bilingual,
    labelNeedsReview: { zh: "需人工复核", en: "Needs review" } as Bilingual,

    // Step status badges (plain language, not engineering jargon)
    // M8-F1: "blocked" displays as "已安全拦截" per user-facing requirement.
    statusCompleted: { zh: "已完成", en: "Completed" } as Bilingual,
    statusWarning: { zh: "有提醒", en: "Has warning" } as Bilingual,
    statusBlocked: { zh: "已安全拦截", en: "Safely blocked" } as Bilingual,
    statusRunning: { zh: "运行中", en: "Running" } as Bilingual,
    statusPending: { zh: "等待中", en: "Pending" } as Bilingual,
    statusUnknown: { zh: "未知", en: "Unknown" } as Bilingual,

    // Collapsible technical details
    techToggle: { zh: "查看技术详情", en: "View technical details" } as Bilingual,
    techToggleHide: { zh: "隐藏技术详情", en: "Hide technical details" } as Bilingual,
    techHint: {
      zh: "以下为开发者调试用字段，普通用户无需关注。",
      en: "Developer debug fields below — not needed for normal use.",
    } as Bilingual,
    techFieldToolName: { zh: "tool_name", en: "tool_name" } as Bilingual,
    techFieldInputs: { zh: "inputs_summary", en: "inputs_summary" } as Bilingual,
    techFieldOutputs: { zh: "outputs_summary", en: "outputs_summary" } as Bilingual,
    techFieldDetails: { zh: "technical_details", en: "technical_details" } as Bilingual,
    techFieldEvidenceIds: { zh: "evidence_ids", en: "evidence_ids" } as Bilingual,
    techFieldEmpty: { zh: "（空）", en: "(empty)" } as Bilingual,

    // Read-only disclaimer (mirrors backend final_message)
    readOnlyNote: {
      zh: "这是只读预览，不会自动执行。",
      en: "This is a read-only preview; nothing is auto-executed.",
    } as Bilingual,
  } as const,
} as const;

// ---- Helper: format salary ----
export function formatSalary(salary: number | null, lang: Lang): string {
  if (salary === null) return copy.empty.na[lang];
  return `$${salary.toLocaleString("en-US")}`;
}

// ---- Helper: format bool ----
export function formatBool(value: boolean, lang: Lang): string {
  return value ? copy.bool.yes[lang] : copy.bool.no[lang];
}

// ---- Helper: empty value ----
export function orNa(value: string | null | undefined, lang: Lang): string {
  if (value === null || value === undefined || value === "") return copy.empty.na[lang];
  return value;
}

export function orNone(value: string | null | undefined, lang: Lang): string {
  if (value === null || value === undefined || value === "") return copy.empty.none[lang];
  return value;
}

export function evidenceIdsText(ids: string[], lang: Lang): string {
  if (!ids || ids.length === 0) return copy.empty.noEvidence[lang];
  return ids.join(", ");
}
