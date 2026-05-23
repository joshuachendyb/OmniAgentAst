"""
已废弃的adapter代码 — 从adapter.py和llm_adapter.py移出的死代码
保留备用，业务代码不引用

移出时间: 2026-05-23
原因: 业务代码中无任何调用者
"""

from typing import Any, Dict, List, Optional
import copy

# ============================================================
# 从 adapter.py 移出的 Phase 3 ReAct转换函数
# ============================================================

def observation_to_llm_input(observation_step: Dict[str, Any]) -> str:
    if not isinstance(observation_step, dict):
        return "Observation: unknown"
    status = observation_step.get("execution_status", observation_step.get("status", "unknown"))
    summary = observation_step.get("summary", "")
    return f"Observation: {status} - {summary}"


def thought_to_message(thought_step: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(thought_step, dict):
        return {"role": "assistant", "content": ""}
    return {"role": "assistant", "content": thought_step.get("content", "")}


def action_tool_to_message(action_tool_step: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(action_tool_step, dict):
        return {"role": "user", "content": ""}
    status = action_tool_step.get("execution_status", "unknown")
    summary = action_tool_step.get("summary", "")
    content = f"Observation: {status} - {summary}"
    return {"role": "user", "content": content}


# ============================================================
# 从 llm_adapter.py 积出的 build_messages / build_tools
# ============================================================

class _LLMAdapterDeadCode:
    """llm_adapter.py 中 build_messages/build_tools 的逻辑，业务代码未调用"""
    
    def __init__(self, os_adapter=None):
        self.os_adapter = os_adapter
    
    def build_messages(self, messages: Optional[list] = None, system_override: Optional[str] = None) -> list:
        result = []
        system_content = system_override or (self.os_adapter.get_system_prompt() if self.os_adapter else "")
        result.append({"role": "system", "content": system_content})
        if messages:
            result.extend(messages)
        return result
    
    def build_tools(self, tools: list) -> list:
        if not tools:
            return tools
        tool_hints = self.os_adapter.get_tool_descriptions() if self.os_adapter else {}
        enriched_tools = []
        for tool in tools:
            enriched_tool = copy.deepcopy(tool)
            if "function" in enriched_tool:
                func = enriched_tool["function"]
                if "parameters" in func:
                    params = func["parameters"]
                    if "properties" in params:
                        if "path" in params["properties"]:
                            params["properties"]["path"]["description"] = tool_hints.get("path", "")
            enriched_tools.append(enriched_tool)
        return enriched_tools
