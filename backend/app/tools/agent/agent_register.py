# -*- coding: utf-8 -*-
# 2026-11-18 商量 - 新增 question/schedule 注册点(模板参照 timer_register.py): 分类 AGENT, 扁平 input_model, 描述遵循简洁路由规范
# 2026-11-19 小欧 - schedule 注册声明 hide_from_steps=True(清单走 notice→taskinfo, 前端步骤流不画工具行);
#   schedule 注册描述为工具级路由文案; items 字段规格由 schema description 引用 tool_constants.SCHEDULE_ITEMS_PARAM_DESC
# 2026-11-19 小欧 - 注册描述"中途更换/必须更新每个状态"改"中途替换/状态按实际进度填写", 消除术语不一致与 pending 误导
# 2026-11-19 小欧 - 注册描述补 plan_stage 必填说明(init/update/finish)
"""
agent_register — 智能体交互工具注册点(question / schedule)
"""
from app.logger import logger
from app.tools.agent.agent_schema import QuestionInput, ScheduleInput
from app.tools.agent.question import question
from app.tools.agent.schedule import schedule
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory

# 描述仅作一句话路由/适用场景说明, 能力详情写在 Schema 类 description(会进 JSON Schema 发给 LLM)。
AGENT_TOOL_DESCRIPTIONS = {
    "question": """执行中向用户提问, 收集偏好/澄清歧义/获取实现决策。questions 为问题数组, 每项含 question(完整问题)/header(短标签)/options(选项数组)/multiple(是否多选)。适用于: 需要用户决策、指令存在歧义、多个方案需用户选择时。阻塞等待回答后继续。""",
    "schedule": (  # 2026-11-19 小欧: 工具级路由描述; items 字段规格见 tool_constants.SCHEDULE_ITEMS_PARAM_DESC(schema/失败hint 引用)
        "适用: 任务含多步骤(≥3)或用户索要计划时; 单一简单步骤严禁使用。"
        "在长任务中，根据任务进展实时更新及时通知，便于用户掌握任务进展。"
        "创建/更新/结束当前任务的用户可见的执行计划清单,实时同步任务计划完成状态。"
        "中途替换-可按需修改每项的content与status, status按实际进度填写即可(pending/in_progress/completed/cancelled)。"
        "必填 plan_stage 声明本次阶段(init=初建/update=更新进展/finish=结束清空), 需与 items 相符。"
    ),
}

AGENT_INPUT_MODELS = {
    "question": QuestionInput,
    "schedule": ScheduleInput,
}

AGENT_TOOL_EXAMPLES = {
    "question": [
        {
            "questions": [
                {
                    "question": "选择哪种认证方式?",
                    "header": "认证",
                    "options": [
                        {"label": "OAuth", "description": "第三方登录"},
                        {"label": "JWT", "description": "自建账号体系"},
                    ],
                }
            ]
        }
    ],
    "schedule": [
        {
            "items": [
                {"content": "分析需求", "status": "completed"},
                {"content": "编写代码", "status": "in_progress"},
                {"content": "测试", "status": "pending"},
            ]
        }
    ],
}


def _register_agent_tools():
    """注册 question/schedule 两个智能体交互工具 — 商量 2026-11-18"""
    tool_methods = {"question": question, "schedule": schedule}
    # 2026-11-19 小欧 - 前端步骤流隐藏: schedule 清单走 notice→taskinfo 独立通道, 不画工具行;
    #   question 保持默认(False, 仍画工具行, 其用户可见态由 question_required/resolved meta 承担)。
    hide_from_steps = {"schedule"}
    for name, method in tool_methods.items():
        tool_registry.register(
            name=name,
            description=AGENT_TOOL_DESCRIPTIONS.get(name, ""),
            category=ToolCategory.AGENT,
            implementation=method,
            version="1.0.0",
            input_model=AGENT_INPUT_MODELS.get(name),
            examples=AGENT_TOOL_EXAMPLES.get(name, []),
            hide_from_steps=name in hide_from_steps,
        )
        logger.debug(f"[agent_register] 已注册工具: {name}")


__all__ = ["_register_agent_tools"]
