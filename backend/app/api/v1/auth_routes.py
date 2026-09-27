# -*- coding: utf-8 -*-
"""
auth_routes — 访问口令（token）设置接口

编辑历史:
  2026-09-26 小欧 - [72]第九章 新建：补齐口令"设置侧"（此前只有校验侧与登录页，无处可设 → 死锁）。
  2026-09-26 小欧 - 修 3 处注释与实现不符（留空实为 400 / 无 main.py 特殊挂载 / 删死代码）。
  2026-09-27 小欧 - token 加 max_length=200000；本机准入改用 _is_trusted_localhost（与 deps 同判据）。
  2026-09-27 小欧 - [75]5.2：status 删 masked/config_key/env_name（YAGNI）、补两个按来源的结论；
    set_api_token 本机准入改调 deps 单一判据（DRY）。
  2026-09-27 小欧 - [75]缺陷修复：403 文案引用 deps.SET_TOKEN_LOCAL_ONLY_MESSAGE；
    get_token_status 只读一次配置并同源下传。
  2026-09-27 小欧 - [75]会审 BUG-B：status 增 set_token_blocked_reason（前端分叉指引，
    * 部署不再死路）；两处 403 改按原因取文案（deps.SET_TOKEN_BLOCKED_MESSAGES）。

设计（[72]第六章方案 B）：
  - `security.access_token` 是 registry 的 secret 项：读路径掩码永不回明文，settings 通用通道
    显式拒绝写 secret。
  - 改口令只走本模块端点，与 provider 通道同构（单一权威写入口，避免同 key 两个写入口分叉）。
  - 豁免判定全在 deps.verify_token，本文件不重复判断。
    POST /auth/token  设/改口令，仅限本机（deps + 函数体双重把关）。
    GET  /auth/status 查状态，回三个布尔结论；不带口令放行、带口令验真（引导查询与探针两用）。
"""
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.v1.deps import (
    ACCESS_TOKEN_CONFIG_KEY,
    ACCESS_TOKEN_ENV,
    SET_TOKEN_BLOCKED_MESSAGES,
    _resolve_configured_token,
    current_client_requires_auth,
    set_token_blocked_reason,
)
from app.services.model.config_helpers import handle_config_errors, merge_region_patch

router = APIRouter()


class SetTokenRequest(BaseModel):
    """设置访问口令请求体。"""

    model_config = {"extra": "forbid"}
    token: str = Field(
        ...,
        max_length=200000,
        description=(
            "新的访问口令。**不可留空**（留空一律 400，见 set_api_token）；"
            "至少 8 位，建议 16 位以上随机串。关闭鉴权请改用环境变量 "
            "OMNIAGENT_REQUIRE_AUTH=0（显式声明，可追溯），而非把口令置空"
        ),
    )


@router.get("/auth/status")
@handle_config_errors("查询访问口令状态")
async def get_token_status(request: Request) -> Dict[str, Any]:
    """查访问口令状态。永不回明文（[75]5.2）。

    can_set_access_token 为刚需：缺此字段前端只能显示"填入即保存"，非本机提交必被 403。
    set_token_blocked_reason（[75]BUG-B）给出被拒原因，前端据此分叉指引。
    current_client_requires_auth 用于登录页免口令分支。三者均取自 deps，不在本层重算。

    configured 只读一次并同源传给 current_client_requires_auth，避免同一响应内
    两个字段读到不同配置值而给出互相矛盾的结论。
    """
    configured = _resolve_configured_token()
    blocked = set_token_blocked_reason(request)
    return {
        "access_token_configured": bool(configured),
        "can_set_access_token": blocked is None,
        # [75]BUG-B：前端据此分叉指引。* 部署下若只给 can_set=False 而不说原因，
        # 前端只能提示"去服务端本机设置"，用户照做仍被拒 → 死路。
        "set_token_blocked_reason": blocked,
        "current_client_requires_auth": current_client_requires_auth(request, configured),
    }


@router.post("/auth/token")
@handle_config_errors("设置访问口令")
async def set_api_token(req: SetTokenRequest, request: Request) -> Dict[str, Any]:
    """设置/更换访问口令（唯一权威写入口）。

    鉴权（防未鉴权者抢占设置权）：
      已设口令  经 main.py 统一挂 verify_token，无有效 token 进不来。
      未设口令  deps 的豁免只放行读端点 GET /auth/status，本写端点不在豁免内。
      本机准入  deps 裁定①只管免口令访问，白名单设备仍进得来本端点，故此处用同一判据兜住
                （deps 不掺和业务规则，SRP）。判据放函数体内而非 router 级依赖：安全门须对
                任何调用方式生效。* 部署下本机亦不可设，见 deps._is_trusted_localhost。
    """
    # 准入先于业务校验（长度、env 接管）；[75]BUG-B 文案按真实原因取
    blocked = set_token_blocked_reason(request)
    if blocked:
        raise HTTPException(status_code=403, detail=SET_TOKEN_BLOCKED_MESSAGES[blocked])
    new_token = req.token.strip()
    # 空串 len=0 必然 < 8，一条判据同时拦掉"留空"与"过短"，不再单写 if not new_token（死代码）。
    # 拒绝留空是刻意的安全取向: 静默清空口令等于无声关掉全站鉴权（防呆 > 便利）。
    if len(new_token) < 8:
        raise HTTPException(
            status_code=400,
            detail="访问口令至少 8 位且不可为空（建议 16 位以上随机串）；"
                   "如需关闭鉴权请显式设置环境变量 OMNIAGENT_REQUIRE_AUTH=0",
        )
    # 2026-09-26 小欧 - 修 C01：deps 是 env 优先，本函数原先无 env 接管检测，无条件写 yaml 后
    #   回"旧口令已作废"。env 部署下管理员改口令 → 旧口令（env 里的）仍有效、新值永不生效且无报错，
    #   "泄露了改成新的立即作废"的承诺形同虚设。改：env 接管时显式拒绝并指路。
    if (os.environ.get(ACCESS_TOKEN_ENV) or "").strip():
        raise HTTPException(
            status_code=409,
            detail=f"访问口令当前由环境变量 {ACCESS_TOKEN_ENV} 接管，设置页改写不生效"
                   f"（env 优先于配置文件）。请修改该环境变量后重启后端；"
                   f"或先清除该环境变量再回到本页面设置。",
        )
    merge_region_patch({ACCESS_TOKEN_CONFIG_KEY: new_token}, scope="auth")
    return {
        "ok": True,
        # 2026-09-27 小欧 - 与 GET /auth/status 对齐改名（原 "configured" 泛化，看不出是访问口令）
        "access_token_configured": True,
        "message": "访问口令已保存，立即生效（旧口令已作废）",
    }
