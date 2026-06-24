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
    eyebrow: { zh: "休赛期方案生成工作台", en: "Offseason Plan Console" } as Bilingual,
    title: { zh: "休赛期方案生成工作台", en: "Offseason Plan Console" } as Bilingual,
    lede: {
      zh: "选择目标和预算，预览系统会如何检查薪资、阵容需求、候选人和规则，最后生成一个可审计的休赛期方案。这是一个静态 demo：点击生成会在两份本地样例结果之间切换，不调用后端 API。",
      en: "Pick a target and budget, then preview how the system checks cap space, roster needs, candidates, and rules to produce an auditable offseason plan. This is a static demo: clicking generate switches between two local sample results — no backend API call.",
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
      zh: "当前为静态 demo：点击生成会在两份本地样例结果之间切换，不调用后端 API。",
      en: "Static demo: clicking generate switches between two local sample results. No backend API call.",
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
      zh: "以下是 Agent 按顺序执行的检查流程。本次为静态 demo，点击生成后所有步骤会标记为已完成。",
      en: "The agent runs these checks in order. This is a static demo — after clicking generate, all steps are marked complete.",
    } as Bilingual,
    steps: [
      { zh: "读取球队薪资空间", en: "Read team cap space" } as Bilingual,
      { zh: "分析阵容缺口", en: "Analyze roster needs" } as Bilingual,
      { zh: "匹配自由球员", en: "Match free agents" } as Bilingual,
      { zh: "预览签约规则", en: "Preview signing rules" } as Bilingual,
      { zh: "检索样例证据", en: "Retrieve sample evidence" } as Bilingual,
      { zh: "运行安全检查", en: "Run guardrail checks" } as Bilingual,
      { zh: "生成方案", en: "Build proposal" } as Bilingual,
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

  // ---- Footer ----
  footer: {
    body: {
      zh: "这是一个静态前端查看器。它渲染 CLI JSON 输出的快照，不调用任何后端 API。无 LLM、无 MCP、无外部 NBA API、不修改数据。所有动作都只是预览，需要人工确认。",
      en: "This is a static frontend viewer. It renders a snapshot of the CLI JSON output and does not call any backend API. No LLM, no MCP, no external NBA API, no data mutation. Every action is a preview that requires human approval.",
    } as Bilingual,
    payloadSource: { zh: "数据来源：", en: "Payload source: " } as Bilingual,
  },
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
