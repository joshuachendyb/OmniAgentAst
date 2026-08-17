# -*- coding: utf-8 -*-
"""compaction.compaction_constants — 消息压缩/裁剪专属常量 — 小健 2026-08-17

职责(单一职责): 仅承载「消息压缩/裁剪」业务域常量 + 复用全局系统常量(DRY, 不重写)。
依据: doc-8月优化/[4]对话-HistoryMemory与历史裁剪设计方案 v5.10(14.9.2「压缩专属常量不堆进 app/constants.py」
      + 第八章节常量表 + 14.9.3 trigger 代码 import 全局缓冲常量)。设计文档: 10.1.8 S5 C4+compaction 全模块。

与 app/constants.py 边界(DRY 不重复):
  全局系统常量 MAX_CONTEXT_TOKENS/MAX_CONTEXT_RATIO/COMPACTION_BUFFER/CHARS_PER_TOKEN 定义在 app/constants.py
  (react_cycle/message_builder 既有引用), 本法仅 re-export 供 compaction 模块用, 不重复定义;
  其余「压缩裁剪专属」常量(PRUNE_*/SUMMARY_*/TRIGGER_*/COOLDOWN_*/TAIL_*/SPLIT_*/ASSEMBLE_*)定义在本文件。

编辑历史:
# 格式规范: {日期} {署名} {修改内容}
  2026-08-17 小健 新建: 压缩裁剪专属常量 + re-export 全局缓冲常量(DRY, 不重复 app/constants)
  2026-08-17 小健 修正: 移除本文件自实现的 preserve_recent_budget(与 split_turn.py 权威版本重复, DRY 违反),
                       保尾预算实现收敛到 split_turn.preserve_recent_budget([4] 14.9.7)
"""
from app.constants import (  # noqa: F401 — re-export 全局缓冲常量, 供 compaction 模块复用(DRY)
    MAX_CONTEXT_RATIO,
    MAX_CONTEXT_TOKENS,
    COMPACTION_BUFFER,
)
from app.constants import CHARS_PER_TOKEN  # noqa: F401 — token 估算系数

# ---- C4 接入开关(10.1.8 S5, R4 前置) ———————————————————————————————
# R4 是「零额外 LLM 调用」原则; C4(锚定摘要)每次压缩需 1 次 LLM 调用, 故需放开 R4 才能接入主链路。
# 文档1 10.1.8 口径: R4 未放开前 _needs_compact 不置位, 行为同现状不退化。
# 北京老陈未拍板放开 R4 前保持 False; 放开后置 True 即 C4 接入生效。 — 小健 2026-08-17
COMPACTION_ENABLED = False

# ---- 触发比例(C3 轻量/T1 紧急裁剪, [4] 第八章节) ———————————————————————————
TRIGGER_T1_RATIO = 0.50   # C3 的轻量实现函数 t1_compress_observations 触发比例
TRIGGER_T3_RATIO = 0.95   # T1 紧急裁剪法(触发比例, 窗口快爆最后安全网)
TRIM_TARGET_RATIO = 0.50  # 裁剪目标比例
KEEP_TAIL_ROUNDS = 3      # 保尾轮数(T1: 保留最近 3 轮完整 FC 对, [4] 5.2 步骤4)

# ---- 剪枝(C3/Prune) ———————————————————————————————
PRUNE_MINIMUM_TOKENS = 20000   # 剪枝/T1 最少需释放 token, 否则跳过(借鉴 OpenCode PRUNE_MINIMUM, [4] 第八章节)
PRUNE_PROTECT_TOKENS = 40000   # prune 保护近期工具输出细节的 token 阈值([4] 14.3.3; prune.py 引用 _TOKENS 权威名)

# ---- Hermes Pass3 参数截断(T1 步骤2, [4] 5.2/第八章节) ————————————————————
PASS3_ARGS_THRESHOLD = 500   # tool_call 参数超过此长度才截断
PASS3_ARG_MAX_CHARS = 200    # 截断后字符串字段最大长度

# ---- 锚定摘要(C4/Anchored Summary) ——————————————————
SUMMARY_FEED_MAX_CHARS = 2000  # 喂 LLM 的单条 tool content 截断上限字符(防二次胀窗, [4] 14.9.4②「截断喂」)

# ---- 触发(Trigger) ——————————————————————————————
TRIGGER_MAX_MSGS = 80  # 窗口触发备用消息数阈值(大窗口模型下消息数兜底触发, [4] 14.9.6 K1)

# ---- 冷却(Cooldown) ——————————————————————————————
COOLDOWN_ROUNDS = 2  # 压缩后冷却轮次(防连续轮次反复压缩抖动, 尤其 C4 每次 1 次 LLM 调用, [4] 14.9.6 K2)

# ---- 保尾切分(Split-Turn) ————————————————————————
TAIL_TOKEN_RATIO = 0.25      # 保尾窗口占可用预算比例(14.3.2 preserveRecentBudget 用 usable*0.25)
TAIL_TOKEN_MIN = 2000        # 保尾预算下限(14.3.2 select: max(2000, usable*0.25))
TAIL_TOKEN_MAX = 8000        # 保尾预算上限(14.3.2 select: min(8000, ...))
SPLIT_TURN_MAX_ASSISTANT_CHARS = 4000  # 半轮劈分: 单条消息内容超此上限则截断([4] 14.9.2 splitTurn)

# ---- 装配线(Assembler) ————————————————————————————
ASSEMBLE_KEEP_TAIL = 1  # 注入摘要后保留的尾部最新消息条数(默认保最新 task 一条)