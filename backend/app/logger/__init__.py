# logger/__init__.py — 高层日志服务
# 小欧 2026-07-10 从 services/prompts/ 迁入

from app.logger.prompt_logger import get_prompt_logger, PromptLogger

__all__ = ["get_prompt_logger", "PromptLogger"]
