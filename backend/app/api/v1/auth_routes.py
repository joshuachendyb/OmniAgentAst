# -*- coding: utf-8 -*-
"""
auth_routes — 访问口令（token）设置接口

编辑历史:
  2026-09-26 - 小欧 - [72]第九章(9.5.3 第1步/第4步 + 9.8) 新建。补齐第九章的"设置侧" ——
    此前只实现了"校验侧"(deps.verify_token 读 security.access_token) 与"登录页"，
    但**无处可设口令** → 用户被 401 跳登录页后拿不到口令，系统进不去（死锁）。
    本模块提供口令的**唯一权威写入口**，使 "设置一次即可" 与 "泄露可随时换"（9.5.3 第1/4步）落地。

设计（与 [72]第六章方案 B 严格一致）：
  - `security.access_token` 是 registry 的 **secret=True** 项 → 读路径经 mask_secret_value 掩码
    （**永不回明文**），settings 通用通道写路径被 `_validate_value` **显式拒绝**。
  - 改口令**只走本模块的专用端点**（与 provider 通道 model_service.update_provider_config 同构：
    单一权威写入口 + 通用通道显式拒绝），杜绝"同一个 key 两个写入口"的分叉。

  两条端点（豁免判定全在 deps.verify_token 内，本文件不重复判断）：
  POST /auth/token   设/改口令。**仅限本机**（deps + 本函数体双重把关）；已配置时另需当前有效 token
  GET  /auth/status  查是否已配置（**不回明文**，只回 configured；未配置时对所有来源放行，供前端引导首设）

  2026-09-26 小欧 - 三堂会审修 3 处"注释/文案与实现不符"（撒谎的注释比没注释更坏）：
    ①token 的 description 原写"留空 = 关闭鉴权" —— 实现里留空一律 400（len=0 已被长度校验拦掉）。
      已改为"不可留空"，关闭鉴权指明走 OMNIAGENT_REQUIRE_AUTH=0。
    ②set_api_token docstring 原写"见 main.py 特殊挂载" —— 实际无特殊挂载，main.py 对所有 router 一视同仁。
    ③删死代码 `if not new_token: 400`：空串已被长度校验拦掉，两条判据合一（KISS-DIRECT）。

  2026-09-27 小欧 - 精简冗长注释（三堂会审叙事压缩为结论，只留决策不留过程）。
    同轮修正本文件 docstring 的又一处撒谎：原写"非本机设口令一律 401"，实际 deps.verify_token
    抛的是 403（北京老陈裁定"设口令只能本机"属准入失败、非口令错误）。已按实现改写。
  2026-09-27 小欧 - SetTokenRequest.token 加 max_length=200000（此前只有下限 8 位，
    超长口令可被写入 yaml）。本机准入改用 deps._is_trusted_localhost：FORWARDED_ALLOW_IPS=*
    时伪造 XFF 即可冒充本机，必须与 deps.verify_token 用同一判据，否则此端点仍可被绕过。
"""
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.v1.deps import (
    ACCESS_TOKEN_CONFIG_KEY,
    ACCESS_TOKEN_ENV,
    _client_ip,
    _is_trusted_localhost,
    _resolve_configured_token,
)
from app.services.model.config_helpers import (
    handle_config_errors,
    mask_secret_value,
    merge_region_patch,
)

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
async def get_token_status() -> Dict[str, Any]:
    """查访问口令配置状态。**永不回明文**，只回 configured（供设置页显示"已配置/未配置"）。

    2026-09-27 小欧 - 删 `bootstrap_allowed`（YAGNI）：曾加它想让前端分流"只能本机设置"文案，
    但无消费方。准入由 set_api_token 的本机检查强制，前端文案另议。
    """
    current = _resolve_configured_token()
    return {
        "access_token_configured": bool(current),
        # masked 与 provider api_key 同形（掩码同一权威）；外层 configured 省得前端再解一层
        "masked": mask_secret_value(current),
        "config_key": ACCESS_TOKEN_CONFIG_KEY,
        "env_name": ACCESS_TOKEN_ENV,
    }


@router.post("/auth/token")
@handle_config_errors("设置访问口令")
async def set_api_token(req: SetTokenRequest, request: Request) -> Dict[str, Any]:
    """设置/更换访问口令（唯一权威写入口）。

    鉴权规则（防"未鉴权者抢占设置权"）：
      - 服务端**已配置**口令时：本端点经 main.py 统一挂 verify_token，无有效 token 根本进不来。
      - 服务端**未配置**口令时：deps.verify_token 的首次设置豁免**只放行读端点**
        GET /auth/status（configured=false 引导首设），**本写端点不在豁免内** ——
        非本机客户端一律 403（防局域网任意客户端抢先设口令锁死管理员）。管理员首次配置在服务端本机进行。
      - **本机准入**（北京老陈裁定「设置口令只能本机，白名单的只是免口令登录」）：
        deps 的豁免只管"能否免口令访问"，白名单设备**能进得来**本端点，故此处单独兜住
        ——deps 不掺和业务规则（SRP）。判据放在**函数体内**而非 router 级依赖：
        安全门必须对任何调用方式生效，放在依赖上会被直调该函数的调用绕过。
        豁免逻辑在 deps.verify_token 一处实现，本文件不重复判断（单一权威，DRY）。
    """
    # 本机准入：先于一切业务校验（长度、env 接管）——它是"能不能做这件事"的准入，不是业务状态
    if not _is_trusted_localhost(_client_ip(request)):
        raise HTTPException(
            status_code=403,
            detail="设置或更换访问口令只能在服务端本机进行"
                   "（白名单设备只是免口令登录，不能改口令）",
        )
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
