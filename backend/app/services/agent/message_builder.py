# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-13 - 小欧 - #2 add_tool_result构造失败兜底追加最小tool消息防结果丢失
"""
MessageBuilder — conversation_history 状态管理器

将分散在 base_react.py 和 react_agent_mixin.py 中的
conversation_history操作集中管理。

无状态工具函数已迁入 message_utils.py,遵循 SRP。

【生命周期与会话绑定说明 — 小沈 2026-05-20】:
MessageBuilder 实例生命周期必须与 Agent 实例强绑定,
严禁全局共享单例,防止多会话并发状态污染。

【FC-only重构 — 小沈 2026-06-11】:
- 删除 add_assistant / flush_temp_to_history / add_parse_error
- _append_observation 只存FC协议格式(role=assistant tool_calls + role=tool)
- _trim_to_budget 统一裁剪,按原始顺序重排
"""

import json
from typing import Any, Dict, List, Optional

from app.config import get_config  # 小欧 2026-07-08
from app.constants import MAX_CONTEXT_CHARS, TEMP_HISTORY_CHAR_LIMIT
from app.logger import logger  # 小欧 2026-07-01: 裁剪日志
from app.services.agent.fc_message_types import (
    FcMessage, SystemMessage, UserMessage, AssistantMessage, ToolResultMessage, ToolCall,
    message_to_dict, dict_to_message,
)


class MessageBuilder:
    """Prompt/Message组装的统一入口"""

    def __init__(self, max_context_chars: int = MAX_CONTEXT_CHARS):
        self.conversation_history: List[Dict[str, Any]] = []
        self.temp_history: List[Dict[str, Any]] = []
        self.MAX_CONTEXT_CHARS = max_context_chars
        self._max_rounds: int = get_config().get_max_rounds()  # 最多保留FC轮数(默认100) — 小欧 2026-07-08

    def reset_per_run(self) -> None:
        """每次 run_react_cycle 仅重置 conversation_history,缓存和计数保留跨会话"""
        self.conversation_history = []
        self.temp_history = []

    # =========================================================================
    # 第一组:conversation_history 写操作(统一入口)
    # =========================================================================

    def add_system_message(self, content: str) -> SystemMessage:
        """添加system消息 — 北京老陈 2026-06-25"""
        msg = SystemMessage(content=content)
        self.conversation_history.append(message_to_dict(msg))
        return msg

    def add_user_message(self, content: str) -> UserMessage:
        """添加user消息 — 北京老陈 2026-06-25"""
        msg = UserMessage(content=content)
        self.conversation_history.append(message_to_dict(msg))
        return msg

    def add_assistant_tool_call(self, tool_calls: list,
                                content: Optional[str] = None) -> AssistantMessage:
        """添加assistant工具调用消息 — 北京老陈 2026-06-25

        配对说明:
          此assistant(带N个tool_calls)与后续N条tool(通过tool_call_id关联)组成一对。
          调用顺序: add_assistant_tool_call → add_tool_result x N
          LLM收到的历史: ...→assistant(tool_calls=[id1,id2])→tool(id1)→tool(id2)→...
        — 小欧 2026-07-12
        """
        msg = AssistantMessage(content=content, tool_calls=tool_calls)
        self.conversation_history.append(message_to_dict(msg))
        return msg

    def add_tool_result(self, tool_call_id: str, content: str) -> ToolResultMessage:
        """添加工具执行结果消息 — 北京老陈 2026-06-25

        与add_assistant_tool_call配对使用:
          每条tool通过tool_call_id关联回assistant中的某一条tool_call.id。
          同一轮的所有tool共用同一个assistant父消息。
        — 小欧 2026-07-12 — 小欧 2026-07-13 防御: 构造/序列化失败也兜底追加最小合法tool消息, 保证工具结果绝不丢失
        """
        try:
            msg = ToolResultMessage(content=content, tool_call_id=tool_call_id)
            self.conversation_history.append(message_to_dict(msg))
            return msg
        except Exception as e:
            logger.warning(f"[message_builder] add_tool_result构造失败(tool_call_id={tool_call_id}): {type(e).__name__}: {e!r}")
            # 兜底: 直接追加最小合法tool消息, 保证对话历史完整(结果不丢失) — 小欧 2026-07-13
            self.conversation_history.append({
                "role": "tool",
                "content": content,
                "tool_call_id": tool_call_id,
            })
            return None

    def init_history(self, sys_prompt: str, task_prompt: str) -> None:
        """初始化conversation_history — 替代base_react.py L368-369"""
        if not task_prompt or not task_prompt.strip():
            raise ValueError("task_prompt不能为空")
        self.conversation_history = []
        self.add_system_message(sys_prompt)
        self.add_user_message(task_prompt)

    def inject_history(self, history_msgs: List[Dict]) -> None:
        """注入多轮对话历史到 system 和 task 之间 — 小欧 2026-07-02

        封装 history_msgs 插入 conversation_history 的列表操作：
        - history >= 2：[:1] + history_msgs + [1:]（system 之后、task 之前插入）
        - 否则：history_msgs + 现有（兜底追加）

        不转换消息格式，调用方负责构建好 history_msgs（如去掉最后一条 user 避免与 task 重复）。
        """
        if not history_msgs:
            return
        if len(self.conversation_history) >= 2:
            self.conversation_history = (
                self.conversation_history[:1]
                + history_msgs
                + self.conversation_history[1:]
            )
        else:
            self.conversation_history = history_msgs + self.conversation_history

    def _append_observation(self, observation_text: str, fc_context: Dict) -> None:
        """追加FC协议observation消息 — fc_context必传 — FC-only重构 2026-06-11 小沈
        北京老陈 2026-06-25: 使用类型安全方法替代原始message_to_dict调用

        FC协议要求: assistant(tool_calls)必须在role:tool之前,且每个tool_call_id唯一。
        始终添加assistant消息,确保配对完整。重复tool_call_id跳过assistant以避免重复。
        """
        tool_call_id = fc_context.get("tool_call_id", "")
        tool_calls = fc_context.get("tool_calls", [])
        # 检查是否已有相同tool_call_id的assistant消息(并行工具调用场景)
        has_existing_assistant = any(
            msg.get("role") == "assistant" and
            any(tc.get("id") == tool_call_id for tc in (msg.get("tool_calls") or []))
            for msg in self.conversation_history
        ) if tool_call_id else False
        if tool_calls and not has_existing_assistant:
            llm_content = fc_context.get("llm_content", "") or None
            self.add_assistant_tool_call(tool_calls, content=llm_content)
        elif tool_call_id and not has_existing_assistant:
            self.add_assistant_tool_call([])
        elif not has_existing_assistant:
            llm_content = fc_context.get("llm_content", "") or ""
            self.add_assistant_tool_call([], content=llm_content)
        self.add_tool_result(tool_call_id, observation_text)

    def add_observation(self, observation_text: str, fc_context: Dict) -> None:
        """添加observation — 裁剪统一在 _process_single_step — 小欧 2026-07-01"""
        self._append_observation(observation_text, fc_context)

    def add_assistant_message(self, content: str) -> AssistantMessage:
        """追加assistant最终回答到conversation_history — 2026-06-25 小欧 J-1修复: 封装统一入口
        北京老陈 2026-06-25: 返回类型化AssistantMessage对象"""
        msg = AssistantMessage(content=content)
        self.conversation_history.append(message_to_dict(msg))
        return msg

    # =========================================================================
    # 第二组:每轮 LLM 调用的消息组装
    # =========================================================================

    def prepare_messages_for_llm(self) -> List[Dict[str, Any]]:
        """准备发给LLM的完整消息列表 — 合并原split+merge+assemble

        不再拆出last_message再拼回,整个history作为一个List[Dict]贯穿流程。
        注入点(tools/summary/schema)在第一个非system消息前或末尾操作。

        MSG-001 小沈 2026-05-24: temp_history加入字符容量限制,从最旧开始移除
        """
        # temp_history容量保护:总字符超50000时从最旧截断,再构建messages
        self._cap_temp_history()
        messages = list(self.conversation_history)
        if self.temp_history:
            messages = messages + list(self.temp_history)
        return messages

    def _cap_temp_history(self):
        """对temp_history加字符容量限制(最多50000字符),从最旧条目开始截断"""
        while self._total_chars(self.temp_history) > TEMP_HISTORY_CHAR_LIMIT and len(self.temp_history) > 1:
            self.temp_history.pop(0)

    # =========================================================================
    # 第三组:历史裁剪
    # =========================================================================

    def trim_history(self) -> None:
        """对话历史裁剪 — 两个独立条件 — 小欧 2026-07-02

        裁剪策略:
        - 条件1(轮次太多): 消息数 >self._max_rounds(100)*2+2 → 只保留最近 self._max_rounds 轮FC完整对 — 小欧 2026-07-08
        - 条件2(字符太多): 字符 >160K → _trim_to_budget 按70%预算从旧到新裁
        - system+user 消息永保
        - 配对不完整的 FC 对由 _trim_fc_pairs 清理
        """
        total = self._total_chars(self.conversation_history)
        msg_count = len(self.conversation_history)

        if msg_count <= 5:
            return

        # 两个条件都不达标 → 不裁剪
        if total < self.MAX_CONTEXT_CHARS * 0.8 and msg_count <= self._max_rounds * 2 + 5:
            return

        system_msgs, user_msgs, obs_list, assistant_msgs = self._classify_messages()
        original_order = {id(m): i for i, m in enumerate(self.conversation_history)}

        # 条件1: 轮次太多 → 保留最近 self._max_rounds 轮FC完整对
        if msg_count > self._max_rounds * 2 + 2:
            all_fc = sorted(obs_list + assistant_msgs, key=lambda m: original_order.get(id(m), 0))
            kept_fc = all_fc[-(self._max_rounds * 2):]
            obs_list = [m for m in kept_fc if m.get("role") == "tool"]
            assistant_msgs = [m for m in kept_fc if m.get("role") == "assistant"]

        # 条件2: 字符太多 → 按预算裁(70%余量)
        if total > self.MAX_CONTEXT_CHARS * 0.8:
            always_keep_chars = self._total_chars(system_msgs) + self._total_chars(user_msgs)
            available_budget = max(0, int(self.MAX_CONTEXT_CHARS * 0.7) - always_keep_chars)
            trimmed = self._trim_to_budget(obs_list, assistant_msgs, available_budget)
        else:
            trimmed = sorted(obs_list + assistant_msgs, key=lambda m: original_order.get(id(m), 0))

        rebuilt = self._rebuild_and_validate(system_msgs, user_msgs, trimmed)
        if rebuilt is not None:
            self.conversation_history = rebuilt

        logger.info(f"[trim_history] 裁剪: {msg_count}条({total} chars) "
                    f"→ {len(rebuilt)}条(触发: {'消息数' if msg_count > self._max_rounds * 2 + 2 else '字符'})")

    def _classify_messages(self):
        """将消息分类为 system / user / observation(tool) / assistant 四组 — 2026-06-25 小欧 D-1修复"""
        system_msgs = []
        user_msgs = []
        obs_list = []
        assistant_msgs = []
        for msg in self.conversation_history:
            role = msg.get("role", "")
            if role == "assistant":
                assistant_msgs.append(msg)
            elif self._is_observation_role(msg):
                obs_list.append(msg)
            elif role == "user":
                user_msgs.append(msg)
            else:
                system_msgs.append(msg)
        return system_msgs, user_msgs, obs_list, assistant_msgs

    def _trim_to_budget(self, obs_list, assistant_msgs, budget):
        """FC-only: 从最新往最旧扫,按配对收集,简洁高效

        策略: 从最后一条消息往前遍历,遇到tool就找其配对assistant一起保留,
        遇到独立消息直接保留,直到budget用完。剩余的全部丢弃。
        小欧 2026-06-25: 去掉强制保留机制,纯预算裁剪,简单可靠。
        """
        tool_to_assistant = {}
        for msg in assistant_msgs:
            for tc in (msg.get("tool_calls") or []):
                if tc.get("id"):
                    tool_to_assistant[tc["id"]] = msg

        # 按原始顺序排列 obs+assistant
        original_order = {id(msg): i for i, msg in enumerate(self.conversation_history)}
        all_msgs = sorted(obs_list + assistant_msgs, key=lambda m: original_order.get(id(m), 0))

        kept = []
        used_chars = 0
        i = len(all_msgs) - 1
        consumed_ids = set()  # 已作为配对加入 kept 的消息id，不再重复处理 — 小欧 2026-06-26

        while i >= 0:
            msg = all_msgs[i]
            if id(msg) in consumed_ids:
                i -= 1
                continue
            tc_id = msg.get("tool_call_id", "")

            if msg.get("role") == "tool" and tc_id and tc_id in tool_to_assistant:
                asst = tool_to_assistant[tc_id]
                asst_already_kept = id(asst) in consumed_ids
                # 配对: 只加tool（assistant已存在）或加两者 — 小欧 2026-06-26
                if asst_already_kept:
                    need_chars = self._total_chars([msg])
                else:
                    need_chars = self._total_chars([asst, msg])
                if used_chars + need_chars <= budget:
                    kept.append(msg)
                    if not asst_already_kept:
                        kept.append(asst)
                        consumed_ids.add(id(asst))
                    used_chars += need_chars
                i -= 1
                continue

            msg_chars = self._total_chars([msg])
            if used_chars + msg_chars <= budget:
                kept.append(msg)
                if msg.get("role") == "assistant":
                    consumed_ids.add(id(msg))
                used_chars += msg_chars
            else:
                break
            i -= 1

        kept.reverse()
        return kept

    def _rebuild_and_validate(self, system_msgs, user_msgs, trimmed_msgs):
        """重组消息列表并验证FC配对完整性 — 2026-06-25 小欧 D-1修复: user_msgs在system和trimmed之间"""
        rebuilt = system_msgs + user_msgs + trimmed_msgs
        rebuilt = self._trim_fc_pairs(rebuilt)
        if len(rebuilt) >= 2:
            return rebuilt
        if len(self.conversation_history) > 10:
            return self.conversation_history[:2] + self.conversation_history[-8:]
        return None

    # =========================================================================
    # 第四组:observation 辅助
    # =========================================================================

    @staticmethod
    def _normalize_observation_prefix(text: str) -> str:
        """确保observation文本以 [Observation] 开头 — 替代 base_react.py 前缀处理"""
        # 【修复 小健 2026-05-24】P1-7: 防止双重[Observation]前缀
        if text.startswith("[Observation]"):
            return text
        for prefix in ["Observation:", "observation:"]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        # 去掉前缀后再次检查,避免双重
        if text.startswith("[Observation]"):
            return text
        return f"[Observation] {text}"

    @staticmethod
    def _is_observation_role(msg: Dict) -> bool:
        """FC-only: observation只有role=tool一种形式 — 重构 2026-06-11 小沈"""
        return msg.get("role") == "tool"

    @staticmethod
    def _trim_fc_pairs(messages: List[Dict]) -> List[Dict]:
        """FC协议配对裁剪:确保role:tool与role:assistant(tool_calls)严格配对

        OpenAI要求:assistant消息中每个tool_call.id都必须有对应role:tool(tool_call_id),
        role:tool的tool_call_id也必须有对应assistant(tool_calls)。
        任一端缺失则双方都移除。
        """
        assistant_ids: set = set()
        tool_ids: set = set()
        for msg in messages:
            if msg.get("role") == "assistant":
                for tc in msg.get("tool_calls") or []:
                    if tc.get("id"):
                        assistant_ids.add(tc["id"])
            elif msg.get("role") == "tool":
                if msg.get("tool_call_id"):
                    tool_ids.add(msg["tool_call_id"])
        paired_ids = assistant_ids & tool_ids
        result = []
        for msg in messages:
            if msg.get("role") == "assistant":
                tcs = msg.get("tool_calls") or []
                kept_tcs = [tc for tc in tcs if tc.get("id") in paired_ids]
                if not kept_tcs and tcs:
                    continue
                new_msg = dict(msg)
                new_msg["tool_calls"] = kept_tcs
                result.append(new_msg)
            elif msg.get("role") == "tool":
                if msg.get("tool_call_id") in paired_ids:
                    result.append(msg)
                elif not msg.get("tool_call_id"):
                    result.append(msg)
            else:
                result.append(msg)
        return result

    @staticmethod
    def _total_chars(messages: List[Dict]) -> int:
        """计算消息列表总字符数 — 含tool_calls JSON

        FC模式下assistant消息content可为None(tool_calls协议),
        但tool_calls包含JSON负载(tool名/参数/id),必须计入预算。
        """
        total = 0
        for msg in messages:
            content = msg.get("content")
            total += len(content) if content is not None else 0
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                total += len(json.dumps(tool_calls, ensure_ascii=False))
        return total
