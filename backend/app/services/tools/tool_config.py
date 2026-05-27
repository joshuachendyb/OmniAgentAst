# -*- coding: utf-8 -*-
"""
工具配置模块 - 小健

T2: 配置外部化 + 配置安全机制
参考文档: Omni系统tool-实现分析报告 v1.15 第7.4.2节

创建时间: 2026-04-19 09:00:00
更新时间: 2026-04-19
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


# ============================================================
# 【别名映射表 - 小健 2026-05-02】
# ============================================================

# 工具名称别名从tool_aliases.py统一导入
from app.services.tools.tool_aliases import TOOL_NAME_ALIASES

# 废弃工具列表（不再支持，调用时返回错误提示）
DEPRECATED_TOOLS = {
    # 目前无废弃工具
}


# ============================================================
# 【步骤3】配置Schema验证（Pydantic）
# ============================================================

class ToolTimeoutSchema(BaseModel):
    """工具超时配置Schema"""
    read_file: int = Field(default=10, ge=1, le=3600)
    write_file: int = Field(default=10, ge=1, le=3600)
    default: int = Field(default=5, ge=1, le=3600)


class ToolAliasSchema(BaseModel):
    """工具别名配置Schema"""
    path: Optional[str] = None
    file: Optional[str] = None
    content: Optional[str] = None


class ToolsConfigSchema(BaseModel):
    """工具配置完整Schema"""
    timeouts: ToolTimeoutSchema = Field(default_factory=ToolTimeoutSchema)
    aliases: Dict[str, ToolAliasSchema] = Field(default_factory=dict)


class ToolConfig:
    """
    工具配置管理
    
    功能:
    - 加载YAML配置文件
    - 获取工具超时设置
    - 获取参数别名
    - 配置热重载
    
    使用方式:
        config = ToolConfig()
        timeout = config.get_timeout("read_file")
    """
    
    DEFAULT_TIMEOUT = 5
    DEFAULT_CONFIG_PATH = "config/tools.yaml"
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置
        
        Args:
            config_path: 配置文件路径，默认config/tools.yaml
        """
        self._config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config: Dict[str, Any] = {}
        self._last_modified: Optional[datetime] = None
        self._load_config()
    
    def _load_config(self) -> None:
        """加载配置文件"""
        config_file = Path(self._config_path)
        
        if not config_file.exists():
            logger.warning(f"Config file not found: {self._config_path}, using defaults")
            self._config = self._get_default_config()
            return
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
            
            self._last_modified = datetime.fromtimestamp(config_file.stat().st_mtime)
            logger.info(f"Config loaded: {self._config_path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "tools": {
                "timeouts": {
                    "default": self.DEFAULT_TIMEOUT
                },
                "aliases": {}
            }
        }
    
    def get_timeout(self, tool_name: str) -> int:
        """
        获取工具超时时间
        
        Args:
            tool_name: 工具名称
        
        Returns:
            超时时间（秒）
        """
        timeouts = self._config.get("tools", {}).get("timeouts", {})
        
        # 查找YAML配置的特定超时
        if tool_name in timeouts:
            return timeouts[tool_name]
        
        # YAML中有default则用它
        if "default" in timeouts:
            return timeouts["default"]
        
        # 回退到tool_meta硬编码超时表
        from app.services.tools.tool_meta import TOOL_TIMEOUTS
        return TOOL_TIMEOUTS.get(tool_name, TOOL_TIMEOUTS["default"])
    
    def get_aliases(self, tool_name: str) -> Optional[Dict[str, str]]:
        """
        获取参数别名
        
        Args:
            tool_name: 工具名称
        
        Returns:
            别名dict或None
        """
        aliases = self._config.get("tools", {}).get("aliases", {})
        return aliases.get(tool_name)
    
    # =============================================================================
    # 7.4.3 T3：执行器增强 - 重试配置方法
    # =============================================================================
    
    def get_retry_max(self, tool_name: str) -> int:
        """
        获取最大重试次数
        
        Args:
            tool_name: 工具名称
        
        Returns:
            最大重试次数
        """
        retry = self._config.get("tools", {}).get("retry", {})
        return retry.get(tool_name, retry.get("default", {}).get("max_retries", 3))
    
    def get_retry_backoff(self, tool_name: str) -> float:
        """
        获取重试退避因子
        
        Args:
            tool_name: 工具名称
        
        Returns:
            退避因子
        """
        retry = self._config.get("tools", {}).get("retry", {})
        return retry.get(tool_name, retry.get("default", {}).get("backoff_factor", 2.0))
    
    def get_retryable_errors(self, tool_name: str) -> list:
        """
        获取可重试错误列表
        
        Args:
            tool_name: 工具名称
        
        Returns:
            可重试错误列表
        """
        retry = self._config.get("tools", {}).get("retry", {})
        return retry.get(tool_name, retry.get("default", {}).get("retryable_errors", ["timeout"]))
    
    def reload(self) -> bool:
        """
        【步骤4】热重载原子性保证
        先加载到临时变量，再原子替换
        
        Returns:
            是否重新加载成功
        """
        config_file = Path(self._config_path)
        
        if not config_file.exists():
            logger.warning(f"Config file not found: {self._config_path}")
            return False
        
        # 检查文件是否修改
        current_mtime = datetime.fromtimestamp(config_file.stat().st_mtime)
        if self._last_modified and current_mtime == self._last_modified:
            return False
        
        # 【步骤4】原子性替换：先加载到临时变量
        temp_config = self._load_config_safe()
        if temp_config is not None:
            # 原子替换
            self._config = temp_config
            self._last_modified = current_mtime
            logger.info("Config hot reloaded (atomic)")
            return True
        
        return False
    
    def _load_config_safe(self) -> Optional[Dict[str, Any]]:
        """安全加载配置（带环境变量处理）"""
        try:
            config_file = Path(self._config_path)
            if not config_file.exists():
                return None
            
            with open(config_file, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f) or {}
            
            # 【步骤6】环境变量替换错误处理
            return self._resolve_env_vars(raw_config)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return None
    
    def _resolve_env_vars(self, config: Union[Dict, Any]) -> Union[Dict, Any]:
        """
        【步骤6】环境变量替换
        - 未设置时保留原占位符并记录警告
        - 错误时使用默认值
        """
        if isinstance(config, dict):
            return {k: self._resolve_env_vars(v) for k, v in config.items()}
        elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
            env_var = config[2:-1]
            value = os.environ.get(env_var)
            if value is None:
                # 环境变量未设置：记录警告，保留原始占位符
                logger.warning(f"环境变量 '${{{env_var}}}' 未设置，配置项保留原值")
                return config
            return value
        return config
    
    def validate(self) -> Dict[str, Any]:
        """
        验证配置
        
        Returns:
            验证结果dict
        """
        errors = []
        warnings = []
        
        # 验证超时值
        timeouts = self._config.get("tools", {}).get("timeouts", {})
        for tool_name, timeout in timeouts.items():
            if not isinstance(timeout, int):
                errors.append(f"Timeout for {tool_name} must be int")
            elif timeout <= 0:
                warnings.append(f"Timeout for {tool_name} should be positive")
        
        if errors:
            return {"status": "error", "errors": errors, "warnings": warnings}
        
        return {"status": "success", "warnings": warnings}


# 全局配置实例
tool_config = ToolConfig()


def get_tool_config() -> ToolConfig:
    """获取工具配置实例"""
    return tool_config


def get_timeout(tool_name: str) -> int:
    """获取工具超时时间 — 模块级便捷入口

    【小健 2026-05-27】去重：统一超时查询入口，替代tool_meta.get_timeout()。
    YAML优先 + tool_meta.TOOL_TIMEOUTS兜底。
    """
    return tool_config.get_timeout(tool_name)


def get_tool_name_alias(alias: str) -> Optional[str]:
    """
    获取工具名称的主名 - 小健 2026-05-02
    
    Args:
        alias: 工具别名
    
    Returns:
        主工具名，如果不是别名则返回None
    """
    return TOOL_NAME_ALIASES.get(alias)


def is_deprecated_tool(tool_name: str) -> Optional[str]:
    """
    检查工具是否已废弃 - 小健 2026-05-02
    
    Args:
        tool_name: 工具名称
    
    Returns:
        废弃提示信息，如果未废弃则返回None
    """
    return DEPRECATED_TOOLS.get(tool_name)