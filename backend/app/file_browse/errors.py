# -*- coding: utf-8 -*-
# 编辑历史: 2026-10-13 小欧 - 文档[28] v3.7: 文件浏览模块错误契约(K1: 统一 {code,message}，仅本模块不改全局) — 小欧-2026-10-13
# 2026-10-21 小杨 - UNSUPPORTED_TYPE 文案与实际判定口径对齐：类型闸已由后缀白名单改为
#   "可解码文本或图片"，原文案仍写"仅支持查看 .txt / .md 与图片文件"会误导用户以为
#   .py/.json/无后缀文件不可读 — 小杨-2026-10-21
"""文件浏览模块的错误契约。

K1：错误响应固定 `{"code": <机器可读>, "message": <中文说明>}，
前端按 code 分支而非匹配中文文案（文案会变、也会被翻译）。

范围纪律：**仅本模块统一**，不改全局 HTTPException 行为 —— 既有接口
（如 sessions 的 dict 型 detail）形态不一，全局改造属独立议题。
本模块内所有异常一律经 `fail()` 抛出，不手写 HTTPException。
"""

# ── 错误码常量（供 service 引用的字面量） ──────────────────────────────
INVALID_PATH = "INVALID_PATH"                    # 400 路径非法（绝对路径 / 是目录却调单文件接口）
PATH_OUTSIDE_ROOT = "PATH_OUTSIDE_ROOT"          # 403 越出项目根目录
PATH_FORBIDDEN = "PATH_FORBIDDEN"                # 403 触达代码库根禁区
NOT_FOUND = "NOT_FOUND"                          # 404 路径不存在
SESSION_NOT_FOUND = "SESSION_NOT_FOUND"          # 404 会话不存在
IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"              # 413 图片超 10MB
UNSUPPORTED_TYPE = "UNSUPPORTED_TYPE"            # 415 类型不在白名单
UNDECODABLE = "UNDECODABLE_ENCODING"             # 415 文本编码无法识别

from typing import Dict, NamedTuple, NoReturn, Optional, Tuple

from fastapi import HTTPException


class _Err(NamedTuple):
    """一个错误码的全部对外信息 —— **单一真源**。

    2026-10-13 小欧 - DRY 修复：原为 _STATUS / _MESSAGES 两个平行字典，
    增删改错误码必须同步两处，迟早漂移；合并为单表，结构上不可能对不上。
    """
    status: int
    message: str


# code → (HTTP 状态码, 中文说明)。前端按 code 分支，不匹配中文文案（文案会变、也会被翻译）。
_CATALOG: Dict[str, _Err] = {
    INVALID_PATH: _Err(400, "路径非法：只接受相对项目根的相对路径"),
    PATH_OUTSIDE_ROOT: _Err(403, "路径超出项目根目录范围"),
    PATH_FORBIDDEN: _Err(403, "路径位于受保护区域"),
    NOT_FOUND: _Err(404, "路径不存在"),
    SESSION_NOT_FOUND: _Err(404, "会话不存在"),
    IMAGE_TOO_LARGE: _Err(413, "图片超过 10MB，本期不支持预览"),
    # 2026-10-21 小杨 - 修复：文案还停留在"后缀白名单"时代（实际已放开为
    #   "可解码文本 + 图片"），会误导用户以为 .py/.json/无后缀文件不可读。
    UNSUPPORTED_TYPE: _Err(415, "该文件不是可预览的文本或图片"),
    UNDECODABLE: _Err(415, "文件编码无法识别"),
}


def fail(code: str, message: Optional[str] = None) -> NoReturn:
    """抛出统一格式的 HTTPException —— **本模块唯一抛错出口**。

    2026-10-13 小欧 - detail 固定两键 {code, message}，前端按 code 分支（文档[28] 2.6/4.2.4）。
    """
    spec = _CATALOG[code]
    raise HTTPException(
        status_code=spec.status,
        detail={"code": code, "message": message or spec.message},
    )