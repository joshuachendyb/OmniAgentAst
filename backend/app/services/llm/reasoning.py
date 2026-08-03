
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 #49 fix: 删冗余getattr(delta,…),统一delta.get(…)
"""
Reasoning内容处理适配器 — 思考(推理)的识别与流转，统一说明在此 — 小欧 2026-07-12

====================================================================
一、什么是"思考"，为什么要和"答案"分开
====================================================================
LLM 一次回答 = 思考过程(thought/reasoning) → 产出结果(content/答案)。
思考是模型"心里嘀咕"，答案才是给用户的最终输出。两者要分开存：
  - 思考 → 思考区(full_reasoning)，多数情况只推前端展示，不进对话历史
  - 答案 → 答案区(full_content)，作为最终回答或工具调用存进对话历史

====================================================================
二、不同模型把"思考"放在哪（识别规则，全在此模块处理）
====================================================================
各家模型/网关吐思考的位置不同，extract_reasoning_from_chunk 一网打尽：

  模型/网关                思考所在位置                        识别方式
  ──────────────────────  ────────────────────────────────  ──────────────
  DeepSeek 系             独立字段 reasoning_content         直接取该字段
  Anthropic Claude       独立字段 thinking                 直接取该字段
  OpenAI 系              独立字段 reasoning                 直接取该字段
  其他(打标记型)         混在 content 里，另带标记           见下方③

  ③ 打标记型：内容在 content，但 delta 带 is_reasoning=True 或
     reasoning_flag=True，意思是"这段 content 是思考不是答案"
     → 此时取 content 当思考文字

  识别顺序：reasoning_content → thinking → reasoning → 标记型。
  都不命中 → 返回 None，说明这条消息是普通答案内容。

====================================================================
三、识别之后怎么流转（路由）—— 你问的那两种情况，就在这里
====================================================================
LLM 每发一小段(chunk)，都按下面两条规则分流：

  chunk.delta.content 存在 + is_reasoning=False → 累积到 full_content（答案区）
  chunk.delta.content 存在 + is_reasoning=True  → 累积到 full_reasoning（思考区）

  这两条就是核心。判断 is_reasoning 是 True 还是 False，靠第二节的识别规则：
  - 模型把思考放独立字段(reasoning_content/thinking/reasoning) → 取出后标 True
  - 模型把思考混在 content 里并打 is_reasoning=True/reasoning_flag=True 标记 → 标 True
  - 都不是 → 标 False，content 当答案

_parse_sse_data(base_service.py) 拿到 extract_reasoning_from_chunk 的结果后：
  - 是思考(reasoning_text 非空) → 生成 StreamChunk(is_reasoning=True)
        → call_llm_stream 里累积进 full_reasoning（思考区）
  - 不是思考 → 生成 StreamChunk(is_reasoning=False)
        → call_llm_stream 里累积进 full_content（答案区）

====================================================================
四、进了区之后，下游怎么用（与 fc_message_types.py 第5.1节呼应）
====================================================================
  思考区 full_reasoning + 答案区 full_content 组合成 LLM 响应：
    A. 有答案(content 非空)：只把答案存对话历史，思考仅推前端展示
       （循环已结束，思考对后续无用途 → 丢弃，省预算）
    B. 纯思考(content 空、reasoning 非空)：reasoning 伪装成 observation
       注入对话历史，循环继续（思考是仅存轨迹，必须保留）
  详见 fc_message_types.py 第5.1节"thought 入不入历史的科学原理"。

====================================================================
五、为什么不会"模型混乱"
====================================================================
识别只在模型显式发出思考信号(reasoning_content/thinking/reasoning/标记)时触发，
标准模型根本不发这些 → 永远走答案分支，零误判。循环有 _max_rounds 上限，
纯思考续轮触顶即终止，不会死循环。

====================================================================
六、三个代码怎么分工处理这个 True/False（单向流水线）
====================================================================
is_reasoning 的 True/False 不是在一个文件里搞定，而是三个文件接力，谁也不重复对方的活：

  reasoning.py        →  base_service.py        →  llm_stream.py
  (定规则/出主意)         (打标记)                  (按标记分流)

  ① reasoning.py  ：源头。判定"这段是不是思考"，返回思考文字或 None
                    （有文字=本质 True，None=本质 False）。不知道 StreamChunk，不知道缓冲区。
  ② base_service.py：翻译。调 reasoning.py 的结果，if reasoning_text: 写 is_reasoning=True
                    否则 False，钉在 StreamChunk 上。不知道 full_reasoning 缓冲区。
  ③ llm_stream.py  ：消费。读 chunk.is_reasoning，True 进思考区、False 进答案区。
                    不知道"怎么判定"的规则。

  三者唯一的纽带 = StreamChunk.is_reasoning 这个布尔字段（定义见 core.py:47）。
  规则只生在一处(reasoning.py)，True/False 出生在 base_service，生效在 llm_stream，
  靠布尔字段传递，不复制逻辑。

Author: 小沈 - 2026-05-27（原）；小欧 2026-07-12（补充统一说明）
"""

from typing import Dict, List, Optional

from app.logger import logger


def fix_thinking_messages(messages: List[Dict], is_thinking: bool) -> List[Dict]:
    """
    修复thinking模型消息兼容性

    thinking模型(如deepseek-v3/r1)要求assistant消息必须包含
    reasoning_content或tool_calls字段,否则API返回400。

    修复策略:对缺少reasoning_content且无tool_calls的assistant消息,
    将content移入reasoning_content字段,content置空字符串。

    Args:
        messages: 消息列表
        is_thinking: 是否为thinking模型

    Returns:
        修复后的消息列表
    """
    if not is_thinking:
        return messages
    for msg in messages:
        if msg.get("role") == "assistant" and not msg.get("tool_calls"):
            if "reasoning_content" not in msg:
                content = msg.get("content") or ""
                msg["reasoning_content"] = content
                msg["content"] = ""
    return messages


def extract_reasoning_from_chunk(delta: Dict) -> Optional[str]:
    """
    这条消息到底是"思考"还是"答案"？如果是思考，就把思考文字返回，否则返回 None。— 小欧 2026-07-12

    不同模型把"思考过程"放在不同地方，本函数一网打尽：
      - 有的模型把思考放在独立字段 reasoning_content（如 DeepSeek 系）
      - 有的模型放在独立字段 thinking（如 Anthropic Claude）
      - 有的模型放在独立字段 reasoning（如 OpenAI 系）
      - 有的模型把思考混在正式内容里，但额外打个标记 is_reasoning=True / reasoning_flag=True
        （这种就取它的 content 当思考文字）

    返回思考文字；如果这条消息不是思考，返回 None。

    Args:
        delta: LLM 流式返回的一小段消息

    Returns:
        思考文字（如果是思考），否则 None
    """
    # 1) 思考在独立字段里：直接取
    rc = delta.get('reasoning_content') or delta.get('reasoning') or delta.get('thinking')
    if rc:
        return rc
    thinking = delta.get('thinking')
    if thinking:
        return thinking
    reasoning = delta.get('reasoning')
    if reasoning not in (None, "", False):
        return reasoning
    # 2) 思考混在 content 里，但打了"这是思考"的标记：取 content 当思考
    if delta.get('is_reasoning') is True or delta.get('reasoning_flag') is True:
        return delta.get('content') or ""
    return None


def extract_reasoning_from_message(message: Dict) -> str:
    """
    从非流式响应message中提取reasoning内容

    Args:
        message: API响应的message字典

    Returns:
        reasoning内容字符串
    """
    return message.get("reasoning_content", "") or message.get("reasoning", "")


__all__ = [
    "fix_thinking_messages",
    "extract_reasoning_from_chunk",
    "extract_reasoning_from_message",
]

