# -*- coding: utf-8 -*-
# 2026-11-13 商量 - 新建: bash_result 后台命令结果查询工具。按 shell_id 或 output_file 查
#   后台命令状态+输出; 通知丢失兜底 + 中途读输出(非轮询)
# 编辑历史:
# (初版)
"""
S: bash_result — 查询后台 Shell 命令状态与输出

支持两种查询键: shell_id(注册表内存态, 服务重启后失效) 或 output_file(磁盘文件, 恒可查)。
输出读当前文件后过 _truncate_shell_field 截断(与前台同款, LLM 侧恒有界)。
"""
import os
from typing import Any, Dict, Optional

from app.logger import logger
from app.tools.fundamental import shell_background
from app.tools.fundamental.execute_shell_command import _truncate_shell_field
from app.tools.tool_constants import (
    ERR_PARAMETER_EMPTY,
    ERR_PARAMETER_INVALID,
    SHELL_OUTLIMIT_STDOUT_MAX_CHARS,
)
from app.tools.tool_response import build_error, build_success


def bash_result(
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
            "action": {"tool": "bash_result", "tool_zh": "查询", "params": {}},
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
                    "action": {"tool": "bash_result", "tool_zh": "查询", "params": {"shell_id": shell_id}},
                    "status": {"exec_code": "error", "message": "失败", "code": ERR_PARAMETER_INVALID,
                               "detail": f"未找到后台命令 {shell_id}(服务重启或结果已过期清理)",
                               "hint": "请检查 shell_id 是否正确; 结果文件过期后不可恢复"},
                    "duration_ms": 0, "metrics": {}})

    # ── 路径2: output_file 直查(磁盘文件, 重启后可用) ──
    else:
        if not os.path.isfile(output_file):
            return build_error(data={}, llm_data={
                "summary": "查询后台命令结果，失败",
                "action": {"tool": "bash_result", "tool_zh": "查询", "params": {"output_file": output_file}},
                "status": {"exec_code": "error", "message": "失败", "code": ERR_PARAMETER_INVALID,
                           "detail": f"输出文件不存在: {output_file}",
                           "hint": "请核对文件路径"},
                "duration_ms": 0, "metrics": {}})
        info = {"output_file": output_file, "status": "unknown", "command": "", "task_id": ""}

    # ── 读输出(单文件; 不做轮转, 进程写端只管追加) ──
    path = info["output_file"]
    parts = []
    if os.path.isfile(path):
        try:
            with open(path, "rb") as f:
                parts.append(f.read())
        except OSError as e:
            logger.warning(f"[bash_result] 读输出失败({path}): {e}")
    raw = b"".join(parts)
    stdout_str = raw.decode("utf-8", errors="replace")
    stdout_str, _trunc = _truncate_shell_field(stdout_str, SHELL_OUTLIMIT_STDOUT_MAX_CHARS)

    duration_s = 0
    if "started_at" in info and "finished_at" in info:
        duration_s = int(info["finished_at"] - info["started_at"])

    data: Dict[str, Any] = {
        "status": info.get("status", "unknown"),
        "command": info.get("command", ""),
        "returncode": info.get("returncode"),
        "duration_s": duration_s,
        "stdout": stdout_str,
    }
    if _trunc:
        data["_truncated"] = True
    return build_success(
        data=data,
        llm_data={
            "summary": f"查询后台命令{shell_id or os.path.basename(path)}，成功",
            "action": {"tool": "bash_result", "tool_zh": "查询",
                       "params": {"shell_id": shell_id or "", "output_file": output_file or ""}},
            "status": {"exec_code": "success", "message": "成功", "code": "", "detail": "", "hint": ""},
            "duration_ms": 0,
            "metrics": {"status": {"value": data["status"], "text": f"状态 {data['status']}"},
                        "output_len": {"value": len(stdout_str), "text": f"输出{len(stdout_str)}字符"}}})
