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
# 2026-09-20 - 小欧 - P0+P1+C-3/C-4(13.1+13.2无条件快照共享连接池 + RED-C-3/C-4):
#   ①P0+P1: snapshot 构造注入 shared_client(全局共享连接池引用), 快照复用不 new;
#   ②C-3/C-4: 会话决议失败路径(跨provider配置查找失败 / 读 sessionModel 异常)不再返回 None
#     (破坏C1), 经 _default_snapshot 派生全局默认快照兜底(复用共享连接池)。
#   compliance: DRY(两失败路径共用 helper)/KISS-DIRECT/禁止backward
# 2026-09-20 - 小欧 - 三堂会审BUG-12修复: resolve_session_client添加hasattr类型保护(防非ModelRef类型如dict导致AttributeError静默失效)
# 2026-09-21 - 小欧 - 修复 None 陷阱: _extract_provider_model 的 .get('provider','')/get('model','') 改为 .get() or ''；
#   _validate_model_in_list 的 .get('models',[]) 改为 .get() or []（key 存在但值为 None 时原写法返回 None）
# 2026-09-21 - 小欧 - v4.20 单源收敛: _extract_provider_model 改读结构化 ai.model_ref（删扁平 ai.provider/ai.model
#   双源，与 model_service.get_current_ref / config_helpers._update_model_ref   统一为单一真相源）
# 2026-09-25 - 小欧 - [70] v1.12 修掩盖根因: finally 里未转移 lease 的归还原为裸 await, 一旦归还抛错
#   会替换掉正在传播的真实失败原因(排障只看到归还错误, 看不到真因); 改为兜 try/except 记 error 后继续原路径。
#   不吞异常、不改归还语义, 只保证"真因"不被"善后失败"顶掉 — 小欧 2026-09-25
# 2026-09-25 - 小欧 - [70] ConnectionScope连接池统一所有者: ①resolve_session_client 签名 ai_service→scope(lease 只从 scope.acquire_lease() 出, 反射摸 _shared_client 消亡); ②进门 acquire + transferred 标记 + finally 未转移归还; ③空会话走无覆盖分支派生默认快照(恒非 None); ④_default_snapshot 改传 lease 接管池引用
# 2026-09-26 - 小欧 - [72]第二章(2.4 配套·DRY) + 第十章(10.3) 两处同批落地:
#   ①fetch_remote_models 探测用的 api_key 空判定改调公用 is_blank_secret()（原为
#     `(_pv_cfg.get("api_key") or "").strip() or None`，与 lifecycle/validation.py 是同一判定的第二处写法，
#     收口到 app/utils/secret_utils.py 唯一权威，行为等价：空/纯空白=未配置，语义零变化）；
#   ②fetch_remote_models 按 [72]第十章(10.3) 返回错误分类：探测失败不再一律 HTTPException，
#     改返 (models, error_kind, status_code) 三元组 —— 调用方（model_routes.test-connection）
#     据此分「地址问题」与「key 问题」两套文案，不再把两类根因混成一句泛化报错。— 小欧 2026-09-26
# 2026-09-26 (三堂会审后修正) - 小欧 - 本文件 2 处已改:
#   ①[严重功能退化 · 修A坏B] 见下方 resolve_session_client 构造 ModelRef 处的详注(已实测复现):
#     第八章把 api_base 的 `or ai_service.llm_model.api_base` 回落**无条件**删除，但同 provider 时
#     _pv_cfg 恒为 None ⇒ api_base=None ⇒ LLMClient 抛 400「URL 为空」⇒
#     **会话内换同一 provider 的模型 100% 失败**。已按"是否跨 provider"分两种语义修复。
#   ②[编辑历史位置违规 + DRY] resolve_session_client 的 09-26 说明原被塞进**函数体内注释**，
#     而文件头已有同一条目 —— 同一事实两处写、改一处必漏另一处。已删函数体内那份，只留文件头。
#   ③[历史记录事实错误] 上一条 ② 的记录本身有两处不实，现更正: fetch_remote_models **不在本文件**
#     (它在 model_service.py —— 本文件只经 get_ai_config_resolver() 间接读配置)，且它返回的是
#     **dict**(带 status_code/category 键)不是三元组。照原记录去找会找不到函数、对不上返回形状。
#     第八章真正改在本文件的是 resolve_session_client 的 api_base 回落(见上方 ①)。
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
# 2026-09-26 小欧 - [72]第二章(2.4 配套·DRY): 密钥空白判定收口到公用函数（与 lifecycle/validation.py 同一权威）
from app.utils.secret_utils import is_blank_secret


class ProviderKeyMissingError(Exception):
    """第二章 2.4 专属异常：会话跨 provider 切换、但目标 provider 未配置 api_key。

    与其它 Exception 区分：本异常是【用户可自行修复的配置问题】，不是系统故障，
    故由 stream_orchestrator 单独 catch 并转 error_type="config_error" + 人话文案，
    不让它掉进通用 router_error 兜底（见 2.5）。
    2026-09-26 小欧 - [72]第二章(2.4)(2.5) 新增
    """


class AIConfigResolver:
    
    def __init__(self, config: Optional[Config] = None):
        self._config = config or get_config()
        self._model_warning: Optional[str] = None
    
    def get_ai_config(self) -> Dict[str, Any]:
        return self._config.get("ai", {})
    
    def _extract_provider_model(self, ai_config: Dict[str, Any]) -> Tuple[str, str]:
        """提取provider和model - 小沈 2026-06-08
        2026-09-21 小欧 v4.20 单源收敛：改读结构化 ai.model_ref（删扁平 ai.provider/ai.model，见[54]）"""
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


def _default_snapshot(ai_service, lease) -> "BaseAIService":   # [70] 增 lease 参数, 快照接管本代池 — 小欧-2026-09-25
    """C3/C4(小欧 2026-09-20): 会话决议失败路径派生全局默认快照兜底(无条件快照)。
    resolver 失败时绝不允许返回 None 让主流程回退全局单例(破坏C1'无条件快照'),
    统一返回 ai_service.snapshot(复用其共享连接池, 快照模型=全局默认)。[70] 增 lease, 快照接管本代池。"""
    # [70] 共享池地址改经 lease.client 公开属性(反射摸 _shared_client 消亡) — 小欧 2026-09-25
    _snap = ai_service.snapshot(shared_client=lease.client, client_lease=lease)
    logger.warning(f"[chat] 会话决议失败, 派生全局默认快照兜底: model={_snap.llm_model.model}")
    return _snap


async def resolve_session_client(scope, session_id):
    """会话模型覆盖决议：返回任务私有快照(恒非 None), 同 provider 快照接管本代 lease — [70] 小欧 2026-09-25
    # 2026-09-05 - 小健 - 自 stream_orchestrator 编排⑥(原 285-336)整块外迁 — 小健 2026-09-05
    # [70] 签名 ai_service→scope: lease 只从 scope.acquire_lease() 出(反射摸 _shared_client 消亡);
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
        #   有覆盖按原路径查目标 provider 配置; 无覆盖仅派生全局默认, snapshot 复用本代共享池 — [70] 小欧-2026-09-25
        # BUG-12修复(小欧 2026-09-20): 添加类型保护, 防非ModelRef类型(如dict)导致AttributeError静默失效
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
                    # [72]第二章(2.4 配套·DRY) - 小欧 - 2026-09-26: 密钥空白判定收口到公用函数
                    #   is_blank_secret（与 lifecycle/validation.py 同一权威，杜绝第三份不一致写法）
                    _pv_key = (None if is_blank_secret(_pv_cfg.get("api_key"))
                               else str(_pv_cfg["api_key"]).strip())
                    # [72]第二章(2.4) - 小欧 - 2026-09-26: 情况 B 判定 —— 跨 provider 且目标 provider
                    #   配置取到、但 api_key 空白 => 明确报错(带 provider 名 + env 变量名)，不再偷用全局默认 key。
                    #   情况 A(同 provider)不经过本分支(:189 if 条件), 行为原样不动, 严禁一并"修掉"。
                    #   env 安全性: get_service_config 返回的 cfg 已过 config.py 的 _apply_env_overrides,
                    #   env 提供的 key 已写入配置 -> 用 {NAME}_API_KEY 的 provider 不会被误判为"未配置"。
                    if not _pv_key:
                        raise ProviderKeyMissingError(
                            f"会话切换到 provider {_ov.provider}，但该 provider 未配置 api_key，"
                            f"请先在设置页填写，或设置环境变量 {_ov.provider.upper()}_API_KEY"
                        )
                    # model_params 解析复用 service.parse_model_params(DRY 唯一权威, 与全局实例同逻辑)
                    from app.services.lifecycle.service import parse_model_params
                    _pv_ebp, _pv_ctx = parse_model_params(_pv_cfg, _ov.model or "")
                except ProviderKeyMissingError:
                    # [72]第二章(2.4) 小欧 2026-09-26: 专属异常向上冒泡, 不被下方 except Exception
                    #   降级为"放弃会话模型覆盖"(那会用全局默认快照继续跑 = 恰恰是要消灭的行为 B)
                    raise
                except Exception as _pv_e:
                    logger.warning(f"[chat] 按 provider 查配置失败({_ov.provider}): {_pv_e}, 放弃会话模型覆盖")
                    _pv_cfg = None
                    _pv_key = None
                    _pv_ebp = None
                    _pv_ctx = None
            if _pv_cfg is None and _ov.provider and _ov.provider != ai_service.llm_model.provider:
                logger.warning(f"[chat] 会话模型覆盖已跳过(配置查找失败), 使用全局默认模型快照: provider={ai_service.llm_model.provider}, model={ai_service.llm_model.model}")
                _snap = _default_snapshot(ai_service, lease)  # C-3(小欧 2026-09-20): 配置失败不再返回 None(破坏C1), 改派生全局默认快照 — 小欧-2026-09-20
                transferred = True   # [70] 默认快照接管 lease(close 归还) — 小欧-2026-09-25
                return _snap
            # 2026-09-26 - 小欧 - [72]三堂会审后修正(修严重功能退化): 跨 provider 判定**提前**到构造 ModelRef 之前。
            #   原改动把 api_base 的 `or ai_service.llm_model.api_base` 回落**无条件**删掉了,
            #   但"该不该用全局地址"取决于是否跨 provider, 而原代码在**同 provider 时 _pv_cfg 恒为 None**
            #   (:219 的 if 不成立 → 不查配置 → _pv_cfg 保持 None), 于是 `(_pv_cfg or {}).get("api_base")`
            #   恒为 None。
            #   实测复现(非理论): LLMClient(ModelRef(api_base=None), 'sk') 直接抛
            #   HTTPException 400「provider deepseek 的 URL 为空」。
            #   ⇒ 用户在**同一 provider 内切换模型**(只换 model 不换 provider, 会话覆盖的常见用法)
            #     100% 报 400、功能完全不可用。这是本轮 [72]第八章改动引入的退化, 属"修 A 坏 B"。
            #   正确语义分两种情况(8.5-4 只针对"跨 provider 不得用别人的地址", 未要求同 provider 也放弃):
            #     · 跨 provider: 留空即由 LLMClient 报错(空就是空不瞎兜底) —— 8.5-4 的本意;
            #     · 同 provider / 无 provider 覆盖: 本代地址就是该 provider 自己的地址, 必须沿用,
            #       否则会话内换模型全废。
            _same_pv = (not _ov.provider or _ov.provider == ai_service.llm_model.provider)
            override_ref = ModelRef(
                provider=_ov.provider or ai_service.llm_model.provider,
                model=_ov.model or ai_service.llm_model.model,
                api_base=(
                    ai_service.llm_model.api_base            # 同 provider: 沿用本代地址(原行为, 不可删)
                    if _same_pv
                    else (_pv_cfg or {}).get("api_base")     # 跨 provider: 留空即报错(8.5-4), 不用别人的地址
                ),
                display_name=_ov.display_name or ai_service.llm_model.display_name,
            )
            session_client = ai_service.snapshot(
                override_ref,
                api_key=_pv_key,
                extra_body_params=_pv_ebp,
                context_limit=_pv_ctx,
                shared_client=(lease.client if _same_pv else None),  # [70] 同 provider 复用本代共享池; 跨 provider 独占新池 — 小欧-2026-09-25
                client_lease=(lease if _same_pv else None),  # [70] lease 与池成对: 同 provider 接管(close 归还), 跨 provider 不接 — 小欧-2026-09-25
            )
            if _same_pv:
                transferred = True   # [70] 跨 provider 不转移 → finally 归还 — 小欧-2026-09-25
            # 2026-09-01 小欧: 同步 _task_llm_model 为生效快照模型, 使 react_cycle 日志/telemetry
            # 显示真实生效模型(而非全局 agnes), 与 TASK_START 显示实际生效模型同一精神
            logger.info(f"[chat] L2 sessionModel 已生效(独立客户端快照): session={session_id}, "
                        f"provider={session_client.llm_model.provider}, model={session_client.llm_model.model}")
            return session_client
        # ---- 无条件快照分支(无覆盖/空会话): 派生全局默认快照 + 接管本代共享池 lease ----
        logger.info(f"[chat] C1 无覆盖会话快照(session={session_id})")
        _snap = ai_service.snapshot(shared_client=lease.client, client_lease=lease)   # [70] 构造期注入共享池+成对 lease — 小欧-2026-09-25
        transferred = True
        return _snap
    except ProviderKeyMissingError:
        # 2026-09-26 - 小欧 - [72]三堂会审后修正（修设计被架空）：
        #   内层的 `except ProviderKeyMissingError: raise` 只防住了内层 `except Exception`，
        #   但本外层 `except Exception`（读会话失败兜底）会把好不容易冒泡出来的专属异常**再接住**，
        #   降级走 `_default_snapshot` 全局默认快照 + 只记一条 warning —— 即用全局 key 继续跑，
        #   恰恰是 [72]第二章要消灭的行为 B。且前端永远收不到 `config_error`（2.5 专属 catch 成摆设）。
        #   已实测复现：跨 provider 空白 key 时无 config_error、静默用全局快照。
        #   修法与内层同模式：在本 except 之前加专属分支原样上抛；finally 的 lease 归还照常执行。
        raise
    except Exception as _ov_e:
        logger.warning(f"[chat] 读会话sessionModel失败(session={session_id}): {_ov_e}")
        _snap = _default_snapshot(ai_service, lease)  # C-4(小欧 2026-09-20): 异常不再返回 None(破坏C1), 改派生全局默认快照 — 小欧-2026-09-20
        transferred = True
        return _snap
    finally:
        # [70] 未转移的 lease 归还(跨 provider/构造失败), 防 ref 永久悬挂 — 小欧-2026-09-25
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
