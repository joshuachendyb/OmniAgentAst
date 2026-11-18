# -*- coding: utf-8 -*-
# 2026-11-18 商量 - 新增 question/schedule 注册点(模板参照 timer_register.py): 分类 AGENT, 扁平 input_model, 描述遵循简洁路由规范
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
    "schedule": """创建/更新当前会话的任务计划清单(用户可见的执行计划)。items 为完整清单(整体替换), 每项含 content(任务简述)/status(pending|in_progress|completed|cancelled)。适用于: 任务≥3个步骤、用户给了多项任务、用户索要计划时。单一简单任务不要用。""",
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
    for name, method in tool_methods.items():
        tool_registry.register(
            name=name,
            description=AGENT_TOOL_DESCRIPTIONS.get(name, ""),
            category=ToolCategory.AGENT,
            implementation=method,
            version="1.0.0",
            input_model=AGENT_INPUT_MODELS.get(name),
            examples=AGENT_TOOL_EXAMPLES.get(name, []),
        )
        logger.debug(f"[agent_register] 已注册工具: {name}")


__all__ = ["_register_agent_tools"]
