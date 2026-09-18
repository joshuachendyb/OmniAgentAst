# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 新建(10.4第二阶段提一): check_safety_and_confirm 自 action_handler.py 整搬(逐字复制不重写),
#   随迁import(trust/safety/hitl/sandbox/status/steps/constants); 函数内延迟import原样保留;
#   本文件=安全检查+HITL确认门禁(安全+HITL+沙箱三合一), 与 sandbox_gate 同族目录。
# 2026-09-06 小欧 步骤3A落盘(test_path1_step3a_gateway_cutover.py T3A红→绿, 文档[6]5.4.0):
#   真HITL区(行156-212)/bypass区(行104-154)"等待源头"全收 hitl_gateway——删 create/wait/S1窗口/
#   计时/trust_path/paused与resumed自行组装/SUSPENDED/EXECUTING/授权try收口, 改 ConfirmSpec+hitl_confirm
#   唯一暂停源头; 函数保持 async generator 其余 yield 不动(收list/签名返回/sniff删归5.4.2三B);
#   三处汇合点 run_sandbox_gate 加 main_confirmed 透传(141区传_bypass_confirmed/205区传True/226区缺省False);
#   StreamBuffer缺失显式失败不静默; 仅凭auth_path授权不设trust_session门
# 2026-09-06 小欧 步骤3B落盘(文档[6]5.4.2终态, 对应清单#4纯函数半#3纯函数半补):
#   收list→签名->list, blocked/超时/拒绝错误与三处sandbox汇合事件全部并入 _events 列表(单一出口return),
#   删sandbox resumed旁路判定(any(...=='resumed'))与事件透传plumbing(for _st: yield _st),
#   函数由 async generator 收敛纯函数(返回事件列表), 零并发副作用; 等待/resolve/计时/暂停/恢复仍归网关;
#   grant异常不阻断try/except三处保留, _out/_denied_out回传语义不变, handle_action消费点改 await 收列表
# 2026-09-06 小欧 POT-002优化(老陈核查定案): grant_temp_auth 同函数内3处重复import合并——上提模块顶层一次
#   (temp_auth仅标准库依赖contextvars/pathlib/typing, 依赖图核实无环, 上提不破坏任何防环边界);
#   三处try/except保留(捕获授权执行异常不阻断), warning文案逐处保留(决策日志审计区分度), import失败改启动fail-fast
# 2026-09-06 小欧 B2方案C(北京老陈裁定: 拒绝不是error事件): 真HITL拒绝(not confirmed)分支
#   由 MetaStep(type="error", error_type="user_rejected") 改独立 type="user_rejected" 单独发(无 error_type/
#   severity, 不占 error 通道/liveErrorText); 前端 onDenied 独立回调聚合 deniedStepSet 停齿轮;
#   配套：react_dispatch 状态推断适配(独立ttype计入可恢复拒绝计数)、agent_runner 仅SSE集合补入(不落库) — 小欧-2026-09-06
# 2026-09-06 小欧 BUG-2 拒绝计数记错工具修复(react_dispatch 死胡同机制, A/B实证):
#   真HITL拒绝分支构造 user_rejected 事件时未传 tool_name → react_dispatch 取 llm_response.
#   tool_name(主工具) 兜底计数 → 拒绝累到主工具名下, 被拒工具读不完防呆的3次FAILED阈值;
#   [修复] user_rejected 事件补 tool_name=_cn(被拒工具名, 拒绝语义自包含) — 小欧-2026-09-06
# 2026-09-06 小欧 BUG-2 拒绝计数错键修复补全(问题挖掘文档六.6.2): 与 user_rejected 同根——blocked(拦截)/timeout(超时)
#   事件亦未带被拒工具名 tool_name, react_dispatch 计数同样回退主工具名;_deny_counts 同键跨拦截/超时累计漂移;
#   [修复] blocked/timeout 事件均补 tool_name=_cn(拒绝语义自包含, react_dispatch 事件级优先取数) — 小欧-2026-09-06
# 2026-09-17 小欧 - 统一拒绝事件 type="rejected": ①行82 type="error"→"rejected", 新增 reject_type="safety"; ②行125 type="error"→"rejected", 新增 reject_type="timeout"; ③行137 type="user_rejected"→"rejected", 新增 reject_type="user" - 小欧-2026-09-17
# 2026-09-18 小欧 TDD过宽收敛(第3章3.2/3.2.1/3.3/3.4):
#   ①3.2/3.2.1 只读短路: requires_confirmation 前判 shell 只读白名单(含新增五项), 命中不进网关落site③沙箱只读直通;
#   ②3.3 site③ run_sandbox_gate 传 trusted=_skip(会话信任豁免能力缺口直放, risky仍弹);
#   ③3.4 同批合并: 循环外_confirm_cache按(tool, auth/trust_path)组键, 组内首call弹窗其余复用verdict(确认1次/拒绝整组),
#      grant_temp_auth组内仅首call授齐, content追加"另有N-1个同类调用同批一并裁决" - 小欧-2026-09-18
# 2026-09-18 小欧 - safety_level→severity: getattr读取字符串+ConfirmSpec字段同步重命名 — 小欧-2026-09-18
# 2026-09-18 小欧 - 第7章实施([50]7.2.1/7.3.0): ConfirmSpec构造前按SafetyResult.message关键词分类safety_level(未注册→unregistered/系统禁区→forbidden_zone/
#   受保护区域/超出允许范围→path_auth/高风险Shell/系统保护进程→command_block/中风险Shell→shellparam/删除需确认/禁止删除→tool_delete/数据保护→data_guard/
#   安全检查异常→command_block/兜底tool_execute); content改载_message原样(去拼接问句), bypass改"安全开关已绕过，自动确认执行" - 小欧-2026-09-18
# 2026-09-18 小欧 - 三思三省精确化(9类全量核查): keyword链尾部补 `elif not _msg` 按工具名二次归属 —
#   无message确认类(needs_confirmation=True且无风险文案)原全落tool_execute兜底, 与§6.2.2归属不符:
#   shell确认→shellparam(§6.2.3中风险弹窗即needs_confirmation驱动, 命令确认主场景)、create_task/writetext/edittext/writetool→tool_write、
#   delete_task→tool_delete; execute_sql/registry_write/registry_delete保持tool_execute兜底(本就准确) — 小欧-2026-09-18
"""safety_gate — 安全检查+HITL确认门禁 — 小健 2026-09-05

自 action_handler 拆出(八章9.3): check_safety_and_confirm 整函数, 门禁=安全+HITL+沙箱三合一。
"""
from typing import List, Dict

from app.logger import logger
from app.services.agent.steps import MetaStep
from app.services.agent.handlers.sandbox_gate import run_sandbox_gate
from app.tools.security.temp_auth import grant_temp_auth  # POT-002: 3处重复import合并上提(仅标准库依赖无环) — 小欧 2026-09-06

__all__ = ["check_safety_and_confirm"]

async def check_safety_and_confirm(agent, all_calls: List[Dict], step: int, fc_context: Dict = None, _out: list = None, _denied_out: list = None) -> list:
        """安全检查+HITL确认 — 纯函数返回事件列表(MetaStep dict/replay), 3B终态(5.4.2收list) — 小欧 2026-09-06

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
        # 2026-09-06 小欧 3B终态(文档[6]5.4.2): 事件只经 _events 单一列表路径返回(5.5纯函数零并发副作用),
        #   删sandbox resumed旁路判定与事件透传plumbing; blocked/超时/拒绝错误并入列表, 签名落->list
        """
        from app.safety.tool_safety_checker import get_tool_safety_checker
        from app.tools.trust import resolve_skip
        from app.tools.trust import extract_trust_path        # 3.4 同组路径归一(trust.py:69主链权威复用, 防环延迟import同resolve_skip) — 小欧-2026-09-18
        from app.safety.sandbox.executor import _is_readonly_whitelisted, _is_shell_tool  # 3.2 只读短路判定(延迟导入防环, 与sandbox_gate同款写法) — 小欧-2026-09-18
        safety_checker = get_tool_safety_checker()

        _denied = []
        _events = []
        _confirm_cache = {}      # 3.4 同批合并: 组键(tool, auth_path或trust_path)→首call裁决, 组内其余复用 — 小欧-2026-09-18
        for call in all_calls:
            _cn = call.get("tool_name", "?")
            _cp = call.get("tool_params", {})

            # 会话信任预查 — 调用 trust.resolve_skip 独立函数 — 小健 2026-09-04
            _skip = await resolve_skip(agent.task_id, _cn, _cp)

            safety_result = safety_checker.check_before_execute(_cn, _cp, skip_confirmation=_skip)

            # v1.25 M3(设计文档 3.2.3): 沙箱预检闸门 — 逻辑已拆分至 sandbox_gate.sandbox_precheck/sandbox_resolve
            # (2026-08-25 合规重构: 去嵌套闭包隐式耦合, Agent编排层落点, 三处汇合点共用, 每 call 恰好预检一次不重复)

            if safety_result.blocked:
                # 2026-08-28 小欧 决策日志审计: 拦截决策日志(SRP); 3B: blocked错误併入列表 — 小欧 2026-09-06
                logger.warning(f"[action] step={step} blocked: tool={_cn} reason={safety_result.message}")
                _events.append(agent._step_emitter.emit(MetaStep(
                    step=step, type="rejected", content=safety_result.message, reject_type="safety",
                    tool_name=_cn
                )))
                _denied.append((_cn, f"被安全策略拦截: {safety_result.message}", call))
                continue  # was: return  — 小欧 2026-07-18 #12 fix

            # 3.2/3.2.1 只读短路: shell 只读白名单(含新增五项)的 requires_confirmation 不进网关,
            #   恒与真机放行并行(仍落 site③ 走沙箱只读直通), 仅收敛"只读也弹窗"的过宽 — 小欧-2026-09-18
            _readonly = (safety_result.requires_confirmation
                         and _is_shell_tool(_cn)
                         and _is_readonly_whitelisted(str(_cp.get("command") or "")))
            if safety_result.requires_confirmation and not _readonly:
                # 3A: 等待源头全收 hitl_gateway——create/wait/S1窗口/三处独立计时/trust_path/引用信组装 全部删,
                #   paused/resumed 由网关 publish(事件唯一入口); 3B: 本函数纯函数化收list — 小欧 2026-09-06
                from app.services.agent.handlers.hitl_gateway import ConfirmSpec, hitl_confirm  # 同层调用(hitl→task单向, 无环) — 小欧 2026-09-06
                from app.services.task.task_state import get_stream_buffer                # 延迟import防环 — 小欧 2026-09-06
                _buf = get_stream_buffer(agent.task_id)
                if _buf is None:  # buffer仅编排层建(stream_orchestrator.py:273); 直调无缓冲即显式失败, 不静默 — 小健 2026-09-05
                    raise RuntimeError(f"[safety] StreamBuffer缺失(task={agent.task_id})")
                # 3.4 同批合并: 组键(tool, auth_path或trust_path)归一; 组内首call弹窗, 其余复用裁决(拒绝整组/确认同放) — 小欧-2026-09-18
                _group_ref = getattr(safety_result, "auth_path", None) or extract_trust_path(_cn, _cp)
                _group_key = (_cn, _group_ref)
                _group_lead = _group_key not in _confirm_cache
                _bypass = bool(getattr(safety_result, "auto_confirm", False))
                if _group_lead:
                    _group_size = sum(
                        1 for c in all_calls
                        if c.get("tool_name") == _cn
                        and extract_trust_path(c.get("tool_name", ""), c.get("tool_params", {})) == _group_ref)
                    # 网关内统一: SUSPENDED→wait→EXECUTING / 脱敏 / trust_path / confirm_id回传 / 单点resolve收口
                    # 7.2.1 safety_level 分类: 按 content 关键词匹配问题来源 — 小欧-2026-09-18
                    _msg = getattr(safety_result, "message", "")
                    _sl = "tool_execute"  # 兜底
                    if "未注册" in _msg:
                        _sl = "unregistered"
                    elif "系统禁区" in _msg:
                        _sl = "forbidden_zone"
                    elif "受保护区域" in _msg or "超出允许范围" in _msg:
                        _sl = "path_auth"
                    elif "高风险Shell" in _msg or "系统保护进程" in _msg:
                        _sl = "command_block"
                    elif "中风险Shell" in _msg:
                        _sl = "shellparam"
                    elif "删除需确认" in _msg or "禁止删除" in _msg:
                        _sl = "tool_delete"
                    elif "数据保护" in _msg:
                        _sl = "data_guard"
                    elif "安全检查异常" in _msg or "安全检查未通过" in _msg:
                        _sl = "command_block"
                    elif not _msg:
                        # 三思三省(2026-09-18 小欧): 无message确认类(keyword无内容)按工具名精确归属 —
                        #   §6.2.2 归属: shell确认→shellparam(命令确认主场景, §6.2.3中风险弹窗即needs_confirmation驱动),
                        #   create_task等写类→tool_write(实际触发源), delete_task→tool_delete; execute_sql/registry写删保持tool_execute兜底 ✓
                        if _cn == "shell":
                            _sl = "shellparam"
                        elif _cn in ("create_task", "writetext", "edittext", "writetool"):
                            _sl = "tool_write"
                        elif _cn == "delete_task":
                            _sl = "tool_delete"

                    _content = (f"安全开关已绕过，自动确认执行: {_cn}" if _bypass
                                else (_msg if _msg else f"是否允许执行工具: {_cn}")
                                + (f"（另有 {_group_size - 1} 个同类调用同批一并裁决）"
                                   if _group_size > 1 else ""))

                    _verdict = await hitl_confirm(agent, ConfirmSpec(
                        mode="bypass" if _bypass else "hitl", tool_name=_cn, params=_cp,
                        content=_content,
                        severity=getattr(safety_result, "severity", ""),
                        safety_level=_sl),
                        _buf.publish)
                    _confirm_cache[_group_key] = _verdict
                else:
                    _verdict = _confirm_cache[_group_key]   # 组内复用首call裁决, 不发第二次弹窗 — 小欧-2026-09-18
                if _bypass:
                    _bypass_confirmed = _verdict["confirmed"] or _verdict["expired"]  # S1超时bypass兜底放行(原119-120语义) — 小欧 2026-09-06
                    if _group_lead and getattr(safety_result, "auth_path", None):    # 原126语义: 仅凭auth_path, 不设trust_session门; 3.4组内仅首call授齐 — 小欧-2026-09-06/2026-09-18
                        try:
                            grant_temp_auth(safety_result.auth_path, recursive=True)
                        except Exception as e:
                            logger.warning(f"[action] bypass grant_temp_auth失败仍放行: {e!r}")
                    # v1.25 M3 插入点①: auto_confirm 汇合路径 — 沙箱预检最后闸门(统一入口) — 小健 2026-09-04/2026-09-06
                    _ok, _steps = await run_sandbox_gate(agent, step, call, _cn, _cp, safety_result, _denied,
                                                         _bypass_confirmed)
                    _events.extend(_steps)  # 3B: 汇合事件併入返回列表(透传plumbing删除) — 小欧 2026-09-06
                    if not _ok:
                        continue
                    continue

                # 3A: 等待源头已收网关(上方requires_confirmation入口统一调hitl_confirm), 此处按verdict分流 — 小欧 2026-09-06
                if not _verdict["confirmed"]:                     # verdict四键恒在(见5.1), 直接下标安全 — 小欧 2026-09-06
                    if _verdict["expired"]:
                        # #11 fix: 超时与拒绝分流 — 小欧 2026-07-18 (3B: 错误併入列表)
                        logger.warning(f"[action] step={step} timeout: tool={_cn}")
                        _events.append(agent._step_emitter.emit(MetaStep(
                            step=step, type="rejected", content=f"工具执行确认超时: {_cn}", reject_type="timeout",
                            tool_name=_cn
                        )))
                        _denied.append((_cn, "确认超时", call))
                    else:
                        logger.warning(f"[action] step={step} rejected: tool={_cn}")
                        # 2026-09-06 小欧 B2(北京老陈裁定): 拒绝不是error事件, 独立 type="user_rejected" 单独发
                        #   (不挂 error_type/severity, 不占 error 通道); 仅 blocked(拦截)/timeout(超时) 走 error —
                        #   前端按独立事件聚合 deniedStepSet 停齿轮, error 通道不再承载 user_rejected
                        # 2026-09-06 小欧 根因修复(b2 test_02/06/07): user_rejected 必须带被拒工具名 tool_name,
                        #   否则 react_dispatch 回退主工具名 → 多工具并行拒绝死胡同计数记错键 — 小欧-2026-09-06
                        _events.append(agent._step_emitter.emit(MetaStep(
                            step=step, type="rejected", content=f"用户拒绝执行工具: {_cn}", reject_type="user",
                            tool_name=_cn
                        )))
                        _denied.append((_cn, "被用户拒绝执行", call))
                    continue  # was: return  — 小欧 2026-07-18 #12 fix

                # 用户已确认: 仅凭auth_path授权(不设trust_session门), 3.4组内去重仅首call授齐, grant异常不阻断后续沙箱汇合 — 小欧 2026-09-06/2026-09-18
                if _group_lead and getattr(safety_result, "auth_path", None):
                    try:
                        grant_temp_auth(safety_result.auth_path, recursive=True)
                        # 2026-09-06 小欧 3B: 保留授权留痕日志(决策日志SRP, 语义沿用2026-08-28审计)
                        logger.info(f"[action] step={step} resumed+auth: tool={_cn} path={safety_result.auth_path}")
                    except Exception as e:
                        logger.warning(f"[action] 确认后grant_temp_auth失败不阻断: {e!r}")
                # v1.25 M3 插入点②: 用户确认汇合路径 — 2026-09-04 小健 DRY: 统一入口 — 小欧 2026-09-06
                _ok, _steps = await run_sandbox_gate(agent, step, call, _cn, _cp, safety_result, _denied, True)
                _events.extend(_steps)  # 3B: 用户确认汇合事件併入返回列表(透传plumbing删除) — 小欧 2026-09-06
                if not _ok:
                    continue
                continue

            # 5.3(2026-09-02 小欧, 病根3.5): 信任豁免/safe 直通汇合点统一授权收口——
            #   tool_safety_checker 豁免返回 requires_confirmation=False 但保留 auth_path,
            #   此处补 grant_temp_auth 闭环, 防"豁免跳窗不放行"(工具内部 validate_path 拦截执行失败)
            try:
                # 2026-09-03 小欧 Bug-25: 白名单外豁免直通亦包 try/except, grant_temp_auth 异常不阻断 sandbox 汇合
                if getattr(safety_result, "auth_path", None):
                    grant_temp_auth(safety_result.auth_path, recursive=True)
            except Exception as e:
                logger.warning(f"[action] 豁免直通grant_temp_auth失败不阻断: {e!r}")

            # v1.25 M3 插入点③: 循环体末尾兜底(仅 safe 直通/会话信任豁免触达) — 2026-09-04 小健 DRY: 统一入口
            # 3.3: 传 trusted=_skip——会话信任豁免落此, 能力缺口(ruling_kind=unsupported)直放不二次弹窗 — 小欧-2026-09-18
            _ok, _steps = await run_sandbox_gate(agent, step, call, _cn, _cp, safety_result, _denied,
                                                 trusted=_skip)
            _events.extend(_steps)  # 3B: 兜底汇合事件併入返回列表(透传plumbing删除) — 小欧 2026-09-06
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

        return _events  # 3B: 单一列表出口返回事件(纯函数零并发副作用) — 小欧 2026-09-06

