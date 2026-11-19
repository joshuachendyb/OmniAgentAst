# -*- coding: utf-8 -*-
# 2026-11-18 商量 - 新增 schedule 工具: 会话内任务/计划清单(一期方案A纯回显零状态), 整体替换+摘要给 LLM
# 2026-11-19 小欧 - notice 通道改造: 清理单从步骤流派生; 成功发 notice(kind=schedule, items)供前端卡片;
#   data 改 rows 二维数组(事项|完成标志)给 LLM; action 删 params.items(obs不用); 失败 hint 按参数说明
# 2026-11-19 小欧 - 规格收紧(描述无歧义): 条数 50→20、content 200→100; 约束前置到 schema/注册描述;
#   items 结构/四态语义/整体替换单一真源描述, 常量与描述同源;
#   数值上限与参数描述文案全迁 tool_constants(SCHEDULE_*)，本文件只 import 不重定义
# 2026-11-19 小欧 - 失败二分: 完全错误(结构不符)→error; 可容忍错(content/条数超标记裁剪、status 非法归 pending)
#   →成功+warning(build_warning), 裁剪后清单照常发 notice 落地
# 2026-11-19 小欧 - 三态均发 notice: done(带 items→事件列表+卡片) / failed(only_event=True→仅事件列表不占位置2);
#   三态均返回 LLM+落库, 仅 SSE 转发出口摘工具行
# 2026-11-19 小欧 - 新增 plan_stage 必填参数(init/update/finish): LLM 主动阶段决策, 与 items 宽松核对,
#   核对反馈进 llm_data(plan_stage_note), update 附持续维护引导; 不硬拒绝;
#   summary 前置"任务计划:初建/更新/结束", notice content 随 summary 同步可见
"""
schedule — 任务/计划清单(方案A: 纯回显, 与 opencode todoWrite 一致)

【铁规1】helper 只返回 raw dict, build_* 与 llm_data 在 main 函数构建。
【铁规2】工具返回原始 data, 不调用 truncate_data_for_frontend。
【铁规3】计时(duration_ms)只在 main 函数。
"""
import time as _time_mod
from typing import Any, Dict, List, Tuple

from app.tools.context import get_current_notice_callback
from app.tools.tool_constants import (
    ERR_SCHEDULE,
    SCHEDULE_INPUT_MAX_CONTENT_CHARS,
    SCHEDULE_INPUT_MAX_ITEMS,
    SCHEDULE_ITEM_KEYS,
    SCHEDULE_ITEMS_PARAM_DESC,
    SCHEDULE_PLAN_STAGE_LABELS,
    SCHEDULE_PLAN_STAGES,
    SCHEDULE_STATUSES,
    SCHEDULE_UPDATE_GUIDANCE,
)
from app.tools.tool_response import build_error, build_success, build_warning

VALID_STATUSES = SCHEDULE_STATUSES  # 四态单一真源在 tool_constants, 校验与 schema enum 同源
VALID_PLAN_STAGES = SCHEDULE_PLAN_STAGES  # plan_stage 三阶段单一真源


def _normalize_items(items: Any) -> Tuple[List[Dict[str, str]], str, List[str]]:
    """校验并归一化清单(错误二分: 结构错拒绝, 可容忍错裁剪/归位+警告) — 商量 2026-11-18
    2026-11-19 小欧 - 分两类: 完全错误(error, 立即拒) / 可容忍错误(warning, 裁剪或归位后继续)。
      返回 (归一化清单, 错误文案, 警告列表); error 非空即拒绝, warning 非空则成功+警告。
    """
    if not isinstance(items, list):
        return [], "items 必须是数组", []

    allowed = SCHEDULE_ITEM_KEYS  # 从 schema properties 派生, 与参数层同源(拒未知字段口径不漂移)
    warnings: List[str] = []

    # 可容忍: 条数超标 → 裁剪取前 N 项
    if len(items) > SCHEDULE_INPUT_MAX_ITEMS:
        warnings.append(f"清单共{len(items)}项, 超过上限{SCHEDULE_INPUT_MAX_ITEMS}, 已裁剪保留前{SCHEDULE_INPUT_MAX_ITEMS}项")
        items = items[:SCHEDULE_INPUT_MAX_ITEMS]

    normalized: List[Dict[str, str]] = []
    for idx, item in enumerate(items, start=1):
        # ---- 完全错误: 结构不符, 立即拒绝 ----
        if not isinstance(item, dict):
            return [], f"第{idx}项必须是对象", []
        extra = set(item) - allowed
        if extra:
            return [], f"第{idx}项含未知字段 {sorted(extra)}, 每项只允许 content/status", []
        if "content" not in item:
            return [], f"第{idx}项缺少 content", []
        content = item["content"]
        if not isinstance(content, str):
            return [], f"第{idx}项 content 必须是字符串", []
        if not content.strip():
            return [], f"第{idx}项 content 不能为空", []
        if "status" not in item:
            return [], f"第{idx}项缺少 status", []
        status = item["status"]
        if not isinstance(status, str):
            return [], f"第{idx}项 status 必须是字符串", []

        # ---- 可容忍: content 超长 → 裁剪, status 非法 → 归 pending, 记警告 ----
        if len(content) > SCHEDULE_INPUT_MAX_CONTENT_CHARS:
            warnings.append(f"第{idx}项 content 超过{SCHEDULE_INPUT_MAX_CONTENT_CHARS}字, 已裁剪")
            content = content[:SCHEDULE_INPUT_MAX_CONTENT_CHARS]
        if status not in VALID_STATUSES:
            warnings.append(f"第{idx}项 status={status!r} 非法, 已按 pending 处理")
            status = "pending"
        normalized.append({"content": content, "status": status})
    return normalized, "", warnings


def _summarize(items: List[Dict[str, str]], plan_stage: str = "") -> str:
    """计划摘要: 阶段 + 共 N 项, 按完成/未完成/取消三类计数 — 商量 2026-11-18
    2026-11-19 小欧 - 改「共N项+完成/未完成/取消三分类」, 一项不重复列; 未完成=进行中+待开始。
    2026-11-19 小欧 - 前置 plan_stage 中文含义(初建/更新/结束), 让 LLM 一眼看到本次阶段决策。
    """
    # 任务计划前缀: 合法取值给中文标签(初建/更新/结束), 非法值原样带入(核对在 _check_plan_stage 反馈), 无则不加
    stage_prefix = ""
    if plan_stage:
        label = SCHEDULE_PLAN_STAGE_LABELS.get(plan_stage, plan_stage)
        stage_prefix = f"任务计划:{label}; "
    if not items:
        return f"{stage_prefix}计划已清空"
    total = len(items)
    counts = {s: 0 for s in VALID_STATUSES}
    for item in items:
        counts[item["status"]] += 1
    unfinished = counts["in_progress"] + counts["pending"]
    return (
        f"{stage_prefix}收到{total}项: 已完成{counts['completed']}项, "
        f"未完成{unfinished}项(进行中{counts['in_progress']}、待开始{counts['pending']}), "
        f"已取消{counts['cancelled']}项。"
    )


def _check_plan_stage(plan_stage: str, items: List[Dict[str, str]]) -> str:
    """plan_stage 与 items 的宽松语义核对 — 小欧 2026-11-19
    plan_stage 必填, 是 LLM 主动决策, 与 items 语义相关非精密绑定: 不一致只反馈不拒绝。
    返回给 LLM 的反馈文案(进 llm_data), update 阶段附持续维护引导。
    """
    has_items = bool(items)
    note = ""
    if plan_stage not in VALID_PLAN_STAGES:
        note = f"plan_stage={plan_stage!r} 非法(init/update/finish 三选一), 已忽略"
    elif plan_stage == "finish" and has_items:
        note = "你标注 finish(结束)但清单非空, 若非有意请确认; finish 通常传[]清空"
    elif plan_stage in ("init", "update") and not has_items:
        note = f"你标注 {plan_stage} 但清单为空, 若非有意请补充 items"
    if plan_stage == "update":
        note = (note + "; " if note else "") + SCHEDULE_UPDATE_GUIDANCE
    return note


def _build_schedule_llm_data(
    exec_code: str,
    duration_ms: int,
    detail: str = "",
    summary: str = "",
    item_count: int = 0,
    plan_stage_note: str = "",
) -> Dict[str, Any]:
    """schedule 的 llm_data 构建(helper 只返 raw dict) — 商量 2026-11-18
    2026-11-19: 删 items 参数与 action.params.items(obs 不用, 前端 hook 已删); 计数改用 item_count。
    2026-11-19 小欧 - plan_stage_note: plan_stage 宽松核对反馈, 有值才进 result(LLM 下一轮可见)。
    """
    if exec_code == "error":
        # message="失败"已表成败(全仓规范); summary 给概括(具体违反项在 detail→"✖错误"行), 两行不重复
        summary = "计划未被接受, 请修正后重新提交完整清单"
        status = {
            "exec_code": "error", "message": "失败", "code": ERR_SCHEDULE,
            "detail": detail, "hint": f"请按 schedule 参数说明重新提交 items: {SCHEDULE_ITEMS_PARAM_DESC}",
        }
    elif exec_code == "warning":
        # 可容忍错已就地处理(裁剪/归位), summary 仍报清单计数; 警告逐条进 detail(→"⚠警告"行)
        status = {
            "exec_code": "warning", "message": "完成但有警告", "code": "",
            "detail": detail, "hint": "计划已按上述处理落地, 如需精确控制请修正后重新提交完整清单",
        }
    else:
        status = {
            "exec_code": "success", "message": "成功", "code": "",
            "detail": "", "hint": "",
        }
    result: Dict[str, Any] = {
        "summary": summary,
        "action": {"tool": "schedule", "tool_zh": "计划"},
        "status": status,
        "duration_ms": duration_ms,
        "metrics": {"item_count": item_count},
    }
    # plan_stage 宽松核对反馈(LLM 下一轮可见); 仅不一致或 update 持续引导时有值, 无反馈则不塞字段
    if plan_stage_note:
        result["plan_stage_note"] = plan_stage_note
    return result


async def schedule(items: List[Dict[str, Any]], plan_stage: str) -> Dict[str, Any]:
    """创建/更新当前会话的任务计划清单(整体替换) — 商量 2026-11-18
    2026-11-19: 三态均发 notice — done(带 items, 事件列表+卡片) / failed(only_event=True, 仅事件列表不占位置2);
       三态均返回 LLM + 落库(observation 步原样), 仅 SSE 转发出口摘除工具行; data 改 rows 二维数组给 LLM。
    """
    # plan_stage 在 _build 阶段宽松核对并反馈, 见下方 stage_note
    t0 = _time_mod.perf_counter()
    _notice_cb = get_current_notice_callback()

    normalized, err, warnings = _normalize_items(items)
    if err:
        # 完全错误(结构不符)→ error: 发 failed notice(only_event=True)→ 前端只进事件列表, 不画卡片不占位置2, 保持上一份
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if _notice_cb:
            await _notice_cb("schedule", "failed", f"计划未更新: {err}", only_event=True)
        return build_error(
            data={"rows": []},
            llm_data=_build_schedule_llm_data("error", duration_ms, detail=err),
        )

    summary = _summarize(normalized, plan_stage)  # 阶段含义前置到 summary
    # plan_stage 宽松核对: LLM 主动决策, 与 items 语义相关非精密绑定; 反馈进 llm_data 供下一轮自省
    stage_note = _check_plan_stage(plan_stage, normalized)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    # 成功/可容忍错发 done notice(带裁剪/归位后的 items)→ 前端事件列表 + 计划卡片显示实际落地结果
    if _notice_cb:
        await _notice_cb("schedule", "done", summary, items=normalized)
    data = {"rows": [[it["content"], it["status"]] for it in normalized]}
    if warnings:
        # 可容忍错(长度超标裁剪/status 非法归位)→ 成功+warning, 清单已就地处理落地
        return build_warning(
            data=data,
            llm_data=_build_schedule_llm_data("warning", duration_ms, summary=summary,
                                              detail="; ".join(warnings), item_count=len(normalized),
                                              plan_stage_note=stage_note),
        )
    return build_success(
        data=data,
        llm_data=_build_schedule_llm_data("success", duration_ms, summary=summary,
                                          item_count=len(normalized), plan_stage_note=stage_note),
    )


__all__ = ["schedule"]
