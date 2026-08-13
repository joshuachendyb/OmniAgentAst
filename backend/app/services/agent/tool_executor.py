# -*- coding: utf-8 -*-
"""
tool_executor — 工具执行逻辑

从universal_agent拆出 — 小沈 2026-06-17
"""

# 编辑历史:
# 2026-08-05 小欧 修复BUG1/2(三堂会审通过): auto_inject_from_search只对未加载分类调load_category并尊重返回值, 去掉对已加载分类的多余重复调用; 空实现分类不再被误标为已加载
# 2026-08-12 小欧 A1后半面(4.1.7定案): execute_tool 入口注入安全 hooks(经 ContextVar, try/finally reset),
#   并行/顺序两分支工具内 get_current_hooks() 读到注入值; getattr 通道支持子类自定义 hooks(OCP)
# 2026-08-13 小欧 A4收尾解耦: execute_tool 显式接收 retry_engine 依赖(去除对 agent._retry_engine 私有字段的强耦合, KISS-DIRECT);
#   两调用方(action_handler/tool_facade)显式传入同一引擎对象, 行为不变, 无退化; searchtool 自动注入仍走 agent 内部状态(领域正确)
import time
from typing import Any, Callable, Dict, Optional, Set

from app.tools.tool_types import ToolCategory
from app.tools.tool_response import is_success
from app.logger import logger
from app.services.agent.tool_cache_manager import invalidate_tool_cache, patch_search_desc
from app.safety.default_hooks import DefaultToolSecurityHooks  # A1: 默认 hooks 转发壳 — 小欧 2026-08-12
from app.tools.context import set_current_hooks, reset_current_hooks  # A1: ContextVar 注入 — 小欧 2026-08-12


async def execute_tool(agent, tool_name: str, tool_params: Dict[str, Any],
                       retry_engine: Any,
                       parallel: bool = False,
                       on_retry_started: Optional[Callable] = None) -> Dict[str, Any]:
    """执行工具（单入口）— 根据parallel参数分派try_once或带重试执行
     
    职责（SRP：只决定「执行方式」，不重写重试逻辑）：
    1. parallel=True → 调retry_engine.try_once() → 一次执行，不重试
       适用场景：action_handler并行分支（asyncio.gather），瞬态失败概率低
    2. parallel=False → 调retry_engine.execute_tool_with_retry() → 带重试
       适用场景：单工具/顺序执行，需要自动重试瞬态失败
     
    无论哪种路径，统一处理：
    - 耗时统计 + 日志输出
    - is_success状态判断
    - searchtool自动注入（searchtool成功时自动注入整个工具类别给LLM）
     
    Args:
        agent: UniversalAgent实例
        tool_name: 工具名
        tool_params: 工具参数字典
        parallel: True=并行模式用try_once，False=顺序模式用execute_tool_with_retry
        on_retry_started: 仅在parallel=False时透传给execute_tool_with_retry
     
    小健 2026-06-26: 修复状态判断逻辑
    小欧 2026-07-09: 新增parallel/on_retry_started参数，支持并行无重试模式
    """
    
    start = time.time()
    # A1(4.1.7 定案): 注入安全 hooks 到 ContextVar — 并行/顺序两分支统一覆盖。
    #   getattr 通道: 子类可在 agent 上挂 _security_hooks 自定义实现(OCP), 缺省用 DefaultToolSecurityHooks。
    _hooks = getattr(agent, "_security_hooks", None) or DefaultToolSecurityHooks()
    _hook_token = set_current_hooks(_hooks)
    try:
        if parallel:
            # 并行分支：一次执行不重试，失败信息直接返回给LLM决策
            result = await retry_engine.try_once(tool_name, tool_params)
        else:
            # 单工具/顺序分支：带重试+回调通知
            result = await retry_engine.execute_tool_with_retry(
                tool_name, tool_params, on_retry_started=on_retry_started,
            )
    finally:
        reset_current_hooks(_hook_token)
    elapsed = time.time() - start
    
    # 小健 2026-06-26: 使用is_success函数判断状态，而非错误的result.get("code")
    status = "ok" if is_success(result) else "fail"
    _log_single_tool(tool_name, tool_params, elapsed, status)
    
    if tool_name == "searchtool":
        auto_inject_from_search(agent, result)
    return result


def _log_single_tool(tool_name: str, params: Dict[str, Any], elapsed: float, status: str) -> None:
    """一行格式: [tool_executor] tool=xxx, 耗时=0.35s, 状态=ok, params无敏感字段"""
    keys = list(params.keys()) if params else []
    logger.info(f"[tool_executor] tool={tool_name}, 耗时={elapsed:.2f}s, 状态={status}, params={keys}")


def auto_inject_from_search(agent, result: Dict[str, Any]) -> None:
    """从searchtool结果自动注入整个工具类给LLM — 小欧 2026-06-23

    P0-4修复: 匹配到一个工具，就把该工具所在的整个类(如NETWORK)全部注入LLM。
    因为LLM知道类名后就能理解该类的所有工具，无需逐个注入。
    
    注意：注入(inject)是指将工具描述提供给LLM使用，工具函数已在启动时注册(register)
    """
    data = result.get("data", {})
    llm_matches = data.get("matches", [])
    if not llm_matches:
        return

    # 收集匹配工具所属的tool类别
    new_categories: Set[ToolCategory] = set()
    for m in llm_matches:
        cat_str = m.get("category", "")
        if cat_str:
            try:
                new_categories.add(ToolCategory(cat_str))
            except ValueError:
                continue

    if not new_categories:
        return

    # 只对尚未加载的分类调用load_category(单一权威, 见base_agent.load_category)
    # 2026-08-05 小欧 修复BUG1/2: 空实现分类load_category返回False, 不再被标记为已加载;
    #   同时去掉对已加载分类的多余重复调用
    loaded_any = False
    for cat in new_categories:
        if cat in agent._loaded_categories:
            continue
        if agent._tool_loader.load_category(cat):
            loaded_any = True

    if not loaded_any:
        return

    # 已加载分类的工具实现已在上方循环内写入_tools_dict
    invalidate_tool_cache(agent)
    patch_search_desc(agent)
