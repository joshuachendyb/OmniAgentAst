# -*- coding: utf-8 -*-
"""
validate_chat_config — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第378-413行
"""

from app.utils.logger import logger


async def validate_chat_config():
    """拷贝自 chat_router.py 第378-413行"""
    try:
        from app.services.ai_config_resolver import get_ai_config_resolver

        resolver = get_ai_config_resolver()
        is_valid, final_provider, final_model, error_messages = resolver.validate_config()

        if not is_valid:
            return {
                "valid": False,
                "message": f"配置验证失败: {', '.join(error_messages)}",
                "provider": final_provider or "unknown",
                "model": final_model or ""
            }

        return {
            "valid": True,
            "message": f"配置验证通过: {final_provider} ({final_model})",
            "provider": final_provider,
            "model": final_model
        }
    except Exception as e:
        logger.error(f"验证AI服务配置失败: {e}")
        return {
            "valid": False,
            "message": f"验证失败: {str(e)}",
            "provider": "unknown",
            "model": ""
        }
