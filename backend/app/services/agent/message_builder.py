# -*- coding: utf-8 -*-
"""
MessageBuilder — conversation_history 状态管理器

将分散在 base_react.py 和 react_agent_mixin.py 中的
conversation_history操作集中管理。

无状态工具函数(build_llm_messages、inject_tools_info、build_schema_text 等)
已迁入 message_utils.py,遵循 SRP。

【生命周期与会话绑定说明 — 小沈 2026-05-20】:
MessageBuilder 实例生命周期必须与 Agent 实例强绑定,
严禁全局共享单例,防止多会话并发状态污染。

【FC-only重构 — 小沈 2026-06-11】:
- 删除 add_assistant / flush_temp_to_history / add_parse_error
- _append_observation 只存FC协议格式(role=assistant tool_calls + role=tool)
- _trim_to_budget 统一裁剪,按原始顺序重排
"""

from typing import Any, Dict, List

from app.constants import MAX_CONTEXT_CHARS, OBSERVATION_BUDGET_DECAY, OBSERVATION_BUDGET_MAX, OBSERVATION_BUDGET_MIN, TEMP_HISTORY_CHAR_LIMIT
from app.utils.text_utils import smart_truncate_text

from app.services.agent.agent_utils.fc_message_types import (
    FcMessage, SystemMessage, UserMessage, AssistantMessage, ToolResultMessage,
    message_to_dict, dict_to_message,
)


class MessageBuilder:
    """Prompt/Message组装的统一入口"""

    # ===== 观测文本构建常量(从base_react.py搬入) — 小沈 2026-06-17 删除冗余X=X =====
    OBSERVATION_HEAD_RATIO = 0.6

    def __init__(self, max_context_chars: int = MAX_CONTEXT_CHARS):
        self.conversation_history: List[Dict[str, Any]] = []
        self.temp_history: List[Dict[str, Any]] = []
        self.MAX_CONTEXT_CHARS = max_context_chars

    def reset_per_run(self) -> None:
        """每次 run_react_cycle 仅重置 conversation_history,缓存和计数保留跨会话"""
        self.conversation_history = []
        self.temp_history = []

    # =========================================================================
    # 第一组:conversation_history 写操作(统一入口)
    # =========================================================================

    def init_history(self, sys_prompt: str, task_prompt: str) -> None:
        """初始化conversation_history — 替代base_react.py L368-369"""
        if not task_prompt or not task_prompt.strip():
            raise ValueError("task_prompt不能为空")
        self.conversation_history = [
            message_to_dict(SystemMessage(content=sys_prompt)),
            message_to_dict(UserMessage(content=task_prompt)),
        ]

    def _prepare_observation_text(self, observation_text: str, llm_call_count: int) -> str:
        """准备observation文本 — 截断+归一化 — 小沈 2026-06-08"""
        budget = self._get_observation_budget(llm_call_count)
        if len(observation_text) > budget:
            observation_text = smart_truncate_text(observation_text, budget=budget)
        observation_text = self._normalize_observation_prefix(observation_text)
        return observation_text

    def _append_observation(self, observation_text: str, fc_context: Dict) -> None:
        """追加FC协议observation消息 — fc_context必传 — FC-only重构 2026-06-11 小沈

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
            self.conversation_history.append(message_to_dict(AssistantMessage(content=llm_content, tool_calls=tool_calls)))
        elif tool_call_id and not has_existing_assistant:
            self.conversation_history.append(message_to_dict(AssistantMessage(tool_calls=[])))
        self.conversation_history.append(message_to_dict(ToolResultMessage(content=observation_text, tool_call_id=tool_call_id)))

    def add_observation(self, observation_text: str, llm_call_count: int, fc_context: Dict) -> None:
        """FC-only: fc_context必传 — 重构 2026-06-11 小沈"""
        observation_text = self._prepare_observation_text(observation_text, llm_call_count)
        self._append_observation(observation_text, fc_context)
        self.trim_history()

    # =========================================================================
    # 第二组:每轮 LLM 调用的消息组装
    # =========================================================================

    def export_messages_as_typed(self) -> List[FcMessage]:
        """导出类型化的 FC 消息列表 — 小沈 2026-06-11"""
        from app.services.agent.agent_utils.fc_message_types import dict_to_message
        result = []
        for msg in self.conversation_history:
            try:
                result.append(dict_to_message(msg))
            except (ValueError, TypeError):
                result.append(SystemMessage(content=str(msg)))
        for msg in self.temp_history:
            try:
                result.append(dict_to_message(msg))
            except (ValueError, TypeError):
                result.append(SystemMessage(content=str(msg)))
        return result

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
        """容量感知的对话历史裁剪 — budget包含system_msgs"""
        total = self._total_chars(self.conversation_history)
        if total < self.MAX_CONTEXT_CHARS * 0.8:
            return
        if len(self.conversation_history) <= 2:
            return

        system_msgs, obs_list, assistant_msgs = self._classify_messages()
        system_chars = self._total_chars(system_msgs)
        available_budget = max(10000, int(self.MAX_CONTEXT_CHARS * 0.7) - system_chars)
        trimmed = self._trim_to_budget(obs_list, assistant_msgs, available_budget)
        rebuilt = self._rebuild_and_validate(system_msgs, trimmed)
        if rebuilt is not None:
            self.conversation_history = rebuilt

    def _classify_messages(self):
        """将消息分类为 system / observation / assistant 三组"""
        system_msgs = []
        obs_list = []
        assistant_msgs = []
        for msg in self.conversation_history:
            role = msg.get("role", "")
            if role == "assistant":
                assistant_msgs.append(msg)
            elif self._is_observation_role(msg):
                obs_list.append(msg)
            else:
                system_msgs.append(msg)
        return system_msgs, obs_list, assistant_msgs

    def _trim_to_budget(self, obs_list, assistant_msgs, budget):
        """FC-only: 从最新往最旧扫,按配对收集,简洁高效

        策略: 从最后一条消息往前遍历,遇到tool就找其配对assistant一起保留,
        遇到独立消息直接保留,直到budget用完。剩余的全部丢弃。
        小欧 2026-06-16: 保留每种工具的首次observation，防止LLM忘记已搜索过。
        """
        tool_to_assistant = {}
        for msg in assistant_msgs:
            for tc in (msg.get("tool_calls") or []):
                if tc.get("id"):
                    tool_to_assistant[tc["id"]] = msg

        # 按原始顺序排列 obs+assistant
        original_order = {id(msg): i for i, msg in enumerate(self.conversation_history)}
        all_msgs = sorted(obs_list + assistant_msgs, key=lambda m: original_order.get(id(m), 0))

        # 小欧 2026-06-16: 识别每种工具的首次observation
        first_tool_obs = {}
        for msg in obs_list:
            tool_call_id = msg.get("tool_call_id", "")
            if tool_call_id:
                assistant = tool_to_assistant.get(tool_call_id)
                if assistant:
                    for tc in assistant.get("tool_calls", []):
                        tool_name = tc.get("function", {}).get("name", "")
                        if tool_name and tool_name not in first_tool_obs:
                            first_tool_obs[tool_name] = msg

        kept = []
        used_chars = 0
        i = len(all_msgs) - 1

        while i >= 0:
            msg = all_msgs[i]
            tc_id = msg.get("tool_call_id", "")

            if msg.get("role") == "tool" and tc_id and tc_id in tool_to_assistant:
                asst = tool_to_assistant[tc_id]
                pair_chars = self._total_chars([asst, msg])
                # 小欧 2026-06-16: 首次observation强制保留
                is_first_obs = msg in first_tool_obs.values()
                if is_first_obs or used_chars + pair_chars <= budget:
                    kept.append(msg)
                    kept.append(asst)
                    used_chars += pair_chars
                i -= 1
                continue

            msg_chars = self._total_chars([msg])
            if used_chars + msg_chars <= budget:
                kept.append(msg)
                used_chars += msg_chars
            else:
                break
            i -= 1

        kept.reverse()
        return kept

    def _rebuild_and_validate(self, system_msgs, trimmed_msgs):
        """重组消息列表并验证FC配对完整性 — FC-only: trimmed已含obs+assistant"""
        rebuilt = system_msgs + trimmed_msgs
        rebuilt = self._trim_fc_pairs(rebuilt)
        if len(rebuilt) >= 2:
            return rebuilt
        if len(self.conversation_history) > 10:
            return self.conversation_history[:2] + self.conversation_history[-8:]
        return None

    # =========================================================================
    # 第四组:observation 截断辅助
    # =========================================================================

    @staticmethod
    def _get_observation_budget(llm_call_count: int) -> int:
        """计算observation可用预算 — 替代 base_react.py L1378-1382"""
        budget = OBSERVATION_BUDGET_MIN + OBSERVATION_BUDGET_DECAY * max(0, 5 - llm_call_count)
        return min(budget, OBSERVATION_BUDGET_MAX)

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
            else:
                result.append(msg)
        return result

    @staticmethod
    def _total_chars(messages: List[Dict]) -> int:
        """计算消息列表总字符数 — 含tool_calls JSON

        FC模式下assistant消息content可为None(tool_calls协议),
        但tool_calls包含JSON负载(tool名/参数/id),必须计入预算。
        """
        import json
        total = 0
        for msg in messages:
            content = msg.get("content")
            total += len(content) if content is not None else 0
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                total += len(json.dumps(tool_calls, ensure_ascii=False))
        return total
