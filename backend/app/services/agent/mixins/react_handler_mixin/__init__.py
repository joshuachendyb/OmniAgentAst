# -*- coding: utf-8 -*-
"""
react_handler_mixin 模块 — 从 react_handler_mixin.py 拆出的职责

- merge_thought_text: 合并thought文本
- handle_chunk_type: chunk处理
- complete_chunk: chunk完成
- handle_completion_type: 完成处理
- handle_thought_only: 思考处理
- handle_parse_error: 解析错误处理
- handle_action_type: 动作处理
- handle_observation_flow: 观察流处理
- handle_pending_calls: 并行调用处理
- _core: ReActHandlerMixin 核心类
"""

from app.services.agent.mixins.react_handler_mixin.react_handler_mixin import ReActHandlerMixin

__all__ = ["ReActHandlerMixin"]
