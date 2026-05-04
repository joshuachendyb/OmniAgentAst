# -*- coding: utf-8 -*-
"""
Agent 核心基类 - 支持多工具分类

参考: 文档5.6节+7.5节完整代码

定义 ReAct 循环的核心逻辑，供所有 Agent 实现类继承。

【重构 2026-03-25】：
- 从 agent.py 提取核心逻辑
- base.py 是核心基准
- 子类继承并实现抽象方法

【重构 2026-04-17】：
- 步骤2.9：所有yield改为StepFactory调用
- 步骤2.10：添加步骤历史管理self.steps
- 步骤2.11：清理废弃的create_*_result函数

【Phase 1修复 2026-04-26 小沈】：
- 添加 llm_client, session_id 参数
- 添加 _load_tools 方法从 registry 加载工具

Author: 小沈 - 2026-03-25
Updated: 小沈 - 2026-04-26
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator, Callable

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
from app.services.tools.registry import ToolCategory, get_tools_from_registry_by_category
from app.utils.logger import logger
from app.chat_stream.chat_helpers import create_timestamp
from app.chat_stream.incident_handler import create_incident_data
from app.utils.prompt_logger import get_prompt_logger

# 【步骤2.11】已废弃以下导入，改用StepFactory：
# from app.chat_stream.error_handler import create_tool_error_result, create_session_error_result, create_error_from_exception
# 这些函数的逻辑已整合到StepFactory.create_action_tool_step()和create_error_step()

# ===== 全局默认值常量 =====
# 原则：config.yaml > 代码常量 > 硬编码默认值
# react_sse_wrapper.py 从 config.yaml 读取后传入
DEFAULT_MAX_STEPS = 100


class BaseAgent(ABC):
    """
    Agent 核心基类 - 支持多工具分类
    
    参考: 文档5.6节+7.5节完整代码
    
    定义 ReAct (Thought-Action-Observation) 循环的核心逻辑
    子类需要实现抽象方法
    """
    
    def __init__(
        self,
        llm_client: Any,
        task_id: str,  # 【修改】session_id → task_id，2026-04-26 小沈
        tool_category: Optional[ToolCategory] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        **kwargs
    ):
        """
        初始化 BaseAgent
        参考: 5.1节行 503-534

        Args:
            llm_client: LLM 客户端函数
            task_id: 任务ID - 用于操作安全追踪和审计（必需，不可为空字符串）
            tool_category: 工具分类（可选，用于加载特定工具集）
            max_steps: 最大步数（默认 DEFAULT_MAX_STEPS=100，优先从 config.yaml 读取）
        """
        self.llm_client = llm_client
        self.task_id = task_id  # 赋值task_id
        self.tool_category = tool_category
        self.max_steps = max_steps
        
        # 【修复 2026-04-30 小沈】将 **kwargs 中有用的参数 setattr 到 self
        # 之前 **kwargs 被静默忽略，导致 model/provider/api_base/api_key 丢失
        # 这些属性被 prompt_logger 和 llm_adapter 等使用
        _ALLOWED_KWARGS = {'model', 'provider', 'api_base', 'api_key'}
        for key, value in kwargs.items():
            if key in _ALLOWED_KWARGS:
                setattr(self, key, value)
        
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
        
        # 【Phase1修复】从registry加载工具
        self._tools_dict = self._load_tools()
        
        # 创建工具执行器
        self.executor = None  # 子类应初始化
    
    def _load_tools(self) -> Dict[str, Callable]:
        """
        从registry加载工具
        参考: 7.5节行1082-1088
        """
        if not self.tool_category:
            return {}
        
        return get_tools_from_registry_by_category(self.tool_category)
    
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
    
    def _on_before_loop(self, sys_prompt: str, task_prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        循环开始前 Hook
        子类可覆盖：做 prompt 日志等
        
        【修复 2026-04-30 小沈】添加 context 参数，与子类 FileReactAgent 签名一致
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
        max_steps: int = DEFAULT_MAX_STEPS,
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
        self.last_answer_response = ""
        
        # 【重要】task_id 用于操作追踪和回退，【禁止】使用 session_id
        # session_id 专用于会话场景，操作追踪必须用 task_id
        if task_id:
            self.task_id = task_id  # 保存answer类型的真正答案
        
        # Hook: Session 初始化
        self._on_session_init(task, context)
        
        # 获取 prompt
        sys_prompt = self._get_system_prompt()
        task_prompt = self._get_task_prompt(task, context)
        
        # Hook: 循环开始前
        self._on_before_loop(sys_prompt, task_prompt, context)
        
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
                import time
                if task_id and running_tasks:
                    # 直接检查 cancelled 标志（非线程安全但可接受，因为只是检查布尔值）
                    task_data = running_tasks.get(task_id, {})
                    is_cancelled = task_data.get("cancelled", False)
                    # 【时间测量】计算时间差
                    cancel_request_time = task_data.get("cancel_request_time")
                    if cancel_request_time:
                        time_diff = (time.time() - cancel_request_time) * 1000
                        logger.info(f"[InterruptCheck] 任务 {task_id} 延迟: {time_diff:.0f}ms")
                    if is_cancelled:
                        logger.info(f"[Interrupt] 任务 {task_id} 被取消，发送 interrupted 事件")
                        # 【问题2修复】使用create_incident_data替代裸字典，保证Step封装统一性
                        interrupted_data = create_incident_data(
                            incident_value="interrupted",
                            message="用户取消了任务",
                            step=step_count
                        )
                        yield interrupted_data
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
                    # 【修复 2026-05-05 小沈】response为空时用reasoning+content兜底
                    # LLM返回JSON通常没有response字段，回答在content，推理在reasoning
                    # 将二者合并作为最终回答，确保前端能拿到完整内容
                    answer_response = parsed.get("response", "")
                    if not answer_response or not answer_response.strip():
                        reasoning_part = parsed.get("reasoning", "")
                        answer_response = (reasoning_part + "\n" + thought_content).strip() if reasoning_part else thought_content
                    
                    # 【步骤3.4】在退出前，如果存在thought内容，先yield一个ThoughtStep
                    # 确保前端能即时显示AI的思考过程
                    if thought_content and thought_content.strip():
                        # 2026-05-01 小强修改：thought不兜底thought_content，避免和content重复
                        thought_step = StepFactory.create_thought_step(
                            step=step_count,
                            content=thought_content,
                            tool_name="finish",
                            tool_params={},
                            thought=parsed.get("thought", ""),
                            reasoning=parsed.get("reasoning", "")
                        )
                        self.steps.append(thought_step)
                        yield thought_step.to_dict()

                    # 2026-05-01 小强修改：thought和response各归各位，不生搬硬套重复
                    final_step = StepFactory.create_final_step(
                        step=step_count,
                        response=answer_response,
                        thought=parsed.get("thought", ""),
                        model=getattr(self, 'model', None),
                        provider=getattr(self, 'provider', None)
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
                    # 【问题3修复】重试前发送retrying事件，让前端显示重试提示
                    retrying_data = create_incident_data(
                        incident_value="retrying",
                        message=f"解析失败，正在重试（第{self.parse_retry_count}次）",
                        step=step_count
                    )
                    yield retrying_data
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
                        # 【问题2修复】使用create_incident_data替代裸字典
                        interrupted_data = create_incident_data(
                            incident_value="interrupted",
                            message="用户取消了任务",
                            step=step_count
                        )
                        yield interrupted_data
                        self._on_after_loop()
                        return
                
                # 使用 perf_counter 计算工具执行耗时（高精度）
                start_time = time.perf_counter()
                logger.info(f"[DEBUG_TOOL_PARAMS] before execute_tool: tool_name={tool_name}, tool_params={tool_params}")
                execution_result = await self._execute_tool(tool_name, tool_params)
                execution_time_ms = int((time.perf_counter() - start_time) * 1000)
                
                # 【工具执行后中断检查】在执行工具后检查是否被中断
                if task_id and running_tasks:
                    is_cancelled = running_tasks.get(task_id, {}).get("cancelled", False)
                    logger.info(f"[InterruptCheck] 任务 {task_id} 工具执行后取消状态: {is_cancelled}")
                    if is_cancelled:
                        logger.info(f"[Interrupt] 任务 {task_id} 被取消，工具执行后中断")
                        # 【问题2修复】使用create_incident_data替代裸字典
                        interrupted_data = create_incident_data(
                            incident_value="interrupted",
                            message="用户取消了任务",
                            step=step_count
                        )
                        yield interrupted_data
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
                
                # 【改进2 2026-05-01 小沈 小健】agent层独立内容质量检测
                # 给LLM通道：在observation_text中附加质量警告和content摘要
                if tool_name == "write_file" and exec_status == 'success':
                    data_dict = execution_result.get('data', {}) or {}
                    quality_warning = self._check_write_content_quality(tool_params, data_dict)
                    if quality_warning:
                        observation_text += f"\n⚠️ 内容质量警告: {quality_warning}"
                    # 附加content摘要供LLM自查
                    written_content = tool_params.get("content", "")
                    if written_content:
                        content_preview = written_content[:200]
                        if len(written_content) > 200:
                            content_preview += "..."
                        observation_text += f"\n写入内容摘要({len(written_content)}字符): {content_preview}"

                # 更新消息历史（给LLM通道）
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
                # 【改进2 2026-05-01】给前端通道也附加质量警告
                display_summary = execution_result.get('summary', '')
                if tool_name == "write_file" and exec_status == 'success':
                    data_dict = execution_result.get('data', {}) or {}
                    quality_warning = self._check_write_content_quality(tool_params, data_dict)
                    if quality_warning:
                        display_summary += f"\n⚠️ {quality_warning}"

                # 使用带警告的display_result创建ObservationStep（给前端）
                display_result = dict(execution_result)
                display_result['summary'] = display_summary

                observation_step = StepFactory.create_observation_step(
                    step=step_count,
                    tool_name=tool_name,
                    tool_params=tool_params,
                    execution_result=display_result,
                    return_direct=execution_result.get("return_direct", False)
                )

                # 【步骤2.10】记录步骤历史（用原始execution_result，不含警告，避免重复）
                self.steps.append(StepFactory.create_observation_step(
                    step=step_count,
                    tool_name=tool_name,
                    tool_params=tool_params,
                    execution_result=execution_result,
                    return_direct=execution_result.get("return_direct", False)
                ))

                # yield带警告的版本给前端
                yield observation_step.to_dict()

                # 【步骤3.6】核心设计: observation_step.is_done() 决定是否直接结束任务
                if observation_step.is_done():
                    # return_direct 时生成 FinalStep 并退出
                    final_step = StepFactory.create_final_step(
                        step=step_count,
                        response=str(execution_result.get("data", "")),
                        thought="工具执行要求直接返回结果",
                        model=getattr(self, 'model', None),
                        provider=getattr(self, 'provider', None)
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
        - 保留原始用户消息（任务需求）← 【改进3 2026-05-01 小沈 小健】
        - 保留所有 observation 消息（工具执行结果）
        - 保留最近5条消息

        【修复 2026-04-01 小沈】
        - 问题：关键词匹配可能丢失工具执行结果（如代码、JSON数据）
        - 修复：直接识别 observation 消息（以 "Observation:" 开头），不再依赖关键词

        【优化 2026-04-16 小沈】
        - 问题：entries 数据过大导致 API 429 错误
        - 修复：在 list_directory 中截断 entries（最多 200 项），已从根本上解决超长 observation 问题

        【改进3 2026-05-01 小沈 小健】
        - 问题：原始user消息在important裁剪时可能被丢弃，导致LLM丢失任务约束（如"10章"）
        - 修复：显式保留conversation_history[1]（原始user消息），不参与important裁剪
        - 参考：设计文档 v2.1 §改进3
        """
        if len(self.conversation_history) <= 2:
            return  # 少于 system + user，不需要裁剪

        # 不需要裁剪
        if len(self.conversation_history) <= 15:
            return

        system_msg = self.conversation_history[0]

        # 【改进3 2026-05-01】显式保留原始用户消息，不参与裁剪
        # 原始user消息在conversation_history[1]，记录了用户最初的任务需求（如"写10章小说"）
        original_user_msg = self.conversation_history[1] if len(self.conversation_history) > 1 else None

        recent = self.conversation_history[-5:]

        original_len = len(self.conversation_history)

        # 从index=2开始遍历（跳过已显式保留的原始user消息）
        important = []
        start_idx = 2 if original_user_msg else 1
        for msg in self.conversation_history[start_idx:-5]:
            content = msg.get("content", "")
            role = msg.get("role", "")

            # 保留条件：
            # 1. assistant消息（LLM推理过程，保持上下文连贯性）
            # 2. observation消息（工具执行结果，以 "Observation:" 开头）
            if role == "assistant" or content.startswith("Observation:"):
                important.append(msg)

        # 如果重要消息太多，只保留最新的10条
        if len(important) > 10:
            important = important[-10:]

        # 重建：system + original_user + important + recent
        rebuilt = [system_msg]
        if original_user_msg:
            rebuilt.append(original_user_msg)
        rebuilt.extend(important)
        rebuilt.extend(recent)

        self.conversation_history = rebuilt

        logger.info(f"[History] Trimmed from {original_len} to {len(self.conversation_history)} messages (important={len(important)}, recent={len(recent)})")

    # ===== 通用方法 =====

    def _add_observation_to_history(self, observation: str) -> None:
        """添加观察结果到对话历史"""
        self.conversation_history.append({"role": "user", "content": observation})
        self._trim_history()

    # ========== 【改进2 2026-05-01 小沈 小健】agent层独立内容质量检测 ==========

    def _check_write_content_quality(self, tool_params: dict, data: dict) -> str:
        """
        agent层独立检查write_file写入内容的质量。

        与改进1（工具层）不同，此方法在Observation阶段执行，检测结果通过
        两条Observation通道（给LLM + 给前端）传递。即使工具层漏检（如精确
        关键词未命中），agent层仍能发现并警告LLM和前端用户。

        使用共享的 content_quality.check_content_quality 方法，检测逻辑
        与工具层完全一致。

        另外独立检查 bytes_written 极小（<256字节），提示可能输出不完整。

        Args:
            tool_params: LLM返回的tool_params字典（含content, file_path等）
            data: 工具执行返回的data字典（含bytes_written等）

        Returns:
            警告信息字符串（空字符串表示无问题）
        """
        bytes_written = 0
        if isinstance(data, dict):
            bytes_written = data.get("bytes_written", 0)

        written_content = tool_params.get("content", "")
        file_path = tool_params.get("file_path", "")
        warnings = []

        # 使用共享的自我指涉检测方法
        if written_content:
            from app.services.tools.content_quality import check_content_quality
            quality_result = check_content_quality(content=written_content, file_path=file_path)
            if quality_result.get("is_thought_leak"):
                warnings.append(
                    f"内容疑似思维泄漏：写入内容中{int(quality_result['self_ref_rate']*100)}%"
                    f"为自我指涉描述，不是实际的文件内容。"
                    f"请在content参数中传入真正的文件内容，而非你的思考过程。"
                )

        # 检查bytes_written极小（<256字节），可能不是期望的完整内容
        if 0 < bytes_written < 256:
            warnings.append(
                f"写入内容过小：仅{bytes_written}字节，"
                f"请确认是否已将完整内容写入content参数。"
            )

        return "；".join(warnings)
