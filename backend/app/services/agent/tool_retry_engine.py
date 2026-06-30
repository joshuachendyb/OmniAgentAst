# -*- coding: utf-8 -*-
"""
统一工具重试引擎 — 工具的外部重试机制

物理位置: Agent编排层(被 UniversalAgent.run_react_cycle 调用)
归属分层: 【工具层】— 虽在编排层目录，但本质是工具的外部重试机制，引用工具层常量

小沈 - 2026-06-08 P1-7/8/9: 参数非法改报错, 删全局单例改Agent实例变量, 合并tool_executor重复查找
小欧 - 2026-06-30: 明确分层归属(工具的外部重试 → 工具层)，常量全部引自 tool_constants

【分层规范 - 小健 2026-05-27】
本文件是工具的【外部重试】，使用 tool_result_utils.py 的 create_xxx 函数
禁止使用 _response.py 的 build_xxx 函数(那是工具层内部响应用的)

负责统一处理工具执行的重试逻辑,消除双重实现
Author: 小沈 - 2026-05-27
"""

import asyncio
import inspect
from typing import Any, Callable, Dict, Optional

from app.utils.logger import logger
from app.tools.tool_error_classifier import ToolErrorClassifier
from app.tools.tool_constants import (
    TOOL_TIMEOUTS, TOOL_RETRY_BACKOFF,
    ERR_MISSING_PARAM, ERR_INVALID_PARAMS, ERR_TOOL_NOT_FOUND, ERR_UNKNOWN,
)
from app.tools.tool_response import build_error


# TOOL_RETRY_CONFIG: 按 tool 名直配重试参数
# 不在字典中的 tool → max_retries=0（不重试）。默认不重试的 tool 不列入字典。
# 返回格式: {tool名: {"max_retries": int, "retryable": list[str]}}
# 注意: retryable 列表中的字符串必须与 ToolErrorCategory.value 完全匹配
TOOL_RETRY_CONFIG = {
    "http_request": {"max_retries": 3, "retryable": ["timeout", "connect", "network", "protocol"]},
    "download_file": {"max_retries": 3, "retryable": ["timeout", "connect", "network", "protocol"]},
    "fetch_webpage": {"max_retries": 2, "retryable": ["timeout", "connect", "network", "protocol"]},
    "search_web": {"max_retries": 2, "retryable": ["timeout", "connect", "network"]},
    # shell/代码: 非幂等+永久性错误为主，工具内部已 catch 所有异常，
    # 不会传播到 retry engine，不在字典中即默认不重试 — 小欧 2026-06-30
    "network_diagnose": {"max_retries": 2, "retryable": ["timeout", "connect"]},
}


class ToolRetryEngine:
    """统一工具重试引擎 — 绑定Agent的工具字典"""
    
    def __init__(self, tools: Dict[str, Callable]):
        self._tools = tools
    
    async def _execute_tool_once(self, tool: Callable, normalized_input: Dict[str, Any], 
                                timeout: float) -> Any:
        """
        统一单次工具调用 — 小沈 2026-06-08 重构
        小健 2026-06-18 内联_is_async_tool/_execute_async_tool/_execute_sync_tool
        
        修复:纯同步工具通过 to_thread 移出事件循环,wait_for 超时保护生效。
        """
        if inspect.iscoroutinefunction(tool):
            return await asyncio.wait_for(tool(**normalized_input), timeout=timeout)
        result = await asyncio.wait_for(
            asyncio.to_thread(lambda: tool(**normalized_input)), timeout=timeout
        )
        if inspect.iscoroutine(result):
            return await asyncio.wait_for(result, timeout=timeout)
        return result
    
    def _build_retry_error(
        self, code: str, message: str, retry_count: int,
        *, error_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """统一构建重试相关错误响应 — 小欧 2026-06-21 适配新3字段result"""
        return build_error(
            data={"error_detail": message, "params": {}},
            llm_data={
                "summary": message[:200],
                "action": {"tool": "", "tool_zh": "", "target": "", "params": {}},
                "status": {"exec_code": "error", "message": message[:200], "code": code, "detail": message, "hint": ""},
                "duration_ms": 0,
                "metrics": {},
            },
            other_data={"retry_count": retry_count},
            error_type=error_type or "unknown",
        )
    
    def _get_retry_config(self, action: str):
        """获取重试配置 — 按 tool 名直配 — 小欧 2026-06-29"""
        config = TOOL_RETRY_CONFIG.get(action, {})
        return (
            config.get("max_retries", 0),
            TOOL_RETRY_BACKOFF["default"],  # 直接使用默认退避因子
            config.get("retryable", []),  # 修正：使用 retryable 而不是 retryable_errors
            TOOL_TIMEOUTS.get(action, TOOL_TIMEOUTS["default"]),
        )
    
    async def execute_tool_with_retry(
        self,
        action: str,
        action_input: Dict[str, Any],
    ) -> Dict[str, Any]:
        """统一工具执行方法 — FC-only: 无finish分支
        
        小欧 2026-06-27: 增加参数名别名映射，解决LLM返回参数名不匹配问题
        """
        tool = self._tools.get(action)
        if tool is None:
            return build_error(
                data={"error_detail": f"工具 '{action}' 未找到", "params": {"action": action}},
                llm_data={
                    "summary": f"工具 '{action}' 未找到",
                    "action": {"tool": action, "tool_zh": "", "target": "", "params": {"action": action}},
                    "status": {"exec_code": "error", "message": f"工具 '{action}' 未找到", "code": ERR_TOOL_NOT_FOUND, "detail": f"可用工具: {list(self._tools.keys())}", "hint": "该工具未注入。请先调用 tool_search 搜索该工具名称(如'网络 搜索')，系统会自动注入整个工具分类。"},
                    "duration_ms": 0,
                    "metrics": {},
                },
                other_data={"retry_count": 0},
                error_type="tool_not_found",
            )
        
        # 参数名别名映射 — 小欧 2026-06-27
        # 解决LLM返回参数名不匹配问题（如返回path而非file_path）
        from app.tools.param_alias_mapper import normalize_params
        normalized_input, has_mapping = normalize_params(action, action_input)
        
        params = self._validate_params(action, normalized_input, tool)
        _ec = params.get("llm_data", {}).get("status", {}).get("exec_code", "") if isinstance(params, dict) else ""
        if _ec == "error":
            return params
        
        return await self._execute_with_retry(action, params, tool)
    
    def _validate_params(self, action: str, action_input: Dict[str, Any], tool: Callable):
        """验证参数（非法参数+必需参数）— P1-05修复: 返回错误字典而非None
        小健 2026-06-18 合并_are_params_valid和_check_missing_params为一次查询"""
        params = action_input.copy()
        
        try:
            from app.tools.registry import tool_registry
            metadata = tool_registry.get_tool(action)
            if metadata and metadata.input_schema:
                input_schema = metadata.input_schema
                valid_params = set(input_schema.get("properties", {}).keys())
                invalid_keys = [k for k in params if k not in valid_params]
                if invalid_keys:
                    logger.warning(f"[参数验证] action={action} 含非法字段: {invalid_keys}")
                    return self._build_retry_error(
                        ERR_INVALID_PARAMS,
                        f"参数验证失败: {action} 含非法参数, keys={list(params.keys())}",
                        0, error_type="invalid_params",
                    )
                
                required = input_schema.get("required", [])
                missing = [p for p in required if p not in params]
                if missing:
                    return self._build_retry_error(
                        ERR_MISSING_PARAM,
                        f"缺少必需参数: {action}, 缺失: {missing}",
                        0, error_type="missing_param",
                    )
        except (ImportError, AttributeError) as e:
            logger.warning(f"[参数验证] action={action}, 获取schema失败: {e}", exc_info=True)

        
        return params
    
    def _should_retry(self, e: Exception, retryable_errors: list, attempt: int, max_retries: int) -> bool:
        """判断是否应该重试 — 只查 per-tool 配置，不查 is_retryable — 小欧 2026-06-29"""
        error_category = ToolErrorClassifier.classify_tool_error(e)
        # 使用 error_category.value 进行匹配，因为 TOOL_RETRY_CONFIG 中的字符串是 ToolErrorCategory.value
        is_retryable = error_category.value in retryable_errors
        return is_retryable and attempt < max_retries

    async def _execute_with_retry(self, action: str, params: Dict[str, Any], tool: Callable) -> Dict[str, Any]:
        """带重试执行工具 — 内联版，去掉 RetryEngine 中介层 — 小欧 2026-06-29"""
        max_retries, backoff_factor, retryable_errors, timeout = self._get_retry_config(action)

        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                result = await self._execute_tool_once(tool, params, timeout)
                if isinstance(result, dict):
                    other = result.get("other_data", {})
                    if not isinstance(other, dict):
                        other = {}
                    other["retry_count"] = attempt
                    result["other_data"] = other
                    return result
                return result
            except Exception as e:
                last_error = e
                error_category = ToolErrorClassifier.classify_tool_error(e)

                # 超时/网络错误不打印堆栈，只有未知错误才打印 — 小沈 2026-06-28
                should_print_traceback = error_category.name in ("UNKNOWN", "INTERNAL")
                logger.warning(
                    f"[重试] action={action} 尝试{attempt + 1}/{max_retries + 1} "
                    f"失败：{error_category.description} - {str(e)[:100]}",
                    exc_info=should_print_traceback
                )

                if not self._should_retry(e, retryable_errors, attempt, max_retries):
                    return self._build_retry_error(
                        f"ERR_{error_category.name}",
                        f"{error_category.description}: {str(e)[:200]}",
                        attempt, error_type=error_category.name.lower(),
                    )

                delay = backoff_factor ** attempt
                await asyncio.sleep(delay)

        return self._build_retry_error(
            ERR_UNKNOWN, str(last_error)[:200] if last_error else "Unknown error",
            max_retries,
        )

