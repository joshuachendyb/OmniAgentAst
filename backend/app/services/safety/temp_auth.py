# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-10 - 小欧 - 新建: 白名单外路径临时授权(⑮) — 一次一申请+支持递归+per-request隔离(补A)
"""
temp_auth — 白名单外路径临时授权(3.3决策⑤, 文档7.8-5, 补A)

原则(北京老陈 2026-08-10 裁定):
  - 一次一申请: 授权仅针对本次申请的精确路径, 本次操作结束后即失效, 不缓存复用;
  - 支持递归: 授权某目录后, 其整个子目录树的递归操作在该授权范围内;
  - per-request隔离(补A): 用 ContextVar 承载, 与请求/任务作用域绑定, 并发请求互不干扰;
  - 代码库根(⑦)不参与临时授权: tool 禁区不受任何授权影响, 永久封锁。

权限模型: ContextVar 存 {授权路径 -> 是否递归} 映射, 只在本请求作用域内生效。
"""
from contextvars import ContextVar
from pathlib import Path
from typing import Dict, Optional

# 每请求的临时授权映射: {授权根(Path) -> 是否递归}
_authorized_paths: ContextVar[Dict[Path, bool]] = ContextVar("temp_authorized_paths", default=None)


def get_authorized() -> Dict[Path, bool]:
    """获取当前作用域的授权映射 — 小欧 2026-08-10"""
    auth = _authorized_paths.get()
    if auth is None:
        return {}
    return auth


def _ensure_auth() -> Dict[Path, bool]:
    """确保当前作用域存在授权映射, 返回之 — 小欧 2026-08-10"""
    auth = _authorized_paths.get()
    if auth is None:
        auth = {}
        _authorized_paths.set(auth)
    return auth


def grant_temp_auth(root: str, recursive: bool = True) -> None:
    """临时授权某路径(本次操作有效, 支持递归) — 小欧 2026-08-10
    Args:
        root: 授权根路径
        recursive: True=授权根及其子目录树; False=仅精确路径
    """
    _ensure_auth()[Path(root).resolve()] = recursive


def clear_temp_auth() -> None:
    """清空当前作用域临时授权(本次操作结束) — 小欧 2026-08-10"""
    _authorized_paths.set({})


def is_temp_authorized(file_path: str) -> bool:
    """检查路径是否在当前作用域临时授权范围内 — 小欧 2026-08-10
    支持递归: 授权目录后其子目录树一并放行。
    """
    auth = get_authorized()
    if not auth:
        return False
    try:
        p = Path(file_path).resolve()
    except Exception:
        return False
    for root, recursive in auth.items():
        if recursive:
            if p == root or root in p.parents:
                return True
        else:
            if p == root:
                return True
    return False


__all__ = ["grant_temp_auth", "clear_temp_auth", "is_temp_authorized",
           "get_authorized"]
