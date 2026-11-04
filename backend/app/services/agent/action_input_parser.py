# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-04 小健 第3阶段拆分: 从 action_handler 完整复制 _build_call_list + BuildCallListResult; [背景] handle_action 内 _build_call_list/build_observation 等4个"名不副实"函数混装, 非action编排本身; [改法] 先复制后修改: 本文件保留原名完整复制(逻辑零改动), 仅迁移存放位置; [效果] action_handler 920→~596行纯编排调度层, 本文件为 LLM action 输入解析层, 零 agent 依赖
# 2026-10-17 小欧 - 认领(未注册识别)上移解析层: 新增 _claim(resolve_registered_tool 逐call标记 _normal_name/_registered); _build_call_list 末尾逐 call 认领; 下游不再复判未注册(批二 safety_gate 删该段)。
# 2026-10-18 - 小欧 - 归一化前置(L2 唯一职责): _claim 在工具名归一后, 用 normalize_params 把参数名归一为 schema 规范名并原地写回;
#   下游安全层/执行层统一拿规范 tool+params, 安全层不再重复 normalize_params。未注册工具(_meta is None)不归一, 保持原样交上游拒绝。
# 2026-10-18 - 小欧 - 补【路径名契约】注释: 安全模块只识别 path/dest 两个路径名, 要求 schema 路径参数名只能是 path/dest, 其余历史名仅作别名归一到二者。
from dataclasses import dataclass
from typing import Dict, List

from app.logger import logger
from app.tools.registry import resolve_registered_tool  # 2026-10-17 小欧 - 认领(未注册识别)上移解析层
from app.tools.tools_alias_mapper import normalize_params  # 2026-10-18 小欧 - 参数名归一前置


@dataclass
class BuildCallListResult:
    """_build_call_list 返回值 — 6元组→dataclass — 小欧 2026-07-10"""
    tool_name: str
    tool_params: Dict
    fc_context: Dict
    pending_calls: List
    all_calls: List[Dict]
    is_parallel: bool


def _claim(call: Dict) -> Dict:
    """[1] 认领: 归一化工具名 + 查注册表标记未注册 — 小欧 2026-10-17

    未注册判定上移解析层(认领=解析职责), 下游 safety_gate 不再复判, 复判点归零。
    _normal_name 供下游按归一名取路径参数; _registered=False 即未注册(handle_action 直接拒绝)。
    下游: [2] 处理范围门 → [3] 合法性初查 → [4] 危险+权限总闸 → [5] 确认 → [6] 沙箱执行。
    """
    _normal, _meta = resolve_registered_tool(call.get("tool_name", ""))
    call["_normal_name"] = _normal
    call["_registered"] = _meta is not None
    # 2026-10-18 小欧 - 参数名归一前置: 原地写回, 保住 tool_params 引用(BIR 与 all_calls[0] 同对象)
    # 【路径名契约 ★】本系统的路径安全模块只识别两个路径参数名: path 与 dest。
    #   因此约定: 各工具 schema 的路径参数名只能是 path 或 dest(download/screen_capture 用 dest);
    #   历史名(source_path/destination_path/file_path/directory/file_name/output_path/search_dir/
    #   src/dst/to/target/output 等)一律只作 LLM 别名, 由本步 normalize_params 归一到 path/dest。
    #   schema 若新增第三种路径名 = 破坏契约(安全层会静默漏检), 守护见 test_p1_layer_ownership.py
    #   ::test_single_line_tool_path_keys_converge_to_path_or_dest。
    if _meta is not None:
        _params = call.get("tool_params")
        if isinstance(_params, dict):
            _normalized, _ = normalize_params(_normal, _params)
            if _normalized is not _params:
                _params.clear()
                _params.update(_normalized)
    return call


def _build_call_list(parsed: Dict) -> BuildCallListResult:
    """构建工具调用列表 — 小欧 2026-06-18 从handle_action提取
    chendyg 2026-06-26 修复: 防御tool_name为空和pending_calls缺字段"""
    tool_name = parsed.get("tool_name", "")
    tool_params = parsed.get("tool_params") or {}
    fc_context = parsed.get("fc_context") or {}
    pending_calls = parsed.get("_pending_calls", [])

    # 【修复】tool_name为空时直接FAILED — chendyg 2026-06-26
    # handle_action已兜底空检查(ErrorStep+return), 此处删除重复日志 — 小欧 2026-07-25

    all_calls = [{
        "tool_name": tool_name, "tool_params": tool_params,
        "_tool_call_id": fc_context.get("tool_call_id", "") if fc_context else "",
        "_repair_warning": parsed.get("_repair_warning", ""),
        "params_raw_str": parsed.get("params_raw_str", ""),   # 透传 LLM 原始参数串 — 小欧 2026-08-23
    }]
    # 【修复】pending_calls条目缺tool_name时跳过 — chendyg 2026-06-26
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

    # 2026-10-17 小欧 - 逐 call 认领(未注册识别唯一真源, 主 call 与 pending 一并)
    all_calls = [_claim(c) for c in all_calls]

    return BuildCallListResult(
        tool_name=tool_name, tool_params=tool_params, fc_context=fc_context,
        pending_calls=pending_calls, all_calls=all_calls,
        is_parallel=len(all_calls) > 1,
    )
