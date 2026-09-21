# -*- coding: utf-8 -*-
"""settings 路由薄壳。

编辑历史:
  2026-09-20 - 小沈 - 新建：GET/PUT /settings（5.2 参数配置接口）
  2026-09-21 - 小欧 - [59]B-9 修复: GET /settings 空串/纯空白 group 不再被 `if group` 误判走全量（拼写错误静默成功），
    改 is not None and strip() 判空；大小写不规范交 service get_group 归一（B-8）
"""
from typing import Optional
from fastapi import APIRouter, Query

from app.api.v1.settings_schemas import (
    SchemaResponse,
    SettingsGetResponse,
    SettingsGroupResponse,
    SettingsUpdateRequest,
    SettingsUpdateResponse,
    UpdatedItem,
)
from app.services.model.config_helpers import handle_config_errors
from app.services.settings import settings_service as svc


router = APIRouter()


@router.get("/settings/schema", response_model=SchemaResponse)
@handle_config_errors("获取设置 Schema")
async def get_settings_schema():
    return svc.get_schema()


@router.get("/settings/mtime")
@handle_config_errors("获取设置 mtime")
async def get_settings_mtime():
    return svc.get_mtime()


@router.get("/settings")
@handle_config_errors("获取设置")
async def get_settings(group: Optional[str] = Query(default=None)):
    if group is not None and group.strip():
        one = svc.get_group(group)
        return SettingsGroupResponse(data=one["data"], sources=one["sources"],
                                     mtime=one["mtime"])
    all_ = svc.get_all_groups()
    return SettingsGetResponse(groups=all_["groups"], version=all_["version"],
                               mtime=all_["mtime"])


@router.put("/settings", response_model=SettingsUpdateResponse)
@handle_config_errors("保存设置")
async def update_settings(req: SettingsUpdateRequest):
    result = svc.update_settings(req.patch or {})
    return SettingsUpdateResponse(
        ok=result["ok"],
        updated=[UpdatedItem(**u) for u in result.get("updated", [])],
        need_restart=result.get("need_restart", []),
        warnings=result.get("warnings", []),
        errors=result.get("errors", []),
        mtime=result.get("mtime", 0.0),
    )
