# -*- coding: utf-8 -*-
"""
基础 Prompt 模板 - 各意图共享的 Prompt 框架

【创建时间】2026-03-21 小沈
【设计依据】多意图处理架构设计-小沈-2026-03-20.md (v2.18) - 12.2节

职责：
定义各意图 Prompt 的基类接口，各意图的 Prompt（如 file_prompts.py）继承此类。
统一管理 System Prompt、Task Prompt、Observation Prompt 等通用模板。

各意图的 Prompt 目录结构：
- prompts/base.py              → 共享 Prompt 基类和框架
- prompts/file/file_prompts.py → file 意图的 Prompt（继承 BasePrompts）
- prompts/network/             → network 意图的 Prompt（待实现）
- prompts/desktop/             → desktop 意图的 Prompt（待实现）

扩展新意图只需：
1. 在对应的 prompts/{intent}/ 目录下创建 {intent}_prompts.py
2. 继承 BasePrompts 类
3. 实现 get_system_prompt() 方法

Author: 小沈 - 2026-03-21
"""

from abc import ABC, abstractmethod
from typing import List, Optional


class BasePrompts(ABC):
    """
    Prompt 模板基类（抽象）
    
    所有意图的 Prompt 模板都需要继承此类。
    子类必须实现：
    - get_system_prompt()      → 获取系统级 Prompt
    - get_available_tools_prompt() → 获取工具列表描述
    
    子类可选覆盖：
    - get_task_prompt()        → 获取任务描述 Prompt
    - get_observation_prompt() → 获取观察结果 Prompt
    - get_safety_reminder()    → 获取安全提醒
    - get_parameter_reminder() → 获取参数命名提醒
    """

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        获取系统级 Prompt
        
        包含：
        - Agent 角色定义
        - 可用工具列表
        - 重要约束规则
        
        Returns:
            系统 Prompt 字符串
        """
        pass

    @abstractmethod
    def get_available_tools_prompt(self) -> str:
        """
        获取可用工具列表描述
        
        包含每个工具的名称、参数说明、使用示例。
        用于在 System Prompt 中告知 LLM 可用的工具。
        
        Returns:
            工具列表 Prompt 字符串
        """
        pass

    def get_task_prompt(self, task: str) -> str:
        """
        获取任务描述 Prompt
        
        将用户任务包装成适合 LLM 理解的格式。
        
        Args:
            task: 用户原始输入
            
        Returns:
            任务描述 Prompt 字符串
        """
        return f"Task: {task}\n\nPlease think step by step and use the available tools to complete this task."

    def get_observation_prompt(self, observation: str) -> str:
        """
        获取观察结果 Prompt
        
        将工具执行结果包装成适合 LLM 继续推理的格式。
        
        Args:
            observation: 工具执行结果
            
        Returns:
            观察结果 Prompt 字符串
        """
        return f"Observation: {observation}\n\n"

    def get_safety_reminder(self) -> str:
        """
        获取安全提醒
        
        提醒 LLM 注意操作的安全性约束。
        各意图可覆盖此方法添加特定安全提醒。
        
        Returns:
            安全提醒字符串，默认为空
        """
        return ""

    def get_parameter_reminder(self) -> str:
        """
        获取参数命名提醒
        
        提醒 LLM 正确使用参数名称。
        各意图可覆盖此方法添加特定参数约束。
        
        Returns:
            参数命名提醒字符串，默认为空
        """
        return ""

    def get_rollback_instructions(self) -> str:
        """
        获取回滚说明
        
        当操作失败时，告知 LLM 如何处理回滚。
        
        Returns:
            回滚说明字符串
        """
        return """
If an operation fails:
1. Analyze why the operation failed
2. If possible, try an alternative approach
3. Report the error to the user clearly
"""

    def build_full_system_prompt(self) -> str:
        """
        构建完整的系统 Prompt
        
        将各部分 Prompt 组合成完整的 System Prompt。
        
        Returns:
            完整的 System Prompt
        """
        parts = [
            self.get_system_prompt(),
        ]
        
        tools_prompt = self.get_available_tools_prompt()
        if tools_prompt:
            parts.append(tools_prompt)
        
        safety = self.get_safety_reminder()
        if safety:
            parts.append(safety)
        
        param_reminder = self.get_parameter_reminder()
        if param_reminder:
            parts.append(param_reminder)
        
        rollback = self.get_rollback_instructions()
        if rollback:
            parts.append(rollback)
        
        return "\n\n".join(parts)


__all__ = [
    "BasePrompts",
]
