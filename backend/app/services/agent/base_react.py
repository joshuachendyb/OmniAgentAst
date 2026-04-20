# -*- coding: utf-8 -*-
"""
Agent 核心基类

定义 ReAct 循环的核心逻辑，供所有 Agent 实现类继承。

【重构 2026-03-25】：
- 从 agent.py 提取核心逻辑
- base.py 是核心基准
- 子类继承并实现抽象方法

【重构 2026-04-17】：
- 步骤2.9：所有yield改为StepFactory调用
- 步骤2.10：添加步骤历史管理self.steps
- 步骤2.11：清理废弃的create_*_result函数

Author: 小沈 - 2026-03-25
Updated: 小沈 - 2026-04-17
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator

from app.services.agent.types import AgentStatus
from app.services.agent.react_output_parser import parse_react_response
from app.services.agent.reasoning_steps import (
    StepFactory,
    ReasoningStep,
    ThoughtStep,
    ActionToolStep,
    ObservationStep,
    FinalStep,
    ErrorStep,
)
from app.utils.logger import logger
from app.chat_stream.chat_helpers import create_timestamp
from app.utils.prompt_logger import get_prompt_logger

# 【步骤2.11】已废弃以下导入，改用StepFactory：
# from app.chat_stream.error_handler import create_tool_error_result, create_session_error_result, create_error_from_exception
# 这些函数的逻辑已整合到StepFactory.create_action_tool_step()和create_error_step()


class BaseAgent(ABC):
    """
    Agent 核心基类
    
    定义 ReAct (Thought-Action-Observation) 循环的核心逻辑
    子类需要实现抽象方法
    """
    
    def __init__(self, max_steps: int = 100):
        """初始化 BaseAgent"""
        self.max_steps = max_steps
        
        # 【步骤2.10】步骤历史管理：使用ReasoningStep类型
        self.steps: List[ReasoningStep] = []
        self.conversation_history: List[Dict[str, str]] = []
        self.status = AgentStatus.IDLE
        self.llm_call_count = 0
        self._lock = asyncio.Lock()
        
        # 【步骤4】移除旧ToolParser初始化，使用parse_react_response函数调用
        # self.parser = ToolParser()  # 已移除
        
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
        max_steps: int = 100,
        task_id: Optional[str] = None,
        running_tasks: Optional[Dict[str, Any]] = None
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
        self.last_answer_response = ""  # 保存answer类型的真正答案
        
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

        # ===== 场景1：未捕获异常 (try...except包裹整个循环) =====
        try:
            while True:
                # ===== 场景3：每次循环开始检查最大步数 =====
                if step_count >= max_steps:
                    # 【步骤3.2】直接ErrorStep→return
                    error_step = StepFactory.create_error_step(
                        step=step_count,
                        error_type="max_steps_exceeded",
                        error_message=f"已达到最大迭代次数 {max_steps}",
                        recoverable=False
                    )
                    self.steps.append(error_step)
                    yield error_step.to_dict()
                    self._on_after_loop()
                    return

                step_count += 1
                
                # =====【中断检查】每次循环开始检查任务是否被取消 - 小欧-2026-04-21 =====
                if task_id and running_tasks:
                    # 直接检查 cancelled 标志（非线程安全但可接受，因为只是检查布尔值）
                    is_cancelled = running_tasks.get(task_id, {}).get("cancelled", False)
                    logger.info(f"[InterruptCheck] 任务 {task_id} 取消状态: {is_cancelled}")
                    if is_cancelled:
                        logger.info(f"[Interrupt] 任务 {task_id} 被取消，发送 interrupted 事件")
                        # 使用 interrupted 类型，与 error 类型区分
                        yield {
                            "type": "interrupted",
                            "step": step_count,
                            "message": "用户取消了任务"
                        }
                        self._on_after_loop()
                        return
                
                # ===== 调用LLM =====
                self.status = AgentStatus.THINKING
                logger.info(f"[Debug] 调用LLM (第{self.llm_call_count}轮), history长度={len(self.conversation_history)}")
                response = await self._get_llm_response()
                logger.info(f"[Debug] LLM响应 (第{self.llm_call_count}轮): {response[:200]}...")
                
                # ===== 场景2：LLM返回空响应 =====
                if not response:
                    logger.error(f"LLM返回空响应: {response}")
                    # 【步骤3.2】直接ErrorStep→return
                    error_step = StepFactory.create_error_step(
                        step=step_count,
                        error_type="empty_response",
                        error_message="AI服务返回空响应",
                        recoverable=False
                    )
                    self.steps.append(error_step)
                    yield error_step.to_dict()
                    self._on_after_loop()
                    return
                
                # ===== 场景4：解析响应并获取结果 =====  # 修复 2026-04-15 小沈
                parsed = parse_react_response(response)
                
                # ===== 先获取 parsed 结果 =====
                thought_content = parsed.get("content", "")
                tool_name = parsed.get("tool_name", parsed.get("action_tool", "finish"))
                tool_params = parsed.get("tool_params", parsed.get("params", {}))
                
                # ===== 场景5：正常完成（基于type字段判断）=====
                # 【重构 2026-04-16 小沈】使用type字段判断，替代旧的tool_name=="finish"
                if parsed["type"] in ["answer", "implicit"]:
                    logger.info(f"[parse_react_response] 情况2: type={parsed['type']}, answer/implicit完成")
                    
                    # 【修复D3】成功解析，重置重试计数器
                    self.parse_retry_count = 0
                    
                    # 提取 thought_content 和 answer_response
                    thought_content = parsed.get("content", "")
                    answer_response = parsed.get("response", "")
                    
                    # 【步骤3.4】在退出前，如果存在thought内容，先yield一个ThoughtStep
                    # 确保前端能即时显示AI的思考过程
                    if thought_content and thought_content.strip():
                        thought_step = StepFactory.create_thought_step(
                            step=step_count,
                            content=thought_content,
                            tool_name="finish",
                            tool_params={},
                            thought=parsed.get("thought", thought_content),
                            reasoning=parsed.get("reasoning", "")
                        )
                        self.steps.append(thought_step)
                        yield thought_step.to_dict()

                    # 【步骤3.4】直接FinalStep→return，传入thought参数
                    final_step = StepFactory.create_final_step(
                        step=step_count,
                        response=answer_response or thought_content,
                        thought=parsed.get("thought", thought_content),
                        is_finished=True
                    )
                    self.steps.append(final_step)
                    yield final_step.to_dict()
                    
                    self._on_after_loop()
                    # FinalStep.is_done() 必然为 True，无需检查直接return
                    return
                
                # 【新增】thought_only类型：纯思考分支，继续下一轮循环
                if parsed["type"] == "thought_only":
                    logger.info(f"[parse_react_response] 情况3: type=thought_only, 纯思考继续")
                    thought = parsed.get("thought", "")
                    
                    # 【修复D3】成功解析，重置重试计数器
                    self.parse_retry_count = 0
                    
                    # 【步骤2.9】使用StepFactory创建ThoughtStep
                    thought_step = StepFactory.create_thought_step(
                        step=step_count,
                        content=thought_content,
                        tool_name="",
                        tool_params={},
                        thought=thought,
                        reasoning=parsed.get("reasoning", "")
                    )
                    
                    # 【步骤2.10】记录步骤历史
                    self.steps.append(thought_step)
                    
                    # yield Step字典
                    yield thought_step.to_dict()
                    
                    self.conversation_history.append({"role": "assistant", "content": response})
                    
                    # 【修复D2】调用_trim_history防止历史无限增长
                    self._trim_history()
                    
                    continue  # 继续下一轮循环
                
                # ===== 【深度优化】问题3：检查解析是否失败 =====
                # 不再依赖 "⚠️" 符号，改用显式的 type="parse_error" 判断
                # parse_error表示解析失败，需要重试；error表示真实运行错误
                if parsed["type"] == "parse_error":
                    error_msg = parsed.get("error", "Unknown parse error")
                    logger.warning(f"[parse_react_response] 情况4: 解析错误: {error_msg}, 重试次数={self.parse_retry_count}")
                    
                    # 【步骤3.3】添加错误提示到历史，引导 LLM 修复
                    self._add_observation_to_history(f"Parse Error: {error_msg}. Please ensure your response follows the ReAct format (Thought -> Action -> Action Input).")
                    
                    # 重试计数器+1
                    self.parse_retry_count += 1
                    
                    # 【步骤3.3】重试次数 >= 3？直接ErrorStep→return
                    if self.parse_retry_count >= self.max_parse_retries:
                        error_step = StepFactory.create_error_step(
                            step=step_count,
                            error_type="parse_error",
                            error_message=f"解析失败: {error_msg}（已重试{self.max_parse_retries}次）",
                            recoverable=False
                        )
                        self.steps.append(error_step)
                        yield error_step.to_dict()
                        self._on_after_loop()
                        return
                    # 否则继续下一次循环
                    continue
                
                # ===== 【步骤2.9】情况1：工具调用（Action）=====
                logger.info(f"[parse_react_response] 情况1: type=action, tool={tool_name}")
                # 获取thought和reasoning字段
                thought = parsed.get("thought", "")
                reasoning = parsed.get("reasoning", "")
                
                # 【修复D3】成功解析，重置重试计数器
                self.parse_retry_count = 0

                # 【步骤2.9】使用StepFactory创建ThoughtStep
                thought_step = StepFactory.create_thought_step(
                    step=step_count,
                    content=thought_content,
                    tool_name=tool_name,
                    tool_params=tool_params,
                    thought=thought,
                    reasoning=reasoning
                )

                # 【步骤2.10】记录步骤历史
                self.steps.append(thought_step)

                # yield Step字典
                yield thought_step.to_dict()
                
                # 【修正 2026-04-17 小沈】删除：response 提前加入 conversation_history
                # 按照设计文档15.2.0.4，response 应该在 action_tool 之后才加入
                
                # ========== Action 阶段 ==========
                self.status = AgentStatus.EXECUTING
                
                # 【工具执行前中断检查】在执行工具前检查是否被中断
                if task_id and running_tasks:
                    is_cancelled = running_tasks.get(task_id, {}).get("cancelled", False)
                    logger.info(f"[InterruptCheck] 任务 {task_id} 工具执行前取消状态: {is_cancelled}")
                    if is_cancelled:
                        logger.info(f"[Interrupt] 任务 {task_id} 被取消，工具执行前中断")
                        yield {"type": "interrupted", "step": step_count, "message": "用户取消了任务"}
                        self._on_after_loop()
                        return
                
                # 使用 perf_counter 计算工具执行耗时（高精度）
                start_time = time.perf_counter()
                execution_result = await self._execute_tool(tool_name, tool_params)
                execution_time_ms = int((time.perf_counter() - start_time) * 1000)
                
                # 【工具执行后中断检查】在执行工具后检查是否被中断
                if task_id and running_tasks:
                    is_cancelled = running_tasks.get(task_id, {}).get("cancelled", False)
                    logger.info(f"[InterruptCheck] 任务 {task_id} 工具执行后取消状态: {is_cancelled}")
                    if is_cancelled:
                        logger.info(f"[Interrupt] 任务 {task_id} 被取消，工具执行后中断")
                        yield {"type": "interrupted", "step": step_count, "message": "用户取消了任务"}
                        self._on_after_loop()
                        return
                
                # 【步骤2.9】根据执行结果构建 action_tool
                
                # 【步骤2.9】统一执行结果字典格式（供StepFactory使用）
                execution_result_dict = {
                    "status": execution_result.get("status", "success"),
                    "summary": execution_result.get("summary", ""),
                    "data": execution_result.get("data"),
                    "error": execution_result.get("error", ""),
                    "retry_count": execution_result.get("retry_count", 0)
                }

                # 【步骤2.9】使用StepFactory创建ActionToolStep
                action_step = StepFactory.create_action_tool_step(
                    step=step_count,
                    tool_name=tool_name,
                    tool_params=tool_params,
                    execution_result=execution_result_dict,
                    execution_time_ms=execution_time_ms
                )

                # 【步骤2.10】记录步骤历史
                self.steps.append(action_step)

                # yield Step字典
                yield action_step.to_dict()
                
                # 【修正 2026-04-17 小沈】按照设计文档15.2.0.4执行顺序
                # 步骤5：response 应该在 action_tool 之后再加入 conversation_history
                self.conversation_history.append({"role": "assistant", "content": response})
                
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
                
                # ===== 【步骤2.9】yield observation =====

                # 【步骤2.9】使用StepFactory创建ObservationStep
                observation_step = StepFactory.create_observation_step(
                    step=step_count,
                    tool_name=tool_name,
                    tool_params=tool_params,
                    execution_result=execution_result,
                    return_direct=execution_result.get("return_direct", False)
                )

                # 【步骤2.10】记录步骤历史
                self.steps.append(observation_step)

                # yield Step字典
                yield observation_step.to_dict()

                # 【步骤3.6】核心设计: observation_step.is_done() 决定是否直接结束任务
                if observation_step.is_done():
                    # return_direct 时生成 FinalStep 并退出
                    final_step = StepFactory.create_final_step(
                        step=step_count,
                        response=str(execution_result.get("data", "")),
                        thought="工具执行要求直接返回结果",
                        is_finished=True
                    )
                    self.steps.append(final_step)
                    yield final_step.to_dict()
                    self._on_after_loop()
                    return

                self._trim_history()
        
        except Exception as e:
            # ===== 【步骤2.9+2.11】场景1：未捕获异常 =====
            # 【步骤2.11】废弃create_error_from_exception，使用StepFactory.create_error_step
            logger.error(f"Agent run_stream error: {e}", exc_info=True)
            
            # 【步骤2.9】使用StepFactory创建ErrorStep
            error_step = StepFactory.create_error_step(
                step=step_count,
                error_type="unhandled_exception",
                error_message=str(e),
                recoverable=False
            )
            
            # 【步骤2.10】记录步骤历史
            self.steps.append(error_step)
            
            # yield Step字典
            yield error_step.to_dict()
            
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
        
        # 记录裁剪前的长度
        original_len = len(self.conversation_history)
        
        # 保留重要消息（用户需求、工具调用结果等）
        important = []
        for msg in self.conversation_history[1:-5]:  # 排除system和recent
            content = msg.get("content", "")
            role = msg.get("role", "")
            
            # 保留条件：
            # 1. 用户消息（任务需求）
            # 2. assistant消息（LLM推理过程，保持上下文连贯性）【修复D6】
            # 3. observation消息（工具执行结果，以 "Observation:" 开头）
            if role == "user" or role == "assistant" or content.startswith("Observation:"):
                important.append(msg)
        
        # 如果重要消息太多，只保留最新的10条
        if len(important) > 10:
            important = important[-10:]
        
        # 重建对话历史：system + user + important + recent
        self.conversation_history = [system_msg] + important + recent
        
        # 【修复D5】使用裁剪前记录的长度
        logger.info(f"[History] Trimmed from {original_len} to {len(self.conversation_history)} messages (important={len(important)}, recent={len(recent)})")

    # ===== 通用方法 =====

    def _add_observation_to_history(self, observation: str) -> None:
        """添加观察结果到对话历史"""
        self.conversation_history.append({"role": "user", "content": observation})
        self._trim_history()
