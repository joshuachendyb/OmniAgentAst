# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-16 小欧 新增: 锚定摘要固定结构模板(借鉴 opencode SUMMARY_TEMPLATE)
#   2026-08-17 小健 对齐设计文档 14.9.4①: 模板六段固定结构, 供 C4 generate_anchored_summary/generate_chunked_summary 复用
# 2026-10-26 小沈 - 段名与顺序对齐 opencode: Critical Context→Important Details(改名), Progress 子项 Done→Completed, 删 Next Steps, 增 Summary(成功/失败情况); Goal/Key Decisions/Relevant Files 保留 — 小沈-2026-10-26
# 2026-10-27 小欧 - 文案统一: previousSummary 改为 [往次摘要], 与 summary.py 的 assistant 注入方式一致
"""compaction.summary_prompt — C4 摘要模板 — 小欧 2026-08-16 / 小健 2026-08-17

职责(单一职责): 仅承载「锚定摘要固定结构模板」。不包含任何压缩/裁剪业务逻辑。
依据: [4] 14.9.4①(compaction.ts:43-78) —— 强制输出 Markdown 结构六段, 保留精确文件路径/命令/
      错误串/标识符, 用简短 bullet 不用长段落, 不提及压缩过程本身。
"""
SUMMARY_TEMPLATE = """你是专业的汇总分析助手。
根据**历史对话数据**。
铁规:严格按照下面的格式顺序输出六段 Markdown 摘要. 

- Goal: [one or two brief sentences describing what the user is trying to accomplish]
- Key Decisions: 关键决策与结论
- Important Details: [constraints/preferences, decisions and why, important facts/assumptions, exact context needed to continue, or "(none)"]
- Progress:
  [1] Completed: [finished work, verified facts, or changes made; otherwise "(none)"]
  [2] InProgress: [current work, partial changes, or investigation state; otherwise "(none)"]
  [3] Blocked: [blockers, failing commands, or unknowns; otherwise "(none)"]
- Summary: 前一段工作总结(成功情况/失败情况)
- Relevant Files: [file or directory path: why it matters, or "(none)"]
如果提供了[往次摘要]，请基于它增量更新摘要: 保留仍然成立的结论, 合并新发现, 删除过期或已被纠正的信息, 不重复不遗漏。"""