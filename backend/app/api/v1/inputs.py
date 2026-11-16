# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-15 小欧 新建([23] §9.2 阶段A): 输入预检路由薄壳(同 attachments.py 分层:
#   本层只做参数解包与转译, 判定全在 app/services/inputs/preflight.py)。
#   preflight 永不阻断(建议性预览, strict 拦截只在发送侧 409) — 小欧-2026-11-15
# 2026-11-16 小欧 [23]阶段D: 入参增 mode(suggest/auto/strict); 本层构建候选(capability_router
#   .build_candidates 唯一真源=模型库)下传, 路由建议由 preflight 经 capability_router 产出 — 小欧-2026-11-16
# 2026-11-16 小欧 [23]阶段D: routing_advice 增 provider(前端一键切换落 L2 需 provider+model) — 小欧-2026-11-16

# 2026-11-16 小欧 修正: 删除未使用的 session_id 预留字段(预检无状态, 避免死参); 候选构建失败
#   降级为空候选(预检永不阻断), 模型库/YAML 异常不再放大为 500 返回


"""inputs_routes — 输入预检 API 路由薄壳。挂载走 main.py 的 _mount()(唯一入口)。"""
from typing import Any, List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.inputs.preflight import preflight, result_to_dict
from app.services.model.capability_router import build_candidates

router = APIRouter()


class PreflightIn(BaseModel):
    model_id: str = Field(default="", description="目标模型 ID(provider/model 或 model)")
    text: str = Field(default="", description="消息正文(扫描其中 URL)")
    items: List[dict] = Field(default_factory=list, description="显式输入项(kind/url/path 等)")
    mode: str = Field(default="suggest", description="路由模式: suggest | auto | strict")


@router.post("/inputs/preflight")
def run_preflight(payload: PreflightIn) -> dict[str, Any]:
    """输入预检(建议性): 识别无条件执行, 能力判定读模型画像。
    永不阻断: 不含 limits/accepted; 不下载、不触发二次抽取。"""
    mode = payload.mode if payload.mode in ("suggest", "auto", "strict") else "suggest"
    # 未指定目标模型时不做路由: 画像无从判定, 避免对未知模型误报"推荐切换"; 且不触模型库 I/O。
    # 候选构建失败(如模型库/YAML 异常)降级为空: 预检永不阻断, 前端静默退化为无建议。
    candidates = None
    if payload.model_id:
        try:
            candidates = build_candidates()
        except Exception:
            candidates = None
    return result_to_dict(preflight(text=payload.text, items=payload.items,
                                    model_id=payload.model_id, mode=mode,
                                    candidates=candidates))
