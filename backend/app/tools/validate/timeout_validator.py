# -*- coding: utf-8 -*-
# validate/timeout_validator.py — timeout参数统一验证（跨工具共享）
# 小沈 2026-06-27
# 编辑历史:
# 2026-10-02 - 小欧 - 注册名归位: 入口加 normalize_tool_name, 堵"传旧名/别名即绕过上下界校验"的洞(LLM 用 write_text 等变体名调 write 时同样绕过)
# 2026-10-02 - 小欧 - 注册名归位: TIMEOUT_RANGES_SECONDS 键 "shell"→"bash"(与 fundamental 注册名一致)

from typing import Optional, Tuple

from app.tools.tools_alias_mapper import normalize_tool_name


# 各工具timeout范围（秒）
TIMEOUT_RANGES_SECONDS = {
    "httpget":           (1,   300),     # 1秒 ~ 5分钟
    "download":          (5,  3600),     # 5秒 ~ 1小时
    "fetchpage":          (1,   120),     # 1秒 ~ 2分钟
    "ping_port":              (1,    30),     # 1秒 ~ 30秒
    "bash":      (1,   600),     # 1秒 ~ 10分钟
    "compress":          (5,  1800),     # 5秒 ~ 30分钟
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

    tool_name = normalize_tool_name(tool_name)  # 2026-10-02 小欧 - 归一后再查表, 防别名绕过上下界
    if tool_name not in TIMEOUT_RANGES_SECONDS:
        return True, None, None

    min_s, max_s = TIMEOUT_RANGES_SECONDS[tool_name]
    if timeout < min_s:
        return False, f"{tool_name}的timeout不能小于{min_s}秒", None
    if timeout > max_s:
        return False, f"{tool_name}的timeout不能大于{max_s}秒", None

    return True, None, None
