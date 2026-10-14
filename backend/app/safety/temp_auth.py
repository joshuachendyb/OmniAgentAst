# 编辑历史:
# 2026-10-14 - 小欧 - 文档[33] 4.1: 本文件由 app/tools/security/ 整文件复制升回 app/safety/(业务逻辑一字不改); 包内互引 1 处(:96)由 app.tools.security.path_safe_check 改同包 app.safety.path_safe_check。
"""
temp_auth — 白名单外路径临时授权(决策记录, 补项)

原则(北京老陈 2026-08-10 裁定, v1.43 M1-M3 修正):
  - 一次一申请: 授权仅针对本次申请的精确路径, 本 task 内有效, task 结束清零;
  - 支持递归: 授权某目录后, 其整个子目录树的递归操作在该授权范围内;
  - task 绑定(补M3): 用 ContextVar 承载, 与 task 作用域绑定, 并发 task 互不干扰;
  - 非系统禁区仅写可任务级授权(3.2.10/3.2.13), 删仍硬拦; 系统禁区永不授权(M1)。

权限模型: ContextVar 存 {授权路径 -> 是否递归} 映射, 只在本 task 作用域内生效。
生命周期: task 级 — grant_temp_auth 后本 task 内持续有效, task 结束 run_react_cycle finally 清零.
"""
from contextvars import ContextVar
from pathlib import Path
from typing import Dict, Optional

# 每 task 的临时授权映射: {授权根(Path) -> 是否递归} — M3: task 级生命周期
_authorized_paths: ContextVar[Dict[Path, bool]] = ContextVar("temp_authorized_paths", default=None)


def get_authorized() -> Dict[Path, bool]:
    """获取当前 task 作用域的授权映射 — 小欧 2026-08-10, M3 更新"""
    auth = _authorized_paths.get()
    if auth is None:
        return {}
    return auth


def _ensure_auth() -> Dict[Path, bool]:
    """确保当前 task 作用域存在授权映射, 返回之 — 小欧 2026-08-10"""
    auth = _authorized_paths.get()
    if auth is None:
        auth = {}
        _authorized_paths.set(auth)
    return auth


def grant_temp_auth(root: str, recursive: bool = True) -> None:
    """临时授权某路径(本 task 内有效, task 结束清零) — 小欧 2026-08-10, M3 更新
    [SA6] 权限信任框架第6步写入点: SA1/HITL确认后grant, SA5校验内is_temp_authorized读取 — 小欧-2026-10-14
    Args:
        root: 授权根路径
        recursive: True=授权根及其子目录树; False=仅精确路径
    """
    # 2026-09-03 小欧 修复: 空/根路径前置拒绝（Path("").resolve()得cwd扩域根治）
    if not root or (isinstance(root, str) and root.strip() in ("", ".", "/")):
        from app.logger import logger as _lg
        _lg.warning(f"[temp_auth] 空/根路径拒绝授权: {root!r}")
        return
    # 2026-09-03 小欧 修复: 文件路径(有后缀)强制recursive False，仅目录保持True，防task级目录越权
    _recursive = recursive
    if recursive and isinstance(root, str) and Path(root).suffix:
        _recursive = False
    _ensure_auth()[Path(root).resolve()] = _recursive
    # 2026-09-03 小欧/北京老陈: 授权操作补日志
    from app.logger import logger as _lg
    _lg.info(f"[temp_auth] 授权: root={root}, recursive={_recursive}")


def clear_temp_auth() -> None:
    """清空当前作用域临时授权(task 结束调用) — 小欧 2026-08-10, M3 更新
    [SA6] task结束清零点(run_react_cycle finally) — 小欧-2026-10-14"""
    # 2026-09-03 小欧/北京老陈: 清空授权补日志
    from app.logger import logger as _lg
    auth = _authorized_paths.get()
    _count = len(auth) if auth else 0
    _lg.info(f"[temp_auth] 清空授权: cleared={_count}项")
    _authorized_paths.set({})


def is_temp_authorized(file_path: str) -> bool:
    """检查路径是否在当前作用域临时授权范围内 — 小欧 2026-08-10
    M2 (v1.43): 前置禁区分类(深度防御, 无 mode 参数):
        - 系统禁区 → 即使入单也返回 False(永不授权);
        - 非系统禁区写放行判定在 validate_path 写 mode 分支内完成,
          is_temp_authorized 仅做 auth-list 匹配, 不再硬拦(删已在 validate_path 删除规则硬拦)
    支持递归: 授权目录后其子目录树一并放行。
    [SA6] 权限信任框架第6步读取点: SA5路径校验内调用 — 小欧-2026-10-14
    """
    # M2: depth defense — 系统禁区永不授权(即使入单也False)
    try:
        from app.safety.path_safe_check import _is_forbidden_path  # 惰性导入避免循环依赖
        category, _ = _is_forbidden_path(file_path)
        if category == "system":
            return False
    except Exception:
        pass  # 异常不阻断, 继续走下文 auth-list 匹配(深度防御不影响主流程)

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
                # 2026-09-03 小欧/北京老陈: 授权命中补日志
                from app.logger import logger as _lg
                _lg.info(f"[temp_auth] 授权命中: file={file_path}, root={root}, recursive=True")
                return True
        else:
            if p == root:
                from app.logger import logger as _lg
                _lg.info(f"[temp_auth] 授权命中: file={file_path}, root={root}, recursive=False")
                return True
    return False


__all__ = ["grant_temp_auth", "clear_temp_auth", "is_temp_authorized",
           "get_authorized"]
