
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-22 - 小欧 - get_service 异常时清除 _model_warning 防止残留到下一请求(代码审查缺陷1边沿修复)
# 2026-08-14 - 小欧 - llm 独立为 app 顶层能力层目录(services/llm→app/llm), 本文件 import 路径同步
# 2026-08-17 - 小健 - DEFAULT_CONTEXT_LIMIT(262144) 迁 app.services.agent.compaction_constants; create_service_instance 局部导入引用, 取值顺序不变(配置 model_params.context_limit 优先, 否则默认兜底)
# 2026-08-22 - 小欧 - model结构化归一报告v1.25 6.6: 全链 ModelRef 归一——get_resolver_and_config 返回
#   resolved_model(ModelRef); _current_provider 单值态升级 _current_model_ref 结构态(缓存判定整体比较);
#   create_service_instance 构造 BaseAIService 改传 llm_model=ModelRef(api_base 由 provider_config 纳入,
#   设计要求3); get_service_for_model 入参归一 model_ref: ModelRef — 调用点已随改(F8 无兼容 shim)
# 2026-09-01 - 小欧 - DRY 归一: 新增 parse_model_params(provider_config, model)->(extra_body_params, context_limit)
#   唯一权威解析 model_params; create_service_instance 与 stream_orchestrator(L2 跨 provider 快照)同用,
#   消除 create_service_instance 内联 model_params 解析双份漂移
"""
service — 服务创建与获取

合并: get_service + get_service_for_model
小沈 2026-06-17
"""

from typing import Optional, Dict, Any, Tuple
import threading

from app.logger import setup_logger
from app.llm import BaseAIService
from app.db.models.chat_models import ModelRef
from app.services.lifecycle.lifecycle import close_instance_sync

logger = setup_logger(__name__)

_instance: Optional[BaseAIService] = None
_current_model_ref: Optional[ModelRef] = None   # 归一: 结构态替代原 _current_provider 单值态 — 小欧 2026-08-22
_instance_lock = threading.Lock()


def get_resolver_and_config():
    """获取resolver和配置 — 小沈 2026-06-08; 2026-06-17 去除_前缀; 2026-08-22 返回 resolved_model(ModelRef)"""
    from app.services.model.resolver import get_ai_config_resolver
    resolver = get_ai_config_resolver()
    resolved_model = resolver.resolve_model_ref()
    ai_config = resolver.get_ai_config()
    return resolver, resolved_model, ai_config


def validate_provider_model(final_provider: str, final_model: str) -> None:
    """验证provider和model — 小沈 2026-06-08; 2026-06-17 去除_前缀"""
    if not final_provider:
        raise ValueError("未找到有效的AI provider配置")
    if not final_model:
        raise ValueError("未找到有效的AI model配置")


def check_cache_valid(config_model: ModelRef) -> bool:
    """检查缓存是否有效 — 小沈 2026-06-08; 2026-08-22 归一: 整体 ModelRef 值比较(Pydantic 相等) — 小欧"""
    return _instance is not None and _current_model_ref == config_model


def cleanup_old_instance(new_model_ref: Optional[ModelRef] = None) -> None:
    """清理旧实例 — 小沈 2026-06-08; 小欧 2026-06-09 新增new_provider参数; 2026-06-17 去除_前缀+透传层;
    2026-08-22 归一: 参数改 new_model_ref: Optional[ModelRef] — 小欧"""
    global _instance, _current_model_ref
    old_instance = _instance
    _instance = None
    _current_model_ref = new_model_ref
    close_instance_sync(old_instance)


def log_service_creation(final_provider: str, final_model: str) -> None:
    """记录服务创建日志 — 小沈 2026-06-08; 2026-06-17 去除_前缀+透传层"""
    log_msg = f"[AIServiceFactory] 创建服务实例: provider={final_provider}, model={final_model}"
    logger.info(log_msg)


def get_provider_config(ai_config: dict, final_provider: str) -> dict:
    """获取provider配置 — 小沈 2026-06-08; 2026-06-17 去除_前缀"""
    provider_config = ai_config.get(final_provider, {})
    if not provider_config:
        raise ValueError(f"provider {final_provider} 的配置为空,请检查 config.yaml")
    return provider_config


def parse_model_params(provider_config: dict, model: str) -> Tuple[Optional[dict], int]:
    """解析 provider 配置的 model_params → (extra_body_params, context_limit)
    复用优先/DRY 归一(小欧 2026-09-01): 原逻辑双份嵌在 create_service_instance(本文件) 与
    stream_orchestrator(L2 跨 provider 快照), 双份漂移风险; 归一为本函数唯一权威, 两处同用。
    行为: 取目标 model 专属 dict, pop context_limit(配置优先否则 DEFAULT_CONTEXT_LIMIT 兜底),
    余量作 extra_body_params(无则 None)。与历史行为完全一致(仅去重, 不改逻辑)。"""
    from app.services.agent.compaction_constants import DEFAULT_CONTEXT_LIMIT  # 小健 2026-08-17: 常量权威归一 agent/compaction_constants
    model_params = (provider_config or {}).get("model_params", {}) or {}
    specific_params = dict(model_params.get(model, {})) if model_params else {}
    context_limit = specific_params.pop("context_limit", DEFAULT_CONTEXT_LIMIT)
    return (specific_params or None), context_limit


def create_service_instance(provider_config: dict, final_provider: str, final_model: str) -> BaseAIService:
    """创建服务实例 — 小沈 2026-06-08; 2026-06-17 去除_前缀+透传层; 小欧 2026-07-09 新增model_params透传;
    小健 2026-08-17 DEFAULT_CONTEXT_LIMIT 迁 agent.compaction_constants;
    2026-08-22 小欧 归一报告v1.25 6.6: BaseAIService 构造改传 llm_model=ModelRef(provider+model+api_base),
    api_base 来源 provider_config(设计要求3纳入 ModelRef); 2026-09-01 小欧 params 解析改复用 parse_model_params(DRY)"""
    extra_body_params, context_limit = parse_model_params(provider_config, final_model)
    return BaseAIService(
        api_key=(provider_config.get("api_key") or "").strip(),
        llm_model=ModelRef(
            provider=final_provider,
            model=final_model,
            api_base=(provider_config.get("api_base") or "https://api.openai.com/v1").strip(),
        ),
        timeout=provider_config.get("timeout", 30),
        max_tokens=provider_config.get("max_tokens"),
        temperature=float(provider_config.get("temperature", 0.7)),
        seed=provider_config.get("seed", None),
        extra_body_params=extra_body_params,
        context_limit=context_limit,
    )


def get_service() -> BaseAIService:
    """获取服务实例 — 小沈 2026-06-08
    P2-09修复: 删除未使用的config_path
    【修复P1-1 2026-06-09 小沈】threading.Lock保护多线程安全
    【修复P-2026-07-22 小欧】异常时清除 _model_warning 防止残留到下一请求
    【2026-08-22 小欧】归一: 拆包变量随 get_resolver_and_config 新返回值同步(config_model: ModelRef)
    """
    global _instance, _current_model_ref

    resolver, config_model, ai_config = get_resolver_and_config()

    try:
        validate_provider_model(config_model.provider, config_model.model)

        if check_cache_valid(config_model):
            return _instance

        with _instance_lock:
            if check_cache_valid(config_model):
                return _instance
            cleanup_old_instance(config_model)

            log_service_creation(config_model.provider, config_model.model)

            provider_config = get_provider_config(ai_config, config_model.provider)

            _instance = create_service_instance(provider_config, config_model.provider, config_model.model)
    except:
        # get_service 异常时消费并丢弃 _model_warning，防止残留到下一请求— 小欧 2026-07-22
        resolver.pop_model_warning()
        raise

    return _instance


def reset_instance():
    """重置实例 — 小沈 2026-06-08
    P1-07修复: 公开reset方法,替代直接操作私有变量
    【修复P1-1 2026-06-09 小沈】threading.Lock保护
    【2026-08-22 小欧】归一: _current_model_ref 结构态
    """
    global _instance, _current_model_ref
    with _instance_lock:
        old = _instance
        _instance = None
        _current_model_ref = None
    return old


def set_instance(instance, model_ref: Optional[ModelRef] = None):
    """设置实例 — 小沈 2026-06-08
    P1-07修复: 公开set方法,替代直接操作私有变量
    【修复P1-1 2026-06-09 小沈】threading.Lock保护
    【2026-08-22 小欧】归一: 参数 provider:str → model_ref: Optional[ModelRef]
    """
    global _instance, _current_model_ref
    with _instance_lock:
        _instance = instance
        _current_model_ref = model_ref


def get_service_for_model(model_ref: ModelRef):
    """获取指定模型的服务实例 — 小沈 2026-06-08
    P2-07修复: 使用set_instance替代直接操作私有变量; P2-09: 删除未使用的config_path
    【2026-08-22 小欧】归一: 入参 (provider, model) → model_ref: ModelRef(F8 无兼容 shim, 调用点随改)
    """
    from app.services.model.resolver import get_ai_config_resolver
    resolver = get_ai_config_resolver()
    ai_config = resolver.get_ai_config()

    provider_config = resolver.get_service_config(model_ref.provider, model_ref.model)

    cleanup_old_instance(model_ref)

    log_service_creation(model_ref.provider, model_ref.model)

    if not provider_config:
        provider_config = {}

    instance = create_service_instance(provider_config, model_ref.provider, model_ref.model)
    set_instance(instance, model_ref)

    return instance

