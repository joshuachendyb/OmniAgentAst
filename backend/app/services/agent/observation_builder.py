# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-04 小健 第3阶段拆分: 从 action_handler 完整复制 build_observation + ObservationContext + _add_denial_feedback
#   [背景] build_observation 职责远超"构建观察", 实为观察反馈构建层(写LLM历史+record_operation+编排决策收集)
#   [改法] 先复制后修改: 本文件保留原名完整复制(逻辑零改动), 仅迁移存放位置; 函数名后续阶段再改名
#   [效果] action_handler 920→~596行纯编排调度层; 本文件与 observation_formatter 同层(LLM交互反馈层)
#   [YAGNI] _add_denial_feedback(19行)与 build_observation 同层配套, 并入本文件(不单拆 feedback_writer.py)
from itertools import zip_longest
from dataclasses import dataclass
from typing import Dict, List, Any

from app.logger import logger
from app.utils.display_utils import format_llm_data_text
from app.logger.prompt_logger import get_prompt_logger
from app.services.agent.steps import ObservationStep
from app.services.agent.observation_formatter import build_observation_text
from app.db.models.operation_models import OperationStatus


@dataclass
class ObservationContext:
    """构建observation所需的上下文 — 遵守ISP原则"""
    agent: Any
    all_calls: List[Dict]
    results: List[Any]
    step: int
    tool_name: str
    tool_params: Dict
    is_parallel: bool
    pending_calls: List
    fc_context: Dict = None


def _add_denial_feedback(agent, denied_items, fc_context=None):
    """HITL拒绝/拦截→把反馈写入LLM历史, 让LLM换方案(符合人类认知: 拒绝≠失败) — 小欧 2026-07-13

    2026-08-11 小欧 fix D2: 精确到call对象, 只对被拒call写observation:
      原实现遍历all_calls按tool_name匹配→同批同名工具(实际会执行)被误标"被拦截",
      且自行add_assistant_tool_call→与build_observation的assistant双重写, LLM历史矛盾;
      现assistant统一由build_observation写(L649), 本函数在execute_tools后只补被拒call的tool result。
    """
    for _cn, _reason, _call in (denied_items or []):
        _tid = _call.get("_tool_call_id", "")
        _obs = f"[Observation] 工具 {_cn} {_reason}. 请改用其他工具或方式完成用户任务。"
        try:
            agent.message_builder.add_tool_result(_tid, _obs)
        except Exception as e:
            logger.debug(f"add_tool_result(_tid={_tid})失败, 尝试空ID: {e}")
            try:
                agent.message_builder.add_tool_result("", _obs)
            except Exception as e2:
                logger.debug(f"add_tool_result(空ID)也失败: {e2}")


async def build_observation(ctx: ObservationContext) -> "tuple[List, Dict]":
    """构建 observation - tool_result 数组方案（§10.3.3(3)）— 2026-08-18 小欧

    职责不变: 1条assistant(tool_calls)+逐工具add_tool_result喂LLM; record_operation双表同号
    变更: 删 ActionStep 发射/删 _merge_other_data/删顶层 llm_data/tool_result/other_data/parallel_results
          ObservationStep 仅 tool_result 数组; 编排层从各 tool_result[i].other_data 收集(return_direct/attachment/warning)
    返回: (events, orchestration)  orchestration={"return_direct","attachments","warning","return_direct_message"}
    """
    events: List = []
    tool_result: List[Dict[str, Any]] = []
    orchestration = {"return_direct": False, "attachments": [], "warning": "", "return_direct_message": ""}

    # assistant+tool 配对 — 建1条assistant带所有tool_calls
    _fc = ctx.fc_context or {}
    _shared_tc = _fc.get("tool_calls", [])
    if _shared_tc:
        ctx.agent.message_builder.add_assistant_tool_call(
            _shared_tc, content=_fc.get("llm_content", "") or None,
            reasoning=_fc.get("llm_reasoning", "") or None,
        )

    for call, result in zip_longest(ctx.all_calls, ctx.results):
        if call is None:
            continue
        # 2026-09-03 小欧 Bug-1: 全工具被安全拦截时 results 可能缺失该 call 的结果(zip_longest 补 None),
        #   用合成"无结果"占位, 使 ObservationStep 必然发出、前端 results 保长度, 齿轮/动画不再永驻
        # 2026-09-03 小欧 D2-01: synthetic补summary使折叠区可见“已安全拦截：tool”
        if result is None:
            _syn_tool = call.get("tool_name", "?") if isinstance(call, dict) else "?"
            result = {"llm_data": {"status": {"exec_code": "error"}, "summary": f"已安全拦截：{_syn_tool}"}, "other_data": {"synthetic": True}}
        if isinstance(result, Exception):
            obs_text = f"Observation: 工具{call.get('tool_name', '?')}执行异常: {result}"
            _is_failed = True
        else:
            obs_text = build_observation_text(result, call.get("tool_name", ""), call.get("tool_params", {}))
            _llm_data = result.get("llm_data") if isinstance(result.get("llm_data"), dict) else {}
            # 2026-08-18 小健 三堂会审 Bug#7: status 可能为 str(工具实现不规范), 防御防 AttributeError
            _status = _llm_data.get("status") if isinstance(_llm_data.get("status"), dict) else {}
            _ec = _status.get("exec_code", "")
            _is_failed = _ec == "error"

        get_prompt_logger().log_observation(
            step_name=f"步骤{ctx.step}: 工具执行结果",
            observation_content=obs_text, tool_name=call.get("tool_name", ""),
            tool_params=call.get("tool_params", {}), round_number=ctx.step, raw_data=result,
        )
        _tool = call.get("tool_name", "?")
        ctx.agent.record_operation(
            _tool,
            status=OperationStatus.FAILED.value if _is_failed else OperationStatus.SUCCESS.value,
            error=str(result) if _is_failed else None,
        )
        repair_warning = call.get("_repair_warning", "")
        if repair_warning:
            obs_text = f"Observation: {repair_warning}\n{obs_text}"
            logger.warning(f"[action_handler] step={ctx.step}, {_tool} 参数截断修复: {repair_warning}")
        try:
            tc_id = call.get("_tool_call_id", "")
            ctx.agent.message_builder.add_tool_result(tc_id, obs_text)
        except Exception as e:
            logger.warning(f"[action_handler] add_tool_result异常: {type(e).__name__}: {e!r}")
            try:
                ctx.agent.message_builder.add_tool_result("", obs_text)
            except Exception as e2:
                logger.warning(f"[action_handler] add_tool_result最终异常: {type(e2).__name__}: {e2!r}")

        # ── 构建 tool_result[i]（每元素自包含, other_data 1:1 不合并）── 2026-08-18 小欧
        # 2026-08-18 小健 三堂会审 Bug#4: 删除死变量 _data(只赋值未使用, 原始 data 已由 data_text/dl 承载)
        if isinstance(result, dict):
            _llm = result.get("llm_data") if isinstance(result.get("llm_data"), dict) else {}
            _other = result.get("other_data") if isinstance(result.get("other_data"), dict) else {}
        else:
            _llm, _other = {}, {}
        tool_result.append({
            "tool_name": _tool,
            "llm_data": _llm,
            "llm_data_text": format_llm_data_text(_llm),
            "data_text": obs_text,
            "other_data": _other,
        })
        # ── 编排层收集（取代旧 _merge_other_data 盲目合并）── 2026-08-18 小欧
        if _other.get("return_direct"):
            orchestration["return_direct"] = True
            # 2026-08-18 小健 Bug#7: status 可能非 dict, .get 前防御 (line 732 同各 status 取值点)
            _rd_status = _llm.get("status") if isinstance(_llm.get("status"), dict) else {}
            orchestration["return_direct_message"] = _rd_status.get("message", "") or obs_text
        if _other.get("attachment") is not None:
            orchestration["attachments"].append(_other["attachment"])
        if _other.get("warning"):
            _w = str(_other["warning"])
            orchestration["warning"] = (orchestration["warning"] + "\n\n" + _w).strip() if orchestration["warning"] else _w

    # 2026-09-03 小欧 Bug-1: 无条件发 ObservationStep(即使 tool_result 为空/全拦截),
    #   前端 results 到达即卸载等待动画, 杜绝齿轮/动画永驻(改前空 tool_result 直接 return 不发事件)
    # 2026-09-03 小欧 D2-01补：all_calls空时不发空观察（无工具调用无需观察）
    if ctx.all_calls:
        events.append(ctx.agent._step_emitter.emit(ObservationStep(step=ctx.step, tool_result=tool_result)))
    return events, orchestration
