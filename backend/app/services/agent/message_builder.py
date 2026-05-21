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
- add_assistant() 不自动调 trim_history()，由 _call_llm_with_summary 统一调度
- build_observation_text() 设计为 @staticmethod，不依赖实例状态
"""

import json
import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple


class MessageBuilder:
    """Prompt/Message组装的统一入口"""

    # ===== 观测文本构建常量（从base_react.py搬入）=====
    OBSERVATION_BUDGET_DECAY = 10000
    OBSERVATION_BUDGET_MIN = 20000
    OBSERVATION_HEAD_RATIO = 0.6

    def __init__(self, max_context_chars: int = 150000):
        self.conversation_history: List[Dict[str, Any]] = []
        self.temp_history: List[Dict[str, Any]] = []
        self._executed_tool_summary: List[str] = []
        self._failed_attempts: Dict[str, int] = {}
        self._executed_cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl: int = 60
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
        
        【19.8修正】不自动调 trim_history()，由 _call_llm_with_summary 统一调度。
        """
        self.conversation_history.append({"role": "assistant", "content": content})

    def add_observation(self, observation_text: str, llm_call_count: int = 0) -> None:
        """追加observation消息（role=system）— 替代_add_observation_to_history
        
        含智能截断 + [Observation]前缀归一化 + trim。
        """
        # 智能截断
        budget = self._get_observation_budget(llm_call_count)
        if len(observation_text) > budget:
            observation_text = self._smart_truncate(observation_text, budget=budget)
        # 统一[Observation]前缀
        observation_text = self._normalize_observation_prefix(observation_text)
        # 追加
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
        """根据工具执行结果构建observation文本 — 替代base_react.py L831-910
        
        工具层统一返回 {code, data, message} 格式后，observation构建简化为：
          - SUCCESS → message + （llm_data优先于data）
          - WARNING_ → message + 部分数据
          - ERR_*   → [code] + message
        """
        code = execution_result.get("code", "SUCCESS")
        message = execution_result.get("message", "")
        display_data = execution_result.get("llm_data") or execution_result.get("data")

        if code == "SUCCESS":
            text = f"Observation: success - {message}"
            if execution_result.get("warning"):
                text += f"\n⚠ 警告: {execution_result['warning']}"
            if display_data:
                text += f"\n数据: {json.dumps(display_data, ensure_ascii=False)}"
            return text
        elif code.startswith("WARNING_"):
            text = f"Observation: warning - {message}"
            if display_data:
                text += f"\n部分数据: {json.dumps(display_data, ensure_ascii=False)}"
            return text
        else:  # ERR_*
            return f"Observation: error [{code}] - {message}"

    # =========================================================================
    # 第三组：每轮 LLM 调用的消息组装（从 _call_llm_with_summary 拆出）
    # =========================================================================

    def split_history_for_llm(self) -> Tuple[str, List[Dict[str, Any]]]:
        """将conversation_history拆分为last_message和history_dicts
        
        替代 react_agent_mixin.py L310-322
        """
        last_user_idx = -1
        for i in range(len(self.conversation_history) - 1, -1, -1):
            if self.conversation_history[i].get("role") == "user":
                last_user_idx = i
                break

        if last_user_idx >= 0:
            last_message = self.conversation_history[last_user_idx]["content"]
            history_dicts = (self.conversation_history[:last_user_idx]
                           + self.conversation_history[last_user_idx + 1:])
        else:
            last_message = self.conversation_history[-1]["content"]
            history_dicts = self.conversation_history[:-1]

        return last_message, history_dicts

    def merge_temp_history(self, history_dicts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并temp_history — 替代 react_agent_mixin.py L324-326"""
        if self.temp_history:
            return list(history_dicts) + list(self.temp_history)
        return history_dicts

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
    def inject_executed_summary(
        history_dicts: List[Dict[str, Any]],
        executed_tool_summary: List[str]
    ) -> List[Dict[str, Any]]:
        """注入已执行工具汇总 — 替代 react_agent_mixin.py L365-371"""
        done_tools = [s for s in executed_tool_summary if '→success' in s]
        if not done_tools:
            return history_dicts
        progress = ("【已执行工具(勿重复)】" + "; ".join(done_tools[-8:])
                   + "\n注意：上述工具已成功执行，结果已在Observation中，禁止再次调用！")
        return list(history_dicts) + [{"role": "system", "content": progress}]

    @staticmethod
    def inject_schema_text(
        history_dicts: List[Dict[str, Any]],
        schema_text: str
    ) -> List[Dict[str, Any]]:
        """注入Schema文本（仅TextStrategy使用）— 替代 react_agent_mixin.py L381-390"""
        if not schema_text:
            return history_dicts
        return list(history_dicts) + [{"role": "system", "content": schema_text}]

    @staticmethod
    def assemble_messages(
        history_dicts: List[Dict[str, Any]],
        last_message: str
    ) -> List[Dict[str, Any]]:
        """组装最终发给LLM的messages — 替代 react_agent_mixin.py L394-395"""
        return list(history_dicts) + [{"role": "user", "content": last_message}]

    # =========================================================================
    # 第四组：历史裁剪（从 base_react.py 搬入）
    # =========================================================================

    def trim_history(self) -> None:
        """容量感知的对话历史裁剪 — 替代 base_react.py _trim_history()

        【优化-延迟裁剪机制 — 小沈 2026-05-20】：
        估算当前总字符长度，仅当超过 MAX_CONTEXT_CHARS 的 80% 时触发裁剪，
        否则直接跳过。
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

    @staticmethod
    def _params_to_key(params: dict) -> str:
        """参数 → MD5 key — 替代 base_react.py L208-217"""
        param_str = json.dumps(params, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(param_str.encode()).hexdigest()

    @staticmethod
    def _is_no_cache_tool(tool_name: str, tool_params: dict) -> bool:
        """判断工具是否不应缓存 — 小沈 2026-05-21"""
        _NO_CACHE_TOOLS = {"ping", "port_check"}
        if tool_name in _NO_CACHE_TOOLS:
            return True
        if tool_name == "execute_shell_command" and tool_params:
            command = str(tool_params.get("command", "")).lower()
            if any(kw in command for kw in ["ping", "tracert", "curl", "wget"]):
                return True
        return False

    def check_cache_or_block(self, tool_name: str, tool_params: dict) -> tuple:
        """缓存检查+失败拦截 — 整合 base_react.py L768-801
        返回: (execution_result, observation_prefix, cache_hit, fail_count)
        """
        cache_key = f"{tool_name}:{self._params_to_key(tool_params)}"
        observation_prefix = ""
        cache_hit = False
        execution_result = None
        fail_count = self._failed_attempts.get(cache_key, 0)
        
        # 失败拦截
        if fail_count >= 3:
            execution_result = {
                "code": "ERR_BLOCKED",
                "message": f"已连续失败{fail_count}次，系统强制跳过",
                "data": None,
                "error": f"{tool_name} 已连续失败{fail_count}次"
            }
            observation_prefix = f"[系统拦截] {tool_name} 已连续失败{fail_count}次，强制跳过执行。请换用其他工具或方法。\n"
            return execution_result, observation_prefix, cache_hit, fail_count
        
        # 缓存检查
        if not self._is_no_cache_tool(tool_name, tool_params) and cache_key in self._executed_cache:
            cached_time = self._cache_timestamps.get(cache_key, 0)
            if time.time() - cached_time < self._cache_ttl:
                execution_result = self._executed_cache[cache_key]
                observation_prefix = "[缓存命中] 此命令已执行过，结果已在上方Observation中。禁止再次调用相同工具+参数！ "
                cache_hit = True
            else:
                del self._executed_cache[cache_key]
                del self._cache_timestamps[cache_key]
        
        return execution_result, observation_prefix, cache_hit, fail_count

    def update_execution_cache(self, tool_name: str, tool_params: dict, execution_result: dict, exec_status: str) -> str:
        """更新缓存+失败计数+汇总 — 整合 base_react.py L898-936
        返回: observation附加文本（失败警告）
        """
        cache_key = f"{tool_name}:{self._params_to_key(tool_params)}"
        extra_text = ""
        
        if exec_status == 'success':
            if not self._is_no_cache_tool(tool_name, tool_params):
                self._executed_cache[cache_key] = execution_result
                self._cache_timestamps[cache_key] = time.time()
            if cache_key in self._failed_attempts:
                del self._failed_attempts[cache_key]
        elif exec_status in ('error', 'timeout', 'permission_denied', 'blocked'):
            _fc = self._failed_attempts.get(cache_key, 0) + 1
            self._failed_attempts[cache_key] = _fc
            if _fc >= 2:
                extra_text += f"\n[此操作已失败{_fc}次]"
            if _fc >= 3:
                extra_text += "\n[⚠️ 禁止再尝试此操作！必须使用其他方法或换URL]"
        
        # 已执行工具汇总
        summary_entry = self.build_summary_entry(tool_name, tool_params, exec_status)
        if summary_entry:
            self._executed_tool_summary.append(summary_entry)
            if len(self._executed_tool_summary) > 50:
                self._executed_tool_summary = self._executed_tool_summary[-30:]
        
        # 限制失败计数器长度
        if len(self._failed_attempts) > 100:
            self._failed_attempts = dict(list(self._failed_attempts.items())[-50:])
        
        return extra_text

    @staticmethod
    def build_summary_entry(tool_name: str, tool_params: dict, exec_status: str) -> str:
        """构建汇总条目 — 整合 base_react.py L915-931"""
        if tool_name == "http_request" and tool_params:
            _url = str(tool_params.get("url", ""))[:60]
            return f"http_request({_url})→{exec_status}"
        elif tool_name == "ping" and tool_params:
            _host = str(tool_params.get("host", ""))
            return f"ping({_host})→{exec_status}"
        elif tool_name == "port_check" and tool_params:
            _host = str(tool_params.get("host", ""))
            _port = tool_params.get("port", "")
            return f"port_check({_host}:{_port})→{exec_status}"
        elif tool_name == "execute_shell_command" and tool_params:
            _cmd = str(tool_params.get("command", ""))[:50]
            return f"shell({_cmd})→{exec_status}"
        elif tool_name != "finish":
            return f"{tool_name}→{exec_status}"
        return ""

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
        """判断消息是否为observation — 替代 base_react.py L1252-1254"""
        content = msg.get("content", "")
        return msg.get("role") == "system" and ("[Observation]" in content or "Observation:" in content)

    @staticmethod
    def _is_error_obs(content: str) -> bool:
        """判断observation是否为错误 — 替代 base_react.py L1262-1264"""
        return "error" in content.lower() or "timeout" in content.lower() or "fail" in content.lower()

    @staticmethod
    def _dedup_by_fingerprint(obs_list: List[Dict]) -> List[Dict]:
        """基于指纹去重observation — 替代 base_react.py L1267-1278"""
        seen = set()
        result = []
        for obs in obs_list:
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
