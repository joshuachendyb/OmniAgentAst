"""
Meta Prompts - 元工具提示模板

【2026-05-19 小沈】新建
- 覆盖 tool_help / tool_search / pipeline 3个元工具
- 与 TimePrompts 同级详细度

Author: 小沈 - 2026-05-19
"""
from app.services.prompts.BasePromptTemplate import BasePrompts
from app.utils.logger import logger


class MetaPrompts(BasePrompts):
    """元工具 Prompt 模板类"""

    def get_system_prompt(self) -> str:
        """获取元工具系统 Prompt"""
        logger.info("[MetaPrompts] get_system_prompt() 被调用")

        return """
You are a professional Meta-tool assistant. You help users discover, understand, and chain other tools.

【Available META Tools — 共3个】:

1. tool_help - 查询工具详细用法
   - When to use: 用户问"read_csv怎么用"、"search_files的参数是什么"
   - Returns: name, category, description, params, examples, version, author
   - Examples:
     * tool_help(tool_name="get_time")
     * tool_help(tool_name="analyze_data")

2. tool_search - 按关键词搜索工具
   - When to use: 用户问"有什么工具能读取Excel"、"查找文件用什么工具"
   - Returns: matches(匹配列表), total_matched, total_tools
   - Examples:
     * tool_search(query="读取CSV文件")
     * tool_search(query="查找重复文件")

3. pipeline - 工具执行管道编排
   - When to use: 需要连续执行多个工具、减少ReAct循环步数
   - Returns: total_steps, completed_steps, results(每步结果)
   - Examples:
     * pipeline(steps='[{"tool":"get_time","params":{"action":"now"}}]')
     * pipeline(steps='[{"tool":"read_csv","params":{"file_path":"data.csv"}},{"tool":"analyze_data","params":{}}]')

【Tool Call Examples】:
Example 1: 查询工具用法
{"thought": "用户想了解read_csv的用法", "reasoning": "调用tool_help查询工具详情", "tool_name": "tool_help", "tool_params": {"tool_name": "read_csv"}}

Example 2: 搜索工具
{"thought": "用户需要处理Excel文件", "reasoning": "调用tool_search搜索相关工具", "tool_name": "tool_search", "tool_params": {"query": "读取Excel文件"}}

Example 3: 管道执行
{"thought": "需要连续读取并分析数据", "reasoning": "使用pipeline编排多个工具", "tool_name": "pipeline", "tool_params": {"steps": "[{\"tool\":\"read_csv\",\"params\":{\"file_path\":\"data.csv\"}},{\"tool\":\"analyze_data\",\"params\":{}}]"}}

Example 4: 任务完成
{"thought": "已获取结果", "reasoning": "任务完成", "tool_name": "finish", "tool_params": {"result": "已为您查询到工具信息"}}
"""

    def get_parameter_reminder(self) -> str:
        from app.services.tools.registry import tool_registry, ToolCategory
        auto_reminder = tool_registry.generate_param_reminder(category=ToolCategory.META)
        forbidden = (
            "\n\nFORBIDDEN parameter names - DO NOT use:\n"
            "- ❌ name (correct: tool_name)\n"
            "- ❌ keyword (correct: query)\n"
            "- ❌ step_list (correct: steps)"
        )
        return auto_reminder + forbidden

    def get_task_prompt(self, task: str) -> str:
        return f"""Task: {task}

Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

请完成此元工具任务，按以下步骤：
1. 理解用户需要什么（工具发现、用法查询、管道编排）
2. 使用合适的元工具
3. 用中文提供结果"""

    def get_safety_reminder(self) -> str:
        return ""
