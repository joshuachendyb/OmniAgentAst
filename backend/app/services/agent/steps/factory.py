# -*- coding: utf-8 -*-
"""
StepFactory工厂类 - 统一构建入口

解决S3分散问题，提供统一的Step构建方法：
- create_thought_step()
- create_action_tool_step()
- create_observation_step()
- create_chunk_step()
- create_final_step()
- create_error_step()

Author: 小沈
Date: 2026-04-15
"""

from typing import Any, Dict, Optional

from .thought_step import ThoughtStep
from .action_step import ActionToolStep
from .observation_step import ObservationStep
from .chunk_step import ChunkStep
from .final_step import FinalStep
from .error_step import ErrorStep
from .incident_step import IncidentStep
from .start_step import StartStep


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
    - create_incident_step()
    - create_start_step()
    
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
        is_reasoning: bool = False,
        thought: str = '',
        reasoning: str = '',
        thinking: str = '',
        model: str = '',
        provider: str = '',
    ) -> ChunkStep:
        """
        创建ChunkStep
        
        Args:
            step: 步骤序号
            content: 块内容
            is_reasoning: 是否正在推理
            thought: 思考内容
            reasoning: 推理过程
            thinking: 内部思考标记
            model: 模型名称
            provider: 提供商
                
        Returns:
            ChunkStep实例
        """
        return ChunkStep(
            step=step,
            content=content,
            is_reasoning=is_reasoning,
            thought=thought,
            reasoning=reasoning,
            thinking=thinking,
            model=model,
            provider=provider,
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

    @staticmethod
    def create_incident_step(
        step: int,
        incident_value: str,
        message: str,
        content: Optional[str] = None
    ) -> IncidentStep:
        """
        创建IncidentStep

        Args:
            step: 步骤序号
            incident_value: 事件类型值（interrupted/paused/resumed/retrying）
            message: 事件消息
            content: 内容（可选，默认等于message）

        Returns:
            IncidentStep实例
        """
        return IncidentStep(
            step=step,
            incident_value=incident_value,
            message=message,
            content=content
        )

    @staticmethod
    def create_start_step(
        step: int,
        display_name: str,
        provider: str,
        model: str,
        task_id: str,
        user_message: str,
        security_check: Dict[str, Any]
    ) -> StartStep:
        """
        创建StartStep

        Args:
            step: 步骤序号
            display_name: 模型显示名称
            provider: 提供商
            model: 模型名称
            task_id: 任务ID
            user_message: 用户消息
            security_check: 安全检查结果

        Returns:
            StartStep实例
        """
        return StartStep(
            step=step,
            display_name=display_name,
            provider=provider,
            model=model,
            task_id=task_id,
            user_message=user_message,
            security_check=security_check
        )
