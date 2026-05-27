# -*- coding: utf-8 -*-
"""
ReAct Agent Step封装类模块

提供统一的Step类封装体系，解决现有系统的10个核心问题：
- S1: 无封装 - 所有步骤都是裸字典
- S2: 字段命名不统一
- S3: 构建入口分散在6处代码位置
- S4: 无类型注解
- S5: tool_name/tool_params重复
- S6: step字段缺失
- S7: 错误处理逻辑分散
- S8: 无steps列表统一管理
- S9: 扩展困难
- S10: 代码复用率低

Author: 小沈
Date: 2026-04-15
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Callable

from app.chat_stream.chat_helpers import create_timestamp, create_step_counter


# =============================================================================
# 第一部分：ReasoningStep抽象基类
# =============================================================================

class ReasoningStep(ABC):
    """
    ReasoningStep抽象基类
    
    所有Step类的基类，定义通用接口：
    - step: int → 步骤序号（统一）
    - timestamp: int → 时间戳（毫秒，统一）
    - get_type(): str → 获取type字段值
    - get_content(): str → 获取用户可见文本
    - is_done(): bool → 判断是否结束（抽象方法）
    - to_dict(): dict → 转换为前端SSE格式
    
    设计依据：
    - 13.2.2.2节Step类层次结构设计
    - 5.1.3节LlamaIndex BaseReasoningStep基类设计
    """
    
    def __init__(self, step: int, timestamp: Optional[int] = None):
        """
        初始化ReasoningStep
        
        Args:
            step: 步骤序号
            timestamp: 时间戳（毫秒），默认使用当前时间
        """
        self._step = step
        self._timestamp = timestamp or create_timestamp()
    
    @property
    def step(self) -> int:
        """获取步骤序号"""
        return self._step
    
    @property
    def timestamp(self) -> int:
        """获取时间戳（毫秒）"""
        return self._timestamp
    
    @abstractmethod
    def get_type(self) -> str:
        """
        获取type字段值
        
        Returns:
            type字段值：thought/action_tool/observation/final/error
        """
        pass
    
    @abstractmethod
    def get_content(self) -> str:
        """
        获取用户可见文本
        
        Returns:
            用户可见的文本内容
        """
        pass
    
    @abstractmethod
    def is_done(self) -> bool:
        """
        判断是否结束循环
        
        Returns:
            True - 结束循环
            False - 继续循环
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为前端SSE格式
        
        Returns:
            前端期望的字典格式
        """
        return {
            "type": self.get_type(),
            "step": self._step,
            "timestamp": self._timestamp,
            "content": self.get_content()
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(step={self._step}, type={self.get_type()})"


# =============================================================================
# 第二部分：ToolMixin混入类（解决S5重复问题）
# =============================================================================

class ToolMixin:
    """
    ToolMixin混入类
    
    将tool_name和tool_params字段混入Step类，解决字段重复问题：
    - ThoughtStep：需要tool_name/tool_params
    - ActionToolStep：需要tool_name/tool_params
    - ObservationStep：需要tool_name/tool_params
    
    设计依据：13.2.2.2节ToolMixin设计
    """
    
    def __init__(self, tool_name: str, tool_params: Optional[Dict[str, Any]] = None):
        """
        初始化ToolMixin
        
        Args:
            tool_name: 工具名称
            tool_params: 工具参数字典
        """
        self._tool_name = tool_name
        self._tool_params = tool_params or {}
    
    @property
    def tool_name(self) -> str:
        """获取工具名称"""
        return self._tool_name
    
    @property
    def tool_params(self) -> Dict[str, Any]:
        """获取工具参数"""
        return self._tool_params
    
    def get_tool_name_safe(self) -> str:
        """获取工具名称（安全版本，空值返回finish）"""
        return self._tool_name or "finish"


# =============================================================================
# 第2.5部分：ChunkStep类（新增）
# =============================================================================

class ChunkStep(ReasoningStep):
    """
    ChunkStep类 - 流式块步骤
    
    表示LLM生成的流式文本片段：
    - type: "chunk"
    - is_done() = False → 继续生成
    
    字段说明：
    - content: 块内容
    - is_reasoning: 是否正在推理
    
    设计依据：补充流式输出统一封装
    """
    
    def __init__(
        self,
        step: int,
        content: str,
        is_reasoning: bool = False,
        timestamp: Optional[int] = None
    ):
        """
        初始化ChunkStep
        
        Args:
            step: 步骤序号
            content: 块内容
            is_reasoning: 是否正在推理
            timestamp: 时间戳（毫秒）
        """
        # 调用ReasoningStep初始化
        ReasoningStep.__init__(self, step, timestamp)
        
        self._content = content
        self._is_reasoning = is_reasoning
    
    def get_type(self) -> str:
        return "chunk"
    
    def get_content(self) -> str:
        return self._content
    
    @property
    def is_reasoning(self) -> bool:
        """获取是否推理中"""
        return self._is_reasoning
    
    def is_done(self) -> bool:
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "is_reasoning": self._is_reasoning
        })
        return base_dict


# =============================================================================
# 第三部分：ThoughtStep类
# =============================================================================

class ThoughtStep(ToolMixin, ReasoningStep):
    """
    ThoughtStep类 - 思考步骤
    
    对应LLM的Thought输出，表示正在思考并准备执行工具：
    - type: "thought"
    - is_done() = False → 不结束，继续执行工具
    
    字段说明：
    - content: 思考内容摘要（用户可见）
    - thought: 详细思考内容
    - reasoning: 推理过程
    
    设计依据：13.2.2.2节具体实现类设计
    """
    
    def __init__(
        self,
        step: int,
        content: str,
        tool_name: str = "",
        tool_params: Dict[str, Any] = None,
        thought: str = "",
        reasoning: str = "",
        timestamp: Optional[int] = None
    ):
        """
        初始化ThoughtStep
        
        Args:
            step: 步骤序号
            content: 思考内容摘要（用户可见）
            tool_name: 工具名称
            tool_params: 工具参数
            thought: 详细思考内容
            reasoning: 推理过程
            timestamp: 时间戳（毫秒）
        """
        # 调用ToolMixin初始化
        ToolMixin.__init__(self, tool_name, tool_params)
        # 调用ReasoningStep初始化
        ReasoningStep.__init__(self, step, timestamp)
        
        self._content = content
        self._thought = thought or content
        self._reasoning = reasoning
    
    def get_type(self) -> str:
        return "thought"
    
    def get_content(self) -> str:
        return self._content
    
    @property
    def content(self) -> str:
        """获取思考内容摘要"""
        return self._content
    
    @property
    def thought(self) -> str:
        """获取详细思考内容"""
        return self._thought
    
    @property
    def reasoning(self) -> str:
        """获取推理过程"""
        return self._reasoning
    
    def is_done(self) -> bool:
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "thought": self._thought,
            "reasoning": self._reasoning,
            "tool_name": self._tool_name,  # 来自ToolMixin
            "tool_params": self._tool_params,  # 来自ToolMixin
        })
        return base_dict


# =============================================================================
# 第四部分：ActionToolStep类
# =============================================================================

class ActionToolStep(ToolMixin, ReasoningStep):
    """
    ActionToolStep类 - 工具执行步骤
    
    表示工具执行的结果：
    - type: "action_tool"
    - is_done() = False → 不结束，继续生成observation
    
    字段说明：
    - execution_status: 执行状态（success/error/warning）
    - summary: 执行摘要
    - execution_result: 执行结果数据（原raw_data）
    - error_message: 错误信息（成功时为空字符串）
    - action_retry_count: 重试次数（原retry_count）
    - execution_time_ms: 执行耗时（毫秒）
    
    设计依据：13.2.2.2节具体实现类设计
    """
    
    def __init__(
        self,
        step: int,
        tool_name: str,
        tool_params: Dict[str, Any],
        execution_status: str = "success",
        summary: str = "",
        execution_result: Any = None,
        error_message: str = "",
        action_retry_count: int = 0,
        execution_time_ms: int = 0,
        timestamp: Optional[int] = None
    ):
        """
        初始化ActionToolStep
        
        职责：只传递执行结果摘要（status/data/耗时/重试），
        详细信息（code/warning/next_actions/attachment）由ObservationStep负责。
        
        Args:
            step: 步骤序号
            tool_name: 工具名称
            tool_params: 工具参数
            execution_status: 执行状态（success/error/warning）
            summary: 执行摘要
            execution_result: 执行结果数据（原raw_data）
            error_message: 错误信息（成功时为空）
            action_retry_count: 重试次数（原retry_count）
            execution_time_ms: 执行耗时（毫秒）
            timestamp: 时间戳（毫秒）
        """
        # 调用ToolMixin初始化
        ToolMixin.__init__(self, tool_name, tool_params)
        # 调用ReasoningStep初始化
        ReasoningStep.__init__(self, step, timestamp)
        
        self._execution_status = execution_status
        self._summary = summary
        self._execution_result = execution_result
        self._error_message = error_message
        self._action_retry_count = action_retry_count
        self._execution_time_ms = execution_time_ms
    
    def get_type(self) -> str:
        return "action_tool"
    
    def get_content(self) -> str:
        return self._summary or self._error_message
    
    @property
    def execution_status(self) -> str:
        """获取执行状态"""
        return self._execution_status
    
    @property
    def summary(self) -> str:
        """获取执行摘要"""
        return self._summary
    
    @property
    def execution_result(self) -> Any:
        """获取执行结果数据"""
        return self._execution_result
    
    @property
    def error_message(self) -> str:
        """获取错误信息"""
        return self._error_message
    
    @property
    def action_retry_count(self) -> int:
        """获取重试次数"""
        return self._action_retry_count
    
    @property
    def execution_time_ms(self) -> int:
        """获取执行耗时"""
        return self._execution_time_ms
    
    @property
    def is_error(self) -> bool:
        """是否执行失败"""
        return self._execution_status == "error"
    
    def is_done(self) -> bool:
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "execution_status": self._execution_status,
            "execution_result": self._execution_result,
            "raw_data": self._execution_result,
            "action_retry_count": self._action_retry_count,
            "execution_time_ms": self._execution_time_ms,
            "tool_name": self._tool_name,
            "tool_params": self._tool_params,
        })
        return base_dict


# =============================================================================
# 第五部分：ObservationStep类
# =============================================================================

class ObservationStep(ToolMixin, ReasoningStep):
    """
    ObservationStep类 - 观察步骤
    
    表示工具执行后的观察结果：
    - type: "observation"
    - is_done() = return_direct → 根据工具是否要求直接返回
    
    字段说明：
    - observation: 观察结果
    - return_direct: 是否直接返回（工具要求直接返回结果）
    
    设计依据：13.2.2.2节具体实现类设计
    """
    
    def __init__(
        self,
        step: int,
        tool_name: str,
        tool_params: Dict[str, Any],
        observation: str = "",
        return_direct: bool = False,
        execution_status: str = "",
        code: str = "",
        warning: Optional[str] = None,
        attachment: Any = None,
        next_actions: Optional[List[Dict[str, str]]] = None,
        summary: str = "",
        error_message: str = "",
        timestamp: Optional[int] = None
    ):
        """
        初始化ObservationStep
        
        职责：传递执行详细信息（code/warning/next_actions/attachment/summary/error_message），
        业务数据（data）由ActionToolStep负责，不重复。
        
        Args:
            step: 步骤序号
            tool_name: 工具名称
            tool_params: 工具参数
            observation: 观察结果文本（summary）
            return_direct: 是否直接返回
            execution_status: 执行状态
            code: 原始错误码
            warning: 警告文本
            attachment: 二进制附件
            next_actions: 推荐下一步操作
            summary: 执行摘要（给前端展示用）
            error_message: 错误信息（给前端展示用）
            timestamp: 时间戳（毫秒）
        """
        ToolMixin.__init__(self, tool_name, tool_params)
        ReasoningStep.__init__(self, step, timestamp)
        
        self._observation = observation
        self._return_direct = return_direct
        self._execution_status = execution_status
        self._code = code
        self._warning = warning
        self._attachment = attachment
        self._next_actions = next_actions
        self._summary = summary
        self._error_message = error_message
    
    def get_type(self) -> str:
        return "observation"
    
    def get_content(self) -> str:
        return self._observation
    
    @property
    def observation(self) -> str:
        """获取观察结果"""
        return self._observation
    
    @property
    def return_direct(self) -> bool:
        """获取是否直接返回"""
        return self._return_direct
    
    @property
    def summary(self) -> str:
        """获取执行摘要"""
        return self._summary
    
    @property
    def error_message(self) -> str:
        """获取错误信息"""
        return self._error_message
    
    def is_done(self) -> bool:
        return self._return_direct
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        
        # 【改造 2026-05-22 小沈】observation改为JSON对象，符合第13章设计方案
        # 【修复 2026-05-22 小资】summary为空时使用error_message或默认值，避免前端渲染失败
        summary_text = self._observation or self._summary or self._error_message or "执行完成"
        observation_obj = {
            "summary": summary_text,
            "tool_name": self._tool_name or "unknown",
            "tool_params": self._tool_params or {},
            "return_direct": self._return_direct or False,
        }
        
        if self._execution_status:
            observation_obj["execution_status"] = self._execution_status
        if self._error_message:
            observation_obj["error_message"] = self._error_message
        if self._warning:
            observation_obj["warning"] = self._warning
        if self._next_actions:
            observation_obj["next_actions"] = self._next_actions
        if self._attachment is not None:
            observation_obj["attachment"] = self._attachment
        
        d = {"observation": observation_obj}
        if self._code:
            d["code"] = self._code
        
        base_dict.update(d)
        return base_dict


# =============================================================================
# 第六部分：FinalStep类
# =============================================================================

class FinalStep(ReasoningStep):
    """
    FinalStep类 - 最终回答步骤
    
    表示Agent完成，最终给出答案：
    - type: "final"
    - is_done() = True → 结束循环
    
    字段说明：
    - response: 最终回答
    - thought: 思考过程
    - is_finished: 业务完成标志
    
    设计依据：13.2.2.2节具体实现类设计
    """
    
    def __init__(
        self,
        step: int,
        response: str,
        thought: str = "",
        model: Optional[str] = None,
        provider: Optional[str] = None,
        timestamp: Optional[int] = None
    ):
        """
        初始化FinalStep
        
        Args:
            step: 步骤序号
            response: 最终回答
            thought: 思考过程
            model: 模型名称（可选）
            provider: 提供商（可选）
            timestamp: 时间戳（毫秒）
            
        说明【2026-05-04 小沈】：
        - 不需要 is_finished: type="final" 本身就是已完成标识
        - 不需要 is_streaming: 最终回答不是流式，流式用SHE实时推送
        - 不需要 is_reasoning: type="final" 不可能在推理中
        """
        # 调用ReasoningStep初始化
        ReasoningStep.__init__(self, step, timestamp)
        
        self._response = response
        self._thought = thought
        self._model = model
        self._provider = provider
        # 【修复 2026-05-13 小健】初始化属性，避免访问时AttributeError
        self._is_finished = True       # type="final"本身就是已完成标识
        self._is_streaming = False     # 最终回答不是流式
        self._is_reasoning = False     # 最终回答不可能在推理中
    
    def get_type(self) -> str:
        return "final"
    
    def get_content(self) -> str:
        return self._response
    
    @property
    def response(self) -> str:
        """获取最终回答"""
        return self._response
    
    @property
    def thought(self) -> str:
        """获取思考过程"""
        return self._thought
    
    @property
    def is_finished(self) -> bool:
        """获取业务完成标志"""
        return self._is_finished
    
    @property
    def is_streaming(self) -> bool:
        """获取是否流式输出"""
        return self._is_streaming
    
    @property
    def is_reasoning(self) -> bool:
        """获取是否推理中"""
        return self._is_reasoning
    
    @property
    def model(self) -> Optional[str]:
        """获取模型名称"""
        return self._model
    
    @property
    def provider(self) -> Optional[str]:
        """获取提供商"""
        return self._provider
    
    def is_done(self) -> bool:
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        # 【修复 2026-05-13 小沈】M5: 保留content作为response别名，向后兼容旧消费者
        base_dict.update({
            "response": self._response,
            "content": self._response,  # content作为response的别名
            "thought": self._thought,
            "model": self._model,
            "provider": self._provider,
        })
        return base_dict


# =============================================================================
# 第七部分：ErrorStep类
# =============================================================================

class ErrorStep(ReasoningStep):
    """
    ErrorStep类 - 错误步骤
    
    表示执行过程中出现错误：
    - type: "error"
    - is_done() = True → 结束循环
    
    字段说明：
    - error_type: 错误类型
    - error_message: 错误信息
    - recoverable: 是否可恢复
    
    设计依据：13.2.2.2节具体实现类设计
    """
    
    def __init__(
        self,
        step: int,
        error_type: str,
        error_message: str,
        recoverable: bool = False,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        reasoning: str = "",
        is_reasoning: bool = False,
        context: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
        timestamp: Optional[int] = None
    ):
        """
        初始化ErrorStep
        
        Args:
            step: 步骤序号
            error_type: 错误类型
            error_message: 错误信息
            recoverable: 是否可恢复
            model: 模型名称（可选）
            provider: 提供商（可选）
            reasoning: 思考过程（可选）
            is_reasoning: 是否推理中（可选）
            context: 错误上下文（可选）
            retry_after: 重试等待秒数（可选）
            timestamp: 时间戳（毫秒）
        """
        # 调用ReasoningStep初始化
        ReasoningStep.__init__(self, step, timestamp)
        
        self._error_type = error_type
        self._error_message = error_message
        self._recoverable = recoverable
        self._model = model
        self._provider = provider
        self._reasoning = reasoning
        self._is_reasoning = is_reasoning
        self._context = context
        self._retry_after = retry_after
    
    def get_type(self) -> str:
        return "error"
    
    def get_content(self) -> str:
        return self._error_message
    
    @property
    def error_type(self) -> str:
        """获取错误类型"""
        return self._error_type
    
    @property
    def error_message(self) -> str:
        """获取错误信息"""
        return self._error_message
    
    @property
    def recoverable(self) -> bool:
        """获取是否可恢复"""
        return self._recoverable
    
    @property
    def model(self) -> Optional[str]:
        """获取模型名称"""
        return self._model
    
    @property
    def provider(self) -> Optional[str]:
        """获取提供商"""
        return self._provider
    
    @property
    def reasoning(self) -> str:
        """获取思考过程"""
        return self._reasoning
    
    @property
    def is_reasoning(self) -> bool:
        """获取是否推理中"""
        return self._is_reasoning
    
    @property
    def context(self) -> Optional[Dict[str, Any]]:
        """获取错误上下文"""
        return self._context
    
    @property
    def retry_after(self) -> Optional[int]:
        """获取重试等待秒数"""
        return self._retry_after
    
    def is_done(self) -> bool:
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "error_type": self._error_type,
            "error_message": self._error_message,
            "recoverable": self._recoverable,
            "model": self._model,
            "provider": self._provider,
            "reasoning": self._reasoning,
            "is_reasoning": self._is_reasoning,
            "context": self._context,
            "retry_after": self._retry_after,
        })
        return base_dict


# =============================================================================
# 第八部分：StepFactory工厂类
# =============================================================================

class StepFactory:
    """
    StepFactory工厂类 - 统一构建入口
    
    解决S3分散问题，提供统一的Step构建方法：
    - create_thought_step()
    - create_action_tool_step()
    - create_observation_step()
    - create_chunk_step()
    - create_final_step()
    - create_error_step()
    
    设计依据：13.2.2.2节Step构建统一入口设计
    """
    
    @staticmethod
    def create_thought_step(
        step: int,
        content: str,
        tool_name: str = "",
        tool_params: Dict[str, Any] = None,
        thought: str = "",
        reasoning: str = ""
    ) -> ThoughtStep:
        """
        创建ThoughtStep
        
        Args:
            step: 步骤序号
            content: 思考内容摘要
            tool_name: 工具名称
            tool_params: 工具参数
            thought: 详细思考内容
            reasoning: 推理过程
            
        Returns:
            ThoughtStep实例
        """
        return ThoughtStep(
            step=step,
            content=content,
            tool_name=tool_name,
            tool_params=tool_params,
            thought=thought or content,
            reasoning=reasoning
        )
    
    @staticmethod
    def create_action_tool_step(
        step: int,
        tool_name: str,
        tool_params: Dict[str, Any],
        execution_result: Dict[str, Any],
        execution_time_ms: int = 0
    ) -> ActionToolStep:
        """
        创建ActionToolStep
        
        Args:
            step: 步骤序号
            tool_name: 工具名称
            tool_params: 工具参数
            execution_result: 执行结果字典
                - status: 执行状态（success/error/warning）
                - summary: 执行摘要
                - data: 执行结果数据
                - error: 错误信息
                - retry_count: 重试次数
            execution_time_ms: 执行耗时（毫秒，使用perf_counter计算）
                
        Returns:
            ActionToolStep实例
        """
        # 【已修复 2026-05-21 小沈】
        # 原 bug：execution_result_dict 没有 "code" 键（只有 "status" 键），
        # extract_status() 始终返回 "success" 默认值。
        # 修正：直接使用 execution_result_dict["status"]（由 caller 已计算好）
        _status = execution_result.get("status", "success")
        
        return ActionToolStep(
            step=step,
            tool_name=tool_name,
            tool_params=tool_params or {},
            execution_status=_status,
            summary=execution_result.get("summary", ""),
            execution_result=execution_result.get("data"),
            error_message=(execution_result.get("error_message", "") or execution_result.get("message", "")) if execution_result.get("code", 0) != 0 else "",
            action_retry_count=execution_result.get("retry_count", 0),
            execution_time_ms=execution_time_ms,
        )
    
    @staticmethod
    def create_chunk_step(
        step: int,
        content: str,
        is_reasoning: bool = False
    ) -> ChunkStep:
        """
        创建ChunkStep
        
        Args:
            step: 步骤序号
            content: 块内容
            is_reasoning: 是否正在推理
                
        Returns:
            ChunkStep实例
        """
        return ChunkStep(
            step=step,
            content=content,
            is_reasoning=is_reasoning
        )
    
    @staticmethod
    def create_observation_step(
        step: int,
        tool_name: str,
        tool_params: Dict[str, Any],
        execution_result: Dict[str, Any],
        return_direct: bool = False
    ) -> ObservationStep:
        """
        创建ObservationStep
        
        execution_result 中包含完整信息，observation 字段取 summary 文本，
        其余字段（code/data/warning/attachment/next_actions）条件透传给前端SSE。
        
        Args:
            step: 步骤序号
            tool_name: 工具名称
            tool_params: 工具参数
            execution_result: 执行结果字典
                - status: 执行状态
                - summary: 执行摘要（用于 observation 文本字段）
                - data: 业务数据
                - code: 原始错误码
                - warning: 警告文本
                - attachment: 附件
                - next_actions: 推荐下一步
            return_direct: 是否直接返回
            
        Returns:
            ObservationStep实例
        """
        # 【修复 2026-04-17 小沈】使用 summary 而不是 data
        # observation 字段只应包含精简摘要，不是完整的原始数据结构
        # display_text 在 base_react.py 中定义为：execution_result.get('summary', '')
        observation_text = execution_result.get("summary", "")
        
        return ObservationStep(
            step=step,
            tool_name=tool_name,
            tool_params=tool_params or {},
            observation=observation_text,
            return_direct=return_direct,
            execution_status=execution_result.get("status", ""),
            code=execution_result.get("code", ""),
            warning=execution_result.get("warning"),
            attachment=execution_result.get("attachment"),
            next_actions=execution_result.get("next_actions"),
            summary=execution_result.get("summary", ""),
            error_message=execution_result.get("error_message", ""),
        )
    
    @staticmethod
    def create_final_step(
        step: int,
        response: str,
        thought: str = "",
        model: Optional[str] = None,
        provider: Optional[str] = None
    ) -> FinalStep:
        """
        创建FinalStep【2026-05-04 小沈】精简参数
        
        Args:
            step: 步骤序号
            response: 最终回答
            thought: 思考过程
            model: 模型名称（可选）
            provider: 提供商（可选）
                
        Returns:
            FinalStep实例
        """
        return FinalStep(
            step=step,
            response=response,
            thought=thought,
            model=model,
            provider=provider
        )
    
    @staticmethod
    def create_error_step(
        step: int,
        error_type: str,
        error_message: str,
        recoverable: bool = False,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        reasoning: str = "",
        is_reasoning: bool = False,
        context: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None
    ) -> ErrorStep:
        """
        创建ErrorStep
        
        【补充 2026-04-17 小沈】参考v0.9.7.1版本，补全所有字段
        
        Args:
            step: 步骤序号
            error_type: 错误类型
            error_message: 错误信息
            recoverable: 是否可恢复
            model: 模型名称（可选）
            provider: 提供商（可选）
            reasoning: 思考过程（可选）
            is_reasoning: 是否推理中（可选）
            context: 错误上下文（可选）
            retry_after: 重试等待秒数（可选）
                
        Returns:
            ErrorStep实例
        """
        return ErrorStep(
            step=step,
            error_type=error_type,
            error_message=error_message,
            recoverable=recoverable,
            model=model,
            provider=provider,
            reasoning=reasoning,
            is_reasoning=is_reasoning,
            context=context,
            retry_after=retry_after
        )


# =============================================================================
# 第九部分：导出声明
# =============================================================================

__all__ = [
    "ReasoningStep",
    "ToolMixin",
    "ThoughtStep",
    "ActionToolStep",
    "ObservationStep",
    "ChunkStep",
    "FinalStep",
    "ErrorStep",
    "StepFactory",
    "create_timestamp",
    "create_step_counter",
]
