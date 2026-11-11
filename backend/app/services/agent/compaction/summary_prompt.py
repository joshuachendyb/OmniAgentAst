# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-16 小欧 新增: 锚定摘要固定结构模板(借鉴 opencode SUMMARY_TEMPLATE)
#   2026-08-17 小健 对齐设计文档 14.9.4①: 模板六段固定结构, 供 C4 generate_anchored_summary/generate_chunked_summary 复用
# 2026-10-26 小沈 - 段名与顺序对齐 opencode: Critical Context→Important Details(改名), Progress 子项 Done→Completed, 删 Next Steps, 增 Summary(成功/失败情况); Goal/Key Decisions/Relevant Files 保留 — 小沈-2026-10-26
# 2026-10-27 小欧 - 文案统一: previousSummary 改为 [往次摘要], 与 summary.py 的 assistant 注入方式一致
# 2026-11-01 小欧 - 七段重构(北京老陈亲定段名与顺序): ①Goal→Previous Task Goal ②Key Decisions→Task Plan and Decisions
#   ③新增 Important Context 独立段 ④顺序定音: Previous Task Goal→Task Plan and Decisions→Important Details→Progress→Summary→Important Context→Relevant Files
#   (Context 处 Summary 收束与 Relevant Files 载体之间, Summary(收束过去)→Context(面向未来延续)→Files(延续所需载体) 续聊动线)
#   ⑤描述全英文重写(对齐 opencode 形态); 分工重切防两段串义: 决策理由("decisions and why")自 Details 挪入 Task Plan and Decisions,
#   "exact context needed to continue" 自 Details 挪入 Important Context; [往次摘要] 标签字面不译(summary.py 注入字面一致) — 小欧-2026-11-01
# 2026-11-01 小欧 - 头部指令段回退中文(北京老陈令): 角色句/铁规句保持原中文形态(10-07 实测100%命中载体, 仅六段→七段数量词联动),
#   各段字段描述维持英文定音不变; 末尾增量指令句同回退中文(与头部同属指令段, 不拆二态) — 小欧-2026-11-01
"""compaction.summary_prompt — C4 摘要模板 — 小欧 2026-08-16 / 小健 2026-08-17

职责(单一职责): 仅承载「锚定摘要固定结构模板」。不包含任何压缩/裁剪业务逻辑。
依据: [4] 14.9.4①(compaction.ts:43-78) —— 强制输出 Markdown 结构七段, 保留精确文件路径/命令/
      错误串/标识符, 用简短 bullet 不用长段落, 不提及压缩过程本身。
2026-11-01 小欧: 六段→七段(段名/顺序/描述 北京老陈亲定); 段名变更必同步 summary.py _SUMMARY_SECTIONS。
"""
SUMMARY_TEMPLATE = """你是专业的汇总分析助手。
根据**历史对话数据**。
铁规:严格按照下面的格式顺序输出七段 Markdown 摘要.

- Previous Task Goal: [one or two brief sentences describing the goal/requirements of the previous task]
- Task Plan and Decisions: [the task plan, key decisions made and why; or "(none)"]
- Important Details: [constraints, preferences, important facts/assumptions; or "(none)"]
- Progress:
  [1] Completed: [finished work, verified facts, or changes made; otherwise "(none)"]
  [2] InProgress: [current work, partial changes, or investigation state; otherwise "(none)"]
  [3] Blocked: [blockers, failing commands, or unknowns; otherwise "(none)"]
- Summary: [brief wrap-up of the previous round of work — what succeeded, what failed]
- Important Context: [exact context needed to continue the work — working environment state, pending dependencies, unresolved questions, anything the next session must know; or "(none)"]
- Relevant Files: [file or directory path: why it matters, or "(none)"]
如果提供了[往次摘要]，必须基于增量信息重写全部摘要: 务必删除过期或已被纠正的信息, 不重复不遗漏。"""
#
