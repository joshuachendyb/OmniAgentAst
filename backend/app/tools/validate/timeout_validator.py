# validate/timeout_validator.py — timeout参数统一验证（跨工具共享）
# 小沈 2026-06-27

from typing import Optional, Tuple


# 各工具timeout范围（秒）
TIMEOUT_RANGES_SECONDS = {
    "http_request":           (1,   300),     # 1秒 ~ 5分钟
    "download_file":          (5,  3600),     # 5秒 ~ 1小时
    "fetch_webpage":          (1,   120),     # 1秒 ~ 2分钟
    "network_diagnose":       (1,    30),     # 1秒 ~ 30秒
    "execute_shell_command":  (1,   600),     # 1秒 ~ 10分钟
    "execute_code":           (1,   300),     # 1秒 ~ 5分钟
}


def validate_timeout(timeout: int, tool_name: str) -> Tuple[bool, Optional[str], None]:
    """
    timeout参数验证（适用于所有有timeout的工具）
    
    参数：timeout — 秒（schema给LLM暴露的单位就是秒）
    
    检查内容：
    1. timeout必须为正整数
    2. timeout必须在工具对应的[min_seconds, max_seconds]范围内
    
    Returns: (is_valid, error_msg, None)
    """
    if not isinstance(timeout, int) or timeout <= 0:
        return False, f"timeout必须为正整数（秒），收到: {timeout}", None
    
    if tool_name not in TIMEOUT_RANGES_SECONDS:
        return True, None, None
    
    min_s, max_s = TIMEOUT_RANGES_SECONDS[tool_name]
    if timeout < min_s:
        return False, f"{tool_name}的timeout不能小于{min_s}秒", None
    if timeout > max_s:
        return False, f"{tool_name}的timeout不能大于{max_s}秒", None
    
    return True, None, None
