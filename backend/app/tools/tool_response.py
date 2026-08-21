# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-18 - 小健 - 三堂会审 Bug#7(同源): is_success/is_warning/is_error 的 llm_data.status 可能为 str, 防御 AttributeError; 抽 _exec_code 统一取值, 保留 is_error 畸形结果(无llm_data)视为错误语义不退化
# 2026-08-21 - 小欧 - 11.6.1: 新增 extract_ext/with_artifacts/with_artifact_file 三个公共helper（DRY+KISS，产出型工具声明artifacts统一入口）
"""
统一工具返回结构定义 — 小健 2026-05-21

【Phase 1 v6.0 重构 — 小欧 2026-06-21】
result 统一为 3 字段: data + llm_data + other_data
build_success/error/warning 签名重写，函数名即语义，无需 exec_code 参数
删除旧格式代码: _REQUIRED_FIELDS/_OPTIONAL_FIELDS/_add_optionals/register_builder/_default_builder/_BUILDERS/build_result

两层职责边界:
  tool_response.py (构建层) ← 本文件
    → 提供 build_success / build_error / build_warning（纯组装 result）
    → 提供 is_success / is_error（从 llm_data.status.exec_code 判断）
    → 工具函数、helper函数、Agent编排层 统一使用这些函数

  observation_formatter.py (格式化层)
    → LLM observation / 前端SSE / extract_status 格式化
    → 禁止构建结果,只消费和格式化
"""
import os
from typing import Any, Dict, List, Optional

_RESERVED_TOP_KEYS: set = {"data", "llm_data", "other_data"}


def build_success(data: Any = None, llm_data: Optional[Dict] = None,
                  other_data: Optional[Dict] = None, **extra) -> Dict[str, Any]:
    """构建成功响应 — 小欧 2026-06-21，小欧 2026-06-27 修复默认llm_data一致性"""
    if llm_data is None:
        llm_data = {"status": {"exec_code": "success"}}
    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    for k, v in extra.items():
        if k not in _RESERVED_TOP_KEYS:
            result[k] = v
    return result


def build_error(data: Any = None, llm_data: Optional[Dict] = None,
                other_data: Optional[Dict] = None, **extra) -> Dict[str, Any]:
    """构建错误响应 — 小欧 2026-06-21，小欧 2026-06-27 修复默认llm_data一致性"""
    if llm_data is None:
        llm_data = {"status": {"exec_code": "error"}}
    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    for k, v in extra.items():
        if k not in _RESERVED_TOP_KEYS:
            result[k] = v
    return result


def build_warning(data: Any = None, llm_data: Optional[Dict] = None,
                  other_data: Optional[Dict] = None, **extra) -> Dict[str, Any]:
    """构建警告响应 — 小欧 2026-06-21，小欧 2026-06-27 修复默认llm_data一致性"""
    if llm_data is None:
        llm_data = {"status": {"exec_code": "warning"}}
    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    for k, v in extra.items():
        if k not in _RESERVED_TOP_KEYS:
            result[k] = v
    return result


def _exec_code(result: Dict[str, Any]) -> str:
    """2026-08-18 小健 三堂会审 Bug#7(同源): llm_data.status 可能为 str, 防御 .get AttributeError"""
    llm_data = result.get("llm_data")
    if not isinstance(llm_data, dict):
        return ""
    _st = llm_data.get("status")
    return _st.get("exec_code", "") if isinstance(_st, dict) else ""


def is_success(result: Dict[str, Any]) -> bool:
    """判断返回是否成功 — 从llm_data.status.exec_code判断 — 小欧 2026-06-21"""
    return _exec_code(result) in ("success", "warning")


def is_warning(result: Dict[str, Any]) -> bool:
    """判断返回是否为warning — 小健 2026-06-25"""
    return _exec_code(result) == "warning"


def is_error(result: Dict[str, Any]) -> bool:
    """判断返回是否失败 — 从llm_data.status.exec_code判断 — 小欧 2026-06-21 — 小欧 2026-06-24 畸形结果视为错误"""
    llm_data = result.get("llm_data") if isinstance(result, dict) else None
    if not isinstance(llm_data, dict):
        return True  # 畸形结果(无llm_data)视为错误
    return _exec_code(result) == "error"


def extract_ext(file_path: str) -> str:
    """提取文件扩展名（小写无点），无扩展名返回 'file' — 小欧 2026-08-21 DRY"""
    _base = os.path.basename(file_path)
    return _base.rsplit(".", 1)[-1].lower() if "." in _base else "file"


def with_artifacts(llm_data: Optional[Dict], items: List[Dict[str, str]]) -> Dict:
    """产出型工具成功时声明产出物 [{name, path, type}]，挂 llm_data.action.artifacts（无白名单、OCP）— 小欧 2026-08-20"""
    if not isinstance(llm_data, dict):
        llm_data = {}
    _act = llm_data.setdefault("action", {})
    if not isinstance(_act, dict):
        _act = {}
        llm_data["action"] = _act
    _act["artifacts"] = list(items or [])
    return llm_data


def with_artifact_file(llm_data: Optional[Dict], file_path: str) -> Dict:
    """便捷声明：从文件路径自动提取 name/path/type，挂 llm_data.action.artifacts — 小欧 2026-08-21 KISS"""
    return with_artifacts(llm_data, [{
        "name": os.path.basename(file_path),
        "path": file_path,
        "type": extract_ext(file_path),
    }])
