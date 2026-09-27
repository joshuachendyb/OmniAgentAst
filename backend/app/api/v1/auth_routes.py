# -*- coding: utf-8 -*-
"""
auth_routes — 访问口令（token）设置接口

编辑历史:
  2026-09-26 - 小欧 - [72]第九章(9.5.3 第1步/第4步 + 9.8) 新建。补齐第九章的"设置侧" ——
    此前只实现了"校验侧"(deps.verify_token 读 security.api_token) 与"登录页"，
    但**无处可设口令** → 用户被 401 跳登录页后拿不到口令，系统进不去（死锁）。
    本模块提供口令的**唯一权威写入口**，使 "设置一次即可" 与 "泄露可随时换"（9.5.3 第1/4步）落地。

设计（与 [72]第六章方案 B 严格一致）：
  - `security.api_token` 是 registry 的 **secret=True** 项 → 读路径经 mask_secret_value 掩码
    （**永不回明文**），settings 通用通道写路径被 `_validate_value` **显式拒绝**。
  - 改口令**只走本模块的专用端点**（与 provider 通道 model_service.update_provider_config 同构：
    单一权威写入口 + 通用通道显式拒绝），杜绝"同一个 key 两个写入口"的分叉。

  两条端点（/status 由 deps 的首次设置豁免**只读放行**，其余情况与其他接口同一把锁）：
  POST /auth/token   设/改口令（已配置时需当前有效 token，防未鉴权者抢占；未配置时**不豁免**，
                     fail-closed：非本机/白名单一律 401，管理员在服务端本机首次配置）
  GET  /auth/status  查是否已配置（**不回明文**，只回 configured，供前端显示"已配置/未配置";
                     未配置时豁免放行，供前端经 configured=false 引导首设）

  2026-09-26 (三堂会审后修正) - 小欧 - 修 2 处"注释/文案与实现不符"（撒谎的注释比没注释更坏，
  后人照着它会做出错误改动):
    ①SetTokenRequest.token 的 description 原写"留空字符串 = 关闭鉴权" —— 实现里留空一律 400
      （len=0 < 8 在长度校验处即被拦），承诺的功能根本不存在。已改为"不可留空"+指明关闭鉴权的
      正道（环境变量显式声明，可追溯）；
    ②set_api_token docstring 原写"见 main.py 对本 router 的特殊挂载" —— 实际首次设置豁免是
      deps.verify_token 内按 AUTH_EXEMPT_PATHS 判定的，main.py 对所有 router 一视同仁统一挂
      verify_token，并无"特殊挂载"。已按实现改写。
    ③删死代码: 原 `if not new_token: 400` 分支永不可达（空串长度 0 已被上一条 <8 拦掉），
      空串与"过短"合并为一条判据（KISS-DIRECT：不为同一件事写两条判据）。
"""
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.deps import (
    API_TOKEN_CONFIG_KEY,
    API_TOKEN_ENV,
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
        description=(
            "新的访问口令。**不可留空**（留空一律 400，见 set_api_token）；"
            "至少 8 位，建议 16 位以上随机串。关闭鉴权请改用环境变量 "
            "OMNIAGENT_REQUIRE_AUTH=0（显式声明，可追溯），而非把口令置空"
        ),
    )


@router.get("/auth/status")
@handle_config_errors("查询访问口令状态")
async def get_token_status() -> Dict[str, Any]:
    """查访问口令配置状态。**永不回明文**，只回 configured（供设置页显示"已配置/未配置"）。"""
    current = _resolve_configured_token()
    return {
        "configured": bool(current),
        # masked 键内是与 provider api_key **同形**的 {configured, masked} 两键对象（掩码规则同一权威）；
        # 外层 configured 是给设置页直接用的布尔，省得前端再解一层
        "masked": mask_secret_value(current),
        "config_key": API_TOKEN_CONFIG_KEY,
        "env_name": API_TOKEN_ENV,
    }


@router.post("/auth/token")
@handle_config_errors("设置访问口令")
async def set_api_token(req: SetTokenRequest) -> Dict[str, Any]:
    """设置/更换访问口令（唯一权威写入口）。

    鉴权规则（防"未鉴权者抢占设置权"）：
      - 服务端**已配置**口令时：本端点经 main.py 统一挂 verify_token，无有效 token 根本进不来。
      - 服务端**未配置**口令时：deps.verify_token 的「首次设置豁免」**只放行读端点**
        GET /auth/status（configured=false 引导首设），**本写端点不在豁免内** ——
        非本机/白名单客户端一律 401（fail-closed 只读不写），防局域网任意客户端抢先
        设口令锁死管理员；管理员首次配置口令在服务端本机（本机豁免）进行。
        豁免逻辑在 deps.verify_token 一处实现，本文件不重复判断（单一权威，DRY）。
    """
    new_token = req.token.strip()
    # 不可为空 + 长度下限合并为一条判据: 空串 len=0 必然 < 8，故只需判长度即可同时拦掉"留空"，
    # 不必再写一条 `if not new_token` —— 那条分支永远不可达(死代码，YAGNI)。
    # 拒绝留空是刻意的安全取向: 静默把口令清空等于无声关掉全站鉴权(防呆 > 便利)。
    if len(new_token) < 8:
        raise HTTPException(
            status_code=400,
            detail="访问口令至少 8 位且不可为空（建议 16 位以上随机串）；"
                   "如需关闭鉴权请显式设置环境变量 OMNIAGENT_REQUIRE_AUTH=0",
        )
    # 2026-09-26 - 小欧 - 修 C01「env 存在时改口令静默失效」（三遍核实确认成立）：
    #   deps._resolve_configured_token 是**环境变量优先**（env 非空就直接返回，不看配置文件），
    #   而本函数改前**无任何 env 接管检测**，无条件写 yaml 后无条件回"旧口令已作废"。
    #   ⇒ 在多机部署按文档用 OMNIAGENT_API_TOKEN 统一口令的形态下：管理员在设置页改口令 →
    #   前端提示"旧口令已作废" → **旧口令（env 里的）仍然有效**，新写的值成了永不生效的影子值，
    #   且**无任何报错**。安全承诺（9.5.3 第4步"泄露了改成新的，旧的立即作废"）在 env 部署下直接失效，
    #   已泄露的口令无法通过本接口作废。
    #   修法：env 接管时**显式拒绝并指路**（与 provider 通道的 `_raise_if_env_takeover` 同一口径），
    #   而不是让用户以为改成功了。 —— 编辑：小欧 2026-09-26
    if (os.environ.get(API_TOKEN_ENV) or "").strip():
        raise HTTPException(
            status_code=409,
            detail=f"访问口令当前由环境变量 {API_TOKEN_ENV} 接管，设置页改写不生效"
                   f"（env 优先于配置文件）。请修改该环境变量后重启后端；"
                   f"或先清除该环境变量再回到本页面设置。",
        )
    merge_region_patch({API_TOKEN_CONFIG_KEY: new_token}, scope="auth")
    return {
        "ok": True,
        "configured": True,
        "message": "访问口令已保存，立即生效（旧口令已作废）",
    }
