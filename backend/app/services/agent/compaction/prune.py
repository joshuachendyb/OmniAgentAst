# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-16 小欧 新增: C3 剪枝引擎 prune_tool_outputs(借鉴 opencode prune, 纯规则零 LLM)
#   2026-08-16 小欧 新增: t1_reuse_summary(复用工具层 llm_data.summary) + value_first_prune(按价值权重保留)
#   2026-08-17 小健 落地: 四函数合并 prune.py, 常量自 compaction.compaction_constants(DRY re-export)
#                        t1_compress_observations 实现为通用字符串级摘要兜底(去 per-tool 模板过度设计,
#                        [4] 14.9.6 明示 t1_reuse_summary 强推荐替代逐工具模板; 本版为无 _summary 时的兜底)
"""compaction.prune — C3 剪枝压缩 + t1_reuse_summary + 价值优先保留 — 小欧 2026-08-16 / 小健 2026-08-17

职责(单一职责): 仅承载「同一窗口内的消息级压缩/剪枝取舍」, 不含触发判定(归 trigger)与语义摘要(归 summary)。
依据: [4] 14.9.3②(prune_tool_outputs) / 14.9.6 C2(t1_reuse_summary) / 14.9.6 T1 策略(value_first_prune)
      / 第五章(t1_compress_observations 设计)。

函数关系:
  - prune_tool_outputs: 通用清零旧 tool output, 保留 tool_call 参数(零 LLM, [4] 14.9.3②)。
  - t1_reuse_summary: 复用工具层已 stash 的 `_summary` 做一行语义摘要(DRY 升级, [4] 14.9.6 C2 推荐)。
  - t1_compress_observations: 通用字符串级摘要兜底(无 per-tool 模板, 依赖前置 stash `_summary` 缺位时回溯首段)。
  - value_first_prune: 按价值权重保留, 预算内先丢低价值 tool 输出(T1 保真增强)。

三堂会审:
  合规: 全部纯规则零 LLM; 复用既有 `_compressed` 防重复标记; 常量不硬编码(DRY)。
  合理(KISS): 各自一条 if/循环直线, 无绕路; t1_compress_observations 不重造 per-tool 模板(去过度设计)。
  关联(增强不退化): `_summary`/`_compressed` 属内部标记, 由 prepare_messages_for_llm 与 `_temp_*` 同段剥离;
                    value_first_prune 删 tool 后由 assembler.trim_orphan_pairs_proactive 闭环保配对。
"""
import logging
from typing import List, Dict

from app.services.agent.compaction.compaction_constants import (
    CHARS_PER_TOKEN,
    PRUNE_MINIMUM_TOKENS,
    PRUNE_PROTECT_TOKENS,
)

logger = logging.getLogger(__name__)


def _released_tokens(content: str) -> int:
    """按 CHARS_PER_TOKEN 估算释放 token(与 MessageBuilder._estimate_tokens 同款纯数学, 零依赖) — 小健 2026-08-17"""
    return len(str(content)) // CHARS_PER_TOKEN


# ---- C3 策略实现: prune 通用清零(14.9.3②) ————————————————————————————————


def prune_tool_outputs(messages: List[Dict]) -> tuple[List[Dict], int]:
    """清旧 tool output、保留 tool_call 参数与消息结构 — 小欧 2026-08-16

    遍历 assistant(tool_calls) ↔ tool 配对, 将 tool 的 content 清空并打 _pruned 标记,
    保留 tool_call_id/name/arguments(供后续轮引用"做了什么"), 返回 (处理后的消息, 释放的token估算)。
    近端受保护判定由上层依据 reserve 决定(PRUNE_PROTECT_TOKENS), 此处仅清 content 打标记。
    """
    released = 0
    pruned = []
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            content = msg.pop("content", None)
            if content:
                released += _released_tokens(content)
            msg.update({"_pruned": True, "content": ""})
        pruned.append(msg)
    return pruned, released


# ---- C3 策略实现: t1_reuse_summary(14.9.6 C2, DRY 升级) —————————————————————


def t1_reuse_summary(messages: List[Dict]) -> List[Dict]:
    """用工具返回自带 summary 替换 tool content — 小欧 2026-08-16

    前置(必做, 见 message_builder.add_tool_result): tool 消息构造时把 llm_data.summary 存为 _summary 字段。
    依据本地真实代码: observation_formatter.py:603/627 已将 summary 拼进 content 文本, tool 消息字典本身只有
    role/tool_call_id/content, 无独立 summary 字段 —— 复用已 stash 的 _summary(三堂会审去臆测 msg["summary"])。
    不写 per-tool 模板(DRY, 消除 14.3 指出的 C1 逐工具模板过度设计)。
    """
    for msg in messages:
        if msg.get("role") == "tool" and not msg.get("_compressed"):
            summ = msg.get("_summary")
            raw = msg.get("content", "")
            if summ and raw and len(str(raw)) > len(str(summ)):
                msg["_raw"] = raw
                msg["content"] = f"[tool-summary] {summ}"
                msg["_compressed"] = True
    return messages


# ---- C3 策略实现: t1_compress_observations 通用摘要兜底(第五章) —————————————


def t1_compress_observations(messages: List[Dict],
                             min_release: int = PRUNE_MINIMUM_TOKENS,
                             protect_tokens: int = PRUNE_PROTECT_TOKENS) -> tuple[List[Dict], int]:
    """逐工具观测压缩：超长 tool 输出压缩为一行通用摘要 — 小健 2026-08-17

    设计文档: [4] 第五章(t1_compress_observations Tool-Summary) + 14.9.6 C2(t1_reuse_summary 强推荐替代,
    本函数为其兜底: 无 `_summary` 时仍可为长 tool 输出做字符串级摘要)。
    相对于 t1_reuse_summary: 后者依赖工具层已 stash 的 `_summary`; 本函数不依赖, 直接用
    内容首段 + 长度标记生成"一行摘要"(零 per-tool 模板, 去 14.7 指出的过度设计)。
    返回 (处理后的消息, 释放的token估算)。
    """
    released = 0
    for msg in messages:
        if msg.get("role") != "tool" or msg.get("_compressed"):
            continue
        raw = str(msg.get("content", "") or "")
        if len(raw) <= protect_tokens * CHARS_PER_TOKEN:   # 近期/短输出受保护, 不压缩(防小输出反向膨胀)
            continue
        release = _released_tokens(raw)
        if release < min_release:
            continue                          # 释放不足 PRUNE_MINIMUM_TOKENS 跳过(防抖动, 借鉴 OPENCODE)
        head = " ".join(raw.split())[:120]
        msg["_raw"] = raw
        msg["content"] = f"[tool-summary] {head}…({len(raw)}字符)"
        msg["_compressed"] = True
        released += release
    return messages, released


# ---- T1 策略实现: value_first_prune(14.9.6, 保真增强) ——————————————————————


def _value_weight(msg: Dict) -> int:
    """消息语义价值权重(越高越优先保留) — 小欧 2026-08-16"""
    role = msg.get("role")
    if msg.get("_history_mem"):
        return 100          # History Memory 最高
    if role == "system":
        return 90
    if role == "assistant" and msg.get("tool_calls"):
        return 80          # 决策: 调了什么工具
    if role == "assistant":
        return 70          # thought/answer
    if role == "tool":
        return 10          # 纯输出, 价值最低, 先删
    return 50


def value_first_prune(messages: List[Dict], budget_tokens: int) -> List[Dict]:
    """按价值权重保留, 预算内先丢低价值 tool 输出 — 小欧 2026-08-16"""
    # 用 enumerate 记原始下标, 避免 dict 重复导致 index() 错位(三堂会审: 关联逻辑保时序)
    indexed = list(enumerate(messages))
    kept_idx = []
    used = 0
    for i, msg in sorted(indexed, key=lambda t: _value_weight(t[1]), reverse=True):
        cost = len(str(msg.get("content", ""))) // CHARS_PER_TOKEN
        if used + cost <= budget_tokens or _value_weight(msg) >= 70:
            kept_idx.append(i)
            used += cost
    # 按原始下标升序还原(保 LLM 阅读时序)
    return [messages[i] for i in sorted(kept_idx)]