# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-14 - 小欧 - 改名名实相符: model_schemas.py → config_schemas.py(实为配置DTO定义: ConfigUpdate/SecurityConfig/ProviderInfo等)
# 2026-08-22 - 小欧 - model结构化归一报告v1.25 6.6 方案B(前端随后端修改): ConfigUpdate.ai_provider/ai_model、
#   ConfigResponse.ai_provider/ai_model、FullConfigResponse.current_provider/current_model 分离字段归一为
#   ai_model_ref/current_model_ref: ModelRef 封装字段(前端 api.ts 契约同步改); FullConfigValidationResponse
#   死DTO(全仓无引用)按 YAGNI 删除
# 2026-09-21 - 小欧 - 三堂会审修复: ProviderAddRequest 添加 label 字段（model_routes.add_provider 依赖）
# 2026-09-21 - 小欧 - 对齐文档54 9.3.9：label 字段类型定为 str = Field("")（缺省与 name 相同），撤销此前 Optional[str] 变更
# 2026-09-21 - 小欧 - 修复 None 陷阱: ProviderInfo.api_base 由 Field(...) 改 Field("")（配置文件 api_base 缺失/None 时不再炸 Pydantic 500）
# 2026-09-21 - 小欧 - 删除无意义白/黑名单配置项: SecurityConfig 移除 whitelistEnabled/commandWhitelist/commandBlacklist
#   （全库无消费方，仅透传保存不生效；命令安全由 path_safe_check/tools/security 代码内实现，北京老陈裁定删除）
# 2026-09-21 - 小欧 - v4.20 死配置清理: SecurityConfig 移除 contentFilterEnabled/contentFilterLevel/maxFileSize（全库无消费方）
# 2026-09-22 - 小欧 - [61] constants.py 配置化迁移：import DEFAULT_MAX_STEPS 改别名 _D_MAX_STEPS + Field 默认值改读配置
# 2026-09-24 - 小欧 - 禁止backward死代码清理: 删 ProviderUpdate/ModelAddRequest 死DTO（仅被已删 /config/provider/* 路由引用）— 小欧-2026-09-24
# 2026-09-26 - 小欧 - [72]第七章(7.3) 落地: ConfigResponse.api_key_configured 字段说明写清"第3套契约"的语义边界 ——
#   本字段回答【是否已配置】(布尔, 不泄露任何位), 与掩码契约 mask_secret_value 的
#   {configured, prefix, suffix}(回答"已配置的话长什么样")语义不同、非重复, 故第3套保留不删；
#   但三套形状并存易令后人误以为可互换取错形状, 故在字段说明处显式区分(本项为 7.3 明确要求)。 — 小欧 2026-09-26
"""配置DTO定义（Pydantic模型）"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from app.constants import DEFAULT_MAX_STEPS as _D_MAX_STEPS
from app.config import get_config
from app.db.models.chat_models import ModelRef   # 归一: 模型身份唯一结构 — 小欧 2026-08-22


class SecurityConfig(BaseModel):
    """安全配置 — 2026-09-21 小欧 v4.20 死配置清理: 移除 contentFilterEnabled/contentFilterLevel/maxFileSize（无消费方）；仅保留 confirmDangerousOps（UX层）"""
    confirmDangerousOps: bool = Field(True, description="危险操作需要二次确认")


# 2026-09-26 - 小欧 - [72]第十一章(11.5 第1步) 修正: ConfigUpdate **保留但只留 ai_model_ref 一个字段**。
#   原计划整类删除（随 PUT /config 端点删），实施时实测发现文档 11.2「前端零调用」结论不成立 ——
#   configApi.switchCurrentModel（AppContext.tsx:266，顶栏与设置页「切换全局模型」唯一写链）在调 PUT /config，
#   整类删除会导致切全局模型 404 失效（功能退化，违反"只能增强不能退化"红线）。
#   故保留端点与本类，但**只保留切模型必需的 ai_model_ref**，其余 6 个字段全部删除：
#     provider_api_keys —— [72]第三章认定的"第二个能擦除密钥的入口"，删除即漏洞消失（本次整改的核心目标）
#     theme/language/max_steps/security/project_root —— 功能已全部迁移至 settings registry 对应项（11.2 表）
#   配合 config_helpers.FIELD_HANDLERS 同步只留 "ai_model_ref" 一项（六个旧 handler 已随第 1 步删除）。
class ConfigUpdate(BaseModel):
    """配置更新请求 — 归一: provider+model 成对语义由 ModelRef 单字段承载(原子切换)

    [72]第十一章: 原 7 字段现只留 ai_model_ref（切全局模型唯一必需）；其余 6 项功能已迁移或属安全隐患。

    2026-09-26 - 小欧 - [72]三堂会审后修正（修空 PUT 必 500 回归）:
    ai_model_ref 由 Optional 改为**必填**。收敛前 7 字段全 None 时派发循环自动跳过 → 无害 no-op 成功；
    收敛后 update_config 直调 _update_model_ref，后者首行即 `update.ai_model_ref.provider` ——
    空 PUT（{} 或缺该字段）会在 None 上取属性 → AttributeError → 被 except 吞成 500。
    PUT /config 的唯一能力就是切模型，不带模型调它属客户端错误，应在 DTO 层 422 拦掉，
    不得穿透到 service 变成 500。唯一合法调用方 switchCurrentModel 恒传完整 ref，不受影响。
    """
    ai_model_ref: ModelRef = Field(..., description="AI模型(provider+model 结构)")


class ConfigResponse(BaseModel):
    """配置响应 — 归一: ai_provider/ai_model → ai_model_ref: ModelRef"""
    ai_model_ref: ModelRef = Field(..., description="当前AI模型(provider+model 结构)")
    # [72]第七章(7.3) - 小欧 - 2026-09-26: 第 3 套契约保留，但在此写清它与掩码契约(第1/2套)的区别 ——
    # 本字段是**布尔问题**"是否已配置"(只回 configured 与否，不泄露任何位)，
    # 而 mask_secret_value 是**掩码问题**"已配置的话长什么样"(回 configured+prefix+suffix 三键)。
    # 二者语义不同、非重复，故本套不删；但读者易误以为三套可互换，故在此显式说明，避免后人取错形状。
    api_key_configured: bool = Field(
        ..., description="API Key是否已配置（布尔，只回是否；不回任何位，与掩码契约 mask_secret_value 的 {configured,prefix,suffix} 语义不同、非重复）"
    )
    theme: str = Field(..., description="当前主题")
    language: str = Field(..., description="当前语言")
    security: Optional[SecurityConfig] = Field(None, description="安全配置")
    max_steps: int = Field(_D_MAX_STEPS, description="Agent最大迭代次数")
    project_root: str = Field("", description="项目根目录路径")


class ConfigValidateRequest(BaseModel):
    """配置验证请求"""
    provider: str = Field(..., description="AI提供商")
    api_key: str = Field(..., description="API密钥")


class ConfigValidateResponse(BaseModel):
    """配置验证响应"""
    valid: bool = Field(..., description="配置是否有效")
    message: str = Field(..., description="验证消息")
    model: Optional[str] = Field(None, description="模型名称")


class ModelInfo(BaseModel):
    """模型信息"""
    id: int = Field(..., description="模型ID序号")
    provider: str = Field(..., description="提供商名称(小写)")
    model: str = Field(..., description="模型名称")
    display_name: str = Field(..., description="显示名称,格式: Provider (model)")
    current_model: bool = Field(default=False, description="是否为当前模型")


class ModelListResponse(BaseModel):
    """模型列表响应"""
    models: list[ModelInfo] = Field(..., description="可用模型列表")
    default_provider: str = Field(..., description="默认提供商")


class ApiKeyMask(BaseModel):
    """密钥掩码形态（[72]第七章 7.3 + 第十二章 12.5 三键恒定契约）。

    2026-09-26 - 小欧 - [72]三堂会审后修正（修 critical 回归）:
    config_service.get_full_config 已改用 mask_secret_value（返对象 {configured,prefix,suffix}），
    但 ProviderInfo.api_key 仍声明为 str → ProviderInfo(**p) 遇 dict 即抛 ValidationError →
    **GET /config/full 全挂 500**（已实测复现）。本类即该对象的 DTO 形态，与前端
    config.api.ts 的 ProviderInfo.api_key 对象声明同构（前后端同一契约）。
    """
    configured: bool = Field(..., description="是否已配置")
    prefix: str = Field("", description="前4位（短 key 为空）")
    suffix: str = Field("", description="末4位（短 key 为空）")


class ProviderInfo(BaseModel):
    """Provider信息"""
    name: str = Field(..., description="Provider名称")
    api_base: str = Field("", description="API地址")
    # 2026-09-26 - 小欧 - [72]第七章(7.3): 由 str 改为 ApiKeyMask 对象（见本类上方案内说明）。
    api_key: ApiKeyMask = Field(..., description="API密钥掩码（三键恒定，永不返明文）")
    model: str = Field("", description="当前使用的模型")
    models: list[str] = Field(default_factory=list, description="模型列表")
    timeout: int = Field(60, description="超时时间")
    max_retries: int = Field(3, description="最大重试次数")


class FullConfigResponse(BaseModel):
    """完整配置响应 — 归一: current_provider/current_model → current_model_ref: ModelRef"""
    providers: dict[str, ProviderInfo] = Field(..., description="所有Provider配置")
    current_model_ref: ModelRef = Field(..., description="当前使用的模型(provider+model 结构)")


class ProviderAddRequest(BaseModel):
    """添加Provider请求"""
    name: str = Field(..., description="Provider名称")
    label: str = Field("", description="显示名，缺省与 name 相同 — 小沈 2026-09-20")
    api_base: str = Field(..., description="API地址")
    api_key: str = Field("", description="API密钥")
    model: str = Field("", description="默认模型")
    models: list[str] = Field(default_factory=list, description="模型列表")
    timeout: int = Field(60, description="超时时间")
    max_retries: int = Field(3, description="最大重试次数")


class ConfigFixResponse(BaseModel):
    """配置修复响应"""
    success: bool = Field(..., description="修复是否成功")
    fixed_issues: List[str] = Field(default_factory=list, description="修复的问题列表")
    warnings: List[str] = Field(default_factory=list, description="警告列表")
    backup_path: str = Field("", description="备份文件路径")


class ConfigPathResponse(BaseModel):
    """配置文件路径响应"""
    config_path: str = Field(..., description="配置文件完整路径")
    config_dir: str = Field(..., description="配置文件所在目录")
    exists: bool = Field(..., description="配置文件是否存在")
