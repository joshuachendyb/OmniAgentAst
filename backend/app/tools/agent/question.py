# -*- coding: utf-8 -*-
# 2026-11-18 商量 - 新增 question 工具: 阻塞式人机问答; 回调经 tools/context ContextVar 注入(零越层);
#   开关/超时继承 HITL; 降级/超时/取消统一以 build_error + hint 收口, 不引入异常控制流
# 2026-11-18 商量 - 三堂会审整改: 双分支镜像 hitl_confirm — HTL关不再立即降级(改由发射器分窗: 短窗要问+到点expired自动过);
#   降级分支仅保留"回调未注入"(直接调工具/无agent); expired hint 去秒数插值(窗口双分支后工具侧不再自知秒数); 清 get_config/HITL_TIMEOUT 死导入
# 2026-11-18 商量 - 到点未答兜底作答优化: expired 由"空答案+报错"改"成功收口+真实答案" — HTL关→各题首选项(最合理默认),
#   HTL开→专家指令回填答案槽(按最合理逻辑处理); summary 带 auto_note 说明自动作答; cancelled 维持报错收口
# 2026-11-18 商量 - 兜底作答补收口指令(AUTO_FALLBACK_DIRECTIVE): 原摘要只给结果不给指令, 模型把"系统自动代答/自动决策"
#   讲给用户听并重新征求确认(实证两轮); 现与结果同行下发"视为用户选择, 不要再重复询问" — 商量-2026-11-18
# 2026-11-18 商量 - cancelled 分支补传 wait_ms: 原漏传走默认 0, 用户实际等了多久被记成 0ms(遥测失真) — 商量-2026-11-18
# 2026-11-18 商量 - 三堂会审复核: 兜底文案判据改读回调下发的 auto_confirm(窗口模式单一判定在发射器, 工具层不判安全策略);
#   异常/取消分支补 wait_ms; 摘要未作答项标「（未作答）」— 商量-2026-11-18
# 2026-11-19 小欧 - 约束常量迁入 tool_constants 单一真源(同 schedule 模式), 校验统一引用;
#   补同题选项 label 重复校验(前端按 label 判选中, 重复会同选致答案无法区分) — 小欧-2026-11-19
# 2026-11-19 小欧 - 字段顺序统一 header→question→options; header 可选(缺失/null→空串), question/options 必填 — 小欧-2026-11-19
# 2026-11-19 小欧 - llm_data.summary 标题回退: header 缺省时用 question, 防出现 ="" 空标题(conv/落库同源) — 小欧-2026-11-19
# 2026-11-19 小欧 - multiple→single 语义反转: single 默认true=单选; 校验/归一化同步 — 小欧-2026-11-19
# 2026-11-19 小欧 - 一致性整改: header strip(空白归空)/未知字段拒(白名单从schema派生, 同schedule) — 小欧-2026-11-19
# 2026-11-19 小欧 - 函数改名 _validate_questions→_normalize_params: 实为校验+补默认值+理顺结构的参数归一化 — 小欧-2026-11-19
# 2026-11-19 小欧 - 正常回答分支两档: 全答success/部分答warning; 全未答不可达(canSubmit 保证≥1题有答案); summary 报"回答 M/N 个" — 小欧-2026-11-19
# 2026-11-19 小欧 - warning 补 hint UNANSWERED_HINT: 三思三省做最佳决策继续, 仅关键信息无法推断才停下请补充 — 小欧-2026-11-19
# 2026-11-19 小欧 - 超限容错: 字数/条数超限改截断(schedule 模式)转 warning; 截断说明进 detail+hint 两处, 与未答叠加 — 小欧-2026-11-19
# 2026-11-19 小欧 - warning 文案统一: 兜底 summary 与 success 同款格式; message 按实际未答/截断组合精确措辞 — 小欧-2026-11-19
"""
question — 阻塞式人机问答(执行中收集偏好 / 澄清歧义 / 获取实现决策)

【返回状态设计决策 — 小欧 2026-11-19】
  成功(success): 全题作答 且 无参数截断。
  警告(warning): 部分题未答(三思三省做最佳决策继续) 或 参数超限截断(按截断后内容继续) 或 两者叠加;
    有截断则必不 success, detail 放截断说明+未答数, hint 放截断提示+未答决策指引(两处都说明)。
  失败(error): 用户取消(停下推进) / 参数结构错(非数组/缺字段/未知字段/类型错/label重复, 拒绝) /
    问询通道未注入 / 回调异常(后两者让 LLM 自行决策继续)。
  全题未答不单独设档: 前端 canSubmit 保证至少一题有答案, 正常链路不可达。
  到点兜底(expired): 系统生成答案让任务继续, 无截断=success, 有截断=warning。

【铁规1】helper 只返回 raw dict, build_* 与 llm_data 在 main 函数构建。
【铁规2】工具返回原始 data, 不调用 truncate_data_for_frontend。
【铁规3】计时(duration_ms/wait_ms)只在 main 函数。
"""
import time as _time_mod
from typing import Any, Dict, List, Tuple

from app.tools.context import get_current_question_callback
from app.tools.tool_constants import (
    ERR_QUESTION,
    QUESTION_INPUT_MAX_DESCRIPTION_CHARS,
    QUESTION_INPUT_MAX_LABEL_CHARS,
    QUESTION_INPUT_MAX_OPTIONS,
    QUESTION_INPUT_MAX_QUESTION_CHARS,
    QUESTION_INPUT_MAX_QUESTIONS,
    QUESTION_INPUT_MAX_TITLE_CHARS,
    QUESTION_ITEM_SCHEMA_KEYS,
    QUESTION_ITEMS_PARAM_DESC,
    QUESTION_OPTION_SCHEMA_KEYS,
)
from app.tools.tool_response import build_error, build_success, build_warning

# HTL开(真人工)到点未答的兜底作答文案 — 商量 2026-11-18
EXPERT_FALLBACK_ANSWER = "你是资深专家, 以专家的高水准和全局视野, 按最合理的逻辑进行处理"
# 到点未答兜底后给模型的收口指令 — 商量 2026-11-18
#   兜底答案已生效, 问题也已关闭; 缺此指令时模型会把"系统自动代答/自动决策"复述给用户并重新征求确认,
#   等于用一句内部机制说明换掉了用户本该看到的推进结果。
AUTO_FALLBACK_DIRECTIVE = "该答案即视为用户的选择, 不要再向用户重复询问同一问题, 直接按此结果继续"
# 未答问题的统一 hint(warning 用) — 小欧 2026-11-19
#   核心: 让 LLM 三思三省做最佳决策继续(不停下); 仅当关键信息确实无法推断时才停下说明并请用户补充。
UNANSWERED_HINT = (
    "未作答的问题请三思三省: 结合任务目标、已回答内容与专家判断, 做出最合理的选择后继续推进, "
    "不要再向用户重复询问同一问题, 也不要停下等待; "
    "仅当该问题的关键信息确实无法从任务上下文推断时, 才在最终回答中说明卡点并请用户补充。"
)


def _normalize_params(questions: Any) -> Tuple[List[Dict[str, Any]], str, List[str]]:
    """归一化 question 工具参数(校验+补默认值+理顺结构+超限截断) — 商量 2026-11-18
    返回 (归一化数组, 硬错误文案, 截断警告列表); 硬错误非空即拒绝, 截断警告降级 warning 继续 — 小欧 2026-11-19
    """
    if not isinstance(questions, list):
        return [], "questions 必须是数组", []
    if not questions:
        return [], "至少需要一个问题", []

    warnings: List[str] = []
    # 问题数超限: 截断保留前 N 项 + 记警告(不拒绝)
    if len(questions) > QUESTION_INPUT_MAX_QUESTIONS:
        warnings.append(f"问题数组共{len(questions)}项, 超过上限{QUESTION_INPUT_MAX_QUESTIONS}, 已保留前{QUESTION_INPUT_MAX_QUESTIONS}项")
        questions = questions[:QUESTION_INPUT_MAX_QUESTIONS]

    normalized: List[Dict[str, Any]] = []
    for idx, q in enumerate(questions, start=1):
        if not isinstance(q, dict):
            return [], f"第{idx}个问题必须是对象", warnings
        extra = set(q.keys()) - QUESTION_ITEM_SCHEMA_KEYS
        if extra:
            return [], f"第{idx}个问题含未知字段 {sorted(extra)}, 每项只允许 header/question/options/single", warnings

        # 问题标题(header)可选: 缺失/null/纯空白 归一为空串(前端不渲染小标签), 传了则须是字符串且不超长 — 小欧-2026-11-19
        header = q.get("header", "")
        if header is None:
            header = ""
        if not isinstance(header, str):
            return [], f"第{idx}个问题 header 必须是字符串", warnings
        header = header.strip()
        if len(header) > QUESTION_INPUT_MAX_TITLE_CHARS:
            warnings.append(f"第{idx}个问题 header 超过{QUESTION_INPUT_MAX_TITLE_CHARS}字, 已截断")
            header = header[:QUESTION_INPUT_MAX_TITLE_CHARS]

        text = q.get("question")
        if not isinstance(text, str) or not text.strip():
            return [], f"第{idx}个问题缺少 question(完整问题)", warnings
        if len(text) > QUESTION_INPUT_MAX_QUESTION_CHARS:
            warnings.append(f"第{idx}个问题 question 超过{QUESTION_INPUT_MAX_QUESTION_CHARS}字, 已截断")
            text = text[:QUESTION_INPUT_MAX_QUESTION_CHARS]

        options = q.get("options")
        if not isinstance(options, list) or not options:
            return [], f"第{idx}个问题 options 不能为空", warnings
        if len(options) > QUESTION_INPUT_MAX_OPTIONS:
            warnings.append(f"第{idx}个问题 options 共{len(options)}项, 超过上限{QUESTION_INPUT_MAX_OPTIONS}, 已保留前{QUESTION_INPUT_MAX_OPTIONS}项")
            options = options[:QUESTION_INPUT_MAX_OPTIONS]

        norm_options: List[Dict[str, str]] = []
        seen_labels = set()
        for oi, opt in enumerate(options, start=1):
            if not isinstance(opt, dict):
                return [], f"第{idx}个问题第{oi}个选项必须是对象", warnings
            extra = set(opt.keys()) - QUESTION_OPTION_SCHEMA_KEYS
            if extra:
                return [], f"第{idx}个问题第{oi}个选项含未知字段 {sorted(extra)}, 每项只允许 label/description", warnings
            label = opt.get("label")
            if not isinstance(label, str) or not label.strip():
                return [], f"第{idx}个问题第{oi}个选项缺少 label", warnings
            if len(label) > QUESTION_INPUT_MAX_LABEL_CHARS:
                warnings.append(f"第{idx}个问题第{oi}个选项 label 超过{QUESTION_INPUT_MAX_LABEL_CHARS}字, 已截断")
                label = label[:QUESTION_INPUT_MAX_LABEL_CHARS]
            # 前端按 label 判选中/作答案值, 重复 label 会同选且无法区分 — 小欧-2026-11-19
            label_key = label.strip()
            if label_key in seen_labels:
                return [], f"第{idx}个问题选项 label 重复: {label!r}", warnings
            seen_labels.add(label_key)
            desc = opt.get("description", "")
            if desc is None:
                desc = ""
            if not isinstance(desc, str):
                return [], f"第{idx}个问题第{oi}个选项 description 必须是字符串", warnings
            if len(desc) > QUESTION_INPUT_MAX_DESCRIPTION_CHARS:
                warnings.append(f"第{idx}个问题第{oi}个选项 description 超过{QUESTION_INPUT_MAX_DESCRIPTION_CHARS}字, 已截断")
                desc = desc[:QUESTION_INPUT_MAX_DESCRIPTION_CHARS]
            norm_options.append({"label": label, "description": desc})

        single = q.get("single", True)
        if not isinstance(single, bool):
            return [], f"第{idx}个问题 single 必须是布尔值", warnings

        normalized.append({
            "header": header,
            "question": text,
            "options": norm_options,
            "single": single,
        })
    return normalized, "", warnings


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


def _auto_fallback(
    normalized: List[Dict[str, Any]], auto_confirm: bool
) -> Tuple[List[List[str]], str]:
    """到点未答的兜底作答(双分支) — 商量 2026-11-18
    auto_confirm=True(人工干预关=bypass 短窗)→各题首选项作答(最合理默认);
    auto_confirm=False(真人工)→专家指令作答(按最合理逻辑处理)。
    auto_confirm 由回调下发(窗口模式唯一判定在发射器), 工具层不自行推导配置。返回 (answers, 说明文案)。
    """
    if auto_confirm:
        return (
            [[q["options"][0]["label"]] for q in normalized],
            "问询到点未答, 已按首选项自动作答",
        )
    return (
        [[EXPERT_FALLBACK_ANSWER] for _ in normalized],
        "问询到点未答, 已按专家模式自动决策",
    )


def _build_question_llm_data(
    exec_code: str,
    duration_ms: int,
    detail: str = "",
    hint: str = "",
    answers: List[List[str]] = None,
    questions: List[Dict[str, Any]] = None,
    wait_ms: int = 0,
    auto_note: str = "",
    answered: int = None,
    warnings: List[str] = None,
) -> Dict[str, Any]:
    """question 的 llm_data 构建(helper 只返 raw dict) — 商量 2026-11-18; auto_note 非空=到点自动兜底作答
    answered=实际作答题数; warnings=参数截断警告; 截断说明进 detail(警告行)+hint(建议行)两处 — 小欧-2026-11-19
    """
    answers = answers or []
    questions = questions or []
    warnings = warnings or []
    total = len(questions)
    # 截断说明(两处复用): detail 放警告行, hint 放建议行 — 小欧 2026-11-19
    trunc_detail = "参数超限已截断: " + "; ".join(warnings) if warnings else ""
    trunc_hint = "提交的参数已按上限截断处理(见警告), 请基于截断后的内容继续; " if warnings else ""
    if exec_code == "error":
        summary = f"提问失败: {detail}"
        status = {
            "exec_code": "error", "message": "失败", "code": ERR_QUESTION,
            "detail": detail, "hint": hint,
        }
    elif exec_code == "warning":
        pairs = []
        for q, ans in zip(questions, answers):
            title = q.get("header", "") if isinstance(q, dict) else ""
            if not title:
                title = q.get("question", "") if isinstance(q, dict) else ""
            value = "、".join(ans) or "（未作答）"
            pairs.append(f'{title}="{value}"')
        if auto_note:
            # 兜底+截断: summary 与 success 同款格式(避免同语义两种措辞) — 小欧-2026-11-19
            summary = f"{auto_note}: {len(answers)} 个问题: " + "; ".join(pairs)
            summary = f"{summary}。{AUTO_FALLBACK_DIRECTIVE}"
        else:
            summary = f"用户回答 {answered}/{total} 个问题: " + "; ".join(pairs)
        # detail 叠加: 截断说明 + 未答数; hint 叠加: 截断提示 + 未答决策指引 — 小欧-2026-11-19
        detail_parts = ([trunc_detail] if trunc_detail else [])
        if answered < total:
            detail_parts.append(f"{total - answered} 个问题未作答")
        hint_parts = ([trunc_hint] if trunc_hint else [])
        if answered < total:
            hint_parts.append(UNANSWERED_HINT)
        # message 按实际情况精确措辞(避免全答时仍说"有未答") — 小欧-2026-11-19
        _has_unanswered = answered < total
        if warnings and _has_unanswered:
            _msg = "完成但有未答和截断"
        elif warnings:
            _msg = "完成但有截断"
        else:
            _msg = "完成但有未答"
        status = {
            "exec_code": "warning", "message": _msg, "code": "",
            "detail": "; ".join(detail_parts), "hint": "".join(hint_parts),
        }
    else:
        pairs = []
        for q, ans in zip(questions, answers):
            title = q.get("header", "") if isinstance(q, dict) else ""
            # 标题可选: 缺省时回退完整问题, 否则 summary 出现 ="" 的空标题, 模型无法分辨是哪题的答案 — 小欧-2026-11-19
            if not title:
                title = q.get("question", "") if isinstance(q, dict) else ""
            # 未作答项显式标注: 空串会被模型读成"用户选择了空", 与"没答"是两件事 — 商量-2026-11-18
            value = "、".join(ans) or "（未作答）"
            pairs.append(f'{title}="{value}"')
        if pairs:
            prefix = f"{auto_note}: " if auto_note else "用户已回答 "
            summary = prefix + f"{len(answers)} 个问题: " + "; ".join(pairs)
        else:
            summary = auto_note or "用户已回答问题"
        if auto_note:
            # 兜底作答与收口指令同一行下发: 只给答案不给指令, 模型会当成"还没问过"再问一遍
            summary = f"{summary}。{AUTO_FALLBACK_DIRECTIVE}"
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

    normalized, err, warnings = _normalize_params(questions)
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return build_error(
            data={"answers": [], "questions": []},
            llm_data=_build_question_llm_data(
                "error", duration_ms, detail=err,
                hint=f"请按 question 参数说明重新提交 questions: {QUESTION_ITEMS_PARAM_DESC}",
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

    t_wait = _time_mod.perf_counter()
    try:
        result = await callback(normalized)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return build_error(
            data={"answers": [], "questions": normalized},
            llm_data=_build_question_llm_data(
                "error", duration_ms, detail=str(e),
                hint="问询通道异常, 请自行决策后继续", questions=normalized,
                wait_ms=int((_time_mod.perf_counter() - t_wait) * 1000),
            ),
        )
    wait_ms = int((_time_mod.perf_counter() - t_wait) * 1000)

    if not isinstance(result, dict):
        result = {}
    cancelled = bool(result.get("cancelled", False))
    expired = bool(result.get("expired", False))
    if cancelled or expired:
        if cancelled:
            detail = "用户已放弃本次提问"
            hint = "用户已放弃本次提问, 请停止推进并在最终回答中说明已中断"
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            return build_error(
                data={"answers": [], "questions": normalized},
                llm_data=_build_question_llm_data(
                    "error", duration_ms, detail=detail, hint=hint,
                    questions=normalized, wait_ms=wait_ms,
                ),
            )
        # 2026-11-18 商量 - 到点未答兜底作答(成功收口, 不再空答案报错):
        #   auto_confirm(bypass短窗)→各题首选项; 真人工→专家指令回填答案槽;
        #   auto_confirm 由回调下发(发射器按 security.hitl.enabled 唯一判定窗口模式) — 商量-2026-11-18
        auto_confirm = bool(result.get("auto_confirm", False))
        fallback, note = _auto_fallback(normalized, auto_confirm)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        # 有截断则兜底降级 warning(截断不 success) — 小欧 2026-11-19
        fallback_code = "warning" if warnings else "success"
        llm_data = _build_question_llm_data(
            fallback_code, duration_ms, answers=fallback,
            questions=normalized, wait_ms=wait_ms, auto_note=note,
            answered=len(fallback), warnings=warnings,
        )
        data = {"answers": fallback, "questions": normalized, "auto": True}
        if fallback_code == "warning":
            return build_warning(data=data, llm_data=llm_data)
        return build_success(data=data, llm_data=llm_data)

    answers = _normalize_answers(result.get("answers"), len(normalized))
    answered = sum(1 for a in answers if a)  # 空答案组=未作答
    total = len(normalized)
    # 状态叠加: 有截断→必warning(无success); 无截断时全答success/部分答warning — 小欧-2026-11-19
    exec_code = "warning" if (warnings or answered < total) else "success"
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    llm_data = _build_question_llm_data(
        exec_code, duration_ms, answers=answers, questions=normalized,
        wait_ms=wait_ms, answered=answered, warnings=warnings,
    )
    data = {"answers": answers, "questions": normalized}
    if exec_code == "warning":
        return build_warning(data=data, llm_data=llm_data)
    return build_success(data=data, llm_data=llm_data)


__all__ = ["question"]
