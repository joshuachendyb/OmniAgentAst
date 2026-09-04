
"""
日志工具模块 — 统一入口
整合 log_config(通用日志)

创建时间: 2026-07-10
迁移更新: 2026-07-10 小欧 — 从 utils/log_config/ 迁入合并
"""
# 编辑历史:
# 2026-07-23 小欧 - 新增公共函数 log_and_print(): 将 logger.info(msg)+print(msg) 双输出模式收口到统一函数, 解决 console handler 仅 WARNING 以上级别时 info 日志无法上控制台的问题; 导出至 __all__
# 2026-08-30 小欧 - 控制台镜像离线化(根治 case09 挂起): log_and_print 的 print(msg)→console_put(msg), 事件循环线程零同步 stdout 写; stdout 阻塞时只丢控制台镜像, logger.info 文件日志始终完整

from app.logger.config import SafeRotatingFileHandler, LogConfig, LOG_DIR
from app.logger.shared_handler import setup_logger
from app.logger.api_logger import APILogger
from app.logger.console_writer import console_put  # 小欧 2026-08-30 控制台镜像离线化(根治 case09 挂起)

api_logger = APILogger()
logger = setup_logger(__name__)


def log_and_print(msg: str) -> None:
    """同时输出到日志文件和控制台 — 小欧 2026-07-23 (2026-08-30 小欧 print→console_put 离线化)

    背景: setup_logger 的 console handler 仅显示 WARNING 以上级别,
    logger.info() 不上控制台。此函数将 info 级别同时写入文件日志和
    控制台, 供需要实时查看 info 日志的场景使用(如Agent执行进度)。
    2026-08-30 小欧: print(msg)→console_put(msg), 事件循环线程零同步 stdout 写
    (stdout 阻塞时只丢控制台镜像, 文件日志始终完整).
    """
    logger.info(msg)
    console_put(msg)


__all__ = [
    "SafeRotatingFileHandler",
    "LogConfig",
    "LOG_DIR",
    "setup_logger",
    "APILogger",
    "logger",
    "api_logger",
    "log_and_print",
]

