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
import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator, Callable

from app.services.agent.types import AgentStatus
from app.services.agent.react_output_parser import parse_react_response
from app.services.agent.message_builder import MessageBuilder
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
from app.services.agent.types import AgentStatus
from app.services.preprocessing.intent_classifier import IntentClassifier  # 【步骤9】意图分类器
from app.utils.logger import logger
from app.chat_stream.chat_helpers import create_timestamp
from app.chat_stream.incident_handler import create_incident_data
from app.utils.prompt_logger import get_prompt_logger
from app.services.agent.tool_result_formatter import extract_status
# 【Phase 1修复 小健 2026-05-14】删除模块级import，改为函数内import
# from app.services.tools.file.file_tools import _current_task_id

# 【步骤2.11】已废弃以下导入，改用StepFactory：
# from app.chat_stream.error_handler import create_tool_error_result, create_session_error_result, create_error_from_exception
# 这些函数的逻辑已整合到StepFactory.create_action_tool_step()和create_error_step()

# ===== 全局默认值常量 =====
# 原则：config.yaml > 代码常量 > 硬编码默认值
# react_sse_wrapper.py 从 config.yaml 读取后传入
DEFAULT_MAX_STEPS = 100
# 连续chunk最大次数-达到此阈值且为工具Agent时提升为implicit退出循环
# chat Agent（无工具）首个chunk即退出，不受此限制
MAX_CONSECUTIVE_CHUNKS = 5


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
        self.message_builder = MessageBuilder(max_context_chars=self.MAX_CONTEXT_CHARS)
        self.status = AgentStatus.IDLE
        self.llm_call_count = 0
        self._lock = asyncio.Lock()
        
        # 【步骤4】移除旧ToolParser初始化，使用parse_react_response函数调用
        # self.parser = ToolParser()  # 已移除
        
        # 【重构 2026-04-11 小沈】解析重试相关参数
        self.parse_retry_count = 0  # 解析重试计数器
        self.max_parse_retries = 3   # 最大重试次数
        
        # 【修复 2026-05-05 小沈】空响应重试相关参数
        self.empty_response_retry_count = 0  # 空响应重试计数器
        self.max_empty_response_retries = 2  # 空响应最大重试次数（截断历史后重试）
        
        # 【Phase1修复】从registry加载工具 - 【修复 2026-05-10 小健】确保先注册再加载
        self._tools_dict = self._load_tools()
        self._loaded_categories = set()
        if self.tool_category:
            self._loaded_categories.add(self.tool_category.value)
        # self._loaded_categories.add("support_tool")  # support_tool已废弃，不再预加载
        
        from app.services.preprocessing.intent_classifier import IntentClassifier
        self._intent_classifier = IntentClassifier()
        
        # 【v2.3新增】chunk处理相关属性—所有Agent子类共享
        self.max_consecutive_chunks = MAX_CONSECUTIVE_CHUNKS  # 连续chunk达此阈值时提升为implicit
        # self.temp_history 已迁入 MessageBuilder，此处保留向后兼容属性
        self.temp_history: List[Dict[str, str]] = []  # 临时历史，用于chunk过程中LLM参考
        
        # 创建工具执行器
        self.executor = None  # 子类应初始化
        
        # 【2026-05-21 小沈】缓存/失败计数/汇总已迁入MessageBuilder，此处删除
        # 原: _executed_cache, _cache_ttl, _cache_timestamps, _failed_attempts, _executed_tool_summary
    
    @property
    def conversation_history(self) -> List[Dict[str, str]]:
        """@property透传至MessageBuilder — 小沈 2026-05-21"""
        return self.message_builder.conversation_history
    
    @conversation_history.setter
    def conversation_history(self, value: List[Dict[str, str]]) -> None:
        """@property setter — 小沈 2026-05-21"""
        self.message_builder.conversation_history = value
    
    def _load_tools(self) -> Dict[str, Callable]:
        """
        从registry加载工具
        参考: 7.5节行1082-1088
        """
        if not self.tool_category:
            return {}
        
        # 【Phase 1修复 小健 2026-05-14】【修复 U8 小沈 2026-05-15】全量注册，不再传categories
        from app.services.tools import ensure_tools_registered
        ensure_tools_registered()
        
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
    
    # 【2026-05-21 小沈】_params_to_key和_is_no_cache_tool已迁入MessageBuilder
    
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
    
    # ===== 步骤9：动态加载工具相关方法（文档4.14节）=====
    
    def load_tools_by_intent(self, intent_type: str, reason: str = ""):
        """
        动态加载某个意图的工具
        
        参考：文档4.14节步骤9代码示例
        
        Args:
            intent_type: 意图类型（file/meta/shell/network等，也兼容旧名time/database等）
            reason: 加载原因（用于日志）
        """
        if intent_type in self._loaded_categories:
            return  # 已加载
        
        logger.info(f"[动态加载] 原因: {reason}，加载意图: {intent_type}")
        
        # 1. 获取该意图的工具（支持新旧意图名） - 【2026-05-18 小沈】
        from app.services.tools.registry import resolve_category
        category = resolve_category(intent_type)
        if not category:
            logger.warning(f"[动态加载] 意图'{intent_type}'无对应工具分类")
            return
        new_tools = get_tools_from_registry_by_category(category)
        
        # 2. 添加到_tools_dict
        self._tools_dict.update(new_tools)
        self._loaded_categories.add(category.value)

        # 【修复 N4 小沈 2026-05-15】不再注入load_hint，依赖下一轮detail自动包含新分类
        new_tool_names = sorted(new_tools.keys())
        logger.info(f"[动态加载] 已加载{intent_type}分类的{len(new_tool_names)}个工具，下一轮detail将自动包含")

        # 3. 刷新FC通道的tools定义（如果已启用）
        # 【修复 问题2+9 小沈 2026-05-15】增加openai_tools存在性检查
        if hasattr(self, 'tools_strategy') and self.tools_strategy is not None and hasattr(self, 'openai_tools') and self.openai_tools:
            from app.services.tools.registry import tool_registry
            new_openai_tools = tool_registry.to_openai_tools(category=category)
            self.openai_tools.extend([t for t in new_openai_tools if t not in self.openai_tools])
            self.tools_strategy.tools = self.openai_tools
            logger.info(f"[FC刷新] tools定义已更新，当前{len(self.openai_tools)}个")

        # 【修复 N1 小沈 2026-05-15】动态加载后同步刷新response_format enum
        if hasattr(self, 'response_format_strategy') and self.response_format_strategy and hasattr(self, 'openai_tools') and self.openai_tools:
            try:
                tool_names = [t["function"]["name"] for t in self.openai_tools] + ["finish"]
                self.response_format_strategy.response_format["json_schema"]["schema"]["properties"]["tool_name"]["enum"] = tool_names
                logger.info(f"[FC刷新] response_format enum已更新，当前{len(tool_names)}个工具名")
            except Exception as e:
                logger.warning(f"[FC刷新] response_format enum更新失败: {e}")

        # 【2026-05-21 小沈】统一使用message_builder.invalidate_cache()清除全部缓存
        self.message_builder.invalidate_cache()
        # mixin自身的缓存也需清除
        if hasattr(self, '_cached_schema_text'):
            delattr(self, '_cached_schema_text')
        if hasattr(self, '_cached_tools_content'):
            delattr(self, '_cached_tools_content')
        if hasattr(self, '_last_injected_categories'):
            delattr(self, '_last_injected_categories')

        logger.info(f"[动态加载] 完成，新增{len(new_tools)}个工具，总计{len(self._tools_dict)}个")
    
    async def _check_and_load_missing_tools(self, observation: str, llm_client=None):
        """全量注册后无需动态加载 - 小沈 2026-05-15"""
        return
    
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
        self.message_builder.reset_per_run()
        self.conversation_history = self.message_builder.conversation_history
        self.status = AgentStatus.THINKING
        self.llm_call_count = 0
        
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
        self.message_builder.init_history(sys_prompt, task_prompt)
        self.conversation_history = self.message_builder.conversation_history
        
        step_count = 0
        # chunk处理相关变量
        chunk_buffer = ""
        consecutive_chunk_count = 0
        consecutive_cache_hit_count = 0
        MAX_CONSECUTIVE_CACHE_HIT = 2
        # 超时机制
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
                logger.info(f"[Debug] 调用LLM (第{self.llm_call_count + 1}轮), history长度={len(self.conversation_history)}")
                response = await self._get_llm_response()
                logger.info(f"[Debug] LLM响应 (第{self.llm_call_count + 1}轮): {response[:200]}...")
                
                # =====【LLM返回后中断检查】2026-05-13 小沈 =====
                # ai_service.cancel()取消了HTTP请求，LLM可能返回错误/空。
                # 在进入重试逻辑之前检查cancelled标志，避免把取消当成可重试的错误
                if task_id and running_tasks:
                    task_data = running_tasks.get(task_id, {})
                    if task_data.get("cancelled", False):
                        logger.info(f"[Interrupt] 任务 {task_id} LLM返回后被取消，立即中断")
                        interrupted_data = create_incident_data(
                            incident_value="interrupted",
                            message="用户取消了任务",
                            step=step_count
                        )
                        yield interrupted_data
                        self._on_after_loop()
                        return
                
                # ===== 场景2：LLM返回空响应 =====
                if not response:
                    self.empty_response_retry_count += 1
                    logger.error(
                        f"[空响应] LLM返回空响应 (第{self.empty_response_retry_count}次重试), "
                        f"history长度={len(self.conversation_history)}"
                    )
                    
                    if self.empty_response_retry_count <= self.max_empty_response_retries:
                        # 【修复 2026-05-05 小沈】截断历史重试
                        original_len = len(self.conversation_history)
                        if original_len > 4:
                            # 保留system prompt(前2条) + 最近2条，删除中间的
                            kept = self.conversation_history[:2] + self.conversation_history[-2:]
                            removed_len = original_len - len(kept)
                            self.conversation_history = kept
                            logger.warning(
                                f"[空响应截断历史] 从{original_len}条截断到{len(kept)}条, "
                                f"移除{removed_len}条中间历史, 准备重试"
                            )
                            # 发送重试提示事件
                            retrying_data = create_incident_data(
                                incident_value="retrying",
                                message=f"AI返回空响应，已压缩对话历史重试（第{self.empty_response_retry_count}次）"
                            )
                            yield retrying_data
                            continue
                        else:
                            logger.warning("[空响应] 历史已很短无法截断，直接报错")
                    # 重试次数用尽或历史太短，报错退出
                    error_step = StepFactory.create_error_step(
                        step=step_count,
                        error_type="empty_response",
                        error_message=f"AI服务返回空响应（已重试{self.empty_response_retry_count}次）",
                        recoverable=False
                    )
                    self.steps.append(error_step)
                    yield error_step.to_dict()
                    self._on_after_loop()
                    return
                
                # ===== 场景4：解析响应并获取结果 =====  # 修复 2026-04-15 小沈
                parsed = parse_react_response(response)
                
                # 【修复 2026-05-05 小沈】成功获取响应，重置空响应计数器
                self.empty_response_retry_count = 0
                
                # ===== 先获取 parsed 结果 =====
                thought_content = parsed.get("content", "")
                tool_name = parsed.get("tool_name", parsed.get("action_tool", "finish"))
                tool_params = parsed.get("tool_params", parsed.get("params", {}))
                
                # ===== chunk类型处理（流式中间文本片段，非完成信号）=====
                # 解析器已将纯文本从implicit改为chunk，此处处理并continue
                if parsed["type"] == "chunk":
                    logger.info(f"[parse_react_response] type=chunk, 流式中间文本片段，继续循环")
                    self.parse_retry_count = 0
                    
                    chunk_content = parsed.get("content", "")
                    
                    # 拼接chunk_buffer
                    chunk_buffer += chunk_content
                    consecutive_chunk_count += 1
                    
                    # 追加到临时历史（供下一轮LLM参考）
                    self.message_builder.temp_history.append({"role": "assistant", "content": chunk_content})
                    if len(self.message_builder.temp_history) > 10:
                        self.message_builder.temp_history = self.message_builder.temp_history[-10:]
                    
                    # yield chunk步骤给前端（is_reasoning默认False，非流式场景无法从chunk元数据获取）
                    chunk_step = StepFactory.create_chunk_step(
                        step=step_count, content=chunk_content
                    )
                    self.steps.append(chunk_step)
                    yield chunk_step.to_dict()
                    
                    # 无工具Agent（chat）：第一个chunk直接作为最终回答，不循环
                    if self.tool_category is None:
                        logger.info(f"[ReAct] 无工具Agent，第一个chunk即为最终回答，退出循环")
                        self.temp_history.clear()
                        if chunk_buffer:
                            self.message_builder.add_assistant(chunk_buffer)
                        final_step = StepFactory.create_final_step(
                            step=step_count, response=chunk_buffer, thought=""
                        )
                        self.steps.append(final_step)
                        yield final_step.to_dict()
                        self._on_after_loop()
                        return
                    
                    # 工具Agent：连续chunk达阈值→提升为implicit退出循环
                    # 阈值意义：连续N次chunk（无tool_call），说明LLM在重复生成，应结束
                    if consecutive_chunk_count >= self.max_consecutive_chunks:
                        logger.info(f"[ReAct] 连续chunk达到{self.max_consecutive_chunks}次，提升为implicit")
                        self.temp_history.clear()
                        if chunk_buffer:
                            self.message_builder.add_assistant(chunk_buffer)
                        final_step = StepFactory.create_final_step(
                            step=step_count, response=chunk_buffer, thought=""
                        )
                        self.steps.append(final_step)
                        yield final_step.to_dict()
                        self._on_after_loop()
                        return
                    
                    # 【修复 2026-05-14 小沈】chunk不是完成信号，必须continue防止fall through到action
                    # 如果没有continue，代码会落到场景5(非answer/implicit)→action处理
                    # → tool_name=None→_execute_tool(None,None)→None.copy()崩溃
                    continue
                
                # ===== 场景5：正常完成（基于type字段判断）=====
                # 【重构 2026-04-16 小沈】使用type字段判断，替代旧的tool_name=="finish"
                if parsed["type"] in ["answer", "implicit"]:
                    logger.info(f"[parse_react_response] 情况2: type={parsed['type']}, answer/implicit完成")
                    
                    # 【修复D3】成功解析，重置重试计数器
                    self.parse_retry_count = 0
                    
                    # flush chunk_buffer到正式会话历史
                    if chunk_buffer:
                        self.temp_history.clear()
                        self.message_builder.add_assistant(chunk_buffer)
                        chunk_buffer = ""
                        consecutive_chunk_count = 0
                    
                    # 提取 thought_content 和 answer_response
                    thought_content = parsed.get("content", "")
                    # 【修复 2026-05-07 小沈】response取值链：response → tool_params.result → content → reasoning
                    answer_response = parsed.get("response", "")
                    if not answer_response or not answer_response.strip():
                        answer_response = parsed.get("tool_params", {}).get("result", "") if isinstance(parsed.get("tool_params"), dict) else ""
                    if not answer_response or not answer_response.strip():
                        answer_response = parsed.get("content", "")
                    if not answer_response or not answer_response.strip():
                        answer_response = parsed.get("reasoning", "")
                    
                    # 【修复 2026-05-05 小沈】finish时直接yield final，不再先yield thought
                    _reasoning = parsed.get("reasoning", "")
                    final_step = StepFactory.create_final_step(
                        step=step_count,
                        response=answer_response,
                        thought=_reasoning,
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
                    # 【修复 2026-05-05 小沈】thought去重拼接：相同则不拼
                    _thought_val = thought_content
                    if thought and thought.strip():
                        _thought_val = thought if thought == thought_content else (thought + "\n" + thought_content).strip()
                    thought_step = StepFactory.create_thought_step(
                        step=step_count,
                        content="",
                        tool_name="",
                        tool_params={},
                        thought=_thought_val,
                        reasoning=parsed.get("reasoning", "")
                    )
                    
                    # 【步骤2.10】记录步骤历史
                    self.steps.append(thought_step)
                    
                    # yield Step字典
                    yield thought_step.to_dict()
                    
                    self.message_builder.add_assistant(response)
                    
                    # 【修复D2】调用message_builder.trim_history防止历史无限增长
                    self.message_builder.trim_history()
                    
                    continue  # 继续下一轮循环
                
                # ===== 【深度优化】问题3：检查解析是否失败 =====
                # 不再依赖 "⚠️" 符号，改用显式的 type="parse_error" 判断
                # parse_error表示解析失败，需要重试；error表示真实运行错误
                if parsed["type"] == "parse_error":
                    error_msg = parsed.get("error", "Unknown parse error")
                    logger.warning(f"[parse_react_response] 情况4: 解析错误: {error_msg}, 重试次数={self.parse_retry_count}")
                    
                    # 【修复 小健 2026-05-16】网络/API错误不注入history，只有LLM格式错误才注入
                    _err = str(error_msg).lower()
                    is_network_error = any(kw in _err for kw in [
                        "429", "rate_limit", "请求过于频繁",
                        "readerror", "connecttimeout", "connectionerror",
                        "timeout", "服务调用失败", "api请求",
                        "502", "503", "504", "network",
                    ])
                    if not is_network_error:
                        # LLM格式错误：添加提示到历史，引导LLM修复
                        self.message_builder.add_observation(f"Parse Error: {error_msg}. Please ensure your response follows the ReAct format (Thought -> Action -> Action Input).")
                    else:
                        # 网络/API错误：不注入history，给前端提示，直接重试
                        logger.info(f"[parse_react_response] 网络/API错误，不注入history: {error_msg}")
                        # 【修复 小健 2026-05-21】429等网络错误添加指数退避等待
                        _is_429 = "429" in _err or "rate_limit" in _err or "请求过于频繁" in _err
                        if _is_429:
                            _retry_delay = 2.0 * (2 ** self.parse_retry_count)
                            logger.warning(f"[parse_react_response] 429限流, 等待{_retry_delay:.0f}s后重试 (第{self.parse_retry_count+1}次)")
                            import asyncio as _asyncio
                            await _asyncio.sleep(_retry_delay)
                        net_error_data = create_incident_data(
                            incident_value="rate_limit",
                            message=f"API暂时不可用，正在重试（第{self.parse_retry_count + 1}次）",
                            step=step_count
                        )
                        yield net_error_data
                    
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
                
                # flush chunk_buffer到正式会话历史（工具执行前保存LLM已输出的文本）
                if chunk_buffer:
                    self.temp_history.clear()
                    self.message_builder.add_assistant(chunk_buffer)
                    chunk_buffer = ""
                    consecutive_chunk_count = 0

                # 【步骤2.9】使用StepFactory创建ThoughtStep
                # 【修复 2026-05-05 小沈】thought去重拼接：thought和thought_content相同则不拼
                _thought_val = thought_content
                if thought and thought.strip():
                    _thought_val = thought if thought == thought_content else (thought + "\n" + thought_content).strip()
                thought_step = StepFactory.create_thought_step(
                    step=step_count,
                    content="",
                    tool_name=tool_name,
                    tool_params=tool_params,
                    thought=_thought_val,
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
                
                # 【方案B 小沈 2026-05-15】缓存检查 + 【方案A 小沈 2026-05-15】失败拦截
                execution_result, observation_prefix, cache_hit, fail_count = self.message_builder.check_cache_or_block(
                    tool_name, tool_params)
                execution_time_ms = 0
                
                if cache_hit:
                    consecutive_cache_hit_count += 1
                    logger.warning(f"[CacheHitLoop] 连续缓存命中 {consecutive_cache_hit_count} 次, tool={tool_name}")
                    if consecutive_cache_hit_count >= MAX_CONSECUTIVE_CACHE_HIT:
                        logger.warning(f"[CacheHitLoop] 连续缓存命中达 {MAX_CONSECUTIVE_CACHE_HIT} 次，强制finish打断死循环")
                        final_step = StepFactory.create_final_step(
                            step=step_count,
                            response=f"工具 {tool_name} 已成功执行，结果已在上方。无需重复调用。",
                            thought="检测到重复调用同一工具，自动结束任务"
                        )
                        self.steps.append(final_step)
                        yield final_step.to_dict()
                        self._on_after_loop()
                        return
                else:
                    consecutive_cache_hit_count = 0
                
                if execution_result is None and not cache_hit and fail_count < 3:
                    # 【Phase 1修复 小健 2026-05-14】函数内import避免触发register
                    from app.services.context_vars import _current_task_id
                    _current_task_id.set(task_id)
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
                _status = extract_status(execution_result)
                exec_status = _status
                execution_result_dict = {
                    "status": _status,
                    "summary": execution_result.get("message", ""),
                    "data": execution_result.get("data"),
                    "retry_count": execution_result.get("retry_count", 0),
                    "code": execution_result.get("code", "SUCCESS"),
                    "warning": execution_result.get("warning"),
                    "attachment": execution_result.get("attachment"),
                    "next_actions": execution_result.get("next_actions"),
                    "return_direct": execution_result.get("return_direct", False),
                    "error_message": execution_result.get("error_message", ""),
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
                self.message_builder.add_assistant(response)
                
                # ========== Observation 阶段（主工具的结果）==========
                observation_text = self.message_builder.build_observation_text(execution_result)
                
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

                # 【方案B 小沈 2026-05-15】缓存命中前缀
                if observation_prefix:
                    observation_text = observation_prefix + observation_text
                # 【方案A 小沈 2026-05-15】失败计数+已执行汇总更新
                fail_warning = self.message_builder.update_execution_cache(
                    tool_name, tool_params, execution_result, exec_status)
                if fail_warning:
                    observation_text += fail_warning
                
                logger.info(f"[Debug] observation加入history: {observation_text[:100]}...")
                self.message_builder.add_observation(observation_text, self.llm_call_count)

                # 记录观察结果到prompt日志
                prompt_logger = get_prompt_logger()
                prompt_logger.log_observation(
                    step_name="工具执行结果",
                    observation_content=observation_text,
                    tool_name=tool_name,
                    tool_params=tool_params,
                    round_number=self.llm_call_count
                )

                # ===== 【步骤2.9】yield observation =====
                # 【改进2 2026-05-01】给前端通道也附加质量警告
                display_summary = execution_result.get('message', '')
                if tool_name == "write_file" and exec_status == 'success':
                    data_dict = execution_result.get('data', {}) or {}
                    quality_warning = self._check_write_content_quality(tool_params, data_dict)
                    if quality_warning:
                        display_summary += f"\n⚠️ {quality_warning}"

                # 使用带警告的display_result创建ObservationStep（给前端）
                display_result = dict(execution_result)
                display_result['summary'] = display_summary
                display_result.setdefault('error_message', '')

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
                
                # 【步骤9】检查是否需要动态加载新工具
                # 在Observation之后、下一轮LLM调用前检查
                # observation_text 是行712-744构建的observation内容
                await self._check_and_load_missing_tools(observation_text, self.llm_client)
                
                # 【步骤3.6】核心设计: observation_step.is_done() 决定是否直接结束任务
                if observation_step.is_done():
                    _result_data = execution_result.get("data")
                    try:
                        _response_text = json.dumps(_result_data, ensure_ascii=False) if _result_data is not None else ""
                    except (TypeError, ValueError):
                        _response_text = str(_result_data)
                    _msg = execution_result.get("message", "")
                    if _msg:
                        _response_text = _msg + "\n" + _response_text
                    final_step = StepFactory.create_final_step(
                        step=step_count,
                        response=_response_text,
                        thought="工具执行要求直接返回结果",
                        model=getattr(self, 'model', None),
                        provider=getattr(self, 'provider', None)
                    )
                    self.steps.append(final_step)
                    yield final_step.to_dict()
                    self._on_after_loop()
                    return

                self.message_builder.trim_history()
                
                # 【2026-05-14 小沈】在主干工具完成后再执行并行工具调用（成对显示）
                pending_calls = parsed.get("_pending_calls", [])
                if pending_calls:
                    logger.info(f"[ReAct] 主工具完成，继续执行 {len(pending_calls)} 个并行工具")
                for pending in pending_calls:
                    # 【修复 U9 小沈 2026-05-15】并行工具step_count递增
                    step_count += 1
                    p_name = pending.get("name", "finish")
                    p_params = pending.get("args", {})
                    logger.info(f"[ReAct] 执行并行工具: {p_name}")
                    # 【修复 小沈 2026-05-15】删除冗余[系统记录: 并行执行]消息，并行标记合并到observation
                    start_p = time.perf_counter()
                    p_result = await self._execute_tool(p_name, p_params)
                    p_time = int((time.perf_counter() - start_p) * 1000)
                    
                    _p_code = p_result.get("code", "SUCCESS")
                    p_result_dict = {
                        "status": "success" if _p_code == "SUCCESS" and not p_result.get("warning") else ("warning" if _p_code.startswith("WARNING_") or p_result.get("warning") else "error"),
                        "summary": p_result.get("message", ""),
                        "data": p_result.get("data"),
                        "retry_count": p_result.get("retry_count", 0),
                        "code": _p_code,
                        "warning": p_result.get("warning"),
                        "attachment": p_result.get("attachment"),
                        "next_actions": p_result.get("next_actions"),
                        "return_direct": p_result.get("return_direct", False),
                        "error_message": p_result.get("error_message", ""),
                    }
                    
                    # action_tool + observation 成对yield
                    p_action_step = StepFactory.create_action_tool_step(
                        step=step_count, tool_name=p_name, tool_params=p_params,
                        execution_result=p_result_dict,
                        execution_time_ms=p_time
                    )
                    self.steps.append(p_action_step)
                    yield p_action_step.to_dict()
                    
                    p_obs_step = StepFactory.create_observation_step(
                        step=step_count, tool_name=p_name, tool_params=p_params,
                        execution_result=p_result_dict,
                        return_direct=False
                    )
                    self.steps.append(p_obs_step)
                    yield p_obs_step.to_dict()
                    # 并行工具observation — 小沈 2026-05-21 统一使用message_builder
                    p_obs_text = self.message_builder.build_observation_text(p_result)
                    self.message_builder.add_observation(f"[并行] {p_obs_text}", self.llm_call_count)
                    # 【修复 问题4 小沈 2026-05-15】并行工具也更新缓存和失败计数
                    p_code = p_result.get("code", "SUCCESS")
                    p_status = "success" if p_code == "SUCCESS" else "error"
                    self.message_builder.update_execution_cache(p_name, p_params, p_result, p_status)
                    # 【修复 2026-05-15 小健】并行工具也记录到prompt日志
                    try:
                        _p_logger = get_prompt_logger()
                        _p_logger.log_observation(
                            step_name="工具执行结果",
                            observation_content=p_obs_text,
                            tool_name=p_name,
                            tool_params=p_params,
                            round_number=self.llm_call_count
                        )
                    except Exception:
                        pass
        
        except Exception as e:
            # ===== 【步骤2.9+2.11】场景1：未捕获异常 =====
            # 【步骤2.11】废弃create_error_from_exception，使用StepFactory.create_error_step
            import traceback; traceback.print_exc()
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

    MAX_CONTEXT_CHARS = 150000  # 统一上下文+单条observation预算上限 小沈-2026-05-15
    # 【2026-05-21 小沈】_trim_history及6个辅助方法已迁入MessageBuilder，此处删除

    def _build_alternative_tools_hint(self, failed_tool: str, tool_params: Optional[dict] = None) -> str:
        """工具执行失败时，从当前Agent已注册工具中动态生成替代建议 - 小沈 2026-05-14
        【更新 2026-05-15 小健】http_request失败时提示国内替代URL；tools策略下精简提示
        
        Args:
            failed_tool: 失败的工具名称
            tool_params: 失败时的工具参数（用于提取URL等上下文）
            
        Returns:
            替代建议文本
        """
        # 【2026-05-15 小健】http_request失败时，提示国内替代URL
        if failed_tool == "http_request" and tool_params:
            failed_url = tool_params.get("url", "")
            hint = "⚠️ 网络请求失败。如果是访问国外服务超时，请换用国内可达的替代地址：\n"
            hint += "  - 查公网IP → 用 https://httpbin.org/ip 或 https://myip.ipip.net\n"
            hint += "  - 查IP详情 → 用 https://ipapi.co/json/ 或 https://ip.sb/api/\n"
            hint += "  - DNS查询 → 用 https://dns.alidns.com/resolve?name=域名&type=A\n"
            hint += "  - 网络连通 → 用 ping 测试国内域名(如 baidu.com)\n"
            hint += f"  失败URL: {failed_url}\n"
            hint += "请勿重复请求同一失败URL！"
            return hint
        
        if not hasattr(self, '_tools_dict') or not self._tools_dict:
            return ""
        
        # 【2026-05-15 小健】tools策略下LLM已有tools定义，只做精简提示
        strategy_method = getattr(self, '_last_strategy_method', None)
        if strategy_method == "tools":
            return "⚠️ 工具执行失败，请尝试其他可用工具，不要重复调用同一失败操作。"
        
        alternatives = []
        for name in self._tools_dict:
            if name == failed_tool or name in ("finish",):
                continue
            try:
                from app.services.tools.registry import tool_registry
                meta = tool_registry.get_tool(name)
                desc = meta.description[:40] if meta and meta.description else name
            except Exception:
                desc = name
            alternatives.append(f"{name}({desc})")
        
        if not alternatives:
            return ""
        
        listed = ", ".join(alternatives[:3])
        remaining = len(alternatives) - 3
        hint = f"其他可用工具: {listed}"
        if remaining > 0:
            hint += f" 等{len(alternatives)}个"
        return hint

    # ===== 通用方法 =====

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
            from app.services.tools.toolhelper.content_quality import check_content_quality
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
