# -*- coding: utf-8 -*-
"""
setup_logger — 全局共享一个 SafeRotatingFileHandler 实例
- 修改人 小欧 2026-07-11
- 所有 logger 共用一个文件 handler，消灭多 handler 写同一文件的 Windows rename 锁竞争
"""

# 编辑历史:
# 2026-07-17 - 小欧 - 日志会话维度隔离: 通过 contextvars(context.py) + SessionFilter 将 session_id 注入每条日志记录, formatter 增加 %(session_id)s 字段; 保持全局单例 handler 不变(不破坏 2026-07-11 的 Windows rename 锁竞争修复), 多会话日志可按 session 过滤且不引入多文件描述符, 功能零退化

import logging
from typing import Optional

from app.logger.config import SafeRotatingFileHandler, LogConfig


# ---- 全局共享文件 handler ------------------------------------------------
# 关键：整个进程只创建一个 SafeRotatingFileHandler，所有 logger 共用
# 根因：7个 handler 分别写同一文件 → Windows rename 被其他句柄锁住
# 修复：1 handler → 1 文件描述符 → 0 竞争
# — 小欧 2026-07-11

_FILE_HANDLER: Optional[SafeRotatingFileHandler] = None


def _get_shared_handler() -> SafeRotatingFileHandler:
    """获取全局唯一的文件 handler — 小欧 2026-07-11"""
    global _FILE_HANDLER
    if _FILE_HANDLER is None:
        from app.logger.config import _get_log_file_path
        log_file = _get_log_file_path()
        _FILE_HANDLER = SafeRotatingFileHandler(
            log_file,
            maxBytes=LogConfig.get_max_bytes(),
            backupCount=LogConfig.get_backup_count(),
            encoding='utf-8',
        )
        _FILE_HANDLER.addFilter(SessionFilter())
    return _FILE_HANDLER


# ---- Console 截断 Formatter --------------------------------------------

class _TruncateConsoleFormatter(logging.Formatter):
    """console 日志截断 Formatter — 只截断消息体%(message)s，前缀不动 — 小欧 2026-07-11"""
    def format(self, record):
        raw = record.getMessage()
        if len(raw) > 100:
            record.msg = raw[:120] + f"...(截断{len(raw)-120}字符)"
            record.args = None
        return super().format(record)


# ---- SessionFilter: 注入 session_id 到日志记录 ---------------------------------
class SessionFilter(logging.Filter):
    """将当前协程上下文的 session_id 注入每条日志记录 — 小欧 2026-07-17
    原理: 从请求作用域的上下文变量读取会话标识写入 record.session_id, 供 formatter 的 %(session_id)s 字段输出;
    默认值为 '-'(无会话上下文时)。延迟导入上下文变量以避开 app.logger 与 app.services 的循环依赖。
    作用: 多会话并发时日志可按 session 过滤, 且不破坏全局单例 handler 的 Windows 锁修复。
    """
    def filter(self, record: logging.LogRecord) -> bool:
        from app.services.task.task_context import session_id_var
        record.session_id = session_id_var.get()
        return True


# ---- setup_logger -----------------------------------------------------

def setup_logger(name: str) -> logging.Logger:
    """
    创建或获取指定名称的 logger
    - 所有 logger 共享同一个文件 handler（全局单例）
    - 每个 logger 独立拥有一个 console handler
    — 小欧 2026-07-11
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    log_level = getattr(logging, LogConfig.get_log_level().upper())
    is_debug = LogConfig.is_debug_mode()

    # formatter — 文件 handler 和 console handler 共用
    if is_debug:
        _fmt = '%(asctime)s - %(levelname)s - %(session_id)s - %(filename)s:%(lineno)d - %(message)s'
    else:
        _fmt = '%(asctime)s - %(levelname)s - %(session_id)s - %(filename)s - %(message)s'
    formatter = logging.Formatter(_fmt, datefmt='%Y-%m-%d %H:%M:%S')

    # 文件 handler — 全局共享
    file_handler = _get_shared_handler()
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # console handler — 每 logger 独立
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        _TruncateConsoleFormatter(fmt=_fmt, datefmt='%Y-%m-%d %H:%M:%S')
    )
    console_handler.setLevel(logging.WARNING)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.setLevel(log_level)
    logger.propagate = False

    return logger
