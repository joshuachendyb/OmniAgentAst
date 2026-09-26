# -*- coding: utf-8 -*-
"""模型管理路由薄壳。

编辑历史:
  2026-09-20 - 小沈 - 新建：/models /providers CRUD（5.2 模型管理接口）
   2026-09-21 - 小欧 - 对齐文档54 9.1.6：import 补 ModelAddRequest/ProviderInfo/ProviderUpdate（DTO 复用 config_schemas）
   2026-09-24 - 小欧 - 禁止backward死代码清理: 删未使用的 ModelAddRequest/ProviderInfo/ProviderUpdate import
     （本文件实际用 ModelCreateRequest/ModelUpdateRequest/ProviderConfigUpdate/ProviderAddRequest）— 小欧-2026-09-24
   2026-09-21 - 小欧 - 三堂会审第三轮 22 真实 bug 修复：①M13 add_provider 透传 req.models 列表与
     req.max_retries（旧实现丢弃，DTO 有字段借而不传，前端无法创建多模型 Provider/设置重试）；
     ②S7 ProviderConfigUpdate 补 label 字段并交由 update_provider_config 落盘（旧实现 provider
     label 创建后永不可改）
   2026-09-21 - 小欧 - 建议报告 P18: PUT/DELETE /models/{provider}/{model} 路由 model 参数改 :path 转换器——
     FastAPI 单段 path 参数对模型名含 '/'（真实 z-ai/glm-4.7, moonshotai/kimi-k2）先解码再分断必然 404，
     改贪婪吞余段后含斜杠模型名可更新/删除
   2026-09-22 - 小欧 - [62]P1/P2 param_options 读写链落地：P1 ModelCreateRequest/ModelUpdateRequest 各加
     param_options: Optional[Dict[str,List[str]]]=None（Pydantic 不声明即丢字段，老前端不送也不报错）；
     P2 POST /models 路由 add_model 调用透传 req.param_options（5 位置参→7 位置参，防 param_options 形参
     永远拿 None 静默丢）。PUT 路由无需改——model_dump(exclude_none=True) 自动含 param_options。
   2026-09-22 - 小欧 - [62]P6 4.3(3) ProviderConfigUpdate 补 max_retries: Optional[int]=None：
     前端 ProviderConfig.tsx 实际发送 max_retries 而 DTO 原只有 retry_times 别名，Pydantic v2
     extra='ignore' 丢弃未声明字段 → model_dump 不产 max_retries → 落不了盘；补声明后
     前端发的 max_retries 直连 key_map，不再依赖隐式绕过（BY-06 红条件验证）。
   2026-09-22 - 小欧 - [62]P8 4.3(9)-3-a/b：import 补 ConfigDict + ProviderConfigUpdate 加
      model_config = ConfigDict(extra='allow')——动态字段（rate_limit 等 param_types 元数据驱动）
      放行（静态字段仍强类型），后端白名单拒注入在 model_service.update_provider_config。
   2026-09-24 - 小欧 - 参数删除键级通道：ModelUpdateRequest 加 remove_params: Optional[List[str]]=None
      （前端②参数行 × 删除按钮经 PUT /models 送键名列表，update_model 白名单放行并先删后 merge；
      不声明则 Pydantic 丢字段，老前端不送不报错）— 小欧-2026-09-24
   2026-09-24 - 小欧 - [68] 模型库：新增 RemoteModelItem/RemoteModelsResponse/ProviderModelsReplaceRequest
      DTO + GET /providers/{name}/remote-models + PUT /providers/{name}/models 两 endpoint
      （远程拉取走后端代理绕 CORS，替换式写入 models 列表）— 小欧-2026-09-24
   2026-09-26 - 小欧 - [72]第十章(10.3) 落地: 新增 POST /providers/{name}/test-connection 端点 + TestConnectionRequest DTO
      ①复用 svc.fetch_remote_models(name, probe_key=...) 的探测能力, 不新造第二套探测逻辑(DRY/KISS-DIRECT);
      ②用 POST body 而非 GET query 传待测 key —— GET query 会进 uvicorn access log, 服务器日志将留下明文 key,
        违反设计"待测 key 严禁落盘、严禁进日志"的硬要求;
      ③DTO extra='forbid' 拒绝未知字段, 杜绝任意键注入(与既有 DTO 白名单口径一致);
      ④返回 category(ok/key_invalid/endpoint_unsupported/network_error) 供前端分流"地址问题"与"key 问题"两套文案 — 小欧-2026-09-26
   2026-09-26 - 小欧 - [72]第十二章(12.5) 落地: 新增 GET /providers/{name}/api-key 明文查看端点
      ①必须记审计日志: provider 名 + 来源 IP(request.client.host), 读密钥属敏感操作须可追溯;
         env 接管被拒时**同样留痕**(谁在探查 env 接管的密钥也要可查);
      ②env 接管一律拒绝返回明文(400): env 优先消费, YAML 里那个不是生效值, 给出即假象
         (与第二章"静默回落"同类陷阱), 文案明确指出真实来源 {NAME}_API_KEY;
      ③上线硬依赖第九章 token 鉴权 —— 无鉴权时局域网任何客户端可直接调走全部明文密钥(见 12.6 依赖表);
      ④新增 _client_ip 辅助(取 request.client.host, 无 request 时返回 unknown 不抛) — 小欧-2026-09-26
"""
import os  # [72]第十二章(12.5) 小欧 2026-09-26: env 接管判定（拒绝返回明文）
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.api.v1.config_schemas import (
    ProviderAddRequest,
)
from app.logger import logger  # [72]第十二章(12.5) 小欧 2026-09-26: 明文查看审计日志
from app.services.model.config_helpers import handle_config_errors
from app.services.model import model_service as svc
# 2026-09-26 - 小欧 - [72]三堂会审后修正(DRY): 审计用来源 IP 复用 deps._client_ip（唯一权威），
#   不在本文件另写一份。本文件原先自带的 _client_ip 与 deps 版是"同一逻辑两份实现"，
#   且语义还不一致（deps 版懂 TRUST_PROXY_HEADERS/X-Forwarded-For，本版不懂），
#   审计日志的 IP 口径会随调用点不同而漂移。现统一 + `or "unknown"` 保底（审计行不写空值）。
from app.api.v1.deps import _client_ip as _audit_ip


router = APIRouter()


class ModelCreateRequest(BaseModel):
    provider: str = Field(...)
    model: str = Field(...)
    label: str = Field("")
    default_params: Dict[str, Any] = Field(default_factory=dict)
    range: Dict[str, Any] = Field(default_factory=dict)
    capabilities: List[str] = Field(default_factory=list)
    param_options: Optional[Dict[str, List[str]]] = Field(default=None)


class ModelUpdateRequest(BaseModel):
    label: Optional[str] = Field(default=None)
    default_params: Optional[Dict[str, Any]] = Field(default=None)
    range: Optional[Dict[str, Any]] = Field(default=None)
    capabilities: Optional[List[str]] = Field(default=None)
    param_options: Optional[Dict[str, List[str]]] = Field(default=None)
    # 2026-09-24 小欧 - 参数键级删除：送键名列表，update_model 先从 model_params/range/param_options 删键再 merge — 小欧-2026-09-24
    remove_params: Optional[List[str]] = Field(default=None)


class ProviderConfigUpdate(BaseModel):
    """Provider 配置更新 DTO — 2026-09-22 小欧 [62]P6 补 max_retries：
    前端 ProviderConfig.tsx 发送 max_retries，DTO 原只有 retry_times 别名——Pydantic v2
    默认 extra='ignore' 会丢弃未声明字段，补声明后 model_dump(exclude_none=True) 才落盘。
    [62]P8 4.3(9)-3-b extra='allow'：静态字段仍强类型，动态字段（param_types 元数据驱动）
    放行——违背"前端零改代码"初衷的每个新参数无需改 DTO；后端白名单见 update_provider_config。"""
    model_config = ConfigDict(extra='allow')
    label: Optional[str] = Field(default=None, description="Provider 显示名")
    # [72]第三章(3.3 契约文档化) - 小欧 - 2026-09-26: api_key 三态契约写进字段说明，避免调用方误用。
    #   三态（后端已实现并做实为唯一权威，见 model_service.update_provider_config）：
    #     ①字段不出现 / None  = 不修改（跳过，不写）
    #     ②"" 或纯空白        = 不修改（跳过，不写）—— 与界面"留空=保持原值"对齐
    #     ③非空字符串         = 设置（先 strip 再落盘）
    #     ④clear=true         = 清空（显式写空串，唯一允许清空的途径）
    #   另：clear=true 与非空 api_key **互斥**，同传返回 400（[72]第四章）。
    #   ⑤base_url 空/纯空白  = 错误状态，返回 400（[72]第八章，与 api_key 三态方向相反）。
    api_key: Optional[str] = Field(
        default=None,
        description=(
            "API Key 三态: 不传/None/空串/纯空白=不修改; 非空=设置(自动 strip); "
            "清空须用 clear=true(与 api_key 互斥, 同传 400)。空串不再擦除已保存的 key"
        ),
    )
    base_url: Optional[str] = Field(
        default=None,
        description="API 地址。**必填语义**: 空/纯空白返回 400(错误状态，不可保存) —— 与 api_key 的'空=不修改'方向相反",
    )
    timeout: Optional[int] = Field(default=None)
    retry_times: Optional[int] = Field(default=None)
    max_retries: Optional[int] = Field(default=None)
    clear: Optional[bool] = Field(default=None, description="clear=true 显式清空 api_key")


class RemoteModelItem(BaseModel):
    id: str
    owned_by: Optional[str] = None


class RemoteModelsResponse(BaseModel):
    ok: bool
    provider: str
    models: List[RemoteModelItem]
    count: int
    configured: List[str]
    current_model: Optional[str] = None
    message: Optional[str] = None


class ProviderModelsReplaceRequest(BaseModel):
    models: List[str]


class TestConnectionRequest(BaseModel):
    """[72]第十章(10.3) - 小欧 - 2026-09-26: 测试连接请求体（可选带待测 key）。

    用 POST body 而非 GET query 传 key：GET 的 query 会进 uvicorn access log
    （服务器日志里会留下明文 key），违反设计"待测 key 严禁落盘、严禁进日志"的硬要求。
    """
    model_config = ConfigDict(extra='forbid')
    api_key: Optional[str] = Field(
        default=None,
        description="待测 key（可空=用已保存值）。仅本次探测用，不落盘、不进日志、不回传。",
    )


@router.get("/models")
@handle_config_errors("获取模型列表")
async def get_models():
    return svc.get_models()


@router.post("/models")
@handle_config_errors("添加模型")
async def add_model(req: ModelCreateRequest):
    return svc.add_model(req.provider, req.model, req.label,
                         req.default_params, req.range, req.capabilities,
                         req.param_options)


@router.put("/models/{provider}/{model:path}")
@handle_config_errors("修改模型")
async def update_model(provider: str, model: str, req: ModelUpdateRequest):
    # 2026-09-21 小欧 修 P18：模型名可含 '/'（真实 z-ai/glm-4.7、moonshotai/kimi-k2），
    # FastAPI 单段 path 参数遇 '/' 先解码再分断必然 404，改 path 转换器贪婪吞余段。
    return svc.update_model(provider, model, req.model_dump(exclude_none=True))


@router.delete("/models/{provider}/{model:path}")
@handle_config_errors("删除模型")
async def delete_model(provider: str, model: str):
    # 2026-09-21 小欧 修 P18：同 update_model，path 转换器支持含 '/' 模型名删除。
    return svc.delete_model(provider, model)


@router.get("/providers")
@handle_config_errors("获取 Provider 列表")
async def get_providers():
    return svc.get_providers()


@router.post("/providers")
@handle_config_errors("添加 Provider")
async def add_provider(req: ProviderAddRequest):
    return svc.add_provider(req.name, req.label or req.name, req.api_base,
                            req.api_key, req.model, req.timeout,
                            models=req.models, max_retries=req.max_retries)


@router.put("/providers/{name}")
@handle_config_errors("修改 Provider 配置")
async def update_provider(name: str, req: ProviderConfigUpdate):
    return svc.update_provider_config(name, req.model_dump(exclude_none=True))


@router.delete("/providers/{name}")
@handle_config_errors("删除 Provider")
async def delete_provider(name: str):
    return svc.delete_provider(name)


@router.get("/providers/{name}/remote-models")
@handle_config_errors("获取远程模型列表")
async def get_remote_models(name: str):
    return await svc.fetch_remote_models(name)


@router.get("/providers/{name}/api-key")
@handle_config_errors("查看 Provider 密钥明文")
async def get_provider_api_key_plain(name: str, request: Request):
    """[72]第十二章(12.5) - 小欧 - 2026-09-26: 返回**已保存**的 api_key 明文（供"眼睛"切换查看）。

    三条硬约束（设计 12.5 / 12.6）：
      ①**必须记审计日志**：provider 名 + 时间戳 + 来源 IP（request.client.host）—— 读密钥属敏感操作。
      ②**env 接管时一律拒绝返回明文**：env 优先消费(config.py _apply_env_overrides)，YAML 里那个可能
         **不是生效值**，给用户看是假象（与第二章"静默回落"同类陷阱）。文案明确指出真实来源。
      ③**上线硬依赖第九章 token 鉴权**：无鉴权时局域网任何客户端可直接调走全部明文密钥，
         故第九章落地前本接口不得对外暴露（见 12.6 依赖表）。
    """
    # 2026-09-26 - 小欧 - [72]三堂会审后修正·二(分层): 经 service 公开函数取数，
    #   不再直调 svc._raw_ai()/svc._provider_names() 私有函数（破坏封装，见 model_service 文件头）。
    entry = svc.get_provider_raw_entry(name)
    env_name = f"{name.upper()}_API_KEY"
    env_val = os.environ.get(env_name)
    if env_val:
        # 审计：拒绝也要留痕（谁在探查 env 接管的密钥）
        logger.info(
            f"[audit] 查看明文被拒(provider={name}, env={env_name}, ip={_audit_ip(request) or 'unknown'})"
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"该 provider 由 {env_name} 环境变量接管，密钥不在配置文件中，无法查看明文"
                f"（配置里的值不是生效值，给出即假象）"
            ),
        )
    # 2026-09-26 - 小欧 - [72]三堂会审后修正: strip 后再判 configured/返回。
    #   YAML 手误写了纯空白 key（"   "）时，原 `str(... or "")` 非空 → configured=True，
    #   还把空白串当"明文"返回（失真）。与掩码侧 is_blank_secret 口径对齐：空白=未配置。
    plain = str(entry.get("api_key") or "").strip()
    # 审计日志：读密钥属敏感操作，必须可追溯（provider + 时间戳 + 来源 IP）
    logger.info(f"[audit] 查看 Provider 密钥明文(provider={name}, ip={_audit_ip(request) or 'unknown'})")
    return {"provider": name, "api_key": plain, "configured": bool(plain)}


@router.post("/providers/{name}/test-connection")
@handle_config_errors("测试 Provider 连接")
async def test_provider_connection(name: str, req: TestConnectionRequest):
    """[72]第十章(10.3) - 小欧 - 2026-09-26: 复用 fetch_remote_models 的探测能力（DRY，不新造第二套探测逻辑）。

    返回 category 供前端分流文案：ok / key_invalid / endpoint_unsupported / network_error。
    """
    return await svc.fetch_remote_models(name, probe_key=req.api_key)


@router.put("/providers/{name}/models")
@handle_config_errors("替换 Provider 模型列表")
async def replace_provider_models(name: str, req: ProviderModelsReplaceRequest):
    return svc.replace_provider_models(name, req.models)
