# 编辑历史:
# 2026-11-07 小欧 - 新建: 同机文件系统路由(磁盘列表 / 授权目录 增删查), 供「我的电脑」自研浏览器;
#   薄壳同 file_routes/attachments_routes: 只做参数解包与错误转译, 判定全在 file_browse/local_fs.py
#   — 小欧-2026-11-07
#   2026-11-07 小欧 - /fs/drives 增 quick 常用位置(桌面/下载/文档), 数据源 local_fs.quick_paths — 小欧-2026-11-07
"""fs_routes — 同机文件系统 API 路由薄壳。

分层同 file_routes.py：本层只做参数解包与错误转译，不写业务、不碰 DB。
挂载走 main.py 的 _mount()（唯一入口，自动注入 token 鉴权）。

端点 4 个：
- GET    /fs/drives      磁盘列表（盘符 + 卷标 + 总/剩余空间）+ 常用位置
- GET    /fs/authorize   已授权目录台账
- POST   /fs/authorize   授权一个目录（幂等）
- DELETE /fs/authorize   撤销授权（不影响已导入的附件）

全部**仅同机可用**：跨机访问返回 403 LOCAL_IMPORT_DISABLED（与 import-local 同一口径）。
"""
from typing import Any, Dict

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app.attachments import local_import as local
from app.file_browse import local_fs
from app.file_browse.errors import LOCAL_IMPORT_DISABLED, fail

router = APIRouter()


class AuthorizeIn(BaseModel):
    """授权目录请求体（仅同机）。"""

    path: str = Field(..., description="盘符绝对路径，如 D:\\资料")


def _require_local(request: Request) -> None:
    """同机闸门：磁盘与授权只对真实本机请求开放。"""
    if not local.is_local_request(request):
        fail(LOCAL_IMPORT_DISABLED, "该功能仅同机可用")


@router.get("/fs/drives")
def get_drives(request: Request) -> Dict[str, Any]:
    """磁盘列表：盘符 + 卷标 + 总/剩余空间（不可读的盘照列，ready=false）+ 常用位置。"""
    _require_local(request)
    return {
        "host_label": local_fs.host_label(),
        "drives": local_fs.list_drives(),
        "quick": local_fs.quick_paths(),
    }


@router.get("/fs/authorize")
def get_authorized(request: Request) -> Dict[str, Any]:
    """已授权目录台账（撤销不影响已导入的附件）。"""
    _require_local(request)
    return {"dirs": local_fs.list_authorized()}


@router.post("/fs/authorize")
def post_authorize(payload: AuthorizeIn, request: Request) -> Dict[str, Any]:
    """授权一个目录（幂等）；受保护目录（凭据/系统配置/浏览器配置）一律拒绝。"""
    _require_local(request)
    return {"dirs": local_fs.authorize(payload.path)}


@router.delete("/fs/authorize")
def delete_authorize(
    request: Request,
    path: str = Query(..., description="要撤销授权的目录（盘符绝对路径）"),
) -> Dict[str, Any]:
    """撤销授权；已导入的附件不受影响（附件已复制进工作区）。"""
    _require_local(request)
    return {"dirs": local_fs.revoke(path)}
