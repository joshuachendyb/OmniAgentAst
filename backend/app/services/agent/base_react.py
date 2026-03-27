# -*- coding: utf-8 -*-
"""
Agent 核心基类

定义 ReAct 循环的核心逻辑，供所有 Agent 实现类继承。

【重构 2026-03-25】：
- 从 agent.py 提取核心逻辑
- base.py 是核心基准
- 子类继承并实现抽象方法

Author: 小沈 - 2026-03-25
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator

from app.services.agent.types import AgentStatus
from app.services.agent.tool_parser import ToolParser
from app.utils.logger import logger
from app.chat_stream.chat_helpers import create_timestamp


class BaseAgent(ABC):
    """
    Agent 核心基类
    
    定义 ReAct (Thought-Action-Observation) 循环的核心逻辑
    子类需要实现抽象方法
    """
    
    def __init__(self, max_steps: int = 100):
        """初始化 BaseAgent"""
        self.max_steps = max_steps
        
        self.steps: List[Any] = []
        self.conversation_history: List[Dict[str, str]] = []
        self.status = AgentStatus.IDLE
        self.llm_call_count = 0
        self._lock = asyncio.Lock()
        
        self.parser = ToolParser()
    
    # ===== 抽象方法（子类必须实现）=====
    
    @abstractmethod
    async def _get_llm_response(self) -> str:
        """
        获取 LLM 响应
        
        子类实现：调用具体的 LLM 客户端
        """
        pass
    
    @abstractmethod
    async def _execute_tool(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具
        
        子类实现：调用具体的工具执行器
        """
        pass
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """
        获取系统 Prompt
        
        子类实现：返回具体的系统提示
        """
        pass
    
    @abstractmethod
    def _get_task_prompt(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        获取任务 Prompt
        
        子类实现：返回具体的任务提示
        """
        pass
    
    # ===== 可扩展 Hook 方法（子类可覆盖）=====
    
    def _on_session_init(self, task: str, context: Optional[Dict[str, Any]]):
        """
        Session 初始化 Hook
        子类可覆盖：做 session 相关的初始化
        """
        pass
    
    def _on_before_loop(self, sys_prompt: str, task_prompt: str):
        """
        循环开始前 Hook
        子类可覆盖：做 prompt 日志等
        """
        pass
    
    def _on_after_loop(self):
        """
        循环结束后 Hook
        子类可覆盖：做 session 关闭等
        """
        pass
    
    # ===== 核心方法（子类调用）=====
    
    async def run_stream(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        max_steps: int = 100
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        ReAct 核心循环
        
        每次循环包含 3 个阶段：
        1. Thought - LLM 生成思考和动作
        2. Action - 执行工具
        3. Observation - LLM 根据结果更新思考
        
        【修复 2026-03-25】：observation 包含实际执行数据，让 LLM 能根据结果更新 thought
        """
        # 初始化状态
        self.steps = []
        self.conversation_history = []
        self.status = AgentStatus.THINKING
        self.llm_call_count = 0
        
        # Hook: Session 初始化
        self._on_session_init(task, context)
        
        # 获取 prompt
        sys_prompt = self._get_system_prompt()
        task_prompt = self._get_task_prompt(task, context)
        
        # Hook: 循环开始前
        self._on_before_loop(sys_prompt, task_prompt)
        
        # 添加到对话历史
        self.conversation_history.append({"role": "system", "content": sys_prompt})
        self.conversation_history.append({"role": "user", "content": task_prompt})
        
        step_count = 0
        
        try:
            while step_count < max_steps:
                step_count += 1
                
                # ========== Thought 阶段 ==========
                self.status = AgentStatus.THINKING
                response = await self._get_llm_response()
                
                # 解析响应
                try:
                    parsed = self.parser.parse_response(response)
                except ValueError as e:
                    logger.error(f"Failed to parse LLM response: {e}")
                    self._add_observation_to_history(f"Parse error: {e}. Please respond with valid JSON format.")
                    continue
                
                thought_content = parsed.get("content", "")
                reasoning = parsed.get("reasoning") or ""  # 确保不是None
                action_tool = parsed.get("action_tool", "finish")
                params = parsed.get("params", {})
                
                # yield thought
                current_time = create_timestamp()
                yield {
                    "type": "thought",
                    "step": step_count,
                    "timestamp": current_time,
                    "content": thought_content,
                    "reasoning": reasoning,
                    "action_tool": action_tool,
                    "params": params
                }
                
                # 判断是否结束
                if action_tool == "finish":
                    yield {
                        "type": "final",
                        "timestamp": current_time,
                        "content": params.get("result", thought_content)
                    }
                    break
                
                # ========== Action 阶段 ==========
                self.status = AgentStatus.EXECUTING
                execution_result = await self._execute_tool(action_tool, params)
                
                # yield action_tool
                yield {
                    "type": "action_tool",
                    "content": action_tool,  # 工具名称作为content
                    "step": step_count,
                    "timestamp": current_time,
                    "tool_name": action_tool,
                    "tool_params": params,
                    "execution_status": execution_result.get("status", "success"),
                    "summary": execution_result.get("summary", ""),
                    "raw_data": execution_result.get("data"),
                    "action_retry_count": execution_result.get("retry_count", 0)
                }
                
                # ========== Observation 阶段 ==========
                # 【修复 2026-03-25】把实际执行数据添加到 observation，让 LLM 能根据结果更新 thought
                raw_data = execution_result.get('data')
                if raw_data:
                    observation_text = f"Observation: {execution_result.get('status', 'unknown')} - {execution_result.get('summary', '')}\n实际数据: {raw_data}"
                else:
                    observation_text = f"Observation: {execution_result.get('status', 'unknown')} - {execution_result.get('summary', '')}"
                self._add_observation_to_history(observation_text)
                
                # 再次调用 LLM 获取下一个决策
                self.status = AgentStatus.OBSERVING
                llm_response = await self._get_llm_response()
                
                try:
                    parsed_obs = self.parser.parse_response(llm_response)
                except ValueError as e:
                    logger.error(f"Failed to parse observation LLM response: {e}")
                    parsed_obs = {"content": "无法解析LLM响应", "action_tool": "finish", "params": {}}
                
                is_finished = parsed_obs.get("action_tool") == "finish"
                
                # yield observation
                current_time = create_timestamp()
                yield {
                    "type": "observation",
                    "step": step_count,
                    "timestamp": current_time,
                    "obs_execution_status": execution_result.get("status", "success"),
                    "obs_summary": execution_result.get("summary", ""),
                    "obs_raw_data": execution_result.get("data"),
                    "content": parsed_obs.get("content", ""),
                    "obs_reasoning": parsed_obs.get("reasoning"),
                    "obs_action_tool": parsed_obs.get("action_tool", "finish"),
                    "obs_params": parsed_obs.get("params", {}),
                    "is_finished": is_finished
                }
                
                # 更新消息历史
                self.conversation_history.append({"role": "assistant", "content": thought_content})
                
                # 判断是否结束
                if is_finished:
                    yield {
                        "type": "final",
                        "timestamp": current_time,
                        "content": parsed_obs.get("content", "任务已完成")
                    }
                    break
            
            # 超过最大步数
            if step_count >= max_steps:
                yield {
                    "type": "error",
                    "timestamp": create_timestamp(),
                    "code": "MAX_STEPS_EXCEEDED",
                    "message": f"已达到最大迭代次数 {max_steps}"
                }
                
        except Exception as e:
            logger.error(f"Agent run_stream error: {e}", exc_info=True)
            yield {
                "type": "error",
                "timestamp": create_timestamp(),
                "code": "INTERNAL_ERROR",
                "message": str(e)
            }
    
    # ===== 通用方法 =====

    def _add_observation_to_history(self, observation: str) -> None:
        """添加观察结果到对话历史"""
        self.conversation_history.append({"role": "user", "content": observation})
