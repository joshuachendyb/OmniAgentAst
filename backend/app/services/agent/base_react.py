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
from app.chat_stream.error_handler import create_tool_error_result, create_session_error_result, create_error_from_exception
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
        
        # 【重构 2026-04-11 小沈】解析重试相关参数
        self.parse_retry_count = 0  # 解析重试计数器
        self.max_parse_retries = 3   # 最大重试次数
    
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
        
        【重构 2026-04-11 小沈】按照"先 break → 循环外 yield"原则重构：
        - 场景1-4（错误场景）：循环内 break → 循环外 yield error
        - 场景5（正常完成）：循环内 break → 循环外 yield final
        - yield error/final 后就是最后一个 step，不需要额外的 final step
        
        场景编号：
        1. 未捕获异常 - except块捕获
        2. LLM返回空响应
        3. 超过最大步数
        4. 解析失败 - 重试3次
        5. 正常完成（finish）
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
        
        # 循环外变量（用于保存需要循环外处理的值）
        last_error = None
        last_response = None
        thought_content = ""
        tool_name = "finish"
        tool_params = {}
        
        # ===== 场景1：未捕获异常 (try...except包裹整个循环) =====
        try:
            while True:
                # ===== 每次迭代开始时重置计数器 =====
                self.parse_retry_count = 0
                
                # ===== 场景3：每次循环开始检查最大步数 =====
                if step_count >= max_steps:
                    last_error = "max_steps_exceeded"
                    break  # 达到最大步数，退出
                
                step_count += 1
                
                # ===== 调用LLM =====
                self.status = AgentStatus.THINKING
                logger.info(f"[Debug] 调用LLM (第{self.llm_call_count}轮), history长度={len(self.conversation_history)}")
                response = await self._get_llm_response()
                logger.info(f"[Debug] LLM响应 (第{self.llm_call_count}轮): {response[:200]}...")
                
                # ===== 场景2：LLM返回空响应 =====
                if not response:
                    logger.error(f"LLM返回空响应: {response}")
                    last_error = "empty_response"
                    break  # 空响应，退出
                
                # ===== 场景4：解析响应并获取结果 =====  # 修复 2026-04-15 小沈
                parsed = self.parser.parse_response(response)
                
                # ===== 先获取 parsed 结果 =====
                thought_content = parsed.get("content", "")
                tool_name = parsed.get("tool_name", parsed.get("action_tool", "finish"))
                tool_params = parsed.get("tool_params", parsed.get("params", {}))
                
                # ===== 场景5：正常完成（finish）=====
                # 【修复 2026-04-15 小沈】先判断 finish，再判断解析错误
                # 避免将合法的 finish 响应误判为解析错误
                if tool_name == "finish":
                    last_response = response  # 保存用于后续使用
                    break  # 直接退出，不yield thought
                
                # ===== 检查解析是否失败 =====  # 修复 2026-04-15 小沈
                # parse_response现在返回错误结果而不是抛异常
                # 通过检查content是否包含错误标识来判断
                is_parse_error = "⚠️" in parsed.get("content", "")
                
                if is_parse_error:
                    # 保存原始response到conversation_history
                    self.conversation_history.append({"role": "assistant", "content": response})
                    
                    # 添加错误提示到历史，让LLM重新尝试
                    error_content = parsed.get("content", "Parse error")
                    self._add_observation_to_history(f"{error_content}. Please respond with valid JSON format.")
                    
                    # 重试计数器+1
                    self.parse_retry_count += 1
                    
                    # 重试次数 >= 3？退出循环；否则继续循环
                    if self.parse_retry_count >= self.max_parse_retries:
                        last_error = "parse_error"
                        break  # 重试次数用尽，退出循环
                    continue  # 继续循环，让LLM重新尝试
                
                # ===== 正常流转：yield thought (非finish时) =====
                current_time = create_timestamp()
                # 获取thought和reasoning字段
                thought = parsed.get("thought", "")
                reasoning = parsed.get("reasoning", "")
                yield {
                    "type": "thought",
                    "step": step_count,
                    "timestamp": current_time,
                    "content": thought_content,
                    "thought": thought,
                    "reasoning": reasoning,
                    "tool_name": tool_name,
                    "tool_params": tool_params
                }
                
                # 将 LLM 的 thought 响应加入 conversation_history
                self.conversation_history.append({"role": "assistant", "content": response})
                
                # ========== Action 阶段 ==========
                self.status = AgentStatus.EXECUTING
                execution_result = await self._execute_tool(tool_name, tool_params)
                
                # 根据执行结果构建 action_tool
                exec_status = execution_result.get("status", "success")
                
                if exec_status == "success":
                    # 工具执行成功 - 按15.7.1要求修改字段
                    yield {
                        "type": "action_tool",
                        "step": step_count,
                        "timestamp": current_time,
                        "tool_name": tool_name,
                        "tool_params": tool_params,
                        "execution_status": "success",
                        "summary": execution_result.get("summary", ""),
                        "execution_result": execution_result.get("data"),
                        "error_message": "",
                        "execution_time_ms": execution_result.get("execution_time_ms", 0),
                        "action_retry_count": 0
                    }
                elif exec_status == "warning":
                    # 工具执行警告（部分成功）- 使用 create_tool_error_result 传递 warning 状态
                    action_tool_result = create_tool_error_result(
                        tool_name=tool_name,
                        error_message=execution_result.get("summary", "部分成功"),
                        step_num=step_count,
                        tool_params=tool_params,
                        retry_count=execution_result.get("retry_count", 0),
                        raw_data=execution_result.get("data"),
                        timestamp=current_time,
                        status="warning"  # 传递 warning 状态
                    )
                    yield action_tool_result
                else:
                    # error/timeout/permission_denied - 统一使用 create_tool_error_result
                    action_tool_result = create_tool_error_result(
                        tool_name=tool_name,
                        error_message=execution_result.get("summary", "执行失败"),
                        step_num=step_count,
                        tool_params=tool_params,
                        retry_count=execution_result.get("retry_count", 0),
                        raw_data=execution_result.get("data"),
                        timestamp=current_time,
                        status=exec_status  # 传递实际的 execution_status
                    )
                    yield action_tool_result
                
                # ========== Observation 阶段 ==========
                # 区分不同 execution_status 生成 observation_text（给 LLM 历史）
                exec_status = execution_result.get('status', 'unknown')
                
                if exec_status == 'success':
                    # 成功状态：显示完整信息，包括实际数据
                    observation_text = f"Observation: {exec_status} - {execution_result.get('summary', '')}"
                    if execution_result.get('data'):
                        data = execution_result.get('data')
                        # 【优化 2026-04-16 小沈】检查是否截断
                        # 如果是 list_directory 的大目录，会返回 truncated=True
                        if isinstance(data, dict) and data.get('truncated'):
                            # 大目录截断：显示统计摘要，让 LLM 知道目录规模
                            # 格式：[目录包含 X 项: Y 目录, Z 文件，显示前 200 项]
                            total = data.get('total', 0)
                            dir_count = data.get('dir_count', 0)
                            file_count = data.get('file_count', 0)
                            display_count = min(total, 200)
                            truncated_info = f"\n[目录包含 {total} 项: {dir_count} 目录, {file_count} 文件，显示前 {display_count} 项]"
                            observation_text += truncated_info
                            # 【修复 2026-04-16 小沈】保留 entries 中的 path 字段
                            # 原因：LLM 需要 path 来定位文件/目录
                            if data.get('entries'):
                                observation_text += f"\n实际数据: {data.get('entries')}"
                        else:
                            # 非截断数据：直接显示
                            observation_text += f"\n实际数据: {data}"
                elif exec_status == 'warning':
                    # 警告状态：显示警告信息和部分数据
                    observation_text = f"Observation: {exec_status} - {execution_result.get('summary', '')}"
                    if execution_result.get('data'):
                        observation_text += f"\n部分数据: {execution_result.get('data')}"
                else:
                    # 失败状态（error/timeout/permission_denied）：只显示错误摘要，不显示数据
                    observation_text = f"Observation: {exec_status} - {execution_result.get('summary', '')}"
                
                # 【小沈修复 2026-04-16】生成 display_text（给前端 UI 显示）
                # 只显示摘要，不包含冗余数据结构
                display_text = execution_result.get('summary', '')
                
                # 更新消息历史
                logger.info(f"[Debug] observation加入history: {observation_text[:100]}...")
                self._add_observation_to_history(observation_text)
                
                # 记录观察结果到prompt日志
                prompt_logger = get_prompt_logger()
                prompt_logger.log_observation(
                    step_name="工具执行结果",
                    observation_content=observation_text,
                    tool_name=tool_name,
                    tool_params=tool_params
                )
                
                # yield observation - 【小沈修复 2026-04-16】使用 display_text 给前端
                yield {
                    "type": "observation",
                    "step": step_count,
                    "timestamp": create_timestamp(),
                    "tool_name": tool_name,
                    "tool_params": tool_params,
                    "observation": display_text,  # 前端显示用精简摘要
                    "execution_status": exec_status,
                    "return_direct": execution_result.get("return_direct", False),
                }

                self._trim_history()
        
            # ===== 循环外：统一处理退出场景 =====
            
            # 场景5：正常完成（发现finish时不yield thought，这里只需要yield final）
            if tool_name == "finish":
                yield {
                    "type": "final",
                    "step": step_count,  # 新增字段
                    "timestamp": create_timestamp(),
                    "response": tool_params.get("result", thought_content),  # content替换为response
                    "is_finished": True,  # 新增字段
                    "thought": thought_content,  # 新增字段
                    "is_streaming": False,  # 新增字段
                    "is_reasoning": False,  # 新增字段
                }
                self._on_after_loop()
                return
            
            # 场景2：LLM返回空响应错误
            if last_error == "empty_response":
                error_response, error_step = create_session_error_result(
                    original_error="AI服务返回空响应",
                    error_step_type='empty_response',
                    step_num=step_count
                )
                yield error_response
                self._on_after_loop()
                return
            
            # 场景4：解析失败（重试3次后仍失败）
            if last_error == "parse_error":
                error_response, error_step = create_session_error_result(
                    original_error=f"解析失败（已重试{self.max_parse_retries}次）",
                    error_step_type='parse_error',
                    step_num=step_count
                )
                yield error_response
                self._on_after_loop()
                return
            
            # 场景3：超过最大步数
            if step_count >= max_steps:
                error_response, error_step = create_session_error_result(
                    original_error=f"已达到最大迭代次数 {max_steps}",
                    error_step_type='max_steps_exceeded',
                    step_num=step_count
                )
                yield error_response
                self._on_after_loop()
                return
            
            # 场景1：未捕获异常 - 正常情况下不会执行到这里
            # 如果执行到这里，说明循环正常结束但没有处理任何退出场景
            # 这是一个安全保护分支
    
        except Exception as e:
            # 【重构 2026-04-11 小沈】场景1：未捕获异常
            # except块中只做记录日志和yield error
            logger.error(f"Agent run_stream error: {e}", exc_info=True)
            
            error_response, error_step = create_error_from_exception(
                error=e,
                step_num=step_count,
                model=None,
                provider=None
            )
            yield error_response
            
            self._on_after_loop()
            return
    
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

        【优化 2026-04-16 小沈】
        - 问题：entries 数据过大导致 API 429 错误
        - 修复：在 list_directory 中截断 entries（最多 200 项），已从根本上解决超长 observation 问题
        """
        if len(self.conversation_history) <= 2:
            return  # 少于 system + user，不需要裁剪

        # 【优化 2026-04-16 小沈】不再需要总长度检查，因为 entries 已被截断
        
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
