# -*- coding: utf-8 -*-
"""
基础 Prompt 模板 - 各意图共享的 Prompt 框架

【创建时间】2026-03-21 小沈
【重构时间】2026-05-07 小沈 — 统一prompt组装架构，消除双轨制

职责：
定义各意图 Prompt 的基类接口和公共规则，各意图的 Prompt 继承此类。
统一管理 System Prompt 的组装顺序，确保所有Agent的prompt结构一致。

组装架构（唯一入口：build_full_system_prompt()）：
  ① get_system_prompt()        — 分类特有：角色定义 + 参数命名 + 工具详情 + 示例
  ② OUTPUT_FORMAT              — 公共：JSON输出格式（对齐解析器）
  ③ TOOL_CALL_RULES            — 公共：工具调用规则（直接调用，禁止反复讨论）
  ④ get_safety_reminder()      — 分类特有：安全提醒（子类覆盖，默认空）
  ⑤ get_parameter_reminder()   — 分类特有：参数命名提醒（子类覆盖，默认空）
  ⑥ get_rollback_instructions()— 公共：回滚说明

  运行时由mixin追加：
  ⑦ _build_candidates_hint()   — 动态：候选意图提示
  ⑧ _build_cross_tool_hint()   — 动态：跨分类工具提示
  ⑨ _FINISH_RULE               — 公共：终止规则（防死循环）

Author: 小沈 - 2026-03-21
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class BasePrompts(ABC):
    """
    Prompt 模板基类（抽象）
    
    所有意图的 Prompt 模板都需要继承此类。
    子类必须实现：
    - get_system_prompt()      → 获取系统级 Prompt（角色+工具+示例）
    
    子类可选覆盖：
    - get_task_prompt()        → 获取任务描述 Prompt
    - get_observation_prompt() → 获取观察结果 Prompt
    - get_safety_reminder()    → 获取安全提醒
    - get_parameter_reminder() → 获取参数命名提醒
    """

    # 【2026-05-07 小沈】统一JSON输出格式（对齐react_output_parser.py解析逻辑）
    OUTPUT_FORMAT = """【Response Format - 必须遵守】:
必须使用JSON格式输出，包含以下字段：
- thought: 分析当前状态和下一步决策（禁止写确认性语言如"已成功"/"需要继续"）
- reasoning: 为什么选这个工具、参数如何确定（必需，不能为空）
- tool_name: 要调用的工具名
- tool_params: 工具参数（无参数时为空对象{}）

格式禁止项：
- ❌ 禁止使用 [TOOL_CALL] 格式
- ❌ 禁止在tool_params中使用 args: {} 嵌套，参数直接作为tool_params的键值对

示例：
{"thought": "用户询问当前时间", "reasoning": "调用get_current_time获取", "tool_name": "get_current_time", "tool_params": {"format": "%Y-%m-%d"}}"""

    # 【2026-05-07 小沈】通用Tool Call Rules
    TOOL_CALL_RULES = """【Tool Call Rules - 极其重要】:
- 确认用户意图后，立即调用对应工具，不要在thought中反复讨论该用哪个工具
- reasoning字段简短说明选择理由即可（1-2句），不要写长篇分析
- ❌ 禁止：在thought中列举多个工具比较优缺点而不调用
- ❌ 禁止：在thought中分析参数是否必填而不调用
- ✅ 正确：确认意图→直接调用→根据结果决定下一步
- 始终用中文回复用户
- 工具返回错误时，向用户解释错误并建议替代方案"""

    # 【2026-05-07 小沈】终止规则（从react_agent_mixin集中到基类）
    FINISH_RULE = """
【TERMINATION RULE - 任务完成时必须正确退出，否则会死循环】:

系统通过解析器判断你的输出类型：
- 含 tool_name 且 tool_name≠"finish" → type=action（继续调用工具，循环不退出）
- 含 tool_name="finish" → type=answer（退出循环，返回结果）
- 不含 tool_name，只含 content/reasoning → type=implicit（退出循环，返回结果）

因此，任务完成后你必须用以下任一方式退出：

方式1（推荐）：使用finish
{"thought": "任务完成", "tool_name": "finish", "tool_params": {"result": "完成摘要"}}

方式2：直接输出纯文本回复（不包含tool_name字段）
{"content": "今天是2026年5月7日", "reasoning": "已获取时间信息"}

⚠️ 禁止：任务完成后在回复中包含其他工具的tool_name，这会被解析为type=action导致死循环"""

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        获取系统级 Prompt（分类特有内容）
        
        只包含本分类特有的内容：
        - Agent 角色定义
        - 参数命名规则（IMPORTANT + FORBIDDEN，精简版）
        - 可用工具详细说明
        - Tool Call Examples（JSON格式示例）
        
        不包含公共规则（OUTPUT_FORMAT/TOOL_CALL_RULES等由基类统一注入）
        
        Returns:
            系统 Prompt 字符串
        """
        pass

    @abstractmethod
    def get_available_tools_prompt(self) -> str:
        """
        获取可用工具列表描述
        
        Returns:
            工具列表 Prompt 字符串
        """
        pass

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
2. If possible, try an alternative approach
3. Report the error to the user clearly"""

    def build_full_system_prompt(self) -> str:
        """
        构建完整的系统 Prompt（唯一组装入口）
        
        【2026-05-07 小沈重构】统一组装架构：
        ① 分类特有内容（角色+工具+示例）
        ② 公共JSON输出格式
        ③ 公共工具调用规则
        ④ 分类特有安全提醒
        ⑤ 分类特有参数命名提醒
        ⑥ 公共回滚说明
        
        Returns:
            完整的 System Prompt
        """
        parts = [self.get_system_prompt()]
        
        parts.append(self.OUTPUT_FORMAT)
        parts.append(self.TOOL_CALL_RULES)
        
        safety = self.get_safety_reminder()
        if safety:
            parts.append(safety)
        
        param_reminder = self.get_parameter_reminder()
        if param_reminder:
            parts.append(param_reminder)
        

        parts.append(self.FINISH_RULE)
        rollback = self.get_rollback_instructions()
        if rollback:
            parts.append(rollback)
        
        return "\n\n".join(parts)


__all__ = [
    "BasePrompts",
]
