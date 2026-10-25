
# -*- coding: utf-8 -*-
"""
shared_handler — 全局共享一个 SafeRotatingFileHandler 实例
- 原名 setup_logger.py，2026-07-26 改名 shared_handler.py（名实相符）
- 所有 logger 共用一个文件 handler，消灭多 handler 写同一文件的 Windows rename 锁竞争
"""

# 编辑历史:
# 2026-07-17 - 小欧 - 日志会话维度隔离: 通过 contextvars(context.py) + SessionFilter 将 session_id 注入每条日志记录, formatter 增加 %(session_id)s 字段; 保持全局单例 handler 不变(不破坏 2026-07-11 的 Windows rename 锁竞争修复), 多会话日志可按 session 过滤且不引入多文件描述符, 功能零退化
# 2026-07-26 - 小欧 - setup_logger.py → shared_handler.py 改名（名实相符: 核心是共享 handler 而非 setup_logger 函数）
# 2026-07-30 - 小沈 - 从 task_context.py 迁入 session_id ContextVar: 新增 _session_id_var + set_session_id(); SessionFilter 改为直接引用 _session_id_var 消除延迟导入
# 2026-09-29 - 小欧 - 控制台 handler 换掉同步 logging.StreamHandler(直写 stderr), 改用 ConsoleMirrorHandler(投递队列, 非阻塞): 同一病根第二个入口, 同步写 stderr 阻塞时持 handler 锁连带冻结事件循环线程  小欧-2026-09-29
# 2026-10-25 - 小欧 - 新增 setup_uvicorn_loggers(): uvicorn 三 logger(uvicorn/error/access) 接入共享文件
#   handler(落盘) + ConsoleMirrorHandler(非阻塞上屏)。uvicorn 本体 logger 由自身 dictConfig 装配, 不在
#   setup_logger 管辖内, 须单独收口; 须配合 run_server 传 log_config=None, 否则被覆盖。  小欧-2026-10-25
# 2026-10-25 - 小欧 - 截断阈值 100/120 收敛为单一 _CONSOLE_MAX_MSG=500: 原实现 101~120 字符的消息
#   触发截断但截不到, 提示出现负数(如"截断-9字符"), uvicorn 访问日志高频轮询刷屏; 阈值抬高后访问日志
#   不再触发, 提示数恒正。  小欧-2026-10-25
# 2026-10-25 - 小欧 - uvicorn 三 logger 去掉 ConsoleMirrorHandler, 只保留文件 handler: 访问日志对排障
#   无价值却高频刷屏, 控制台只留 log_and_print 与应用 WARNING+ 日志。  小欧-2026-10-25
# 2026-10-25 - 小欧 - 日志级别热重载: 新增 _managed_loggers 登记表 + refresh_log_levels() 幂等重刷;
#   setup_logger/setup_uvicorn_loggers 装配时登记, 供 main.py 周期 watcher 调用。  小欧-2026-10-25
# 2026-10-25 - 小欧 - refresh 补 formatter 刷新(会审缺陷1): 只改级别不改格式串, debug 切换后 lineno 字段
#   与模式脱节; 现同步重设共享 file handler 的 _build_formatter 与各 console 的 _TruncateConsoleFormatter。
#   get_log_level 单次 get_config()(会审缺陷2)。  小欧-2026-10-25

import logging
from contextvars import ContextVar
from typing import Optional

from app.logger.config import SafeRotatingFileHandler, LogConfig
from app.logger.console_writer import ConsoleMirrorHandler  # 小欧 2026-09-29: 控制台镜像走队列, 禁同步写 stderr

# ---- 会话上下文（session_id），供日志 SessionFilter 注入 — 小沈 2026-07-30 ————

_session_id_var: ContextVar[str] = ContextVar("session_id", default="-")


def set_session_id(sid: str):
    """设置当前协程的 session_id — 请求入口调用"""
    _session_id_var.set(sid)


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
# console 消息体截断阈值: 超此长度才截断并提示。取 500 兼顾两诉求 —
# uvicorn 访问日志(约130字符)完整上屏不刷屏, 同时长日志(如工具原始返回)仍被收敛不撑爆控制台。

_CONSOLE_MAX_MSG = 500


class _TruncateConsoleFormatter(logging.Formatter):
    """console 日志截断 Formatter — 只截断消息体%(message)s，前缀不动 — 小欧 2026-07-11"""
    def format(self, record):
        raw = record.getMessage()
        if len(raw) > _CONSOLE_MAX_MSG:
            record.msg = raw[:_CONSOLE_MAX_MSG] + f"...(截断{len(raw)-_CONSOLE_MAX_MSG}字符)"
            record.args = None
        return super().format(record)


# ---- SessionFilter: 注入 session_id 到日志记录 ---------------------------------
class SessionFilter(logging.Filter):
    """将当前协程上下文的 session_id 注入每条日志记录 — 小欧 2026-07-17
    原理: 从请求作用域的上下文变量读取会话标识写入 record.session_id, 供 formatter 的 %(session_id)s 字段输出;
    默认值为 '-'(无会话上下文时)。变量定义在同一模块, 无循环依赖。
    作用: 多会话并发时日志可按 session 过滤, 且不破坏全局单例 handler 的 Windows 锁修复。
    """
    def filter(self, record: logging.LogRecord) -> bool:
        record.session_id = _session_id_var.get()
        return True


# ---- 公共工具 -----------------------------------------------------

# 已装配 logger 名单: setup_logger/setup_uvicorn_loggers 装配时登记, 供热重载遍历 — 小欧 2026-10-25
_managed_loggers: set = set()


def _get_log_level() -> int:
    """读取配置日志级别 — 小欧 2026-10-25 抽函数(setup_logger 与 setup_uvicorn_loggers 共用)"""
    return getattr(logging, LogConfig.get_log_level().upper())


def _build_fmt(is_debug: bool) -> str:
    """文件/控制台统一格式串 — 小欧 2026-10-25 抽函数复用"""
    if is_debug:
        return '%(asctime)s - %(levelname)s - %(session_id)s - %(filename)s:%(lineno)d - %(message)s'
    return '%(asctime)s - %(levelname)s - %(session_id)s - %(filename)s - %(message)s'


def _build_formatter(is_debug: bool) -> logging.Formatter:
    """文件/控制台统一 formatter — 小欧 2026-10-25"""
    return logging.Formatter(_build_fmt(is_debug), datefmt='%Y-%m-%d %H:%M:%S')


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

    log_level = _get_log_level()
    is_debug = LogConfig.is_debug_mode()

    formatter = _build_formatter(is_debug)

    # 文件 handler — 全局共享
    file_handler = _get_shared_handler()
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    # console handler — 2026-09-29 小欧 换掉 logging.StreamHandler(直写 stderr):
    #   同步写 stderr 遇阻塞型 stderr 时 emit() 永久阻塞, 而 Handler.handle() 持 handler 锁,
    #   连带冻结事件循环线程。改投 ConsoleMirrorHandler 队列, 级别 WARNING, 控制台仅镜像。
    console_handler = ConsoleMirrorHandler(level=logging.WARNING)
    console_handler.setFormatter(
        _TruncateConsoleFormatter(fmt=_build_fmt(is_debug), datefmt='%Y-%m-%d %H:%M:%S')
    )

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.setLevel(log_level)
    logger.propagate = False
    _managed_loggers.add(name)

    return logger


# ---- setup_uvicorn_loggers -------------------------------------------------
# uvicorn 本体 logger 由自身 dictConfig 装配, 不在 setup_logger 管辖内, 单独收口。
# 只挂共享文件 handler(落盘), 不挂 console 镜像: 访问日志高频轮询刷屏且无排障价值。
# 须配合 run_server 传 log_config=None, 否则被 uvicorn 默认 dictConfig 覆盖。

def setup_uvicorn_loggers() -> None:
    """把 uvicorn 三个本体 logger 接入共享文件 handler, 只落盘不上屏 — 小欧 2026-10-25
    幂等: 重复调用先清空 handlers 再装配, 防 dictConfig/重复启动遗留旧 handler。
    访问日志是高频轮询噪音, 对定位问题无帮助, 故不挂 console 镜像; 需查时看文件日志即可。
    """
    is_debug = LogConfig.is_debug_mode()
    formatter = _build_formatter(is_debug)

    file_handler = _get_shared_handler()
    file_handler.setFormatter(formatter)
    file_handler.setLevel(_get_log_level())

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.addHandler(file_handler)
        lg.setLevel(_get_log_level())
        lg.propagate = False
        _managed_loggers.add(name)


def refresh_log_levels() -> None:
    """按当前配置重刷所有已装配 logger 与共享文件 handler 的级别与格式 — 小欧 2026-10-25
    幂等: 配置未变则结果不变。供周期 watcher 调用, 使 config.yaml 的 debug/level 改动免重启生效。
    """
    log_level = _get_log_level()
    is_debug = LogConfig.is_debug_mode()

    file_handler = _get_shared_handler()
    file_handler.setFormatter(_build_formatter(is_debug))
    file_handler.setLevel(log_level)

    for name in list(_managed_loggers):
        lg = logging.getLogger(name)
        if lg.level != log_level:
            lg.setLevel(log_level)
        for h in lg.handlers:
            if isinstance(h, ConsoleMirrorHandler):
                h.setFormatter(
                    _TruncateConsoleFormatter(fmt=_build_fmt(is_debug), datefmt='%Y-%m-%d %H:%M:%S')
                )

