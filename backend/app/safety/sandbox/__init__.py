# -*- coding: utf-8 -*-
# __init__.py — 沙箱预检模块导出(设计文档 3.1) — 小欧 2026-08-25
from app.safety.sandbox.executor import SandboxExecutor, get_sandbox_executor, PreCheckResult

__all__ = ["SandboxExecutor", "get_sandbox_executor", "PreCheckResult"]
