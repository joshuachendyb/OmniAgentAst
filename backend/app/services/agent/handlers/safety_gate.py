# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 新建(10.4第二阶段提一): check_safety_and_confirm 自 action_handler.py 整搬(逐字复制不重写),
#   随迁import(trust/safety/hitl/sandbox/status/steps/constants); 函数内延迟import原样保留;
#   本文件=安全检查+HITL确认门禁(安全+HITL+沙箱三合一), 与 sandbox_gate 同族目录。
"""safety_gate — 安全检查+HITL确认门禁 — 小健 2026-09-05

自 action_handler 拆出(八章9.3): check_safety_and_confirm 整函数, 门禁=安全+HITL+沙箱三合一。
"""
from typing import List, Dict

from app.logger import logger
from app.constants import HITL_TIMEOUT, HITL_CONFIRM_LEAD, BYPASS_AUTO_LEAD, HITL_MIN_CONFIRM_TIMEOUT  # v1.5.13(2026-09-02 小欧): 后端唯一计时权威前后端计时关联; 2026-09-03 小欧/北京老陈: 前端倒计时最小值改常量3(改前硬编码5)
from app.services.agent.steps import MetaStep
from app.services.agent.status_table import AgentStatus, set_status
from app.tools.tool_constants import SENSITIVE_FIELDS as _SENSITIVE_FIELDS
from app.tools.trust import extract_trust_path as _extract_trust_path
from app.services.agent.handlers.sandbox_gate import run_sandbox_gate

__all__ = ["check_safety_and_confirm"]

async def check_safety_and_confirm(agent, all_calls: List[Dict], step: int, fc_context: Dict = None, _out: list = None, _denied_out: list = None):
        """安全检查+HITL确认 — async generator: MetaStep先yield给前端,再等确认 — 小沈 2026-06-10

        拒绝/拦截是可恢复的(符合人类认知: 拒绝≠失败), 不置终态FAILED:
        - 把"工具被拒绝/拦截"作为 observation 写进LLM历史(_add_denial_feedback), 让LLM换方案;
        - 循环回 THINKING 由主循环 EXECUTING→THINKING 处理;
        - 仅当同类拒绝累计>=3次才由 _dispatch_handler 置 FAILED。 — 小欧 2026-07-13
        # 2026-07-18 小欧 #11+#12 fix: 超时/拒绝分流; 拒绝不终止整批, 收集_denied后继续检查剩余工具,
        #   最终只执行通过的call(通过_out返回过滤后的call列表)
        # 2026-08-11 小欧 fix D2: _denied从2元组(tool_name,reason)扩展为3元组(tool_name,reason,call),
        #   _out过滤从按tool_name改按id(call)对象精确标识(同批同名工具1个被拒不再误杀);
        #   反馈推迟到调用方build_observation之后(_denied_out回传), 由_add_denial_feedback精确到call写,
        #   消除"会执行的同名工具被误标被拦截"与"assistant双重写入"的矛盾
        """
        from app.safety.tool_safety_checker import get_tool_safety_checker
        from app.services.task.hitl_confirmation import create_confirmation, wait_for_confirmation_result, resolve_confirmation
        from app.tools.trust import resolve_skip
        safety_checker = get_tool_safety_checker()

        _denied = []
        for call in all_calls:
            _cn = call.get("tool_name", "?")
            _cp = call.get("tool_params", {})

            # 会话信任预查 — 调用 trust.resolve_skip 独立函数 — 小健 2026-09-04
            _skip = await resolve_skip(agent.task_id, _cn, _cp)

            safety_result = safety_checker.check_before_execute(_cn, _cp, skip_confirmation=_skip)

            # v1.25 M3(设计文档 3.2.3): 沙箱预检闸门 — 逻辑已拆分至 sandbox_gate.sandbox_precheck/sandbox_resolve
            # (2026-08-25 合规重构: 去嵌套闭包隐式耦合, Agent编排层落点, 三处汇合点共用, 每 call 恰好预检一次不重复)

            if safety_result.blocked:
                # 2026-08-28 小欧 yield日志审计: 拦截决策日志(SRP)
                logger.warning(f"[action] step={step} blocked: tool={_cn} reason={safety_result.message}")
                yield agent._step_emitter.emit(MetaStep(
                    step=step, type="error", content=safety_result.message, error_type="blocked", severity="warn"
                ))
                _denied.append((_cn, f"被安全策略拦截: {safety_result.message}", call))
                continue  # was: return  — 小欧 2026-07-18 #12 fix

            if safety_result.requires_confirmation:
                desensitized_params = {k: v for k, v in _cp.items()
                                       if k not in _SENSITIVE_FIELDS}

                confirm_id = await create_confirmation(agent.task_id, _cn, _extract_trust_path(_cn, _cp))  # v1.5: path 透传供 tool+path 落库 — 小欧 2026-09-02

                # 2026-08-28 小欧 yield日志审计: 等待确认决策日志(SRP)
                logger.info(f"[action] step={step} paused: tool={_cn} confirm_id={confirm_id}")
                # v1.5.13(老陈三审定案: 后端唯一计时权威 + 前端倒计时=后端窗口−提前量)
                #   真HITL: backend_timeout=HITL_TIMEOUT(120) / confirm_timeout=120-HITL_CONFIRM_LEAD(10)=110;
                #   bypass: backend_timeout=security.auto_confirm_delay(默认10) / confirm_timeout=10-BYPASS_AUTO_LEAD(2)=8
                _bypass = bool(getattr(safety_result, "auto_confirm", False))
                if _bypass:
                    from app.config import get_config as _get_cfg
                    # 对应 config.yaml security.auto_confirm_delay(默认10, 前端倒计时=此值−BYPASS_AUTO_LEAD即8s); 未配置兜底用 10.0 — 小欧-2026-09-03
                    # 2026-09-03 小沈 缺陷2修复: 钳制≥HITL_MIN_CONFIRM_TIMEOUT+BYPASS_AUTO_LEAD, 确保confirm_timeout+S1差≥BYPASS_AUTO_LEAD — 小沈-2026-09-03
                    _backend_timeout = max(HITL_MIN_CONFIRM_TIMEOUT + BYPASS_AUTO_LEAD, int(float(_get_cfg().get("security.auto_confirm_delay", 10.0))))
                    # 2026-09-03 小欧/北京老陈: 0窗钳制≥3s(改前5→常量3)，避免max(0,bt-LEAD)=0致0秒窗口瞬间消失
                    _confirm_timeout = max(HITL_MIN_CONFIRM_TIMEOUT, _backend_timeout - BYPASS_AUTO_LEAD)
                else:
                    from app.config import get_config as _get_cfg
                    # 对应 config.yaml security.hitl_timeout(真HITL后端确认窗口,默认120); 未配置兜底用常量 HITL_TIMEOUT=120 — 小欧 2026-09-03
                    _backend_timeout = int(float(_get_cfg().get("security.hitl_timeout", HITL_TIMEOUT)))
                    # 2026-09-03 小欧/北京老陈: 0窗钳制≥3s(改前5→常量3)
                    _confirm_timeout = max(HITL_MIN_CONFIRM_TIMEOUT, _backend_timeout - HITL_CONFIRM_LEAD)
                _tp = _extract_trust_path(_cn, _cp)  # v1.5.3: trust_path 透传
                yield agent._step_emitter.emit(MetaStep(
                    step=step,
                    type="paused",
                    content=f"需要用户确认工具执行: {_cn}",
                    confirm_id=confirm_id,
                    tool_name=_cn,
                    params=desensitized_params,
                    safety_level=safety_result.safety_level,
                    severity="attention",
                    trust_path=_tp,
                    auto_confirm=_bypass,
                    confirm_timeout=_confirm_timeout,
                    backend_timeout=_backend_timeout,
                ))

                if safety_result.auto_confirm:
                    # v1.5.13(2026-09-02 小欧, 5.7.1 bypass 自动代发): bypass 从"立即resolve"改为"等前端确认消息(S1窗口)"
                    #   前端confirm_timeout到0自动代发confirm → resolve_confirmation → wait收到即走确认流程;
                    #   前端未发(无浏览器/崩溃) → S1超时 → expired → bypass 兜底放行
                    from app.services.task.hitl_confirmation import wait_for_confirmation_result as _wait_confirm
                    from app.config import get_config as _get_cfg
                    # 对应 config.yaml security.auto_confirm_delay(S1后端等待窗口=backend_timeout值,默认10); 未配置兜底 10.0 — 小欧-2026-09-03
                    # 2026-09-03 小沈 缺陷2修复: 与上方同源钳制, 确保S1=backend_timeout — 小沈-2026-09-03
                    _s1 = float(max(HITL_MIN_CONFIRM_TIMEOUT + BYPASS_AUTO_LEAD, int(float(_get_cfg().get("security.auto_confirm_delay", 10.0)))))
                    # 2026-09-03 小欧/北京老陈: bypass S1窗口开始补日志
                    logger.info(f"[action] bypass S1窗口开始: confirm_id={confirm_id}, S1={_s1}s, tool={_cn}")
                    _auth_result = await _wait_confirm(confirm_id, timeout=int(_s1 if _s1 > 0 else 0)) if _s1 > 0 else {"confirmed": True}
                    # 2026-09-03 小欧/北京老陈: bypass S1结果补日志
                    logger.info(f"[action] bypass S1结果: confirm_id={confirm_id}, expired={_auth_result.get('expired')}, confirmed={_auth_result.get('confirmed')}")
                    # 2026-09-03 小欧 P0-1: S1已expired则不再二次resolve(已pop死码)，仅confirmed分支需resolve
                    if _auth_result.get("expired"):
                        _bypass_confirmed = True
                    else:
                        _bypass_confirmed = bool(_auth_result.get("confirmed", False))
                        try:
                            # 2026-09-03 小欧 Bug-25: grant_temp_auth 包 try/finally, 授权异常不跳过 resolve_confirmation,
                            #   confirm_id 必被 resolve 收口, 前端 Modal 不泄漏挂到后端超时; 授权失败仅告警不改安全意图
                            if getattr(safety_result, "auth_path", None):
                                from app.tools.security.temp_auth import grant_temp_auth
                                grant_temp_auth(safety_result.auth_path, recursive=True)
                        except Exception as e:
                            logger.warning(f"[action] grant_temp_auth失败仍放行: {e!r}")
                        finally:
                            await resolve_confirmation(confirm_id, confirmed=_bypass_confirmed, trust_session=False)
                    set_status(agent, AgentStatus.EXECUTING, "安全策略自动确认工具执行")
                    # v1.25 M3 插入点①: auto_confirm 汇合路径 — 沙箱预检最后闸门(统一入口)
                    # 2026-09-02 小欧 BUG-001: resumed须在sandbox通过后发(被拒已continue不发),
                    #   否则无paired paused→resumed 前端badge卡running; 语义=真正恢复执行
                    # 2026-09-04 小健 DRY: 三处重复调用→统一入口 run_sandbox_gate
                    # 2026-09-04 小健 回归修复: 放行(返回True,[])后必须无条件resumed+continue, 否则落入下方真HITL等待
                    # 2026-09-05 小欧 ISS-001修复: 删除DRY重构遗留的旧块(sandbox_precheck+sandbox_resolve双调用),
                    #   现仅单一入口 run_sandbox_gate 一次预检, 消除bypass路径同call重复预检
                    _ok, _steps = await run_sandbox_gate(agent, step, call, _cn, _cp, safety_result, _denied)
                    for _st in _steps:
                        yield _st
                    if not _ok:
                        continue
                    if any(getattr(_s, "type", None) == "resumed" for _s in _steps):
                        continue
                    yield agent._step_emitter.emit(MetaStep(
                        step=step, type="resumed",
                        content=f"已自动确认工具执行: {_cn}",
                        severity="info",
                        confirm_id=confirm_id,
                    ))
                    continue

                set_status(agent, AgentStatus.SUSPENDED, f"等待用户确认工具执行: {_cn}")
                from app.config import get_config as _get_cfg_wait
                # 对应 config.yaml security.hitl_timeout(与 emit 的 backend_timeout 同源,默认120); 未配置兜底用常量 HITL_TIMEOUT — 小欧 2026-09-03
                auth = await wait_for_confirmation_result(confirm_id, timeout=int(float(_get_cfg_wait().get("security.hitl_timeout", HITL_TIMEOUT))))

                if not auth.get("confirmed"):
                    if auth.get("expired"):
                        # #11 fix: 超时与拒绝分流 — 小欧 2026-07-18
                        # 2026-08-28 小欧 yield日志审计: 超时决策日志(SRP)
                        logger.warning(f"[action] step={step} timeout: tool={_cn}")
                        yield agent._step_emitter.emit(MetaStep(
                            step=step, type="error", content=f"工具确认超时未响应: {_cn}", error_type="timeout", severity="warn"
                        ))
                        _denied.append((_cn, "确认超时未响应", call))
                    else:
                        # 2026-08-28 小欧 yield日志审计: 拒绝决策日志(SRP)
                        logger.warning(f"[action] step={step} rejected: tool={_cn}")
                        yield agent._step_emitter.emit(MetaStep(
                            step=step, type="error", content=f"用户拒绝执行工具: {_cn}", error_type="user_rejected", severity="warn"
                        ))
                        _denied.append((_cn, "被用户拒绝执行", call))
                    set_status(agent, AgentStatus.EXECUTING, "用户拒绝/超时，恢复执行态")
                    continue  # was: return  — 小欧 2026-07-18 #12 fix

                # 用户已确认：恢复执行态继续工具执行（SUSPENDED→EXECUTING 合法）— 小欧 2026-07-12
                # ⑮ 白名单外临时授权: 确认后授予本次操作权限(一次一申请, 支持递归, per-request) — 小欧 2026-08-10
                # 2026-09-01 小欧 - 紧急bug修复S2(前端badge卡paused): resumed从if auth_path内移出,
                #   用户确认即恢复(与是否授权白名单外路径解耦), 无条件发1条, 授权信息并入文案, 消除重复(KISS/DRY)
                try:
                    # 2026-09-03 小欧 Bug-25: 用户确认授权白名单外路径, grant_temp_auth 异常不阻断恢复执行态
                    if getattr(safety_result, "auth_path", None):
                        from app.tools.security.temp_auth import grant_temp_auth
                        grant_temp_auth(safety_result.auth_path, recursive=True)
                        # 2026-08-28 小欧 yield日志审计: 临时授权日志(SRP) — 保留(2026-09-01 S2移出resumed时同步保留授权留痕)
                        logger.info(f"[action] step={step} resumed+auth: tool={_cn} path={safety_result.auth_path}")
                except Exception as e:
                    logger.warning(f"[action] 确认后grant_temp_auth失败不阻断: {e!r}")
                # 2026-08-28 小欧 yield日志审计: 临时授权日志(SRP)
                set_status(agent, AgentStatus.EXECUTING, "用户已确认工具执行")
                # 2026-09-03 小沈 缺陷1修复: resumed增confirm_id, 前端收到后可据此关弹窗(防御性兜底) — 小沈-2026-09-03
                yield agent._step_emitter.emit(MetaStep(
                    step=step, type="resumed",
                    content=(f"已临时授权白名单外路径: {safety_result.auth_path}"
                             if getattr(safety_result, "auth_path", None)
                             else f"用户已确认工具执行: {_cn}"),
                    severity="info",
                    confirm_id=confirm_id,
                ))
                # v1.25 M3 插入点②: 用户确认汇合路径 — 2026-09-04 小健 DRY: 统一入口
                _ok, _steps = await run_sandbox_gate(agent, step, call, _cn, _cp, safety_result, _denied)
                for _st in _steps:
                    yield _st
                if not _ok:
                    continue
                if any(getattr(_s, "type", None) == "resumed" for _s in _steps):
                    continue
                continue

            # 5.3(2026-09-02 小欧, 病根3.5): 信任豁免/safe 直通汇合点统一授权收口——
            #   tool_safety_checker 豁免返回 requires_confirmation=False 但保留 auth_path,
            #   此处补 grant_temp_auth 闭环, 防"豁免跳窗不放行"(工具内部 validate_path 拦截执行失败)
            try:
                # 2026-09-03 小欧 Bug-25: 白名单外豁免直通亦包 try/except, grant_temp_auth 异常不阻断 sandbox 汇合
                if getattr(safety_result, "auth_path", None):
                    from app.tools.security.temp_auth import grant_temp_auth
                    grant_temp_auth(safety_result.auth_path, recursive=True)
            except Exception as e:
                logger.warning(f"[action] 豁免直通grant_temp_auth失败不阻断: {e!r}")

            # v1.25 M3 插入点③: 循环体末尾兜底(仅 safe 直通/会话信任豁免触达) — 2026-09-04 小健 DRY: 统一入口
            _ok, _steps = await run_sandbox_gate(agent, step, call, _cn, _cp, safety_result, _denied)
            for _st in _steps:
                yield _st
            if not _ok:
                continue

        # 回传未被拒的call索引给调用方 — 小欧 2026-07-18 #12 fix
        # 2026-08-11 小欧 fix D2: 用call对象id标识被拒调用,而非tool_name;
        #   原按tool_name过滤→同批同名工具(如2×edittext)1个被拒全部误杀
        if _out is not None:
            _denied_call_ids = {id(d[2]) for d in _denied}
            _out[:] = [c for c in all_calls if id(c) not in _denied_call_ids]
        # 2026-08-11 小欧 fix D2: _denied(含call对象)回传给调用方, 反馈在build_observation之后
        #   由_add_denial_feedback精确到call写(避免在execute前写tool result导致assistant重复/同名误标)
        if _denied_out is not None:
            _denied_out[:] = list(_denied)

