"""
安全轮转文件处理器 — 单例 handler + 内置 OSError 保护
- 修改人 小欧 2026-07-11
- 根因：7个独立 handler 写同一文件 → Windows rename 文件锁冲突 → PermissionError 死循环
- 修复：全局共享一个 handler，消除竞争；doRollover() 加 OSError 保护
"""

import logging
import logging.handlers
from pathlib import Path
from app.utils.time_utils import now_str
from app.config import get_config

LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


# ============================================================
# LogConfig — 日志配置，委托至 app.config.Config
# ============================================================

class LogConfig:
    """日志配置 — 委托至 app.config.Config — 小欧 2026-07-11"""

    _config = get_config()

    @classmethod
    def is_debug_mode(cls) -> bool:
        return cls._config.get('app.debug', False)

    @classmethod
    def get_log_level(cls) -> str:
        if cls._config.get('app.debug', False):
            return "DEBUG"
        return cls._config.get('logging.level', 'INFO')

    @classmethod
    def get_max_bytes(cls) -> int:
        return cls._config.get('logging.max_file_size', 10 * 1024 * 1024)

    @classmethod
    def get_backup_count(cls) -> int:
        return cls._config.get('logging.backup_count', 5)


# ============================================================
# SafeRotatingFileHandler
# ============================================================

class SafeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """
    安全的轮转文件处理器
    - 日期轮转：detect 日期变更 → 切 baseFilename + reopen
    - 大小轮转：委托 RotatingFileHandler.doRollover()，加 OSError 保护
    - 不分日志名，全应用共享同一个实例（由 setup_logger 保证）
    — 小欧 2026-07-11
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_date = now_str('%Y-%m-%d')

    # ---- 日期轮转 -------------------------------------------------

    def _check_and_rotate_by_date(self):
        """检测日期变更，切 baseFilename 后 reopen — 不新建 handler — 小欧 2026-07-11"""
        today = now_str('%Y-%m-%d')
        if self._current_date == today:
            return
        self._current_date = today
        new_path = str(LOG_DIR / f"app_{today}.log")
        if new_path == self.baseFilename:
            return
        print(f"[Logger] 日期轮转: {self.baseFilename} -> {new_path}")
        self.baseFilename = new_path
        if self.stream:
            self.stream.close()
            self.stream = None
        self.stream = self._open()

    # ---- 大小轮转 -------------------------------------------------

    def doRollover(self):
        """重写：super 失败后恢复流，防止流永久损坏 — 小欧 2026-07-11"""
        try:
            super().doRollover()
        except OSError:
            self.stream = self._open()

    # ---- emit -----------------------------------------------------

    def emit(self, record):
        try:
            self._check_and_rotate_by_date()
        except Exception:
            self.handleError(record)
        super().emit(record)


# ============================================================
# 工具函数
# ============================================================

def _get_log_file_path() -> Path:
    return LOG_DIR / f"app_{now_str('%Y-%m-%d')}.log"
