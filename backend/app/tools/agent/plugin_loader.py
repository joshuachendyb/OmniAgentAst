# -*- coding: utf-8 -*-
"""plugin_loader — 插件 manifest 扫描与注册 — 小欧 2026-11-28

编辑历史:
  2026-11-28 - 小欧 - 新增插件扫描器：扫描 plugins_dir 下各子目录的 manifest.json，逐个委托 AgentRegistry.load_from_manifest；
    单个非法 manifest 只 warning 不阻塞启动，目录不存在静默跳过；配置项缺省回落代码库根 plugins 目录
"""
from pathlib import Path
from typing import List

from app.config import get_code_root, get_config
from app.logger import logger
from app.tools.agent.agent_config import get_agent_registry


def _plugins_dir() -> Path:
    """插件目录 — 配置 tuning.agent.plugins_dir 优先，缺省回落代码库根/plugins（小欧 2026-11-28）"""
    configured = get_config().get("tuning.agent.plugins_dir", "") or ""
    return Path(configured) if configured else Path(get_code_root()) / "plugins"


def load_plugins() -> List[str]:
    """扫描并注册全部合法插件，返回成功加载的 agent_id 列表 — 小欧 2026-11-28

    容错契约：单个 manifest 非法由 AgentRegistry.load_from_manifest 记 warning 并返回 None，
    本函数只跳过不抛；目录不存在（含配置未建目录）静默返回空列表，不阻塞启动。
    """
    root = _plugins_dir()
    if not root.is_dir():
        logger.info(f"[plugin_loader] 插件目录不存在，跳过: {root}")
        return []
    loaded: List[str] = []
    registry = get_agent_registry()
    for manifest in sorted(root.glob("*/manifest.json")):
        config = registry.load_from_manifest(str(manifest))
        if config is not None:
            loaded.append(config.agent_id)
    return loaded


__all__ = ["load_plugins"]
