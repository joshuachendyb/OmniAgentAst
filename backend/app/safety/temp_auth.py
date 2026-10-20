# 编辑历史:
# 2026-10-14 - 小欧 - 本文件由 app/tools/security/ 整文件迁移至 app/safety/(业务逻辑一字不改); 包内互引由 app.tools.security.path_safe_check 改为同包 app.safety.path_safe_check。
# 2026-10-18 - 小欧 - 授予范围判定上提为共用原子: 新增 resolve_grant_recursive —— 授权实际生效的 recursive(有后缀=单文件只放精确路径、无后缀=目录放整棵子树)是"授予自由度"的真值源, 原为 grant_temp_auth 内联; 现由 HITL 弹窗的授权影响面展示一并消费, 两处同口径、杜绝"授权给了整子树、界面显示单文件"的偏差。同时抽出 _is_rejectable_root 承载空/根路径拒绝判据(Path("") resolve 成 cwd 会把整个当前目录放开, 属安全关键判据, 不宜两处各写一份)。纯等价重构, 授权行为零变化。
# 2026-10-19 小欧 - 补漏: _is_rejectable_root 原只拒 ""/./"/", 漏 Windows 盘根(C:\ D:\ ...)——
#   splitdrive 后尾段为空即盘根, 授权它等于递归放开整盘(实测 resolve_grant_recursive('C:\\',True)=True)。
#   现盘根纳入拒绝线; 顺带非字符串一律拒绝(fail-closed)。授权/影响面两处同源, 一并生效。
# 2026-10-20 05:27 小欧 - FIX resolve_grant_recursive: 目录判定原用后缀启发式(Path.suffix),
#   目录名含点(如 E:\dir\v1.0)被误判为"文件"使递归授权静默失效; 已存在者改 os.path.isdir/isfile
#   真实类型判定, 不存在者维持后缀口径。授权行为对存量目录零退化, 文件仍单精确授权。
"""
temp_auth — 白名单外路径临时授权(决策记录, 补项)

原则(v1.43 M1-M3 修正):
  - 一次一申请: 授权仅针对本次申请的精确路径, 本 task 内有效, task 结束清零;
  - 支持递归: 授权某目录后, 其整个子目录树的递归操作在该授权范围内;
  - task 绑定(补M3): 用 ContextVar 承载, 与 task 作用域绑定, 并发 task 互不干扰;
  - 非系统禁区仅写可任务级授权(3.2.10/3.2.13), 删仍硬拦; 系统禁区永不授权(M1)。

权限模型: ContextVar 存 {授权路径 -> 是否递归} 映射, 只在本 task 作用域内生效。
生命周期: task 级 — grant_temp_auth 后本 task 内持续有效, task 结束 run_react_cycle finally 清零.
"""
import os
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


def _is_rejectable_root(root) -> bool:
    r"""空/根路径判定(授权拒绝线) — 小欧 2026-10-18

    判定为真表示**不可授权**: 空串/None/纯空白, 以及 "." "/" 与 Windows 盘根(C:\ D:\ ...)
    这类根路径 —— 授权根路径等于把整个(盘/当前目录)一次性放开。

    上提成独立原子: 授权写入(grant_temp_auth) 与影响面判定(resolve_grant_recursive)
    必须同口径, 判据两处并存必然"改一处漏一处"。
    """
    if not root or not isinstance(root, str):
        return True
    s = root.strip()
    if s in ("", ".", "/"):
        return True
    drive, tail = os.path.splitdrive(s)
    if drive and tail.strip("\\/") == "":
        return True                                 # 盘根 C:\ C: 亦不可授权(否则整盘放开)
    return False


def resolve_grant_recursive(root: str, requested: bool = True) -> bool:
    """给定授权根, 返回**实际生效**的 recursive —— 授予自由度真值源 — 小欧 2026-10-18

    规则(自 grant_temp_auth 内联逻辑上提):
      文件路径(Path(root).suffix 非空) → False, 只授权该精确文件
      目录路径(suffix 为空)           → True, 授权根及其整棵子目录树

    为何必须上提为共用原子: 这是"授权写入"与"授权影响面展示"的唯一口径来源。
    两处各判一次, 必然出现授权按目录给了整子树、界面却按单文件显示影响面小 的偏差。

    Args:
        root: 授权根路径
        requested: 调用方请求的 recursive(grant_temp_auth 入口参数); False 表示不授权递归
    Returns:
        bool: 实际生效的 recursive
    """
    if not requested or _is_rejectable_root(root):
        return False
    # 2026-10-20 小欧 - FIX: 目录判定不能用后缀启发式(Path.suffix), 目录名含点(如 E:\dir\v1.0)
    #   会被误判为"文件"使递归授权静默失效; 已存在者以 os.path.isdir/isfile 真实类型为准,
    #   不存在者维持原后缀口径(无类型可凭) — 小欧-2026-10-20
    _str = str(root)
    if os.path.isdir(_str):
        return True
    if os.path.isfile(_str):
        return False
    return not bool(Path(root).suffix)


def grant_temp_auth(root: str, recursive: bool = True) -> None:
    """临时授权某路径(本 task 内有效, task 结束清零) — 小欧 2026-08-10, M3 更新
    HITL确认后 grant 写入点: 路径层校验内 is_temp_authorized 读取 — 小欧-2026-10-14
    Args:
        root: 授权根路径
        recursive: True=授权根及其子目录树; False=仅精确路径
    """
    # 2026-09-03 小欧 修复: 空/根路径前置拒绝（Path("").resolve()得cwd扩域根治）
    if _is_rejectable_root(root):
        from app.logger import logger as _lg
        _lg.warning(f"[temp_auth] 空/根路径拒绝授权: {root!r}")
        return
    # 2026-09-03 小欧 修复: 文件路径(有后缀)强制recursive False，仅目录保持True，防task级目录越权
    _recursive = resolve_grant_recursive(root, recursive)
    # 2026-10-20 05:27 小欧 - FIX: 存取两侧统一 normcase —— Windows 路径不区分大小写,
    #   原 Path 相等比较区分, 授权时 e:\testdir 与使用时 E:\TestDir 命不中造成弹窗重出(过拦)
    #   注: 比较语义仍保持"授权了才能命中", 仅消除大小写/分隔符书写差导致的无谓失效 — 小欧-2026-10-20
    _ensure_auth()[Path(os.path.normcase(str(Path(root).resolve())))] = _recursive
    # 2026-09-03 小欧/: 授权操作补日志
    from app.logger import logger as _lg
    _lg.info(f"[temp_auth] 授权: root={root}, recursive={_recursive}")


def clear_temp_auth() -> None:
    """清空当前作用域临时授权(task 结束调用) — 小欧 2026-08-10, M3 更新
    task结束清零点(run_react_cycle finally) — 小欧-2026-10-14"""
    # 2026-09-03 小欧/: 清空授权补日志
    from app.logger import logger as _lg
    auth = _authorized_paths.get()
    _count = len(auth) if auth else 0
    _lg.info(f"[temp_auth] 清空授权: cleared={_count}项")
    _authorized_paths.set({})


def is_temp_authorized(file_path: str) -> bool:
    """检查路径是否在当前作用域临时授权范围内 — 小欧 2026-08-10
    M2 (v1.43): 前置禁区分类(深度防御):
        - 系统禁区 → 即使入单也返回 False(**永不授权**);
        - 非系统禁区写放行判定在 validate_path 写 mode 分支内完成,
          is_temp_authorized 仅做 auth-list 匹配, 不再硬拦(删已在 validate_path 删除规则硬拦)
        - 禁区判定异常 → **同样返回 False**(2026-10-15 起由"异常不阻断"改 fail-closed;
          原实现在判定异常时继续走 auth-list 匹配, 与上面"永不授权"的承诺矛盾, 且实测可让系统目录被授权)。
    支持递归: 授权目录后其子目录树一并放行。
    路径校验内读取点 — 小欧-2026-10-14
    """
    # M2: depth defense — 系统禁区永不授权(即使入单也False)
    try:
        # 2026-10-19 小欧 - 目录名单收口: 改查名单, 惰性导入避免循环依赖
        from app.safety.path_dir_lists import classify_path, SCOPE_FORBIDDEN_SYSTEM
        import os
        from pathlib import Path
        scope, _ = classify_path(file_path)
        if scope == SCOPE_FORBIDDEN_SYSTEM:
            return False
    except Exception:
        # 2026-10-15 (·修 fail-open): 原为 `pass` 继续走下文 auth-list 匹配,
        #   与本函数 docstring「系统禁区永不授权」的硬承诺矛盾 —— 故障注入实测: 判定异常时
        #   C:\Windows\secret.dll 会被判为【已授权】(崩不掉就当没禁区, 等于门失效)。
        #   现改 fail-closed: 判不出是否禁区 → 不授权。宁可少授权, 不可漏禁区。
        from app.logger import logger as _lg
        _lg.warning(f"[temp_auth] 禁区判定异常, 本次按未授权处理: {file_path}")
        return False

    auth = get_authorized()
    if not auth:
        return False
    try:
        # 2026-10-20 05:27 小欧 - FIX: 命中侧与 grant 存储侧同口径 normcase, 大小写不再影响命中
        p = Path(os.path.normcase(str(Path(file_path).resolve())))
    except Exception:
        return False
    for root, recursive in auth.items():
        if recursive:
            if p == root or root in p.parents:
                # 2026-09-03 小欧/: 授权命中补日志
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
           "get_authorized", "resolve_grant_recursive"]
