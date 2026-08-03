# -*- coding: utf-8 -*-
"""
LLM层常量集中管理 — 小欧 2026-06-25

散落在4个文件的硬编码统一收敛到此文件。
原则：不配置，写到常量文件。max_tokens不设置（传None，LLM自行决定）。
"""

# --- LLM请求参数 ---
LLM_TEMPERATURE = 0.7
LLM_TOOL_CHOICE = "auto"
LLM_STREAM_MAX_RETRIES = 3  # request_stream()应用层重试上限，区别于config.yaml的HTTP层max_retries
LLM_STREAM_OPTIONS = {"include_usage": True}

# --- FC降级配置 ---
FC_FALLBACK_ENABLED = True
FC_MAX_RETRIES = 2  # FC模式最多重试2次，失败后降级到Text模式

# --- 工具缓存 ---
TOOL_CACHE_TTL = 300  # 5分钟
