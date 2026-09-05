# 编辑历史:
# 2026-07-22 - 小欧 - 修复: _validate_model_in_list 模型不在列表时由 raise ValueError 改为 logger.warning
#   背景: 用户选择模型 deepseek-v4-flash-free 不在 provider sensenova 的 models 列表时,
#   原代码抛 ValueError → 一路穿透到 chat_stream(第186行 get_service() 在 generate() 之外)
#   → FastAPI 全局异常处理器 → ASGI 层炸掉 → 长篇 traceback + 前端500
#   修复(v3):
#     1. _validate_model_in_list 返回带可用模型列表的warning消息, 纯验证无副作用(SRP)
#     2. resolve_provider_model 接收返回值存 self._model_warning (编排层存状态)
#     3. pop_model_warning() 供 chat_stream 获取透传给前端 start step
#     4. send_start_step(handlers.py) + step_start(openai.py) 接收 warning 参数传入 MetaStep
#     5. validate_config 使用返回值, warning 出现在验证结果中
#   合规: SRP + KISS + DRY + SLAP
# 2026-08-22 - 小欧 - model结构化归一报告v1.25 6.6: resolve_provider_model 二元组改 resolve_model_ref 返回
#   ModelRef(provider+model 结构, F8 禁 backward 不留旧签名); validate_config 返回值同步归一为
#   (is_valid, config_model: ModelRef, errors) — 调用点 lifecycle/config_service/stream_orchestrator 已随改
# 2026-09-05 - 小健 - 8.7 会话模型覆盖决议外迁(纯搬迁): 新增 resolve_session_client 独立函数,
#   承接 orchestrator 编排⑥ sessionModel 块(原 stream_orchestrator.py 285-336),
#   读会话覆盖→按 provider 查配置→构造独立客户端快照; 无覆盖返回 None, 由编排层赋值 agent.llm_client
"""
AI配置解析器 — 直接读配置,无效就报错

迁入: services/config/resolver.py — 小欧 2026-07-10
Author: 小沈 - 2026-06-07
"""

from typing import Dict, Any, Tuple, Optional
from app.config import Config, get_config
from app.db.models.chat_models import ModelRef
from app.logger import logger
from app.db import db
from app.services.chat.storage import get_session_model


class AIConfigResolver:
    
    def __init__(self, config: Optional[Config] = None):
        self._config = config or get_config()
        self._model_warning: Optional[str] = None
    
    def get_ai_config(self) -> Dict[str, Any]:
        return self._config.get("ai", {})
    
    def _extract_provider_model(self, ai_config: Dict[str, Any]) -> Tuple[str, str]:
        """提取provider和model - 小沈 2026-06-08"""
        provider = ai_config.get("provider", "")
        model = ai_config.get("model", "")
        return provider, model
    
    def _validate_provider_model_not_empty(self, provider: str, model: str) -> None:
        """验证provider和model不为空 - 小沈 2026-06-08"""
        if not provider or not model:
            raise ValueError(f"AI配置缺少provider或model: provider={provider}, model={model}")
    
    def _validate_provider_exists(self, ai_config: Dict[str, Any], provider: str) -> None:
        """验证provider存在 - 小沈 2026-06-08"""
        if provider not in ai_config:
            raise ValueError(f"配置文件中不存在 provider: {provider}")
    
    def _get_provider_config(self, ai_config: Dict[str, Any], provider: str) -> Dict[str, Any]:
        """获取provider配置 - 小沈 2026-06-08"""
        provider_config = ai_config[provider]
        if not isinstance(provider_config, dict):
            raise ValueError(f"provider {provider} 配置格式错误")
        return provider_config
    
    def _validate_model_in_list(self, provider_config: Dict[str, Any], provider: str, model: str) -> Optional[str]:
        """验证model在列表中, 不在则warning并返回提示消息(含可用列表) - 小欧 2026-07-22"""
        models = provider_config.get("models", [])
        if model not in models:
            msg = f"model \"{model}\" 不在 provider \"{provider}\" 的 models 列表中，可用模型: {', '.join(models)}"
            logger.warning(msg)
            return msg
        return None

    def pop_model_warning(self) -> Optional[str]:
        """获取并清除模型列表校验警告（一次性透传给前端）— 小欧 2026-07-22"""
        msg = self._model_warning
        self._model_warning = None
        return msg
    
    def resolve_model_ref(self) -> ModelRef:
        """直接读配置的provider和model,无效就报错 — 返回 ModelRef 结构(归一, 禁二元组拆包) — 小欧 2026-08-22
        api_base 当前无调用方需求(F7), 不在此读取; 构造服务实例时由 provider_config 补齐(lifecycle 6.6)"""
        ai_config = self.get_ai_config()
        provider, model = self._extract_provider_model(ai_config)

        self._validate_provider_model_not_empty(provider, model)
        self._validate_provider_exists(ai_config, provider)
        provider_config = self._get_provider_config(ai_config, provider)
        warning = self._validate_model_in_list(provider_config, provider, model)
        if warning:
            self._model_warning = warning

        return ModelRef(provider=provider, model=model)
    
    def get_service_config(self, provider: str, model: str) -> Dict[str, Any]:
        ai_config = self.get_ai_config()
        if provider not in ai_config:
            raise ValueError(f"配置文件中不存在 provider: {provider}")
        return ai_config[provider]

    def validate_config(self) -> tuple:
        """验证AI配置有效性 — 完全复用已有方法 — 小欧 2026-08-22 返回值归一 ModelRef
        Returns:
            (is_valid, config_model: ModelRef, error_messages)
        """
        ai_config = self.get_ai_config()
        provider, model = self._extract_provider_model(ai_config)
        errors = []
        try:
            self._validate_provider_model_not_empty(provider, model)
            self._validate_provider_exists(ai_config, provider)
            provider_config = self._get_provider_config(ai_config, provider)
            warning = self._validate_model_in_list(provider_config, provider, model)
            if warning:
                errors.append(warning)
        except ValueError as e:
            errors.append(str(e))
        return (len(errors) == 0, ModelRef(provider=provider or "unknown", model=model or ""), errors)


_global_resolver: Optional[AIConfigResolver] = None


def get_ai_config_resolver() -> AIConfigResolver:
    global _global_resolver
    if _global_resolver is None:
        _global_resolver = AIConfigResolver()
    return _global_resolver


async def resolve_session_client(ai_service, session_id):
    """会话模型覆盖决议：返回独立客户端快照，无覆盖返回None。纯搬迁，逻辑零改动。
    # 2026-09-05 - 小健 - 自 stream_orchestrator 编排⑥(原 285-336)整块外迁, 逐字复制逻辑零改动。
    #   S2 sessionModel 生效(10.1.7②-4/文档2 6.1.1/6.1.8)：编排层读会话覆盖写 ai_service.llm_model(L2 结构化)
    #   归一(小欧 2026-08-22 报告v1.25 6.5): 整个 ModelRef 单变量原子切换——缺省键回退原值合并,
    #   消除原逐属性赋值的半覆盖中间态(KISS-DIRECT 纯增强)
    """
    if not session_id:
        return None
    try:
        # 落库 offload 出事件循环(后端卡死修复收尾 小欧 2026-08-24)
        _ov = await db.atxn("chat", lambda conn: get_session_model(conn, session_id))
        if _ov and (_ov.model or _ov.provider):
            # 病根修复(小沈 2026-08-29): 旧实现直接改共享单例 ai_service.llm_model + reset_sdk,
            # 是"用全局副作用表达每会话模型", 单例还原时序竞态→断连后台任务误模/跨会话串模(#5)。
            # 改为构造本会话独立 LLM 客户端快照(携带覆盖模型), 与进程单例解耦: 会话流与后台任务均用快照,
            # 共享单例恒定全局默认不变, 不再需要 finally 还原, 根除 #5 两类退化(含断连后跨会话泄漏窄边界)。
            # 2026-09-01 小欧: L2 切跨 provider 模型, api_base/api_key/model_params(含 context_limit)
            # 均按目标 provider+model 从 config.yaml 查出(后端内部, 不落库、不出前端);
            # api_base 必须用目标 provider 的, 而非 _ov.api_base or 全局(全局=agnes 地址, 仍 503)
            _pv_cfg = None
            _pv_key = None
            _pv_ebp = None
            _pv_ctx = None
            if _ov.provider and _ov.provider != ai_service.llm_model.provider:
                try:
                    _pv_cfg = get_ai_config_resolver().get_service_config(
                        _ov.provider, _ov.model or "")
                    _pv_key = (_pv_cfg.get("api_key") or "").strip() or None
                    # model_params 解析复用 service.parse_model_params(DRY 唯一权威, 与全局实例同逻辑)
                    from app.services.lifecycle.service import parse_model_params
                    _pv_ebp, _pv_ctx = parse_model_params(_pv_cfg, _ov.model or "")
                except Exception as _pv_e:
                    logger.warning(f"[chat] 按 provider 查配置失败({_ov.provider}): {_pv_e}, 放弃会话模型覆盖")
                    _pv_cfg = None
                    _pv_key = None
                    _pv_ebp = None
                    _pv_ctx = None
            if _pv_cfg is None and _ov.provider and _ov.provider != ai_service.llm_model.provider:
                logger.warning(f"[chat] 会话模型覆盖已跳过(配置查找失败), 使用全局默认模型: provider={ai_service.llm_model.provider}, model={ai_service.llm_model.model}")
                return None
            override_ref = ModelRef(
                provider=_ov.provider or ai_service.llm_model.provider,
                model=_ov.model or ai_service.llm_model.model,
                api_base=(_pv_cfg or {}).get("api_base") or ai_service.llm_model.api_base,
                display_name=_ov.display_name or ai_service.llm_model.display_name,
            )
            session_client = ai_service.snapshot(
                override_ref,
                api_key=_pv_key,
                extra_body_params=_pv_ebp,
                context_limit=_pv_ctx,
            )
            # 2026-09-01 小欧: 同步 _task_llm_model 为生效快照模型, 使 react_cycle 日志/telemetry
            # 显示真实生效模型(而非全局 agnes), 与 TASK_START 显示实际生效模型同一精神
            logger.info(f"[chat] L2 sessionModel 已生效(独立客户端快照): session={session_id}, "
                        f"provider={session_client.llm_model.provider}, model={session_client.llm_model.model}")
            return session_client
    except Exception as _ov_e:
        logger.warning(f"[chat] 读会话sessionModel失败(session={session_id}): {_ov_e}")
    return None
