# -*- coding: utf-8 -*-
# 2026-11-18 商量 - 新增 question 工具: 阻塞式人机问答; 回调经 tools/context ContextVar 注入(零越层);
#   开关/超时继承 HITL; 降级/超时/取消统一以 build_error + hint 收口, 不引入异常控制流
# 2026-11-18 商量 - 三堂会审整改: 双分支镜像 hitl_confirm — HTL关不再立即降级(改由发射器分窗: 短窗要问+到点expired自动过);
#   降级分支仅保留"回调未注入"(直接调工具/无agent); expired hint 去秒数插值(窗口双分支后工具侧不再自知秒数); 清 get_config/HITL_TIMEOUT 死导入
"""
question — 阻塞式人机问答(执行中收集偏好 / 澄清歧义 / 获取实现决策)

【铁规1】helper 只返回 raw dict, build_* 与 llm_data 在 main 函数构建。
【铁规2】工具返回原始 data, 不调用 truncate_data_for_frontend。
【铁规3】计时(duration_ms/wait_ms)只在 main 函数。
"""
import time as _time_mod
from typing import Any, Dict, List, Tuple

from app.tools.context import get_current_question_callback
from app.tools.tool_constants import ERR_QUESTION
from app.tools.tool_response import build_error, build_success

MAX_QUESTIONS = 8
MAX_OPTIONS = 9
MAX_HEADER_CHARS = 30
MAX_QUESTION_CHARS = 1000
MAX_LABEL_CHARS = 200
MAX_DESCRIPTION_CHARS = 500


def _validate_questions(questions: Any) -> Tuple[List[Dict[str, Any]], str]:
    """校验并归一化问题数组 — 商量 2026-11-18; 返回 (归一化数组, 错误文案), 错误文案为空即通过"""
    if not isinstance(questions, list):
        return [], "questions 必须是数组"
    if not questions:
        return [], "至少需要一个问题"
    if len(questions) > MAX_QUESTIONS:
        return [], f"最多{MAX_QUESTIONS}个问题"

    normalized: List[Dict[str, Any]] = []
    for idx, q in enumerate(questions, start=1):
        if not isinstance(q, dict):
            return [], f"第{idx}个问题必须是对象"

        text = q.get("question")
        if not isinstance(text, str) or not text.strip():
            return [], f"第{idx}个问题缺少 question(完整问题)"
        if len(text) > MAX_QUESTION_CHARS:
            return [], f"第{idx}个问题 question 超过{MAX_QUESTION_CHARS}字"

        header = q.get("header")
        if not isinstance(header, str) or not header.strip():
            return [], f"第{idx}个问题缺少 header(极短标签)"
        if len(header) > MAX_HEADER_CHARS:
            return [], f"第{idx}个问题 header 超过{MAX_HEADER_CHARS}字"

        options = q.get("options")
        if not isinstance(options, list) or not options:
            return [], f"第{idx}个问题 options 不能为空"
        if len(options) > MAX_OPTIONS:
            return [], f"第{idx}个问题 options 最多{MAX_OPTIONS}项"

        norm_options: List[Dict[str, str]] = []
        for oi, opt in enumerate(options, start=1):
            if not isinstance(opt, dict):
                return [], f"第{idx}个问题第{oi}个选项必须是对象"
            label = opt.get("label")
            if not isinstance(label, str) or not label.strip():
                return [], f"第{idx}个问题第{oi}个选项缺少 label"
            if len(label) > MAX_LABEL_CHARS:
                return [], f"第{idx}个问题第{oi}个选项 label 过长"
            desc = opt.get("description", "")
            if desc is None:
                desc = ""
            if not isinstance(desc, str):
                return [], f"第{idx}个问题第{oi}个选项 description 必须是字符串"
            if len(desc) > MAX_DESCRIPTION_CHARS:
                return [], f"第{idx}个问题第{oi}个选项 description 过长"
            norm_options.append({"label": label, "description": desc})

        multiple = q.get("multiple", False)
        if not isinstance(multiple, bool):
            return [], f"第{idx}个问题 multiple 必须是布尔值"

        normalized.append({
            "question": text,
            "header": header,
            "options": norm_options,
            "multiple": multiple,
        })
    return normalized, ""


def _normalize_answers(raw: Any, count: int) -> List[List[str]]:
    """回调答案按问题数归一为 [[str,...], ...] — 商量 2026-11-18; 缺失项补空, 单项字符串包成列表"""
    source = raw if isinstance(raw, (list, tuple)) else []
    answers: List[List[str]] = []
    for i in range(count):
        item = source[i] if i < len(source) else []
        if isinstance(item, str):
            answers.append([item])
        elif isinstance(item, (list, tuple)):
            answers.append([str(x) for x in item])
        else:
            answers.append([])
    return answers


def _build_question_llm_data(
    exec_code: str,
    duration_ms: int,
    detail: str = "",
    hint: str = "",
    answers: List[List[str]] = None,
    questions: List[Dict[str, Any]] = None,
    wait_ms: int = 0,
) -> Dict[str, Any]:
    """question 的 llm_data 构建(helper 只返 raw dict) — 商量 2026-11-18"""
    answers = answers or []
    questions = questions or []
    if exec_code == "error":
        summary = f"提问失败: {detail}"
        status = {
            "exec_code": "error", "message": "失败", "code": ERR_QUESTION,
            "detail": detail, "hint": hint,
        }
    else:
        pairs = []
        for q, ans in zip(questions, answers):
            title = q.get("header", "") if isinstance(q, dict) else ""
            value = "、".join(ans)
            pairs.append(f'{title}="{value}"')
        summary = "用户已回答 " + f"{len(answers)} 个问题: " + "; ".join(pairs) if pairs else "用户已回答问题"
        status = {
            "exec_code": "success", "message": "成功", "code": "",
            "detail": "", "hint": "",
        }
    return {
        "summary": summary,
        "action": {"tool": "question", "tool_zh": "提问", "params": {"questions": questions}},
        "status": status,
        "duration_ms": duration_ms,
        "metrics": {"wait_ms": wait_ms},
    }


async def question(questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """阻塞式向用户提问 — 商量 2026-11-18"""
    t0 = _time_mod.perf_counter()

    normalized, err = _validate_questions(questions)
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return build_error(
            data={"answers": [], "questions": []},
            llm_data=_build_question_llm_data(
                "error", duration_ms, detail=err,
                hint="请按字段要求修正 questions 后重试",
            ),
        )

    callback = get_current_question_callback()
    if callback is None:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return build_error(
            data={"answers": [], "questions": normalized},
            llm_data=_build_question_llm_data(
                "error", duration_ms, detail="问询通道未注入",
                hint="无问询通道(直接调工具/无agent场景), 请自行决策并说明假设后继续",
                questions=normalized,
            ),
        )

    try:
        t_wait = _time_mod.perf_counter()
        result = await callback(normalized)
        wait_ms = int((_time_mod.perf_counter() - t_wait) * 1000)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return build_error(
            data={"answers": [], "questions": normalized},
            llm_data=_build_question_llm_data(
                "error", duration_ms, detail=str(e),
                hint="问询通道异常, 请自行决策后继续", questions=normalized,
            ),
        )

    if not isinstance(result, dict):
        result = {}
    cancelled = bool(result.get("cancelled", False))
    expired = bool(result.get("expired", False))
    if cancelled or expired:
        if expired:
            detail = "用户未在规定时间内回答"
            hint = "用户未在规定时间内回答, 请基于最合理假设继续, 不要重新提问"
        else:
            detail = "用户已放弃本次提问"
            hint = "用户已放弃本次提问, 请停止推进并在最终回答中说明已中断"
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return build_error(
            data={"answers": [], "questions": normalized},
            llm_data=_build_question_llm_data(
                "error", duration_ms, detail=detail, hint=hint, questions=normalized,
            ),
        )

    answers = _normalize_answers(result.get("answers"), len(normalized))
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    return build_success(
        data={"answers": answers, "questions": normalized},
        llm_data=_build_question_llm_data(
            "success", duration_ms, answers=answers,
            questions=normalized, wait_ms=wait_ms,
        ),
    )


__all__ = ["question"]
