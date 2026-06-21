"""
MCP文件操作工具集 - 重写版本
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。后续审查关注功能逻辑本身的代码10大规范遵守和最优美简洁性，禁止以"文件过大"作为问题提出。
# 【拨乱反正 2026-05-28 小沈】session→task 命名修正

【重构日期】2026-03-19 小强
【参考】FastMCP、MarcusJellinghaus、LangChain、Claude官方Tool Use规范

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件:
1. *_tools.py: 函数实现(必须有详细注释)
2. *_schema.py: Pydantic 模型(输入参数定义)
3. *_register.py: 显式注册(description + examples + input_model)

改进点:
1. 使用Pydantic模型定义参数Schema
2. 动态白名单(自动添加存在的盘符)
3. 自动生成JSON Schema
4. 添加input_examples示例
5. 修复search_file_content空pattern安全漏洞

统一返回格式:{status, summary, data, retry_count}

【分页方案更新】2026-04-03 小沈
- read_file: 默认读取500行(READ_FILE_DEFAULT_LIMIT = 500)
- 其他工具: 分页返回(DEFAULT_PAGE_SIZE = 200)
"""

import asyncio
import base64
import fnmatch
import glob as glob_module
import inspect
import os
import re as re_mod
import shutil
import tempfile
import threading
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple, get_type_hints

from app.services.context_vars import _current_task_id

from app.tools.tool_response import build_success, build_error, build_warning

from app.tools.tool_constants import (
    READ_FILE_DEFAULT_LIMIT, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE,
    MAX_READ_SIZE, MAX_MEDIA_READ_SIZE, MAX_BATCH_FILE_COUNT,
    MAX_SEARCH_FILE_SIZE, BINARY_EXTENSIONS,
)

from pydantic import BaseModel, Field

from app.tools.file.file_schema import (
    ReadTextFileInput,
    WriteTextFileInput,
    ListDirectoryInput,
    SearchFilesInput,
    ReadMediaFileInput,
    GrepFileContentInput,
    EditTextFileInput,
    CompressFilesInput,
    ExtractArchiveInput,
    MoveFileInput,
    CopyFileInput,
    DeleteFileInput,
    RenameFileInput,
    ReadDataFileInput,
    WriteDataFileInput,
)

from app.db.models.operation_enums import OperationType
from app.utils.logger import logger
from app.tools.tool_constants import TOOL_TIMEOUTS
from app.utils.json_utils import coerce_json
from app.utils.tool_result_formatter import format_file_content_llm, truncate_data_for_frontend, truncate_text, make_json_safe, DEFAULT_MAX_FILE_CHARS
from app.tools.toolhelper import data_format_helper as df_tools
from app.services.safety.file_safety import record_operation, execute_with_safety
from app.constants import (
    ERR_DOC_DATA_FORMAT_FAILED,
    ERR_DOC_FORMAT_NOT_DETECTED,
    ERR_DOC_FORMAT_NOT_SUPPORTED,
    ERR_FILE_CONTENT_BLOCKED,
    ERR_FILE_CONTENT_SEARCH_FAILED,
    ERR_FILE_DELETE_FAILED,
    ERR_FILE_DIRECTORY_NOT_FOUND,
    ERR_FILE_EDIT_FAILED,
    ERR_FILE_EXTRACT,
    ERR_FILE_LIST_DIR_FAILED,
    ERR_FILE_MOVE_FAILED,
    ERR_FILE_NOT_FOUND,
    ERR_FILE_PATH_NOT_DIR,
    ERR_FILE_READ,
    ERR_FILE_READ_BINARY_FILE,
    ERR_FILE_READ_FAILED,
    ERR_FILE_READ_TOO_LARGE,
    ERR_FILE_REPLACE_FAILED,
    ERR_FILE_SEARCH_FAILED,
    ERR_FILE_WRITE_FAILED,
    ERR_META_NO_ACTIVE_TASK,
    ERR_PARAM_CONFLICT,
    ERR_PARAM_INVALID,
    ERR_PARAM_MISSING,
    ERR_NO_MATCH,
    ERR_PATH_INVALID,
    ERR_PATH_NOT_FILE,
)


def _build_list_directory_llm_data(exec_code, duration_ms, dir_path="", total=0, truncated=False, detail=""):
    """list_directory的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {"summary": f"列出目录失败: {detail}", "action": {"tool": "list_directory", "tool_zh": "列出目录", "target": dir_path, "params": {}}, "status": {"exec_code": "error", "message": "列出目录失败", "code": ERR_FILE_LIST_DIR_FAILED, "detail": detail, "hint": ""}, "duration_ms": duration_ms, "metrics": {}}
    m = {"total": {"value": total, "text": f"{total}项"}}
    if truncated:
        m["truncated"] = {"value": True, "text": "已截断"}
    return {"summary": f"列出目录成功: {dir_path} ({total}项)", "action": {"tool": "list_directory", "tool_zh": "列出目录", "target": dir_path, "params": {}}, "status": {"exec_code": "success", "message": "列出目录成功", "code": "", "detail": "", "hint": ""}, "duration_ms": duration_ms, "metrics": m}


def _build_read_text_file_llm_data(exec_code, duration_ms, file_path="", line_count=0, total_lines=0, file_size=0, detail=""):
    """read_text_file的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {"summary": f"读取文件失败: {detail}", "action": {"tool": "read_text_file", "tool_zh": "读取文件", "target": file_path, "params": {}}, "status": {"exec_code": "error", "message": "读取文件失败", "code": ERR_FILE_READ_FAILED, "detail": detail, "hint": ""}, "duration_ms": duration_ms, "metrics": {}}
    return {"summary": f"读取文件成功: {file_path} ({line_count}/{total_lines}行)", "action": {"tool": "read_text_file", "tool_zh": "读取文件", "target": file_path, "params": {}}, "status": {"exec_code": "success", "message": "读取文件成功", "code": "", "detail": "", "hint": ""}, "duration_ms": duration_ms, "metrics": {"line_count": {"value": line_count, "text": f"{line_count}行"}, "file_size": {"value": file_size, "text": f"{file_size}字节"}}}


def _build_write_text_file_llm_data(exec_code, duration_ms, file_path="", bytes_written=0, detail=""):
    """write_text_file的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {"summary": f"写入文件失败: {detail}", "action": {"tool": "write_text_file", "tool_zh": "写入文件", "target": file_path, "params": {}}, "status": {"exec_code": "error", "message": "写入文件失败", "code": ERR_FILE_WRITE_FAILED, "detail": detail, "hint": ""}, "duration_ms": duration_ms, "metrics": {}}
    return {"summary": f"写入文件成功: {file_path} ({bytes_written}字节)", "action": {"tool": "write_text_file", "tool_zh": "写入文件", "target": file_path, "params": {}}, "status": {"exec_code": "success", "message": "写入文件成功", "code": "", "detail": "", "hint": ""}, "duration_ms": duration_ms, "metrics": {"bytes_written": {"value": bytes_written, "text": f"{bytes_written}字节"}}}


def _build_read_media_file_llm_data(exec_code, duration_ms, file_path="", file_name="", mime_type="", file_size=0, detail=""):
    """read_media_file的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {"summary": f"读取媒体文件失败: {detail}", "action": {"tool": "read_media_file", "tool_zh": "读取媒体", "target": file_path, "params": {}}, "status": {"exec_code": "error", "message": "读取媒体文件失败", "code": ERR_FILE_READ_FAILED, "detail": detail, "hint": ""}, "duration_ms": duration_ms, "metrics": {}}
    return {"summary": f"读取媒体文件成功: {file_name} ({mime_type})", "action": {"tool": "read_media_file", "tool_zh": "读取媒体", "target": file_path, "params": {}}, "status": {"exec_code": "success", "message": "读取媒体文件成功", "code": "", "detail": "", "hint": ""}, "duration_ms": duration_ms, "metrics": {"file_size": {"value": file_size, "text": f"{file_size}字节"}}}


def _build_replace_file_llm_data(exec_code, duration_ms, file_path="", replaced_count=0, detail=""):
    """replace_file的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {"summary": f"文件替换失败: {detail}", "action": {"tool": "replace_file", "tool_zh": "替换文件", "target": file_path, "params": {}}, "status": {"exec_code": "error", "message": "替换失败", "code": ERR_FILE_REPLACE_FAILED, "detail": detail, "hint": ""}, "duration_ms": duration_ms, "metrics": {}}
    return {"summary": f"文件替换成功: {file_path} ({replaced_count}处)", "action": {"tool": "replace_file", "tool_zh": "替换文件", "target": file_path, "params": {}}, "status": {"exec_code": "success", "message": "替换成功", "code": "", "detail": "", "hint": ""}, "duration_ms": duration_ms, "metrics": {"replaced_count": {"value": replaced_count, "text": f"{replaced_count}处"}}}


def _build_edit_text_file_llm_data(exec_code, duration_ms, file_path="", applied=0, total=0, detail=""):
    """edit_text_file的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {"summary": f"文件编辑失败: {detail}", "action": {"tool": "edit_text_file", "tool_zh": "编辑文件", "target": file_path, "params": {}}, "status": {"exec_code": "error", "message": "编辑失败", "code": ERR_FILE_EDIT_FAILED, "detail": detail, "hint": ""}, "duration_ms": duration_ms, "metrics": {}}
    return {"summary": f"编辑完成: {file_path} ({applied}/{total}处)", "action": {"tool": "edit_text_file", "tool_zh": "编辑文件", "target": file_path, "params": {}}, "status": {"exec_code": "success", "message": "编辑完成", "code": "", "detail": "", "hint": ""}, "duration_ms": duration_ms, "metrics": {"applied": {"value": applied, "text": f"{applied}/{total}处"}}}


def _build_grep_file_content_llm_data(exec_code, duration_ms, pattern="", search_dir="", total_files=0, total_matches=0, detail=""):
    """grep_file_content的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {"summary": f"内容搜索失败: {detail}", "action": {"tool": "grep_file_content", "tool_zh": "内容搜索", "target": pattern, "params": {"pattern": pattern}}, "status": {"exec_code": "error", "message": "搜索失败", "code": ERR_FILE_CONTENT_SEARCH_FAILED, "detail": detail, "hint": ""}, "duration_ms": duration_ms, "metrics": {}}
    return {"summary": f"搜索完成: 匹配{total_matches}行, {total_files}个文件", "action": {"tool": "grep_file_content", "tool_zh": "内容搜索", "target": pattern, "params": {"pattern": pattern}}, "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""}, "duration_ms": duration_ms, "metrics": {"total_files": {"value": total_files, "text": f"{total_files}个文件"}, "total_matches": {"value": total_matches, "text": f"{total_matches}行"}}}


def _build_directory_tree_llm_data(exec_code, duration_ms, dir_path="", root_name="", child_count=0, detail=""):
    """directory_tree的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {"summary": f"获取目录树失败: {detail}", "action": {"tool": "get_directory_tree", "tool_zh": "目录树", "target": dir_path, "params": {}}, "status": {"exec_code": "error", "message": "获取目录树失败", "code": ERR_FILE_LIST_DIR_FAILED, "detail": detail, "hint": ""}, "duration_ms": duration_ms, "metrics": {}}
    return {"summary": f"目录树: {dir_path} ({child_count}个子项)", "action": {"tool": "get_directory_tree", "tool_zh": "目录树", "target": dir_path, "params": {}}, "status": {"exec_code": "success", "message": "获取目录树成功", "code": "", "detail": "", "hint": ""}, "duration_ms": duration_ms, "metrics": {"child_count": {"value": child_count, "text": f"{child_count}个子项"}}}


def _build_file_op_llm_data(exec_code, duration_ms, tool_name, tool_zh, target="", detail="", extra_metrics=None):
    """move/copy/delete/rename的通用llm_data构建函数 — 小健 2026-06-21"""
    extra_metrics = extra_metrics or {}
    if exec_code == "error":
        return {"summary": f"{tool_zh}失败: {detail}", "action": {"tool": tool_name, "tool_zh": tool_zh, "target": target, "params": {}}, "status": {"exec_code": "error", "message": f"{tool_zh}失败", "code": "", "detail": detail, "hint": ""}, "duration_ms": duration_ms, "metrics": {}}
    return {"summary": f"{tool_zh}成功: {target}", "action": {"tool": tool_name, "tool_zh": tool_zh, "target": target, "params": {}}, "status": {"exec_code": "success", "message": f"{tool_zh}成功", "code": "", "detail": "", "hint": ""}, "duration_ms": duration_ms, "metrics": extra_metrics}


def _build_data_format_llm_data(exec_code, duration_ms, file_path="", detected_format="", action="", detail="", item_count=0):
    """data_format的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {"summary": f"数据格式操作失败: {detail}", "action": {"tool": "data_file_format", "tool_zh": "数据格式", "target": file_path, "params": {}}, "status": {"exec_code": "error", "message": "操作失败", "code": ERR_DOC_DATA_FORMAT_FAILED, "detail": detail, "hint": ""}, "duration_ms": duration_ms, "metrics": {}}
    action_zh = "读取" if action == "read" else "写入"
    m = {"item_count": {"value": item_count, "text": f"{item_count}项"}} if item_count else {}
    return {"summary": f"已{action_zh}{detected_format.upper()}格式文件: {file_path}", "action": {"tool": "data_file_format", "tool_zh": "数据格式", "target": file_path, "params": {}}, "status": {"exec_code": "success", "message": f"{action_zh}成功", "code": "", "detail": "", "hint": ""}, "duration_ms": duration_ms, "metrics": m}


def _build_search_files_llm_data(exec_code, duration_ms, search_dir="", total=0, detail=""):
    """search_files的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {"summary": f"搜索文件失败: {detail}", "action": {"tool": "search_files", "tool_zh": "搜索文件", "target": search_dir, "params": {}}, "status": {"exec_code": "error", "message": "搜索失败", "code": ERR_FILE_SEARCH_FAILED, "detail": detail, "hint": ""}, "duration_ms": duration_ms, "metrics": {}}
    return {"summary": f"搜索完成: {total}个匹配", "action": {"tool": "search_files", "tool_zh": "搜索文件", "target": search_dir, "params": {}}, "status": {"exec_code": "success", "message": "搜索完成", "code": "", "detail": "", "hint": ""}, "duration_ms": duration_ms, "metrics": {"total": {"value": total, "text": f"{total}个匹配"}}}


def _build_file_checksum_llm_data(exec_code, duration_ms, algorithm="", checksum="", verify_result=None, detail=""):
    """file_checksum的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {"summary": f"校验和计算失败: {algorithm}", "action": {"tool": "file_checksum", "tool_zh": "文件校验", "target": algorithm, "params": {"algorithm": algorithm}}, "status": {"exec_code": "error", "message": "校验和计算失败", "code": "", "detail": detail, "hint": ""}, "duration_ms": duration_ms, "metrics": {}}
    summary = f"校验和计算成功: {algorithm}"
    if verify_result is not None:
        summary = f"校验和{'匹配' if verify_result else '不匹配'}: {algorithm}"
    return {"summary": summary, "action": {"tool": "file_checksum", "tool_zh": "文件校验", "target": algorithm, "params": {"algorithm": algorithm}}, "status": {"exec_code": "success", "message": "校验和计算成功", "code": "", "detail": "", "hint": ""}, "duration_ms": duration_ms, "metrics": {}}


# ============================================================
# 第一部分:分页配置常量
# ============================================================


def _is_binary_file(file_path: str) -> tuple[bool, str]:
    """
    检测文件是否为二进制文件 - 小沈 2026-05-02
    
    Args:
        file_path: 文件路径
        
    Returns:
        (is_binary, reason): 是否为二进制文件及原因说明
    """
    path = Path(file_path)
    suffix = path.suffix.lower()
    
    if suffix in BINARY_EXTENSIONS:
        return True, f"文件后缀 '{suffix}' 属于二进制文件类型,禁止使用text工具操作"
    
    return False, ""


def _remove_readonly(func, path, excinfo):
    """force删除时解除只读属性的回调 - 小健 2026-05-02"""
    os.chmod(path, os.stat(path).st_mode | 0o200)
    func(path)


# 【小沈重构 2026-05-25】25.5节:组件1 - 永久删除
def _force_delete_sync(path: Path, recursive: bool = False) -> bool:
    """永久删除:目录(如果recursive→rmtree否则rmdir) / 文件→unlink - 小沈重构 2026-05-25"""
    try:
        if path.is_dir():
            if recursive:
                shutil.rmtree(str(path), onerror=_remove_readonly)
            else:
                path.rmdir()
        else:
            if path.exists() and not os.access(str(path), os.W_OK):
                path.chmod(path.stat().st_mode | 0o200)
            path.unlink()
        return True
    except Exception as e:
        logger.error(f"[_force_delete_sync] 删除失败: {path}, 错误: {e}")
        return False


# 【小沈重构 2026-05-25】25.5节:组件2 - 回收站删除(回退到永久删除)
def _send2trash_sync(path: Path, recursive: bool = False) -> Tuple[bool, str]:
    """尝试放入回收站,失败则回退到永久删除 - 小沈重构 2026-05-25"""
    try:
        import send2trash
        send2trash.send2trash(str(path))
        return True, "send2trash"
    except ImportError:
        logger.warning("send2trash未安装,回退到永久删除")
    except Exception as e:
        logger.warning(f"send2trash失败: {e},回退到永久删除")
    return _force_delete_sync(path, recursive), "permanent"


# 【小沈重构 2026-05-25】25.5节:组件3 - 构建删除结果
def _build_delete_result(operation_id: str, path: Path, force: bool, method: str) -> dict:
    """构建删除操作的统一返回结果 - 小沈重构 2026-05-25"""
    delete_mode = "永久删除" if force else "放入回收站"
    return build_success(
        {"operation_id": operation_id, "deleted_path": str(path)},
        f"文件已{delete_mode}: {path}",
    )


# ============================================================
# 第二部分:动态白名单 — 小沈 2026-06-17 迁移至path_validator
# ============================================================

from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl


# ============================================================
# 第三部分:Pydantic参数模型 + 工具定义
# 【小沈修改 2026-03-24】从 file_schema.py 统一导入,避免重复定义
# ============================================================
# Pydantic模型已统一在 app.tools.file.file_schema 中定义
# 请勿在此文件重复定义模型,直接从 file_schema 导入使用


from datetime import datetime



# ============================================================
# 第五部分B:模块级共享函数(函数12/15拆分提取)— 小健 2026-05-25
# ============================================================

def _classify_size(size: int) -> str:
    """文件大小分桶 — 小健 2026-05-25

    使用场景:
    - list_directory中size_distribution统计
    - _list_sync中消除2处重复的分桶逻辑

    使用示例:
        bucket = _classify_size(st.st_size)  # 返回 "<1KB"/"1KB-10KB"/"10KB-100KB"/"100KB-1MB"/">1MB"

    返回数据说明:
    - 返回str,分桶名称
    """
    if size < 1024: return "<1KB"
    if size < 10240: return "1KB-10KB"
    if size < 102400: return "10KB-100KB"
    if size < 1048576: return "100KB-1MB"
    return ">1MB"


def _build_entry(item: Path, st: os.stat_result) -> Dict[str, Any]:
    """构建单个目录条目(供递归/非递归共用,消除25行重复)— 小健 2026-05-25

    使用场景:
    - list_directory的_list_sync中递归和非递归分支
    - 消除递归/非递归完全相同的entry构建模式

    使用示例:
        entry = _build_entry(item, st)

    返回数据说明:
    - 返回Dict,包含name/path/type/size/mtime
    """
    is_dir = item.is_dir()
    return {
        "name": item.name,
        "path": str(item.absolute()),
        "type": "directory" if is_dir else "file",
        "size": None if is_dir else st.st_size,
        "mtime": st.st_mtime,
    }


def _scan_directory_sync(
    path: Path, recursive: bool, max_depth: int,
    include_hidden: bool, deadline: float,
) -> Tuple[List[Dict], Dict, Dict, Dict]:
    """同步扫描目录(可被to_thread调用)— 小沈 2026-05-25

    使用场景:
    - list_directory的list模式同步扫描
    - 需要在独立线程中执行阻塞IO操作的场景

    使用示例:
        entries, stats, file_types, size_bins = await asyncio.to_thread(
            _scan_directory_sync, path, True, 10, False, deadline
        )

    返回数据说明:
        - entries: List[Dict], 文件/目录条目列表
        - stats: Dict, 统计信息(total_size/dir_count/file_count)
        - file_types: Dict[str, int], 文件类型统计
        - size_bins: Dict[str, int], 文件大小分桶统计
    """
    entries = []
    stats = {"total_size": 0, "dir_count": 0, "file_count": 0}
    ext_counter: Dict[str, int] = {}
    size_bins = {"<1KB": 0, "1KB-10KB": 0, "10KB-100KB": 0, "100KB-1MB": 0, ">1MB": 0}
    _timed_out = False

    def _scan_recursive(current_path: Path, current_depth: int):
        nonlocal _timed_out
        if current_depth > max_depth:
            return
        if time.monotonic() > deadline:
            _timed_out = True
            logger.warning(f"[_scan_directory_sync] 超时自检触发,已收集{len(entries)}条,提前返回")
            return
        try:
            for item in current_path.iterdir():
                if _timed_out:
                    return
                try:
                    if not include_hidden and item.name.startswith('.'):
                        continue
                    st = item.stat()
                    entry = _build_entry(item, st)
                    entries.append(entry)
                    if item.is_dir():
                        stats["dir_count"] += 1
                        _scan_recursive(item, current_depth + 1)
                        if _timed_out:
                            return
                    else:
                        stats["total_size"] += st.st_size
                        stats["file_count"] += 1
                        ext = item.suffix.lower().lstrip('.') if item.suffix else ''
                        ext_counter[ext] = ext_counter.get(ext, 0) + 1
                        size_bins[_classify_size(st.st_size)] += 1
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            return

    if recursive:
        _scan_recursive(path, 1)
    else:
        for item in path.iterdir():
            try:
                if not include_hidden and item.name.startswith('.'):
                    continue
                st = item.stat()
                entry = _build_entry(item, st)
                entries.append(entry)
                if item.is_dir():
                    stats["dir_count"] += 1
                else:
                    stats["total_size"] += st.st_size
                    stats["file_count"] += 1
                    ext = item.suffix.lower().lstrip('.') if item.suffix else ''
                    ext_counter[ext] = ext_counter.get(ext, 0) + 1
                    size_bins[_classify_size(st.st_size)] += 1
            except (PermissionError, OSError):
                continue

    return entries, stats, ext_counter, size_bins


def _count_tree_stats(node: dict) -> tuple:
    """递归统计树形结构的文件数/目录数/总大小 — 小健 2026-05-25

    使用场景:
    - list_directory的tree模式补充统计信息

    使用示例:
        files, dirs, total_size = _count_tree_stats(tree_obj)

    返回数据说明:
    - 返回(int, int, int): 文件数, 目录数, 总大小
    """
    files = dirs = total_size = 0
    if node.get("type") == "file":
        files = 1
        total_size = node.get("size", 0)
    elif node.get("type") == "directory":
        dirs = 1
    for child in node.get("children", []):
        cf, cd, cs = _count_tree_stats(child)
        files += cf; dirs += cd; total_size += cs
    return files, dirs, total_size


def _build_list_success(entries: List, total: int, path: Path, statistics: Dict,
                        start_offset: int, max_display: int) -> Dict[str, Any]:
    """统一构建list模式的成功响应(截断/全量共用)— 小健 2026-05-25

    使用场景:
    - list_directory中截断和全量两种分支的统一响应构建

    使用示例:
        return _build_list_success(all_entries, total, path, statistics, start_offset, 200)

    返回数据说明:
    - 返回build_success结果Dict
    """
    truncated = total > max_display
    if truncated:
        display = entries[start_offset:start_offset + max_display]
        next_token = encode_page_token(start_offset + max_display) if start_offset + max_display < total else None
    else:
        display = entries
        next_token = None
    llm_data = _build_list_directory_llm_data("success", 0, str(path), total, truncated)
    return build_success(
        data={"entries": display, "total": total, "directory": str(path),
         "truncated": truncated, "statistics": statistics, "next_page_token": next_token},
        llm_data=llm_data,
    )


_ENCODING_PRIORITY = ["utf-8", "gbk", "gb2312", "utf-8-sig"]


def _read_file_safe(file_path: Path) -> List[str]:
    """多编码尝试读取文件行,OOM防护 + OSError兜底 — 小健 2026-05-25

    使用场景:
    - grep_file_content中读取搜索文件
    - 复用get_file_encoding编码检测能力

    使用示例:
        lines = _read_file_safe(file_path)
        if not lines: continue

    返回数据说明:
    - 返回List[str],文件行列表;文件过大或读取失败返回[]
    """
    try:
        size = file_path.stat().st_size
        if size > MAX_SEARCH_FILE_SIZE:
            return []
    except OSError:
        return []
    for enc in _ENCODING_PRIORITY:
        try:
            with file_path.open("r", encoding=enc) as f:
                return f.readlines()
        except (UnicodeDecodeError, LookupError):
            continue
    with file_path.open("r", encoding="utf-8", errors="replace") as f:
        return f.readlines()


def _build_context(lines: List[str], line_no: int,
                   context_lines: Optional[int], after_lines: Optional[int],
                   before_lines: Optional[int]) -> Dict[str, Any]:
    """构建匹配行的上下文字段,含边界保护 — 小健 2026-05-25

    使用场景:
    - grep_file_content中构建after/before上下文

    使用示例:
        ctx = _build_context(lines, line_no, context_lines, after_lines, before_lines)

    返回数据说明:
    - 返回Dict,可能包含after/before键
    """
    entry = {}
    n = context_lines or after_lines or 0
    if n and line_no - 1 + n < len(lines) + n:
        after_content = []
        for i in range(1, n + 1):
            if line_no - 1 + i < len(lines):
                after_content.append(lines[line_no - 1 + i].rstrip('\n\r'))
        if after_content:
            entry["after"] = after_content
    m = context_lines or before_lines or 0
    if m:
        before_content = []
        for i in range(1, m + 1):
            if line_no - 1 - i >= 0:
                before_content.insert(0, lines[line_no - 1 - i].rstrip('\n\r'))
        if before_content:
            entry["before"] = before_content
    return entry


def _collect_file_matches(
    lines: List[str],
    regex: Any,
    multiline: bool,
    head_limit: Optional[int],
    match_count: int,
    context_lines: Optional[int],
    after_lines: Optional[int],
    before_lines: Optional[int],
) -> List[Dict]:
    """收集单个文件中的匹配行 — 小沈 2026-05-25

    使用场景:
    - _grep_files_sync中处理单个文件的匹配
    - 支持多行和单行两种模式

    使用示例:
        file_matches = _collect_file_matches(lines, regex, multiline, head_limit, match_count, ...)

    返回数据说明:
    - 返回List[Dict],匹配行列表
    """
    file_matches = []
    if multiline:
        content = ''.join(lines)
        for m in regex.finditer(content):
            if head_limit is not None and match_count + len(file_matches) >= head_limit:
                break
            line_no = content[:m.start()].count('\n') + 1
            file_matches.append({"line": line_no, "content": m.group()})
    else:
        for line_no, line in enumerate(lines, 1):
            if head_limit is not None and match_count + len(file_matches) >= head_limit:
                break
            m = regex.search(line)
            if m:
                entry = {"line": line_no, "content": line.rstrip('\n\r')}
                ctx = _build_context(lines, line_no, context_lines, after_lines, before_lines)
                entry.update(ctx)
                file_matches.append(entry)
    return file_matches


def _grep_files_sync(
    search_path: Path,
    pattern: str,
    file_glob: Optional[str],
    output_mode: Optional[str],
    ignore_case: bool,
    multiline: bool,
    head_limit: Optional[int],
    context_lines: Optional[int],
    after_lines: Optional[int],
    before_lines: Optional[int],
    deadline: float,
) -> Tuple[List[Dict], int]:
    """同步文件内容搜索 — 小沈 2026-05-25

    使用场景:
    - grep_file_content中同步搜索逻辑
    - 需要在独立线程中执行阻塞IO操作的场景

    使用示例:
        matches, total_matches = await asyncio.to_thread(
            _grep_files_sync, search_path, pattern, glob, output_mode, ...
        )

    返回数据说明:
    - matches: List[Dict], 匹配结果列表
    - total_matches: int, 总匹配次数
    """
    flags = re_mod.IGNORECASE if ignore_case else 0
    if multiline:
        flags |= re_mod.DOTALL
    try:
        regex = re_mod.compile(pattern, flags)
    except re_mod.error as e:
        raise ValueError(f"正则表达式错误: {e}")

    results = []
    match_count = 0

    for root, dirs, files in os.walk(search_path):
        if time.monotonic() > deadline:
            logger.warning(f"[_grep_files_sync] 超时自检触发,已匹配{match_count}条,提前返回{len(results)}个文件结果")
            break
        filtered_files = [f for f in files if not file_glob or fnmatch.fnmatch(f, file_glob)]
        for filename in filtered_files:
            if head_limit is not None and match_count >= head_limit:
                break
            file_path = Path(root) / filename
            lines = _read_file_safe(file_path)
            if not lines:
                continue

            file_matches = _collect_file_matches(
                lines, regex, multiline, head_limit, match_count,
                context_lines, after_lines, before_lines
            )
            match_count += len(file_matches)
            fmt_entry = _format_match_output(file_matches, output_mode, str(file_path))
            if fmt_entry:
                results.append(fmt_entry)

    return results, match_count


def _format_match_output(file_matches: List, output_mode: Optional[str],
                         file_path: str) -> Optional[Dict]:
    """根据output_mode格式化单文件结果,返回条目或None — 小健 2026-05-25

    使用场景:
    - grep_file_content中3路output_mode分发

    使用示例:
        entry = _format_match_output(file_matches, output_mode, str(file_path))
        if entry: results.append(entry)

    返回数据说明:
    - count模式: 返回{"file", "count"}
    - files_with_matches模式: 返回{"file"}
    - content模式: 返回{"file", "matches", "match_count"}
    - 无匹配: 返回None
    """
    if not file_matches:
        return None
    if output_mode == "count":
        return {"file": file_path, "count": len(file_matches)}
    if output_mode == "files_with_matches":
        return {"file": file_path}
    return {"file": file_path, "matches": file_matches, "match_count": len(file_matches)}


_DEFAULT_PAGE_SIZE = 200


def _paginate_results(all_items: List, page_token: Optional[str],
                      page_size: int = _DEFAULT_PAGE_SIZE) -> tuple:
    """统一分页:token解码 → 切片 → has_more推导 — 小健 2026-05-25

    使用场景:
    - grep_file_content和list_directory中分页逻辑共享

    使用示例:
        page, next_token = _paginate_results(all_items, page_token, 200)

    返回数据说明:
    - 返回(List, Optional[str]): 当前页条目, 下一页token
    """
    start = decode_page_token(page_token) if page_token else 0
    end = start + page_size
    page = all_items[start:end]
    next_token = encode_page_token(end) if end < len(all_items) else None
    return page, next_token


def _apply_replacement(
    content: str, old_string: str, new_string: str,
    ignore_case: bool = False, replace_all: bool = False,
) -> Tuple[str, int]:
    """精确替换(21.1 组件,小沈 2026-05-25 实施)"""
    if ignore_case:
        if replace_all:
            new_content = re_mod.sub(re_mod.escape(old_string), new_string, content, flags=re_mod.IGNORECASE)
            count = len(re_mod.findall(re_mod.escape(old_string), content, flags=re_mod.IGNORECASE))
        else:
            new_content = re_mod.sub(re_mod.escape(old_string), new_string, content, count=1, flags=re_mod.IGNORECASE)
            count = 1
    else:
        if replace_all:
            count = content.count(old_string)
            new_content = content.replace(old_string, new_string)
        else:
            idx = content.find(old_string)
            if idx == -1:
                return content, 0
            new_content = content[:idx] + new_string + content[idx + len(old_string):]
            count = 1
    return new_content, count


# data_file_format 分发映射表(21.2 组件1,小沈 2026-05-25 实施)
_FORMAT_DISPATCH = {
    "json":       {"read": df_tools._read_json,       "write": df_tools._write_json},
    "yaml":       {"read": df_tools._parse_yaml,      "write": df_tools._write_yaml},
    "toml":       {"read": df_tools._parse_toml,      "write": df_tools._write_toml},
    "ini":        {"read": df_tools._parse_ini,       "write": None},
    "xml":        {"read": df_tools._parse_xml,       "write": None},
    "properties": {"read": df_tools._parse_properties, "write": None},
}


# ============================================================
# 第六部分:文件工具函数(函数式设计) — 小健 2026-06-18 重构移除FileTools类
# ============================================================


def _validate_content_format(file_path: str, content: str) -> Optional[str]:
    """写入前按文件扩展名验证内容格式合法性 — 小健 2026-05-25 重构拆分

    使用场景:
        write_file写入文件前验证格式合法性

    使用示例:
        error = _validate_content_format('test.json', '{"key": "value"}')
        if error:
            print(f"验证失败: {error}")

    返回数据说明:
        - 返回None表示验证通过
        - 返回str表示错误信息
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in BINARY_EXTENSIONS:
        return f"不支持通过write_file写入二进制格式文件(.{suffix[1:]}),请使用对应的专业工具操作"

    from app.tools.toolhelper import content_validation as cv

    validators = {
        '.json': cv.validate_json_content,
        '.csv': cv.validate_csv_content,
        '.xml': cv.validate_xml_content,
        '.html': cv.validate_html_content,
        '.htm': cv.validate_html_content,
        '.py': lambda c: cv.validate_python_content(c, str(path)),
    }

    validator = validators.get(suffix)
    if validator:
        return validator(content)
    return None


def _validate_path(file_path: str) -> tuple[bool, Optional[str]]:
    """验证文件路径是否合法 — 小沈 2026-06-17 委托path_validator"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


async def _try_read_file_with_encodings(
    path: Path,
    preferred: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """编码检测+同步文件读取,返回 (content, used_encoding, error)
    
    小沈 2026-05-25 重构拆分
    """
    try:
        from app.tools.toolhelper.file_helper import get_file_encoding
        
        if preferred:
            encodings_to_try = [preferred]
        else:
            auto = get_file_encoding(str(path))
            encodings_to_try = []
            if auto and auto.get("data", {}).get("encoding"):
                encodings_to_try.append(auto["data"]["encoding"])
        encodings_to_try.extend(["utf-8", "gbk", "gb2312", "utf-8-sig"])
        
        do_detect = preferred is None
        
        for enc in encodings_to_try:
            if enc is None:
                continue
            try:
                def _read(e=enc):
                    with open(path, 'r', encoding=e, errors='replace') as f:
                        return f.read()
                content = await asyncio.to_thread(_read)
                if do_detect and '\ufffd' in content:
                    content = None
                    continue
                return content, enc, None
            except Exception:
                continue
        
        return None, None, f"无法读取文件: {path},已尝试编码: {encodings_to_try}"
    except Exception as e:
        return None, None, str(e)


def _select_lines(
    lines: list,
    head: Optional[int] = None,
    tail: Optional[int] = None,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """根据参数选择行并构建 _data 字典
    
    小沈 2026-05-25 重构拆分
    """
    total = len(lines)
    params = {}
    
    if head is not None:
        selected = lines[:min(head, total)]
        params["head"] = head
    elif tail is not None:
        start = max(0, total - tail)
        selected = lines[start:]
        params["tail"] = tail
    elif offset is not None:
        start_idx = max(0, offset - 1)
        effective_limit = limit if limit else READ_FILE_DEFAULT_LIMIT
        selected = lines[start_idx:start_idx + effective_limit]
        params.update({
            "offset": offset, "limit": limit,
            "start_line": offset, "end_line": offset + len(selected) - 1,
        })
    else:
        selected = lines
    
    content = "".join(selected)
    return {
        "content": content,
        "total_lines": total,
        "line_count": len(selected),
        **params,
    }


async def _read_text_file(
    file_path: str,
    head: Optional[int] = None,
    tail: Optional[int] = None,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """读取文本文件
    
    【小沈重构 2026-05-25】
    - 重构拆分:提取 _try_read_file_with_encodings / _select_lines
    - 保持所有分支完整,功能不减少
    
    参数组合说明:
    - 无参数:读取全部内容
    - head=N:读取前N行
    - tail=N:读取后N行
    - offset=N, limit=M:从第N行开始读取M行(分页读取)
    """
    t0 = _time_mod.perf_counter()
    try:
        is_binary, binary_reason = _is_binary_file(file_path)
        if is_binary:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"{binary_reason}。请使用read_media_file工具读取媒体文件")
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

        for _name, _val in [("head", head), ("tail", tail), ("offset", offset), ("limit", limit)]:
            if _val is not None and _val < 1:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"{_name}必须>=1,当前值: {_val}")
                return build_error(data={_name: _val}, llm_data=llm_data)

        if head is not None and tail is not None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail="head和tail不能同时使用")
            return build_error(data={"head": head, "tail": tail}, llm_data=llm_data)

        if (head is not None or tail is not None) and (offset is not None or limit is not None):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail="head/tail与offset/limit不能同时使用")
            return build_error(data={"head": head, "tail": tail, "offset": offset, "limit": limit}, llm_data=llm_data)

        is_valid, error_msg = _validate_path(file_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error_msg)
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

        path = Path(file_path)
        if not path.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"文件不存在: {file_path}")
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

        if not path.is_file():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"路径不是文件: {file_path}")
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

        file_size = path.stat().st_size
        if file_size > MAX_READ_SIZE:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"文件过大({file_size}字节),请使用head/tail分段读取")
            return build_error(data={"file_path": file_path, "file_size": file_size}, llm_data=llm_data)

        content, used_encoding, error = await _try_read_file_with_encodings(path, encoding)
        if error:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error)
            return build_error(data={"error": error, "file_path": file_path}, llm_data=llm_data)

        lines = content.splitlines(keepends=True)
        _data = _select_lines(lines, head, tail, offset, limit)
        _data["encoding"] = used_encoding
        _data["file_size"] = file_size

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_text_file_llm_data("success", duration_ms, file_path=file_path, line_count=_data["line_count"], total_lines=_data["total_lines"], file_size=file_size)

        return build_success(data=_data, llm_data=llm_data)

    except Exception as e:
        logger.error(f"read_text_file failed: {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_text_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e))
        return build_error(data={"error": str(e), "file_path": file_path}, llm_data=llm_data)


def _detect_file_encoding_for_write(file_path: str, append: bool) -> str:
    """统一编码检测,复用 get_file_encoding
    
    小沈 2026-05-25 重构拆分
    """
    if not append:
        return "utf-8"
    
    path = Path(file_path)
    if not (path.exists() and path.is_file()):
        return "utf-8"

    try:
        from app.tools.toolhelper.file_helper import get_file_encoding
        result = get_file_encoding(file_path)
        return result.get("data", {}).get("encoding", "utf-8")
    except Exception:
        return "utf-8"


def _write_file_atomic(content: str, path: Path, encoding: str,
                        append: bool, create_parents: bool) -> bool:
    """原子写入:追加模式直接写,否则临时文件+os.replace
    
    小沈 2026-05-25 重构拆分
    """
    if create_parents:
        path.parent.mkdir(parents=True, exist_ok=True)
    elif not path.parent.exists():
        raise FileNotFoundError(f"父目录不存在: {path.parent}")
    
    if append and path.exists() and path.is_file():
        with open(path, 'a', encoding=encoding) as f:
            f.write(content)
        return True
    
    with tempfile.NamedTemporaryFile(
        mode='w', encoding=encoding, dir=path.parent,
        delete=False, prefix=f".{path.name}.", suffix=""
    ) as f:
        f.write(content)
        temp_path = f.name
    
    try:
        os.replace(temp_path, str(path))
        return True
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _check_write_safety(file_path: str, content: str,
                         encoding: Optional[str] = None) -> tuple:
    """统一前置校验链,返回 (error_or_None, modified_content)
    
    小沈 2026-05-25 重构拆分
    小健 2026-06-19 新增content类型检查:dict/list→json.dumps,其他→str()
    """
    _enc = encoding or "utf-8"

    if not isinstance(content, str):
        import json as _json
        if isinstance(content, (dict, list)):
            content = _json.dumps(content, ensure_ascii=False, indent=2)
        else:
            content = str(content)

    is_binary, reason = _is_binary_file(file_path)
    if is_binary:
        return f"{reason}。write_text_file 仅支持文本文件。", content
    
    if content and len(content.encode(_enc)) > MAX_READ_SIZE:
        return f"内容过大,超过写入上限{MAX_READ_SIZE//1024//1024}MB。", content
    
    path = Path(file_path)
    if path.suffix.lower() == '.py' and content:
        fullwidth_map = {'(': '(', ')': ')', ',': ',', ':': ':', ';': ';'}
        for fw, hw in fullwidth_map.items():
            content = content.replace(fw, hw)
    
    if content:
        from app.utils.content_quality import check_content_quality
        quality = check_content_quality(content=content, file_path=file_path)
        if quality.get("is_thought_leak"):
            return quality["warning"], content
    
    validation_error = _validate_content_format(file_path, content)
    if validation_error:
        return validation_error, content
    
    is_valid, error_msg = _validate_path(file_path)
    if not is_valid:
        return error_msg, content
    
    old_size = path.stat().st_size if path.exists() and path.is_file() else 0
    new_size = len(content.encode(_enc))
    if old_size > 1024 and new_size > 0 and new_size < old_size * 0.20:
        return f"数据保护:新内容({new_size}字节)远小于原始内容({old_size}字节)", content
    
    return None, content


async def write_text_file(
    file_path: str,
    content: str,
    encoding: Optional[str] = None,
    append: bool = False,
) -> Dict[str, Any]:
    """写入文本文件
    
    【小沈重构 2026-05-25】
    - 重构拆分:提取 _detect_file_encoding_for_write / _write_file_atomic / _check_write_safety
    - 保持所有分支完整,功能不减少
    """
    t0 = _time_mod.perf_counter()
    create_parents = True
    unescape = True
    error, checked_content = _check_write_safety(file_path, content, encoding)
    if error:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error)
        return build_error(data={"file_path": file_path, "error": error}, llm_data=llm_data)

    if unescape:
        checked_content = checked_content.replace("\\\\", "\\").replace("\\n", "\n").replace("\\\"", "\"")

    encoding = encoding or _detect_file_encoding_for_write(file_path, append)

    task_id = _current_task_id.get()
    if not task_id:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail="当前没有活跃任务ID")
        return build_error(data={"file_path": file_path}, llm_data=llm_data)

    path = Path(file_path)

    try:
        operation_id = record_operation(
            task_id=task_id,
            operation_type=OperationType.CREATE,
            destination_path=path,
            sequence_number=0
        )

        def _do_write():
            return execute_with_safety(operation_id, lambda: _write_file_atomic(checked_content, path, encoding, append, create_parents))
        success = await asyncio.to_thread(_do_write)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if success:
            bytes_written = len(checked_content.encode(encoding))
            llm_data = _build_write_text_file_llm_data("success", duration_ms, file_path=str(path), bytes_written=bytes_written)
            return build_success(
                data={"operation_id": operation_id, "file_path": str(path), "bytes_written": bytes_written},
                llm_data=llm_data,
            )
        else:
            llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail="写入文件失败,safety拦截")
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

    except Exception as e:
        logger.error(f"Failed to write file {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_text_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e))
        return build_error(data={"error": str(e), "file_path": file_path}, llm_data=llm_data)


async def list_directory(
    dir_path: str,
    recursive: bool = False,
    sort_by: str = "name",
    include_hidden: bool = False,
) -> Dict[str, Any]:
    """列出目录内容 — 小沈 2026-05-19, 2026-05-25 小健重构拆分
    P11统一入口:list/tree/statistics三合一
    【2026-06-20 小健】删max_depth/page_token,sortBy→sort_by,删tree用recursive决定format
    """
    t0 = _time_mod.perf_counter()
    max_depth = 10
    format = "tree" if recursive else "list"

    if sort_by not in ("name", "size", "mtime"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=f"sort_by只支持'name'/'size'/'mtime',当前值: '{sort_by}'")
        return build_error(data={"sort_by": sort_by}, llm_data=llm_data)

    if format == "tree":
        tree_result = await _get_directory_tree(dir_path=dir_path, max_depth=max_depth)
        if tree_result.get("code") == "SUCCESS" and "data" in tree_result:
            tree_data = tree_result["data"]
            if isinstance(tree_data, dict) and "tree" in tree_data:
                f, d, s = _count_tree_stats(tree_data["tree"])
                tree_data["statistics"] = {"file_count": f, "dir_count": d, "total_size": s}
        return tree_result

    is_valid, error_msg = _validate_path(dir_path)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=error_msg)
        return build_error(data={"file_path": dir_path}, llm_data=llm_data)

    path = Path(dir_path)
    start_offset = 0

    try:
        if not path.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=f"目录不存在: {dir_path}")
            return build_error(data={"file_path": dir_path}, llm_data=llm_data)
        if not path.is_dir():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=f"不是目录: {dir_path}")
            return build_error(data={"file_path": dir_path}, llm_data=llm_data)

        deadline = time.monotonic() + TOOL_TIMEOUTS.get("list_directory", TOOL_TIMEOUTS["default"]) - 2
        all_entries, stats, file_types, size_distribution = await asyncio.to_thread(
            _scan_directory_sync, path, recursive, max_depth, include_hidden, deadline
        )

        if sort_by == "size":
            all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x.get("size") or 0), reverse=True)
        elif sort_by == "mtime":
            all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x.get("mtime", 0)), reverse=True)
        else:
            all_entries.sort(key=lambda x: (0 if x["type"] == "directory" else 1, x["name"].lower()))

        total = len(all_entries)
        MAX_DISPLAY_ENTRIES = 200
        statistics = {
            "total_size": stats["total_size"], "dir_count": stats["dir_count"],
            "file_count": stats["file_count"], "sort_by": sort_by,
            "file_types": file_types, "size_distribution": size_distribution,
        }

        if total > MAX_DISPLAY_ENTRIES:
            logger.warning(
                f"[list_directory] Large directory truncated: path={path}, "
                f"total={total}, dir_count={stats['dir_count']}, file_count={stats['file_count']}, "
                f"displayed={MAX_DISPLAY_ENTRIES}"
            )

        return _build_list_success(all_entries, total, path, statistics, start_offset, MAX_DISPLAY_ENTRIES)

    except Exception as e:
        logger.error(f"Failed to list directory {dir_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_list_directory_llm_data("error", duration_ms, dir_path=dir_path, detail=str(e))
        return build_error(data={"error": str(e), "file_path": dir_path}, llm_data=llm_data)


async def _delete_file(
    file_path: str,
    recursive: bool = False,
    force: bool = False
) -> Dict[str, Any]:
    """删除文件或目录 - 小健 2026-05-03 默认放入回收站,force=True永久删除
    【小沈重构 2026-05-25】25.5节:骨架~30行,闭包拆分为3个独立函数"""

    t0 = _time_mod.perf_counter()

    is_valid, error_msg = _validate_path(file_path)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_file_op_llm_data("error", duration_ms, "delete_file", "删除文件", target=file_path, detail=error_msg)
        return build_error(data={"file_path": file_path}, llm_data=llm_data)

    path = Path(file_path)

    try:
        if not path.exists():
            llm_data = _build_file_op_llm_data("success", 0, "delete_file", "删除文件", target=file_path)
            return build_success(data=None, llm_data=llm_data)

        task_id = _current_task_id.get()
        if not task_id:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_file_op_llm_data("error", duration_ms, "delete_file", "删除文件", target=file_path, detail="当前没有活跃任务ID")
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

        operation_id = record_operation(
            task_id=task_id,
            operation_type=OperationType.DELETE,
            source_path=path,
            sequence_number=0
        )

        def _delete_sync():
            if force:
                return _force_delete_sync(path, recursive), "permanent"
            return _send2trash_sync(path, recursive)

        is_ok, method = await asyncio.to_thread(
            execute_with_safety,
            operation_id,
            operation_func=_delete_sync
        )

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if is_ok:
            return _build_delete_result(operation_id, path, force, method)
        else:
            llm_data = _build_file_op_llm_data("error", duration_ms, "delete_file", "删除文件", target=file_path, detail="删除文件失败,safety拦截")
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

    except Exception as e:
        logger.error(f"Failed to delete {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_file_op_llm_data("error", duration_ms, "delete_file", "删除文件", target=file_path, detail=str(e))
        return build_error(data={"error": str(e), "file_path": file_path}, llm_data=llm_data)


async def _move_file(
    source_path: str,
    destination_path: str,
    overwrite: bool = False
) -> Dict[str, Any]:
    """移动或重命名文件 - 小健 2026-05-02 增加overwrite"""
    t0 = _time_mod.perf_counter()
    is_valid_src, error_msg_src = _validate_path(source_path)
    if not is_valid_src:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_file_op_llm_data("error", duration_ms, "move_file", "移动文件", target=source_path, detail=f"源路径{error_msg_src}")
        return build_error(data={"file_path": source_path}, llm_data=llm_data)

    is_valid_dst, error_msg_dst = _validate_path(destination_path)
    if not is_valid_dst:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_file_op_llm_data("error", duration_ms, "move_file", "移动文件", target=destination_path, detail=f"目标路径{error_msg_dst}")
        return build_error(data={"file_path": destination_path}, llm_data=llm_data)

    src = Path(source_path)
    dst = Path(destination_path)

    try:
        if not src.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_file_op_llm_data("error", duration_ms, "move_file", "移动文件", target=source_path, detail=f"源文件不存在: {source_path}")
            return build_error(data={"file_path": source_path}, llm_data=llm_data)

        task_id = _current_task_id.get()
        if not task_id:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_file_op_llm_data("error", duration_ms, "move_file", "移动文件", target=source_path, detail="当前没有活跃任务ID")
            return build_error(data={"file_path": source_path}, llm_data=llm_data)

        operation_id = record_operation(
            task_id=task_id,
            operation_type=OperationType.MOVE,
            source_path=src,
            destination_path=dst,
            sequence_number=0
        )

        def _move_sync():
            if dst.exists():
                if not overwrite:
                    raise FileExistsError(f"目标路径已存在: {dst},移动操作已取消。请设置overwrite=True或指定其他路径。")
                if dst.is_dir():
                    shutil.rmtree(str(dst))
                else:
                    dst.unlink()
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return True

        success = await asyncio.to_thread(
            execute_with_safety,
            operation_id,
            operation_func=_move_sync
        )

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if success:
            llm_data = _build_file_op_llm_data("success", duration_ms, "move_file", "移动文件", target=str(src))
            return build_success(
                data={"operation_id": operation_id, "source": str(src), "destination": str(dst)},
                llm_data=llm_data,
            )
        llm_data = _build_file_op_llm_data("error", duration_ms, "move_file", "移动文件", target=source_path, detail="移动文件失败")
        return build_error(data={"source": str(source_path), "destination": str(destination_path)}, llm_data=llm_data)

    except Exception as e:
        logger.error(f"Failed to move {source_path} -> {destination_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_file_op_llm_data("error", duration_ms, "move_file", "移动文件", target=source_path, detail=str(e))
        return build_error(data={"error": str(e), "source": str(source_path), "destination": str(destination_path)}, llm_data=llm_data)


async def search_files(
    pattern: str,
    search_dir: str,
    recursive: bool = True,
    ignore_case: bool = True,
    type: Optional[Literal["file", "directory"]] = None,
) -> Dict[str, Any]:
    """搜索文件名 — 小沈 2026-05-19 精简参数(9→7);小健 2026-05-25 重构
    【2026-06-20 小健】删max_depth/page_token
    """
    t0 = _time_mod.perf_counter()
    max_depth = 50
    is_valid, error_msg = _validate_path(search_dir)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_files_llm_data("error", duration_ms, search_dir=search_dir, detail=error_msg)
        return build_error(data={"file_path": search_dir}, llm_data=llm_data)
    if not pattern or not pattern.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_files_llm_data("error", duration_ms, search_dir=search_dir, detail="文件名匹配模式不能为空")
        return build_error(data={"pattern": pattern}, llm_data=llm_data)
    path = Path(os.path.expanduser(search_dir))
    if not path.exists():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_files_llm_data("error", duration_ms, search_dir=search_dir, detail=f"搜索目录不存在: {search_dir}")
        return build_error(data={"file_path": search_dir}, llm_data=llm_data)

    deadline = time.monotonic() + TOOL_TIMEOUTS.get("search_files", TOOL_TIMEOUTS["default"]) - 2
    all_matches, llm_preview = [], []
    seen_files = set()
    start_offset = 0

    def _search_sync():
        nonlocal seen_files
        for root, dirs, files in os.walk(path):
            if time.monotonic() > deadline:
                logger.warning(f"[search_files] 超时自检触发,提前返回{len(all_matches)}个匹配")
                break
            if not recursive:
                dirs.clear()
            elif max_depth:
                depth = root[len(str(path)):].count(os.sep)
                if depth >= max_depth:
                    dirs.clear()

            if type != "file":
                for d in dirs:
                    if not _match_fnmatch(d, pattern, ignore_case):
                        continue
                    relative = os.path.relpath(os.path.join(root, d), path)
                    dup, skip = _is_already_seen_or_skipped(relative, seen_files, len(all_matches), start_offset)
                    if dup or skip:
                        continue
                    _collect_entry_result(relative, d, Path(os.path.join(root, d)), all_matches, llm_preview)

            if type != "directory":
                for f in files:
                    if not _match_fnmatch(f, pattern, ignore_case):
                        continue
                    relative = os.path.relpath(os.path.join(root, f), path)
                    dup, skip = _is_already_seen_or_skipped(relative, seen_files, len(all_matches), start_offset)
                    if dup or skip:
                        continue
                    _collect_entry_result(relative, f, Path(os.path.join(root, f)), all_matches, llm_preview)

    try:
        await asyncio.to_thread(_search_sync)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_search_files_llm_data("error", duration_ms, search_dir=search_dir, detail=f"搜索失败: {e}")
        return build_error(data={"error": str(e), "file_path": search_dir}, llm_data=llm_data)

    all_matches.sort(key=lambda x: x.get("name", ""))
    return _paginate_search(all_matches, search_dir, llm_preview, DEFAULT_PAGE_SIZE, start_offset)


async def _copy_file(
    source_path: str,
    destination_path: str,
    recursive: bool = False,
    overwrite: bool = False,
    preserve_metadata: bool = True,
) -> Dict[str, Any]:
    """复制文件或目录 - 小健 2026-05-02 增加preserve_metadata"""
    from app.tools.toolhelper.file_helper import copy_file_impl

    return await copy_file_impl(
        source_path=source_path,
        destination_path=destination_path,
        recursive=recursive,
        overwrite=overwrite,
        preserve_metadata=preserve_metadata,
        validate_path_func=_validate_path,
        task_id=_current_task_id.get(),
        record_operation_func=record_operation,
        execute_with_safety_func=execute_with_safety,
        get_next_sequence_func=lambda: 0,
    )


async def _get_file_info(
        file_path: str,
        follow_symlinks: bool = True,
    ) -> Dict[str, Any]:
        """获取文件信息 - 小健 2026-05-02 增加follow_symlinks"""
        from app.tools.toolhelper.file_helper import get_file_info_impl

        return await get_file_info_impl(
            file_path=file_path,
            validate_path_func=_validate_path,
            follow_symlinks=follow_symlinks,
        )


async def _compress_files(
    source_path: str,
    output_path: str,
    format: str = "zip",
    exclude_patterns: Optional[List[str]] = None,
    compression_level: int = 6,
    overwrite: bool = False,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """压缩文件或目录"""
    from app.tools.toolhelper.file_helper import compress_files_impl

    return await compress_files_impl(
        source_path=source_path,
        output_path=output_path,
        format=format,
        exclude_patterns=exclude_patterns,
        compression_level=compression_level,
        overwrite=overwrite,
        password=password,
        validate_path_func=_validate_path,
        task_id=_current_task_id.get(),
        record_operation_func=record_operation,
        execute_with_safety_func=execute_with_safety,
        get_next_sequence_func=lambda: 0,
        )


async def _extract_archive(
    archive_path: str,
    output_dir: Optional[str] = None,
    overwrite: bool = False,
    password: Optional[str] = None,
    preserve_permissions: bool = True,
) -> Dict[str, Any]:
    """解压压缩文件"""
    from app.tools.toolhelper.file_helper import extract_archive as _extract_archive_impl
    return _extract_archive_impl(
        archive_path=archive_path,
        output_dir=output_dir,
        overwrite=overwrite,
        password=password,
        preserve_permissions=preserve_permissions,
    )


async def _get_file_hash(
    file_path: str,
    algorithm: str = "sha256",
    verify_against: Optional[str] = None,
    timeout: int = 30000,
) -> Dict[str, Any]:
    """计算文件哈希值"""
    from app.tools.toolhelper.file_helper import hash_file_tool
    return hash_file_tool(
        file_path=file_path,
        algorithm=algorithm,
    )


async def _file_statistics(
    directory: str,
    recursive: bool = True,
    max_depth: int = 100000,
    filters: Optional[Dict[str, Any]] = None,
    output_format: str = "json",
) -> Dict[str, Any]:
    """统计文件系统信息"""
    from app.tools.toolhelper.file_helper import file_statistics_impl

    return await file_statistics_impl(
        directory=directory,
        recursive=recursive,
        max_depth=max_depth,
        filters=filters,
        output_format=output_format,
        validate_path_func=_validate_path,
        task_id=_current_task_id.get(),
        record_operation_func=record_operation,
        execute_with_safety_func=execute_with_safety,
        get_next_sequence_func=lambda: 0,
    )


async def _file_checksum(
    file_path: str,
    algorithm: str = "sha256",
    verify_hash: Optional[str] = None,
    chunk_size: int = 65536,
    timeout: int = 30000,
) -> Dict[str, Any]:
    """计算文件校验和"""
    t0 = _time_mod.perf_counter()
    from app.tools.toolhelper.file_helper import file_checksum_impl

    result = await file_checksum_impl(
        file_path=file_path,
        algorithm=algorithm,
        verify_hash=verify_hash,
        chunk_size=chunk_size,
        timeout=timeout,
        validate_path_func=_validate_path,
        task_id=_current_task_id.get(),
        record_operation_func=record_operation,
        execute_with_safety_func=execute_with_safety,
        get_next_sequence_func=lambda: 0,
    )
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    llm_data = _build_file_checksum_llm_data("success", duration_ms, algorithm=algorithm,
                                              verify_result=result.get("data", {}).get("verify_result"))
    result["llm_data"] = llm_data
    return result


async def read_media_file(
    file_path: str,
) -> Dict[str, Any]:
        """读取媒体文件,返回Base64编码"""
        t0 = _time_mod.perf_counter()
        try:
            is_valid, error_msg = _validate_path(file_path)
            if not is_valid:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=error_msg)
                return build_error(data={"file_path": file_path}, llm_data=llm_data)

            path = Path(file_path)
            if not path.exists():
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=f"文件不存在: {file_path}")
                return build_error(data={"file_path": file_path}, llm_data=llm_data)
            if not path.is_file():
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=f"路径不是文件: {file_path}")
                return build_error(data={"file_path": file_path}, llm_data=llm_data)

            file_size = path.stat().st_size
            if file_size > MAX_MEDIA_READ_SIZE:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=f"媒体文件过大({file_size}字节),超过读取上限{MAX_MEDIA_READ_SIZE//1024//1024}MB")
                return build_error(data={"file_path": file_path, "file_size": file_size}, llm_data=llm_data)

            suffix = path.suffix.lower()
            if suffix == '.pdf':
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail="PDF文件请使用read_document工具读取")
                return build_error(data={"file_path": file_path}, llm_data=llm_data)

            mime_map = {
                ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
                ".svg": "image/svg+xml", ".tiff": "image/tiff", ".tif": "image/tiff",
                ".ico": "image/x-icon", ".heic": "image/heic", ".heif": "image/heif",
                ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg",
                ".m4a": "audio/mp4", ".flac": "audio/flac", ".aac": "audio/aac",
                ".wma": "audio/x-ms-wma", ".mid": "audio/midi", ".midi": "audio/midi",
                ".mp4": "video/mp4", ".avi": "video/x-msvideo", ".mov": "video/quicktime",
                ".mkv": "video/x-matroska", ".webm": "video/webm", ".wmv": "video/x-ms-wmv",
            }
            mime_type = mime_map.get(suffix, "application/octet-stream")

            def _read_sync():
                with open(path, 'rb') as f:
                    return base64.b64encode(f.read()).decode('utf-8')

            b64_data = await asyncio.to_thread(_read_sync)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_media_file_llm_data("success", duration_ms, file_path=str(path), file_name=path.name, mime_type=mime_type, file_size=path.stat().st_size)
            return build_success(
                data={"file_name": path.name, "mime_type": mime_type, "file_size": path.stat().st_size, "base64_data": b64_data},
                llm_data=llm_data,
            )
        except Exception as e:
            logger.error(f"read_media_file failed: {file_path}: {e}")
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_media_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e))
            return build_error(data={"error": str(e), "file_path": file_path}, llm_data=llm_data)


async def _read_batch_file(
    file_paths: List[str],
) -> Dict[str, Any]:
    """同时读取多个文本文件 - 小沈 2026-05-01"""
    t0 = _time_mod.perf_counter()
    if not file_paths:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_text_file_llm_data("error", duration_ms, detail="文件路径列表为空")
        return build_error(data={"file_paths": file_paths}, llm_data=llm_data)

    if len(file_paths) > MAX_BATCH_FILE_COUNT:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_text_file_llm_data("error", duration_ms, detail=f"批量读取文件数({len(file_paths)})超过上限{MAX_BATCH_FILE_COUNT},请分批读取")
        return build_error(data={"count": len(file_paths), "max": MAX_BATCH_FILE_COUNT}, llm_data=llm_data)

    semaphore = asyncio.Semaphore(20)

    async def _read_single(fp: str) -> Dict[str, Any]:
        async with semaphore:
            is_binary, binary_reason = _is_binary_file(fp)
            if is_binary:
                llm_data = _build_read_text_file_llm_data("error", 0, file_path=fp, detail=f"{binary_reason}。已跳过该文件")
                return build_error(data={"file_path": fp}, llm_data=llm_data)

            is_valid, error_msg = _validate_path(fp)
            if not is_valid:
                llm_data = _build_read_text_file_llm_data("error", 0, file_path=fp, detail=error_msg)
                return build_error(data={"file_path": fp}, llm_data=llm_data)
            path = Path(fp)
            if not path.exists():
                llm_data = _build_read_text_file_llm_data("error", 0, file_path=fp, detail=f"文件不存在: {fp}")
                return build_error(data={"file_path": fp}, llm_data=llm_data)

            try:
                if path.stat().st_size > MAX_READ_SIZE:
                    llm_data = _build_read_text_file_llm_data("error", 0, file_path=fp, detail=f"文件过大({path.stat().st_size}字节),超过读取上限")
                    return build_error(data={"file_path": fp}, llm_data=llm_data)
            except OSError as e:
                llm_data = _build_read_text_file_llm_data("error", 0, file_path=fp, detail=str(e))
                return build_error(data={"file_path": fp}, llm_data=llm_data)

            try:
                for enc in ["utf-8", "gbk", "gb2312", "utf-8-sig"]:
                    try:
                        def _read_with(e=enc):
                            with open(path, 'r', encoding=e, errors='replace') as f:
                                return f.read()
                        content = await asyncio.to_thread(_read_with)
                        if '\ufffd' in content:
                            continue
                        return build_success(data={"file_path": fp, "content": content, "encoding": enc, "file_size": path.stat().st_size})
                    except Exception:
                        continue
                llm_data = _build_read_text_file_llm_data("error", 0, file_path=fp, detail=f"无法解码文件: {fp}")
                return build_error(data={"file_path": fp}, llm_data=llm_data)
            except Exception as e:
                llm_data = _build_read_text_file_llm_data("error", 0, file_path=fp, detail=str(e))
                return build_error(data={"file_path": fp}, llm_data=llm_data)

    results = await asyncio.gather(*[_read_single(fp) for fp in file_paths])
    success_count = sum(1 for r in results if r.get("code") == "SUCCESS")
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    llm_data = _build_read_text_file_llm_data("success", duration_ms, line_count=success_count, total_lines=len(results))
    return build_success(
        data={"results": results, "total": len(results), "success_count": success_count, "failed_count": len(results) - success_count},
        llm_data=llm_data,
    )


async def _precise_replace_in_file(
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        ignore_case: bool = False,
        dry_run: bool = False,
        encoding: Optional[str] = None,
    ) -> Dict[str, Any]:
        """精确替换文件中的字符串(21.1 重构,小沈 2026-05-25 实施)
        2026-06-19 小健 修复: 移除self参数,改为独立函数调用"""
        if not old_string:
            llm_data = _build_replace_file_llm_data("error", 0, file_path=file_path, detail="old_string不能为空,空字符串替换会导致内容爆炸")
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

        task_id = _current_task_id.get(None)
        if not task_id:
            llm_data = _build_replace_file_llm_data("error", 0, file_path=file_path, detail="当前没有活跃任务ID")
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

        is_binary, reason = _is_binary_file(file_path)
        if is_binary:
            llm_data = _build_replace_file_llm_data("error", 0, file_path=file_path, detail=f"{reason}。请使用专业工具操作二进制文件")
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

        t0 = _time_mod.perf_counter()
        try:
            is_valid, err = _validate_path(file_path)
            if not is_valid:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_replace_file_llm_data("error", duration_ms, file_path=file_path, detail=err)
                return build_error(data={"file_path": file_path}, llm_data=llm_data)
            path = Path(file_path)
            if not path.exists():
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_replace_file_llm_data("error", duration_ms, file_path=file_path, detail=f"文件不存在: {file_path}")
                return build_error(data={"file_path": file_path}, llm_data=llm_data)
            if path.stat().st_size > MAX_READ_SIZE:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_replace_file_llm_data("error", duration_ms, file_path=file_path, detail=f"文件过大({path.stat().st_size}字节),超过替换上限{MAX_READ_SIZE//1024//1024}MB")
                return build_error(data={"file_path": file_path, "file_size": path.stat().st_size}, llm_data=llm_data)

            operation_id = record_operation(
                task_id=task_id, operation_type=OperationType.MODIFY,
                destination_path=path, sequence_number=0,
            )

            content, used_enc, err_msg = await _try_read_file_with_encodings(path, encoding)
            if err_msg:
                raise ValueError(err_msg)

            replace_result = {}

            def _replace_sync() -> bool:
                new_content, count = _apply_replacement(content, old_string, new_string, ignore_case, replace_all)
                replace_result['count'] = count
                replace_result['used_enc'] = used_enc
                if dry_run:
                    return True
                _write_file_atomic(new_content, path, used_enc, append=False, create_parents=False)
                return True

            success = await asyncio.to_thread(
                execute_with_safety,
                operation_id,
                operation_func=_replace_sync
            )
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            if not success:
                llm_data = _build_replace_file_llm_data("error", duration_ms, file_path=str(path), detail="文件替换失败,safety拦截")
                return build_error(data={"file_path": str(path)}, llm_data=llm_data)

            data = {
                "replaced_count": replace_result['count'],
                "encoding": replace_result['used_enc'],
                "file_path": str(path),
                "file_name": path.name,
                "operation_id": operation_id,
            }
            if dry_run:
                data["preview"] = True
                data["diff_info"] = (f"将替换 {replace_result['count']} 处匹配: "
                                    f"'{old_string[:50]}' -> '{new_string[:50]}'")
            llm_data = _build_replace_file_llm_data("success", duration_ms, file_path=str(path), replaced_count=replace_result['count'])
            return build_success(
                data=data,
                llm_data=llm_data,
            )

        except ValueError as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_replace_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e))
            return build_error(data={"error": str(e), "file_path": file_path}, llm_data=llm_data)
        except Exception as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_replace_file_llm_data("error", duration_ms, file_path=file_path, detail=f"替换失败: {e}")
            return build_error(data={"error": str(e), "file_path": file_path}, llm_data=llm_data)


def _read_file_with_encodings_sync(path: Path, preferred: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """同步读取文件,自动尝试编码 - 小健 2026-05-25

    复用自 _try_read_file_with_encodings(L709)的同步版本,
    供 _edit_sync 等同步闭包使用。
    """
    encodings_to_try = [preferred] if preferred else []
    encodings_to_try.extend(["utf-8", "gbk", "gb2312", "utf-8-sig"])
    for enc in encodings_to_try:
        if enc is None:
            continue
        try:
            with open(path, 'r', encoding=enc, errors='replace') as f:
                content = f.read()
            return content, enc, None
        except Exception:
            continue
    return None, None, f"无法读取文件: {path},已尝试编码: {encodings_to_try}"


def _apply_single_edit(content: str, edit: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """对内容执行一次编辑,返回 (新内容, 编辑结果)。

    小沈 2026-05-25 重构拆分
    消除 R1a-c 的 3 路 if-elif 重复(行1926-1934)。
        YAGNI: 不再返回 old_text/new_text——调用方仅需知悉编辑是否成功。

        edit: {"oldText": str, "newText": str}
        返回 edit_result: {ok, reason} 或 {ok}
        """
    old_text = edit.get("oldText", "")
    new_text = edit.get("newText", "")

    if not old_text:
        return content, {"ok": False, "reason": "oldText 为空"}

    idx = content.find(old_text)
    if idx == -1:
        return content, {"ok": False, "reason": f"未找到匹配: {old_text[:50]}"}

    new_content = content[:idx] + new_text + content[idx + len(old_text):]
    return new_content, {"ok": True}


def _execute_edit_sync(path: Path, edits: List[Dict], dry_run: bool, encoding: Optional[str], edit_result: Dict) -> bool:
    """执行文件编辑同步操作 — 小健 2026-05-25 重构拆分

    使用场景:
        _apply_edits中作为同步操作函数传递给safety.execute_with_safety

    使用示例:
        edit_result = {}
        success = _execute_edit_sync(path, edits, dry_run, encoding, edit_result)

    返回数据说明:
        - 返回bool,True表示成功
        - edit_result会被填充编辑结果(applied_edits/total_edits/results/preview/dry_run/used_enc)
    """
    content, used_enc, err_msg = _read_file_with_encodings_sync(path, encoding)
    if err_msg:
        raise ValueError(err_msg)

    modified = content
    results = []
    for i, edit in enumerate(edits):
        modified, result = _apply_single_edit(modified, edit)
        result["index"] = i
        results.append(result)

    applied = sum(1 for r in results if r["ok"])
    if not dry_run and applied > 0:
        _write_file_atomic(modified, path, used_enc, append=False, create_parents=False)

    edit_result['applied_edits'] = applied
    edit_result['total_edits'] = len(edits)
    edit_result['results'] = results
    edit_result['preview'] = modified if dry_run else None
    edit_result['dry_run'] = dry_run
    edit_result['used_enc'] = used_enc
    return True


async def _apply_edits(
    file_path: str,
    edits: List[Dict[str, str]],
    dry_run: bool = False,
    encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """高级编辑文件,支持多处编辑和预览(内部方法) — 小健 2026-05-25 重构拆分

    使用场景:
        内部调用

    使用示例:
        result = await _apply_edits('test.py', [{'oldText': 'old', 'newText': 'new'}])

    返回数据说明:
        - 返回Dict,包含applied_edits/total_edits/results/preview/dry_run/encoding/operation_id
    """
    t0 = _time_mod.perf_counter()
    try:
        is_valid, error_msg = _validate_path(file_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail=error_msg)
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

        task_id = _current_task_id.get()
        if not task_id:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="当前没有活跃任务ID")
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

        is_binary, binary_reason = _is_binary_file(file_path)
        if is_binary:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"{binary_reason}。请使用对应的专业工具操作二进制文件")
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

        path = Path(file_path)
        if not path.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"文件不存在: {file_path}")
            return build_error(data={"file_path": file_path}, llm_data=llm_data)

        if path.stat().st_size > MAX_READ_SIZE:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail=f"文件过大({path.stat().st_size}字节),超过编辑上限{MAX_READ_SIZE//1024//1024}MB")
            return build_error(data={"file_path": file_path, "file_size": path.stat().st_size}, llm_data=llm_data)

        operation_id = record_operation(
            task_id=task_id,
            operation_type=OperationType.MODIFY,
            destination_path=path,
            sequence_number=0
        )

        edit_result = {}
        success = await asyncio.to_thread(
            execute_with_safety,
            operation_id,
            operation_func=lambda: _execute_edit_sync(path, edits, dry_run, encoding, edit_result)
        )
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if success:
            applied = edit_result['applied_edits']
            total = edit_result['total_edits']
            llm_data = _build_edit_text_file_llm_data("success", duration_ms, file_path, applied, total)
            return build_success(
                data={
                    "applied_edits": applied,
                    "total_edits": total,
                    "results": edit_result['results'],
                    "preview": edit_result['preview'],
                    "dry_run": edit_result['dry_run'],
                    "encoding": edit_result['used_enc'],
                    "operation_id": operation_id,
                },
                llm_data=llm_data,
            )
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail="文件编辑失败,safety拦截")
        return build_error(data={"file_path": file_path}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"edit_text_file failed: {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_edit_text_file_llm_data("error", duration_ms, file_path=file_path, detail=str(e))
        return build_error(data={"error": str(e), "file_path": file_path}, llm_data=llm_data)


async def grep_file_content(
    pattern: str,
    search_dir: Optional[str] = None,
    glob: Optional[str] = None,
    ignore_case: bool = True,
) -> Dict[str, Any]:
    """基于正则的内容搜索 — 小沈 2026-05-19, 2026-05-25 小健重构拆分
    【2026-06-20 小健】删multiline/head_limit/page_token/output_mode/context
    """
    multiline = False
    head_limit = None
    page_token = None
    output_mode = "content"
    after_lines = before_lines = context_lines = None
    t0 = _time_mod.perf_counter()
    try:
        search_path = Path(search_dir).resolve() if search_dir else Path.cwd().resolve()
        is_valid, error_msg = _validate_path(str(search_path))
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=str(search_path), detail=error_msg)
            return build_error(data={"file_path": str(search_path)}, llm_data=llm_data)
        if not pattern:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=str(search_path), detail="搜索模式不能为空")
            return build_error(data={"pattern": pattern}, llm_data=llm_data)

        deadline = time.monotonic() + TOOL_TIMEOUTS.get("grep_file_content", TOOL_TIMEOUTS["default"]) - 2
        matches, total_matches = await asyncio.to_thread(
            _grep_files_sync, search_path, pattern, glob, output_mode,
            ignore_case, multiline, head_limit, context_lines, after_lines, before_lines, deadline
        )

        total = len(matches)
        page_results, next_page_token = _paginate_results(matches, page_token, DEFAULT_PAGE_SIZE)
        has_more = next_page_token is not None

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("success", duration_ms, pattern=pattern, search_dir=str(search_path), total_files=total, total_matches=total_matches)
        return build_success(
            data={
                "matches": page_results,
                "total_files": total,
                "total_matches": total_matches,
                "pattern": pattern,
                "search_dir": str(search_path),
                "output_mode": output_mode,
                "has_more": has_more,
                "next_page_token": next_page_token,
            },
            llm_data=llm_data,
        )
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data("error", duration_ms, pattern=pattern, search_dir=str(search_dir) if search_dir else "", detail=str(e))
        return build_error(data={"error": str(e), "pattern": pattern, "search_dir": str(search_dir)}, llm_data=llm_data)


async def get_directory_tree(dir_path: str) -> Dict[str, Any]:
    """获取目录树(委托给 _get_directory_tree 实现)

        规范:§11.10 浏览器禁止执行write、chmod等shell操作
        通过 path_utils.validate_and_normalize 实现安全路径检查
        """
    return await _get_directory_tree(dir_path)


async def _get_directory_tree(
    dir_path: str,
    excludePatterns: Optional[List[str]] = None,
    max_depth: Optional[int] = None,
) -> Dict[str, Any]:
    """获取目录的递归JSON树结构 - 小沈 2026-05-01"""
    t0 = _time_mod.perf_counter()
    try:
        is_valid, error_msg = _validate_path(dir_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_directory_tree_llm_data("error", duration_ms, dir_path=dir_path, detail=error_msg)
            return build_error(data={"file_path": dir_path}, llm_data=llm_data)

        path = Path(dir_path)
        if not path.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_directory_tree_llm_data("error", duration_ms, dir_path=dir_path, detail=f"目录不存在: {dir_path}")
            return build_error(data={"file_path": dir_path}, llm_data=llm_data)
        if not path.is_dir():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_directory_tree_llm_data("error", duration_ms, dir_path=dir_path, detail=f"不是目录: {dir_path}")
            return build_error(data={"file_path": dir_path}, llm_data=llm_data)

        # 【修复 2026-05-01 小沈】默认max_depth防止无限递归
        effective_max_depth = max_depth if max_depth is not None else 10
        excludes = excludePatterns or []
        entry_count = [0]
        # 【修复 2026-05-10 小健】超时自检
        _tree_deadline = time.monotonic() + TOOL_TIMEOUTS.get("get_directory_tree", TOOL_TIMEOUTS["default"]) - 2
        _tree_timed_out = False

        def _build_tree(current_path: Path, depth: int = 0) -> Optional[Dict[str, Any]]:
            nonlocal _tree_timed_out
            if _tree_timed_out:
                return None
            if depth > effective_max_depth:
                return None
            # 【修复 2026-05-01 小沈】条目数上限防护
            if entry_count[0] >= MAX_PAGE_SIZE:
                return None
            # 【修复 2026-05-01 小沈】符号链接循环防护:跳过符号链接目录
            if current_path.is_dir() and current_path.is_symlink():
                return None
            if time.monotonic() > _tree_deadline:
                _tree_timed_out = True
                logger.warning(f"[get_directory_tree] 超时自检触发,已收集{entry_count[0]}条,提前返回")
                return None
            name = current_path.name
            for pattern in excludes:
                if fnmatch.fnmatch(name, pattern):
                    return None
            if current_path.is_file():
                entry_count[0] += 1
                return {"name": name, "type": "file"}
            try:
                children = []
                for item in sorted(current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                    child = _build_tree(item, depth + 1)
                    if child is not None:
                        children.append(child)
                entry_count[0] += 1
                return {"name": name, "type": "directory", "children": children}
            except (PermissionError, OSError):
                return {"name": name, "type": "directory", "children": []}

        tree = await asyncio.to_thread(_build_tree, path)
        tree = tree or {"name": path.name, "type": "directory", "children": []}
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_directory_tree_llm_data("success", duration_ms, dir_path=str(path), root_name=tree.get("name",""), child_count=len(tree.get("children",[])))
        return build_success(
            data={"tree": tree, "root": str(path)},
            llm_data=llm_data,
        )
    except Exception as e:
        logger.error(f"get_directory_tree failed: {dir_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_directory_tree_llm_data("error", duration_ms, dir_path=dir_path, detail=str(e))
        return build_error(data={"error": str(e), "file_path": dir_path}, llm_data=llm_data)


# ============================================================
# 第九部分:精简合并工具(v2.0)— 小沈 2026-05-18
# ============================================================

async def read_text_file(
    file_path: str,
    head: Optional[int] = None,
    tail: Optional[int] = None,
    offset: Optional[int] = None,
    limit: Optional[int] = None,
    encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """读取文本文件"""
    return await _read_text_file(
        file_path=file_path,
        head=head,
        tail=tail,
        offset=offset,
        limit=limit,
        encoding=encoding
    )

async def edit_text_file(
    file_path: str,
    old_string: str,
    new_string: str = "",
    replace_all: bool = False,
    encoding: Optional[str] = None,
) -> Dict[str, Any]:
    """编辑文本文件 — 小健 2026-06-20 删dry_run参数"""
    dry_run = False
    ignore_case = False
    return await _precise_replace_in_file(
        file_path=file_path,
        old_string=old_string,
        new_string=new_string,
        replace_all=replace_all,
        ignore_case=ignore_case,
        dry_run=dry_run,
        encoding=encoding
    )

async def compress_files(
    source: str,
    destination: str,
    format: str = "zip",
    password: Optional[str] = None,
    overwrite: bool = False,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """压缩文件/目录 — 小沈 2026-06-16, 小健 2026-06-20 删compression_level; 加coerce_json防御; 透传重新包装llm_data"""
    t0 = _time_mod.perf_counter()
    exclude_patterns = coerce_json(exclude_patterns)
    compression_level = 6
    result = await _compress_files(
        source_path=source,
        output_path=destination,
        format=format,
        exclude_patterns=exclude_patterns,
        compression_level=compression_level,
        overwrite=overwrite,
        password=password
    )
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    if result.get("code") == "SUCCESS":
        llm_data = _build_file_op_llm_data("success", duration_ms, "compress_files", "压缩文件", target=source)
        return build_success(data=result.get("data", {}), llm_data=llm_data)
    llm_data = _build_file_op_llm_data("error", duration_ms, "compress_files", "压缩文件", target=source, detail=result.get("data", {}).get("error", "压缩失败"))
    return build_error(data=result.get("data", {}), llm_data=llm_data)

async def extract_archive(
    source: str,
    destination: Optional[str] = None,
    password: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """解压归档包 — 小沈 2026-06-16"""
    result = await _extract_archive(
        archive_path=source,
        output_dir=destination,
        overwrite=overwrite,
        password=password,
        preserve_permissions=True
    )
    if "data" not in result:
        llm_data = _build_file_op_llm_data("error", 0, "extract_archive", "解压文件", target=source, detail=result.get("data", {}).get("error", "解压失败"))
        return build_error(data={"archive_path": source}, llm_data=llm_data)
    llm_data = _build_file_op_llm_data("success", 0, "extract_archive", "解压文件", target=source)
    return build_success(data=result.get("data", {}), llm_data=llm_data)

async def move_file(
    source: str,
    destination: str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """移动文件/目录 — 小沈 2026-06-16"""
    if os.path.abspath(source) == os.path.abspath(destination):
        llm_data = _build_file_op_llm_data("success", 0, "move_file", "移动", source, extra_metrics={"status": "no_change"})
        return build_success(data={"action": "move", "source": source, "destination": destination}, llm_data=llm_data)
    return await _move_file(
        source_path=source,
        destination_path=destination,
        overwrite=overwrite
    )

async def copy_file(
    source: str,
    destination: str,
    recursive: bool = False,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """复制文件/目录 — 小沈 2026-06-16, 小健 2026-06-20 删preserve_metadata"""
    preserve_metadata = True
    if os.path.abspath(source) == os.path.abspath(destination):
        llm_data = _build_file_op_llm_data("success", 0, "copy_file", "复制", source, extra_metrics={"status": "no_change"})
        return build_success(data={"action": "copy", "source": source, "destination": destination}, llm_data=llm_data)
    result = await _copy_file(
        source_path=source,
        destination_path=destination,
        recursive=recursive,
        overwrite=overwrite,
        preserve_metadata=preserve_metadata
    )
    if result.get("code") == "SUCCESS":
        llm_data = _build_file_op_llm_data("success", 0, "copy_file", "复制文件", target=source)
        return build_success(data=result.get("data", {}), llm_data=llm_data)
    llm_data = _build_file_op_llm_data("error", 0, "copy_file", "复制文件", target=source, detail=result.get("data", {}).get("error", "复制失败"))
    return build_error(data=result.get("data", {}), llm_data=llm_data)

async def delete_file(
    source: str,
    recursive: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """删除文件/目录 — 小沈 2026-06-16"""
    src_path = Path(source)
    if not src_path.exists():
        llm_data = _build_file_op_llm_data("success", 0, "delete_file", "删除", source, extra_metrics={"status": "already_deleted"})
        return build_success(data={"action": "delete", "source": source}, llm_data=llm_data)
    return await _delete_file(
        file_path=source,
        recursive=recursive,
        force=force
    )

async def rename_file(
    source: str,
    destination: str,
) -> Dict[str, Any]:
    """重命名文件/目录 — 小沈 2026-06-16"""
    src = Path(source)
    new_name = Path(destination).name
    dst = src.parent / new_name
    if src.name == new_name:
        llm_data = _build_file_op_llm_data("success", 0, "rename_file", "重命名", source, extra_metrics={"status": "no_change"})
        return build_success(data={"action": "rename", "source": source, "destination": str(dst)}, llm_data=llm_data)
    return await _move_file(
        source_path=source,
        destination_path=str(dst),
        overwrite=False
    )


def _build_format_result(
    result: Dict[str, Any], action: str,
    detected_format: str, file_path: str,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """构建 data_file_format 的统一返回数据 + llm_data — 小健 2026-06-21 builder改造"""
    if result.get("code", "").startswith("ERR_"):
        llm_data = _build_data_format_llm_data("error", 0, file_path, detected_format, action, detail=result.get("message", "未知错误"))
        return build_error(data={"file_path": file_path}, llm_data=llm_data), llm_data

    result_data = result.get("data", result)
    suffix = {}

    if action == "write":
        try:
            suffix["bytes_written"] = os.path.getsize(file_path)
        except Exception:
            pass

    item_count = 0
    if action == "read":
        if isinstance(result_data, dict):
            item_count = len(result_data)
        elif isinstance(result_data, list):
            item_count = len(result_data)
    elif action == "write":
        item_count = suffix.get("bytes_written", 0)

    llm_data = _build_data_format_llm_data("success", 0, file_path, detected_format, action, item_count=item_count)
    return build_success(
        data={"data": result_data, "format": detected_format,
         "file_path": file_path, "action": action, **suffix},
        llm_data=llm_data,
    ), llm_data


async def _data_format_exec(
    file_path: str, action: str, detected: str,
    encoding: str, data: Optional[Any] = None, indent: Optional[int] = None
) -> Dict[str, Any]:
    """内部执行:格式检测+分发调度 — 小欧 2026-06-17"""
    dispatch = _FORMAT_DISPATCH.get(detected)
    if not dispatch:
        llm_data = _build_data_format_llm_data("error", 0, file_path=file_path, detail=f"不支持的格式: {detected}")
        return build_error(data={"format": detected, "file_path": file_path}, llm_data=llm_data)
    func = dispatch[action]
    if func is None:
        llm_data = _build_data_format_llm_data("error", 0, file_path=file_path, detail=f"{detected.upper()}格式暂不支持{action}操作")
        return build_error(data={"format": detected, "action": action, "file_path": file_path}, llm_data=llm_data)
    try:
        kwargs = {"file_path": file_path, "encoding": encoding}
        if action == "write":
            kwargs["data"] = data
            if detected == "json":
                kwargs["indent"] = indent or 2
            elif detected == "yaml" and indent is not None:
                kwargs["indent"] = indent
        result = await asyncio.to_thread(func, **kwargs)
        resp, _ = _build_format_result(result, action, detected, file_path)
        return resp
    except Exception as e:
        logger.error(f"[_data_format_exec] 执行失败: {e}")
        llm_data = _build_data_format_llm_data("error", 0, file_path=file_path, detail=str(e))
        return build_error(data={"error": str(e), "file_path": file_path}, llm_data=llm_data)


async def read_data_file(
    file_path: str,
    format: Optional[str] = None,
) -> Dict[str, Any]:
    """读取结构化配置文件 — 小欧 2026-06-17, 小健 2026-06-20 删encoding"""
    encoding = "utf-8"
    if not file_path:
        llm_data = _build_data_format_llm_data("error", 0, file_path=file_path, detail="file_path是必填参数")
        return build_error(data={"file_path": file_path}, llm_data=llm_data)
    is_valid, err = _validate_path(file_path)
    if not is_valid:
        llm_data = _build_data_format_llm_data("error", 0, file_path=file_path, detail=err)
        return build_error(data={"file_path": file_path}, llm_data=llm_data)
    detected = format
    if not detected:
        ext = os.path.splitext(file_path)[1].lower()
        _ext_map = {
            ".json": "json", ".yaml": "yaml", ".yml": "yaml",
            ".toml": "toml", ".ini": "ini", ".cfg": "ini",
            ".xml": "xml", ".properties": "properties",
        }
        detected = _ext_map.get(ext)
    if not detected:
        llm_data = _build_data_format_llm_data("error", 0, file_path=file_path, detail=f"无法识别文件格式: {file_path},请通过format参数指定")
        return build_error(data={"file_path": file_path}, llm_data=llm_data)
    return await _data_format_exec(file_path, "read", detected, encoding)


async def write_data_file(
    file_path: str, data: Any,
    format: Optional[str] = None,
) -> Dict[str, Any]:
    """写入结构化配置文件 — 小欧 2026-06-17, 小健 2026-06-20 删encoding/indent; 加coerce_json防御"""
    data = coerce_json(data)
    encoding = "utf-8"
    indent = None
    if not file_path:
        llm_data = _build_data_format_llm_data("error", 0, file_path=file_path, detail="file_path是必填参数")
        return build_error(data={"file_path": file_path}, llm_data=llm_data)
    if data is None:
        llm_data = _build_data_format_llm_data("error", 0, file_path=file_path, detail="data是必填参数")
        return build_error(data={"data": data}, llm_data=llm_data)
    is_valid, err = _validate_path(file_path)
    if not is_valid:
        llm_data = _build_data_format_llm_data("error", 0, file_path=file_path, detail=err)
        return build_error(data={"file_path": file_path}, llm_data=llm_data)
    detected = format
    if not detected:
        ext = os.path.splitext(file_path)[1].lower()
        _ext_map = {
            ".json": "json", ".yaml": "yaml", ".yml": "yaml",
            ".toml": "toml",
        }
        detected = _ext_map.get(ext)
    if not detected:
        llm_data = _build_data_format_llm_data("error", 0, file_path=file_path, detail=f"无法识别文件格式: {file_path},请通过format参数指定")
        return build_error(data={"file_path": file_path}, llm_data=llm_data)
    if detected in ("ini", "xml", "properties"):
        llm_data = _build_data_format_llm_data("error", 0, file_path=file_path, detail=f"{detected.upper()}格式暂不支持写入")
        return build_error(data={"format": detected, "file_path": file_path}, llm_data=llm_data)
    return await _data_format_exec(file_path, "write", detected, encoding, data, indent)

def _match_fnmatch(name: str, pattern: str, ignore_case: bool) -> bool:
    """统一封装fnmatch,消除if-else三元组重复 — 小健 2026-05-25"""
    return fnmatch.fnmatch(name, pattern) if ignore_case else fnmatch.fnmatchcase(name, pattern)


def _is_already_seen_or_skipped(name: str, seen: set, seen_count: int, start: int) -> Tuple[bool, bool]:
    """返回(is_duplicate, is_skipped_by_offset)。消除20行三段逻辑重复 — 小健 2026-05-25"""
    if name in seen:
        return True, False
    seen.add(name)
    if seen_count < start:
        return False, True
    return False, False


def _collect_entry_result(relative_path: str, name: str, fpath: Path, all_matches: List, llm_preview: List) -> None:
    """收集匹配结果到all_matches和llm_preview — 小健 2026-05-25"""
    try:
        st = fpath.stat()
        entry = {"name": name, "path": relative_path, "size": st.st_size,
                 "mtime": st.st_mtime, "type": "file" if fpath.is_file() else "directory"}
    except (PermissionError, OSError):
        entry = {"name": name, "path": relative_path, "size": 0, "mtime": 0,
                 "type": "file" if fpath.is_file() else "directory"}
    all_matches.append(entry)
    if len(llm_preview) < 30:
        llm_preview.append({"name": name, "path": relative_path, "type": entry["type"]})


def _paginate_search(all_matches: List, path: str, llm_preview: List,
                       page_size: int, start_offset: int) -> Dict:
    """分页+build_success统一构建,生成next_page_token支持游标续页 — 小健 2026-05-25"""
    total = len(all_matches)
    has_more = total > page_size
    page = all_matches[:page_size] if has_more else all_matches
    next_page_token = encode_page_token(start_offset + page_size) if has_more else None
    llm_data = _build_search_files_llm_data("success", 0, path, total)
    return build_success(data={
        "pattern": "", "search_dir": path, "matches": page, "total": total,
        "page": 1, "total_pages": (total + page_size - 1) // page_size if has_more else 1,
        "page_size": page_size, "next_page_token": next_page_token, "has_more": has_more,
    }, llm_data=llm_data)





# ============================================================
# 第八部分:分页支持函数(原第九部分)
# ============================================================

def encode_page_token(offset: int) -> str:
    """编码页码令牌"""
    return base64.b64encode(str(offset).encode()).decode()


def decode_page_token(token: str) -> int:
    """解码页码令牌"""
    try:
        return int(base64.b64decode(token.encode()).decode())
    except Exception:  # 【修复C2 2026-05-01 小沈】移除冗余ValueError(Exception已包含)
        return 0


# 文件结束

