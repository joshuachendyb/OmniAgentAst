# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-15 小欧 新建([23] §9.2 阶段A): 输入预检路由薄壳(同 attachments.py 分层:
#   本层只做参数解包与转译, 判定全在 app/services/inputs/preflight.py)。
#   preflight 永不阻断(建议性预览, strict 拦截只在发送侧 409) — 小欧-2026-11-15

"""inputs_routes — 输入预检 API 路由薄壳。挂载走 main.py 的 _mount()(唯一入口)。"""
from typing import Any, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.inputs.preflight import preflight, result_to_dict

router = APIRouter()


class PreflightIn(BaseModel):
    session_id: Optional[str] = Field(default=None, description="会话 ID(预留溯源, 预检无状态)")
    model_id: str = Field(default="", description="目标模型 ID(provider/model 或 model)")
    text: str = Field(default="", description="消息正文(扫描其中 URL)")
    items: List[dict] = Field(default_factory=list, description="显式输入项(kind/url/path 等)")


@router.post("/inputs/preflight")
def run_preflight(payload: PreflightIn) -> dict[str, Any]:
    """输入预检(建议性): 识别无条件执行, 能力判定读模型画像。
    永不阻断: 不含 limits/accepted; 不下载、不触发二次抽取。"""
    return result_to_dict(preflight(text=payload.text, items=payload.items,
                                    model_id=payload.model_id))
