
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-05-27 - 小沈 - 创建文件
# 2026-06-08 - 小沈 - P1-7/8/9: 参数非法改报错, 删全局单例改Agent实例变量, 合并tool_executor重复查找
# 2026-06-30 - 小欧 - 明确分层归属(工具的外部重试 → 工具层)，常量全部引自 tool_constants
# 2026-07-15 - 小沈 - 外层超时恒>内层timeout+缓冲, 防状态工具进程孤儿化
# 2026-07-17 - 小沈 - max_retries=0日志显示超时值; [Retry][L2]→[Retry][L3]重命名
# 2026-07-18 - 小欧 - #13 fix: _validate_params增加参数类型校验
# 2026-07-21 - 小欧 - #17 参数验证提示改进
# 2026-07-23 - 小欧 - #8 fix: _validate_params扩展number/object类型+值范围clamp
# 2026-07-23 - 小欧 - #11 fix: 智能类型容错(string参数传dict/list自动修复)
# 2026-07-26 - 小沈 - 欧阳报告: 非必填None值自动丢弃
# 2026-07-26 - 小沈 - Bug #7: None丢弃日志增强
# 2026-07-29 - 小沈 - 超时hint注入: 导入TOOL_TIMEOUT_HINTS,try_once/_execute_with_retry的TIMEOUT路径查表传hint给LLM
# 2026-07-30 - 小沈 - 保险丝常量重构: INSURANCE_CEILING=600(天花板), INSURANCE_BUFFER=30(缓冲), PROGRESSIVE_MAX=CEILING//2(无inner渐进上限); 两路径逻辑统一为: 有inner=max(inner,CEILING)+BUFFER, 无inner=min(base_timeout*(attempt+1),PROGRESSIVE_MAX)
# 2026-07-30 - 小沈 - 备用工具命名统一: design注释+error hint中"搜索"→"搜索备用工具的类型(可选:文档/数据分析/数据库/网络/系统/桌面/时间定时)"; docstring渐进超时标注(无inner路径)并补(有inner路径)保险丝公式
"""
统一工具重试引擎 — 工具的外部重试机制

物理位置: Agent编排层(被 UniversalAgent.run_react_cycle 调用)
 归属分层: 【工具层】— 虽在编排层目录，但本质是工具的外部重试机制，引用工具层常量

【分层规范 - 小健 2026-05-27】
本文件是工具的【外部重试】，使用 tool_result_utils.py 的 create_xxx 函数
禁止使用 _response.py 的 build_xxx 函数(那是工具层内部响应用的)

负责统一处理工具执行的重试逻辑,消除双重实现
Author: 小沈 - 2026-05-27
"""

import asyncio
import inspect
import json as _json
from typing import Any, Callable, Dict, Optional

from app.logger import logger
from app.tools.tool_error_classifier import ToolErrorCategory, ToolErrorClassifier
from app.tools.tool_constants import (
    TOOL_TIMEOUTS, TOOL_RETRY_BACKOFF, TOOL_RETRY_CONFIG,
    TOOL_TIMEOUT_HINTS,
    ERR_MISSING_PARAM, ERR_INVALID_PARAMS, ERR_TOOL_NOT_FOUND, ERR_UNKNOWN,
)
from app.tools.tool_response import build_error
from app.tools.param_alias_mapper import normalize_params
from app.tools.registry import tool_registry

# ============================================================
# 保险丝超时策略 — 设计逻辑（北京老陈 2026-07-30）
#
# 所有工具分两类，两类不同策略：
#
# 【有 inner timeout 参数的工具】（compress/shell/download 等）
#   保险丝 = max(inner, INSURANCE_CEILING) + INSURANCE_BUFFER
#   原因：工具有自己的内部超时 deadline，保险丝必须恒大于内部超时，
#         否则保险丝抢先截杀，工具内部的 timed_out hint 来不及返回。
#   CEILING=600：有inner的工具系统至少等10分钟，inner 超 600 则随它去。
#   BUFFER=30：保险丝比内部超时多30秒，给内部 handler 退出窗口。
#
# 【无 inner timeout 参数的工具】（listdir/delete/find 等）
#   保险丝 = min(base_timeout * (attempt+1), PROGRESSIVE_MAX)
#   原因：工具没有内部超时概念，采用渐进递增，首次短快失败立即报错，
#         后续逐步放宽，上限 PROGRESSIVE_MAX。
#   PROGRESSIVE_MAX = CEILING // 2 = 300：无inner工具最长等5分钟。
# ============================================================
INSURANCE_CEILING = 600
INSURANCE_BUFFER = 30
PROGRESSIVE_MAX = INSURANCE_CEILING // 2


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
        action_name: str = "", action_params: Optional[dict] = None,
        hint: str = "",  # task007-欧阳: 可选hint参数,默认空 — 小欧 2026-07-23
    ) -> Dict[str, Any]:
        """统一构建重试相关错误响应 — 小欧 2026-06-21 适配新3字段result
        小欧 2026-07-05: 新增 action_name/action_params 参数，LLM 能看到哪个工具/参数失败
        小欧 2026-07-23: 新增 hint 参数"""
        return build_error(
            data={},
            llm_data={
                "summary": message[:200],
                "action": {"tool": action_name, "tool_zh": "", "target": "", "params": action_params or {}},
                "status": {"exec_code": "error", "message": message[:200], "code": code, "detail": message, "hint": hint or ""},
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
    
    def _prepare_execution(self, action: str, action_input: Dict[str, Any]):
        """查找工具+参数规范化+参数验证 — 统一入口，try_once与execute_tool_with_retry共享
         
        遵守DRY原则：两个执行方法共用此函数，消除查找/规范化/验证的代码重复。
        遵守SRP原则：只负责「准备工作」，不涉执行/重试。
         
        Args:
            action: 工具名
            action_input: 原始参数字典
         
        Returns:
            (tool, validated_params) — 验证通过
            (None, error_dict) — 工具不存在或参数验证失败，error_dict包含给LLM的错误描述
         
        设计决策:
        - 工具不存在时返回含hint的error_dict，提示LLM使用searchtool搜索备用工具的类型(如'网络 搜索')，系统会自动注入整个工具分类
        - 参数验证失败时返回含具体缺失/非法字段的错误，让LLM修正后重试
         
        小欧 2026-07-09
        """
        tool = self._tools.get(action)
        if tool is None:
            return None, build_error(
                data={},
                llm_data={
                    "summary": f"工具 '{action}' 未找到",
                    "action": {"tool": action, "tool_zh": "", "target": "", "params": {"action": action}},
                    "status": {"exec_code": "error", "message": f"工具 '{action}' 未找到", "code": ERR_TOOL_NOT_FOUND, "detail": f"可用工具: {list(self._tools.keys())}", "hint": "该工具未注入。请先调用 searchtool 搜索备用工具的类型(可选:文档/数据分析/数据库/网络/系统/桌面/时间定时)，如'网络 搜索'，系统会自动注入整个工具分类。"},
                    "duration_ms": 0,
                    "metrics": {},
                },
                other_data={"retry_count": 0},
                error_type="tool_not_found",
            )
        # 参数别名映射：解决LLM返回参数名与schema不匹配的问题（如"path"→"file_path"）
        normalized_input, _ = normalize_params(action, action_input)
        params = self._validate_params(action, normalized_input, tool)
        # 验证失败（非法参数/缺失必需参数）→ 返回error_dict，不继续执行
        _ec = params.get("llm_data", {}).get("status", {}).get("exec_code", "") if isinstance(params, dict) else ""
        if _ec == "error":
            return None, params
        return tool, params

    async def try_once(self, action: str, action_input: Dict[str, Any]) -> Dict[str, Any]:
        """单次执行，不重试 — 专供action_handler并行分支使用
         
        与execute_tool_with_retry的区别：
        - 无重试循环：只调一次_execute_tool_once，失败直接返回错误
        - 无等待退避：不调用asyncio.sleep
        - 无on_retry_started回调：一次执行不需要通知
         
        设计理由（action_handler并行分支场景）：
        并行工具失败的瞬态概率低，让LLM从observation看到失败后可自行决定是否重试，
        不需要引擎层自动重试。这避免了asyncio.gather内部的重试复杂性。
         
        小欧 2026-07-09
        """
        tool, params_or_error = self._prepare_execution(action, action_input)
        if tool is None:
            return params_or_error
        # 复用_get_retry_config的超时查询，消除与_execute_with_retry的DRY违规 — 小欧 2026-07-09
        _, _, _, base_timeout = self._get_retry_config(action)
        inner = params_or_error.get("timeout")
        if isinstance(inner, int) and inner > 0:
            # 有inner: 保险丝 = max(inner, CEILING) + BUFFER, 恒 > 内部超时 — 北京老陈 2026-07-30
            timeout = max(inner, INSURANCE_CEILING) + INSURANCE_BUFFER
        else:
            # 无inner: 渐进 cap PROGRESSIVE_MAX — 北京老陈 2026-07-30
            timeout = min(base_timeout, PROGRESSIVE_MAX)
        try:
            result = await self._execute_tool_once(tool, params_or_error, timeout)
            if isinstance(result, dict):
                result.setdefault("other_data", {})["retry_count"] = 0
            return result
        except Exception as e:
            error_category = ToolErrorClassifier.classify_tool_error(e)
            _hint = TOOL_TIMEOUT_HINTS.get(action, "") if error_category == ToolErrorCategory.TIMEOUT else ""
            return self._build_retry_error(
                f"ERR_{error_category.name}", f"{error_category.description}: {str(e)[:200]}",
                0, error_type=error_category.name.lower(),
                action_name=action, action_params=params_or_error,
                hint=_hint,
            )

    async def execute_tool_with_retry(
        self,
        action: str,
        action_input: Dict[str, Any],
        on_retry_started: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """统一工具执行方法（带重试）— action_handler单工具/顺序分支使用
         
        与try_once的区别：
        - 有重试循环：按TOOL_RETRY_CONFIG配置的重试次数自动重试
        - 有指数退避：重试间隔backoff_factor^attempt
        - 有on_retry_started回调：每次重试前通知调用方（→前端显示重试状态）
        - 有渐进超时(无inner路径): 每次重试的超时递增base_timeout*(attempt+1), 上限 PROGRESSIVE_MAX=300
- 有inner超时参数工具: 保险丝 = max(inner, CEILING) + BUFFER, 恒大于内部超时
         
        Args:
            action: 工具名
            action_input: 原始参数字典
            on_retry_started: 可选回调，重试触发前调用。
               签名: (tool_name, attempt_1indexed, max_retries, error_msg)
               attempt从1开始（第1次重试=1）。同步调用，不阻塞重试流程。
         
        小欧 2026-06-27: 增加参数名别名映射，解决LLM返回参数名不匹配问题
        小欧 2026-07-09: 新增on_retry_started回调参数
        """
        tool, params_or_error = self._prepare_execution(action, action_input)
        if tool is None:
            return params_or_error
        return await self._execute_with_retry(action, params_or_error, tool, on_retry_started=on_retry_started)
    
    def _validate_params(self, action: str, action_input: Dict[str, Any], tool: Callable):
        """验证参数（非法参数+必需参数）— P1-05修复: 返回错误字典而非None
        小健 2026-06-18 合并_are_params_valid和_check_missing_params为一次查询"""
        params = action_input.copy()
        
        try:
            metadata = tool_registry.get_tool(action)
            if metadata and metadata.input_schema:
                input_schema = metadata.input_schema
                valid_params = set(input_schema.get("properties", {}).keys())
                invalid_keys = [k for k in params if k not in valid_params]
                if invalid_keys:
                    _props_desc = ", ".join(
                        f"{k}: {v.get('type', '?')}" for k, v in input_schema.get("properties", {}).items()
                    )
                    logger.warning(f"[参数验证] action={action} 含非法字段: {invalid_keys}")
                    return self._build_retry_error(
                        ERR_INVALID_PARAMS,
                        f"参数验证失败: {action} 含非法参数, keys={list(params.keys())}；合法参数: {_props_desc}",
                        0, error_type="invalid_params",
                        action_name=action, action_params=params,
                    )
                
                required = input_schema.get("required", [])
                missing = [p for p in required if p not in params]
                if missing:
                    props = input_schema.get("properties", {})
                    _types = "; ".join(f"{p}(期望类型={props.get(p, {}).get('type', '?')})" for p in missing)
                    return self._build_retry_error(
                        ERR_MISSING_PARAM,
                        f"缺少必需参数: {action}, 缺失: {missing}",
                        0, error_type="missing_param",
                        action_name=action, action_params=params,
                        hint=f"缺少参数 {missing}：{_types}。工具必需参数不可缺，请提供完整的参数后再试",  # task007-欧阳: 提示缺失参数的类型 — 小欧 2026-07-23
                    )
                # 非必填参数的None值自动丢弃(欧阳报告), 类型校验前做 — 小沈 2026-07-26
                _none_discarded = []
                for k in list(params.keys()):
                    if k not in required and params[k] is None:
                        _none_discarded.append(k)
                        del params[k]
                # #13 fix: 参数类型校验 — 小欧 2026-07-18
                # #8 fix: +number/object类型 + 值范围clamp — 三堂会审 小欧 2026-07-23
                props = input_schema.get("properties", {})
                # #11 fix: 智能类型容错(LLM常为string参数传dict/list,自动json.dumps/str修复减少重试) — 小欧 2026-07-23
                for k, v in params.items():
                    spec = props.get(k)
                    if not spec:
                        continue
                    _t = spec.get("type")
                    if _t == "string" and not isinstance(v, str):
                        try:
                            params[k] = _json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
                        except Exception:
                            pass
                type_errors = []
                for k, v in params.items():
                    spec = props.get(k)
                    if not spec:
                        continue
                    _t = spec.get("type")
                    if _t == "string" and not isinstance(v, str):
                        type_errors.append(f"{k}期望类型为{_t},实际类型为{type(v).__name__}")
                    elif _t == "array" and not isinstance(v, list):
                        type_errors.append(f"{k}期望类型为{_t},实际类型为{type(v).__name__}")
                    elif _t == "integer" and not isinstance(v, int):
                        type_errors.append(f"{k}期望类型为{_t},实际类型为{type(v).__name__}")
                    elif _t == "boolean" and not isinstance(v, bool):
                        type_errors.append(f"{k}期望类型为{_t},实际类型为{type(v).__name__}")
                    elif _t == "number" and not isinstance(v, (int, float)):
                        type_errors.append(f"{k}期望类型为{_t},实际类型为{type(v).__name__}")
                    elif _t == "object" and not isinstance(v, dict):
                        type_errors.append(f"{k}期望类型为{_t},实际类型为{type(v).__name__}")
                if type_errors:
                    _extra = f", 已丢弃的None参数={_none_discarded}" if _none_discarded else ""
                    logger.warning(f"[参数验证] action={action} 类型错误: {type_errors}{_extra}")
                    return self._build_retry_error(
                        ERR_INVALID_PARAMS,
                        f"参数验证失败: {action} 参数类型错误: {'; '.join(type_errors)}",
                        0, error_type="invalid_params",
                        action_name=action, action_params=params,
                    )
                # #8 fix: 值范围clamp(integer/number参数的minimum/maximum),防Pydantic ValidationError — 小欧 2026-07-23
                for k, v in params.items():
                    spec = props.get(k)
                    if not spec:
                        continue
                    _t = spec.get("type")
                    if _t == "integer":
                        minimum = spec.get("minimum")
                        maximum = spec.get("maximum")
                        if minimum is not None and v < minimum:
                            params[k] = minimum
                        elif maximum is not None and v > maximum:
                            params[k] = maximum
        except (ImportError, AttributeError) as e:
            logger.warning(f"[参数验证] action={action}, 获取schema失败: {e}", exc_info=True)

        return params
    
    def _should_retry(self, e: Exception, retryable_errors: list, attempt: int, max_retries: int,
                       error_category: Optional[ToolErrorCategory] = None) -> bool:
        """判断是否应该重试 — 只查 per-tool 配置，不查 is_retryable — 小欧 2026-06-29"""
        if error_category is None:
            error_category = ToolErrorClassifier.classify_tool_error(e)
        # 使用 error_category.value 进行匹配，因为 TOOL_RETRY_CONFIG 中的字符串是 ToolErrorCategory.value
        is_retryable = error_category.value in retryable_errors
        return is_retryable and attempt < max_retries

    async def _execute_with_retry(self, action: str, params: Dict[str, Any], tool: Callable,
                                   on_retry_started: Optional[Callable] = None) -> Dict[str, Any]:
        """带重试执行工具 — 核心循环：渐进超时+重试前回调通知
         
        重试策略（遵守KISS-DIRECT原则，简单直线）：
        1. 超时策略分两路:
           - 有inner参数工具: 保险丝 = max(inner, CEILING) + BUFFER, 恒大于内部超时让工具先处理
           - 无inner参数工具: 渐进超时 base_timeout * (attempt + 1), 上限 PROGRESSIVE_MAX
           → 有inner: compress(600)=630, compress(1800)=1830; 无inner: listdir=60/120/180 cap 300
        2. 指数退避等待: 重试间隔 = backoff_factor^attempt（1s, 2s, 4s...）
           → 给小故障足够恢复时间，同时避免立即重试又失败
        3. 分类重试: 只有TOOL_RETRY_CONFIG中retryable列表里的错误类别才会重试
           → 永久性错误（如参数无效）不重试，直接返回错误让LLM修正
        4. 回调通知: 每次重试前调on_retry_started回调
           → action_handler可消费回调→yield ChunkStep→前端显示重试进度
         
        日志约定（[Retry][Lx]层级）：
        - [Retry][L1]: LLM流式调用重试（base_service.py）
        - [Retry][L2]: LLM响应错误重试（llm_stream.py）
        - [Retry][L3]: 工具执行重试（本方法）
         
         小沈 2026-07-17
        """
        max_retries, backoff_factor, retryable_errors, base_timeout = self._get_retry_config(action)

        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            inner = params.get("timeout")
            if isinstance(inner, int) and inner > 0:
                # 有inner: 保险丝 = max(inner, CEILING) + BUFFER, 恒 > 内部超时 — 北京老陈 2026-07-30
                timeout = max(inner, INSURANCE_CEILING) + INSURANCE_BUFFER
            else:
                # 无inner: 渐进递增, cap PROGRESSIVE_MAX — 北京老陈 2026-07-30
                timeout = min(base_timeout * (attempt + 1), PROGRESSIVE_MAX)
            if attempt > 0 and on_retry_started:
                try:
                    on_retry_started(action, attempt, max_retries, str(last_error)[:100])
                except Exception as cb_err:
                    logger.warning(f"[Retry][L3] on_retry_started回调异常: {cb_err}")
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
                if max_retries == 0:
                    logger.warning(
                        f"[Retry][L3] action={action} {error_category.description}:{timeout}秒(无重试) - {str(e)[:100]}",
                        exc_info=should_print_traceback
                    )
                else:
                    logger.warning(
                        f"[Retry][L3] action={action} 尝试{attempt + 1}/{max_retries + 1} "
                        f"失败：{error_category.description} - {str(e)[:100]}",
                        exc_info=should_print_traceback
                    )

                if not self._should_retry(e, retryable_errors, attempt, max_retries, error_category):
                    _hint = TOOL_TIMEOUT_HINTS.get(action, "") if error_category == ToolErrorCategory.TIMEOUT else ""
                    return self._build_retry_error(
                        f"ERR_{error_category.name}",
                        f"{error_category.description}: {str(e)[:200]}",
                        attempt, error_type=error_category.name.lower(),
                        action_name=action, action_params=params,
                        hint=_hint,
                    )

                delay = backoff_factor ** attempt
                await asyncio.sleep(delay)

        return self._build_retry_error(
            ERR_UNKNOWN, str(last_error)[:200] if last_error else "Unknown error",
            max_retries,
            action_name=action, action_params=params,
        )


