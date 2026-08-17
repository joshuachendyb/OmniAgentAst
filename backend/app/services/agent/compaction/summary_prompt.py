# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-16 小欧 新增: 锚定摘要固定结构模板(借鉴 opencode SUMMARY_TEMPLATE)
#   2026-08-17 小健 对齐文档4 14.9.4①: 模板六段固定结构, 供 C4 generate_anchored_summary/generate_chunked_summary 复用
"""compaction.summary_prompt — C4 摘要模板 — 小欧 2026-08-16 / 小健 2026-08-17

职责(单一职责): 仅承载「锚定摘要固定结构模板」。不包含任何压缩/裁剪业务逻辑。
依据: [4] 14.9.4①(compaction.ts:43-78) —— 强制输出 Markdown 结构六段, 保留精确文件路径/命令/
      错误串/标识符, 用简短 bullet 不用长段落, 不提及压缩过程本身。
"""
SUMMARY_TEMPLATE = """将 messages 归档为固定结构 Markdown 摘要:
- Goal: 当前任务目标
- Key Decisions: 关键决策与结论
- Next Steps: 下一步计划
- Critical Context: 不可或缺的上下文(文件路径/关键数据)
- Relevant Files: 涉及文件清单
- Progress: 已完成(Done)/进行中(InProgress)/受阻(Blocked)
若已有 previousSummary, 请增量合并(保留已有结论, 追加新发现), 不重复不遗漏。"""