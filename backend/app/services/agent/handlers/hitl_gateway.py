# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 新建(文档[6]5.1, 对应清单#1): ConfirmSpec + hitl_confirm + _resolve_trust_path/_desensitize/_resolve_timeouts
#   网关内部固定顺序 publish(paused)→wait→publish(resumed)→单点resolve收口; 复用hitl_confirmation三原语不重写等待/超时/取消
# 2026-09-06 小欧 步骤2落盘(test_path1_step2_hitl_gateway.py T2红→绿): 落点handlers/hitl_gateway.py, 与调用方同目录(handlers→task单向依赖防环);
#   会审minor修正: _resolve_timeouts mode非法值显式ValueError校验
# 2026-09-06 小欧 POT-001优化(老陈核查定案): _resolve_trust_path standalone 曾用 for 显式循环——6键回落整体
#   在问题A修复(文档[44]5.5)时随函数一并删除, hitl_confirm 直接调主链 extract_trust_path(KISS 无透传); 本条为历史留痕
# 2026-09-16 小欧 缺陷还原(5.5伴随): _desensitize 回退同步 def(HttpRuntimeWarning: coroutine never awaited 探出,
#   内部纯同步无await, async 声明致 MetaStep(params=coroutine)入队前失真; 与 HEAD def 原语义一致) — 小欧-2026-09-16
# 2026-09-16 老陈 - 后端参数摘要[43]11.6-T4: 新增_summarize_params(主键path+长值截断80) + 组装行包裹_desensitize收口 - 老陈-2026-09-16
"""HITL确认唯一入口。复用hitl_confirmation三原语，不重写等待/超时/取消。"""
from dataclasses import dataclass
from typing import Optional
from app.logger import logger
from app.services.agent.steps import MetaStep
from app.services.agent.status_table import set_status, AgentStatus  # AgentStatus真实位置status_table行19 — 小健-2026-09-05


@dataclass
class ConfirmSpec:
    """确认规格（与4.2同形，属性访问；auto_confirm默认None由mode推导） — 小健-2026-09-05"""
    mode: str                    # "hitl" | "bypass"
    tool_name: str
    params: Optional[dict] = None
    path: Optional[str] = None
    content: str = ""
    safety_level: str = ""
    auto_confirm: Optional[bool] = None


def _desensitize(params) -> dict:
    """纯同步脱敏(HITL限制: 无await原语; 调用处非同await上下文, 保持def而非async — 小欧-2026-09-16规范还原)"""
    from app.tools.tool_constants import SENSITIVE_FIELDS      # 延迟import防环（真实位置，sandbox_gate行66同源 — 小健-2026-09-05）
    return {k: v for k, v in (params or {}).items() if k not in SENSITIVE_FIELDS}


def _summarize_params(tool_name: str, params: dict) -> dict:
    """HITL弹窗参数摘要: 主键(path类extract_trust_path权威)优先展示 + 长值smart_truncate_text兜底截断 — 小欧-2026-09-16
    复现[43]11.6 T4设计: 弹窗只显核心参数(主键path), 长值折叠防弹窗超高;
    脱敏仍由组装行 _desensitize 统一收口(本函数不重复脱敏)。"""
    from app.utils.text_utils import smart_truncate_text  # 延迟import防环(与_desensitize同款; FUNCTIONS.md:84已登记) — 小欧-2026-09-16
    from app.tools.trust import extract_trust_path        # 延迟import防环(主键权威) — 老陈-2026-09-16
    _all: dict = {k: v for k, v in (params or {}).items()}
    _path = extract_trust_path(tool_name, params)          # 复用trust.py:69主键权威, 不重写
    _out: dict = {}
    if _path:
        _out["path"] = _path
    for _k, _v in _all.items():
        if _k in ("path",) or _k in _out:
            continue                                        # path已由主键摘出, 防重复展示
        if isinstance(_v, str) and len(_v) > 80:            # 长值→顶格截断防弹窗超高(复用公用函数)
            _out[_k] = smart_truncate_text(_v, 80)
        else:
            _out[_k] = _v
    return _out


async def _resolve_timeouts(mode):
    """返回 (backend_timeout, confirm_timeout) 二元组（调用处双解包 — 小健-2026-09-05）。
    点分扁平键（与三处同源，禁嵌套get("security")取法）+ 分mode公式：
    hitl→security.hitl_timeout兜底HITL_TIMEOUT，confirm=max(MIN, backend-HITL_CONFIRM_LEAD)；
    bypass→security.auto_confirm_delay兜底10.0，backend=max(MIN+LEAD, delay)，confirm=backend-BYPASS_AUTO_LEAD。
     （见safety_gate行79/85/87/112、sandbox_gate行90-92；四常量均在app.constants）。"""
    from app.config import get_config                            # 延迟import防环
    from app.constants import HITL_TIMEOUT, HITL_CONFIRM_LEAD, HITL_MIN_CONFIRM_TIMEOUT, BYPASS_AUTO_LEAD
    if mode not in ("hitl", "bypass"):
        raise ValueError(f"[hitl_gateway] 非法确认模式: {mode!r} (须为 hitl|bypass)")   # 会审minor - 小欧 2026-09-06
    cfg = get_config()
    if mode == "hitl":
        _bt = int(float(cfg.get("security.hitl_timeout", HITL_TIMEOUT)))
        return _bt, max(HITL_MIN_CONFIRM_TIMEOUT, _bt - HITL_CONFIRM_LEAD)
    _bt = max(HITL_MIN_CONFIRM_TIMEOUT + BYPASS_AUTO_LEAD,
              int(float(cfg.get("security.auto_confirm_delay", 10.0))))
    return _bt, _bt - BYPASS_AUTO_LEAD


async def hitl_confirm(agent, spec: ConfirmSpec, publish):
    """spec属性访问（与4.2同形）→verdict。网关内统一：超时计算/trust_path/脱敏/SUSPENDED→wait→EXECUTING。"""
    from app.services.task.hitl_confirmation import (            # 延迟import防环
        create_confirmation, wait_for_confirmation_result, resolve_confirmation)
    from app.tools.trust import extract_trust_path    # 延迟import防环（原 _resolve_trust_path 内联, KISS 无透传函数 — 小欧-2026-09-16）
    _path = spec.path or extract_trust_path(spec.tool_name, spec.params)
    confirm_id = await create_confirmation(agent.task_id, spec.tool_name, _path)
    _bt, _ct = await _resolve_timeouts(spec.mode)
    _auto = spec.auto_confirm if spec.auto_confirm is not None else (spec.mode == "bypass")
    paused = agent._step_emitter.emit(MetaStep(step=agent.llm_call_count, type="paused",
        content=spec.content, confirm_id=confirm_id, tool_name=spec.tool_name,
        params=_desensitize(_summarize_params(spec.tool_name, spec.params)),  # [43]11.6-T4 参数摘要(主键path优先+长值截断)防弹窗超高 — 小健-2026-09-16
        safety_level=spec.safety_level,
        severity="attention", trust_path=_path, auto_confirm=_auto,
        confirm_timeout=_ct, backend_timeout=_bt))
    set_status(agent, AgentStatus.SUSPENDED, f"等待用户确认: {spec.tool_name}")
    await publish(paused.to_dict())
    auth = await wait_for_confirmation_result(confirm_id, timeout=_bt)
    set_status(agent, AgentStatus.EXECUTING, "用户裁决完成")
    # 裁决统一收口：confirmed/expired/rejected 三路径共用一处注销，防无人裁决(超时/拒绝)时 confirm_id pending 泄漏；
    #   重复 resolve 幂等仅告警，Bug-25"confirm_id 必收口"语义 — 老陈 2026-09-06 定案补入
    try:
        await resolve_confirmation(confirm_id,
                                   confirmed=bool(auth.get("confirmed")),
                                   trust_session=bool(auth.get("trust_session", False)))
    except Exception as _e:
        logger.error(f"[hitl_gateway] resolve_confirmation({confirm_id})收口失败: {_e!r}")   # 不阻断 resumed/verdict
    # resumed配对条件同4.2（confirmed必发；bypass+expired亦发，真HITL expired/rejected不发）。— 小健-2026-09-05
    if auth.get("confirmed") or (spec.mode == "bypass" and auth.get("expired")):
        resumed = agent._step_emitter.emit(MetaStep(step=agent.llm_call_count, type="resumed",
            content=f"已确认执行: {spec.tool_name}", severity="info", confirm_id=confirm_id))
        await publish(resumed.to_dict())
    return {"confirmed": bool(auth.get("confirmed")), "expired": bool(auth.get("expired")),
            "trust_session": bool(auth.get("trust_session", False)), "confirm_id": confirm_id}