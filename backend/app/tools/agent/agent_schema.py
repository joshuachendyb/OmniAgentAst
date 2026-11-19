# -*- coding: utf-8 -*-
# 2026-11-18 商量 - 新增 question/schedule 输入模型: 扁平 List[Dict[str, Any]], 避免嵌套 BaseModel 生成 $defs/$ref 被严格 provider 拒绝
# 2026-11-19 小欧 - ScheduleInput.items 描述引用 tool_constants.SCHEDULE_ITEMS_PARAM_DESC(与校验/失败 hint 同源),
#   规格收紧: 条数≤20、content≤100字; 并经 json_schema_extra 内联 item schema 把 enum/required/maxLength
#   前置到参数层(不嵌套 BaseModel 故无 $ref), 校验层 schedule._normalize_items 为兜底双保险
# 2026-11-19 小欧 - ScheduleInput 增 plan_stage 必填参数(enum init/update/finish), LLM 主动阶段决策
"""
agent_schema — 智能体交互工具参数模型(question / schedule)

本仓契约: _validate_params 只做顶层校验, 嵌套字段的语义校验在工具函数内手工完成。
"""
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from app.tools.tool_constants import (
    SCHEDULE_INPUT_MAX_ITEMS,  # 2026-11-19 小欧: items 参数约束单一真源(schema 与校验同源)
    SCHEDULE_ITEM_SCHEMA,
    SCHEDULE_ITEMS_PARAM_DESC,
    SCHEDULE_PLAN_STAGE_DESC,
    SCHEDULE_PLAN_STAGES,
)


class QuestionInput(BaseModel):
    questions: List[Dict[str, Any]] = Field(
        ..., description="问题数组(1~8项)。每项: {question:完整问题, header:极短标签(≤30字), "
                         "options:[{label:选项文本, description:选项说明}](1~9项), multiple:是否多选(默认false)}"
    )


class ScheduleInput(BaseModel):
    items: List[Dict[str, Any]] = Field(
        ...,
        description=f"任务计划清单及状态说明。{SCHEDULE_ITEMS_PARAM_DESC}",
        # 2026-11-19 小欧 - 约束前置参数层: item 内联 schema(enum/required/additionalProperties/maxLength)
        #   + maxItems, 让 LLM 从参数结构就无法填错 status/字段; 实测无 $ref/$defs, 严格 provider 兼容。
        #   List[Dict[str,Any]] 保持扁平类型(不嵌套 BaseModel), json_schema_extra 只加约束不引入引用。
        json_schema_extra={"items": SCHEDULE_ITEM_SCHEMA, "maxItems": SCHEDULE_INPUT_MAX_ITEMS},
    )
    # 2026-11-19 小欧 - plan_stage 必填: LLM 主动声明的计划阶段(init/update/finish), enum 前置约束;
    #   与 items 宽松核对后反馈, 非精密绑定
    plan_stage: str = Field(
        ..., description=SCHEDULE_PLAN_STAGE_DESC,
        json_schema_extra={"enum": list(SCHEDULE_PLAN_STAGES)},
    )


__all__ = ["QuestionInput", "ScheduleInput"]
