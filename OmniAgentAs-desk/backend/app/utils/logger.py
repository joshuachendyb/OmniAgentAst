"""
日志工具模块
用于记录API请求和响应日志
支持debug模式和生产模式
"""

import logging
import logging.handlers
import os
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

# 日志目录
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

class LogConfig:
    """日志配置管理"""
    
    _config = None
    
    @classmethod
    def load_config(cls) -> dict:
        """从配置文件加载日志配置"""
        if cls._config is not None:
            return cls._config
        
        config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                cls._config = config.get("logging", {})
        except Exception as e:
            print(f"[Logger] 无法加载配置文件，使用默认配置: {e}")
            cls._config = {}
        
        return cls._config
    
    @classmethod
    def is_debug_mode(cls) -> bool:
        """检查是否为debug模式"""
        config = cls.load_config()
        app_config = config.get("app", {})
        return app_config.get("debug", False)
    
    @classmethod
    def get_log_level(cls) -> str:
        """获取日志级别"""
        config = cls.load_config()
        level = config.get("level", "INFO")
        # debug模式下使用DEBUG级别
        if cls.is_debug_mode():
            return "DEBUG"
        return level
    
    @classmethod
    def get_max_bytes(cls) -> int:
        """获取单个日志文件最大大小（字节）"""
        config = cls.load_config()
        return config.get("max_file_size", 10 * 1024 * 1024)  # 默认10MB
    
    @classmethod
    def get_backup_count(cls) -> int:
        """获取备份文件数量"""
        config = cls.load_config()
        return config.get("backup_count", 5)

def setup_logger(name: str) -> logging.Logger:
    """
    设置并返回logger实例
    
    Args:
        name: logger名称
        
    Returns:
        logging.Logger: 配置好的logger
    """
    logger = logging.getLogger(name)
    
    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger
    
    # 获取配置
    log_level = getattr(logging, LogConfig.get_log_level().upper())
    is_debug = LogConfig.is_debug_mode()
    
    # 设置日志级别
    logger.setLevel(log_level)
    
    # 日志格式
    if is_debug:
        # Debug模式：详细格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        )
    else:
        # 生产模式：简洁格式
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
    
    # 文件处理器 - 带轮转
    log_file = LOG_DIR / f"app_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=LogConfig.get_max_bytes(),
        backupCount=LogConfig.get_backup_count(),
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)
    logger.addHandler(file_handler)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    # 生产模式下控制台只显示WARNING及以上
    console_handler.setLevel(logging.DEBUG if is_debug else logging.WARNING)
    logger.addHandler(console_handler)
    
    return logger

# 创建主logger
logger = setup_logger("OmniAgentAst")

class APILogger:
    """API请求日志记录器"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.logger = setup_logger("OmniAgentAst.API")
            cls._instance.debug_mode = LogConfig.is_debug_mode()
        return cls._instance
    
    def _should_log(self, level: int) -> bool:
        """检查是否应该记录该级别日志"""
        return self.logger.isEnabledFor(level)
    
    def log_request(self, provider: str, model: str, message_len: int, history_count: int = 0):
        """记录请求开始"""
        self.logger.info(
            f"[{provider}] 请求开始 | 模型: {model} | 消息长度: {message_len} | 历史消息数: {history_count}"
        )
        if self.debug_mode:
            self.logger.debug(f"[{provider}] 调试模式: 消息内容长度={message_len}")
    
    def log_response(self, provider: str, status_code: int, content_len: int = 0, error: str = None):
        """记录响应"""
        if error:
            self.logger.error(
                f"[{provider}] 响应错误 | 状态码: {status_code} | 错误: {error}"
            )
        else:
            self.logger.info(
                f"[{provider}] 响应成功 | 状态码: {status_code} | 内容长度: {content_len}"
            )
    
    def log_timeout(self, provider: str, timeout_seconds: int):
        """记录超时"""
        self.logger.warning(
            f"[{provider}] 请求超时 | 超时时间: {timeout_seconds}秒"
        )
    
    def log_switch(self, from_provider: str, to_provider: str, success: bool, reason: str = None):
        """记录提供商切换"""
        if success:
            self.logger.info(f"[切换] {from_provider} -> {to_provider} | 成功")
        else:
            self.logger.error(
                f"[切换] {from_provider} -> {to_provider} | 失败 | 原因: {reason}"
            )
    
    def log_validation(self, provider: str, model: str, success: bool, message: str):
        """记录服务验证"""
        if success:
            self.logger.info(f"[{provider}] 验证成功 | 模型: {model}")
        else:
            self.logger.warning(
                f"[{provider}] 验证失败 | 模型: {model} | 原因: {message}"
            )
    
    def log_error(self, provider: str, error: str, exc_info: Exception = None):
        """记录详细错误信息"""
        if exc_info and self.debug_mode:
            self.logger.exception(f"[{provider}] 异常: {error}")
        else:
            self.logger.error(f"[{provider}] 错误: {error}")

# 全局实例
api_logger = APILogger()
