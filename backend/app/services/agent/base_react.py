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
from app.utils.prompt_logger import get_prompt_logger


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
                
                # 解析响应 - 使用统一的错误处理方法
                try:
                    parsed = self.parser.parse_response(response)
                except ValueError as e:
                    # 使用ToolParser统一处理解析错误
                    error_result = ToolParser.handle_parse_error(response, e, logger)
                    error_info = error_result["parsed_obs"]
                    
                    # 保存原始response到conversation_history
                    if error_result["save_to_history"]:
                        self.conversation_history.append({"role": "assistant", "content": response})
                    
                    # 发送thought事件（显示错误信息）
                    yield {
                        "type": "thought",
                        "step": step_count,
                        "timestamp": create_timestamp(),
                        "content": error_info["content"],
                        "reasoning": error_info.get("reasoning", ""),
                        "action_tool": error_info["action_tool"],
                        "params": error_info.get("params", {}),
                        "parse_error": error_result["error_type"]  # 添加错误类型标记
                    }
                    
                    # 添加observation提示，让LLM可以重新响应
                    self._add_observation_to_history(f"Parse error: {error_result['error_message']}. Please respond with valid JSON format.")
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
                    "type": "action",  # 步骤13：统一SSE事件type命名
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
                
                # 更新消息历史：先添加 assistant (thought)，后添加 observation (user)
                self._add_observation_to_history(observation_text)
                
                # 记录观察结果到prompt日志
                prompt_logger = get_prompt_logger()
                prompt_logger.log_observation(
                    step_name="工具执行结果",
                    observation_content=observation_text,
                    tool_name=action_tool,
                    tool_params=params
                )
                
                # 再次调用 LLM 获取下一个决策
                self.status = AgentStatus.OBSERVING
                llm_response = await self._get_llm_response()
                
                try:
                    parsed_obs = self.parser.parse_response(llm_response)
                except ValueError as e:
                    # 使用ToolParser统一处理解析错误（与Thought阶段保持一致）
                    error_result = ToolParser.handle_parse_error(llm_response, e, logger)
                    parsed_obs = error_result["parsed_obs"]
                
                is_finished = parsed_obs.get("action_tool") == "finish"
                
                # 保存第2次LLM的响应到conversation_history
                # 优先保存原始响应，保留完整信息
                history_content = parsed_obs.get("raw_response") or parsed_obs.get("content", "")
                self.conversation_history.append({"role": "assistant", "content": history_content})
                
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
                    "reasoning": parsed_obs.get("reasoning"),
                    "action_tool": parsed_obs.get("action_tool", "finish"),
                    "params": parsed_obs.get("params", {}),
                    "is_finished": is_finished
                }
                
                self._trim_history()
                
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
        finally:
            # Hook: 循环结束后调用
            self._on_after_loop()
    
    # ===== 对话历史管理 =====

    MAX_HISTORY_TURNS = 5  # 保留最近 N 轮对话（每轮 = thought + observation）

    def _trim_history(self) -> None:
        """限制对话历史长度，避免 token 爆炸导致 LLM 输出被截断"""
        if len(self.conversation_history) <= 2:
            return  # 少于 system + user，不需要裁剪
        
        # 保留 system message 和最近的 N 轮对话
        # 每轮 = 1 thought (assistant) + 1 observation (user)
        # 加上原始的 user message (task_prompt)
        max_messages = 1 + 1 + (self.MAX_HISTORY_TURNS * 2)  # system + task + N*(thought+obs)
        
        if len(self.conversation_history) > max_messages:
            # 保留 system message 和最近的消息
            system_msg = self.conversation_history[0]
            recent_msgs = self.conversation_history[-max_messages + 1:]
            self.conversation_history = [system_msg] + recent_msgs
            logger.info(f"[History] Trimmed conversation history from {len(self.conversation_history) + max_messages - 1} to {len(self.conversation_history)} messages")

    # ===== 通用方法 =====

    def _add_observation_to_history(self, observation: str) -> None:
        """添加观察结果到对话历史"""
        self.conversation_history.append({"role": "user", "content": observation})
        self._trim_history()
