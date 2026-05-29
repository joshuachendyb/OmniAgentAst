# -*- coding: utf-8 -*-
"""
工具返回结构查询函数 — 小健 2026-05-29

【SRP拆分】从_response.py拆出，职责：查询/判断返回状态
_response.py负责构建，本文件负责查询

使用场景:
  from app.services.tools.response_utils import is_success, is_error
  if is_success(result):
      ...

返回数据说明:
  is_success: code为SUCCESS_CODE或WARNING_开头返回True
  is_error: code为ERR_开头返回True
"""
from typing import Dict, Any

from app.constants import SUCCESS_CODE


def is_success(result: Dict[str, Any]) -> bool:
    """判断返回是否成功"""
    code = result.get("code", "")
    return code == SUCCESS_CODE or code.startswith("WARNING_")


def is_error(result: Dict[str, Any]) -> bool:
    """判断返回是否失败"""
    code = result.get("code", "")
    return code.startswith("ERR_")
