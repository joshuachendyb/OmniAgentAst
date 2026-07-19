# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 小欧 更新推理-only注入注释: 旧3条空tool_call_id消息→合法assistant(content)(工具调用意图由llm_stream XML提取接管)
# 2026-07-19 小欧 AssistantMessage加reasoning字段; message_to_dict做reasoning→reasoning_content提升
# 2026-07-19 小欧 message_to_dict提升后del推理内部字段(不泄露非标准字段); dict_to_message反向映射reasoning_content→reasoning(回环不丢)
# 2026-07-19 小欧 改善: message_to_dict用pop单次重命名; dict_to_message去掉backward条件直接映射(禁backward)
"""
FC 消息类型安全 — Pydantic 模型

定义 OpenAI-兼容的 Function Calling 消息的 Pydantic 模型。
所有 FC 协议中的消息都使用这些类型，替代原始的 dict。

【创建时间】2026-06-11 小沈
【签名】小沈
"""

from pydantic import BaseModel
from typing import List, Optional, Union
from typing_extensions import Literal


class ToolFunction(BaseModel):
    """tool_call 中的 function 对象"""
    name: str
    arguments: str  # JSON 编码的参数字符串


class ToolCall(BaseModel):
    """FC 协议中的 tool_call 条目"""
    id: str
    type: Literal["function"] = "function"
    function: ToolFunction


"""
LLM 历史消息结构说明

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 四种角色
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  角色       role         说明
  ────────  ────────────  ──────────────────────────────
  system    "system"      系统 prompt，对话开头仅 1 条
  user      "user"        用户输入的 task，对话开头仅 1 条
  assistant "assistant"   LLM 回答（tool_calls 或纯文本）
  tool      "tool"        工具执行结果，与 assistant 配对

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. 配对规则
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  assistant(tool_calls) + 多条 tool 组成一对。
  1 条 assistant（带 N 个 tool_calls）+ N 条 tool（通过 tool_call_id 关联）。

  见 build_observation（action_handler.py:315-364）:
    # 1) 先插 1 条 assistant，带本轮所有 tool_calls
    ctx.agent.message_builder.add_assistant_tool_call(
        _shared_tc, content=_fc.get("llm_content", "") or None
    )
    # 2) 循环每条 tool result，逐条插 tool
    for call, result in zip(...):
        ctx.agent.message_builder.add_tool_result(tc_id, obs_text)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. 历史结构示例
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  system                                              ← 系统 prompt
  user                                                ← 用户 task
  assistant(tool_calls=[tc1, tc2, tc3])               ← 第1轮 LLM 调用
  tool(tool_call_id=tc1)                              ← 工具 1 结果
  tool(tool_call_id=tc2)                              ← 工具 2 结果
  tool(tool_call_id=tc3)                              ← 工具 3 结果
  assistant(tool_calls=[tc4, tc5])                    ← 第2轮 LLM 调用
  tool(tool_call_id=tc4)                              ← 工具 4 结果
  tool(tool_call_id=tc5)                              ← 工具 5 结果
  ...
  assistant(content="最终回答")                        ← 最终回答（无 tool_calls）

  ── 不是 assistant+tool 一对一，而是一对多。
  ── tool 通过 tool_call_id 关联回 assistant 中对应的 tool_call.id。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. 三个代码文件的关系
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   fc_message_types.py  ─ 模型层：定义 4 种消息 Pydantic 模型 + 序列化工具
   message_builder.py   ─ 管理层：conversation_history 列表管理器（增删裁 + 组装 + 配对保持）
   action_handler.py    ─ 编排层：build_observation 中实际组装 FC 配对（调 MessageBuilder 的接口）

   数据流:
     action_handler.py (编排)
         ↓ 调 add_assistant_tool_call / add_tool_result
     message_builder.py (管理)
         ↓ 用 SystemMessage / AssistantMessage / ToolResultMessage 等
     fc_message_types.py (模型)

    一句话: action_handler.py 编排调用顺序 → message_builder.py 管理历史列表 → fc_message_types.py 定义消息格式

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5. 什么进了 conversation_history，什么没进
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    进了历史（conversation_history）：
      role=system         ─ 系统 prompt
      role=user           ─ 用户 task
      role=assistant      ─ LLM 响应（tool_calls 或最终回答），content=llm_content
      role=tool           ─ 工具执行结果

    没进历史（仅 SSE 推前端）：
      ThoughtStep         ─ LLM 推理/思考内容（thought/reasoning），只展示不存储

    例外：content="" 但 reasoning 有内容时（answer_handler.py），reasoning 会以
          合法 assistant(content) 形式注入 conversation_history，避免 LLM 在下轮丢失上下文。
          （旧实现曾伪造空 tool_call_id 的 tool 消息导致下游协议违反，已改为纯文本注入。）
          若 reasoning 内嵌 <tool_call> XML，由 llm_stream.py 的 XML 提取在 type 判定前处理为
          合法 action 执行，合成非空 tool_call_id 配对，不落此分支。

    ───────────────────────────────────────────────────────────
    5.1 thought（推理）入不入历史的科学原理
    ───────────────────────────────────────────────────────────

    【反思纠正】"结果替代过程"是通俗比喻，不严格科学。
      - answer 无法反推 reasoning，二者不构成信息论上的"压缩↔解压"冗余关系。
      - 真正开关是：下一轮迭代还需不需要这段信息来保持任务连贯，
        而非"结果能否替代过程"。

    【三条硬约束】
      1. 协议约束（主因）：OpenAI FC 协议只有 system/user/assistant/tool 四种角色，
         没有 thought 角色。reasoning 无法"原生"入历史，只能塞进
         assistant.content、伪装成 tool observation、或丢弃。
      2. 状态连续性约束：agentic 循环里，下一轮 LLM 必须看到完整轨迹
         （thought→action→observation）才能决策。情况 B（纯推理）没有
         action/answer，reasoning 是唯一轨迹，必须保留，否则下一轮从零开始。
      3. 上下文预算约束：reasoning 通常比 answer 长 3-5 倍，情况 A（已给答案）
         循环终止，留着纯粹浪费 token 且无功能价值。

    【科学结论：状态最小持久化原则】
      只持久化下一轮迭代所必须的任务状态；对后续轮次无功能价值的辅助内容，
      在协议无原生角色 + 预算有限的前提下予以丢弃。
        - 情况 A（answer+reasoning）：循环终止 → reasoning 对后续无功能价值
          → 丢弃（仅 SSE 推前端展示）。
        - 情况 B（reasoning only）：循环继续 → reasoning 是仅存轨迹状态
          → 必须持久化（伪装成 observation 注入）。

      ⚠ 修正：情况 A 不是"过程被结果替代"，而是"过程对后续已无用途"。
      — 小欧 2026-07-12

————————————————— 小欧 2026-07-12
"""

class SystemMessage(BaseModel):
    role: Literal["system"] = "system"
    content: str


class UserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: str


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    reasoning: Optional[str] = None  # 推理链内部字段(message_to_dict→reasoning_content提升) — 小欧 2026-07-19


class ToolResultMessage(BaseModel):
    role: Literal["tool"] = "tool"
    content: str
    tool_call_id: str


FcMessage = Union[SystemMessage, UserMessage, AssistantMessage, ToolResultMessage]


def message_to_dict(msg: FcMessage) -> dict:
    """将 FcMessage 转为 OpenAI 兼容的 dict（排除 None 字段）
    — 小欧 2026-07-19: reasoning→reasoning_content 提升（DeepSeek/Kimi thinking mode 相容）
    """
    d = msg.model_dump(exclude_none=True)
    if d.get("role") == "assistant" and d.get("reasoning"):
        d["reasoning_content"] = d.pop("reasoning")  # 内部字段提升为API标准字段reasoning_content(单次重命名)
    return d


def dict_to_message(d: dict) -> FcMessage:
    """将 OpenAI 兼容的 dict 转回 FcMessage"""
    role = d.get("role", "")
    if role == "system":
        return SystemMessage(**d)
    elif role == "user":
        return UserMessage(**d)
    elif role == "assistant":
        d = dict(d)
        if "reasoning_content" in d:
            d["reasoning"] = d.pop("reasoning_content")  # 回环: API标准字段映射回内部字段(禁backward条件)
        return AssistantMessage(**d)
    elif role == "tool":
        return ToolResultMessage(**d)
    raise ValueError(f"Unknown role: {role}")


__all__ = [
    "ToolFunction",
    "ToolCall",
    "SystemMessage",
    "UserMessage",
    "AssistantMessage",
    "ToolResultMessage",
    "FcMessage",
    "message_to_dict",
    "dict_to_message",
]
