# -*- coding: utf-8 -*-
"""
基础 Prompt 模板 - 各意图共享的 Prompt 框架

【创建时间】2026-03-21 小沈
【重构时间】2026-05-07 小沈 — 统一prompt组装架构，消除双轨制

职责：
定义各意图 Prompt 的基类接口和公共规则，各意图的 Prompt 继承此类。
统一管理 System Prompt 的组装顺序，确保所有Agent的prompt结构一致。

组装架构（唯一入口：build_full_system_prompt()）：
  ① get_system_prompt()        — 分类特有：角色定义 + 工具详情 + 示例
  ② OUTPUT_FORMAT              — 公共：JSON输出格式（含退出规则，已合并FINISH_RULE）
  ③ TOOL_CALL_RULES            — 公共：工具调用规则（直接调用，禁止反复讨论）
  ④ get_safety_reminder()      — 分类特有：安全提醒（子类覆盖，默认空）
  ⑤ get_rollback_instructions()— 公共：回滚说明
  
  注：⑥ get_parameter_reminder() 已去掉，由方案C（_tools_to_schema_text）替代
     ⑦ FINISH_RULE 已合并到 OUTPUT_FORMAT（2026-05-10 小沈）

运行时由ReactAgentMixin._build_system_prompt()追加：
  ⑧ _build_candidates_hint()   — 动态：候选意图提示
  ⑨ _build_cross_tool_hint()   — 动态：跨分类工具提示

Author: 小沈 - 2026-03-21
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class BasePrompts(ABC):
    """
    Prompt 模板基类（抽象）
    
    子类必须实现：
    - get_system_prompt()      → 获取系统级 Prompt（角色+工具+示例）
    
    子类可选覆盖：
    - get_task_prompt()        → 获取任务描述 Prompt
    - get_observation_prompt() → 获取观察结果 Prompt
    - get_safety_reminder()    → 获取安全提醒
    - get_parameter_reminder() → 获取参数命名提醒
    """

    # 【2026-05-07 小沈】统一JSON输出格式（对齐react_output_parser.py解析逻辑）
    # 【2026-05-10 小沈】合并FINISH_RULE到OUTPUT_FORMAT，统一两种返回情况 - 小健审查
    OUTPUT_FORMAT = """【Response Format - 必须遵守】:
必须使用JSON格式输出，只能返回以下两种情况之一：

情况1：调用工具（继续执行）
{
  "thought": "分析当前状态和下一步决策",
  "reasoning": "为什么选这个工具、参数如何确定",
  "tool_name": "具体工具名",
  "tool_params": {"参数名": "参数值"}
}

情况2：任务完成（退出循环）
{
  "thought": "任务已完成",
  "reasoning": "完成说明",
  "tool_name": "finish",
  "tool_params": {"result": "最终结果"}
}

【字段要求】：
- thought: 必需
- reasoning: 必需
- tool_name: 必需（具体工具名或finish）
- tool_params: 必需（参数对象或{}）

【禁止项】：
- ❌ 禁止同时返回多个tool_name
- ❌ 禁止tool_name存在但tool_params缺失
- ❌ 禁止使用 [TOOL_CALL] 格式（如：[TOOL_CALL]{{...}}[/TOOL_CALL]）
- ❌ 禁止使用XML标签格式（如：&lt;longcat_tool_call&gt; &lt;arg_key&gt;等任何XML/HTML标签）
- ❌ 禁止在content中嵌入工具调用（工具调用必须通过tool_name+tool_params字段）
- ❌ 禁止使用任意自定义标签或特殊标记包裹工具名和参数

【示例】：
{"thought": "用户询问时间", "reasoning": "调用get_current_time", "tool_name": "get_current_time", "tool_params": {"format": "%Y-%m-%d"}}
{"thought": "已完成", "tool_name": "finish", "tool_params": {"result": "当前时间是2026-05-09"}}

【SAFETY WARNING】:
⚠️ 任务完成时必须返回 tool_name="finish"，否则会进入死循环。"""

    # 【2026-05-07 小沈】通用Tool Call Rules
    TOOL_CALL_RULES = """【Tool Call Rules - 极其重要】:
- 确认用户意图后，立即调用对应工具，不要在thought中反复讨论该用哪个工具
- reasoning字段简短说明选择理由即可（1-2句），不要写长篇分析
- ❌ 禁止：在thought中列举多个工具比较优缺点而不调用
- ❌ 禁止：在thought中分析参数是否必填而不调用
- ✅ 正确：确认意图→直接调用→根据结果决定下一步
- 始终用中文回复用户
- 工具返回错误时，向用户解释错误并建议替代方案"""

    # 【2026-05-07 小沈】终止规则已合并到OUTPUT_FORMAT - 2026-05-10 小沈
    FINISH_RULE = ""

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        获取系统级 Prompt（分类特有内容）
        
        只包含本分类特有的内容：
        - Agent 角色定义
        - 可用工具详细说明
        - Tool Call Examples（JSON格式示例）
        
        不包含公共规则（OUTPUT_FORMAT/TOOL_CALL_RULES等由基类统一注入）
        
        Returns:
            系统 Prompt 字符串
        """
        pass

    def get_available_tools_prompt(self) -> str:
        """获取可用工具列表描述（已废弃：工具概要由_call_llm动态注入）"""
        return ""

    def get_task_prompt(self, task: str) -> str:
        """获取任务描述 Prompt"""
        return f"Task: {task}\n\nPlease think step by step and use the available tools to complete this task."

    def get_observation_prompt(self, observation: str) -> str:
        """获取观察结果 Prompt"""
        return f"Observation: {observation}\n\n"

    def get_safety_reminder(self) -> str:
        """获取安全提醒（子类覆盖）"""
        return ""

    def get_parameter_reminder(self) -> str:
        """获取参数命名提醒（子类覆盖）"""
        return ""

    def get_rollback_instructions(self) -> str:
        """获取回滚说明（公共）"""
        return """If an operation fails:
1. Analyze why the operation failed
2. If possible, try an alternative approach (call another tool or use finish to report error)
3. Report the error to the user clearly"""

    def build_full_system_prompt(self) -> str:
        """
        构建完整的系统 Prompt（唯一组装入口）
        
        组装顺序：
        ① get_system_prompt()       — 分类特有（角色+工具+示例）
        ② OUTPUT_FORMAT             — 公共：JSON输出格式（含退出规则）
        ③ TOOL_CALL_RULES           — 公共：工具调用规则
        ④ get_safety_reminder()     — 分类特有：安全提醒
        ⑤ get_rollback_instructions()— 公共：回滚说明
        
        注：⑥ get_parameter_reminder() 已去掉，由方案C（_tools_to_schema_text）替代
           ⑦ FINISH_RULE 已合并到 OUTPUT_FORMAT
        
        Returns:
            完整的 System Prompt
        """
        parts = [self.get_system_prompt()]
        
        parts.append(self.OUTPUT_FORMAT)
        parts.append(self.TOOL_CALL_RULES)
        
        safety = self.get_safety_reminder()
        if safety:
            parts.append(safety)
        
        rollback = self.get_rollback_instructions()
        if rollback:
            parts.append(rollback)
        
        # 【修复 U3 小沈 2026-05-15】避免重复规则
        avoid_repeat_rules = """
【避免重复规则】
- 同一命令/URL成功后不要重复执行（结果不会变）
- 同一命令/URL失败3次后必须换工具或换URL，禁止再试同方式
- 已获取的信息直接使用，不需要重新获取
- 失败后优先尝试替代方法，而非反复重试同一方法"""
        parts.append(avoid_repeat_rules)
        
        return "\n\n".join(parts)


__all__ = [
    "BasePrompts",
]
