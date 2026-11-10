# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-04 小欧 新建: 素材包路由薄壳(4 端点, 业务全在 service) — 小欧-2026-11-04
# 2026-11-07 小欧 - 条目保留引用身份(kind/attachment_id,
#   附件条目投喂时按 id 恢复附件语义) — 小欧-2026-11-07
# 2026-11-10 小欧 新增 GET /material-packs/limits: 限额单一出口供前端预校验(消前端硬编码) — 小欧-2026-11-10
# 2026-11-10 小欧 注释清理: 去除修复序号等过期标识, 注释语义不变 — 小欧-2026-11-10

"""material_packs 路由薄壳 —— 参数解包 + 转 service, 不写业务、不碰 DB。

挂载走 main.py 的 _mount()(唯一入口, 自动注入 token 鉴权)。
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.material_packs import material_pack_service as packs

router = APIRouter()


class PackItemIn(BaseModel):
    path: str = Field(..., description="与引用同口径：项目根内相对 / 盘符绝对")
    label: str = Field(default="", description="展示名")
    kind: Optional[str] = Field(default=None, description="引用身份(attachment 时按 id 恢复附件语义)")
    attachment_id: Optional[str] = Field(default=None, description="附件记录 ID(kind=attachment 时必填)")


class PackCreateIn(BaseModel):
    name: str
    note: str = ""
    group_name: str = ""
    items: List[PackItemIn] = Field(default_factory=list)


class PackUpdateIn(BaseModel):
    name: Optional[str] = None
    note: Optional[str] = None
    group_name: Optional[str] = None
    items: Optional[List[PackItemIn]] = None


@router.get("/material-packs")
def list_packs() -> List[Dict[str, Any]]:
    """全部素材包(含 items); 分组/搜索在前端本地过滤。"""
    return packs.list_packs()


@router.get("/material-packs/limits")
def pack_limits() -> Dict[str, int]:
    """合集限额(包总数/单包条目): 前端预校验与文案, 与 service 常量同源。"""
    return packs.get_limits()


@router.post("/material-packs")
def create_pack(body: PackCreateIn) -> Dict[str, Any]:
    return packs.create_pack(body.name, body.note, body.group_name,
                             [i.model_dump() for i in body.items])


@router.patch("/material-packs/{pack_id}")
def update_pack(pack_id: str, body: PackUpdateIn) -> Dict[str, Any]:
    return packs.update_pack(
        pack_id, name=body.name, note=body.note,
        group_name=body.group_name,
        items=None if body.items is None else [i.model_dump() for i in body.items],
    )


@router.delete("/material-packs/{pack_id}")
def delete_pack(pack_id: str) -> Dict[str, Any]:
    packs.delete_pack(pack_id)
    return {"ok": True}
