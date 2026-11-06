# 编辑历史:
# 2026-11-04 小欧 新建: 附件路由薄壳(8 端点, 业务全在 app/attachments/attachment_service.py) — 小欧-2026-11-04
# 2026-11-05 Agnes - 增 local-capability / import-local 两端点(同机本地导入通道,
#   与 upload 构成双通道); 薄壳仍不写业务, 判定与读盘全在 app/attachments/local_import.py — Agnes-2026-11-05
# 2026-11-06 小欧 方案B: CollectIn 加可选 task_id(产物来源任务溯源), 透传给 collect_artifact — 小欧-2026-11-06

"""attachments_routes — 附件 API 路由薄壳。

分层同 file_routes.py: 本层只做参数解包与错误转译, 不写业务, 不碰 DB。
挂载走 main.py 的 _mount()(唯一入口, 自动注入 token 鉴权)。
端点 8 个: upload / list / get / delete / text / collect / local-capability / import-local。
"""
import asyncio
from typing import Any

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from pydantic import BaseModel, Field

from app.attachments import attachment_service as attach
from app.attachments import collect as collector
from app.attachments import local_import as local
from app.file_browse.errors import NOT_FOUND, fail

router = APIRouter()


class CollectIn(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    source_path: str = Field(..., description="产物路径（引用同口径）")
    task_id: str | None = Field(default=None, description="产物来源任务 ID（溯源，可选）")


class ImportLocalPayload(BaseModel):
    """同机本地导入请求体（仅同机启用）。"""
    session_id: str
    path: str


@router.post("/attachments/upload")
async def upload_attachment(
    session_id: str = Form(..., description="会话 ID（用于定位默认工作区）"),
    file: UploadFile = File(..., description="上传文件"),
) -> dict[str, Any]:
    """上传落盘并登记, 返回附件记录(含项目根相对 path)。"""
    return await attach.save_upload(session_id, file)


@router.get("/attachments")
def list_attachments(
    session_id: str = Query(..., description="会话 ID"),
) -> list[dict[str, Any]]:
    """会话附件列表(按创建时间倒序)。"""
    return attach.list_attachments(session_id)


@router.get("/attachments/id/{attachment_id}")
def get_attachment(attachment_id: str) -> dict[str, Any]:
    """单条详情 —— 前端发送前存在性校验的唯一数据源(不走 /files/stat)。"""
    att = attach.get_attachment(attachment_id)
    if not att:
        fail(NOT_FOUND, "附件不存在")
    return att


@router.delete("/attachments/id/{attachment_id}")
def delete_attachment(
    attachment_id: str,
    purge: bool = Query(False, description="true=同时删除磁盘文件"),
) -> dict[str, Any]:
    """删记录; 默认不删磁盘文件(防误删)。"""
    attach.delete_attachment(attachment_id, purge=purge)
    return {"ok": True}


@router.get("/attachments/id/{attachment_id}/text")
async def get_attachment_text(attachment_id: str) -> dict[str, Any]:
    """按附件类型生成注入文本 —— 仅供预览/排查, **不是**前端入队来源。"""
    text = await asyncio.to_thread(attach.read_inject_text, attachment_id)
    return {"id": attachment_id, "text": text}


@router.post("/attachments/collect")
def collect_attachment(body: CollectIn) -> dict[str, Any]:
    """存为附件：工作区内 referenced(不复制) / 工作区外 copied。"""
    return collector.collect_artifact(body.session_id, body.source_path,
                                      task_id=body.task_id)


@router.get("/attachments/local-capability")
def local_capability(request: Request) -> dict[str, Any]:
    """同机能力探测：前端据此显示「从本机导入」入口（跨机隐藏）。"""
    return {"local_import": local.is_local_request(request)}


@router.post("/attachments/import-local")
def import_local(payload: ImportLocalPayload, request: Request) -> dict[str, Any]:
    """同机本地导入（仅同机，跨机 403）。"""
    return local.import_local(payload.session_id, payload.path, request=request)
