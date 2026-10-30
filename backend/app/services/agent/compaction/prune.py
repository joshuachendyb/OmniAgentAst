# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-16 小欧 新增: C3 剪枝引擎 prune_tool_outputs(借鉴 opencode prune, 纯规则零 LLM)
#   2026-08-16 小欧 新增: t1_reuse_summary(复用工具层 llm_data.summary) + value_first_prune(按价值权重保留)
#   2026-08-17 小健 落地: 四函数合并 prune.py, 常量自 agent.compaction_constants(DRY)
#                        t1_compress_observations 实现为通用字符串级摘要兜底(去 per-tool 模板过度设计,
#                        14.9.6 明示 t1_reuse_summary 强推荐替代逐工具模板; 本版为无 _summary 时的兜底)
#   2026-08-17 小健 补全: 各函数 docstring 补全适用场景/使用方法/前置条件/输入输出, 常量注释补意义/依据/可选范围
#                        (043ed9c54, 对齐老陈函数名符其实要求), 并清除模块头"三堂会审"残留措辞
#   2026-08-17 小健 改名: 8 函数名符其实——prune_tool_outputs→clear_tool_outputs, t1_reuse_summary→use_tool_summary,
#                        t1_compress_observations→compress_long_tool_output, value_first_prune→keep_valuable_messages;
#                        模块级注释/函数关系/设计文档引用同步, 编辑历史保留原名(历史事实)
#   2026-08-17 小健 常量归属迁移(北京老陈驱动): 压缩/裁剪常量权威迁至 agent 层根 compaction_constants.py, 本模块导入路径由 compaction.compaction_constants 改为 app.services.agent.compaction_constants
#   2026-10-04 小欧 CHARS_PER_TOKEN 改浮点(1.8)后两处 `// c` 返回 float, 改 int(x / c) 与 MessageBuilder 同口径
#   2026-10-08 小欧 摘要降本接线 + 两处修复(单测实测暴露, 非风格调整):
#     ①新增 prune_tool_output_keeping_tail(messages, tail_start): 保尾区 tool 原样/更早的清零, 已接入 start_step;
#       边界由调用方给(find_tail_start 算), 故本模块不 import split_turn(零新依赖职责不混);
#     ②keep_valuable_messages 两处修: FC 对原子化(新增 _fc_atomic_units, 修"决策留下/结果被删"→provider 400)
#       + 无条件保留收窄到 system(原 weight>=70 使 FC 单元永不丢, 实测 budget=2000 输出 83164 tok 超 41 倍);
#     ③新增 _msg_cost 统一 token 口径(复用 MessageBuilder._estimate_tokens, 原 len/c 自算漏 tool_calls 开销)。 — 小欧-2026-10-08
#   2026-10-20 小欧 FC 单元划分迁协议层: 删除本地 _fc_atomic_units, 复用 fc_message_types.fc_atomic_units
#     (message_builder 裁剪也需同一划分, 而 prune 顶层 import message_builder, 反向导入必成环;
#      迁至零依赖协议模块即解环, 两边共用一份真源)。行为不变。 — 小欧-2026-10-20
#   2026-10-29 小欧 三堂会审两修(北京老陈令, 未提交先修): ①use_tool_summary 增 _raw 保长守卫(truncate 已存的全量
#     原文不得被截断头覆盖, 保住原文尾部); ②增最小长度门槛 USE_SUMMARY_MIN_CHARS=300——短小观察(文件清单/命中数/
#     行数, 40~80字)信息密集, 换一行模板摘要在 token 收益趋零下灭失信息, 仅长文本才值得整条换取真摘要 — 小欧-2026-10-29
#   2026-10-29 小欧 魔法数字清账(北京老陈令): _value_weight 六权重值与 clear_tool_outputs 头部截长 [:120] 迁
#     compaction_constants.VALUE_WEIGHT_*/TOOL_SUMMARY_HEAD_CHARS 常量域, 代码零行为变化 — 小欧-2026-10-29
#   2026-10-30 小欧 三堂会审收尾(北京老陈令): ①use_tool_summary/compress_long_tool_output 两处 _raw 写入改调
#     MessageBuilder.keep_full_raw 单点(原 use_tool_summary 内联"已有更长不覆盖"守卫, 与其他两处同构重复, DRY);
#     ②use_tool_summary docstring 补"当前无生产调用点"警示(trim 语义替换已实测撤销, 接线前须坐实 summary 含正文) — 小欧-2026-10-30
#   2026-10-30 小欧 观测/DRY 收口: 删除私有 _released_tokens, clear_tool_outputs/compress_long_tool_output
#     两处调用改公共 estimate_tokens(与 refs.budget 原 _tokens_of 同一实现收口, 原两份同款单行) — 小欧-2026-10-30
"""compaction.prune — C3 剪枝压缩 + use_tool_summary + 价值优先保留 — 小欧 2026-08-16 / 小健 2026-08-17

职责(单一职责): 仅承载「同一窗口内的消息级压缩/剪枝取舍」, 不含触发判定(归 trigger)与语义摘要(归 summary)。
依据: [4] 14.9.3②(clear_tool_outputs) / 14.9.6 C2(use_tool_summary) / 14.9.6 T1 策略(keep_valuable_messages)
      / compress_long_tool_output 设计)。

函数关系:
  - clear_tool_outputs: 通用清零旧 tool output, 保留 tool_call 参数(零 LLM, [4] 14.9.3②)。
  - use_tool_summary: 复用工具层已 stash 的 `_summary` 做一行语义摘要(DRY 升级, [4] 14.9.6 C2 推荐)。
  - compress_long_tool_output: 通用字符串级摘要兜底(无 per-tool 模板, 依赖前置 stash `_summary` 缺位时回溯首段)。
  - keep_valuable_messages: 按价值权重保留, 预算内先丢低价值 FC 轮(T1 保真增强, FC 对原子不可拆)。

全部纯规则零 LLM; 复用既有 `_compressed` 防重复标记; 常量不硬编码(DRY);
内部标记 `_summary`/`_compressed`/`_pruned`/`_raw` 由 prepare_messages_for_llm 与 `_temp_*` 同段剥离。
"""
import logging
from typing import List, Dict

from app.services.agent.compaction_constants import (
    CHARS_PER_TOKEN,
    PRUNE_MINIMUM_TOKENS,
    PRUNE_PROTECT_TOKENS,
    TOOL_SUMMARY_HEAD_CHARS,          # 2026-10-29 小欧: 原文摘要头部截长(魔法数字清账)
    USE_SUMMARY_MIN_CHARS,            # 2026-10-29 小欧: use_tool_summary 最小参与长度门槛(三堂会审修复)
    VALUE_WEIGHT_ASSISTANT,           # 2026-10-29 小欧: 消息价值权重族(魔法数字清账, 原内联权重值直迁)
    VALUE_WEIGHT_HISTORY_MEM,
    VALUE_WEIGHT_OTHER,
    VALUE_WEIGHT_SYSTEM,
    VALUE_WEIGHT_TOOL,
    VALUE_WEIGHT_TOOL_CALL_DECISION,
)
from app.services.agent.message_builder import MessageBuilder  # 2026-10-08 小欧: 预算口径与 split_turn/message_builder 统一(DRY) — 小欧-2026-10-08
from app.services.agent.token_estimate import estimate_tokens  # 2026-10-30 小欧: chars→token 唯一实现(原私有 _released_tokens, DRY)
from app.services.agent.fc_message_types import fc_atomic_units  # 2026-10-20 小欧: FC 单元划分唯一源迁协议层(解循环, message_builder 裁剪共用)

logger = logging.getLogger(__name__)

# 2026-10-08 小欧 - 无条件保留的权重门槛: 仅 system(90)/_history_mem(100) 属结构性必需
#   (丢掉 system 等于丢掉系统约束, agent 不可用), 其余一律受 budget 约束 — 小欧-2026-10-08
_WEIGHT_ALWAYS_KEEP = 90


# ---- C3 策略实现: clear_tool_outputs 通用清零(14.9.3②) ————————————————————————————————


def clear_tool_outputs(messages: List[Dict]) -> tuple[List[Dict], int]:
    """清旧 tool output、保留 tool_call 参数与消息结构 — 小欧 2026-08-16

    适用场景: C3 剪枝压缩核心; 上下文超窗但无需语义保真时, 快速释放 tool 输出 token。
    使用方法: 直接对消息列表调用, 返回 (新列表, 释放 token 估算); 近端受保护由上层依 reserve 决定。
    输入: messages 消息列表(含 role/tool_call_id/content 等字段)。
    输出: (处理后消息列表, 释放的 token 估算 int)。被清 tool 打 `_pruned=True` 标记。
    前置条件: 无; 只清 role=tool 且有 tool_call_id 的消息的 content, 保留结构与 tool_call 参数。
    """
    released = 0
    pruned = []
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            content = msg.pop("content", None)
            if content:
                released += estimate_tokens(content)
            msg.update({"_pruned": True, "content": ""})
        pruned.append(msg)
    return pruned, released


# ---- C3 策略实现: use_tool_summary(14.9.6 C2, DRY 升级) —————————————————————


def use_tool_summary(messages: List[Dict]) -> List[Dict]:
    """用工具返回自带 summary 替换 tool content — 小欧 2026-08-16

    适用场景: 作为 compress_long_tool_output 的 DRY 升级替代; 当工具已返回 llm_data.summary 时优先用本法。
    使用方法: 对消息列表调用, 原地替换 content 为 `[tool-summary] {_summary}`, 返回同一列表。
    输入: messages 消息列表。
    输出: 处理后的同一列表; 被替换的 tool 消息带 `_raw`(原 content) 与 `_compressed=True` 标记。
    门槛(2026-10-29 三堂会审修复): content 长度 ≥ USE_SUMMARY_MIN_CHARS 才参与替换——短小观察
                   信息密度高(文件清单/命中数/行数), 换模板摘要得不偿失; 未达标原样跳过。
    前置条件(必做): tool 消息构造时必须先 stash `_summary`(见 message_builder.add_tool_result 的 summary 形参);
                   否则无 _summary 时函数空转安全(仅跳过不报错)。
    依据本地真实代码: observation_formatter.py:603/627 已将 summary 拼进 content 文本, tool 消息字典本身只有
    role/tool_call_id/content, 无独立 summary 字段 —— 复用已 stash 的 _summary(去臆测 msg["summary"])。
    不写 per-tool 模板(DRY, 消除 14.3 指出的 C1 逐工具模板过度设计)。
    ⚠ 当前无生产调用点(2026-10-30 小欧): trim_history 的语义替换已实测撤销——全库 llm_data.summary 均为一两行
      状态/计数, 换掉后正文本轮不可见。保留本函数仅作"确实带正文摘要"的工具接入预备, 接线前须先坐实该工具
      summary 含正文, 否则必然灭失信息。
    """
    for msg in messages:
        if msg.get("role") == "tool" and not msg.get("_compressed"):
            summ = msg.get("_summary")
            raw = msg.get("content", "")
            # 2026-10-29 小欧 - 三堂会审修复: 增最小长度门槛——短小观察(文件清单/命中数/行数)信息密集,
            #   换一行模板摘要 token 收益趋零而信息全失, 仅达门槛的长文本才参与; 门槛值归
            #   compaction_constants.USE_SUMMARY_MIN_CHARS(权威常量域, 与其他压缩阈值同源) — 小欧-2026-10-29
            if summ and raw and len(str(raw)) >= USE_SUMMARY_MIN_CHARS and len(str(raw)) > len(str(summ)):
                # 2026-10-30 小欧 - _raw 保长守卫收口 MessageBuilder.keep_full_raw(DRY): 原内联
                #   "已有更长 _raw 不覆盖"逻辑在本文件两处 + split_turn 一处重复, 统一走单点 — 小欧-2026-10-30
                MessageBuilder.keep_full_raw(msg, raw)
                msg["content"] = f"[tool-summary] {summ}"
                msg["_compressed"] = True
    return messages


# ---- C3 策略实现: compress_long_tool_output 通用摘要兜底(设计文档) —————


def compress_long_tool_output(messages: List[Dict],
                             min_release: int = PRUNE_MINIMUM_TOKENS,
                             protect_tokens: int = PRUNE_PROTECT_TOKENS) -> tuple[List[Dict], int]:
    """逐工具观测压缩：超长 tool 输出压缩为一行通用摘要 — 小健 2026-08-17

    适用场景: use_tool_summary 的兜底——当工具未 stash `_summary` 时, 对超长 tool 输出做字符串级一行摘要。
    使用方法: 对消息列表调用, 返回 (新列表, 释放 token 估算); 默认受保护/最小释放阈值由常量控制。
    输入: messages 消息列表; min_release 最小需释放 token(默认 PRUNE_MINIMUM_TOKENS=20000);
          protect_tokens 受保护 token 阈值(默认 PRUNE_PROTECT_TOKENS=40000, 短输出不压缩防反向膨胀)。
    输出: (处理后的消息列表, 释放的 token 估算 int); 被压缩消息带 `_raw` 与 `_compressed=True` 标记。
    前置条件: 无; 只处理 role=tool 且未 `_compressed` 的消息, 已压缩/短输出自动跳过。

    设计文档: compress_long_tool_output Tool-Summary + 14.9.6 C2(use_tool_summary 强推荐替代,
    本函数为其兜底: 无 `_summary` 时仍可为长 tool 输出做字符串级摘要)。
    相对于 use_tool_summary: 后者依赖工具层已 stash 的 `_summary`; 本函数不依赖, 直接用
    内容首段 + 长度标记生成"一行摘要"(零 per-tool 模板, 去 14.7 指出的过度设计)。
    """
    released = 0
    for msg in messages:
        if msg.get("role") != "tool" or msg.get("_compressed"):
            continue
        raw = str(msg.get("content", "") or "")
        if len(raw) <= protect_tokens * CHARS_PER_TOKEN:   # 近期/短输出受保护, 不压缩(防小输出反向膨胀)
            continue
        release = estimate_tokens(raw)
        if release < min_release:
            continue                          # 释放不足 PRUNE_MINIMUM_TOKENS 跳过(防抖动, 借鉴 OPENCODE)
        head = " ".join(raw.split())[:TOOL_SUMMARY_HEAD_CHARS]
        MessageBuilder.keep_full_raw(msg, raw)   # 2026-10-30 小欧: _raw 写入收口 message_builder 单点
        msg["content"] = f"[tool-summary] {head}…({len(raw)}字符)"
        msg["_compressed"] = True
        released += release
    return messages, released


def prune_tool_output_keeping_tail(messages: List[Dict],
                                    tail_start: int) -> tuple[List[Dict], int]:
    """摘要降本: 保尾区 tool 原样, 更早的清零 — 小欧 2026-10-07

    传消息列表 + 保尾起点下标(由 split_turn.find_tail_start 算), 返回 (新列表, 释放 token); 不改入参。
    边界由调用方给: "怎么算边界"属 split_turn 语义, 本函数只管"前清后保", 故不 import split_turn。
    只动 content 不删消息, FC 结构原样配对不受影响; 当前调用方=start_step 摘要前置。— 小欧-2026-10-08
    """
    cut = max(0, min(int(tail_start), len(messages)))
    head, released = clear_tool_outputs([dict(m) for m in messages[:cut]])
    return head + [dict(m) for m in messages[cut:]], released


# ---- T1 策略实现: keep_valuable_messages(14.9.6, 保真增强) ——————————————————————


def _value_weight(msg: Dict) -> int:
    """消息语义价值权重(越高越优先保留) — 小欧 2026-08-16"""
    role = msg.get("role")
    if msg.get("_history_mem"):
        return VALUE_WEIGHT_HISTORY_MEM         # History Memory 最高
    if role == "system":
        return VALUE_WEIGHT_SYSTEM
    if role == "assistant" and msg.get("tool_calls"):
        return VALUE_WEIGHT_TOOL_CALL_DECISION  # 决策: 调了什么工具
    if role == "assistant":
        return VALUE_WEIGHT_ASSISTANT           # thought/answer
    if role == "tool":
        return VALUE_WEIGHT_TOOL                # 纯输出, 价值最低, 先删
    return VALUE_WEIGHT_OTHER


def _msg_cost(msg: Dict) -> int:
    """单条消息的预算占用 token — 小欧 2026-10-08

    原用 len(content)/CHARS_PER_TOKEN 自算, 漏算 assistant.tool_calls 结构开销(实测决策消息 0 vs 41)
    → budget 约束不准(budget=2000 实测输出 10245 tok)。现复用 MessageBuilder._estimate_tokens,
    与 split_turn/message_builder 同一真源; message_builder 不 import compaction, 无循环依赖。
    """
    return MessageBuilder._estimate_tokens([msg])


def keep_valuable_messages(messages: List[Dict], budget_tokens: int) -> List[Dict]:
    """按价值权重保留, 预算内先丢低价值 FC 轮 — 小欧 2026-08-16

    适用场景: 关键决策发生在早期轮时, 替代"保最近 N 轮"; 与 T1 组合增强保真。
    使用方法: 对消息列表 + 预算 token 调用, 返回按原始时序还原的保留列表。
    输入: messages 消息列表; budget_tokens 允许保留的 token 预算上限。
输出: 保留的消息列表(原始顺序)。system/_history_mem 无条件保留(结构性必需), 其余受 budget 约束。
    2026-10-08 小欧 两处修正(单测实测暴露): ①FC 对原子化(修"决策留下/结果被删"→ provider 400);
      ②无条件保留收窄到 system(原 ≥70 使 FC 单元永不丢, 实测 budget=2000 输出 83164 tok 超 41 倍)。 — 小欧-2026-10-08
    """
    units = fc_atomic_units(messages)
    kept_idx: List[int] = []
    used = 0
    for grp in sorted(units,
                      key=lambda g: max(_value_weight(messages[j]) for j in g),
                      reverse=True):
        cost = sum(_msg_cost(messages[j]) for j in grp)
        weight = max(_value_weight(messages[j]) for j in grp)
        if used + cost <= budget_tokens or weight >= _WEIGHT_ALWAYS_KEEP:
            kept_idx.extend(grp)
            used += cost
    # 按原始下标升序还原(保 LLM 阅读时序)
    return [messages[i] for i in sorted(kept_idx)]