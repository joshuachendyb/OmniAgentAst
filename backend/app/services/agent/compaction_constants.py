# -*- coding: utf-8 -*-
"""app.services.agent.compaction_constants — 消息压缩/裁剪专属常量 — 小健 2026-08-17

职责(单一职责): 承载「消息压缩/裁剪」业务域全部常量——原全局压缩/裁剪常量(MAX_CONTEXT_TOKENS 等 5 个)
2026-08-17 从 app/constants.py 迁入本文件(归属随用方集中到 agent/compaction 域), 不重复定义(DRY)。
依据: doc-8月优化/[4]对话-HistoryMemory与历史裁剪设计方案 v5.10(14.9.2「压缩专属常量不堆进 app/constants.py」
      + 第八章节常量表 + 14.9.3 trigger 代码 import 全局缓冲常量)。设计文档: 10.1.8 S5 C4+compaction 全模块。

与 app/constants.py 边界(DRY 不重复):
  压缩/裁剪核心阈值本文件权威定义(自 app/constants.py 迁入 2026-08-17):
    MAX_CONTEXT_TOKENS/MAX_CONTEXT_RATIO/COMPACTION_BUFFER/CHARS_PER_TOKEN/TEMP_HISTORY_CHAR_LIMIT
  其余「压缩裁剪专属」常量(PRUNE_*/SUMMARY_*/TRIGGER_*/COOLDOWN_*/TAIL_*/SPLIT_*/ASSEMBLE_*)亦定义在本文件。
  app/constants.py 不再承载压缩/裁剪相关常量。

编辑历史:
# 格式规范: {日期} {署名} {修改内容}
  2026-08-17 小健 新建: 压缩裁剪专属常量 + re-export 全局缓冲常量(DRY, 不重复 app/constants)
  2026-08-17 小健 补全: 每常量注释补全意义/默认值依据/可选范围(043ed9c54)
  2026-08-17 小健 改名: TRIGGER_T1_RATIO 注释同步 compress_long_tool_output(旧 t1_compress_observations 已改名)
  2026-08-17 小健 修正: 移除本文件自实现的 preserve_recent_budget(与 split_turn.py 权威版本重复, DRY 违反),
                       保尾预算实现收敛到 split_turn.preserve_recent_budget([4] 14.9.7)
  2026-08-17 小健 重构(北京老陈驱动): 压缩/裁剪核心阈值本色权威定义——MAX_CONTEXT_TOKENS/MAX_CONTEXT_RATIO/
                        COMPACTION_BUFFER/CHARS_PER_TOKEN/TEMP_HISTORY_CHAR_LIMIT 自 app/constants.py 迁入本文件,
                        由 re-export 改为直接 define(与用方同域, 消除跨层引用)
  2026-08-17 小健 移址: 自 compaction/ 包内迁至 agent/ 层根(compaction_constants.py)——因 message_builder 导入本文件会
                        触发 compaction/__init__→assembler→split_turn→message_builder 循环导入, 迁出 compaction 包避开
                        __init__ 重链; 全部引用方(start_step/message_builder/compaction 各模块)导入路径同步更新
"""
# ============================================================
# A. 压缩/裁剪核心阈值(自 app/constants.py 第4节迁入, 2026-08-17) — 小健
# ============================================================
# 意义: 上下文总体 Token 上限(默认值, 配置可覆盖 = MessageBuilder 构造默认/max_tokens)
MAX_CONTEXT_TOKENS = 200000
# 意义: 裁剪绝对值安全网触发比例(默认80%, 历史占满此比例即触发)
MAX_CONTEXT_RATIO = 0.8
# 意义: 输出预留缓冲区(OpenCode 式, 用于增量触发和预算裁剪)
COMPACTION_BUFFER = 20000
# 意义: chars→token 换算系数
CHARS_PER_TOKEN = 4
# 意义: 临时历史字符上限
TEMP_HISTORY_CHAR_LIMIT = 50000

# ---- C4 接入开关(10.1.8 S5, R4 前置) ———————————————————————————————
# 意义: 控制 C4 锚定摘要是否接入主链路。False=行为同现状(trim_history 原逻辑), True=历史超窗时 await 摘要回填。
# 默认值依据: R4「零额外 LLM 调用」原则未放开前必须 False, 防意外烧 LLM; 北京老陈未拍板前保持 False。
# 可选范围: 仅 False/True 二值; 放开 R4 后置 True 即生效。 — 小健 2026-08-17
COMPACTION_ENABLED = False

# ---- 触发比例(C3 轻量/T1 紧急裁剪, [4] 第八章节) ———————————————————————————
# 意义: TRIGGER_T1_RATIO/compress_long_tool_output 触发阈值; TRIGGER_T3_RATIO/keep_valuable_messages 紧急裁剪最后安全网;
#       TRIM_TARGET_RATIO/裁剪到目标占用比例; KEEP_TAIL_ROUNDS/保尾完整 FC 轮数。
# 默认值依据: 借鉴 opencode/历史方案口径(50% 常规触发、95% 濒危安全网、保留最近 3 轮)。
# 可选范围: 比例取 (0,1), 越大越迟触发; 建议常规 0.4~0.6、安全网 0.9~0.98; KEEP_TAIL_ROUNDS 取 1~5 轮。
TRIGGER_T1_RATIO = 0.50   # C3 的轻量实现函数 compress_long_tool_output 触发比例
TRIGGER_T3_RATIO = 0.95   # T1 紧急裁剪法(触发比例, 窗口快爆最后安全网)
TRIM_TARGET_RATIO = 0.50  # 裁剪目标比例
KEEP_TAIL_ROUNDS = 3      # 保尾轮数(T1: 保留最近 3 轮完整 FC 对, [4] 5.2 步骤4)

# ---- 剪枝(C3/Prune) ———————————————————————————————
# 意义: PRUNE_MINIMUM_TOKENS/剪枝至少需释放的 token, 不足则跳过防抖动; PRUNE_PROTECT_TOKENS/保护近期工具输出细节阈值。
# 默认值依据: 借鉴 OpenCode PRUNE_MINIMUM([4] 第八章节), 与 20K/40K 量级匹配常规消息体积。
# 可选范围: 越小越激进(更易触发剪枝); 过小(如 <5K)易反复裁剪抖动, 过大(如 >100K)则剪枝失效。
PRUNE_MINIMUM_TOKENS = 20000   # 剪枝/T1 最少需释放 token, 否则跳过(借鉴 OpenCode PRUNE_MINIMUM, [4] 第八章节)
PRUNE_PROTECT_TOKENS = 40000   # prune 保护近期工具输出细节的 token 阈值([4] 14.3.3; prune.py 引用 _TOKENS 权威名)

# ---- Hermes Pass3 参数截断(T1 步骤2, [4] 5.2/第八章节) ————————————————————
# 意义: PASS3_ARGS_THRESHOLD/tool_call 参数超此长度才截断; PASS3_ARG_MAX_CHARS/截断后字符串字段最大长度。
# 默认值依据: Hermes 2 Pass3 原文参数截断口径(500/200 字符)。
# 可选范围: 阈值过低会误伤关键参数, 建议 300~800; 截断长度建议 100~300(须保留命令可读)。
PASS3_ARGS_THRESHOLD = 500   # tool_call 参数超过此长度才截断
PASS3_ARG_MAX_CHARS = 200    # 截断后字符串字段最大长度

# ---- 锚定摘要(C4/Anchored Summary) ——————————————————
# 意义: SUMMARY_FEED_MAX_CHARS/喂 LLM 的单条 tool content 截断上限字符(防二次胀窗)。
# 默认值依据: 2000 字符足以承载工具返回关键信息又不撑大上下文([4] 14.9.4②「截断喂」)。
# 可选范围: 越小越省 token 但可能丢细节, 越大越保真但增加 LLM 输入; 建议 1000~5000。
SUMMARY_FEED_MAX_CHARS = 2000  # 喂 LLM 的单条 tool content 截断上限字符(防二次胀窗, [4] 14.9.4②「截断喂」)

# ---- 触发(Trigger) ——————————————————————————————
# 意义: TRIGGER_MAX_MSGS/大窗口模型下消息数兜底触发阈值(防超大窗口固定比例形同虚设)。
# 默认值依据: 80 条消息为常规长对话合理上限([4] 14.9.6 K1)。
# 可选范围: 越小越易触发, 越大越宽松; 建议 50~150。
TRIGGER_MAX_MSGS = 80  # 窗口触发备用消息数阈值(大窗口模型下消息数兜底触发, [4] 14.9.6 K1)

# ---- 冷却(Cooldown) ——————————————————————————————
# 意义: COOLDOWN_ROUNDS/压缩后冷却轮次, 防连续轮次反复压缩抖动(尤其 C4 每次 1 次 LLM 调用)。
# 默认值依据: 2 轮冷却足以避开连续触发又不延迟过度([4] 14.9.6 K2)。
# 可选范围: 0=每次评估不冷却, 越大越保守(降 LLM 成本但压缩滞后); 建议 1~5。
COOLDOWN_ROUNDS = 2  # 压缩后冷却轮次(防连续轮次反复压缩抖动, 尤其 C4 每次 1 次 LLM 调用, [4] 14.9.6 K2)

# ---- 保尾切分(Split-Turn) ————————————————————————
# 意义: TAIL_TOKEN_RATIO/保尾窗口占可用预算比例; TAIL_TOKEN_MIN/MAX/保尾预算上下限夹取;
#       SPLIT_TURN_MAX_ASSISTANT_CHARS/半轮劈分单条消息截断上限。
# 默认值依据: 对齐 opencode 14.3.2 select 的 preserveRecentBudget(max(2000, usable*0.25), 上限 8000)。
# 可选范围: 比例取 (0,1)(建议 0.2~0.3); MIN 建议 1000~4000; MAX 建议 4000~16000;
#       劈分上限建议 2000~8000(过低截掉命令可读)。
TAIL_TOKEN_RATIO = 0.25      # 保尾窗口占可用预算比例(14.3.2 preserveRecentBudget 用 usable*0.25)
TAIL_TOKEN_MIN = 2000        # 保尾预算下限(14.3.2 select: max(2000, usable*0.25))
TAIL_TOKEN_MAX = 8000        # 保尾预算上限(14.3.2 select: min(8000, ...))
SPLIT_TURN_MAX_ASSISTANT_CHARS = 4000  # 半轮劈分: 单条消息内容超此上限则截断([4] 14.9.2 splitTurn)

# ---- 装配线(Assembler) ————————————————————————————
# 意义: ASSEMBLE_KEEP_TAIL/注入摘要后保留的尾部最新消息条数(防摘要顶掉最新 task)。
# 默认值依据: 保最新 1 条 task 即可维持对话意图([4] 14.5/10.1.7⑤)。
# 可选范围: 0=只留摘要不保尾; 建议 1~3。
ASSEMBLE_KEEP_TAIL = 1  # 注入摘要后保留的尾部最新消息条数(默认保最新 task 一条)