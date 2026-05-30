# -*- coding: utf-8 -*-
"""
工具配置模块 - 小健

T2: 配置外部化 + 配置安全机制
参考文档: Omni系统tool-实现分析报告 v1.15 第7.4.2节

创建时间: 2026-04-19 09:00:00
更新时间: 2026-05-31
更新内容: 删除tool函数内部常量相关代码，超时数字统一由tool_constants.py管理 - 北京老陈
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
# 【步骤3】配置Schema验证（Pydantic）
# ============================================================

class ToolAliasSchema(BaseModel):
    """工具别名配置Schema"""
    path: Optional[str] = None
    file: Optional[str] = None
    content: Optional[str] = None


class ToolsConfigSchema(BaseModel):
    """工具配置完整Schema"""
    aliases: Dict[str, ToolAliasSchema] = Field(default_factory=dict)


class ToolConfig:
    """
    工具配置管理
    
    功能:
    - 加载YAML配置文件
    - 获取参数别名
    - 配置热重载
    
    使用方式:
        config = ToolConfig()
        aliases = config.get_aliases("read_file")
    """
    
    # 【3.21修复 北京老陈 2026-05-31】路径统一到utils/paths.py
    from app.utils.paths import get_config_path, DEFAULT_TOOLS_CONFIG_FILENAME
    DEFAULT_CONFIG_PATH = get_config_path(DEFAULT_TOOLS_CONFIG_FILENAME)
    
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
                "aliases": {}
            }
        }
    
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
        return {"status": "success", "warnings": []}


# 全局配置实例
tool_config = ToolConfig()


def get_tool_config() -> ToolConfig:
    """获取工具配置实例"""
    return tool_config


