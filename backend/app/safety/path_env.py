# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-15 - 小欧 - 新建: 拆自 path_safe_check 的磁盘枚举 + 白名单构建。
#   逐字搬迁只改 import 路径, 业务逻辑一字不改:
#     get_system_drive          真实系统盘符三级探测
#     get_default_allowed_paths 默认白名单 = 主目录+tmp+项目根+授权目录+会话工作区
#     FALLBACK_SYSTEM_DRIVE     模块级常量, 仅 get_system_drive 消费
#   拆分理由: 这两件事是"环境事实查询"(磁盘/配置/工作区), 与"路径是否属禁区"是两种
#   关注点; classify_forbidden_path 只因要拿系统盘符才与本模块相邻, 属依赖而非同职。
#   本模块不含任何安全判定, 不读 security.hitl.enabled。
# 2026-10-15 - 小欧 - 死代码删除(实测生产引用为 0):
#   get_existing_drives / _get_project_root_safety 生产零消费, 按 YAGNI 删除;
#   FALLBACK_SYSTEM_DRIVE 保留定义(仅 get_system_drive 内部消费), 仅移出 __all__。
# 2026-10-15 - 小欧 - 改名 path_scope.py -> path_env.py: 内容是环境事实查询(盘符/临时目录/白名单), 与 scope 无关。
# 2026-10-18 小欧 - 开关键名随设置项分组前缀跟定为 security.hitl.enabled(模块头"不读该开关"的表述同步),
#   本模块不含安全判定, 取数逻辑零变更。同批清理注释中的 P0-x / P3-x 编号, 技术说明原样保留。
"""
path_env — 路径可用范围: 系统盘符 + 白名单构建

回答一个问题: **哪些路径允许操作?**

与相邻两个模块的分工:
  path_env      本模块 —— 哪里能用(读磁盘/配置/会话工作区)
  path_classify_category      是什么路径(纯判定, 不读开关)
  path_check_common 怎么查(三线共用的判定步骤)

消费方: path_check_common.resolve_allowed_paths → 白名单比对;
        path_classify_category.classify_forbidden_path → 取系统盘符。

小欧 2026-10-15
"""

import os
from pathlib import Path
from typing import List

# 2026-10-15 - 小欧 - 分层去反向依赖: 会话工作区取数收归 app/tools/context.py, 由本层传入 utils 单源。
from app.logger import logger
from app.session_workspace import session_workspace_paths  # 2026-10-15 - 小欧 - 分层: 快照组迁中立层, 解 safety→tools 越层
from app.utils.path_utils import get_allowed_roots

# 2026-10-06 小欧 - 系统盘符三级探测全部失败时的缺省值(唯一消费方就是 get_system_drive)
FALLBACK_SYSTEM_DRIVE = "C:"


def get_system_drive() -> str:
    """动态获取真实系统盘符(安全检查时刻) — 小欧 2026-08-04
    写死C:作默认模板不足, 运行时动态替换为真实系统盘符(支持系统盘非C:/盘符重映射, 不漏判不误伤)。
    优先级: SystemRoot/WINDIR 环境变量 → SystemDrive → 探测存在\\Windows的盘符 → 缺省 C:
    返回带冒号的盘符如 "C:" 或 "D:"(无反斜杠)"""
    for var in ("SystemRoot", "WINDIR"):
        root = os.environ.get(var)
        if root:
            drive, _ = os.path.splitdrive(root)
            if drive:
                return drive
    sdrive = os.environ.get("SystemDrive", "")
    if sdrive:
        return sdrive.rstrip("\\/")
    if os.name == "nt":
        for c in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            if os.path.isdir(f"{c}:\\Windows"):
                return f"{c}:"
    return FALLBACK_SYSTEM_DRIVE


def _system_temp_dir() -> Path:
    """系统临时目录 — 小欧 2026-10-15

    原代码硬编码 /tmp 与 /var/tmp。实测 Windows 上 Path("/tmp") 解析为**当前盘符根**下的
    \\tmp(即 F:\\tmp), 有两个问题: 随启动盘符漂移; 该路径可预测, 任何人创建即自动
    成为白名单目录。现 Windows 取 TEMP/TMP 环境变量(系统真实临时目录), 其它平台沿用 /tmp。
    """
    if os.name == "nt":
        temp = os.environ.get("TEMP") or os.environ.get("TMP")
        if temp:
            return Path(temp)
    return Path("/tmp")


def get_default_allowed_paths() -> List[Path]:
    """获取默认允许的路径列表 — 小沈 2026-06-17 从file_tools提取
    白名单=主目录+系统临时目录+项目根+授权目录+会话工作区。
    """
    paths = [Path.home(), _system_temp_dir()]
    # 2026-10-15 小欧 - 原裸调 get_allowed_roots(config 故障会抛), 异常冒泡致全盘判 system 硬拦。
    #   改为降级最小白名单: 收窄=更多路径需授权=更严, 既不放权也不瘫。
    try:
        paths.extend(get_allowed_roots(session_workspace_paths()))
    except Exception as e:
        logger.warning(f"[path_env] 读取允许根失败, 白名单降级为主目录+tmp: {e}")
    return paths


__all__ = ["get_system_drive", "get_default_allowed_paths"]
