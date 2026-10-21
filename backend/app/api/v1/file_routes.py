# -*- coding: utf-8 -*-
# 编辑历史: 2026-10-13 小欧 - 文档[28] v3.7: 文件浏览路由薄壳(6 个 GET，逻辑全在 app/file_browse/browse_service.py) — 小欧-2026-10-13
#   同批新增 /files/root(项目根信息，前端做路径归一)与 /files/recent-files(T3 的 ● 标记数据源)。
#   v3.8 修正: ① service 改文件顶部一次性 import（原先 6 处函数内 import 是照搬 sessions.py 风格，
#     但本模块与 api/v1 无依赖关系，不存在循环，重复 import 违反 DRY）；
#     ② 补全返回类型注解；③ 模块名 service.py → browse_service.py（与 lifecycle/service.py 撞名）。
#   2026-10-21 小杨 - 对账修正: ① 文件头"5 个 GET"→ 6 个（v3.8 追加了 /files/search，漏改）；
#     ② get_file_content docstring"四道闸门"→ 五道闸门（实码顺序: 存在性→目录→类型→大小→编码）；
"""file_routes — 文件浏览 API 路由薄壳。

按项目分层约定（tool_routes.py:9-10）：API 层只做参数解包与错误转译，
业务逻辑一律在 app.file_browse.browse_service，不在本层 import app.tools / app.safety。

挂载走 main.py 的 _mount()（唯一入口，自动注入 token 鉴权）。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from app.file_browse import browse_service as browse

router = APIRouter()


@router.get("/files/root")
def get_files_root() -> Dict[str, Any]:
    """项目根 / 授权目录 / 禁区是否降级 —— 供前端做路径归一与 J1 校验。"""
    return browse.get_workspace_info()


@router.get("/files/tree")
def get_files_tree(
    path: str = Query("", description="子树起点（相对项目根，空=根目录）"),
    max_depth: int = Query(browse.MAX_TREE_DEPTH, ge=1, le=20, description="递归深度上限"),
    # 2026-10-21 小杨 - **取消节点数上限**（50000/5000 的 cap 全部移除；慢的根因是 browse_service 老实现，另单另行根治）
    max_nodes: int = Query(browse.MAX_TREE_NODES, ge=1, description="节点总数上限"),
) -> Dict[str, Any]:
    """目录树：全量优先 + 自动降级。取任意子树由 path 承担，无独立 list 端点。"""
    return browse.build_tree(path, max_depth=max_depth, max_nodes=max_nodes)


@router.get("/files/search")
def search_files(
    q: str = Query(..., min_length=1, max_length=200, description="文件名关键词（不区分大小写）"),
    limit: int = Query(20, ge=1, le=100, description="最多返回条数"),
) -> Dict[str, Any]:
    """按文件名模糊搜索 —— 输入框 @ 补全的数据源。

    2026-10-13 小欧 - 北京老陈裁定：输入框里手打 @文件名 也应能带内容；
    纯前端过滤不可行（树只在打开文件页时进内存），故后端提供全域搜索。
    """
    return browse.search_files(q, limit=limit)


@router.get("/files/read")
def get_file_content(
    path: str = Query(..., description="相对项目根的文件路径（.txt / .md）"),
    offset: Optional[int] = Query(
        None, ge=1, description="起始行号（1-based）；给了就按行区间读（可翻页到大文件后段）"
    ),
    limit: Optional[int] = Query(
        None, ge=1, le=5000, description="读取行数（配合 offset；默认 2000，上限 5000）"
    ),
) -> Dict[str, Any]:
    """读文本文件正文（存在性/是目录/类型/大小/编码 五道闸门）。

    2026-10-21 小欧 - 加 offset/limit 行号区间：大文件默认只读前 2MB（截断），
      2MB 之后拿不到；带区间时后端**流式**按行读（内存恒定），可翻页到文件末尾。
    """
    return browse.read_text_file(path, offset=offset, limit=limit)


@router.get("/files/raw")
def get_file_raw(
    request: Request,
    path: str = Query(..., description="相对项目根的图片路径"),
) -> Response:
    """图片二进制流。

    ⚠️ 绝不能声明 response_model —— 声明后 FastAPI 会按模型序列化响应体，
    直接破坏二进制流（文档[28] 4.1.3）。
    304 / Range(206) 由 service + Starlette FileResponse 处理。
    """
    return browse.read_image_file(path, request)


@router.get("/files/recent-files")
def get_recent_files(
    session_id: str = Query(..., description="会话ID"),
) -> Dict[str, Any]:
    """本会话 Agent 最近读过的文件（树上的 ● 标记）。"""
    files: List[Dict[str, Any]] = browse.recent_files(session_id)
    return {"session_id": session_id, "files": files}