# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 新建: A4 工具门面(方案4.4.3步骤1) — list_tools 只读组装; execute_tool 复用 tool_executor
#   统一执行入口(tool_executor 内部已 ContextVar 注入 hooks), facade 只做安全预检 + task 上下文管理(try/finally reset)。
#   按真实代码实现: 安全预检用 get_tool_safety_checker().check_before_execute(设计4.4.3示例 check_tool_safety 不存在, 已按实测落地);
#   agent 构造带 _security_hooks(与 action_handler 对齐), 供 tool_executor getattr 通道识别。
"""
tool_facade — 工具门面(API 适配层)

职责(方案4.4.3, 小欧 2026-08-12):
  - list_tools: 工具列表只读组装(无安全检查);
  - execute_tool: 安全预检 + 复用 tool_executor 统一执行(注入 DefaultToolSecurityHooks, 消除双路径)。

依赖方向: services/tool → safety(checker) + services/agent(tool_executor) + tools(registry), 单向无环。
"""
import uuid

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.tools.tool_retry_engine import ToolRetryEngine
from app.safety.tool_safety_checker import get_tool_safety_checker
from app.safety.default_hooks import DefaultToolSecurityHooks
from app.services.task.task_context import _current_task_id
from app.logger import logger

# 模块级惰性缓存: 全量工具实现表(与 ToolLoader 同源的 registry 公共 API 构建, 不摸私有字段)。
# 供 _FacadeAgent._retry_engine(→tool_executor 非并行分支)复用 — 小欧 2026-08-12
_tools_dict: dict = {}


def _get_tool_dict() -> dict:
    global _tools_dict
    if not _tools_dict:
        _tools_dict = {}
        for cat in ToolCategory:
            _tools_dict.update(tool_registry.get_implementations_by_category(cat))
        logger.info(f"[tool_facade] 构建工具实现表, 共{len(_tools_dict)}个工具")
    return _tools_dict


def list_tools() -> dict:
    """供 API 调用的工具列表(只读, 无安全检查) — 小欧 2026-08-12"""
    tools = tool_registry.to_openai_tools()
    result = []
    for t in tools:
        func = t.get('function', {})
        name = func.get('name', '')
        desc = func.get('description', '')
        params = func.get('parameters', {})
        required = params.get('required', [])
        props = list(params.get('properties', {}).keys())
        required_set = set(required)
        result.append({
            "name": name,
            "description": desc[:100] if desc else "",
            "required_params": required,
            "optional_params": [p for p in props if p not in required_set],
            "inputSchema": params,
        })
    return {"total": len(result), "tools": result}


async def execute_tool(tool_name: str, params: dict) -> dict:
    """供 API 调用的安全工具执行入口 — 复用 tool_executor 统一执行路径 — 小欧 2026-08-12

    返回结构对齐 health.py 原 /tool/execute 的 ToolExecuteResponse 语义:
    {success, result | error, tool_name}
    """
    # 1. 安全预检(与 action_handler.check_safety_and_confirm 同源) — 小欧 2026-08-12
    safety = get_tool_safety_checker().check_before_execute(tool_name, params or {})
    if safety.blocked:
        return {"tool_name": tool_name, "success": False, "error": f"安全拦截: {safety.message}"}
    if safety.requires_confirmation and not safety.auto_confirm:
        # 测试接口无前端 HITL: 仅 auto_confirm(安全开关关闭)直放, 其余返回待确认
        return {"tool_name": tool_name, "success": False,
                "error": f"需要用户确认工具执行({tool_name}), 测试接口不支持交互确认"}

    # 2. 设置任务上下文(try/finally reset, 防 ContextVar 泄漏污染并发) — 小欧 2026-08-12
    task_id = str(uuid.uuid4())
    token = _current_task_id.set(task_id)
    try:
        # 3. 复用 tool_executor(统一执行入口): 构造轻量 agent, tool_executor 内 getattr(_security_hooks)→DefaultToolSecurityHooks,
        #    并 set/finally reset 到 ContextVar hooks — 与 chat 路径共享同一 executor + hooks, 消除双路径
        from app.services.agent.tool_executor import execute_tool as _exec

        class _FacadeAgent:
            _security_hooks = DefaultToolSecurityHooks()
            _tools_dict = _get_tool_dict()
            _retry_engine = ToolRetryEngine(_tools_dict)

        result = await _exec(_FacadeAgent(), tool_name, params or {})
        return {"tool_name": tool_name, "success": True,
                "result": result if isinstance(result, dict) else {"output": str(result)}}
    finally:
        _current_task_id.reset(token)