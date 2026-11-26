# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-26 - 小欧 - 新建: 环境变量名集中单点(env_keys)。值源统一为 config.yaml 单一真源,
#   env 仅降级为覆盖口(部署统一配置 / 自动化测试定向), 统一以 OMNI_ 前缀与 _MB/_DAYS 等
#   单位后缀命名; 提供 env_nonempty/env_flag/deprecated_in_use 三个公用判定, 集中旧名告警。
"""env_keys — 环境变量名与判定单点

值源: config.yaml 是唯一真源; 本文件只定义"覆盖口"的名字。
命名: 统一 OMNI_ 前缀; 单位进名(_MB / _DAYS); 布尔用正向词, 命名以 _ENABLED 结尾。
职责: 常量为纯字符串、helper 只依赖 os, 供 config/deps/main 早期导入, 严禁反向 import。
"""
import os
from typing import Dict, List, Tuple

# 路径类(留)
CONFIG_PATH = "OMNI_CONFIG_PATH"              # 覆盖 config.yaml 路径
DATA_DIR = "OMNI_DATA_DIR"                    # 覆盖数据根目录(测试隔离 / 便携数据)
# 鉴权类(留; 安全核心路径)
ACCESS_TOKEN = "OMNI_ACCESS_TOKEN"            # 访问口令(env 优先于 config)
ACCESS_TOKEN_ALLOWLIST = "OMNI_ACCESS_TOKEN_ALLOWLIST"
REQUIRE_AUTH = "OMNI_REQUIRE_AUTH"            # 仅开发/测试显式关闭(默认开)
# 迁移进配置文件的覆盖口
ENABLE_API_DOCS = "OMNI_ENABLE_API_DOCS"      # 覆盖 server.enable_api_docs
ATTACHMENTS_TRUSTED_PROXIES = "OMNI_ATTACHMENTS_TRUSTED_PROXIES"  # 覆盖 network.attachments_trusted_proxies
# 进程域覆盖口(无 config 键; 并发度由 max(12, shell_max) 推导, 此处仅部署级覆盖)
PROC_HANDSHAKE = "OMNI_PROC_HANDSHAKE"        # 主进程 -> 宿主 握手串(base64 JSON, 内部专用)
PROC_CONCURRENCY = "OMNI_PROC_CONCURRENCY"   # 覆盖宿主并发度
PROC_MAX_OUTPUT_MB = "OMNI_PROC_MAX_OUTPUT_MB"  # 覆盖 tuning.shell_fg_max_output_mb(单位 MB)
# 排障类(留)
DEBUG_KEEP_CONSOLE = "OMNI_DEBUG_KEEP_CONSOLE"
DEBUG_SPAWN_STRICT = "OMNI_DEBUG_SPAWN_STRICT"

# 旧名 -> 新名(改名前必须设值; 未使用则忽略)。启动时由 deprecated_in_use() 收集告警。
DEPRECATED: Dict[str, str] = {
    # 路径与鉴权
    "OMNIAGENT_CONFIG_PATH": CONFIG_PATH,
    "OMNIAGENT_DATA_DIR": DATA_DIR,
    "OMNIAGENT_ACCESS_TOKEN": ACCESS_TOKEN,
    "OMNIAGENT_ACCESS_TOKEN_ALLOWLIST": ACCESS_TOKEN_ALLOWLIST,
    "OMNIAGENT_REQUIRE_AUTH": REQUIRE_AUTH,
    # 迁移进配置
    "OMNIAGENT_ENABLE_API_DOCS": ENABLE_API_DOCS,
    "ATTACHMENTS_TRUSTED_PROXIES": ATTACHMENTS_TRUSTED_PROXIES,
    # 进程域(旧 5 个注入变量已并入手柄握手串, 仅作启动告警以免排障误设)
    "OMNI_PROC_HOST": "已删除(宿主单路径自动生效, 无需设置)",
    "OMNI_PROC_HOST_PIPE": f"{PROC_HANDSHAKE}(内部), 改用 {PROC_HANDSHAKE}",
    "OMNI_PROC_HOST_KEY": f"{PROC_HANDSHAKE}(内部), 改用 {PROC_HANDSHAKE}",
    "OMNI_PROC_HOST_PARENT_PID": f"{PROC_HANDSHAKE}(内部), 改用 {PROC_HANDSHAKE}",
    "OMNI_PROC_HOST_LOG": f"{PROC_HANDSHAKE}(内部), 改用 {PROC_HANDSHAKE}",
    "OMNI_PROC_HOST_CONCURRENCY": PROC_CONCURRENCY,
    "OMNI_PROC_HOST_MAX_OUTPUT": f"{PROC_MAX_OUTPUT_MB}(单位改为 MB)",
    # 排障
    "OMNI_KEEP_CONSOLE": DEBUG_KEEP_CONSOLE,
    "OMNI_SPAWN_STRICT": DEBUG_SPAWN_STRICT,
}

# 已彻底删除(无新名): 残留会误导并造成"设了不生效", 启动时告警并提示删除。
REMOVED: Dict[str, str] = {
    "AI_PROVIDER": "已删除(改用 ai.model_ref.provider 配置键)",
    "LOG_LEVEL": "已删除(改用 logging.level 配置键)",
    "CORS_ORIGINS": "已删除(改用 network.cors_origins 配置键)",
    "OMNIAGENT_CHAT_RETENTION_DAYS": "已删除(改用 system.chat_retention_days 配置键)",
}


def deprecated_in_use() -> List[Tuple[str, str]]:
    """返回仍在使用的旧/已删变量 [(名称, 处理指引)]; 无则空列表。"""
    found: List[Tuple[str, str]] = []
    for old, new in DEPRECATED.items():
        if env_nonempty(old):
            found.append((old, f"改用 {new}"))
    for removed, new in REMOVED.items():
        if env_nonempty(removed):
            found.append((removed, new))
    return found


def env_nonempty(name: str) -> bool:
    """返回环境变量是否非空且非纯空白。"""
    v = os.environ.get(name)
    return bool(v and v.strip())


def env_flag(name: str, default: str = "0") -> bool:
    """布尔型环境变量: 值在 {空, 0, false}(忽略大小写)视为关, 其余视为开。

    统一为假值列表(凡不是显式关闭就算开), 替代各处手搓真值列表。
    """
    return (os.environ.get(name) or default).strip().lower() not in ("", "0", "false")
