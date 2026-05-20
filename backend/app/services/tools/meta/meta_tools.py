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
from app.services.tools.tool_result_utils import (
    build_next_actions,
    truncate_data_for_frontend,
    make_json_safe,
)
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
            "data": {"similar_names": similar[:10], "total_tools": len(available)},
            "llm_data": {"similar_names": similar[:5], "total_tools": len(available)},
            "message": f"工具 '{tool_name}' 不存在，请检查名称或使用 tool_search 搜索",
            "next_actions": build_next_actions([
                ("tool_search", "按关键词搜索工具", "不确定工具名时"),
            ]),
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

    llm_result = {
        "name": metadata.name,
        "category": metadata.category.value,
        "description": metadata.description[:200],
        "params": {k: {"type": v["type"], "required": v["required"]} for k, v in params_info.items()},
    }

    data = truncate_data_for_frontend(result)

    return {
        "code": "SUCCESS",
        "data": data,
        "llm_data": llm_result,
        "message": f"工具 '{metadata.name}' 用法查询成功（{metadata.category.value}类）",
        "next_actions": build_next_actions([
            ("tool_search", "按关键词搜索其他工具", "需要模糊查找工具时"),
        ]),
    }


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
            "llm_data": None,
            "message": "搜索关键词不能为空，请提供描述性关键词",
            "next_actions": build_next_actions([
                ("tool_help", "查询单个工具用法", "已知工具名时"),
            ]),
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

    data = truncate_data_for_frontend({
        "query": query,
        "matches": top_results,
        "total_matched": len(scored),
        "total_tools": len(all_tools),
    })

    llm_data = {
        "query": query,
        "matches": [{"name": r["name"], "category": r["category"]} for r in top_results[:10]],
        "total_matched": len(scored),
    }

    return {
        "code": "SUCCESS",
        "data": data,
        "llm_data": llm_data,
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
        if isinstance(steps, (list, dict)):
            steps_list = steps
        else:
            steps_list = json.loads(steps)
    except json.JSONDecodeError as e:
        return {
            "code": "ERR_INVALID_JSON",
            "data": None,
            "llm_data": None,
            "message": f"steps参数不是有效的JSON格式: {str(e)}，请检查JSON语法",
            "next_actions": build_next_actions([
                ("tool_help", "查看pipeline用法", "不确定steps格式时", {"tool_name": "pipeline"}),
            ]),
        }
    except TypeError as e:
        return {
            "code": "ERR_INVALID_JSON",
            "data": None,
            "llm_data": None,
            "message": f"steps参数类型错误: {str(e)}，需要JSON字符串或列表",
            "next_actions": build_next_actions([
                ("tool_help", "查看pipeline用法", "不确定steps格式时", {"tool_name": "pipeline"}),
            ]),
        }

    if not isinstance(steps_list, list):
        return {
            "code": "ERR_INVALID_FORMAT",
            "data": None,
            "llm_data": None,
            "message": f"steps必须是JSON数组格式，当前类型: {type(steps_list).__name__}",
            "next_actions": build_next_actions([
                ("tool_help", "查看pipeline用法", "不确定steps格式时", {"tool_name": "pipeline"}),
            ]),
        }

    context: Dict[str, Any] = {}
    results = []

    for i, step in enumerate(steps_list):
        if not isinstance(step, dict):
            return {
                "code": "ERR_INVALID_STEP",
                "data": None,
                "llm_data": {"failed_step": i + 1, "error": f"步骤类型错误: {type(step).__name__}"},
                "message": f"步骤{i+1}格式无效，应为对象，当前类型: {type(step).__name__}",
                "next_actions": build_next_actions([
                    ("tool_help", "查看pipeline用法", "不确定步骤格式时", {"tool_name": "pipeline"}),
                ]),
            }

        tool_name = step.get("tool")
        if not tool_name:
            return {
                "code": "ERR_MISSING_TOOL",
                "data": None,
                "llm_data": {"failed_step": i + 1},
                "message": f"步骤{i+1}缺少tool字段",
                "next_actions": build_next_actions([
                    ("tool_search", "搜索可用工具", "不确定工具名时"),
                ]),
            }

        metadata = tool_registry.get_tool(tool_name)
        if not metadata:
            available = list(tool_registry._tools.keys())
            similar = [n for n in available if tool_name.lower() in n.lower()]
            return {
                "code": "ERR_TOOL_NOT_FOUND",
                "data": {"similar_tools": similar[:5]},
                "llm_data": {"failed_step": i + 1, "tool": tool_name, "similar_tools": similar[:3]},
                "message": f"步骤{i+1}: 工具 '{tool_name}' 不存在，请用 tool_search 查找正确名称",
                "next_actions": build_next_actions([
                    ("tool_search", "搜索可用工具", "查找正确工具名时"),
                ]),
            }

        params = step.get("params", {})
        if not isinstance(params, dict):
            return {
                "code": "ERR_INVALID_PARAMS",
                "data": None,
                "llm_data": {"failed_step": i + 1, "tool": tool_name},
                "message": f"步骤{i+1}({tool_name})的params必须是对象格式",
                "next_actions": build_next_actions([
                    ("tool_help", "查看工具参数", "不确定参数格式时", {"tool_name": tool_name}),
                ]),
            }

        try:
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

            impl = tool_registry.get_implementation(tool_name)
            if not impl:
                return {
                    "code": "ERR_TOOL_IMPL_NOT_FOUND",
                    "data": None,
                    "llm_data": {"failed_step": i + 1, "tool": tool_name},
                    "message": f"步骤{i+1}: 工具 '{tool_name}' 无法获取实现，请检查工具是否正确注册",
                    "next_actions": build_next_actions([
                        ("tool_search", "搜索替代工具", "需要查找功能类似的工具时"),
                    ]),
                }
            
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
            
            step_data = result.get("data")
            step_llm_data = result.get("llm_data")

            results.append({
                "step": i + 1,
                "tool": tool_name,
                "code": result.get("code"),
                "message": result.get("message"),
                "data": truncate_data_for_frontend(step_data) if isinstance(step_data, dict) else step_data,
                "llm_data": make_json_safe(step_llm_data, max_depth=3, max_str_len=300) if step_llm_data else None,
            })

            if result.get("code") != "SUCCESS" and stop_on_error:
                error_data = truncate_data_for_frontend({
                    "step": i + 1,
                    "tool": tool_name,
                    "error_code": result.get("code"),
                    "error_message": result.get("message"),
                    "results": results,
                })
                return {
                    "code": "ERR_PIPELINE_STOPPED",
                    "data": error_data,
                    "llm_data": {
                        "failed_step": i + 1,
                        "tool": tool_name,
                        "error_code": result.get("code"),
                        "error_message": result.get("message"),
                        "completed_steps": len(results),
                    },
                    "message": f"管道已在步骤{i+1}({tool_name})停止: {result.get('message')}，可设置stop_on_error=False继续执行",
                    "next_actions": build_next_actions([
                        ("tool_help", "查看失败工具用法", "需要修复参数时", {"tool_name": tool_name}),
                        ("tool_search", "搜索替代工具", "需要换工具时"),
                    ]),
                }

            if isinstance(step_data, dict):
                for k, v in step_data.items():
                    if k not in context:
                        context[k] = v

        except TypeError as e:
            return {
                "code": "ERR_PARAM_MISMATCH",
                "data": {"step": i+1, "tool": tool_name, "error": str(e)},
                "llm_data": {"failed_step": i + 1, "tool": tool_name, "error": str(e)},
                "message": f"步骤{i+1}({tool_name})参数不匹配: {str(e)}，请用 tool_help 查看正确参数",
                "next_actions": build_next_actions([
                    ("tool_help", "查看工具参数", "不确定参数时", {"tool_name": tool_name}),
                ]),
            }
        except Exception as e:
            return {
                "code": "ERR_PIPELINE_FAILED",
                "data": {"step": i+1, "tool": tool_name, "error": str(e)},
                "llm_data": {"failed_step": i + 1, "tool": tool_name, "error": str(e)},
                "message": f"步骤{i+1}({tool_name})执行异常: {str(e)}",
                "next_actions": build_next_actions([
                    ("tool_help", "查看失败工具用法", "需要排查问题时", {"tool_name": tool_name}),
                ]),
            }

    data = truncate_data_for_frontend({
        "total_steps": len(steps_list),
        "completed_steps": len(results),
        "results": results,
    })

    llm_data = {
        "total_steps": len(steps_list),
        "completed_steps": len(results),
        "results_summary": [
            {"step": r["step"], "tool": r["tool"], "code": r["code"], "message": r.get("message", "")[:100]}
            for r in results
        ],
    }

    return {
        "code": "SUCCESS",
        "data": data,
        "llm_data": llm_data,
        "message": f"管道执行完成: {len(results)}/{len(steps_list)} 个步骤",
        "next_actions": build_next_actions([
            ("tool_search", "查找可用的工具", "需要编排新管道时"),
        ]),
    }


__all__ = ["tool_help", "tool_search", "pipeline"]
