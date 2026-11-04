# -*- coding: utf-8 -*-
# 2026-10-04 小欧 - obs方案A: 删action.target(params承载目标)+document params file_path→path
# 编辑历史:
# 2026-07-15 - 小欧 - rename新增overwrite参数并透传_move_file_impl: 原硬编码overwrite=False且不向LLM暴露该参数, 目标已存在时FileExistsError无法被LLM用overwrite=True纠正。对齐move/copy新增overwrite字段(默认False, 向后兼容)。另修复执行失败时被execute_with_safety吞掉真因的问题。
# 2026-08-21 - 小欧 - 11.6.1: 两个success分支调 with_artifact_file 声明产出物
# 2026-09-20 - 小欧 - 写仲裁落地: 重命名目标 with claim_write 登记文件写仲裁(外层包裹显式声明重命名写意图,
#   impl 内层同任务登记幂等), 防跨任务并行覆盖; 仅仲裁不强制, 行为零退化。
#   compliance: DRY(复用 arbiter claim_write)/KISS-DIRECT
# 2026-10-05 - 小欧 - 单通道补 metrics(小欧): success 补 size(重命名后目标 stat)/同名分支 size 取原文件
#   + changed=0, 结构化承接结果量; summary 不动
# 2026-10-16 - 小欧 - tool去检查化: 删空参守卫与源合法性检查(归 路径安全层); new_name 保留字符改调 utils 原子。
# 2026-10-17 小欧 - 接入 path_utils.check_path_four_level 四级合法性总入口(仅判源 EXISTS; dest 语义是"新文件名"非路径, 判之会误拦)
"""
F13: rename_file — 重命名文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional

from app.tools.file.move_file import _move_file_impl
from app.tools.tool_response import build_success, build_error, with_artifact_file
from app.tools.tool_constants import ERR_FILE_RENAME_FAILED
from app.utils.path_utils import (  # 2026-10-17 小欧: 路径四级合法性总入口 + 保留字符原子(派生名格式检查用)
    OpCategory,
    check_path_four_level,
    path_has_reserved_char,
)
from app.tools.context import _current_task_id  # A-2: 写仲裁登记使用任务ID — 小欧 2026-09-20
from app.tools.file.file_write_arbiter import claim_write  # 2026-09-20 - 小欧 - A-2: 跨任务文件写仲裁(acquire_write/release_write 上下文)接入(X2) — 重命名登记占用


def _build_rename_file_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", new_name: str = "", detail: str = "", hint: str = "",
    user_destination: str = "", user_overwrite: Optional[bool] = None,
    file_size: int = 0, changed: Optional[int] = None,
) -> Dict[str, Any]:
    """rename_file的llm_data构建函数 — 小健 2026-06-22 — 小沈 2026-07-05 新增hint参数 — 小欧 2026-07-15 新增overwrite"""
    _act_params = {"source": source, "new_name": new_name}
    if user_destination:
        _act_params["destination"] = user_destination
    if user_overwrite is not None:
        _act_params["overwrite"] = user_overwrite
    if exec_code == "error":
        return {
            "summary": f"重命名文件{source}，失败",
            "action": {"tool": "rename", "tool_zh": "重命名", "params": _act_params},
            "status": {"exec_code": "error", "message": "失败", "code": ERR_FILE_RENAME_FAILED, "detail": detail, "hint": hint if hint else "请检查源路径和新名称"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    _summary = f"重命名文件{source} → {new_name}，成功" if new_name else f"重命名文件{source}"
    # 2026-10-05 小欧 - 单通道补 metrics(小欧): size 结构化承接文件大小
    # 2026-10-14 小欧 - summary 统一口径: 动词用 tool_zh, 成功后置, 去"重命名 "多余空格 — 小欧-2026-10-14
    _metrics: Dict[str, Any] = {}
    if file_size:
        _metrics["size"] = {"value": file_size, "text": f"{file_size}字节"}
    if changed is not None:
        _metrics["changed"] = {"value": changed, "text": f"{changed}项改动"}
    return {
        "summary": _summary,
        "action": {"tool": "rename", "tool_zh": "重命名", "params": _act_params},
        "status": {"exec_code": "success", "message": "成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": _metrics,
    }


async def rename(
    path: str,
    dest: str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """重命名文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件 — 小健 2026-06-22 重构：独立builder — 小欧 2026-07-04 增加空串验证 — 小欧 2026-07-11 路径参数统一为path/dest — 小欧 2026-07-15 新增overwrite参数透传"""
    t0 = _time_mod.perf_counter()
    # 路径参数统一为path/dest,桥接到内部变量source/destination — 小欧 2026-07-11
    source = path
    destination = dest
    # 2026-10-17 小欧 - 路径检查走 check_path_four_level 四级合法性总入口(仅源: dest 语义是"新文件名"非路径)
    #   发现: 本工具 dest 只取 Path(dest).name 后落 src.parent(L99/L107), 并非目标路径;
    #   对它判路径会把相对名 realpath 成 cwd(=backend) 而误命中代码目录, 故只判源。
    ok, err = check_path_four_level(source, OpCategory.EXISTS)
    if not ok:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_rename_file_llm_data("error", duration_ms, source, detail=err, hint="请检查源路径", user_destination=destination, user_overwrite=overwrite)
        return build_error(data={}, llm_data=llm_data)
    # 2026-10-16 小欧 - tool去检查化: 空参/源合法性由 路径安全层 唯一检查, 工具只执行
    # 派生名 new_name 是运行时派生, safety 不可见, 由执行方在派生点做格式检查(调 utils 纯函数)
    new_name = Path(destination).name
    _bad = path_has_reserved_char(new_name)
    if _bad:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_rename_file_llm_data("error", duration_ms, source, detail=f"包含Windows保留字符：{destination}", hint="文件名包含Windows保留字符，请修改", user_destination=destination, user_overwrite=overwrite)
        return build_error(data={}, llm_data=llm_data)

    src = Path(source)
    dst = src.parent / new_name

    if src.name == new_name:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        try:
            _same_size = src.stat().st_size if src.is_file() else 0
        except OSError:
            _same_size = 0
        llm_data = _build_rename_file_llm_data("success", duration_ms, source, new_name=new_name, user_destination=destination, user_overwrite=overwrite, file_size=_same_size, changed=0)
        llm_data["summary"] = f"重命名文件{source}，成功: {new_name}（名称相同，无操作）"
        llm_data["status"]["message"] = "名称相同，无需重命名"
        with_artifact_file(llm_data, str(dst))   # 11.6.1 产出物声明 — 小欧 2026-08-21
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback (key:val) — skipped path
        # trigger: 无上述20条分支匹配 — skipped/reason 不命中专用分支
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(data={}, llm_data=llm_data)

    # 重命名目标登记写仲裁(impl 内层同任务登记幂等, 外层包裹保证rename层写意图显式) — 小欧 2026-09-20
    with claim_write(str(dst), _current_task_id.get()):
        result = await _move_file_impl(source_path=source, destination_path=str(dst), overwrite=overwrite)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

    if result.get("success"):
        try:
            _new_size = dst.stat().st_size if dst.is_file() else 0
        except OSError:
            _new_size = 0
        llm_data = _build_rename_file_llm_data("success", duration_ms, source, new_name=new_name, user_destination=destination, user_overwrite=overwrite, file_size=_new_size)
        with_artifact_file(llm_data, str(dst))   # 11.6.1 产出物声明 — 小欧 2026-08-21
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback (key:val)
        # trigger: 无上述20条分支匹配 — operation_id 不命中专用分支
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(
            data={},
            llm_data=llm_data,
        )
    else:
        error_detail = result.get("error_detail", "重命名失败")
        llm_data = _build_rename_file_llm_data("error", duration_ms, source, new_name=new_name, detail=error_detail, hint=result.get("hint", "请检查源路径和新名称是否有效"), user_destination=destination, user_overwrite=overwrite)  # 统一错误提示 - 小欧 2026-07-12  # 2026-10-14 小欧 - 修空话+复述: "重命名失败"message 已说,"文件状态"不知查什么 — 小欧-2026-10-14
        return build_error(data={}, llm_data=llm_data)