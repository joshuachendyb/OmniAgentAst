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
from app.chat_stream.error_handler import create_tool_error_result
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
                
                # 【修复2026-04-08 小沈】检查response是否为None或空
                if not response:
                    logger.error(f"LLM返回空响应: {response}")
                    yield {
                        "type": "error",
                        "step": step_count,
                        "timestamp": create_timestamp(),
                        "code": "EMPTY_RESPONSE",
                        "message": "AI服务返回空响应，请稍后重试"
                    }
                    break
                
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
                        "tool_name": error_info.get("tool_name", "finish"),
                        "tool_params": error_info.get("tool_params", {}),
                        "parse_error": error_result["error_type"]  # 添加错误类型标记
                    }
                    
                    # 添加observation提示，让LLM可以重新响应
                    self._add_observation_to_history(f"Parse error: {error_result['error_message']}. Please respond with valid JSON format.")
                    
                    # 【修复2026-04-08 小沈】解析失败时yield error并退出，避免无限循环
                    # 原：continue 会跳过第203行的 finish 判断，导致无限循环
                    yield {
                        "type": "final",
                        "timestamp": create_timestamp(),
                        "content": error_info["content"]
                    }
                    break
                
                thought_content = parsed.get("content", "")
                tool_name = parsed.get("tool_name", parsed.get("action_tool", "finish"))
                tool_params = parsed.get("tool_params", parsed.get("params", {}))
                
                # yield thought
                current_time = create_timestamp()
                yield {
                    "type": "thought",
                    "step": step_count,
                    "timestamp": current_time,
                    "content": thought_content,
                    "tool_name": tool_name,
                    "tool_params": tool_params
                }
                
                # 【修复 2026-03-31 小沈】将 LLM 的 thought 响应加入 conversation_history
                # 问题：LLM 下一轮看不到自己的思考过程，导致上下文丢失
                # 修复：在 yield thought 后立即添加 assistant 响应到历史
                self.conversation_history.append({"role": "assistant", "content": response})
                
                # 判断是否结束
                if tool_name == "finish":
                    yield {
                        "type": "final",
                        "timestamp": current_time,
                        "content": tool_params.get("result", thought_content)
                    }
                    break
                
                # ========== Action 阶段 ==========
                self.status = AgentStatus.EXECUTING
                execution_result = await self._execute_tool(tool_name, tool_params)
                
                # 根据执行结果构建 action_tool
                exec_status = execution_result.get("status", "success")
                
                if exec_status == "error":
                    # 工具执行失败 - 使用统一函数 (【小沈重构 2026-04-10】)
                    action_tool_result = create_tool_error_result(
                        tool_name=tool_name,
                        error_message=execution_result.get("summary", "执行失败"),
                        step_num=step_count,
                        tool_params=tool_params,
                        retry_count=execution_result.get("retry_count", 0),
                        raw_data=execution_result.get("data"),
                        timestamp=current_time  # 使用统一的时间戳
                    )
                    yield action_tool_result
                else:
                    # 工具执行成功 - 保持原有格式
                    yield {
                        "type": "action_tool",
                        "step": step_count,
                        "timestamp": current_time,
                        "tool_name": tool_name,
                        "tool_params": tool_params,
                        "execution_status": "success",
                        "summary": execution_result.get("summary", ""),
                        "raw_data": execution_result.get("data"),
                        "action_retry_count": 0
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
                    tool_name=tool_name,
                    tool_params=tool_params
                )
                
                # ========== Observation 阶段（简化版）==========
                # 【修复 2026-04-07 小沈】删除第二次LLM调用
                # 问题：每step调用2次LLM，token消耗翻倍
                # 修复：直接使用工具执行结果作为observation，下一轮循环自动调用LLM
                current_time = create_timestamp()
                yield {
                    "type": "observation",
                    "step": step_count,
                    "timestamp": current_time,
                    "tool_name": tool_name,
                    "content": f"Tool '{tool_name}' executed: {execution_result.get('summary', 'completed')}"
                }

                self._trim_history()
            
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
        """
        分层保留对话历史
        - 保留 system message
        - 保留用户消息
        - 保留所有 observation 消息（工具执行结果）
        - 保留最近5条消息

        【修复 2026-04-01 小沈】
        - 问题：关键词匹配可能丢失工具执行结果（如代码、JSON数据）
        - 修复：直接识别 observation 消息（以 "Observation:" 开头），不再依赖关键词
        """
        if len(self.conversation_history) <= 2:
            return  # 少于 system + user，不需要裁剪
        
        # 不需要裁剪
        if len(self.conversation_history) <= 15:
            return
        
        # 保留 system message
        system_msg = self.conversation_history[0]
        
        # 保留最近5条消息（最新工具调用上下文）
        recent = self.conversation_history[-5:]
        
        # 保留重要消息（用户需求、工具调用结果等）
        important = []
        for msg in self.conversation_history[1:-5]:  # 排除system和recent
            content = msg.get("content", "")
            role = msg.get("role", "")
            
            # 保留条件：
            # 1. 用户消息（任务需求）
            # 2. observation 消息（工具执行结果，以 "Observation:" 开头）
            if role == "user" or content.startswith("Observation:"):
                important.append(msg)
        
        # 如果重要消息太多，只保留最新的10条
        if len(important) > 10:
            important = important[-10:]
        
        # 重建对话历史：system + user + important + recent
        self.conversation_history = [system_msg] + important + recent
        
        logger.info(f"[History] Trimmed from {len(self.conversation_history) + 5} to {len(self.conversation_history)} messages (important={len(important)}, recent={len(recent)})")

    # ===== 通用方法 =====

    def _add_observation_to_history(self, observation: str) -> None:
        """添加观察结果到对话历史"""
        self.conversation_history.append({"role": "user", "content": observation})
        self._trim_history()
