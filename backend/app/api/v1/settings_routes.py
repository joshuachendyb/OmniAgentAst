# -*- coding: utf-8 -*-
"""settings 路由薄壳。

编辑历史:
  2026-09-20 - 小沈 - 新建：GET/PUT /settings（5.2 参数配置接口）
  2026-09-21 - 小欧 - 修复: GET /settings 空串/纯空白 group 不再被 `if group` 误判走全量（拼写错误静默成功），
    改 is not None and strip() 判空；大小写不规范交 service get_group 归一（B-8）
  2026-10-06 - 小欧 - 新增: GET /settings/security-docs（安全 Tab 三段只读说明文案）
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
from app.services.settings import security_docs as docs_svc
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


# 2026-10-06 小欧 - 安全 Tab 说明文案: policy 策略说明 / flow 判定流程 / classification 分类表
#   刻意不并入 /settings: 那条返回"可配置项的值", 本条返回"只读说明", 混一起前端分不清哪个能改
@router.get("/settings/security-docs")
@handle_config_errors("获取安全说明文案")
async def get_security_docs():
    return docs_svc.load_security_docs()


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
