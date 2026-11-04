# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 北京老陈裁定(开关归一) - 新建: 调试专用接口的单一守卫, 由 api 层共用。
"""
api 调试开关守卫 — 单一真源 logging.debug

2026-10-15 北京老陈裁定: 「是否调试环境」此前散三处(config 键 tools.execute_tool_enabled、
X-Test-Mode 头、既有 logging.debug), 口径不一致。现统一为 logging.debug 一处, 经
LogConfig.is_debug_mode() 读取(全项目已有访问器, 不新增配置项)。

受约束接口(均为调试探针, 非产品功能):
  - GET  /tool/list        app/api/v1/tool_routes.py
  - POST /tool/execute     app/api/v1/tool_routes.py
  - POST /echo             app/api/v1/health.py

不属调试专用、不受本守卫约束: /providers/*/test-connection 与 /zen-verify/*
(两者均有前端完整交互 UI, 属产品功能)。
"""
from fastapi import HTTPException

from app.logger.config import LogConfig

CLOSED_MSG = "调试接口已关闭(非调试模式, 需在config开启 logging.debug)"


def require_debug_mode() -> None:
    """非调试模式抛 403。2026-10-15 北京老陈裁定: 三接口共用, 不各判各的。"""
    if not LogConfig.is_debug_mode():
        raise HTTPException(status_code=403, detail=CLOSED_MSG)