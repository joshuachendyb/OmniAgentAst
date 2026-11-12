"""
安全轮转文件处理器 — 单例 handler + 内置 OSError 保护
- 修改人 小欧 2026-07-11
- 根因：7个独立 handler 写同一文件 → Windows rename 文件锁冲突 → PermissionError 死循环
- 修复：全局共享一个 handler，消除竞争；doRollover() 加 OSError 保护
"""
# 编辑历史:
# 2026-08-30 - 小欧 - 控制台写离线化(挂起根治): _check_and_rotate_by_date 轮转提示 print→console_put(日志emit路径零同步stdout写)
# 2026-09-19 - 小欧 - exe打包frozen支持: LOG_DIR frozen时改走exe所在目录/logs(源码保持backend/logs不变) - 小欧-2026-09-19
# 2026-09-21 - 小欧 - v4.20 键名按域收敛: app.debug → logging.debug（is_debug_mode/get_log_level 读键同步）
# 2026-10-25 - 小欧 - LogConfig 方法改调 get_config() 取实时值, 删导入期类属性快照:
#   get_config() 内置 mtime 缓存未变则直接返回, 零额外成本; 配置改动无需重启即被读取感知。 - 小欧-2026-10-25
# 2026-10-25 - 小欧 - get_log_level 单次 get_config() 提 cfg 局部变量: 消双重 stat。 - 小欧-2026-10-25
# 2026-11-03 - 小欧 - LogConfig 新增 get_console_level()(logging.console_level, 默认 WARNING 零行为变化),
#   控制台显示阈值与文件日志解耦; 供 shared_handler 装配/热重载读 — 小欧-2026-11-03
# 2026-11-03 - 小欧 - get_log_level→get_file_level, 键 logging.level→logging.file_level(名副其实, 唯一管文件):
#   调试模式开启时仍强制 DEBUG — 小欧-2026-11-03
# 2026-11-03 - 小欧 - 新增 get_console_level_int(): 控制台级别字符串→int 的唯一换算点, shared_handler 与
#   log_and_print 共用; 原换算散在 shared_handler 私有函数, 被 __init__ 跨模块导入 — 小欧-2026-11-03
# 2026-11-03 - 小欧 - console_level 语义定为「精确档位」: 控制台只出 == 该级别的记录(不是 >= 阈值), 文件仍 >= 阈值 — 小欧-2026-11-03
# 2026-11-03 - 小欧 - 换算下沉 levels.to_level_int(DRY), 本类只传 default=WARNING — 小欧-2026-11-03
# 2026-11-03 - 小欧 - 撤销双键(北京老陈令: 一个值即可): 键回到单键 logging.level, 新增 get_log_level() 取原值;
#   get_console_level_int() 读同一原值, 控制台只显示 == 该值的行 — 小欧-2026-11-03
# 2026-11-03 - 小欧 - 删 get_file_level() 纯中转层(三跳违反 KISS-DIRECT): 调试强制下沉到唯一消费点
#   shared_handler._get_file_level — 小欧-2026-11-03
# 2026-11-12 - 小欧 - 日期轮转两处修正: ①新文件按 handler 自身 baseFilename 目录派生, 原用全局 LOG_DIR
#   致自定义目录构造的 handler 轮转跳到 LOG_DIR; ②_current_date 改为 reopen 成功后提交, 原先提交再 _open,
#   失败后当日不再重试且后续写入落到旧日文件 — 小欧-2026-11-12

import logging
import logging.handlers
from pathlib import Path

from app.config import get_config, get_frozen_dir
from app.logger.levels import to_level_int  # 2026-11-03 小欧: 级别名→int 唯一换算点(DRY)
from app.utils.time_utils import now_str

_frozen = get_frozen_dir()
LOG_DIR = (_frozen / "logs") if _frozen is not None else Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


# ============================================================
# LogConfig — 日志配置，委托至 app.config.Config
# ============================================================

class LogConfig:
    """日志配置 — 委托至 app.config.Config — 小欧 2026-07-11
    2026-10-25 小欧 - 方法改调 get_config() 取实时值(其内 mtime 缓存, 未变则直接返回, 零额外成本):
    不再在导入期绑定类属性快照, 配置文件改动后无需重启即被后续读取感知。
    """

    @classmethod
    def is_debug_mode(cls) -> bool:
        # 2026-09-21 小欧 v4.20 键名按域收敛: app.debug → logging.debug
        return get_config().get('logging.debug', False)

    @classmethod
    def get_log_level(cls) -> str:
        """日志级别(logging.level, 配置原值) — 小欧-2026-11-03

        一个键两种用法(北京老陈定, 不再拆 console_level):
        - 控制台: 只显示「级别 == 该值」的行(精确匹配), 见 get_console_level_int;
        - 日志文件: 记「级别 >= 该值」(logging 常规阈值), 调试强制在唯一消费点
          shared_handler._get_file_level() 内施加 —— 本类不再多出一层纯中转的 get_file_level()。
        """
        return str(get_config().get('logging.level', 'INFO')).upper()

    @classmethod
    def get_console_level_int(cls) -> int:
        """控制台级别→logging 整数级别(唯一换算点) — 小欧-2026-11-03

        shared_handler 装配/热重载、ConsoleMirrorHandler 精确档位判定与 log_and_print 上屏判定同读此函数;
        换算复用 levels.to_level_int(DRY), 配置值非法时回落 WARNING, 不让坏配置放大控制台噪音。
        读的是 logging.level 原值(不取调试模式强制后的 DEBUG) — 小欧-2026-11-03
        """
        return to_level_int(cls.get_log_level(), logging.WARNING)

    @classmethod
    def get_max_bytes(cls) -> int:
        return get_config().get('logging.max_file_size', 10 * 1024 * 1024)

    @classmethod
    def get_backup_count(cls) -> int:
        return get_config().get('logging.backup_count', 5)


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
        new_path = str(Path(self.baseFilename).parent / f"app_{today}.log")
        if new_path == self.baseFilename:
            self._current_date = today
            return
        from app.logger.console_writer import (
            console_put,  # 小欧 2026-08-30 轮转提示离线化(日志emit路径零同步stdout写)
        )
        console_put(f"[Logger] 日期轮转: {self.baseFilename} -> {new_path}")
        self.baseFilename = new_path
        if self.stream:
            self.stream.close()
            self.stream = None
        self.stream = self._open()
        self._current_date = today

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
