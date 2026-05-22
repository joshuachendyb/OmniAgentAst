# -*- coding: utf-8 -*-
"""
跨模块共享的 ContextVar 定义 — 小沈 2026-05-21

用途：_current_task_id 用于工具执行链路追踪，以下场景需要：
  - health.py:/tool/execute 端点手动测试（不走Agent链路，必须手动set）
  - 单元测试直接实例化 FileSearcher/FileReader 等类（构造时读 task_id）
  - Agent SSE 集成测试（验证 task_id 传递正确）
"""
from contextvars import ContextVar
from typing import Optional

_current_task_id: ContextVar[Optional[str]] = ContextVar("tool_task_id", default=None)
