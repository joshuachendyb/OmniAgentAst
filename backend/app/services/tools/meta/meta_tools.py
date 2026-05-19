# -*- coding: utf-8 -*-
"""
Meta 工具实现 - tool_help / tool_search

【2026-05-17 小沈】新建：精简方案13.12节
- tool_help: 查询单个工具的详细用法（name/category/description/params/examples）
- tool_search: 按关键词搜索匹配的工具列表
"""

import json
import inspect
import asyncio
from typing import Dict, Any, List

from app.services.tools.registry import tool_registry
from app.services.tools.tool_result_utils import build_next_actions
from app.utils.logger import logger


def tool_help(tool_name: str) -> Dict[str, Any]:
    """
    查询指定工具的详细用法信息。

    Args:
        tool_name: 工具名称

    Returns:
        包含 name/category/description/params/examples 的字典
    """
    metadata = tool_registry.get_tool(tool_name)
    if not metadata:
        available = list(tool_registry._tools.keys())
        similar = [n for n in available if tool_name.lower() in n.lower()]
        return {
            "code": "ERR_TOOL_NOT_FOUND",
            "data": None,
            "message": f"工具 '{tool_name}' 不存在。",
            "similar_names": similar[:10],
            "total_tools": len(available),
        }

    params_info = {}
    if metadata.input_schema:
        properties = metadata.input_schema.get("properties", {})
        required = metadata.input_schema.get("required", [])
        for prop_name, prop_detail in properties.items():
            params_info[prop_name] = {
                "type": prop_detail.get("type", "unknown"),
                "description": prop_detail.get("description", ""),
                "required": prop_name in required,
            }

    result = {
        "name": metadata.name,
        "category": metadata.category.value,
        "description": metadata.description,
        "params": params_info,
        "examples": metadata.examples,
        "version": metadata.version,
        "author": metadata.author,
    }

    return {"code": "SUCCESS", "data": result, "message": "success", "next_actions": build_next_actions([
        ("tool_search", "按关键词搜索其他工具", "需要模糊查找工具时"),
    ])}


def tool_search(query: str) -> Dict[str, Any]:
    """
    按关键词搜索匹配的工具列表。

    Args:
        query: 自然语言描述需求

    Returns:
        匹配的工具列表
    """
    query_lower = query.lower()
    query_words = query_lower.split()

    if not query.strip():
        return {
            "code": "ERR_EMPTY_QUERY",
            "data": None,
            "message": "搜索关键词不能为空，请提供描述性关键词"
        }

    all_tools = tool_registry._tools
    scored: List[Dict[str, Any]] = []

    for name, metadata in all_tools.items():
        score = 0
        name_lower = name.lower()
        desc_lower = metadata.description.lower()

        for word in query_words:
            if word in name_lower:
                score += 10
            if word in desc_lower:
                score += 5

        if name_lower in query_lower or query_lower in name_lower:
            score += 8

        if score > 0:
            scored.append({
                "name": metadata.name,
                "category": metadata.category.value,
                "description": metadata.description[:200],
                "score": score,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_results = scored[:20]

    return {
        "code": "SUCCESS",
        "data": {
            "query": query,
            "matches": top_results,
            "total_matched": len(scored),
            "total_tools": len(all_tools),
        },
        "message": f"找到 {len(scored)} 个相关工具，返回前 {len(top_results)} 个",
        "next_actions": build_next_actions([
            ("tool_help", "查看匹配工具的详细用法", "需要了解具体工具参数时"),
        ]),
    }


def pipeline(steps: str, stop_on_error: bool = True) -> Dict[str, Any]:
    """
    定义工具执行管道 - 小沈 2026-05-17

    将多个工具按顺序编排执行，前一步的输出自动成为后一步的输入。

    Args:
        steps: JSON格式的工具执行步骤列表。如
            '[{"tool":"read_csv","params":{"file_path":"data.csv"}},{"tool":"analyze_data","params":{}}]'
        stop_on_error: 某步失败时是否停止管道，默认True

    Returns:
        执行结果，包含steps(步骤数)和results(每步结果)
    """
    try:
        steps_list = json.loads(steps)
    except json.JSONDecodeError as e:
        return {
            "code": "ERR_INVALID_JSON",
            "data": None,
            "message": f"steps参数不是有效的JSON格式: {str(e)}"
        }

    if not isinstance(steps_list, list):
        return {
            "code": "ERR_INVALID_FORMAT",
            "data": None,
            "message": f"steps必须是JSON数组格式，当前类型: {type(steps_list).__name__}"
        }

    context: Dict[str, Any] = {}
    results = []

    for i, step in enumerate(steps_list):
        if not isinstance(step, dict):
            return {
                "code": "ERR_INVALID_STEP",
                "data": None,
                "message": f"步骤{i+1}格式无效，应为对象，当前类型: {type(step).__name__}"
            }

        tool_name = step.get("tool")
        if not tool_name:
            return {
                "code": "ERR_MISSING_TOOL",
                "data": None,
                "message": f"步骤{i+1}缺少tool字段"
            }

        metadata = tool_registry.get_tool(tool_name)
        if not metadata:
            available = list(tool_registry._tools.keys())
            similar = [n for n in available if tool_name.lower() in n.lower()]
            return {
                "code": "ERR_TOOL_NOT_FOUND",
                "data": {"similar_tools": similar[:5]},
                "message": f"步骤{i+1}: 工具 '{tool_name}' 不存在，可选: {similar[:5]}"
            }

        params = step.get("params", {})
        if not isinstance(params, dict):
            return {
                "code": "ERR_INVALID_PARAMS",
                "data": None,
                "message": f"步骤{i+1}({tool_name})的params必须是对象格式"
            }

        try:
            # 【修复 2026-05-19 小沈】前一步输出注入后一步params
            if context:
                impl_sig = set()
                try:
                    impl_func = tool_registry.get_implementation(tool_name)
                    if impl_func:
                        impl_sig = set(inspect.signature(impl_func).parameters.keys())
                except Exception:
                    pass
                for k, v in context.items():
                    if k not in params and (not impl_sig or k in impl_sig):
                        params[k] = v

            # 获取工具实现函数
            impl = tool_registry.get_implementation(tool_name)
            if not impl:
                return {
                    "code": "ERR_TOOL_IMPL_NOT_FOUND",
                    "data": None,
                    "message": f"步骤{i+1}: 工具 '{tool_name}' 无法获取实现"
                }
            
            # 【修复 2026-05-19 小沈】import提到module level
            if inspect.iscoroutinefunction(impl):
                try:
                    loop = asyncio.get_running_loop()
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        result = pool.submit(asyncio.run, impl(**params)).result()
                except RuntimeError:
                    result = asyncio.run(impl(**params))
            else:
                result = impl(**params)
            
            results.append({
                "step": i + 1,
                "tool": tool_name,
                "code": result.get("code"),
                "message": result.get("message"),
                "data": result.get("data"),
            })

            if result.get("code") != "SUCCESS" and stop_on_error:
                return {
                    "code": "ERR_PIPELINE_STOPPED",
                    "data": {
                        "step": i + 1,
                        "tool": tool_name,
                        "error_code": result.get("code"),
                        "error_message": result.get("message"),
                        "results": results
                    },
                    "message": f"管道已在步骤{i+1}({tool_name})停止，失败原因: {result.get('message')}"
                }

            # 【修复 2026-05-19 小沈】展平result data到context供后续步骤注入
            step_data = result.get("data")
            if isinstance(step_data, dict):
                for k, v in step_data.items():
                    if k not in context:
                        context[k] = v

        except TypeError as e:
            return {
                "code": "ERR_PARAM_MISMATCH",
                "data": {"step": i+1, "tool": tool_name, "error": str(e)},
                "message": f"步骤{i+1}({tool_name})参数不匹配: {str(e)}"
            }
        except Exception as e:
            return {
                "code": "ERR_PIPELINE_FAILED",
                "data": {"step": i+1, "tool": tool_name, "error": str(e)},
                "message": f"步骤{i+1}({tool_name})执行异常: {str(e)}"
            }

    return {
        "code": "SUCCESS",
        "data": {
            "total_steps": len(steps_list),
            "completed_steps": len(results),
            "results": results,
        },
        "message": f"管道执行完成: {len(results)}/{len(steps_list)} 个步骤",
        "next_actions": build_next_actions([
            ("tool_search", "查找可用的工具", "需要编排新管道时"),
        ]),
    }


__all__ = ["tool_help", "tool_search", "pipeline"]
