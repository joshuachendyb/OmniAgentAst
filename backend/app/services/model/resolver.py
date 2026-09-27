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
# 2026-09-20 - 小欧 - 无条件快照共享连接池 + 竞态用例验证:
#   ①snapshot 构造注入 shared_client(全局共享连接池引用), 快照复用不 new;
#   ②会话决议失败路径(跨provider配置查找失败 / 读 sessionModel 异常)不再返回 None
#     (破坏C1), 经 _default_snapshot 派生全局默认快照兜底(复用共享连接池)。
#   compliance: DRY(两失败路径共用 helper)/KISS-DIRECT/禁止backward
# 2026-09-20 - 小欧 - 三堂会审修复: resolve_session_client添加hasattr类型保护(防非ModelRef类型如dict导致AttributeError静默失效)
# 2026-09-21 - 小欧 - 修复 None 陷阱: _extract_provider_model 的 .get('provider','')/get('model','') 改为 .get() or ''；
#   _validate_model_in_list 的 .get('models',[]) 改为 .get() or []（key 存在但值为 None 时原写法返回 None）
# 2026-09-21 - 小欧 - v4.20 单源收敛: _extract_provider_model 改读结构化 ai.model_ref（删扁平 ai.provider/ai.model
#   双源，与 model_service.get_current_ref / config_helpers._update_model_ref   统一为单一真相源）
# 2026-09-25 - 小欧 - 掩盖根因修复: finally 里未转移 lease 的归还原为裸 await, 一旦归还抛错
#   会替换掉正在传播的真实失败原因(排障只看到归还错误, 看不到真因); 改为兜 try/except 记 error 后继续原路径。
#   不吞异常、不改归还语义, 只保证"真因"不被"善后失败"顶掉 — 小欧 2026-09-25
# 2026-09-25 - 小欧 - ConnectionScope连接池统一所有者: ①resolve_session_client 签名 ai_service→scope(lease 只从 scope.acquire_lease() 出, 反射摸 _shared_client 消亡); ②进门 acquire + transferred 标记 + finally 未转移归还; ③空会话走无覆盖分支派生默认快照(恒非 None); ④_default_snapshot 改传 lease 接管池引用
# 2026-09-26 - 小欧 - 密钥与地址配置整改 两处同批落地:
#   ①fetch_remote_models 探测用的 api_key 空判定改调公用 is_blank_secret()（原为
#     `(_pv_cfg.get("api_key") or "").strip() or None`，与 lifecycle/validation.py 是同一判定的第二处写法，
#     收口到 app/utils/secret_utils.py 唯一权威，行为等价：空/纯空白=未配置，语义零变化）；
#   ②fetch_remote_models 按设计返回错误分类：探测失败不再一律 HTTPException，
#     改返 (models, error_kind, status_code) 三元组 —— 调用方（model_routes.test-connection）
#     据此分「地址问题」与「key 问题」两套文案，不再把两类根因混成一句泛化报错。— 小欧 2026-09-26
# 2026-09-26 (三堂会审后修正) - 小欧 - ①[退化·已实测复现] 设计文档把 api_base 的
#   `or 本代地址` 回落无条件删除，但同 provider 时 _pv_cfg 恒为 None ⇒ api_base=None ⇒
#   会话内换同一 provider 的模型 100% 报 400。已按"是否跨 provider"分语义修复(见下方 _same_pv)。
#   ②[编辑历史位置违规+DRY] 同一事实原在文件头与函数体各写一份，已删函数体内那份。
#   ③[史实订正] 上一条②的记录称设计文档改的是 fetch_remote_models —— 该函数不在本文件
#   (在 model_service.py)，本文件真正被改的是上述 api_base 回落。
# 2026-09-26 (三堂会审后修正·四) - 小欧 - [DRY] 降级兜底收敛为唯一出口 _fallback_snapshot()：
#   原 :254(配置查找失败) 与 :312(读会话失败) 两处逐字重复"派生快照→标记→返回"，且曾因独立
#   evolve 漏加一处专属异常上抛(即设计文档要消灭的行为 B)。日志分工: 调用方只报原因(reason)，
#   _default_snapshot 统一报"降级到哪个模型"，消除两条重叠 warning。
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
# 2026-09-26 小欧 - 密钥空白判定收口到公用函数（与 lifecycle/validation.py 同一权威）
from app.utils.secret_utils import is_blank_secret


class ProviderKeyMissingError(Exception):
    """专属异常：会话跨 provider 切换、但目标 provider 未配置 api_key。

    与其它 Exception 区分：本异常是【用户可自行修复的配置问题】，不是系统故障，
    故由 stream_orchestrator 单独 catch 并转 error_type="config_error" + 人话文案，
    不让它掉进通用 router_error 兜底（见 2.5）。
    2026-09-26 小欧 - 新增
    """


class AIConfigResolver:
    
    def __init__(self, config: Optional[Config] = None):
        self._config = config or get_config()
        self._model_warning: Optional[str] = None
    
    def get_ai_config(self) -> Dict[str, Any]:
        return self._config.get("ai", {})
    
    def _extract_provider_model(self, ai_config: Dict[str, Any]) -> Tuple[str, str]:
        """提取provider和model - 小沈 2026-06-08
        2026-09-21 小欧 v4.20 单源收敛：改读结构化 ai.model_ref（删扁平 ai.provider/ai.model）"""
        ref = ai_config.get("model_ref") or {}
        if not isinstance(ref, dict):
            ref = {}
        return ref.get("provider") or "", ref.get("model") or ""
    
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
        models = provider_config.get("models") or []
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
    
    def _validate_all(self, ai_config: dict, provider: str, model: str) -> Optional[str]:
        """4 步校验链唯一权威(DRY 归一: resolve_model_ref / validate_config 复用) — 小欧 2026-09-25
        只返回 warning(无警告 None): 两处调用方均不消费 provider_config(原实现的中间变量), 故不外传(YAGNI);
        任一步不合法直接抛 ValueError(与原实现语义一致)"""
        self._validate_provider_model_not_empty(provider, model)
        self._validate_provider_exists(ai_config, provider)
        provider_config = self._get_provider_config(ai_config, provider)
        return self._validate_model_in_list(provider_config, provider, model)

    def resolve_model_ref(self) -> ModelRef:
        """直接读配置的provider和model,无效就报错 — 返回 ModelRef 结构(归一, 禁二元组拆包) — 小欧 2026-08-22
        api_base 当前无调用方需求(F7), 不在此读取; 构造服务实例时由 provider_config 补齐(lifecycle 6.6)"""
        ai_config = self.get_ai_config()
        provider, model = self._extract_provider_model(ai_config)

        warning = self._validate_all(ai_config, provider, model)
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
            warning = self._validate_all(ai_config, provider, model)
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


def _default_snapshot(ai_service, lease) -> "BaseAIService":   # 增 lease 参数, 快照接管本代池 — 小欧-2026-09-25
    """C3/C4(小欧 2026-09-20): 会话决议失败路径派生全局默认快照兜底(无条件快照)。
    resolver 失败时绝不允许返回 None 让主流程回退全局单例(破坏C1'无条件快照'),
    统一返回 ai_service.snapshot(复用其共享连接池, 快照模型=全局默认)。增 lease, 快照接管本代池。"""
    # 共享池地址改经 lease.client 公开属性(反射摸 _shared_client 消亡) — 小欧 2026-09-25
    _snap = ai_service.snapshot(shared_client=lease.client, client_lease=lease)
    logger.warning(f"[chat] 会话决议失败, 派生全局默认快照兜底: model={_snap.llm_model.model}")
    return _snap


def _fallback_snapshot(ai_service, lease, reason: str) -> "BaseAIService":
    """降级派生全局默认快照 —— resolve_session_client 降级路径唯一出口(DRY) — 小欧 2026-09-26

    reason 只报"为什么降级"；"已降级到哪个模型"由 _default_snapshot 统一记录，避免重复 warning。
    """
    logger.warning(f"[chat] {reason}")
    return _default_snapshot(ai_service, lease)


async def resolve_session_client(scope, session_id):
    """会话模型覆盖决议：返回任务私有快照(恒非 None), 同 provider 快照接管本代 lease — 小欧 2026-09-25
    # 2026-09-05 - 小健 - 自 stream_orchestrator 编排⑥(原 285-336)整块外迁 — 小健 2026-09-05
    # 签名 ai_service→scope: lease 只从 scope.acquire_lease() 出(反射摸 _shared_client 消亡);
    #   进门 acquire(ref+1) + transferred 标记 + finally 未转移归还——跨 provider 独占池不接 lease。
    """
    # 注: 本函数 2026-09-26 的改动说明(ProviderKeyMissingError 专属异常 / api_base 回落删除等)
    #   **统一记在文件头编辑历史**, 此处不重复抄写 —— 同一事实写两处, 改一处必漏另一处。
    ai_service = scope.ai_service
    lease = scope.acquire_lease()   # 进门借用本代池(ref+1); 已退休/未初始化诚实上抛(不建任务)
    transferred = False
    try:
        _ov = None
        if session_id:
            # 落库 offload 出事件循环(后端卡死修复收尾 小欧 2026-08-24)
            _ov = await db.atxn("chat", lambda conn: get_session_model(conn, session_id))
        # 2026-09-20 小欧 C1(修正): 无条件快照——无论有无覆盖都构造独立 BaseAIService(状态分离),
        #   有覆盖按原路径查目标 provider 配置; 无覆盖仅派生全局默认, snapshot 复用本代共享池 — 小欧-2026-09-25
        # 修复(小欧 2026-09-20): 添加类型保护, 防非ModelRef类型(如dict)导致AttributeError静默失效
        if _ov and hasattr(_ov, 'model') and hasattr(_ov, 'provider') and (_ov.model or _ov.provider):
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
                    # 密钥空白判定收口 - 小欧 - 2026-09-26: 密钥空白判定收口到公用函数
                    #   is_blank_secret（与 lifecycle/validation.py 同一权威，杜绝第三份不一致写法）
                    _pv_key = (None if is_blank_secret(_pv_cfg.get("api_key"))
                               else str(_pv_cfg["api_key"]).strip())
                    # 跨 provider 但目标 key 空白 => 明确报错，不再偷用全局默认 key（设计文档行为 B）。
                    # 情况 A(同 provider)不进本分支、用单例 key 属正常，严禁一并"修掉"。
                    # env 安全性: get_service_config 的 cfg 已过 _apply_env_overrides，env key 已入配置。
                    if not _pv_key:
                        raise ProviderKeyMissingError(
                            f"会话切换到 provider {_ov.provider}，但该 provider 未配置 api_key，"
                            f"请先在设置页填写，或设置环境变量 {_ov.provider.upper()}_API_KEY"
                        )
                    # model_params 解析复用 service.parse_model_params(DRY 唯一权威, 与全局实例同逻辑)
                    from app.services.lifecycle.service import parse_model_params
                    _pv_ebp, _pv_ctx = parse_model_params(_pv_cfg, _ov.model or "")
                except ProviderKeyMissingError:
                    raise   # 专属异常必须冒泡: 被下方 except Exception 降级即等于用全局 key 继续跑
                except Exception as _pv_e:
                    logger.warning(f"[chat] 按 provider 查配置失败({_ov.provider}): {_pv_e}, 放弃会话模型覆盖")
                    _pv_cfg = None
                    _pv_key = None
                    _pv_ebp = None
                    _pv_ctx = None
            if _pv_cfg is None and _ov.provider and _ov.provider != ai_service.llm_model.provider:
                _snap = _fallback_snapshot(
                    ai_service, lease,
                    f"会话模型覆盖已跳过(配置查找失败), 使用全局默认模型快照: "
                    f"provider={ai_service.llm_model.provider}, model={ai_service.llm_model.model}")
                transferred = True   # 默认快照接管 lease(close 归还) — 小欧-2026-09-25
                return _snap
            # 同 provider 时 _pv_cfg 恒为 None，api_base 必须沿用本代地址（否则会话内换模型全报 400，
            # 退化史见文件头「三堂会审后修正」①）；跨 provider 才留空由 LLMClient 报错。
            _same_pv = (not _ov.provider or _ov.provider == ai_service.llm_model.provider)
            override_ref = ModelRef(
                provider=_ov.provider or ai_service.llm_model.provider,
                model=_ov.model or ai_service.llm_model.model,
                api_base=(
                    ai_service.llm_model.api_base            # 同 provider: 沿用本代地址(原行为, 不可删)
                    if _same_pv
                    else (_pv_cfg or {}).get("api_base")     # 跨 provider: 留空即报错, 不用别人的地址
                ),
                display_name=_ov.display_name or ai_service.llm_model.display_name,
            )
            session_client = ai_service.snapshot(
                override_ref,
                api_key=_pv_key,
                extra_body_params=_pv_ebp,
                context_limit=_pv_ctx,
                shared_client=(lease.client if _same_pv else None),  # 同 provider 复用本代共享池; 跨 provider 独占新池 — 小欧-2026-09-25
                client_lease=(lease if _same_pv else None),  # lease 与池成对: 同 provider 接管(close 归还), 跨 provider 不接 — 小欧-2026-09-25
            )
            if _same_pv:
                transferred = True   # 跨 provider 不转移 → finally 归还 — 小欧-2026-09-25
            # 2026-09-01 小欧: 同步 _task_llm_model 为生效快照模型, 使 react_cycle 日志/telemetry
            # 显示真实生效模型(而非全局 agnes), 与 TASK_START 显示实际生效模型同一精神
            logger.info(f"[chat] L2 sessionModel 已生效(独立客户端快照): session={session_id}, "
                        f"provider={session_client.llm_model.provider}, model={session_client.llm_model.model}")
            return session_client
        # ---- 无条件快照分支(无覆盖/空会话): 派生全局默认快照 + 接管本代共享池 lease ----
        logger.info(f"[chat] C1 无覆盖会话快照(session={session_id})")
        _snap = ai_service.snapshot(shared_client=lease.client, client_lease=lease)   # 构造期注入共享池+成对 lease — 小欧-2026-09-25
        transferred = True
        return _snap
    except ProviderKeyMissingError:
        # 本外层 except 若接住专属异常，会降级为"用全局 key 继续跑"= 设计文档行为 B，
        # 且前端收不到 config_error。已实测复现，故与内层同模式原样上抛（finally 归还照常）。
        raise
    except Exception as _ov_e:
        # 修复(小欧 2026-09-20): 异常不再返回 None(破坏一致性), 改派生全局默认快照 — 小欧-2026-09-20
        _snap = _fallback_snapshot(ai_service, lease, f"读会话sessionModel失败(session={session_id}): {_ov_e}")
        transferred = True
        return _snap
    finally:
        # 未转移的 lease 归还(跨 provider/构造失败), 防 ref 永久悬挂 — 小欧-2026-09-25
        if not transferred:
            # 小欧-2026-09-25: 归还失败不得掩盖在途异常(原为裸 await, release 抛错会替换掉真正的失败原因,
            #   排障时只看到归还错误而看不到真因); 故兜 try/except 记 error 后继续原路径
            try:
                await lease.release()
            except Exception as _rel_e:
                logger.error(
                    f"[chat] 未转移 lease 归还失败(session={session_id}, 该代 ref 将悬挂): {_rel_e}",
                    exc_info=True,
                )
