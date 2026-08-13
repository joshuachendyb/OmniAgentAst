
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - 解包execute_with_safety返回的(success, detail), 用真实错误细节替代笼统"删除文件失败,safety拦截"提示(根因: execute_with_safety原吞掉细节只返bool), 修复LLM拿不到真因无法自我纠正的问题。
# 2026-07-15 - 小欧 - _force_delete_sync改(bool,str)透传真实失败原因, 替代原返bool(False)导致_delete_sync包装(False,"permanent")致error_detail=模式字串而非真因。
# 2026-07-22 - 小欧 - _force_delete_sync 加重试机制: PermissionError/OSError 最多重试3次,间隔1s。
# 2026-07-29 - 小沈 - 三改: 1)TOOL_TIMEOUTS["delete"]=120s; 2)_force_delete_sync逐文件删除并计数,返回3-tuple(bool,str,list); 3)LLM显式看到删文件数+列表(>30截断5行5列); 4)超时提示hint指引缩小范围。
# 2026-07-30 - 小沈 - 三堂会审修复: _delete_file_impl L200 method改用闭包容器_deleted_container[1]取实际mode(原用force标记计算,当send2trash fallback到永久删除时LLM观察mode与事实不符); error分支metrics改传extra_metrics(含deleted_files), LLM在删除超时/失败时也能看到已删文件列表。
# 2026-08-02 - 小欧 - 最后防线加固: 新增_guard_forbidden_delete, 在delete()最前方无条件硬阻断删除盘根/项目根/系统保护目录, 不依赖security.enabled与config(根因: config security.enabled=false + 07-31撤销auto_confirm后 test_dl4_delete_root_protection真删G盘根; 本防线保证任何路径下禁删)
# 2026-08-10 - 小欧 - ⑥删复刻_get_project_root收敛走config: _guard_forbidden_delete 项目根统一 config.get_project_root()+get_allowed_dirs()(多授权根保护); 代码库根删除保护由Safety层_is_forbidden_path(⑦)承接; 步骤1实施(北京老陈驱动「项目根目录定义混乱修复」)
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, import 路径同步更新(配合 tools 禁 app.services 守护规则)
# 2026-08-12 - 小欧 - A1下沉: task_id ContextVar 迁至 app.tools.context, _current_task_id import 由 app.services.task.task_context 改 app.tools.context,
#   消除 tools 层对 app.services 越层依赖(守护测试 tools 禁 app.services 规则), 行为零变化(同一 ContextVar 对象)
# 2026-08-12 - 小欧 - A1后半面(4.1.7定案): 删除 from app.safety import record_operation/execute_with_safety,
#   改为 get_current_hooks() 取安全 hooks, 消除 tools→safety 越层; task_id 仍 _current_task_id.get()
# 2026-08-13 - 小欧 - A5职责拆分: hint_* 错误提示函数/导入源改 app.tools.toolhelper.error_hints
# 2026-08-13 - 小沈 - P1: remove_readonly 函数迁移至 app/utils/file_utils.py(消除 safety→tools 实现依赖), 本文件改为从 utils 导入
# 2026-08-13 - 小沈 - BUG-3修复(三堂会审): get_current_hooks() 改 get_current_hooks_or_noop() 兜底返回 NoOpHooks,
#   消除入口未注入时 _hooks.record_operation() NPE(如测试直接调工具函数), 行为零退化(生产路径已注入不变)
# 2026-08-13 - 小欧 - 三堂会审修复#5: _force_delete_sync/os.walk/rmdir/unlink/chmod 全链 to_win_long_path
#   长路径化(仅NT生效), 深嵌套目录不再 WinError 206; impl 层 is_dir/exists 探测同步长路径化
#   (超长路径不误判"已不存在"→already_deleted); 报告仍用原始路径不暴露 \\?\ 前缀;
#   send2trash 仍传原始路径(失败自动回退到已长路径化的永久删除)
# 2026-08-13 - 小欧 - 三堂会审修复#22: _guard_forbidden_delete 删除死分支 `if p is None: return None`
#   【病根】p = raw.expanduser().resolve() 恒返回Path(异常已被前try捕获返回), resolve()绝不返回None, L58-59分支永不可达(死代码, 违KISS)
#   【改法】删除该分支; 无任何行为变化(resolve成功则p恒为Path)
"""
F12: delete_file — 删除文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import os
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_FILE_DELETE_FAILED
from app.tools.context import _current_task_id, get_current_hooks_or_noop  # A1: ContextVar hooks — 小欧 2026-08-12; BUG-3修复 — 小沈 2026-08-13
from app.db.models.operation_models import OperationType

from app.tools.validate.file_path_checker import validate_path, OpCategory, WINDOWS_SYSTEM_DIRS  # 统一错误提示 - 小欧 2026-07-12
from app.tools.toolhelper.error_hints import hint_for_write_error
from app.logger import logger
from app.utils.path_utils import to_win_long_path  # #5长路径包裹 — 小欧 2026-08-13
from app.utils.file_utils import remove_readonly  # P1: 从 utils 导入 — 小沈 2026-08-13


def _guard_forbidden_delete(file_path: str) -> Optional[str]:
    """删除最后防线: 无条件禁止删除盘根/项目根+授权目录/系统保护目录 — 小欧 2026-08-02, 2026-08-10 ⑥收敛走config
    不依赖security.enabled, 在delete()最前方硬阻断。
    项目根统一走 config.get_project_root(), 代码库根删除保护由 Safety 层 _is_forbidden_path(⑦) 承接。
    返回blocked原因, 通过返回None表示允许删除。
    """
    try:
        raw = Path(file_path)
        p = raw.expanduser().resolve()
    except Exception as e:
        return f"安全校验: 路径解析失败({e})"
    try:
        if not p.exists() and not p.parent.exists():
            return None
    except Exception:
        pass

    # 1) 盘根(如 G:\ / C:\) — Windows: splitdrive后剩余部分为空或纯斜杠
    try:
        drive, rest = os.path.splitdrive(str(p))
        if drive and not rest.strip("\\/"):
            return f"禁止删除磁盘根目录: {file_path}"
    except Exception:
        pass

    # 2) 系统保护目录(复用file_path_checker规则) — Windows
    if os.name == "nt":
        path_lower = str(p).lower().replace("\\", "/")
        path_after_drive = path_lower.split(":")[-1] if ":" in path_lower else path_lower
        for sd in WINDOWS_SYSTEM_DIRS:
            sd_norm = sd.rstrip("/")
            if path_after_drive == sd_norm or path_after_drive.startswith(sd):
                return f"禁止删除系统目录: {file_path}"

    # 3) 项目根本身及项目根的父级祖先(含盘根) + 授权目录 — 保护根不被删除
    #    根内的具体用户文件/目录仍允许删除, 只禁各根自身及更上层。
    try:
        from app.config import get_config
        protected_roots_ = [Path(get_config().get_project_root()).resolve()]
        try:
            allowed_dirs = get_config().get_allowed_dirs()
            protected_roots_ += [Path(d).resolve() for d in allowed_dirs]
        except Exception:
            pass
        for root_ in protected_roots_:
            if p == root_:
                return f"禁止删除项目根/授权根目录: {file_path}"
            for ancestor in root_.parents:
                if p == ancestor:
                    return f"禁止删除项目根/授权根上级目录: {file_path}"
    except Exception:
        pass
    return None



def _force_delete_sync(path: Path, recursive: bool = False,
                       max_retries: int = 3, retry_delay: float = 1.0) -> Tuple[bool, str, list]:
    """永久删除:逐文件删除(recursive→自底向上walk)/单文件→unlink
    返回(是否成功,模式/错误,已删文件列表) — 小沈 2026-07-29 逐文件重写"""
    last_err: Optional[Exception] = None
    deleted_files: list[str] = []  # 在循环外初始化，retry不丢失已删文件 — 小沈 2026-07-30 三堂会审修复

    # #5长路径: FS操作统一走 \\?\ 前缀(仅NT), 深嵌套路径不再 WinError 206; 报告仍用原始 path — 小欧 2026-08-13
    _long = to_win_long_path(path)

    for attempt in range(max_retries):
        try:
            if Path(_long).is_dir():
                if not recursive:
                    Path(_long).rmdir()
                    deleted_files.append(str(path))
                    return True, "permanent", deleted_files
                # recursive: 自底向上walk,先删文件再删目录
                for root, dirs, files in os.walk(_long, topdown=False):
                    for name in files:
                        fp = Path(root, name)
                        _fpl = to_win_long_path(fp)
                        try:
                            if not os.access(_fpl, os.W_OK):
                                Path(_fpl).chmod(Path(_fpl).stat().st_mode | 0o200)  # 只读→加写权限
                            Path(_fpl).unlink()
                            deleted_files.append(str(fp))
                        except FileNotFoundError:
                            pass  # retry时已删的跳过
                    for name in dirs:
                        dp = Path(root, name)
                        try:
                            Path(to_win_long_path(dp)).rmdir()
                            deleted_files.append(str(dp))
                        except (FileNotFoundError, OSError):
                            pass  # 非空目录跳过
                try:
                    Path(_long).rmdir()
                    deleted_files.append(str(path))
                except (FileNotFoundError, OSError):
                    pass
                return True, "permanent", deleted_files
            # 单文件
            if Path(_long).exists() and not os.access(_long, os.W_OK):
                Path(_long).chmod(Path(_long).stat().st_mode | 0o200)
            Path(_long).unlink()
            deleted_files.append(str(path))
            return True, "permanent", deleted_files
        except PermissionError as e:
            last_err = e
            if attempt < max_retries - 1:
                logger.warning(f"[_force_delete_sync] 文件被锁定(第{attempt+1}次),等待{retry_delay}秒重试: {path}")
                _time_mod.sleep(retry_delay)
        except OSError as e:
            last_err = e
            if attempt < max_retries - 1:
                logger.warning(f"[_force_delete_sync] 删除失败(第{attempt+1}次),等待{retry_delay}秒重试: {path}")
                _time_mod.sleep(retry_delay)
    err_msg = str(last_err) or f"永久删除失败: {path}"
    logger.error(f"[_force_delete_sync] 删除失败(重试{max_retries}次后放弃): {path}, 错误: {last_err}")
    return False, err_msg, deleted_files


def _send2trash_sync(path: Path, recursive: bool = False) -> Tuple[bool, str, list]:
    """尝试放入回收站,失败则回退到永久删除
    返回(是否成功,模式/错误,已删文件列表) — 小沈 2026-07-29 返回3-tuple"""
    try:
        import send2trash
        send2trash.send2trash(str(path))
        return True, "send2trash", [str(path)]
    except ImportError:
        logger.warning("send2trash未安装,回退到永久删除")
    except Exception as e:
        logger.warning(f"send2trash失败: {e},回退到永久删除")
    return _force_delete_sync(path, recursive)


def _build_delete_file_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", detail: str = "", extra_metrics: Optional[Dict] = None,
    hint: str = "",
    user_recursive: Optional[bool] = None, user_force: Optional[bool] = None,
    deleted_files: Optional[list] = None,
) -> Dict[str, Any]:
    """delete_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小沈 2026-07-05 新增hint参数 小沈2026-07-29 新增deleted_files"""
    _act_params = {"source": source}
    if user_recursive is not None:
        _act_params["recursive"] = user_recursive
    if user_force is not None:
        _act_params["force"] = user_force
    extra_metrics = extra_metrics or {}

    # 文件列表格式化(>30项截断:首15+尾15) — 小沈 2026-07-29
    if deleted_files is not None:
        count = len(deleted_files)
        extra_metrics["deleted_count"] = {"value": count, "text": str(count)}
        if count <= 30:
            file_text = "\n".join(f"  {f}" for f in deleted_files)
        else:
            head = "\n".join(f"  {f}" for f in deleted_files[:15])
            tail = "\n".join(f"  {f}" for f in deleted_files[-15:])
            file_text = f"共{count}项，显示前15+后15:\n{head}\n  ...(省略{count-30}项)...\n{tail}"
        extra_metrics["deleted_files"] = {
            "value": (deleted_files[:15] + deleted_files[-15:]) if count > 30 else deleted_files,
            "text": file_text,
        }

    if exec_code == "error":
        return {
            "summary": f"删除{source}，失败",
            "action": {"tool": "delete", "tool_zh": "删除", "target": source, "params": _act_params},
            "status": {"exec_code": "error", "message": "删除失败", "code": ERR_FILE_DELETE_FAILED, "detail": detail, "hint": hint if hint else "请检查文件是否存在"},
            "duration_ms": duration_ms,
            "metrics": extra_metrics,
        }
    _suffix = extra_metrics.get("status", {}).get("text", "") or extra_metrics.get("deleted", {}).get("text", "")
    return {
        "summary": f"删除{source}，成功: {_suffix}" if _suffix else f"删除{source}，成功",
        "action": {"tool": "delete", "tool_zh": "删除", "target": source, "params": _act_params},
        "status": {"exec_code": "success", "message": "删除成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": extra_metrics,
    }


async def _delete_file_impl(
    file_path: str, recursive: bool = False, force: bool = False,
) -> Dict[str, Any]:
    """删除文件或目录实现 — 小欧 2026-06-22 — 小健 2026-06-22 — 小沈 2026-07-29 新增deleted_files跟踪"""

    path = Path(file_path)
    try:
        # #5长路径: 探测统一 \\?\ 前缀, 超长路径不误判"不存在" — 小欧 2026-08-13
        _long = to_win_long_path(path)
        if Path(_long).is_dir() and not recursive:
            return {"success": False, "error_detail": "删除非空目录需要设置recursive=True", "params": {"source": file_path}}
        if not Path(_long).exists():
            return {"success": True, "action": "delete", "source": file_path, "already_deleted": True, "deleted_files": []}

        task_id = _current_task_id.get()
        if not task_id:
            return {"success": False, "error_detail": "当前没有活跃任务ID", "params": {"source": file_path}}

        _hooks = get_current_hooks_or_noop()  # A1: ContextVar 取安全 hooks(BUG-3修复: _or_noop 兜底防 NPE) — 小沈 2026-08-13
        operation_id = _hooks.record_operation(
            task_id=task_id, operation_type=OperationType.DELETE,
            source_path=path, sequence_number=0,
        )

        _deleted_container: list = [[], ""]  # [0]=deleted_files, [1]=method — 小沈 2026-07-30

        def _delete_sync():
            if force:
                ok, detail, files = _force_delete_sync(path, recursive)
            else:
                ok, detail, files = _send2trash_sync(path, recursive)
            _deleted_container[0] = files
            _deleted_container[1] = detail  # "permanent"/"send2trash" or error
            return ok, detail  # 返回2-tuple兼容execute_with_safety

        # 根据operation_id是否存在选择执行方式 — 小健 2026-06-24 — 小沈 2026-07-07 execute_with_safety返回(bool,str)
        if operation_id:
            is_ok, error_detail = await asyncio.to_thread(_hooks.execute_with_safety, operation_id, operation_func=_delete_sync)
        else:
            logger.info("Database unavailable, executing delete operation without recording")
            is_ok, error_detail = await asyncio.to_thread(_delete_sync)

        method = _deleted_container[1] if _deleted_container[1] else ("permanent" if force else "send2trash")  # 实际mode, fallback到force标记 — 小沈 2026-07-30
        deleted_files = _deleted_container[0]
        if is_ok:
            return {"success": True, "deleted_path": str(path), "mode": method, "deleted_files": deleted_files}
        return {"success": False, "error_detail": error_detail or "删除文件失败,safety拦截", "params": {"source": file_path}, "deleted_files": deleted_files}

    except Exception as e:
        logger.error(f"Failed to delete {file_path}: {e}")
        return {"success": False, "error_detail": str(e), "hint": hint_for_write_error(e, Path(file_path).name), "params": {"source": file_path}}


async def delete(
    path: str,
    recursive: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """删除文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件 — 小健 2026-06-22 重构：主函数负责计时+builder+build3 — 小欧 2026-07-11 路径参数统一为path"""
    t0 = _time_mod.perf_counter()
    # 路径参数统一为path,桥接到内部变量source — 小欧 2026-07-11
    source = path
    if not source or not source.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_file_llm_data("error", duration_ms, source, detail="source不能为空", user_recursive=recursive, user_force=force)
        return build_error(data={}, llm_data=llm_data)
    # 最后防线: 无条件硬阻断删除盘根/项目根/系统保护目录(不依赖security.enabled与config) — 小欧 2026-08-02
    block_reason = _guard_forbidden_delete(source)
    if block_reason:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        logger.warning(f"[delete_file] 安全拦截: {block_reason} path={source}")
        llm_data = _build_delete_file_llm_data("error", duration_ms, source, detail=block_reason, user_recursive=recursive, user_force=force)
        return build_error(data={}, llm_data=llm_data)
    # 工具层校验：非空/保留字符/保留名/系统目录/路径存在（含递归/强制警告） — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, warn = validate_path(OpCategory.EXISTS, source, recursive=recursive, force=force)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_file_llm_data("error", duration_ms, source, detail=err, user_recursive=recursive, user_force=force)
        return build_error(data={}, llm_data=llm_data)
    if warn:
        logger.warning(warn)

    result = await _delete_file_impl(file_path=source, recursive=recursive, force=force)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    _df = result.get("deleted_files", [])

    if result.get("success"):
        if result.get("already_deleted"):
            llm_data = _build_delete_file_llm_data("success", duration_ms, source, extra_metrics={"status": {"value": "already_deleted", "text": "文件已删除"}}, user_recursive=recursive, user_force=force, deleted_files=_df)
            # ---- observation_formatter route -------------------------------------------
            # branch: #0 空data (L73)
            # trigger: data 为 {} → if not data: return ""
            # handler: 直接返回空字符串
            # file:    observation_formatter.py:73-74
            # ------------------------------------------------------------------------------
            return build_success(data={}, llm_data=llm_data)
        delete_mode = "永久删除" if force else "放入回收站"
        extra_m = {"mode": {"value": result.get("mode", ""), "text": delete_mode}}
        llm_data = _build_delete_file_llm_data("success", duration_ms, source, extra_metrics=extra_m, user_recursive=recursive, user_force=force, deleted_files=_df)
        # ---- LLM 观察(成功) ----------------------------------------------------------
        # action           | delete (删除) → E:\test_dir\big_folder
        # deleted_count    | 50
        # deleted_files    | 共50项，显示前15+后15:
        #                  |   E:\test_dir\big_folder\file1.py
        #                  |   ...
        #                  |   ...(省略20项)...
        #                  |   E:\test_dir\big_folder\file50.py
        # mode             | 永久删除
        # status           | exec_code=success
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback (key:val)
        # trigger: 无上述20条分支匹配 — operation_id/deleted_path 不命中专用分支
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(
            data={},
            llm_data=llm_data,
        )
    else:
        error_detail = result.get("error_detail", "删除文件失败")
        if "recursive" in error_detail.lower():
            error_hint = "请设置recursive=True重新删除"
        elif "safety" in error_detail.lower():
            error_hint = "文件被安全策略拦截，请检查权限"
        elif "任务ID" in error_detail:
            error_hint = "请先创建任务再删除"
        else:
            error_hint = result.get("hint") or "请检查文件是否存在和权限"  # 统一错误提示 - 小欧 2026-07-12
        # ---- LLM 观察(超时/失败) ----------------------------------------------------
        # status           | exec_code=error
        # hint             | 删除操作超时（120秒），部分文件可能已被删。建议缩小删除范围...
        # deleted_count    | 35
        # deleted_files    | 共35项:
        #                  |   E:\test_dir\big_folder\file1.py
        #                  |   ...
        # ------------------------------------------------------------------------------
        llm_data = _build_delete_file_llm_data("error", duration_ms, source, detail=error_detail, hint=error_hint, user_recursive=recursive, user_force=force, deleted_files=_df)
        return build_error(data={}, llm_data=llm_data)

