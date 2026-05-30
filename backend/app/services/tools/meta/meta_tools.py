# -*- coding: utf-8 -*-
"""
Meta 工具实现 - tool_help / tool_search

【2026-05-17 小沈】新建：精简方案13.12节
- tool_help: 查询单个工具的详细用法（name/category/description/params/examples）
- tool_search: 按关键词搜索匹配的工具列表
"""

import concurrent.futures
import json
import inspect
import asyncio
import os
import shutil
from typing import Dict, Any, List, Optional, Callable
import glob as glob_module

from app.services.tools.registry import tool_registry
from app.utils.tool_result_formatter import (
    build_next_actions,
    truncate_data_for_frontend,
    make_json_safe,
)
from app.utils.logger import logger
from app.services.tools._response import build_success, build_error





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
        return build_error(
            ERR_TOOL_NOT_FOUND,
            f"工具 '{tool_name}' 不存在，请检查名称或使用 tool_search 搜索",
            data={"similar_names": similar[:10], "total_tools": len(available)},
            llm_data={"similar_names": similar[:5], "total_tools": len(available)},
            next_actions=build_next_actions([
                ("tool_search", "按关键词搜索工具", "不确定工具名时"),
            ]),
        )

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

    return build_success(
        data,
        f"工具 '{metadata.name}' 用法查询成功（{metadata.category.value}类）",
        llm_data=llm_result,
        next_actions=build_next_actions([
            ("tool_search", "按关键词搜索其他工具", "需要模糊查找工具时"),
        ]),
    )


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
        return build_error(
            ERR_DOC_QUERY_EMPTY,
            "搜索关键词不能为空，请提供描述性关键词",
            next_actions=build_next_actions([
                ("tool_help", "查询单个工具用法", "已知工具名时"),
            ]),
        )

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
    top_results = scored[:10]

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

    return build_success(
        data,
        f"找到 {len(scored)} 个相关工具，返回前 {len(top_results)} 个",
        llm_data=llm_data,
        next_actions=build_next_actions([
            ("tool_help", "查看匹配工具的详细用法", "需要了解具体工具参数时"),
        ]),
    )


def _pipeline_error(code: str, msg: str, step: Optional[int] = None,
                    tool: Optional[str] = None, data: Optional[Dict] = None,
                    llm_data: Optional[Dict] = None) -> Dict[str, Any]:
    """统一pipeline错误响应，附加next_actions — 小健 2026-05-25"""
    actions = []
    if tool:
        actions.append(("tool_help", "查看工具参数", "不确定参数时", {"tool_name": tool}))
    else:
        actions.append(("tool_help", "查看pipeline用法", "不确定steps格式时", {"tool_name": "pipeline"}))
    if code in (ERR_TOOL_NOT_FOUND, ERR_PIPELINE_STOPPED):
        actions.append(("tool_search", "搜索替代工具", "需要查找其他工具时"))
    return build_error(code, msg, data=data, llm_data=llm_data, next_actions=build_next_actions(actions))


def _timeout_error(step_idx: int, tool_name: str, timeout_val: int,
                   done_results: list, orig_steps: str, orig_stop: bool) -> Dict[str, Any]:
    """pipeline步骤超时错误 — 小健 2026-05-25"""
    error_data = truncate_data_for_frontend({
        "step": step_idx + 1,
        "tool": tool_name,
        "timeout": timeout_val,
        "results": done_results,
    })
    return build_error(
        ERR_PIPELINE_TIMEOUT,
        f"步骤{step_idx + 1}({tool_name})执行超时（{timeout_val}秒），请增大timeout_per_step或简化操作",
        data=error_data,
        llm_data={"failed_step": step_idx + 1, "tool": tool_name, "timeout": timeout_val,
                   "completed_steps": len(done_results)},
        next_actions=build_next_actions([
            ("pipeline", "增大超时重试", "需要更长时间执行时",
             {"steps": orig_steps, "stop_on_error": orig_stop,
              "timeout_per_step": timeout_val * 2}),
        ]),
    )


def _run_tool_with_timeout(impl: Callable, params: Dict, timeout: int) -> Any:
    """统一工具执行分发：async/sync + timeout — 小健 2026-05-25

    使用场景:
    - pipeline中执行每步工具，支持async和sync工具
    - 超时抛出TimeoutError

    使用示例:
        result = _run_tool_with_timeout(impl, params, 60)

    返回数据说明:
    - 正常返回工具执行结果Dict
    - 超时抛出concurrent.futures.TimeoutError
    """
    if inspect.iscoroutinefunction(impl):
        try:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, impl(**params))
                return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise
        except RuntimeError:
            return asyncio.run(impl(**params))
    else:
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(impl, **params)
            return future.result(timeout=timeout)


def _process_step_result(result: Dict, i: int, tool_name: str,
                         results: List, context: Dict, stop_on_error: bool) -> Optional[Dict]:
    """处理单步结果，返回None继续或error dict停止 — 小健 2026-05-25

    使用场景:
    - pipeline中处理每步工具的执行结果

    使用示例:
        err = _process_step_result(result, i, tool_name, results, context, stop_on_error)
        if err: return err

    返回数据说明:
    - None: 继续
    - Dict: 错误响应，应立即返回
    """
    step_data = result.get("data")
    step_llm = result.get("llm_data")
    results.append({
        "step": i + 1, "tool": tool_name, "code": result.get("code"),
        "message": result.get("message"),
        "data": truncate_data_for_frontend(step_data) if isinstance(step_data, dict) else step_data,
        "llm_data": make_json_safe(step_llm, max_depth=3, max_str_len=300) if step_llm else None,
    })
    if result.get("code") != "SUCCESS" and stop_on_error:
        error_data = truncate_data_for_frontend({
            "step": i + 1, "tool": tool_name,
            "error_code": result.get("code"),
            "error_message": result.get("message"),
            "results": results,
        })
        return _pipeline_error(ERR_PIPELINE_STOPPED,
            f"管道已在步骤{i+1}({tool_name})停止: {result.get('message')}，可设置stop_on_error=False继续执行",
            step=i+1, tool=tool_name, data=error_data,
            llm_data={"failed_step": i+1, "tool": tool_name, "error_code": result.get("code"),
                       "error_message": result.get("message"), "completed_steps": len(results)})
    if isinstance(step_data, dict):
        for k, v in step_data.items():
            if k not in context:
                context[k] = v
    return None


def _inject_context(params: Dict, context: Dict, tool_name: str) -> Dict:
    """将context中未在params指定的键注入到params — 小沈 2026-05-25

    使用场景:
    - pipeline中上下文注入逻辑
    - 需要将前一步输出注入到后一步参数的场景

    使用示例:
        params = _inject_context(step.get("params", {}), context, tool_name)

    返回数据说明:
    - 返回Dict，注入后的参数字典
    """
    if not context:
        return params
    result = dict(params)
    impl = tool_registry.get_implementation(tool_name)
    if impl:
        try:
            impl_sig = set(inspect.signature(impl).parameters.keys())
            for k, v in context.items():
                if k not in result and k in impl_sig:
                    result[k] = v
        except Exception:
            pass
    return result


def _validate_step(step: Any, i: int, steps_list: List) -> Optional[Dict]:
    """校验单步格式，返回错误dict或None — 小沈 2026-05-25

    使用场景:
    - pipeline中步骤校验
    - 需要验证步骤格式、工具存在性、参数格式的场景

    使用示例:
        err = _validate_step(step, i, steps_list)
        if err: return err

    返回数据说明:
    - None: 校验通过
    - Dict: 错误响应，应立即返回
    """
    if not isinstance(step, dict):
        return _pipeline_error(ERR_INVALID_STEP,
            f"步骤{i+1}格式无效，应为对象，当前类型: {type(step).__name__}",
            llm_data={"failed_step": i + 1, "error": f"步骤类型错误: {type(step).__name__}"})
    tool_name = step.get("tool")
    if not tool_name:
        return _pipeline_error(ERR_MISSING_TOOL,
            f"步骤{i+1}缺少tool字段",
            llm_data={"failed_step": i + 1})
    if not tool_registry.get_tool(tool_name):
        available = list(tool_registry._tools.keys())
        similar = [n for n in available if tool_name.lower() in n.lower()]
        return _pipeline_error(ERR_TOOL_NOT_FOUND,
            f"步骤{i+1}: 工具 '{tool_name}' 不存在，请用 tool_search 查找正确名称",
            tool=tool_name,
            data={"similar_tools": similar[:5]},
            llm_data={"failed_step": i + 1, "tool": tool_name, "similar_tools": similar[:3]})
    params = step.get("params", {})
    if not isinstance(params, dict):
        return _pipeline_error(ERR_INVALID_PARAMS,
            f"步骤{i+1}({tool_name})的params必须是对象格式",
            tool=tool_name,
            llm_data={"failed_step": i + 1, "tool": tool_name})
    return None


def pipeline(steps: str, stop_on_error: bool = True, timeout_per_step: int = 60) -> Dict[str, Any]:
    """
    定义工具执行管道 — 小沈 2026-05-17, 2026-05-22 新增timeout_per_step, 2026-05-25 小健重构拆分

    将多个工具按顺序编排执行，前一步的输出自动成为后一步的输入。

    Args:
        steps: JSON格式的工具执行步骤列表
        stop_on_error: 某步失败时是否停止管道，默认True
        timeout_per_step: 每步执行超时时间（秒），默认60秒

    Returns:
        执行结果，包含steps(步骤数)和results(每步结果)
    """
    try:
        if isinstance(steps, (list, dict)):
            steps_list = steps
        else:
            steps_list = json.loads(steps)
    except json.JSONDecodeError as e:
        return _pipeline_error(ERR_INVALID_JSON,
            f"steps参数不是有效的JSON格式: {str(e)}，请检查JSON语法")
    except TypeError as e:
        return _pipeline_error(ERR_INVALID_JSON,
            f"steps参数类型错误: {str(e)}，需要JSON字符串或列表")

    if not isinstance(steps_list, list):
        return _pipeline_error(ERR_META_INVALID_FORMAT,
            f"steps必须是JSON数组格式，当前类型: {type(steps_list).__name__}")

    context: Dict[str, Any] = {}
    results: List[Dict] = []


    for i, step in enumerate(steps_list):
        err = _validate_step(step, i, steps_list)
        if err:
            return err
        tool_name = step["tool"]
        impl = tool_registry.get_implementation(tool_name)
        if not impl:
            return _pipeline_error(ERR_META_TOOL_IMPL_NOT_FOUND,
                f"步骤{i+1}: 工具 '{tool_name}' 无法获取实现，请检查工具是否正确注册",
                tool=tool_name,
                llm_data={"failed_step": i + 1, "tool": tool_name})
        params = _inject_context(step.get("params", {}), context, tool_name)
        try:
            result = _run_tool_with_timeout(impl, params, timeout_per_step)
        except concurrent.futures.TimeoutError:
            return _timeout_error(i, tool_name, timeout_per_step, results, steps, stop_on_error)
        except TypeError as e:
            return _pipeline_error(ERR_PARAM_MISMATCH,
                f"步骤{i+1}({tool_name})参数不匹配: {str(e)}，请用 tool_help 查看正确参数",
                tool=tool_name,
                data={"step": i+1, "tool": tool_name, "error": str(e)},
                llm_data={"failed_step": i + 1, "tool": tool_name, "error": str(e)})
        except Exception as e:
            if isinstance(e, concurrent.futures.TimeoutError):
                return _timeout_error(i, tool_name, timeout_per_step, results, steps, stop_on_error)
            return _pipeline_error(ERR_PIPELINE_FAILED,
                f"步骤{i+1}({tool_name})执行异常: {str(e)}",
                tool=tool_name,
                data={"step": i+1, "tool": tool_name, "error": str(e)},
                llm_data={"failed_step": i + 1, "tool": tool_name, "error": str(e)})
        err = _process_step_result(result, i, tool_name, results, context, stop_on_error)
        if err:
            return err

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
    return build_success(
        data,
        f"管道执行完成: {len(results)}/{len(steps_list)} 个步骤",
        llm_data=llm_data,
        next_actions=build_next_actions([
            ("tool_search", "查找可用的工具", "需要编排新管道时"),
        ]),
    )


async def batch_process(
    source_pattern: str,
    action: str,
    target_pattern: Optional[str] = None,
    target_dir: Optional[str] = None,
    dry_run: bool = True,
    max_files: int = 500,
    exist_ok: bool = True,
) -> Dict[str, Any]:
    """批量处理文件 — 小沈 2026-05-22 （从file移入meta）
    对匹配glob模式的所有文件执行同一操作（rename/delete/copy）。
    """
    if max_files < 1 or max_files > 10000:
        return build_error(ERR_PARAM_INVALID, f"max_files必须在1-10000之间，当前值：{max_files}")

    files = glob_module.glob(source_pattern, recursive=True)
    files = [f for f in files if os.path.isfile(f)][:max_files]

    if not files:
        return build_error(ERR_NO_MATCH, f"没有匹配到文件: {source_pattern}")

    plan = {
        "action": action,
        "file_count": len(files),
        "files": files[:20],
        "total_files": len(files),
    }

    if dry_run:
        return build_success(
            truncate_data_for_frontend(plan),
            f"【预览模式】将 {action} {len(files)} 个文件，使用实际执行确认",
            llm_data={"action": action, "file_count": len(files), "files": files[:5]},
            next_actions=build_next_actions([
                ("batch_process", "确认执行以上操作", "预览结果符合预期时",
                 {"source_pattern": source_pattern, "action": action,
                  "target_pattern": target_pattern, "target_dir": target_dir,
                  "dry_run": False, "max_files": max_files, "exist_ok": exist_ok}),
            ]),
        )

    results = {"success": 0, "failed": 0, "errors": []}
    for f in files:
        try:
            if action == "rename":
                ext = os.path.splitext(f)[1]
                if target_pattern:
                    new_ext = os.path.splitext(target_pattern)[1]
                    new_name = os.path.splitext(f)[0] + new_ext
                else:
                    new_name = f
                os.rename(f, new_name)
            elif action == "delete":
                os.remove(f)
            elif action == "copy":
                if not target_dir:
                    return build_error(ERR_PARAM_MISSING, "copy操作需要指定target_dir")
                os.makedirs(target_dir, exist_ok=exist_ok)
                dest = os.path.join(target_dir, os.path.basename(f))
                shutil.copy2(f, dest)
            else:
                return build_error(ERR_PARAM_INVALID, f"不支持的action: {action}，可选: rename/delete/copy")
            results["success"] += 1
        except Exception as e:
            results["failed"] += 1
            results["errors"].append({"file": f, "error": str(e)})

    return build_success(
        truncate_data_for_frontend(results),
        f"批量{action}完成: {results['success']}成功, {results['failed']}失败",
        llm_data={"action": action, "success": results["success"], "failed": results["failed"]},
        next_actions=build_next_actions([
            ("list_directory", "查看处理结果", "需要确认文件变更时"),
            ("archive_tool", "打包剩余文件", "需要对剩余文件打包时"),
        ]),
    )


__all__ = ["tool_help", "tool_search", "pipeline", "batch_process"]
from app.constants import (
    ERR_DOC_QUERY_EMPTY,
    ERR_INVALID_JSON,
    ERR_INVALID_PARAMS,
    ERR_INVALID_STEP,
    ERR_META_INVALID_FORMAT,
    ERR_META_TOOL_IMPL_NOT_FOUND,
    ERR_MISSING_TOOL,
    ERR_NO_MATCH,
    ERR_PARAM_INVALID,
    ERR_PARAM_MISMATCH,
    ERR_PARAM_MISSING,
    ERR_PIPELINE_FAILED,
    ERR_PIPELINE_STOPPED,
    ERR_PIPELINE_TIMEOUT,
    ERR_TOOL_NOT_FOUND,
)
