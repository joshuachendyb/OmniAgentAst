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
from app.constants import MAX_CONTEXT_CHARS
# 【修复 小健 2026-05-24】P2-1: 删除重复导入AgentStatus
from app.services.preprocessing.intent_classifier import IntentClassifier  # 【步骤9】意图分类器
from app.utils.logger import logger
from app.chat_stream.chat_helpers import create_timestamp
from app.chat_stream.incident_handler import create_incident_data
from app.utils.prompt_logger import get_prompt_logger
from app.services.agent.tool_result_formatter import extract_status, build_execution_result_dict
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
        
        # 【修复 小健 2026-05-24】P2-8: _load_tools移到子类_init_tools_and_executor统一调用，避免重复初始化
        self._tools_dict = {}
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

        # 【2026-05-21 小沈】统一使用message_builder.invalidate_cache()清除全部缓存
        self.message_builder.invalidate_cache()
        # 【修复 小健 2026-05-24】P2-9: 用try/except替代hasattr+delattr，消除TOCTOU风险
        for _attr in ('_cached_schema_text', '_cached_tools_content', '_last_injected_categories'):
            try:
                delattr(self, _attr)
            except AttributeError:
                pass

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
        running_tasks: Optional[Dict[str, Any]] = None,
        step_counter: Optional[Callable[[], int]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        ReAct 核心循环
        
        每次循环包含 3 个阶段：
        1. Thought - LLM 生成思考和动作
        2. Action - 执行工具
        3. Observation - LLM 根据结果更新思考
        
        循环内分支（按处理顺序）：
        1. 最大步数检查 → 退出
        2. 中断检查 → 退出
        3. LLM调用 + 返回后中断检查 → 退出
        4. 空响应 → 截断历史重试 / 退出
        5. 解析响应 → 按type分支：
           - chunk → 无工具Agent退出 / 阈值退出 / continue
           - answer/implicit → 正常完成退出
           - thought_only → continue
           - parse_error → 重试 / 退出
           - action → 工具执行(Thought→Action→Observation) → 退出或继续
        6. 未捕获异常(except) → 退出
        """
        # 初始化状态
        self.steps = []
        self.message_builder.reset_per_run()
        # conversation_history是message_builder.conversation_history的引用别名
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
        # 缓存有效工具名集合（每次循环复用，避免重复获取）
        _valid_tool_names = {"finish"}
        try:
            from app.services.tools.registry import tool_registry
            _valid_tool_names = {t["name"] for t in tool_registry.list_tools()} | {"finish"}
        except Exception as _e:
            logger.debug(f"[工具名验证] 获取工具列表失败: {_e}, 仅允许finish")
        # 超时机制
        # ===== 场景1：未捕获异常 (try...except包裹整个循环) =====
        try:
            while True:
                # ===== 场景3：每次循环开始检查最大步数 =====
                if step_count >= max_steps:
                    yield self._exit_with_error(step_count, "max_steps_exceeded", f"已达到最大迭代次数 {max_steps}")
                    self._on_after_loop()
                    return

                step_count = step_counter() if step_counter else (step_count + 1)
                
                # =====【中断检查】每次循环开始检查任务是否被取消 - 小欧-2026-04-21 =====
                _int = self._check_interrupt(step_count, running_tasks)
                if _int:
                    # 【时间测量】计算取消延迟
                    if task_id and running_tasks:
                        _crt = running_tasks.get(task_id, {}).get("cancel_request_time")
                        if _crt:
                            logger.info(f"[InterruptCheck] 任务 {task_id} 延迟: {(time.time() - _crt) * 1000:.0f}ms")
                    logger.info(f"[Interrupt] 任务 {task_id} 被取消，发送 interrupted 事件")
                    yield _int
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
                _int = self._check_interrupt(step_count, running_tasks)
                if _int:
                    logger.info(f"[Interrupt] 任务 {task_id} LLM返回后被取消，立即中断")
                    yield _int
                    self._on_after_loop()
                    return
                
                # ===== 场景2：LLM返回空响应 =====
                if not response:
                    self.empty_response_retry_count += 1
                    # 【修复 小健 2026-05-24】P2-10: 空响应重试时重置parse_retry_count
                    self.parse_retry_count = 0
                    logger.error(
                        f"[空响应] LLM返回空响应 (第{self.empty_response_retry_count}次重试), "
                        f"history长度={len(self.conversation_history)}"
                    )
                    
                    if self.empty_response_retry_count <= self.max_empty_response_retries:
                        # 【修复 2026-05-05 小沈】截断历史重试
                        original_len = len(self.conversation_history)
                        # 【修复 小健 2026-05-24】P1-2: [:2]+[-2:]在短列表时产生重复条目
                        if original_len > 4:
                            kept_head = self.conversation_history[:2]
                            kept_tail = self.conversation_history[-2:]
                            kept = kept_head + kept_tail
                            seen_ids = set()
                            deduped = []
                            for item in kept:
                                item_id = id(item)
                                if item_id not in seen_ids:
                                    seen_ids.add(item_id)
                                    deduped.append(item)
                            kept = deduped
                            removed_len = original_len - len(kept)
                            self.conversation_history = kept
                            # 【修复 小健 2026-05-24】同步message_builder引用，避免断裂
                            self.message_builder.conversation_history = kept
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
                    yield self._exit_with_error(step_count, "empty_response", f"AI服务返回空响应（已重试{self.empty_response_retry_count}次）")
                    self._on_after_loop()
                    return
                
                # ===== 场景4：解析响应并获取结果 =====  # 修复 2026-04-15 小沈
                parsed = parse_react_response(response)
                
                # 【修复 2026-05-05 小沈】成功获取响应，重置空响应计数器
                self.empty_response_retry_count = 0
                
                # ===== 先获取 parsed 结果 =====
                thought_content = parsed.get("content", "")
                tool_name = parsed.get("tool_name") or parsed.get("action_tool") or "finish"
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
                    yield self._emit_step(chunk_step)
                    
                    # 无工具Agent（chat）：第一个chunk直接作为最终回答，不循环
                    if self.tool_category is None:
                        logger.info(f"[ReAct] 无工具Agent，第一个chunk即为最终回答，退出循环")
                        self.message_builder.temp_history.clear()
                        if chunk_buffer:
                            self.message_builder.add_assistant(chunk_buffer)
                        # 【修复 小健 2026-05-24】P2-4: final步骤使用递增step_count
                        step_count = step_counter() if step_counter else (step_count + 1)
                        final_step = StepFactory.create_final_step(
                            step=step_count, response=chunk_buffer, thought=""
                        )
                        yield self._emit_step(final_step)
                        self._on_after_loop()
                        return
                    
                    # 工具Agent：连续chunk达阈值→提升为implicit退出循环
                    # 阈值意义：连续N次chunk（无tool_call），说明LLM在重复生成，应结束
                    if consecutive_chunk_count >= self.max_consecutive_chunks:
                        logger.info(f"[ReAct] 连续chunk达到{self.max_consecutive_chunks}次，提升为implicit")
                        self.message_builder.temp_history.clear()
                        if chunk_buffer:
                            self.message_builder.add_assistant(chunk_buffer)
                        final_step = StepFactory.create_final_step(
                            step=step_count, response=chunk_buffer, thought=""
                        )
                        yield self._emit_step(final_step)
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
                        self.message_builder.temp_history.clear()
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
                    yield self._emit_step(final_step)
                    
                    # 【修复 小健 2026-05-24】P1-3: 正常完成设置COMPLETED
                    self.status = AgentStatus.COMPLETED
                    self._on_after_loop()
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
                    
                    yield self._emit_step(thought_step)
                    
                    # 【修复 小健 2026-05-24】P2-3: 注入结构化thought而非原始LLM文本
                    self.message_builder.add_assistant(_thought_val)
                    
                    # 【修复D2】调用message_builder.trim_history防止历史无限增长
                    self.message_builder.trim_history()
                    
                    # 【修复 小沈 2026-05-24】thought_only后重置chunk计数，防止跨轮次累加
                    consecutive_chunk_count = 0
                    chunk_buffer = ""
                    
                    continue  # 继续下一轮循环
                
                # ===== 无效工具名保护：type=action但tool_name无效时转为parse_error =====
                # 【修复 小健 2026-05-24】空工具名保护
                # 【修复 小健 2026-05-24】Bug#9: ToolRegistry无instance()方法，需用模块级tool_registry变量
                if parsed["type"] != "parse_error":
                    if not tool_name or tool_name not in _valid_tool_names:
                        logger.warning(f"[parse_react_response] 空工具名或无效工具名: tool_name={tool_name!r}, parsed_type={parsed['type']}, 转为parse_error")
                        parsed = {"type": "parse_error", "error": f"LLM返回无效工具名: {tool_name!r}"}
                
                # ===== 检查解析是否失败 =====
                # 不再依赖 "⚠️" 符号，改用显式的 type="parse_error" 判断
                # parse_error表示解析失败，需要重试；error表示真实运行错误
                # （也处理上方无效工具名转来的parse_error）
                if parsed["type"] == "parse_error":
                    error_msg = parsed.get("error", "Unknown parse error")
                    logger.warning(f"[parse_react_response] 情况4: 解析错误: {error_msg}, 重试次数={self.parse_retry_count}")
                    
                    # 【修复 小健 2026-05-16】网络/API错误不注入history，只有LLM格式错误才注入
                    from app.chat_stream.error_handler import is_network_or_api_error
                    is_network_error, _error_type = is_network_or_api_error(error_msg)
                    
                    if not is_network_error:
                        # LLM格式错误：添加提示到历史，引导LLM修复
                        self.message_builder.add_observation(f"Parse Error: {error_msg}. Please ensure your response follows the ReAct format (Thought -> Action -> Action Input).")
                    else:
                        # 网络/API错误：不注入history，给前端提示，直接重试
                        logger.info(f"[parse_react_response] 网络/API错误，不注入history: {error_msg}")
                        # 【修复 小健 2026-05-21】429等网络错误添加指数退避等待
                        if _error_type == "api_error_429":
                            _retry_delay = 2.0 * (2 ** self.parse_retry_count)
                            logger.warning(f"[parse_react_response] 429限流, 等待{_retry_delay:.0f}s后重试 (第{self.parse_retry_count+1}次)")
                            await asyncio.sleep(_retry_delay)
                        yield create_incident_data(
                            incident_value="rate_limit",
                            message=f"API暂时不可用，正在重试（第{self.parse_retry_count + 1}次）",
                            step=step_count
                        )
                    
                    # 重试计数器+1
                    self.parse_retry_count += 1
                    
                    # 【步骤3.3】重试次数 >= 3？直接ErrorStep→return
                    if self.parse_retry_count >= self.max_parse_retries:
                        yield self._exit_with_error(step_count, "parse_error", f"解析失败: {error_msg}（已重试{self.max_parse_retries}次）")
                        self._on_after_loop()
                        return
                    # 【问题3修复】重试前发送retrying事件，让前端显示重试提示
                    retrying_data = create_incident_data(
                        incident_value="retrying",
                        message=f"解析失败，正在重试（第{self.parse_retry_count}次）",
                        step=step_count
                    )
                    yield retrying_data
                    # 【修复 小沈 2026-05-24】parse_error后重置chunk计数，防止跨轮次累加
                    consecutive_chunk_count = 0
                    chunk_buffer = ""
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
                chunk_buffer_was_flushed = bool(chunk_buffer)
                if chunk_buffer:
                    self.message_builder.temp_history.clear()
                    self.message_builder.add_assistant(chunk_buffer)
                    chunk_buffer = ""
                    consecutive_chunk_count = 0
                else:
                    chunk_buffer_was_flushed = False

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

                yield self._emit_step(thought_step)
                
                # 【修正 2026-04-17 小沈】删除：response 提前加入 conversation_history
                # 按照设计文档15.2.0.4，response 应该在 action_tool 之后才加入
                
                # ========== Action 阶段 ==========
                self.status = AgentStatus.EXECUTING
                
                # 【工具执行前中断检查】在执行工具前检查是否被中断
                _int = self._check_interrupt(step_count, running_tasks)
                if _int:
                    logger.info(f"[Interrupt] 任务 {task_id} 被取消，工具执行前中断")
                    yield _int
                    self._on_after_loop()
                    return
                
                # 使用 perf_counter 计算工具执行耗时（高精度）
                start_time = time.perf_counter()
                logger.info(f"[DEBUG_TOOL_PARAMS] before execute_tool: tool_name={tool_name}, tool_params={tool_params}")
                
                execution_time_ms = 0
                from app.services.context_vars import _current_task_id
                # 【修复 小健 2026-05-24】P2-6: task_id可能为None，设为空字符串避免ContextVar存None
                _current_task_id.set(task_id or "")
                execution_result = await self._execute_tool(tool_name, tool_params)
                if execution_result is None:
                    execution_result = {"code": -1, "message": f"工具 {tool_name} 返回None", "data": None}
                    logger.warning(f"[execute_tool] _execute_tool返回None: tool_name={tool_name}")
                execution_time_ms = int((time.perf_counter() - start_time) * 1000)
                
                # 【工具执行后中断检查】在执行工具后检查是否被中断
                _int = self._check_interrupt(step_count, running_tasks)
                if _int:
                    logger.info(f"[Interrupt] 任务 {task_id} 被取消，工具执行后中断")
                    yield _int
                    self._on_after_loop()
                    return
                
                # 【步骤2.9】根据执行结果构建 action_tool
                
                # 【步骤2.9】统一执行结果字典格式（供StepFactory使用）
                execution_result_dict = build_execution_result_dict(execution_result)
                exec_status = execution_result_dict["status"]

                # 【步骤2.9】使用StepFactory创建ActionToolStep
                action_step = StepFactory.create_action_tool_step(
                    step=step_count,
                    tool_name=tool_name,
                    tool_params=tool_params,
                    execution_result=execution_result_dict,
                    execution_time_ms=execution_time_ms
                )

                yield self._emit_step(action_step)
                
                # 【修正 2026-04-17 小沈】按照设计文档15.2.0.4执行顺序
                # 步骤5：response 应该在 action_tool 之后再加入 conversation_history
                # 【修复 小健 2026-05-24】P1-1: chunk_buffer已在行712-716 flush到历史，
                # 此处再add_assistant(response)会重复注入chunk内容，跳过
                # 对于无chunk的场景(parsed直接是action)，response未被注入，需要注入
                if not chunk_buffer_was_flushed:
                    self.message_builder.add_assistant(response)
                
                # ========== Observation 阶段（主工具的结果）==========
                # 【修复 小健 2026-05-24】P1-3: 补全AgentStatus状态机
                self.status = AgentStatus.OBSERVING
                observation_text = self.message_builder.build_observation_text(execution_result, tool_name=tool_name, tool_params=tool_params)
                
                logger.info(f"[Debug] observation加入history: {observation_text[:100]}...")
                # FC协议注入：tools策略下用assistant(tool_calls)+tool(tool_call_id)，text策略用role:system
                fc_context = None
                if getattr(self, '_strategy', None) == "tools":
                    _chat_response = getattr(self, '_last_fc_raw_response', None)
                    if _chat_response and getattr(_chat_response, 'tool_calls', None):
                        tc = _chat_response.tool_calls[0]
                        # 【修复 小健 2026-05-24】P2-7: tc可能是pydantic model，无.get()方法
                        _tc_id = getattr(tc, 'id', None) or (tc.get("id", "") if isinstance(tc, dict) else "")
                        fc_context = {"tool_calls": _chat_response.tool_calls, "tool_call_id": _tc_id}
                self.message_builder.add_observation(observation_text, self.llm_call_count, fc_context=fc_context)

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
                # 【修复 小健 2026-05-24】P1-4: 统一前端yield和steps记录使用同一份execution_result
                display_summary = execution_result.get('message', '')
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

                yield self._emit_step(observation_step)
                
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
                    yield self._emit_step(final_step)
                    # 【修复 小健 2026-05-24】P1-3: return_direct完成设置COMPLETED
                    self.status = AgentStatus.COMPLETED
                    self._on_after_loop()
                    return

                self.message_builder.trim_history()
                
                # 【2026-05-14 小沈】在主干工具完成后再执行并行工具调用（成对显示）
                pending_calls = parsed.get("_pending_calls", [])
                if pending_calls:
                    logger.info(f"[ReAct] 主工具完成，继续执行 {len(pending_calls)} 个并行工具")
                async for _pd in self._execute_pending_calls(
                    pending_calls, step_count, running_tasks, task_id
                ):
                    yield _pd
        
        except Exception as e:
            # ===== 【步骤2.9+2.11】场景1：未捕获异常 =====
            # 【步骤2.11】废弃create_error_from_exception，使用StepFactory.create_error_step
            # 【修复 小健 2026-05-24】P1-3: 异常退出设置FAILED
            # 【修复 小健 2026-05-24】P2-5: 异常退出清理temp_history
            self.message_builder.temp_history.clear()
            import traceback; traceback.print_exc()
            logger.error(f"Agent run_stream error: {e}", exc_info=True)
            
            yield self._exit_with_error(step_count, "unhandled_exception", str(e))
            
            self._on_after_loop()
            return
    
    # ===== 对话历史管理 =====

    MAX_CONTEXT_CHARS = MAX_CONTEXT_CHARS  # from app.constants — 小健 2026-05-24

    # ===== 通用方法 =====

    def _emit_step(self, step) -> dict:
        """记录步骤并返回yield用的dict — 小健 2026-05-24
        
        统一 self.steps.append(step) + step.to_dict() 两步操作。
        调用方: step_dict = self._emit_step(step); yield step_dict
        """
        self.steps.append(step)
        return step.to_dict()

    def _exit_with_error(self, step_count: int, error_type: str, error_message: str, recoverable: bool = False) -> dict:
        """创建error_step并返回yield用的dict，同时设置FAILED状态 — 小健 2026-05-24
        
        统一 error_step创建 + append + status设置。
        调用方: yield self._exit_with_error(...); self._on_after_loop(); return
        """
        self.status = AgentStatus.FAILED
        error_step = StepFactory.create_error_step(
            step=step_count,
            error_type=error_type,
            error_message=error_message,
            recoverable=recoverable
        )
        return self._emit_step(error_step)

    def _check_interrupt(self, step_count: int, running_tasks: Optional[Dict[str, Any]] = None) -> Optional[dict]:
        """检查任务是否被中断，若中断返回interrupted_data的dict — 小健 2026-05-24
        
        统一4处中断检查逻辑。直接读取cancelled标志（非线程安全但可接受，
        因为只是检查布尔值，与loop中现有模式一致）。
        调用方: _int = self._check_interrupt(step_count, running_tasks); 
               if _int: yield _int; self._on_after_loop(); return
        """
        task_id = getattr(self, '_task_id', None) or getattr(self, 'task_id', None)
        if not task_id or not running_tasks:
            return None
        task_data = running_tasks.get(task_id, {})
        if task_data.get("cancelled", False):
            return create_incident_data(
                incident_value='interrupted',
                message='用户取消了任务',
                step=step_count
            )
        return None

    async def _execute_pending_calls(
        self,
        pending_calls: List[Dict[str, Any]],
        step_count: int,
        running_tasks: Optional[Dict[str, Any]],
        task_id: Optional[str]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """执行并行工具调用列表 — 小健 2026-05-24
        
        在主工具Observation完成后执行附带的pending_calls。
        每个调用产出action_tool+observation两个步骤。
        被中断时提前终止（break），不抛异常。
        """
        for pending in pending_calls:
            step_count += 1
            p_name = pending.get("name", "finish")
            p_params = pending.get("args", {})
            logger.info(f"[ReAct] 执行并行工具: {p_name}")
            
            if self._check_interrupt(step_count, running_tasks):
                logger.info(f"[Interrupt] 任务 {task_id} 在并行工具执行前被取消")
                break
            
            try:
                start_p = time.perf_counter()
                p_result = await self._execute_tool(p_name, p_params)
                if p_result is None:
                    p_result = {"code": -1, "message": f"并行工具 {p_name} 返回None", "data": None}
                p_time = int((time.perf_counter() - start_p) * 1000)
                
                p_result_dict = build_execution_result_dict(p_result)
                
                p_action_step = StepFactory.create_action_tool_step(
                    step=step_count, tool_name=p_name, tool_params=p_params,
                    execution_result=p_result_dict,
                    execution_time_ms=p_time
                )
                yield self._emit_step(p_action_step)
                
                p_obs_step = StepFactory.create_observation_step(
                    step=step_count, tool_name=p_name, tool_params=p_params,
                    execution_result=p_result_dict,
                    return_direct=False
                )
                yield self._emit_step(p_obs_step)
                
                p_obs_text = self.message_builder.build_observation_text(p_result, tool_name=p_name, tool_params=p_params)
                _fc_handled = False
                if getattr(self, '_strategy', None) == "tools":
                    _fc_resp = getattr(self, '_last_fc_raw_response', None)
                    if _fc_resp and getattr(_fc_resp, 'tool_calls', None):
                        _p_tc_id = None
                        for _tc in _fc_resp.tool_calls:
                            _fn_name = getattr(_tc, 'function', None)
                            if _fn_name and getattr(_fn_name, 'name', '') == p_name:
                                _p_tc_id = getattr(_tc, 'id', '')
                                break
                            elif isinstance(_tc, dict) and _tc.get("function", {}).get("name", "") == p_name:
                                _p_tc_id = _tc.get("id", "")
                                break
                        if _p_tc_id:
                            _budget = self.message_builder._get_observation_budget(self.llm_call_count)
                            _text = p_obs_text
                            if len(_text) > _budget:
                                _text = self.message_builder._smart_truncate(_text, budget=_budget)
                            _text = self.message_builder._normalize_observation_prefix(_text)
                            self.message_builder.conversation_history.append({
                                "role": "tool", "content": _text,
                                "tool_call_id": _p_tc_id
                            })
                            self.message_builder.trim_history()
                            _fc_handled = True
                if not _fc_handled:
                    self.message_builder.add_observation(f"[并行] {p_obs_text}", self.llm_call_count)
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
            except Exception as _p_err:
                logger.warning(f"[ReAct] 并行工具 {p_name} 执行异常: {_p_err}")
                _p_err_dict = {"status": "error", "summary": str(_p_err), "data": None, "code": -1,
                               "retry_count": 0, "warning": None, "attachment": None,
                               "next_actions": None, "return_direct": False, "error_message": str(_p_err)}
                p_action_step = StepFactory.create_action_tool_step(
                    step=step_count, tool_name=p_name, tool_params=p_params,
                    execution_result=_p_err_dict, execution_time_ms=0
                )
                yield self._emit_step(p_action_step)
                p_obs_step = StepFactory.create_observation_step(
                    step=step_count, tool_name=p_name, tool_params=p_params,
                    execution_result=_p_err_dict, return_direct=False
                )
                yield self._emit_step(p_obs_step)


