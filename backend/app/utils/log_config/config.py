"""
日志配置管理
委托至 app.config.Config（消除重复文件读取）
"""


class LogConfig:
    """日志配置管理 — 委托至 app.config.Config（消除重复文件读取）"""

    @classmethod
    def load_config(cls) -> dict:
        """获取日志配置（通过 Config 缓存）"""
        from app.config import get_config
        return get_config().get_log_config()

    @classmethod
    def is_debug_mode(cls) -> bool:
        """检查是否为debug模式"""
        from app.config import get_config
        return get_config().get('app.debug', False)

    @classmethod
    def get_log_level(cls) -> str:
        """获取日志级别"""
        from app.config import get_config
        level = get_config().get('logging.level', 'INFO')
        if get_config().get('app.debug', False):
            return "DEBUG"
        return level

    @classmethod
    def get_max_bytes(cls) -> int:
        """获取单个日志文件最大大小（字节）"""
        from app.config import get_config
        return get_config().get('logging.max_file_size', 10 * 1024 * 1024)

    @classmethod
    def get_backup_count(cls) -> int:
        """获取备份文件数量"""
        from app.config import get_config
        return get_config().get('logging.backup_count', 5)
