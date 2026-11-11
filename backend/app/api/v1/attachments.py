# 编辑历史:
# 2026-11-04 小欧 新建: 附件路由薄壳(8 端点, 业务全在 app/attachments/attachment_service.py) — 小欧-2026-11-04
# 2026-11-05 Agnes - 增 local-capability / import-local 两端点(同机本地导入通道,
#   与 upload 构成双通道); 薄壳仍不写业务, 判定与读盘全在 app/attachments/local_import.py — Agnes-2026-11-05
# 2026-11-06 小欧 溯源改造: CollectIn 加可选 task_id(产物来源任务溯源), 透传给 collect_artifact — 小欧-2026-11-06
# 2026-11-07 小欧 越权收紧: get/delete/text 三端点加 session_id 必填参数并校验会话归属
#   (service.get_attachment_scoped 单一口径) —— 附件是会话级资产, 跨会话按 id 直取属越权
# 2026-11-07 小欧 加固: CollectIn.source_path 补 API 层基础校验(拒绝 .. 穿越/空字节),
#   防内部 collect._resolve_source 变更后 API 层无第二道防线
# 2026-11-07 小欧 资产台账端点: 列表加 scope/q/limit/offset、get 跨会话自动 promote、
#   POST promote(收藏)、PATCH 重命名、POST clear-recent、DELETE 加 force(合集引用确认)、
#   GET raw(预览图片/PDF 二进制) — 小欧-2026-11-07
# 2026-11-07 小欧 预览严格读: 预览读(raw)改严格校验, 自动升级只属发送注入/手动收藏, 读不产生写副作用;
#   promote 端点改直线分派(已是 global 直接返回, 去掉 auto_promote 后的重复一趟 promote) — 小欧-2026-11-07
# 2026-11-07 小欧 注释清理: 去除文档号/修复序号/评审引用等过期标识, 注释语义不变 — 小欧-2026-11-07
# 2026-11-11 小欧 新增 GET /attachments/capabilities 唯一出口(accept/limits/kind_options) — 小欧-2026-11-11
# 2026-11-11 小欧 新增 POST /attachments/id/{id}/reextract 真抽取手动重跑(文件页重试入口) — 小欧-2026-11-11

"""attachments_routes — 附件 API 路由薄壳。

分层同 file_routes.py: 本层只做参数解包与错误转译, 不写业务, 不碰 DB。
挂载走 main.py 的 _mount()(唯一入口, 自动注入 token 鉴权)。
端点: upload / list / get / raw / delete / text / promote / rename / clear-recent
      / collect / local-capability / import-local。
"""
import asyncio
import mimetypes
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from app.attachments import attachment_service as attach
from app.attachments import collect as collector
from app.attachments import local_import as local
from app.file_browse.errors import (
    ATTACHMENT_NOT_AVAILABLE,
    INVALID_PARAM,
    NOT_FOUND,
    fail,
)

router = APIRouter()


class CollectIn(BaseModel):
    session_id: str = Field(..., description="会话 ID")
    source_path: str = Field(..., description="产物路径（引用同口径）")
    task_id: str | None = Field(default=None, description="产物来源任务 ID（溯源，可选）")

    @field_validator("source_path")
    @classmethod
    def _validate_source_path(cls, v: str) -> str:
        """API 层基础校验(第二道防线) —— 拒绝路径穿越与空字节。"""
        text = (v or "").strip()
        if not text:
            fail(INVALID_PARAM, "缺少文件路径")
        if "\x00" in text:
            fail(INVALID_PARAM, "路径含非法字符")
        if ".." in text.replace("\\", "/").split("/"):
            fail(INVALID_PARAM, "路径不允许包含 .. 穿越")
        return text


class ImportLocalPayload(BaseModel):
    """同机本地导入请求体（仅同机启用）。"""
    session_id: str
    path: str


class RenamePayload(BaseModel):
    """重命名附件展示名（不动磁盘文件名）。"""
    session_id: str | None = None
    name: str = Field(..., description="新文件名（仅展示）")


@router.post("/attachments/upload")
async def upload_attachment(
    session_id: str = Form(..., description="会话 ID（用于定位默认工作区）"),
    file: UploadFile = File(..., description="上传文件"),
) -> dict[str, Any]:
    """上传落盘并登记, 返回附件记录(含项目根相对 path)。"""
    return await attach.save_upload(session_id, file)


@router.get("/attachments")
def list_attachments(
    session_id: str | None = Query(None, description="会话 ID（scope=session 时必填）"),
    scope: str = Query("session", description="session | recent | global | ai"),
    q: str | None = Query(None, description="按文件名过滤"),
    limit: int = Query(attach.MAX_LIST_ITEMS, ge=1, le=attach.MAX_LIST_ITEMS),
    offset: int = Query(0, ge=0),
) -> list[dict[str, Any]]:
    """附件列表（作用域: 本会话 / 最近用过 / 已收藏 / AI 生成）。"""
    if scope not in ("session", "recent", "global", "ai"):
        fail(INVALID_PARAM, "scope 只支持 session / recent / global / ai")
    return attach.list_attachments(session_id, scope=scope, q=q, limit=limit, offset=offset)


@router.get("/attachments/id/{attachment_id}")
def get_attachment(
    attachment_id: str,
    session_id: str = Query(..., description="会话 ID（会话归属校验）"),
) -> dict[str, Any]:
    """单条详情 —— 前端发送前存在性预检的唯一数据源(不走 /files/stat)。

    调用方仅两类(发送预链/合集引用), 跨会话 session 级附件自动 promote,
    用户不感知 404; 纯预览端点(raw/text)一律严格校验, 读不产生写副作用。
    """
    att = attach.get_attachment_scoped(attachment_id, session_id, auto_promote=True)
    if not att:
        fail(NOT_FOUND, "附件不存在")
    return att


@router.get("/attachments/id/{attachment_id}/raw")
def get_attachment_raw(
    attachment_id: str,
    session_id: str = Query(..., description="会话 ID（会话归属校验）"),
) -> FileResponse:
    """预览二进制（图片 / PDF）：直接流式返回磁盘文件，不做 base64。

    预览是纯读：严格会话校验不自动收藏(auto_promote=False)，跨会话 session 级附件如实 404；
    预览内容请先收藏(☆)使其成为全局资产。⚠️ 不声明 response_model —— 声明后 FastAPI 会按模型序列化，破坏二进制流。
    """
    att = attach.get_attachment_scoped(attachment_id, session_id, auto_promote=False)
    if not att:
        fail(NOT_FOUND, "附件不存在")
    path = Path(att["stored_path"])
    if not path.is_file():
        fail(ATTACHMENT_NOT_AVAILABLE)
    media = att.get("mime") or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        path, media_type=media,
        headers={"Cache-Control": "no-cache",
                 "Content-Disposition": f"inline; filename*=UTF-8''{attachment_id}"},
    )


@router.delete("/attachments/id/{attachment_id}")
def delete_attachment(
    attachment_id: str,
    session_id: str | None = Query(None, description="会话 ID（session 行必填；global 行可省）"),
    purge: bool = Query(True, description="true=同时删除磁盘文件（无其他行共享该路径时）"),
    force: bool = Query(False, description="true=确认删除被合集引用的文件"),
) -> dict[str, Any]:
    """删记录；默认按路径引用计数删磁盘文件，被合集引用时 409 需 force。"""
    attach.delete_attachment(attachment_id, session_id, purge=purge, force=force)
    return {"ok": True}


@router.get("/attachments/id/{attachment_id}/text")
async def get_attachment_text(
    attachment_id: str,
    session_id: str = Query(..., description="会话 ID（会话归属校验）"),
) -> dict[str, Any]:
    """按附件类型生成注入文本 —— 仅供预览/排查, **不是**前端入队来源。"""
    text = await asyncio.to_thread(attach.read_inject_text, attachment_id, session_id)
    return {"id": attachment_id, "text": text}


@router.post("/attachments/id/{attachment_id}/reextract")
def reextract_attachment(
    attachment_id: str,
    session_id: str = Query(..., description="会话 ID（会话归属校验）"),
) -> dict[str, Any]:
    """手动重跑真抽取并回填 extract_status/extract_chars（失败折算 failed）。"""
    if not attach.get_attachment_scoped(attachment_id, session_id):
        fail(NOT_FOUND, "附件不存在")
    rec = attach.reextract(attachment_id)
    if not rec:
        fail(NOT_FOUND, "附件不存在")
    return rec


@router.post("/attachments/id/{attachment_id}/promote")
def promote_attachment(
    attachment_id: str,
    session_id: str = Query(..., description="会话 ID（会话归属校验）"),
) -> dict[str, Any]:
    """收藏 / 跨会话复用：升级为全局资产（幂等 + sha 去重）。

    直线分派：跨会话由 get_attachment_scoped(auto_promote) 一趟完成升级, 已是 global 直接返回;
    本会话 session 行才走 promote_attachment —— 不再先 auto 后 promote 两趟重复。
    """
    att = attach.get_attachment_scoped(attachment_id, session_id, auto_promote=True)
    if not att:
        fail(NOT_FOUND, "附件不存在")
    if att["scope"] == "global":
        return att
    rec = attach.promote_attachment(att["id"])
    if not rec:
        fail(NOT_FOUND, "附件不存在")
    return rec


@router.patch("/attachments/id/{attachment_id}")
def rename_attachment(attachment_id: str, body: RenamePayload) -> dict[str, Any]:
    """重命名展示名（磁盘文件名不变）。"""
    return attach.rename_attachment(attachment_id, body.name, body.session_id)


@router.post("/attachments/clear-recent")
def clear_recent() -> dict[str, Any]:
    """清空最近使用记录（不删除任何文件）。"""
    return {"cleared": attach.clear_recent()}


@router.post("/attachments/collect")
def collect_attachment(body: CollectIn) -> dict[str, Any]:
    """存为附件：工作区内 referenced(不复制) / 工作区外 copied。"""
    return collector.collect_artifact(body.session_id, body.source_path,
                                      task_id=body.task_id)


@router.get("/attachments/capabilities")
def get_capabilities() -> dict[str, Any]:
    """上传白名单/上限/类型选项唯一出口(C8): 不设 /limits 别名。
    accept 由后缀词典组合(单一真源 contract/extract), 前端禁止再写死后缀/大小/上限。"""
    from app.attachments import contract
    from app.attachments.extract import (
        AUDIO_SUFFIXES,
        IMAGE_SUFFIXES,
        RICH_SUFFIXES,
        TEXT_SUFFIXES,
        VIDEO_SUFFIXES,
    )
    accept = ",".join(sorted(IMAGE_SUFFIXES | VIDEO_SUFFIXES | AUDIO_SUFFIXES
                            | RICH_SUFFIXES | TEXT_SUFFIXES))
    return {"accept": accept,
            "limits": contract.limits(),
            "kind_options": contract.kind_options()}


@router.get("/attachments/local-capability")
def local_capability(request: Request) -> dict[str, Any]:
    """同机能力探测：前端据此显示「从本机导入」入口（跨机隐藏）。"""
    return {"local_import": local.is_local_request(request)}


@router.post("/attachments/import-local")
def import_local(payload: ImportLocalPayload, request: Request) -> dict[str, Any]:
    """同机本地导入（仅同机，跨机 403）。"""
    return local.import_local(payload.session_id, payload.path, request=request)
