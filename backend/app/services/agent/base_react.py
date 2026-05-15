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
from app.services.agent.types import AgentStatus
from app.services.preprocessing.intent_classifier import IntentClassifier  # 【步骤9】意图分类器
from app.utils.logger import logger
from app.chat_stream.chat_helpers import create_timestamp
from app.chat_stream.incident_handler import create_incident_data
from app.utils.prompt_logger import get_prompt_logger
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
        self.conversation_history: List[Dict[str, str]] = []
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
        self._loaded_categories.add("support_tool")
        
        from app.services.preprocessing.intent_classifier import IntentClassifier
        self._intent_classifier = IntentClassifier()
        
        # 【v2.3新增】chunk处理相关属性—所有Agent子类共享
        self.max_consecutive_chunks = MAX_CONSECUTIVE_CHUNKS  # 连续chunk达此阈值时提升为implicit
        self.temp_history: List[Dict[str, str]] = []  # 临时历史，用于chunk过程中LLM参考
        
        # 创建工具执行器
        self.executor = None  # 子类应初始化
    
    def _load_tools(self) -> Dict[str, Callable]:
        """
        从registry加载工具
        参考: 7.5节行1082-1088
        """
        if not self.tool_category:
            return {}
        
        # 【Phase 1修复 小健 2026-05-14】按当前分类注册，而非全量注册
        from app.services.tools import ensure_tools_registered
        if self.tool_category:
            ensure_tools_registered(categories=[self.tool_category.value, "support_tool"])
        else:
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
            intent_type: 意图类型（file/time/shell/network等）
            reason: 加载原因（用于日志）
        """
        if intent_type in self._loaded_categories:
            return  # 已加载
        
        logger.info(f"[动态加载] 原因: {reason}，加载意图: {intent_type}")
        
        # 1. 获取该意图的工具（所有工具已全量注册）
        try:
            category = ToolCategory(intent_type)
            new_tools = get_tools_from_registry_by_category(category)
        except ValueError as e:
            logger.warning(f"[动态加载] 意图'{intent_type}'无对应工具分类: {e}")
            return
        
        # 2. 添加到_tools_dict
        self._tools_dict.update(new_tools)
        self._loaded_categories.add(intent_type)

        # 【Phase 1 小健 2026-05-14】动态加载后注入提示到conversation_history
        # 让LLM知道新工具已可用，下一轮的_call_llm_with_summary分级注入会自动
        # 包含新分类的detail（因为_get_tools_detail按_loaded_categories输出）
        new_tool_names = sorted(new_tools.keys())
        load_hint = f"【动态加载】已加载{intent_type}分类的{len(new_tool_names)}个工具: {', '.join(new_tool_names)}"
        self.conversation_history.append({"role": "system", "content": load_hint})
        logger.info(f"[动态加载] 已注入LLM提示: {load_hint[:100]}")

        # 3. 刷新FC通道的tools定义（如果已启用）
        if hasattr(self, 'tools_strategy') and self.tools_strategy is not None:
            from app.services.tools.registry import tool_registry
            new_openai_tools = tool_registry.to_openai_tools(category=category)
            self.openai_tools.extend([t for t in new_openai_tools if t not in self.openai_tools])
            self.tools_strategy.tools = self.openai_tools
            logger.info(f"[FC刷新] tools定义已更新，当前{len(self.openai_tools)}个")

        logger.info(f"[动态加载] 完成，新增{len(new_tools)}个工具，总计{len(self._tools_dict)}个")
    
    async def _check_and_load_missing_tools(self, observation: str, llm_client=None):
        """
        在Observation阶段，检测是否需要新工具（改进版） - 小健 2026-05-14
        
        【Phase 1修复】优化检测策略：
        1. 先用关键词检测（快速、低成本）
        2. 关键词检测不确定时，再用LLM分类器（语义理解，补充）
        
        Args:
            observation: LLM返回的observation内容（工具执行结果）
            llm_client: LLM客户端（用于LLM分类器）
        """
        # 【Phase 1 小健 2026-05-14】关键词检测（主方案，快速）
        trigger_keywords = {
            "network": ["ping ", "http", "下载", "网络", "url", "curl", "wget", "公网IP", "DNS", "ipify"],
            "desktop": ["截图", "截屏", "窗口", "鼠标点击", "键盘输入", "UI", "GUI"],
            "shell": ["执行命令", "npm ", "pip ", "git ", "docker ", "nslookup", "shell", "命令行", "bash"],
            "database": ["数据库", "SQL", "查询", "SELECT", "INSERT", "sqlite", "mysql"],
            "environment": ["环境变量", "PATH", "JAVA_HOME", "PYTHONPATH", "Node"],
            "system": ["系统信息", "CPU", "内存", "磁盘", "进程", "systeminfo"],
            "file": ["文件", "目录", "读写", "copy", "move", "重命名"],
            "time": ["时间", "日期", "时区", "timezone"],
            "data_format": ["JSON", "CSV", "Excel", "格式转换", "解析", "序列化"],
            "code_execution": ["执行代码", "Python脚本", "运行代码", "代码执行"],
            "document": ["PDF", "Word", "文档读取", "文档生成", "Markdown"],
        }
        # 注意：support_tool（含finish）在初始化时已始终注册，无需触发关键词
        
        detected_intent = None
        for intent, keywords in trigger_keywords.items():
            if any(kw in observation for kw in keywords):
                # 否定词检测：避免"不要执行shell"误触发
                if self._should_trigger_dynamic_load(observation, intent):
                    detected_intent = intent
                    break  # 只取第一个匹配的
        
        # 如果关键词检测到，直接加载
        if detected_intent and detected_intent not in self._loaded_categories:
            self.load_tools_by_intent(
                detected_intent, 
                reason=f"关键词检测: {trigger_keywords[detected_intent]}"
            )
            return
        
        # 【Phase 1修复 小健 2026-05-14】关键词检测不确定时，用LLM分类器（补充）
        # LLM分类器能理解语义，比关键词更准确，但有延迟和成本
        if llm_client and self._intent_classifier and not detected_intent:
            try:
                from app.services.tools.registry import ToolCategory
                labels = [cat.value for cat in ToolCategory]
                
                result = await self._intent_classifier.classify(observation, labels)
                new_intent = result.get("intent")
                confidence = result.get("confidence", 0)
                
                # 置信度阈值：0.3，比初始阶段的0.5低，因为Observation可能模糊
                if (new_intent and new_intent not in self._loaded_categories 
                        and confidence >= 0.3):
                    # 否定词检测
                    if self._should_trigger_dynamic_load(observation, new_intent):
                        self.load_tools_by_intent(
                            new_intent, 
                            reason=f"LLM分类器检测: {new_intent}(置信度{confidence:.2f})"
                        )
            except Exception as e:
                logger.warning(f"[动态加载] LLM分类器失败: {e}")
    
    def _should_trigger_dynamic_load(self, observation: str, intent: str) -> bool:
        """
        判断是否应该触发动态加载（包含否定词检测）
        
        参考：文档4.14节步骤9缺陷7修正
        避免"不要执行shell"误触发
        
        Args:
            observation: LLM返回的observation内容
            intent: 检测的意图类型
        Returns:
            bool: 是否应该触发动态加载
        """
        # 否定词列表（表示否定的词语）
        negation_words = [
            "不要", "不需要", "别", "禁止", "不可以", "不能", 
            "don't", "donot", "cannot", "should not", "not to"
        ]
        
        # 检查observation中是否包含否定词
        has_negation = any(neg in observation.lower() for neg in negation_words)
        
        if has_negation:
            logger.info(f"[动态加载] 检测到否定词，不触发{intent}工具加载")
            return False
        
        return True
    
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
        # chunk处理相关变量
        chunk_buffer = ""
        consecutive_chunk_count = 0
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
                    self.temp_history.append({"role": "assistant", "content": chunk_content})
                    if len(self.temp_history) > 10:
                        self.temp_history = self.temp_history[-10:]
                    
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
                            self.conversation_history.append({"role": "assistant", "content": chunk_buffer})
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
                            self.conversation_history.append({"role": "assistant", "content": chunk_buffer})
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
                        self.conversation_history.append({"role": "assistant", "content": chunk_buffer})
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
                
                # flush chunk_buffer到正式会话历史（工具执行前保存LLM已输出的文本）
                if chunk_buffer:
                    self.temp_history.clear()
                    self.conversation_history.append({"role": "assistant", "content": chunk_buffer})
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
                # 【Phase 1修复 小健 2026-05-14】函数内import避免触发register
                from app.services.tools.file.file_tools import _current_task_id
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
                
                # ========== Observation 阶段（主工具的结果）==========
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
                    # 【修复 2026-05-14 小沈】失败时动态生成替代建议（从当前Agent已注册工具中找）
                    # 【更新 2026-05-15 小健】传入tool_params用于http_request的国内URL提示
                    alt_hint = self._build_alternative_tools_hint(tool_name, tool_params)
                    if alt_hint:
                        observation_text += f"\n{alt_hint}"
                
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
                    tool_params=tool_params,
                    round_number=self.llm_call_count
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
                
                # 【步骤9】检查是否需要动态加载新工具
                # 在Observation之后、下一轮LLM调用前检查
                # observation_text 是行712-744构建的observation内容
                await self._check_and_load_missing_tools(observation_text, self.llm_client)
                
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
                
                # 【2026-05-14 小沈】在主干工具完成后再执行并行工具调用（成对显示）
                pending_calls = parsed.get("_pending_calls", [])
                if pending_calls:
                    logger.info(f"[ReAct] 主工具完成，继续执行 {len(pending_calls)} 个并行工具")
                for pending in pending_calls:
                    p_name = pending.get("name", "finish")
                    p_params = pending.get("args", {})
                    logger.info(f"[ReAct] 执行并行工具: {p_name}")
                    start_p = time.perf_counter()
                    p_result = await self._execute_tool(p_name, p_params)
                    p_time = int((time.perf_counter() - start_p) * 1000)
                    
                    p_result_dict = {
                        "status": p_result.get("status", "success"),
                        "summary": p_result.get("summary", ""),
                        "data": p_result.get("data"),
                        "error": p_result.get("error", ""),
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
                    # 【修复 2026-05-15 小健】并行工具observation与主工具逻辑一致：success附data，error附替代建议
                    p_status = p_result.get('status', 'success')
                    if p_status == 'success':
                        p_obs_text = f"Observation: {p_status} - {p_result.get('summary', '')}"
                        if p_result.get('data'):
                            p_obs_text += f"\n实际数据: {p_result.get('data')}"
                    else:
                        p_obs_text = f"Observation: {p_status} - {p_result.get('summary', '')}"
                        p_alt_hint = self._build_alternative_tools_hint(p_name, p_params)
                        if p_alt_hint:
                            p_obs_text += f"\n{p_alt_hint}"
                    self._add_observation_to_history(p_obs_text)
                    # 【修复 2026-05-15 小健】并行工具也记录到prompt日志
                    try:
                        from app.utils.prompt_logger import get_prompt_logger
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

    def _build_alternative_tools_hint(self, failed_tool: str, tool_params: dict = None) -> str:
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

    # 【升级 2026-05-05 小沈】智能observation截断策略
    # 方案D: 首尾保留+智能摘要 + 动态递减预算
    CONTEXT_WINDOW_SIZE = 200000  # 上下文窗口大小（字符数，约200K tokens）
    OBSERVATION_BUDGET_INITIAL = 150000  # 第1轮observation最大长度
    OBSERVATION_BUDGET_DECAY = 10000  # 每增加1轮，预算减少10K
    OBSERVATION_BUDGET_MIN = 20000  # 最低预算，不低于20K
    OBSERVATION_HEAD_RATIO = 0.6  # 头部保留比例（60%给头部，40%给尾部）
    OBSERVATION_SUMMARY_THRESHOLD = 50000  # 超过此长度时启用智能摘要

    def _get_observation_budget(self) -> int:
        """根据当前轮数动态计算observation可用预算

        策略：初始150K，每轮递减10K，最低20K
        轮数越多，history越长，留给新observation的空间越小
        """
        budget = self.OBSERVATION_BUDGET_INITIAL - (self.llm_call_count * self.OBSERVATION_BUDGET_DECAY)
        budget = max(budget, self.OBSERVATION_BUDGET_MIN)
        return budget

    @staticmethod
    def _smart_truncate(content: str, budget: int, head_ratio: float = 0.6) -> str:
        """智能截断：首尾保留 + 中间摘要

        策略：
        1. 内容在预算内 → 原样返回
        2. 内容超预算但<摘要阈值 → 首部保留budget，末尾附截断提示
        3. 内容超摘要阈值 → 首部保留head_ratio*budget，
           尾部保留(1-head_ratio)*budget，中间替换为摘要

        Args:
            content: 原始内容
            budget: 本次允许的最大字符数
            head_ratio: 头部保留比例，默认0.6

        Returns:
            截断后的内容
        """
        original_len = len(content)

        if original_len <= budget:
            return content

        head_size = int(budget * head_ratio)
        tail_size = budget - head_size

        # 计算中间省略了多少
        middle_len = original_len - head_size - tail_size

        # 估算省略的行数
        head_part = content[:head_size]
        tail_part = content[-tail_size:]
        total_lines = content.count('\n') + 1
        head_lines = head_part.count('\n') + 1
        tail_lines = tail_part.count('\n') + 1
        omitted_lines = total_lines - head_lines - tail_lines

        # 构建摘要
        if omitted_lines > 0:
            summary = f"\n\n... [省略 {middle_len} 字符, 约 {omitted_lines} 行] ...\n\n"
        else:
            summary = f"\n\n... [省略 {middle_len} 字符] ...\n\n"

        truncated = head_part + summary + tail_part
        return truncated

    def _add_observation_to_history(self, observation: str) -> None:
        """添加观察结果到对话历史

        【升级 2026-05-05 小沈】智能截断策略：
        - 动态预算：第1轮150K，每轮递减10K，最低20K
        - 首尾保留：保留头部（结构/开头信息）+ 尾部（结果/错误信息）
        - 中间摘要：省略部分用字符数+行数摘要替代
        - 上下文保护：总observation不超过上下文窗口
        """
        budget = self._get_observation_budget()

        if len(observation) > budget:
            truncated = self._smart_truncate(
                observation,
                budget=budget,
                head_ratio=self.OBSERVATION_HEAD_RATIO
            )
            logger.warning(
                f"[智能截断] 轮数={self.llm_call_count}, "
                f"原始长度={len(observation)}, "
                f"预算={budget}, "
                f"截断后={len(truncated)}, "
                f"策略=首尾保留(头{int(self.OBSERVATION_HEAD_RATIO*100)}%+尾{int((1-self.OBSERVATION_HEAD_RATIO)*100)}%)"
            )
            observation = truncated
        else:
            logger.info(
                f"[observation] 轮数={self.llm_call_count}, "
                f"长度={len(observation)}, 预算={budget}, 无需截断"
            )
        self.conversation_history.append({"role": "system", "content": observation})  # 【修复 2026-05-13 小沈】M1: 工具执行结果用system角色，避免LLM误认为是用户新输入
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
