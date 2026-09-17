# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-04 小健 第3阶段拆分: 从 action_handler 完整复制 _build_call_list + BuildCallListResult
#   [背景] handle_action 内 _build_call_list/build_observation 等4个"名不副实"函数混装, 非action编排本身
#   [改法] 先复制后修改: 本文件保留原名完整复制(逻辑零改动), 仅迁移存放位置; 函数名后续阶段再改名
#   [效果] action_handler 920→~596行纯编排调度层; 本文件为 LLM action 输入解析层, 零 agent 依赖
from dataclasses import dataclass
from typing import Dict, List

from app.logger import logger


@dataclass
class BuildCallListResult:
    """_build_call_list 返回值 — M-03 6元组→dataclass — 小欧 2026-07-10"""
    tool_name: str
    tool_params: Dict
    fc_context: Dict
    pending_calls: List
    all_calls: List[Dict]
    is_parallel: bool


def _build_call_list(parsed: Dict) -> BuildCallListResult:
    """构建工具调用列表 — 小欧 2026-06-18 从handle_action提取
    chendyg 2026-06-26 P1-10/11修复: 防御tool_name为空和pending_calls缺字段"""
    tool_name = parsed.get("tool_name", "")
    tool_params = parsed.get("tool_params") or {}
    fc_context = parsed.get("fc_context") or {}
    pending_calls = parsed.get("_pending_calls", [])

    # 【P1-10修复】tool_name为空时直接FAILED — chendyg 2026-06-26
    # handle_action已兜底空检查(ErrorStep+return), 此处删除重复日志 — 小欧 2026-07-25

    all_calls = [{
        "tool_name": tool_name, "tool_params": tool_params,
        "_tool_call_id": fc_context.get("tool_call_id", "") if fc_context else "",
        "_repair_warning": parsed.get("_repair_warning", ""),
        "params_raw_str": parsed.get("params_raw_str", ""),   # #3 透传 LLM 原始参数串(11.7.9-2③) — 小欧 2026-08-23
    }]
    # 【P1-11修复】pending_calls条目缺tool_name时跳过 — chendyg 2026-06-26
    for pc in pending_calls:
        pc_name = pc.get("tool_name", "")
        if not pc_name:
            logger.warning(f"[_build_call_list] pending_call缺tool_name,跳过: {pc}")
            continue
        all_calls.append({
            "tool_name": pc_name, "tool_params": pc.get("tool_params") or {},
            "_tool_call_id": pc.get("_tool_call_id", ""),
            "_repair_warning": pc.get("_repair_warning", ""),
            "params_raw_str": pc.get("params_raw_str", ""),   # #3 并行调用各自原始串 — 小欧 2026-08-23
        })

    return BuildCallListResult(
        tool_name=tool_name, tool_params=tool_params, fc_context=fc_context,
        pending_calls=pending_calls, all_calls=all_calls,
        is_parallel=len(all_calls) > 1,
    )
