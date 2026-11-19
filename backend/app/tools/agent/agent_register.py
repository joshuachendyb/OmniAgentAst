# -*- coding: utf-8 -*-
# 2026-11-18 商量 - 新增 question/schedule 注册点(模板参照 timer_register.py): 分类 AGENT, 扁平 input_model, 描述遵循简洁路由规范
# 2026-11-19 小欧 - schedule 注册声明 hide_from_steps=True(清单走 notice→taskinfo, 前端步骤流不画工具行);
#   schedule 注册描述为工具级路由文案; items 字段规格由 schema description 引用 tool_constants.SCHEDULE_ITEMS_PARAM_DESC
# 2026-11-19 小欧 - 注册描述"中途更换/必须更新每个状态"改"中途替换/状态按实际进度填写", 消除术语不一致与 pending 误导
# 2026-11-19 小欧 - 注册描述补 plan_stage 必填说明(init/update/finish)
# 2026-11-19 小欧 - question 注册也声明 hide_from_steps=True(与 schedule 同: 非业务交互 tool 不画通用工具行)
# 2026-11-19 小欧 - question 工具描述字段顺序统一 header(可选)→question→options; multiple 改 single(默认true单选) — 小欧-2026-11-19
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
    "question": (  # 2026-11-19 小欧: 工具级路由描述; questions 字段规格见 tool_constants.QUESTION_ITEMS_PARAM_DESC
        "适用于:任务中有不确认的处理方法的时候邀请用户决策"
        "发问的场景：需要有歧义，指令理解不准确、处理有多个方案，需用户进一步给出准确答复"
        "questions 为问题数组, 每项含 header(问题标题, 可选)/question(问题描述, 必填)/options(选项数组, 必填)/single(是否单选, 默认true)。"
        "阻塞等待回答后继续。"
    ),
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
            ],
            "plan_stage": "init",
        }
    ],
}


def _register_agent_tools():
    """注册 question/schedule 两个智能体交互工具 — 商量 2026-11-18"""
    tool_methods = {"question": question, "schedule": schedule}
    # 2026-11-19 小欧 - 前端步骤流隐藏(非业务 tool 共性): 两者都是 agent 与用户的交互, 产出由专属 UI 呈现,
    #   不画通用工具行; 落库/喂 LLM 照常。schedule→notice 清单卡; question→interact 问询浮层。
    hide_from_steps = {"schedule", "question"}
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
