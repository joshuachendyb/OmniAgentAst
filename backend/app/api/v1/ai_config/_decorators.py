"""ai_config 包统一异常处理装饰器 — 复用全局 handle_api_errors

【小健 2026-05-31】新建 → 改为导入全局装饰器
"""

from app.utils.response_utils import handle_api_errors as handle_config_errors

__all__ = ["handle_config_errors"]
