# -*- coding: utf-8 -*-
"""
Chat Router - 路由层

【第一阶段实现 - 2026-03-26 小沈】
根据用户意图类型，将请求分发到对应的执行层。

架构：
- 第一层：chat_router.py - 路由入口
- 第二层：react_sse_wrapper.py - SSE 包装（待实现）
- 第三层：file_react.py / network_react.py / desktop_react.py - 意图特定 Agent
- 第四层：base_react.py - 通用 ReAct 逻辑

【阶段1目标】
- 实现 chat_router.py（第一层）
- 直接调用 file_react.ver1_run_stream()
- 验证：路由 + 文件操作正常工作

Author: 小沈 - 2026-03-26
"""

import uuid
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from app.services.preprocessing.pipeline import PreprocessingPipeline
from app.services.agent.file_react import FileReactAgent
from app.utils.logger import logger


# 意图标签列表（用于 PreprocessingPipeline）
INTENT_LABELS = ["chat", "file", "network", "desktop"]


class ChatRouter:
    """
    聊天路由器 - 根据意图类型分发到对应的执行层
    """

    def __init__(self) -> None:
        self.preprocessing = PreprocessingPipeline()

    async def route(
        self,
        user_input: str,
        model: str,
        provider: str,
        llm_client: Any,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 100,
        get_next_step: Optional[Callable[[], int]] = None
    ) -> AsyncGenerator[str, None]:
        """
        根据用户意图路由到对应的执行层

        Args:
            user_input: 用户输入
            model: 模型名称
            provider: 提供商
            llm_client: LLM 客户端函数
            session_id: 会话ID
            context: 额外上下文
            system_prompt: 自定义系统提示
            max_steps: 最大步数
            get_next_step: step 计数函数

        Yields:
            SSE 格式字符串
        """
        # 步骤1: 意图检测
        intent_result = self.preprocessing.process(
            user_input=user_input,
            intent_labels=INTENT_LABELS,
            session_id=session_id
        )

        intent_type = intent_result.get("intent", "chat")
        confidence = intent_result.get("confidence", 0.0)

        logger.info(
            f"[ChatRouter] intent_type={intent_type}, confidence={confidence:.4f}, "
            f"original='{user_input}', corrected='{intent_result.get('corrected', '')}'"
        )

        # 步骤2: 根据意图类型分发
        if intent_type == "file" and confidence >= 0.3:
            # 文件操作：调用 FileReactAgent
            async for sse_data in self._handle_file_operation(
                user_input=user_input,
                model=model,
                provider=provider,
                llm_client=llm_client,
                session_id=session_id,
                context=context,
                system_prompt=system_prompt,
                max_steps=max_steps,
                get_next_step=get_next_step
            ):
                yield sse_data
        else:
            # 默认：普通对话（第一阶段暂不实现）
            logger.warning(f"[ChatRouter] Unsupported intent: {intent_type}, falling back to chat")
            yield self._create_error_sse(
                message=f"暂不支持 {intent_type} 意图，当前仅支持 file 意图",
                step=get_next_step() if get_next_step else 0
            )

    async def _handle_file_operation(
        self,
        user_input: str,
        model: str,
        provider: str,
        llm_client: Any,
        session_id: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 100,
        get_next_step: Optional[Callable[[], int]] = None
    ) -> AsyncGenerator[str, None]:
        """
        处理文件操作意图

        Args:
            user_input: 用户输入
            model: 模型名称
            provider: 提供商
            llm_client: LLM 客户端函数
            session_id: 会话ID
            context: 额外上下文
            system_prompt: 自定义系统提示
            max_steps: 最大步数
            get_next_step: step 计数函数

        Yields:
            SSE 格式字符串
        """
        try:
            # 创建 FileReactAgent 实例
            agent = FileReactAgent(
                llm_client=llm_client,
                session_id=session_id
            )

            # 调用 ver1_run_stream（返回 SSE 字符串）
            async for sse_data in agent.ver1_run_stream(
                task=user_input,
                model=model,
                provider=provider,
                context=context,
                system_prompt=system_prompt,
                max_steps=max_steps,
                get_next_step=get_next_step
            ):
                yield sse_data

        except Exception as e:
            logger.error(f"[ChatRouter] File operation failed: {e}", exc_info=True)
            yield self._create_error_sse(
                message=f"文件操作执行失败: {str(e)}",
                step=get_next_step() if get_next_step else 0
            )

    def _create_error_sse(self, message: str, step: int) -> str:
        """创建错误 SSE 响应"""
        import json
        error_data = {
            "type": "error",
            "step": step,
            "code": "ROUTER_ERROR",
            "message": message
        }
        return f"data: {json.dumps(error_data)}\n\n"


# 便捷函数：创建 router 实例
def create_chat_router() -> ChatRouter:
    """创建 ChatRouter 实例"""
    return ChatRouter()
