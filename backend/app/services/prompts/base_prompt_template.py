# -*- coding: utf-8 -*-
"""
基础 Prompt 模板 - 各意图共享的 Prompt 框架

【创建时间】2026-03-21 小沈
【重构时间】2026-05-07 小沈 — 统一prompt组装架构,消除双轨制

职责:
定义各意图 Prompt 的基类接口和公共规则,各意图的 Prompt 继承此类。
统一管理 System Prompt 的组装顺序,确保所有Agent的prompt结构一致。

组装架构(唯一入口:build_full_system_prompt()):
  ① get_system_prompt()        — 分类特有:角色定义 + 工具详情 + 示例
  ② OUTPUT_FORMAT              — 公共:JSON输出格式(含退出规则,已合并FINISH_RULE)
  ③ TOOL_CALL_RULES            — 公共:工具调用规则(直接调用,禁止反复讨论)
  ④ get_safety_reminder()      — 分类特有:安全提醒(子类覆盖,默认空)
  ⑤ get_rollback_instructions()— 公共:回滚说明
  
   注:⑥ FINISH_RULE 已合并到 OUTPUT_FORMAT(2026-05-10 小沈)
      (get_parameter_reminder/get_observation_prompt 已于2026-06-11删除,死代码)

   运行时由Agent._build_system_prompt()追加:
   ⑦ _build_candidates_hint()   — 动态:候选意图提示
   ⑧ _build_cross_tool_hint()   — 动态:跨分类工具提示

Author: 小沈 - 2026-03-21
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class BasePrompts(ABC):
    """
    Prompt 模板基类(抽象)
    
    子类必须实现:
    - get_system_prompt()      → 获取系统级 Prompt(角色+工具+示例)
    
    子类可选覆盖:
    - get_task_prompt()        → 获取任务描述 Prompt
    - get_safety_reminder()    → 获取安全提醒
    """

    # 【2026-05-07 小沈】统一JSON输出格式(对齐react_output_parser.py解析逻辑)
    # 【2026-05-10 小沈】合并FINISH_RULE到OUTPUT_FORMAT,统一两种返回情况 - 小健审查
    OUTPUT_FORMAT = """【Response Format - 必须遵守】:
必须使用JSON格式输出,只能返回以下两种情况之一:

情况1:调用工具(继续执行)
{
  "thought": "分析当前状态和下一步决策",
  "reasoning": "为什么选这个工具、参数如何确定",
  "tool_name": "get_current_time",
  "tool_params": {"action": "now"}
}

情况2:任务完成(退出循环)
{
  "thought": "任务已完成",
  "reasoning": "完成说明",
  "tool_name": "finish",
  "tool_params": {"result": "最终结果"}
}

【字段要求】:
- thought: 必需
- reasoning: 必需
- tool_name: 必需(实际工具名或finish)
- tool_params: 必需(参数对象或{})

【禁止项】:
- ❌ 禁止同时返回多个tool_name
- ❌ 禁止tool_name存在但tool_params缺失
- ❌ 禁止使用 [TOOL_CALL] 格式(如:[TOOL_CALL]{{...}}[/TOOL_CALL])
- ❌ 禁止使用XML标签格式(如:<longcat_tool_call> <arg_key>等任何XML/HTML标签)
- ❌ 禁止在content中嵌入工具调用(工具调用必须通过tool_name+tool_params字段)
- ❌ 禁止使用任意自定义标签或特殊标记包裹工具名和参数

【示例】:
{"thought": "用户询问时间", "reasoning": "调用get_current_time", "tool_name": "get_current_time", "tool_params": {"format": "%Y-%m-%d"}}
{"thought": "已完成", "tool_name": "finish", "tool_params": {"result": "当前时间是2026-05-09"}}"""

    # 【2026-05-07 小沈】通用Tool Call Rules
    # 【2026-06-10 小沈】增强:强制工具调用规则
    # 【2026-06-11 小健】合并SAFETY WARNING(原在OUTPUT_FORMAT),消除SRP/DRY违反
    TOOL_CALL_RULES = """【Tool Call Rules】:
- 确认用户意图后立即调用工具,不要在thought中反复讨论该用哪个工具
- reasoning简短说明选择理由即可(1-2句),不要写长篇分析
- ❌ 禁止:仅用文字回复而不调用工具 — 用户请求需要实际操作时,MUST调用工具
- ✅ 正确:确认意图→直接调用→根据结果决定下一步
- ⚠️ 任务完成时必须返回 tool_name="finish",否则会进入死循环
- 始终用中文回复用户
- 工具返回错误时向用户解释错误并建议替代方案

【IMPERATIVE: 必须使用工具执行操作】:
- 用户请求需要实际操作时,MUST调用对应的工具(非闲聊场景)
- 不得仅回复"好的,我将..."之类的文字确认而不调用工具
- 只有任务完成总结结果时,才能使用 tool_name="finish" 结束
- 如果不确定用什么工具,选择最合理的工具并调用,不要用文字回复代替"""

    # 【2026-06-11 小沈】避免重复规则 — 提取为类常量(#1 fix)
    AVOID_REPEAT_RULES = """
【避免重复规则】
- 同一命令/URL成功后不要重复执行(结果不会变)
- 同一命令/URL失败3次后必须换工具或换URL,禁止再试同方式
- 已获取的信息直接使用,不需要重新获取
- 失败后优先尝试替代方法,而非反复重试同一方法"""


    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        获取系统级 Prompt(分类特有内容)
        
        只包含本分类特有的内容:
        - Agent 角色定义
        - 可用工具详细说明
        - Tool Call Examples(JSON格式示例)
        
        不包含公共规则(OUTPUT_FORMAT/TOOL_CALL_RULES等由基类统一注入)
        
        Returns:
            系统 Prompt 字符串
        """
        pass


    def get_task_prompt(self, task: str) -> str:
        """获取任务描述 Prompt — P2-21: 公共模式(Task+时间+分类指令)"""
        from app.utils.time_utils import now_str
        time_str = now_str()
        domain = self._get_domain_name()
        steps = self._get_domain_steps()
        extra = self._get_domain_extra_notes()
        parts = [
            f"Task: {task}",
            f"\nCurrent time: {time_str}",
            f"\n请完成此{domain}任务,按以下步骤:",
            steps,
        ]
        if extra:
            parts.append(f"\n{extra}")
        return "\n".join(parts)

    def _get_domain_name(self) -> str:
        return "通用"

    def _get_domain_steps(self) -> str:
        return "1. 分析需要什么操作\n2. 使用合适的工具\n3. 用中文总结结果"

    def _get_domain_extra_notes(self) -> str:
        return ""

    def get_safety_reminder(self) -> str:
        """获取安全提醒(子类覆盖)"""
        return ""

    def get_rollback_instructions(self) -> str:
        """获取回滚说明(公共)"""
        return """If an operation fails:
1. Analyze why the operation failed
2. If possible, try an alternative approach (call another tool or use finish to report error)
3. Report the error to the user clearly"""

    def build_full_system_prompt(self, strategy: Optional[str] = None) -> str:
        """
        构建完整的系统 Prompt(唯一组装入口)
        
        组装顺序:
        ① get_system_prompt()       — 分类特有(角色+工具+示例)
        ② OUTPUT_FORMAT             — 公共:JSON输出格式(FC模式跳过,由API生成)
        ③ TOOL_CALL_RULES           — 公共:工具调用规则
        ④ get_safety_reminder()     — 分类特有:安全提醒
        ⑤ get_rollback_instructions()— 公共:回滚说明
        ⑥ AVOID_REPEAT_RULES        — 公共:避免重复操作
        
        Args:
            strategy: "tools"(FC模式,跳过OUTPUT_FORMAT), None(默认,包含OUTPUT_FORMAT)
        
        Returns:
            完整的 System Prompt
        """
        parts = [self.get_system_prompt()]
        

        if strategy != "tools":
            parts.append(self.OUTPUT_FORMAT)
        parts.append(self.TOOL_CALL_RULES)
        
        safety = self.get_safety_reminder()
        if safety:
            parts.append(safety)
        
        rollback = self.get_rollback_instructions()
        if rollback:
            parts.append(rollback)
        

        parts.append(self.AVOID_REPEAT_RULES)
        
        return "\n\n".join(parts)

    @staticmethod
    def build_tool_descriptions(tool_names: List[str], category_label: str = "") -> str:
        """从 ToolRegistry 动态生成工具描述字符串 — 小沈 2026-05-27

        DRY原则:统一 file_prompts 和 system_prompts 中重复的 _build_tool_descriptions。
        新增/修改工具后自动更新 prompt,无需人工维护模板。

        Args:
            tool_names: 工具名列表
            category_label: 分类标签(如"FILE""SYSTEM"),非空时在开头添加分类标题

        Returns:
            工具描述字符串
        """
        from app.services.tools.registry import tool_registry

        tools = []
        for name in tool_names:
            tool = tool_registry.get_tool(name)
            if tool:
                tools.append(tool)

        if not tools:
            return ""

        lines = []
        if category_label:
            lines.append(f"  以下是 {category_label} 分类下的 {len(tools)} 个工具:")

        for idx, t in enumerate(tools, 1):
            desc = t.description or ""
            desc_first = desc.split(',')[0] if ',' in desc else desc
            lines.append(f"{idx}. {t.name} - {desc}")
            lines.append(f"   - 使用场景: 当需要{desc_first}时")

            input_schema = getattr(t, 'input_schema', None) or {}
            params = input_schema.get('properties', {})
            if params:
                required = input_schema.get('required', [])
                parts = []
                for pname, pinfo in params.items():
                    ptype = pinfo.get('type', 'any')
                    mark = '(必填)' if pname in required else ''
                    param_desc = pinfo.get('description', '')
                    if param_desc:
                        parts.append(f"{pname}({ptype}){mark}:{param_desc}")
                    else:
                        parts.append(f"{pname}({ptype}){mark}")
                lines.append(f"   - 参数: {'; '.join(parts)}")
            lines.append(f"   - 返回: 操作结果")
            lines.append("")

        return "\n".join(lines)


__all__ = [
    "BasePrompts",
]
