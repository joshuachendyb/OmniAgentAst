# -*- coding: utf-8 -*-
# 2026-11-13 商量 - 新建: bash_result 后台命令结果查询工具。按 shell_id 或 output_file 查
#   后台命令状态+输出; 通知丢失兜底 + 中途读输出(非轮询)
# 编辑历史:
# (初版)
# 2026-11-13 商量 - 改名: bash_result 改名 task_query(通用后台任务查询), 描述特别指明当前支持 bash background=true 的 Shell 后台命令
# 2026-11-13 商量 - 再改名: task_query 改名 bg_task_query, 与 SYSTEM 计划任务三件套(create/list/delete_task)语义区分
# 2026-11-13 商量 - 三堂会审根治: (1)读输出改"有界尾读"——仅读文件末尾 max_chars*4 字节再解码取尾,
#   峰值内存有界(原全量 f.read() 对 64MiB 文件峰值翻倍); (2)取尾巴而非头截断, 完成态能看到最新结果,
#   契合"中途看进度"意图; (3)output_file 直查加输出目录边界校验, 关闭任意文件读取口子
"""
S: bg_task_query — 查询后台任务执行状态与输出

当前支持的后台任务: bash background=true 的 Shell 后台命令(按 shell_id 或 output_file 查询)。
支持两种查询键: shell_id(注册表内存态, 服务重启后失效) 或 output_file(磁盘文件, 恒可查, 须位于输出目录内)。
输出按"有界尾读"取最新 max_chars 字符(与前台一样对 LLM 有界), 完成态能看到命令最新结果。
"""
import os
from typing import Any, Dict, Optional

from app.logger import logger
from app.tools.fundamental import shell_background
from app.tools.tool_constants import (
    ERR_PARAMETER_EMPTY,
    ERR_PARAMETER_INVALID,
    SHELL_OUTLIMIT_STDOUT_MAX_CHARS,
)
from app.tools.tool_response import build_error, build_success
from app.utils.path_utils import get_output_dir


def _within_output_dir(path: str) -> bool:
    """output_file 直查边界校验: 目标真实路径须位于输出目录内(防借查询工具读任意文件)。"""
    try:
        base = os.path.realpath(get_output_dir())
        target = os.path.realpath(path)
        return os.path.commonpath([base, target]) == base
    except ValueError:   # 跨盘符等无法比较
        return False


def _read_output_tail(path: str, max_chars: int) -> tuple[str, bool]:
    """有界尾读: 只读文件末尾 max_chars*4 字节(utf-8 最坏 4 字节/字符)再解码取尾。
    返回 (尾文本, 是否截断); 峰值内存 O(max_chars), 与文件大小无关。"""
    try:
        size = os.path.getsize(path)
    except OSError:
        return "", False
    if size == 0:
        return "", False
    read_bytes = max_chars * 4
    head_cut = size > read_bytes
    with open(path, "rb") as f:
        if head_cut:
            f.seek(-read_bytes, os.SEEK_END)
        data = f.read()
    text = data.decode("utf-8", errors="replace")
    if head_cut or len(text) > max_chars:
        return text[-max_chars:], True
    return text, False


def bg_task_query(
    shell_id: Optional[str] = None,
    output_file: Optional[str] = None,
) -> Dict[str, Any]:
    """查询后台 Shell 命令状态与输出

    参数:
        shell_id:    后台命令ID(bash background=true 返回值中的 shell_id)
        output_file: 输出文件路径(shell_id 注册表失效时按文件直查, 服务重启后仍可用)

    返回:
        data: {status(running/completed/failed/killed/unknown), command, returncode,
               duration_s, stdout(截断后)}
    """
    # ── 参数校验: 二选一必填 ──
    if not shell_id and not output_file:
        return build_error(data={}, llm_data={
            "summary": "查询后台命令结果，失败",
            "action": {"tool": "bg_task_query", "tool_zh": "查询", "params": {}},
            "status": {"exec_code": "error", "message": "失败", "code": ERR_PARAMETER_EMPTY,
                       "detail": "shell_id 与 output_file 至少提供一个",
                       "hint": "请从 bash background=true 的返回值或对话历史中取 shell_id"},
            "duration_ms": 0, "metrics": {}})

    # ── 路径1: shell_id 查注册表(含进程存活态) ──
    if shell_id:
        info = shell_background.get_bg_info(shell_id)
        if not info:
            # 注册表无此 id: 服务重启/已过期清理 → 若同目录文件在, 引导按文件查
            _guess = os.path.join(shell_background._bg_output_dir(), f"{shell_id}.log")
            if os.path.exists(_guess):
                info = {"output_file": _guess, "status": "unknown", "command": "", "task_id": ""}
            else:
                return build_error(data={}, llm_data={
                    "summary": f"查询后台命令{shell_id}，失败",
                    "action": {"tool": "bg_task_query", "tool_zh": "查询", "params": {"shell_id": shell_id}},
                    "status": {"exec_code": "error", "message": "失败", "code": ERR_PARAMETER_INVALID,
                               "detail": f"未找到后台命令 {shell_id}(服务重启或结果已过期清理)",
                               "hint": "请检查 shell_id 是否正确; 结果文件过期后不可恢复"},
                    "duration_ms": 0, "metrics": {}})

    # ── 路径2: output_file 直查(磁盘文件, 重启后可用; 限输出目录内) ──
    else:
        if not _within_output_dir(output_file) or not os.path.isfile(output_file):
            return build_error(data={}, llm_data={
                "summary": "查询后台命令结果，失败",
                "action": {"tool": "bg_task_query", "tool_zh": "查询", "params": {"output_file": output_file}},
                "status": {"exec_code": "error", "message": "失败", "code": ERR_PARAMETER_INVALID,
                           "detail": f"输出文件不存在或不在输出目录内: {output_file}",
                           "hint": "仅可查询输出目录下的后台命令结果文件, 请核对路径"},
                "duration_ms": 0, "metrics": {}})
        info = {"output_file": output_file, "status": "unknown", "command": "", "task_id": ""}

    # ── 有界尾读最新输出(非全量读; 完成态可见最新结果) ──
    path = info["output_file"]
    try:
        stdout_str, _trunc = _read_output_tail(path, SHELL_OUTLIMIT_STDOUT_MAX_CHARS)
    except OSError as e:
        logger.warning(f"[bg_task_query] 读输出失败({path}): {e}")
        stdout_str, _trunc = "", False

    duration_s = 0
    if "started_at" in info and "finished_at" in info:
        duration_s = int(info["finished_at"] - info["started_at"])

    data: Dict[str, Any] = {
        "status": info.get("status", "unknown"),
        "command": info.get("command", ""),
        "returncode": info.get("returncode"),
        "timed_out": info.get("timed_out", False),
        "duration_s": duration_s,
        "stdout": stdout_str,
    }
    if _trunc:
        data["_truncated"] = True
    return build_success(
        data=data,
        llm_data={
            "summary": f"查询后台命令{shell_id or os.path.basename(path)}，成功",
            "action": {"tool": "bg_task_query", "tool_zh": "查询",
                       "params": {"shell_id": shell_id or "", "output_file": output_file or ""}},
            "status": {"exec_code": "success", "message": "成功", "code": "", "detail": "", "hint": ""},
            "duration_ms": 0,
            "metrics": {"status": {"value": data["status"], "text": f"状态 {data['status']}"},
                        "output_len": {"value": len(stdout_str), "text": f"输出{len(stdout_str)}字符"}}})
