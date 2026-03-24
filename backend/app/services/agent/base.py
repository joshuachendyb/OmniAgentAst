# -*- coding: utf-8 -*-
"""
通用 Agent 基类

提供 ReAct Agent 的核心逻辑，供所有 Agent 实现类继承。

设计依据：file_operations/agent.py (1327行) 提取的通用逻辑

Author: 小沈 - 2026-03-21
"""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator

from app.services.agent.types import Step, AgentResult, AgentStatus
from app.services.agent.tool_parser import ToolParser
from app.services.agent.tool_executor import ToolExecutor
from app.utils.logger import logger
from app.chat_stream.chat_helpers import create_timestamp


class BaseAgent(ABC):
    """
    通用 Agent 基类
    
    实现 ReAct (Thought-Action-Observation) 循环的核心逻辑
    子类需要实现：
    - __init__: 初始化 self.executor
    - _get_llm_response_text()
    - _get_llm_response_with_tools()
    - _get_llm_response_with_response_format()
    """
    
    def __init__(
        self,
        max_steps: int = 20,
        use_function_calling: bool = False,
    ):
        """
        初始化 BaseAgent
        
        Args:
            max_steps: 最大执行步数
            use_function_calling: 是否使用 Function Calling 模式
        """
        self.max_steps = max_steps
        self.use_function_calling = use_function_calling
        
        self.steps: List[Step] = []
        self.conversation_history: List[Dict[str, str]] = []
        self.status = AgentStatus.IDLE
        self.llm_call_count = 0
        self._lock = asyncio.Lock()
        
        self.executor = None  # 保留引用（子类可能使用）
        self.model_name: str = ""
        self.tools: List[Dict[str, Any]] = []
        self.parser = ToolParser()
    
    async def run_with_tools(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> AgentResult:
        """
        运行 Agent 完成任务（ReAct 循环）
        
        Args:
            task: 任务描述
            context: 额外上下文
            system_prompt: 自定义系统 prompt（可选）
            
        Returns:
            Agent 执行结果
        """
        async with self._lock:
            return await self._run_internal(task, context, system_prompt)
    
    async def _run_internal(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> AgentResult:
        """
        内部运行方法（已被锁保护）
        
        实现 ReAct 循环的核心逻辑
        """
        self.steps = []
        self.conversation_history = []
        self.status = AgentStatus.THINKING
        self.llm_call_count = 0
        
        logger.info(f"[LLM Counter] Agent run started, LLM counter reset to 0")
        
        if system_prompt:
            self.conversation_history.append({"role": "system", "content": system_prompt})
        
        if context:
            context_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])
            task_with_context = f"{task}\n\nContext:\n{context_str}"
        else:
            task_with_context = task
        
        self.conversation_history.append({"role": "user", "content": task_with_context})
        
        current_step = 0
        result = None
        
        try:
            while current_step < self.max_steps:
                current_step += 1
                
                self.status = AgentStatus.THINKING
                response = await self._get_llm_response()
                
                try:
                    parsed = self.parser.parse_response(response)
                except ValueError as e:
                    logger.error(f"Failed to parse LLM response: {e}")
                    self._add_observation_to_history(
                        f"Parse error: {e}. Please respond with valid JSON format."
                    )
                    continue
                
                thought_content = parsed.get("content", parsed.get("thought", ""))
                action_tool = parsed.get("action_tool", parsed.get("action", "finish"))
                params = parsed.get("params", parsed.get("action_input", {}))
                
                step = Step(
                    step_number=current_step,
                    thought=thought_content,
                    action=action_tool,
                    action_input=params
                )
                
                logger.info(
                    f"Step {current_step}: {action_tool} - {thought_content[:50]}..."
                )
                
                if action_tool == "finish":
                    if isinstance(params, dict):
                        final_result = params
                    else:
                        final_result = {"result": str(params)}
                    
                    step.observation = {
                        "success": True,
                        "result": final_result
                    }
                    self.steps.append(step)
                    self.status = AgentStatus.COMPLETED
                    
                    result = AgentResult(
                        success=True,
                        message="Task completed successfully",
                        steps=self.steps,
                        total_steps=current_step,
                        final_result=final_result
                    )
                    return result
                
                self.status = AgentStatus.EXECUTING
                observation = await self._execute_with_retry(
                    action_tool,
                    params
                )
                
                step.observation = observation
                self.steps.append(step)
                
                obs_text = self._format_observation(observation)
                self._add_observation_to_history(obs_text)
                
                self.status = AgentStatus.OBSERVING
            
            self.status = AgentStatus.FAILED
            result = AgentResult(
                success=False,
                message=f"Exceeded maximum steps ({self.max_steps})",
                steps=self.steps,
                total_steps=current_step,
                error="Maximum steps exceeded"
            )
            return result
            
        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            self.status = AgentStatus.FAILED
            result = AgentResult(
                success=False,
                message=f"Execution failed: {str(e)}",
                steps=self.steps,
                total_steps=current_step,
                error=str(e)
            )
            return result
    
    async def run_stream_with_tools(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 100
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        异步流式执行 Agent，每轮循环完成后立即 yield 输出
        
        Args:
            task: 任务描述
            context: 额外上下文
            system_prompt: 自定义系统 prompt（可选）
            max_steps: 最大迭代次数
        
        Yields:
            各个阶段的输出字典
        """
        self.steps = []
        self.conversation_history = []
        self.status = AgentStatus.THINKING
        self.llm_call_count = 0
        
        if system_prompt:
            self.conversation_history.append({"role": "system", "content": system_prompt})
        
        if context:
            context_str = "\n".join([f"- {k}: {v}" for k, v in context.items()])
            task_with_context = f"{task}\n\nContext:\n{context_str}"
        else:
            task_with_context = task
        
        self.conversation_history.append({"role": "user", "content": task_with_context})
        
        step_count = 0
        
        try:
            while step_count < max_steps:
                step_count += 1
                
                self.status = AgentStatus.THINKING
                response = await self._get_llm_response()
                
                try:
                    parsed = self.parser.parse_response(response)
                except ValueError as e:
                    logger.error(f"Failed to parse LLM response: {e}")
                    self._add_observation_to_history(f"Parse error: {e}. Please respond with valid JSON format.")
                    continue
                
                thought_content = parsed.get("content", "")
                reasoning = parsed.get("reasoning")
                action_tool = parsed.get("action_tool", "finish")
                params = parsed.get("params", {})
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
                
                if action_tool == "finish":
                    yield {
                        "type": "final",
                        "timestamp": current_time,
                        "content": params.get("result", thought_content)
                    }
                    break
                
                self.status = AgentStatus.EXECUTING
                execution_result = await self._execute_tool(action_tool, params)
                
                yield {
                    "type": "action_tool",
                    "step": step_count,
                    "timestamp": current_time,
                    "tool_name": action_tool,
                    "tool_params": params,
                    "execution_status": execution_result.get("status", "success"),
                    "summary": execution_result.get("summary", ""),
                    "raw_data": execution_result.get("data"),
                    "action_retry_count": execution_result.get("retry_count", 0)
                }
                
                observation_text = f"Observation: {execution_result.get('status', 'unknown')} - {execution_result.get('summary', '')}"
                self._add_observation_to_history(observation_text)
                
                self.status = AgentStatus.OBSERVING
                llm_response = await self._get_llm_response()
                
                try:
                    parsed_obs = self.parser.parse_response(llm_response)
                except ValueError as e:
                    logger.error(f"Failed to parse observation LLM response: {e}")
                    parsed_obs = {"content": "无法解析LLM响应", "action_tool": "finish", "params": {}}
                
                is_finished = parsed_obs.get("action_tool") == "finish"
                
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
                
                self.conversation_history.append({"role": "assistant", "content": thought_content})
                
                if is_finished:
                    yield {
                        "type": "final",
                        "timestamp": current_time,
                        "content": parsed_obs.get("content", "任务已完成")
                    }
                    break
            
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
    
    async def _get_llm_response(self) -> str:
        """获取 LLM 响应的统一入口"""
        self.llm_call_count += 1
        logger.info(f"[LLM Counter] >>> LLM called, count: {self.llm_call_count}")
        
        try:
            last_message = self.conversation_history[-1]["content"]
            history_dicts = self.conversation_history[:-1]
            
            if self.use_function_calling and self.tools:
                response = await self._get_llm_response_with_tools(
                    message=last_message,
                    history_dicts=history_dicts
                )
            else:
                response = await self._get_llm_response_text(
                    message=last_message,
                    history_dicts=history_dicts
                )
            
            return response
            
        except Exception as e:
            logger.error(f"LLM client error: {e}")
            raise
    
    @abstractmethod
    async def _get_llm_response_text(
        self,
        message: str,
        history_dicts: List[Dict[str, str]]
    ) -> str:
        """
        获取 LLM 响应（文本模式）
        
        Args:
            message: 当前用户消息
            history_dicts: 对话历史
            
        Returns:
            LLM 响应文本
        """
        pass
    
    @abstractmethod
    async def _get_llm_response_with_tools(
        self,
        message: str,
        history_dicts: List[Dict[str, str]]
    ) -> str:
        """
        获取 LLM 响应（Function Calling 模式）
        
        Args:
            message: 当前用户消息
            history_dicts: 对话历史
            
        Returns:
            LLM 响应文本（ReAct 格式）
        """
        pass
    
    @abstractmethod
    async def _execute_tool(
        self,
        action: str,
        action_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行工具的抽象方法
        
        子类必须实现此方法，执行具体的工具调用
        
        Args:
            action: 工具名称
            action_input: 工具参数
            
        Returns:
            执行结果，包含 success/error/status/summary 等字段
        """
        pass
    
    async def _get_llm_response_with_response_format(
        self,
        message: str,
        history_dicts: List[Dict]
    ) -> str:
        """
        使用 response_format 模式获取 LLM 响应
        
        Args:
            message: 当前用户消息
            history_dicts: 对话历史
            
        Returns:
            LLM 响应内容（ReAct 格式的 JSON 字符串）
        """
        schema = {
            "type": "json_object",
            "json_schema": {
                "type": "object",
                "properties": {
                    "thought": {"type": "string", "description": "思考过程"},
                    "action": {"type": "string", "description": "工具名称"},
                    "action_input": {
                        "type": "object",
                        "description": "工具参数"
                    }
                },
                "required": ["thought", "action", "action_input"]
            }
        }
        
        try:
            response = await self._call_llm_with_response_format(
                message=message,
                history=history_dicts,
                response_format=schema
            )
            
            if hasattr(response, 'content'):
                content = response.content
            elif isinstance(response, dict):
                content = response.get("content", str(response))
            else:
                content = str(response)
            
            logger.info(f"[Agent] response_format raw content: {repr(content)[:500]}")
            
            try:
                result = json.loads(content)
                thought = result.get("thought", "")
                action = result.get("action", "")
                action_input = result.get("action_input", {})
                
                formatted = {
                    "thought": thought,
                    "action_tool": action,
                    "params": action_input
                }
                
                content = json.dumps(formatted, ensure_ascii=False)
                logger.info(f"[Agent] response_format parsed: action={action}")
                
            except json.JSONDecodeError as e:
                logger.error(f"[Agent] Failed to parse response_format JSON: {e}")
                raise Exception(f"Invalid JSON from LLM: {content}")
            
            self.conversation_history.append({"role": "assistant", "content": content})
            return content
            
        except Exception as e:
            logger.error(f"[Agent] _get_llm_response_with_response_format failed: {e}")
            raise
    
    async def _call_llm_with_response_format(
        self,
        message: str,
        history: List[Dict],
        response_format: Dict[str, Any]
    ) -> Any:
        """
        调用 LLM 并指定 response_format
        
        子类可重写此方法以适配不同的 LLM 客户端
        
        Args:
            message: 当前消息
            history: 对话历史
            response_format: 响应格式定义
            
        Returns:
            LLM 响应
        """
        raise NotImplementedError("子类必须实现 _call_llm_with_response_format 或重写 _get_llm_response_with_response_format")
    
    def _format_tool_calls_for_agent(self, tool_calls: List[Dict[str, Any]]) -> str:
        """
        将 tool_calls 格式化为 Agent 可以理解的格式
        
        将 OpenAI 格式的 tool_calls 转换为 Agent 的 ToolParser 可以解析的 JSON 格式
        """
        if not tool_calls:
            return ""
        
        tool_call = tool_calls[0]
        func = tool_call.get("function", {})
        tool_name = func.get("name", "unknown")
        
        arguments_str = func.get("arguments", "{}")
        try:
            if isinstance(arguments_str, str):
                arguments = json.loads(arguments_str)
            else:
                arguments = arguments_str
        except json.JSONDecodeError:
            arguments = {}
        
        formatted = {
            "thought": f"我需要调用 {tool_name} 工具来完成任务",
            "action_tool": tool_name,
            "params": arguments
        }
        
        return json.dumps(formatted, ensure_ascii=False)
    
    def _add_observation_to_history(self, observation: str) -> None:
        """添加观察结果到对话历史"""
        self.conversation_history.append({"role": "user", "content": observation})
    
    async def _execute_with_retry(
        self,
        action: str,
        action_input: Dict[str, Any],
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        执行动作并重试（指数退避策略）
        
        Args:
            action: 动作名称
            action_input: 动作参数
            max_retries: 最大重试次数（默认3次）
        
        Returns:
            执行结果
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                observation = await self._execute_tool(action, action_input)
                
                if observation.get("status") != "error":
                    if attempt > 0:
                        logger.info(
                            f"Action '{action}' succeeded after {attempt + 1} attempt(s)"
                        )
                    return observation
                
                last_error = observation.get("summary", "Unknown error")
                logger.warning(
                    f"Action '{action}' failed (attempt {attempt + 1}/{max_retries}): {last_error}"
                )
                
            except Exception as e:
                last_error = str(e)
                logger.error(
                    f"Action '{action}' raised exception (attempt {attempt + 1}/{max_retries}): {e}"
                )
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(
                    f"Retrying '{action}' in {wait_time}s... (attempt {attempt + 2}/{max_retries})"
                )
                await asyncio.sleep(wait_time)
        
        error_msg = f"Action '{action}' failed after {max_retries} attempts: {last_error}"
        logger.error(error_msg)
        return {
            "status": "error",
            "summary": error_msg,
            "data": None,
            "retry_count": max_retries
        }
    
    def _format_observation(self, observation: Dict[str, Any]) -> str:
        """格式化观察结果为文本"""
        status = observation.get("status", "success")
        if status != "error":
            result = observation.get("data", observation.get("result", {}))
            if isinstance(result, dict):
                return json.dumps(result, ensure_ascii=False, indent=2)
            return str(result)
        else:
            error = observation.get("summary", observation.get("error", "Unknown error"))
            return f"Error: {error}"
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """获取执行日志"""
        return [step.to_dict() for step in self.steps]
