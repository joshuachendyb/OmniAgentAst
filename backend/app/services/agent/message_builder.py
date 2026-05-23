# -*- coding: utf-8 -*-
"""
MessageBuilder — Prompt/Message组装统一入口

将分散在 base_react.py 和 react_agent_mixin.py 中的
conversation_history操作、observation构建、消息注入逻辑集中管理。

设计原则：
- 所有conversation_history的写操作都通过此类
- observation_text构建独立可测试（静态方法）
- 消息注入(工具/Schema/汇总)独立可测试（静态方法）

【生命周期与会话绑定说明 — 小沈 2026-05-20】：
MessageBuilder 实例生命周期必须与 Agent 实例强绑定，
严禁全局共享单例，防止多会话并发状态污染。

【19.8 修正 — 小沈 2026-05-21】：
- add_assistant() 不自动调 trim_history()，由 _call_llm 统一调度
- build_observation_text() 设计为 @staticmethod，不依赖实例状态
"""

import json
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from app.services.agent.tool_result_formatter import _format_llm_observation


class MessageBuilder:
    """Prompt/Message组装的统一入口"""

    # ===== 观测文本构建常量（从base_react.py搬入）=====
    OBSERVATION_BUDGET_DECAY = 10000
    OBSERVATION_BUDGET_MIN = 20000
    OBSERVATION_HEAD_RATIO = 0.6

    def __init__(self, max_context_chars: int = 150000):
        self.conversation_history: List[Dict[str, Any]] = []
        self.temp_history: List[Dict[str, Any]] = []
        self.MAX_CONTEXT_CHARS = max_context_chars
        # Schema/工具内容缓存
        self._cached_schema_text: Optional[str] = None
        self._cached_tools_content: Optional[str] = None
        self._last_injected_categories: Optional[Any] = None

    def reset_per_run(self) -> None:
        """每次 run_stream 仅重置 conversation_history，缓存和计数保留跨会话"""
        self.conversation_history = []
        self.temp_history = []

    # =========================================================================
    # 第一组：conversation_history 写操作（统一入口）
    # =========================================================================

    def init_history(self, sys_prompt: str, task_prompt: str) -> None:
        """初始化conversation_history — 替代base_react.py L368-369"""
        self.conversation_history = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": task_prompt}
        ]

    def add_assistant(self, content: str) -> None:
        """追加assistant消息 — 替代8处散落的append
        
        【19.8修正】不自动调 trim_history()，由 _call_llm 统一调度。
        """
        self.conversation_history.append({"role": "assistant", "content": content})

    def add_observation(self, observation_text: str, llm_call_count: int = 0, fc_context: Optional[Dict] = None) -> None:
        """追加observation消息 — 含智能截断 + [Observation]前缀归一化 + trim
        
        fc_context: ToolsStrategy下FC协议上下文，含tool_calls和tool_call_id。
        有fc_context时按OpenAI FC协议注入assistant(tool_calls)+tool(tool_call_id)，
        模型能识别"工具已被处理"，不会重复调用。
        """
        budget = self._get_observation_budget(llm_call_count)
        if len(observation_text) > budget:
            observation_text = self._smart_truncate(observation_text, budget=budget)
        observation_text = self._normalize_observation_prefix(observation_text)
        
        if fc_context and fc_context.get("tool_calls"):
            tool_calls = fc_context["tool_calls"]
            tool_call_id = fc_context.get("tool_call_id", "")
            self.conversation_history.append({"role": "assistant", "content": None, "tool_calls": tool_calls})
            self.conversation_history.append({"role": "tool", "content": observation_text, "tool_call_id": tool_call_id})
        else:
            self.conversation_history.append({"role": "system", "content": observation_text})
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
    # 第二组：observation_text 构建（独立可测试，静态方法）
    # =========================================================================

    @staticmethod
    def build_observation_text(execution_result: dict) -> str:
        """根据工具执行结果构建observation文本 — 统一委托_format_llm_observation

        小健 2026-05-22：原手写逻辑已合入 _format_llm_observation（含next_actions），
        此方法保留作为兼容入口。
        """
        return _format_llm_observation(execution_result)

    # =========================================================================
    # 第三组：每轮 LLM 调用的消息组装（从 _call_llm 拆出）
    # =========================================================================

    def prepare_messages_for_llm(self) -> List[Dict[str, Any]]:
        """准备发给LLM的完整消息列表 — 合并原split+merge+assemble

        不再拆出last_message再拼回，整个history作为一个List[Dict]贯穿流程。
        注入点（tools/summary/schema）在第一个非system消息前或末尾操作。
        """
        messages = list(self.conversation_history)
        if self.temp_history:
            messages = messages + list(self.temp_history)
        return messages

    @staticmethod
    def inject_tools_info(
        history_dicts: List[Dict[str, Any]],
        tools_content: str
    ) -> List[Dict[str, Any]]:
        """注入工具信息到 history_dicts
        
        替代 react_agent_mixin.py L339-363
        在第一个非system消息前插入，LLM最先看到工具信息。
        """
        if not tools_content:
            return history_dicts
        tools_msg = {"role": "system", "content": tools_content}
        insert_pos = 0
        for i, msg in enumerate(history_dicts):
            if msg.get("role") != "system":
                insert_pos = i
                break
        else:
            insert_pos = len(history_dicts)
        return list(history_dicts[:insert_pos]) + [tools_msg] + list(history_dicts[insert_pos:])

    @staticmethod
    def inject_schema_text(
        history_dicts: List[Dict[str, Any]],
        schema_text: str
    ) -> List[Dict[str, Any]]:
        """注入Schema文本（仅TextStrategy使用）— 替代 react_agent_mixin.py L381-390"""
        if not schema_text:
            return history_dicts
        return list(history_dicts) + [{"role": "system", "content": schema_text}]

    # =========================================================================
    # 第四组：历史裁剪（从 base_react.py 搬入）
    # =========================================================================

    def trim_history(self) -> None:
        """容量感知的对话历史裁剪 — 替代 base_react.py _trim_history()

        【优化-延迟裁剪机制 — 小沈 2026-05-20】：
        估算当前总字符长度，仅当超过 MAX_CONTEXT_CHARS 的 80% 时触发裁剪，
        否则直接跳过。

        【已知局限 — 小沈 2026-05-21】：
        本方法只移除 role=system 且内容含 [Observation] 标记的 observation 消息。
        system/user/assistant 三类消息不会被删除。因此若 conversation_history
        中不含 observation，即使超过80%阈值也不会真正裁剪。后续如需增强可考虑：
        1. 对 assistant 消息按时间倒序裁剪
        2. 合并相邻短消息
        """
        total = self._total_chars(self.conversation_history)
        if total < self.MAX_CONTEXT_CHARS * 0.8:
            return  # 快速跳过

        # 超过80%阈值，执行裁剪
        budget = int(self.MAX_CONTEXT_CHARS * 0.7)
        system_msgs = []
        obs_list = []
        assistant_msgs = []

        for msg in self.conversation_history:
            role = msg.get("role", "")
            if role == "system" and not self._is_observation_role(msg):
                system_msgs.append(msg)
            elif self._is_observation_role(msg):
                obs_list.append(msg)
            elif role == "assistant":
                assistant_msgs.append(msg)
            else:
                system_msgs.append(msg)

        if len(self.conversation_history) <= 2:
            return

        # 去重observation
        obs_list = self._dedup_by_fingerprint(obs_list)
        # 保留最新assistant
        assistant_msgs = assistant_msgs[-10:]

        # 用最新的observation
        obs_list = obs_list[-30:]

        # 从最旧的开始移除observation，直到满足预算
        while obs_list and self._total_chars(system_msgs + obs_list + assistant_msgs) > budget:
            obs_list.pop(0)

        rebuilt = system_msgs + obs_list + assistant_msgs
        # FC协议配对裁剪：role:tool必须有对应role:assistant(tool_calls)，反之亦然
        rebuilt = self._trim_fc_pairs(rebuilt)
        # 确保至少有 system + user
        if len(rebuilt) >= 2:
            self.conversation_history = rebuilt
        # 如果裁剪过头了，保留至少最近几条
        elif len(self.conversation_history) > 10:
            self.conversation_history = (self.conversation_history[:2]
                                        + self.conversation_history[-8:])

    # =========================================================================
    # 第五组：缓存/失败计数管理（从 base_react.py 搬入）
    # =========================================================================

    def invalidate_cache(self) -> None:
        """清空 Schema/工具内容缓存"""
        self._cached_schema_text = None
        self._cached_tools_content = None
        self._last_injected_categories = None

    # =========================================================================
    # 第七组：Schema 文本生成（从 react_agent_mixin.py 搬入）
    # =========================================================================

    @staticmethod
    def build_schema_text(openai_tools: List[Dict]) -> str:
        """将openai_tools转换为文本格式（方案C）— 迁入自 react_agent_mixin.py L252-292
        小沈 2026-05-21
        """
        if not openai_tools:
            return ""
        lines = ["【Tools Schema参考（仅作参考，实际调用仍以JSON格式返回）】:"]
        for tool in openai_tools:
            func = tool.get("function", {})
            name = func.get("name", "")
            params = func.get("parameters", {})
            properties = params.get("properties", {})
            required = params.get("required", [])
            if not properties:
                lines.append(f"{name}: 无参数")
                continue
            params_list = []
            for pname, pinfo in properties.items():
                ptype = pinfo.get("type", "any")
                pdefault = pinfo.get("default")
                is_required = pname in required
                if pdefault is not None:
                    params_list.append(f"{pname}({ptype}, default={pdefault})")
                elif is_required:
                    params_list.append(f"{pname}({ptype}, required)")
                else:
                    params_list.append(f"{pname}({ptype}, optional)")
            lines.append(f"{name}: {', '.join(params_list)}")
        return "\n".join(lines)

    # =========================================================================
    # 第六组：observation 截断辅助（从 base_react.py 搬入）
    # =========================================================================

    @staticmethod
    def _get_observation_budget(llm_call_count: int) -> int:
        """计算observation可用预算 — 替代 base_react.py L1378-1382"""
        budget = MessageBuilder.OBSERVATION_BUDGET_MIN + MessageBuilder.OBSERVATION_BUDGET_DECAY * max(0, 5 - llm_call_count)
        return min(budget, 50000)

    @staticmethod
    def _smart_truncate(content: str, budget: int, head_ratio: float = None) -> str:
        """智能截断 — 替代 base_react.py L1384-1428"""
        if head_ratio is None:
            head_ratio = MessageBuilder.OBSERVATION_HEAD_RATIO
        if len(content) <= budget:
            return content
        head_budget = int(budget * head_ratio)
        tail_budget = budget - head_budget - 50
        head = content[:head_budget]
        tail = content[-tail_budget:] if tail_budget > 0 else ""
        return f"{head}\n... [中间省略 {len(content) - budget} 字符] ...\n{tail}"

    @staticmethod
    def _normalize_observation_prefix(text: str) -> str:
        """确保observation文本以 [Observation] 开头 — 替代 base_react.py 前缀处理"""
        if text.startswith("[Observation]"):
            return text
        # 去掉已有的 Observation: 前缀变体
        for prefix in ["Observation:", "observation:"]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        return f"[Observation] {text}"

    @staticmethod
    def _is_observation_role(msg: Dict) -> bool:
        """判断消息是否为observation — 替代 base_react.py L1252-1254

        两种形式：
        1. text策略: role=system + content含[Observation]
        2. tools策略(FC协议): role=tool + tool_call_id（与assistant(tool_calls)配对）
        """
        if msg.get("role") == "tool" and msg.get("tool_call_id"):
            return True
        content = msg.get("content", "")
        return msg.get("role") == "system" and ("[Observation]" in content or "Observation:" in content)

    @staticmethod
    def _trim_fc_pairs(messages: List[Dict]) -> List[Dict]:
        """FC协议配对裁剪：确保role:tool与role:assistant(tool_calls)严格配对

        OpenAI要求：assistant消息中每个tool_call.id都必须有对应role:tool(tool_call_id)，
        role:tool的tool_call_id也必须有对应assistant(tool_calls)。
        任一端缺失则双方都移除。
        """
        valid_tool_call_ids = set()
        for msg in messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    tid = tc.get("id")
                    if tid:
                        valid_tool_call_ids.add(tid)
        valid_tool_response_ids = set()
        for msg in messages:
            if msg.get("role") == "tool" and msg.get("tool_call_id"):
                valid_tool_response_ids.add(msg["tool_call_id"])
        paired_ids = valid_tool_call_ids & valid_tool_response_ids
        result = []
        for msg in messages:
            role = msg.get("role", "")
            if role == "tool" and msg.get("tool_call_id"):
                if msg["tool_call_id"] in paired_ids:
                    result.append(msg)
            elif role == "assistant" and msg.get("tool_calls"):
                if all(tc.get("id") in paired_ids for tc in msg["tool_calls"] if tc.get("id")):
                    result.append(msg)
            else:
                result.append(msg)
        return result

    @staticmethod
    def _is_error_obs(content: str) -> bool:
        """判断observation是否为错误 — 替代 base_react.py L1262-1264"""
        return "error" in content.lower() or "timeout" in content.lower() or "fail" in content.lower()

    @staticmethod
    def _dedup_by_fingerprint(obs_list: List[Dict]) -> List[Dict]:
        """基于指纹去重observation — 替代 base_react.py L1267-1278

        FC协议消息(role:tool+tool_call_id)不参与去重：
        同工具重复调用时content可能相同但tool_call_id不同，去重会断裂配对。
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
        """计算消息列表总字符数 — 替代 base_react.py L1281-1283"""
        return sum(len(msg.get("content", "")) for msg in messages)
