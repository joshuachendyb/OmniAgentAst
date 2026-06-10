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

【19.8 修正 — 小沈 2026-05-21】:
- add_assistant() 不自动调 trim_history(),由 _call_llm 统一调度

【2026-05-28 拆分 — 小沈】:
- build_llm_messages() → message_utils.build_llm_messages()
- build_observation_text() → message_utils.build_observation_text()
- inject_tools_info() → message_utils.inject_tools_info()
- inject_schema_text() → message_utils.inject_schema_text()
- build_schema_text() → message_utils.build_schema_text()
"""

import hashlib
from typing import Any, Dict, List, Optional

from app.constants import MAX_CONTEXT_CHARS, OBSERVATION_BUDGET_DECAY, OBSERVATION_BUDGET_MAX, OBSERVATION_BUDGET_MIN, TEMP_HISTORY_CHAR_LIMIT
from app.utils.text_utils import smart_truncate_text






class MessageBuilder:
    """Prompt/Message组装的统一入口"""

    # ===== 观测文本构建常量(从base_react.py搬入)=====
    OBSERVATION_BUDGET_DECAY = OBSERVATION_BUDGET_DECAY
    OBSERVATION_BUDGET_MIN = OBSERVATION_BUDGET_MIN
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
        self.conversation_history = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": task_prompt}
        ]

    def add_assistant(self, content: str) -> None:
        """追加assistant消息 — 替代8处散落的append
        
        【19.8修正】不自动调 trim_history(),由 _call_llm 统一调度。
        """
        self.conversation_history.append({"role": "assistant", "content": content})

    def _prepare_observation_text(self, observation_text: str, llm_call_count: int) -> str:
        """准备observation文本 — 截断+归一化 — 小沈 2026-06-08"""
        budget = self._get_observation_budget(llm_call_count)
        if len(observation_text) > budget:
            observation_text = smart_truncate_text(observation_text, budget=budget)
        observation_text = self._normalize_observation_prefix(observation_text)
        return observation_text

    def _append_observation(self, observation_text: str, fc_context: Optional[Dict] = None) -> None:
        """追加observation消息 — 小沈 2026-06-09 方案G: role=system→user+[Tool Result]"""
        if fc_context and fc_context.get("tool_call_id"):
            tool_call_id = fc_context["tool_call_id"]
            tool_calls = fc_context.get("tool_calls")
            if tool_calls:
                self.conversation_history.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
            self.conversation_history.append({"role": "tool", "content": observation_text, "tool_call_id": tool_call_id})
        else:
            self.conversation_history.append({"role": "user", "content": f"[Tool Result]\n{observation_text}"})

    def add_observation(self, observation_text: str, llm_call_count: int = 0, fc_context: Optional[Dict] = None) -> None:
        """追加observation消息 — 含智能截断 + [Observation]前缀归一化 + trim — 小沈 2026-06-08 重构
        
        fc_context: ToolsStrategy下FC协议上下文,含tool_calls和tool_call_id。
        有fc_context时按OpenAI FC协议注入assistant(tool_calls)+tool(tool_call_id),
        模型能识别"工具已被处理",不会重复调用。
        """
        observation_text = self._prepare_observation_text(observation_text, llm_call_count)
        self._append_observation(observation_text, fc_context)
        self.trim_history()

    def add_parse_error(self, error_msg: str) -> None:
        """追加解析错误到history — 替代base_react.py L643"""
        self.add_observation(
            f"Parse Error: {error_msg}. Please ensure your response follows the ReAct format.",
            llm_call_count=0
        )

    def flush_temp_to_history(self, chunk_buffer: str) -> None:
        """将chunk_buffer从temp_history刷入正式history — 替代L558-562/L689-693"""
        self.temp_history.clear()
        if chunk_buffer:
            self.add_assistant(chunk_buffer)

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
        """容量感知的对话历史裁剪 — P2-8 SLAP拆分"""
        total = self._total_chars(self.conversation_history)
        if total < self.MAX_CONTEXT_CHARS * 0.8:
            return
        if len(self.conversation_history) <= 2:
            return

        system_msgs, obs_list, assistant_msgs = self._classify_messages()
        budget = int(self.MAX_CONTEXT_CHARS * 0.7)
        trimmed_obs = self._trim_to_budget(obs_list, assistant_msgs, budget)
        rebuilt = self._rebuild_and_validate(system_msgs, trimmed_obs, assistant_msgs)
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
        """去重+截断observation,保留最新assistant,直到满足预算"""
        obs_list = self._dedup_by_fingerprint(obs_list)
        assistant_msgs = assistant_msgs[-10:]
        obs_list = obs_list[-30:]
        while obs_list and self._total_chars(obs_list) > budget:
            obs_list.pop(0)
        return obs_list

    def _rebuild_and_validate(self, system_msgs, obs_list, assistant_msgs):
        """重组消息列表并验证FC配对完整性,返回None表示无需更新"""
        rebuilt = system_msgs + obs_list + assistant_msgs
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
        budget = MessageBuilder.OBSERVATION_BUDGET_MIN + MessageBuilder.OBSERVATION_BUDGET_DECAY * max(0, 5 - llm_call_count)
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
        """判断消息是否为observation — 小沈 2026-06-09 方案G: 识别role=user+[Tool Result]

        三种形式:
        1. text策略: role=user + content含[Tool Result]
        2. tools策略(FC协议): role=tool(与assistant(tool_calls)配对)
        """
        if msg.get("role") == "tool":
            return True
        content = msg.get("content", "")
        return msg.get("role") == "user" and "[Tool Result]" in content

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

    def _dedup_by_fingerprint(obs_list: List[Dict]) -> List[Dict]:
        """基于指纹去重observation — 替代 base_react.py L1267-1278

        FC协议消息(role:tool+tool_call_id)不参与去重:
        同工具重复调用时content可能相同但tool_call_id不同,去重会断裂配对。
        """
        seen = set()
        result = []
        for obs in obs_list:
            if obs.get("role") == "tool" and obs.get("tool_call_id"):
                result.append(obs)
                continue
            content = obs.get("content", "")
            fp = hashlib.md5(content.encode()).hexdigest()[:16]
            if fp not in seen:
                seen.add(fp)
                result.append(obs)
        return result

    @staticmethod
    def _total_chars(messages: List[Dict]) -> int:
        """计算消息列表总字符数 — 替代 base_react.py L1281-1283

        FC模式下assistant消息content可为None(tool_calls协议),
        msg.get("content", "")在key存在但值为None时返回None而非默认值,
        len(None)会TypeError。必须显式处理None。
        """
        total = 0
        for msg in messages:
            content = msg.get("content")
            total += len(content) if content is not None else 0
        return total
