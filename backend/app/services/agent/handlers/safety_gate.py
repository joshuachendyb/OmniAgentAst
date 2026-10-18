# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 新建: check_safety_and_confirm 自 action_handler.py 整搬(逐字复制不重写), 随迁 import(trust/safety/hitl/sandbox/status/steps/constants), 函数内延迟 import 原样保留; 本文件=安全检查+HITL确认门禁(安全+HITL+沙箱三合一), 与 sandbox_gate 同族目录。
# 2026-09-06 小欧 落盘(测试红→绿): 真HITL区/bypass区"等待源头"全收 hitl_gateway, 改 ConfirmSpec+hitl_confirm 唯一暂停源头; 函数保持 async generator 其余 yield 不动; 三处汇合点 run_sandbox_gate 加 main_confirmed 透传; StreamBuffer 缺失显式失败不静默; 仅凭 auth_path 授权不设 trust_session 门
# 2026-09-06 小欧 落盘(清单纯函数半补): 收list→签名->list, blocked/超时/拒绝错误与三处sandbox汇合事件全部并入 _events 列表(单一出口return), 删sandbox resumed旁路判定与事件透传plumbing; 函数由 async generator 收敛纯函数(返回事件列表), 零并发副作用; 等待/resolve/计时/暂停/恢复仍归网关; grant异常不阻断try/except三处保留, _out/_denied_out回传语义不变, handle_action消费点改 await 收列表
# 2026-09-06 小欧 优化: grant_temp_auth 同函数内3处重复import合并上提模块顶层一次(temp_auth仅标准库依赖, 依赖图核实无环); 三处try/except保留, warning文案逐处保留, import失败改启动fail-fast
# 2026-09-06 小欧 拒绝不是 error 事件: 真HITL拒绝分支由 MetaStep(type="error", error_type="user_rejected") 改独立 type="user_rejected"(无 error_type/severity, 不占 error 通道/liveErrorText); 前端 onDenied 独立回调聚合 deniedStepSet 停齿轮; 配套 react_dispatch 状态推断适配、agent_runner 仅SSE集合补入(不落库) — 小欧-2026-09-06
# 2026-09-06 小欧 修复: 拒绝计数记错工具修复(react_dispatch 死胡同机制): user_rejected 事件未传 tool_name → 回退取主工具名计数, 被拒工具读不完防呆的3次FAILED阈值; user_rejected 事件补 tool_name=_cn(被拒工具名) — 小欧-2026-09-06
# 2026-09-06 小欧 修复: 拒绝计数错键修复补全: 与 user_rejected 同根 — blocked/timeout 事件亦未带 tool_name, _deny_counts 同键跨拦截/超时累计漂移; blocked/timeout 事件均补 tool_name=_cn — 小欧-2026-09-06
# 2026-09-17 小欧 - 统一拒绝事件 type="rejected": 三处 type="error"/"user_rejected" 归一, 新增 reject_type 区分(safety/timeout/user) - 小欧-2026-09-17
# 2026-09-18 小欧 TDD过宽收敛(分类归属细化): 只读短路: requires_confirmation 前判 shell 只读白名单(含新增五项), 命中不进网关落site3沙箱只读直通; site3 run_sandbox_gate 传 trusted=_skip(会话信任豁免能力缺口直放, risky仍弹); 同批合并: 循环外_confirm_cache按(tool, auth/trust_path)组键, 组内首call弹窗其余复用verdict, grant_temp_auth组内仅首call授齐, content追加"另有N-1个同类调用同批一并裁决" - 小欧-2026-09-18
# 2026-09-18 小欧 - safety_level→severity: getattr读取字符串+ConfirmSpec字段同步重命名 — 小欧-2026-09-18
# 2026-09-18 小欧 - 归属分类实施: ConfirmSpec构造前按SafetyResult.message关键词分类safety_level(未注册→unregistered/系统禁区→forbidden_zone/受保护区域/超出允许范围→path_auth/高风险Shell/系统保护进程→command_block/中风险Shell→shellparam/删除需确认/禁止删除→tool_delete/数据保护→data_guard/安全检查异常→command_block/其余tool_execute); content改载_message原样, bypass改"安全开关已绕过，自动确认执行" - 小欧-2026-09-18
# 2026-09-18 小欧 - 精确化(9类全量核查): keyword链尾部补 `elif not _msg` 按工具名二次归属 — 无message确认类(needs_confirmation=True且无风险文案)原全落tool_execute: shell确认→shellparam、create_task/write/edit/writetool→tool_write、delete_task→tool_delete; execute_sql/registry_write/registry_delete保持tool_execute — 小欧-2026-09-18
# 2026-09-18 小欧 - 弹窗过宽核查: 同批合并组键 (tool, auth/trust_path) 对 shell 恒退化 ("shell", None)(shell 不在 trust 两集合, extract_trust_path 恒 None), 同批高低风险命令共用一次确认; 组键改按 command 全文分组: 同命令合并, 不同命令各弹 — 小欧-2026-09-18
# 2026-09-18 小欧 - 弹窗过宽核查: 用户拒绝记忆 — _confirm_cache 每轮重建, 用户拒绝后 LLM 换参重试同一工具每轮重弹, (tool, reject_type) 计 3 次才 FAILED; 新增任务级 agent._user_rejected_cache {(tool, ref): content}(refusal_key() 供 sandbox_gate 复用): requires 检查点 A 命中不再弹直接复用拒绝, sandbox 检查点 B 覆盖豁免直通; 信任清除记忆, bypass 全自动不受约束, 主路刚确认不受历史约束; 复用仍走 denied 计数(3 次 FAILED 死胡同保护保留) — 小欧-2026-09-18
# 2026-09-18 小欧 - 去bypass写死content: content恒载真实_message, 删三元f"安全开关已绕过，自动确认执行: {_cn}", bypass识别改用_bypass布尔直传 auto_confirm=_bypass(与hitl_gateway去mode同批), content不再被bypass改写 — 小欧-2026-09-18
# 2026-09-18 小欧 - 去mode字段(KISS-DIRECT, 与hitl_gateway同批): ConfirmSpec删mode="bypass" if _bypass else "hitl", 改auto_confirm=_bypass布尔单源, 避免"布尔→字符串→布尔"无意义往返 — 小欧-2026-09-18
# 2026-09-19 小欧 - bypass恢复_bypass_confirmed透传: 误删run_sandbox_gate的_bypass_confirmed参数(main_confirmed), 恢复透传避免bypass下sandbox走110s+超时拒绝; sandbox_gate同步修复auto_confirm读safety_result
# 2026-10-02 - 小欧 - 注册名收敛: 写操作确认集合 write/edit
# 2026-10-02 - 小欧 - 注册名归位: shell 确认门与合并组键 4 处 shell→bash
# 2026-10-11 小欧 - 超时分支文案去歧义: rejected.content 原写"工具执行确认超时"→LLM 误判为工具慢/文件大而重复改用 write; 改直指"未获授权+路径受保护+换策略", _denied 原因同步改"未获授权"; reject_type 仍为 "timeout"(前端 deniedStepSet 停齿轮控制信号不变) - 小欧-2026-10-11
# 2026-10-11 小欧 - 未获授权报错补路径: content 与 _denied 原因均带上具体路径(call 参数 path 优先, 回落 auth_path/trust_path) - 小欧-2026-10-11
# 2026-10-11 小欧 - rejected 补 confirm_id: 原不带该字段, 前端靠它精确匹配才关窗, 缺字段则确认作废后弹窗永留屏幕 - 小欧-2026-10-11
# 2026-10-14 - 小欧 - 权限信任框架标注: 本文件=框架入口(check_safety_and_confirm, 执行第1步)+HITL确认(hitl_confirm+确认后grant_temp_auth写入, 执行第6步); 信任预查resolve_skip→总闸check_before_execute→沙箱run_sandbox_gate
# 2026-10-14 - 小欧 - import 连带整改: trust 改 app.safety.trust, temp_auth 改 app.safety.temp_auth
# 2026-10-14 - 小欧 - bypass 分支补守卫: bypass 分支补 _bypass_confirmed 守卫(在 grant 之前); 原网关拒了仍授权且下方 continue 吞掉 rejected
# 2026-10-15 - 小欧 - 组键同源: 抽 _group_ref 与组大小同源; ConfirmSpec 透传 auth_path; 拒绝记忆加 bypass 守卫; shell 判定补 execute_command
# 2026-10-15 - 小欧 - 门前初查: check_safety_and_confirm 循环入口加初查(第1层格式+第2层存在性, 进门即拦省信任预查/总闸/弹窗); 实现下沉 path_check_entry.precheck_path_legality; 失败按既有 denied 口径发 rejected 事件 + _denied + continue(不弹窗, 直接进 LLM 重试)。执行期工具内 validate_path 全保留(第2层复查防 TOCTOU + 第3层警告)。
# 2026-10-16 - 小欧 - tool去检查化: 唯一合法性检查点, 执行期工具不再复查(只执行+业务警告); 上条"全保留"作废。
# 2026-10-17 - 小欧 - 裁定点整改: (1)删本层未注册复判段(认领已上提 L2, 只按 _normal_name 查 PATH_TOOLS) (2)信任预查 resolve_skip 移入确认层(requires_confirmation 块内), 删 skip_confirmation 传递与 _rej_cache 死 pop, 恒取 trusted=False (3)删 check_safety_and_confirm 的 fc_context 死参 (4)删 _classify_safety_level "未注册"不可达分支。
# 2026-10-17 - 小欧 - 拒绝回传修复: _denied_out 回传由「切片替换」改「extend 追加」, 否则调用方 pre-seed 的认领拒绝项(_denied_pre)被抹掉, 未注册 call 无 tool 反馈 → LLM 历史孤儿 tool_call。
# 2026-10-18 - 小欧 - 归一化前置: 循环内 _cn 改取 call["_normal_name"](解析层已归一), 参数亦为已归一; 本层不再重复 normalize_params。
# 2026-10-18 - 小欧 - 随契约调整同步(三处): ①只读短路与确认入口两处判读改 needs_confirm ②safety_level 改为"字段优先、文本兜底" —— 各判定分支已直给分类, 本层优先直读, 仅在为空时退回关键词分类; 关键词分类函数保留不删, 因工具元数据确认策略触发的确认(execute_sql/create_task 等)不经路径安全检查、本就没有文案可依据 ③新增 _resolve_trust_impact: 按 temp_auth 实际生效的 recursive 给出授权影响面 high/low, 取代原透传的严重度; 与"是否需确认"正交、互不推导。确认分支顺序与放行条件零变更。
"""safety_gate — 安全检查+HITL确认门禁 — 小健 2026-09-05

自 action_handler 拆出: check_safety_and_confirm 整函数, 门禁=安全+HITL+沙箱三合一。
"""
from typing import List, Dict, Optional
from app.tools.tool_types import SafetyResult

from app.logger import logger
from app.services.agent.steps import MetaStep
from app.services.agent.handlers.sandbox_gate import run_sandbox_gate
from app.safety.temp_auth import grant_temp_auth  # 3处重复import合并上提(仅标准库依赖无环) — 小欧 2026-09-06

__all__ = ["check_safety_and_confirm"]


def _group_ref(tool_name: str, params: dict, safety_result: Optional[SafetyResult] = None) -> Optional[str]:
    """组内引用键的唯一表达式: auth_path or trust_path — 小欧 2026-10-14

    抽出独立纯函数的理由: refusal_key 与 _group_size 两处都要这个表达式, 此前各写一遍,
    一处漏改即出现「弹窗按 auth 分组、组大小按 trust 数」的口径分裂(DRY)。
    """
    from app.safety.trust import extract_trust_path  # 延迟导入(与本模块既有模式一致)
    return (getattr(safety_result, "auth_path", None) if safety_result is not None else None) \
        or extract_trust_path(tool_name, params or {})


def refusal_key(tool_name: str, params: dict, safety_result=None):
    """用户拒绝记忆键 (tool, auth/trust_path/shell-command) — 与同批合并组键同口径(小欧-2026-09-18)。
    shell 无 path 主键(trust 两集合皆无)时按 command 全文分组, 同命令合并、不同命令各弹。
    sandbox_gate 函数内延迟导入复用(防 handlers→safety_gate→sandbox_gate 环)。

    2026-10-14 小欧: 引用表达式改调 _group_ref 与组大小同源;
      shell 判定改 `normalize_tool_name(tool_name) in ("bash","execute_command")` — 与
      path_tool_safety_checker 同源; 原单写 == "bash" 漏 execute_command(它非别名而是独立注册名,
      normalize_tool_name 不归一到 bash), 致同一命令经两入口调用被拆成两组各弹一次。
      组键 tool_name 侧存归一名(防跨别名对不上)。"""
    from app.tools.tools_alias_mapper import normalize_tool_name
    _canon = normalize_tool_name(tool_name)
    _ref = _group_ref(_canon, params or {}, safety_result)
    if _ref is None and _canon in ("bash", "execute_command"):
        _ref = "cmd:" + str((params or {}).get("command") or "")
    return (_canon, _ref)


def _rejection_cache_of(agent) -> dict:
    """取任务级用户拒绝记忆 dict(不存在即建, 存 agent 属性随任务消亡) — 小欧-2026-09-18"""
    _c = getattr(agent, "_user_rejected_cache", None)
    if _c is None or not isinstance(_c, dict):
        _c = {}
        try:
            agent._user_rejected_cache = _c
        except Exception:
            pass
    return _c if isinstance(_c, dict) else {}


def _resolve_trust_impact(auth_path) -> str:
    """授权/信任影响面 — 小欧 2026-10-18

    取值 high / low, 表示**这次授权实际授予 Agent 多大操作自由度**(用户据此判断勾不勾"信任此操作"):
      high = 目录根授权 → 整个子目录树内的读写删都放行
      low  = 单文件授权 → 仅该精确路径

    与"是否需要确认"正交: 弹不弹窗和授权后有多自由是两回事, 互不推导。

    真值源取 temp_auth 实际生效的 recursive(该模块已把"有后缀即文件、只授权精确路径"
    的规则上提为共用函数), 此处只消费不再自判有无后缀 —— 两处各判必然漂移:
    授权按目录给了整棵子树、界面却按单文件显示"low", 会误导用户。
    """
    if not auth_path:
        return "low"
    from app.safety.temp_auth import resolve_grant_recursive   # 延迟导入防环
    return "high" if resolve_grant_recursive(auth_path) else "low"


def _classify_safety_level(msg: str, tool_name: str) -> str:
    """safety_level 分类: 按 content 关键词匹配问题来源 — 小欧 2026-09-18

    2026-10-15 小欧 - SLAP 合规拆分(自 check_safety_and_confirm 原样搬出, 逻辑一字未改):
      该 if/elif 关键词链属「底层判定细节」, 原混在编排主函数里, 改一句提示文案就得翻 250 行找,
      且无法单独测。本函数为纯函数(无副作用、无状态), 可独立测试, 编排层只管调。

    顺序即优先级: if/elif 链首个命中即定, 不被后续分支覆盖。
    无 message 时按工具名精确归属(见下方 not msg 分支)。
    """
    _sl = "tool_execute"  # 默认
    if "系统禁区" in msg:
        _sl = "forbidden_zone"
    elif "受保护区域" in msg or "超出允许范围" in msg:
        _sl = "path_auth"
    elif "高风险Shell" in msg or "系统保护进程" in msg:
        _sl = "command_block"
    elif "中风险Shell" in msg:
        _sl = "shellparam"
    elif "删除需确认" in msg or "禁止删除" in msg:
        _sl = "tool_delete"
    elif "数据保护" in msg:
        _sl = "data_guard"
    elif "安全检查异常" in msg or "安全检查未通过" in msg:
        _sl = "command_block"
    elif not msg:
        # 2026-09-18 小欧: 无message确认类(keyword无内容)按工具名精确归属 —
        #   归属: shell确认→shellparam(命令确认主场景, 中风险弹窗即needs_confirmation驱动),
        #   create_task等写类→tool_write(实际触发源), delete_task→tool_delete; execute_sql/registry写删保持tool_execute
        if tool_name == "bash":
            _sl = "shellparam"
        elif tool_name in ("create_task", "write", "edit", "writetool"):
            _sl = "tool_write"
        elif tool_name == "delete_task":
            _sl = "tool_delete"
    return _sl

async def check_safety_and_confirm(agent, all_calls: List[Dict], step: int, _out: list = None, _denied_out: list = None) -> list:
        """安全检查+HITL确认 — 纯函数返回事件列表(MetaStep dict/replay) — 小欧 2026-09-06
        编排段序: 处理范围门 → 合法性初查 → 危险+权限总闸 → 确认(信任豁免/HITL弹窗);
        通过后交沙箱 run_sandbox_gate。(认领·未注册识别在解析层, 本层不再复判) — 小欧-2026-10-14

        拒绝/拦截是可恢复的(符合人类认知: 拒绝≠失败), 不置终态FAILED:
        - 把"工具被拒绝/拦截"作为 observation 写进LLM历史(_add_denial_feedback), 让LLM换方案;
        - 循环回 THINKING 由主循环 EXECUTING→THINKING 处理;
        - 仅当同类拒绝累计>=3次才由 _dispatch_handler 置 FAILED。 — 小欧 2026-07-13
        # 2026-07-18 小欧 修复: 超时/拒绝分流; 拒绝不终止整批, 收集_denied后继续检查剩余工具,
        #   最终只执行通过的call(通过_out返回过滤后的call列表)
        # 2026-08-11 小欧 修复: _denied从2元组(tool_name,reason)扩展为3元组(tool_name,reason,call),
        #   _out过滤从按tool_name改按id(call)对象精确标识(同批同名工具1个被拒不再误杀);
        #   反馈推迟到调用方build_observation之后(_denied_out回传), 由_add_denial_feedback精确到call写,
        #   消除"会执行的同名工具被误标被拦截"与"assistant双重写入"的矛盾
        # 2026-09-06 小欧: 事件只经 _events 单一列表路径返回(纯函数零并发副作用),
        #   删sandbox resumed旁路判定与事件透传plumbing; blocked/超时/拒绝错误并入列表, 签名落->list
        """
        from app.safety.path_tool_safety_checker import get_path_tool_safety_checker
        from app.safety.trust import resolve_skip
        from app.safety.trust import extract_trust_path        # 同组路径归一(trust 主链权威复用, 防环延迟import同resolve_skip) — 小欧-2026-09-18
        from app.safety.shell_readonly import is_shell_readonly_whitelisted  # 只读短路判定(延迟导入防环, 与sandbox_gate同款写法) — 小欧-2026-09-18; 2026-10-18 SRP 拆分后改指 shell_readonly
        from app.safety.shell_tool_classify import is_shell_tool
        safety_checker = get_path_tool_safety_checker()

        _denied = []
        _events = []
        _confirm_cache = {}      # 同批合并: 组键(tool, auth_path或trust_path)→首call裁决, 组内其余复用 — 小欧-2026-09-18
        for call in all_calls:
            # 2026-10-18 小欧 - 归一化前置后, 直接用解析层写好的规范名 + 已归一参数(安全层不再重复归一)
            _cn = call.get("_normal_name") or call.get("tool_name", "?")
            _cp = call.get("tool_params", {})

            # 处理范围门 — 未注册已在解析层认领(_registered), 本层不再复判;
            #   只处理 PATH_TOOLS 工具, 非路径工具直接放行。
            from app.tools.tool_constants import PATH_TOOLS
            if _cn not in PATH_TOOLS:
                continue

            # 合法性初查: 第1层格式+第2层存在性, 进门即拦, 省信任预查/总闸/弹窗(工具层不再复查合法性)。
            #   实现下沉 path_precheck.precheck_path_legality(op表同源, 禁双份); 第3层警告门前不跑(参数不全且要贴执行)。
            from app.safety.path_precheck import precheck_path_legality
            _pre_err = precheck_path_legality(_cn, _cp)
            if _pre_err is not None:
                _events.append(agent._step_emitter.emit(MetaStep(
                    step=step, type="rejected", content=f"路径不合法: {_pre_err}",
                    reject_type="safety", tool_name=_cn
                )))
                _denied.append((_cn, f"路径不合法: {_pre_err}", call))
                continue

            # 危险+权限 总闸: 池快照现取现递（PID 可被 OS 重用，不得缓存复用）— 小欧 2026-10-16
            from app.tools.fundamental.shell_engine import get_pool_pids_snapshot
            safety_result = safety_checker.check_before_execute(_cn, _cp, pool_pids=get_pool_pids_snapshot())

            # 沙箱预检闸门 — 逻辑已拆分至 sandbox_gate.sandbox_precheck/sandbox_resolve
            # (2026-08-25 重构: 去嵌套闭包隐式耦合, Agent编排层落点, 三处汇合点共用, 每 call 恰好预检一次不重复)

            if safety_result.blocked:
                # 2026-08-28 小欧 决策日志审计: 拦截决策日志(SRP); blocked错误并入列表 — 小欧 2026-09-06
                logger.warning(f"[action] step={step} blocked: tool={_cn} reason={safety_result.message}")
                _events.append(agent._step_emitter.emit(MetaStep(
                    step=step, type="rejected", content=safety_result.message, reject_type="safety",
                    tool_name=_cn
                )))
                _denied.append((_cn, f"被安全策略拦截: {safety_result.message}", call))
                continue  # was: return  — 小欧 2026-07-18 修复

            # 只读短路: shell 只读白名单(含新增五项)的 needs_confirm 不进网关,
            #   恒与真机放行并行(仍落 site3 走沙箱只读直通), 仅收敛"只读也弹窗"的过宽 — 小欧-2026-09-18
            _readonly = (safety_result.needs_confirm
                         and is_shell_tool(_cn)
                         and is_shell_readonly_whitelisted(str(_cp.get("command") or "")))
            if safety_result.needs_confirm and not _readonly:
                # 确认 — 信任预查移入本层(与"是否免确认"同层, SRP)。
                _skip = await resolve_skip(agent.task_id, _cn, _cp)
                if _skip:
                    # 会话信任豁免: 免弹窗, 仍 grant auth_path 收口授权, 直通沙箱(trusted=True)
                    if getattr(safety_result, "auth_path", None):
                        try:
                            grant_temp_auth(safety_result.auth_path, recursive=True)
                        except Exception as e:
                            logger.warning(f"[action] 信任豁免grant_temp_auth失败不阻断: {e!r}")
                    _ok, _steps = await run_sandbox_gate(agent, step, call, _cn, _cp, safety_result, _denied, True)
                    _events.extend(_steps)
                    if not _ok:
                        continue
                    continue
                # 等待源头全收 hitl_gateway — create/wait/窗口/三处独立计时/trust_path/引用信组装 全部删,
                #   paused/resumed 由网关 publish(事件唯一入口); 本函数纯函数化收list — 小欧 2026-09-06
                from app.services.agent.handlers.hitl_gateway import ConfirmSpec, hitl_confirm  # 同层调用(hitl→task单向, 无环) — 小欧 2026-09-06
                from app.services.task.task_state import get_stream_buffer                # 延迟import防环 — 小欧 2026-09-06
                _buf = get_stream_buffer(agent.task_id)
                if _buf is None:  # buffer仅编排层建(stream_orchestrator.py:273); 直调无缓冲即显式失败, 不静默 — 小健 2026-09-05
                    raise RuntimeError(f"[safety] StreamBuffer缺失(task={agent.task_id})")
                # 同批合并: 组键(tool, auth_path或trust_path)归一; 组内首call弹窗, 其余复用裁决(拒绝整组/确认同放) — 小欧-2026-09-18
                # shell 无 path 主键时 refusal_key 按 command 全文分组(同命令合并, 不同命令各弹) — 小欧-2026-09-18
                _group_key = refusal_key(_cn, _cp, safety_result)
                _group_ref = _group_key[1]
                _group_lead = _group_key not in _confirm_cache
                _bypass = bool(getattr(safety_result, "auto_confirm", False))  # 上移: 原在组首分支内, 复用分支 else 取不到(隐含未定义) — 小欧-2026-09-18
                # 用户拒绝记忆(2026-09-18 小欧): 同 (tool, path) 本任务内被用户拒绝过, 不再弹直接复用拒绝;
                #   信任清除记忆(用户已显式信任, 拒绝让位); bypass 全自动语义不受记忆约束
                _rej_cache = _rejection_cache_of(agent)
                if _group_key in _rej_cache and not _bypass:
                    _rej_content = _rej_cache[_group_key]
                    logger.warning(f"[action] step={step} rejected-cached: tool={_cn} (本任务内已有拒绝记录, 不再重复确认)")
                    _events.append(agent._step_emitter.emit(MetaStep(
                        step=step, type="rejected", content=_rej_content, reject_type="user",
                        tool_name=_cn
                    )))
                    _denied.append((_cn, f"被用户拒绝执行(本任务内已有拒绝记录，不再重复确认): {_rej_content}", call))
                    continue
                if _group_lead:
                    if _cn == "bash":
                        _group_size = sum(
                            1 for c in all_calls
                            if c.get("tool_name") == "bash"
                            and str((c.get("tool_params") or {}).get("command") or "") == str(_cp.get("command") or ""))
                    else:
                        _group_size = sum(
                            1 for c in all_calls
                            if c.get("tool_name") == _cn
                            and extract_trust_path(c.get("tool_name", ""), c.get("tool_params", {})) == _group_ref)
                    # 网关内统一: SUSPENDED→wait→EXECUTING / 脱敏 / trust_path / confirm_id回传 / 单点resolve收口
                    # safety_level 分类: 按 content 关键词匹配问题来源 — 小欧-2026-09-18
                    # 2026-10-15 小欧 - SLAP 拆分: 分类链已搬至 _classify_safety_level(纯函数, 可独立测)
                    _msg = getattr(safety_result, "message", "")
                    # 2026-10-18 小欧 - 产地归位但**不删本函数**: 有 safety_level 直读(各判定分支已直给),
                    #   空才按文本兜底。兜底不可删: execute_sql/create_task 等由工具元数据确认策略触发的确认
                    #   不经路径安全检查、本就没有 message 可依据, 删之则这些场景分类恒空。
                    _sl = getattr(safety_result, "safety_level", "") or _classify_safety_level(_msg, _cn)

                    # 2026-09-18 小欧 - 去bypass写死content: content恒载真实_message,
                    #   bypass仅由auto_confirm=True区分 — 小欧-2026-09-18
                    _content = (_msg or "") + (f"（另有 {_group_size - 1} 个同类调用同批一并裁决）"
                                               if _group_size > 1 else "")

                    _verdict = await hitl_confirm(agent, ConfirmSpec(
                        auto_confirm=_bypass, tool_name=_cn, params=_cp,
                        content=_content,
                        trust_impact=_resolve_trust_impact(getattr(safety_result, "auth_path", None)),
                        safety_level=_sl,
                        # 2026-10-14 小欧 - 透传 auth_path。
                        #   auth 轨(白名单外临时授权)此前在 HITL 链丢失 — 下游 hitl_gateway
                        #   已按 spec.path 优先消费, 但此处不传则它恒 None, 授权路径无处可查。
                        path=getattr(safety_result, "auth_path", None)),
                        _buf.publish)
                    _confirm_cache[_group_key] = _verdict
                else:
                    _verdict = _confirm_cache[_group_key]   # 组内复用首call裁决, 不发第二次弹窗 — 小欧-2026-09-18
                if _bypass:
                    _bypass_confirmed = _verdict["confirmed"] or _verdict["expired"]  # 超时bypass放行 — 小欧 2026-09-06
                    # 2026-10-14 小欧 - 守卫补在授权之前。网关拒了
                    #   (_bypass_confirmed False)仍往下走 grant + run_sandbox_gate, 而下方 continue 会把
                    #   rejected 吞掉 — 用户已拒, 流程却照走。防御性: bypass 下 auto_confirm=True 使网关
                    #   自动确认, 本守卫几乎恒不触发, 仅网关异常时可拦(与 sandbox_gate 检查点 B 同构)。
                    if not _bypass_confirmed:
                        _events.append({"step": step, "tool_name": _cn,
                                        "rejected": "user", "reason": "bypass未确认即终止"})
                        continue
                    if _group_lead and getattr(safety_result, "auth_path", None):    # 仅凭auth_path, 不设trust_session门; 组内仅首call授齐 — 小欧-2026-09-06/2026-09-18
                        try:
                            grant_temp_auth(safety_result.auth_path, recursive=True)
                        except Exception as e:
                            logger.warning(f"[action] bypass grant_temp_auth失败仍放行: {e!r}")
                    # auto_confirm 汇合路径 — 沙箱预检最后闸门(统一入口) — 小健 2026-09-04/2026-09-06
                    # 2026-09-19 小欧 修复: 恢复 _bypass_confirmed 透传(main_confirmed), 误删导致bypass下sandbox走110s+超时拒绝
                    _ok, _steps = await run_sandbox_gate(agent, step, call, _cn, _cp, safety_result, _denied,
                                                         _bypass_confirmed)
                    _events.extend(_steps)  # 汇合事件并入返回列表(透传plumbing删除) — 小欧 2026-09-06
                    if not _ok:
                        continue
                    continue

                # 等待源头已收网关(上方needs_confirm入口统一调hitl_confirm), 此处按verdict分流 — 小欧 2026-09-06
                if not _verdict["confirmed"]:                     # verdict四键恒在, 直接下标安全 — 小欧 2026-09-06
                    if _verdict["expired"]:
                        # 修复: 超时与拒绝分流 — 小欧 2026-07-18
                        logger.warning(f"[action] step={step} timeout: tool={_cn}")
                        # 2026-10-11 小欧 - 文案去歧义: 原写"工具执行确认超时: {_cn}"把
                        #   主语说成"执行"，LLM 读到即以为工具慢/文件大，改用 write 重写整个文件再试，
                        #   同一受保护路径连撞 3 次判死胡同。
                        #   真实语义=确认窗口关闭、没收到人工授权，与"执行耗时"无关。
                        #   现措辞直指"未获授权 + 路径受保护 + 换策略"，让 LLM 换工具/换路径而非死磕。
                        #   reject_type 仍为 "timeout"(前端 deniedStepSet 停齿轮的控制信号, 不变)。
                        # 2026-10-11 小欧 - 报错补路径: 原文案只说"该路径受保护"却不说哪个路径,
                        #   人工排查时无从判断该去授权哪一处。现取 call 参数 path 优先、
                        #   回落 auth_path/trust_path, 让报错自带定位信息。
                        _tp = str(_cp.get("path") or getattr(safety_result, "auth_path", None)
                                   or getattr(safety_result, "trust_path", None) or "未知路径")
                        _events.append(agent._step_emitter.emit(MetaStep(
                            step=step, type="rejected",
                            content=(f"工具 {_cn} 未获授权: 路径 {_tp} 属受保护区域, 需人工在确认窗口内授权; "
                                     f"确认窗口已关闭(未收到授权)。"),
                            reject_type="timeout",
                            tool_name=_cn,
                            confirm_id=_verdict.get("confirm_id")  # 2026-10-11 小欧 前端按id精确关窗(详见文件头)
                        )))
                        _denied.append((_cn, f"未获授权({_tp})", call))
                    else:
                        logger.warning(f"[action] step={step} rejected: tool={_cn}")
                        # 2026-09-06 小欧: 拒绝不是error事件, 独立 type="user_rejected" 单独发
                        #   (不挂 error_type/severity, 不占 error 通道); 仅 blocked(拦截)/timeout(超时) 走 error —
                        #   前端按独立事件聚合 deniedStepSet 停齿轮, error 通道不再承载 user_rejected
                        # 2026-09-06 小欧 根因修复: user_rejected 必须带被拒工具名 tool_name,
                        #   否则 react_dispatch 回退主工具名 → 多工具并行拒绝死胡同计数记错键 — 小欧-2026-09-06
                        _events.append(agent._step_emitter.emit(MetaStep(
                            step=step, type="rejected", content=f"用户拒绝执行工具: {_cn}", reject_type="user",
                            tool_name=_cn,
                            confirm_id=_verdict.get("confirm_id")  # 2026-10-11 小欧 同 timeout 分支
                        )))
                        _denied.append((_cn, "被用户拒绝执行", call))
                        # 记用户拒绝记忆(键与组键同口径), 同 (tool, path) 本任务内再派发不再弹
                        _rejection_cache_of(agent)[_group_key] = f"用户拒绝执行工具: {_cn}"
                    continue  # was: return  — 小欧 2026-07-18 修复

                # 用户已确认: 仅凭auth_path授权(不设trust_session门), 组内去重仅首call授齐, grant异常不阻断后续沙箱汇合 — 小欧 2026-09-06/2026-09-18
                if _group_lead and getattr(safety_result, "auth_path", None):
                    try:
                        grant_temp_auth(safety_result.auth_path, recursive=True)
                        # 2026-09-06 小欧: 保留授权日志(决策日志SRP, 语义沿用2026-08-28)
                        logger.info(f"[action] step={step} resumed+auth: tool={_cn} path={safety_result.auth_path}")
                    except Exception as e:
                        logger.warning(f"[action] 确认后grant_temp_auth失败不阻断: {e!r}")
                # 用户确认汇合路径 — 2026-09-04 小健 DRY: 统一入口 — 小欧 2026-09-06
                _ok, _steps = await run_sandbox_gate(agent, step, call, _cn, _cp, safety_result, _denied, True)
                _events.extend(_steps)  # 用户确认汇合事件并入返回列表(透传plumbing删除) — 小欧 2026-09-06
                if not _ok:
                    continue
                continue

            # 信任豁免/safe 直通汇合点统一授权收口(2026-09-02 小欧) —
            #   path_tool_safety_checker 豁免返回 needs_confirm=False 但保留 auth_path,
            #   此处补 grant_temp_auth 闭环, 防"豁免跳窗不放行"(工具内部 validate_path 拦截执行失败)
            try:
                # 2026-09-03 小欧 修复: 白名单外豁免直通亦包 try/except, grant_temp_auth 异常不阻断 sandbox 汇合
                if getattr(safety_result, "auth_path", None):
                    grant_temp_auth(safety_result.auth_path, recursive=True)
            except Exception as e:
                logger.warning(f"[action] 豁免直通grant_temp_auth失败不阻断: {e!r}")

            # 循环体末尾汇合(仅 safe 直通/会话信任豁免触达) — 2026-09-04 小健 DRY: 统一入口
            _ok, _steps = await run_sandbox_gate(agent, step, call, _cn, _cp, safety_result, _denied,
                                                 trusted=False)   # 2026-10-17 小欧 - 信任已移入确认层, 本处无信任豁免
            _events.extend(_steps)  # 汇合事件并入返回列表(透传plumbing删除) — 小欧 2026-09-06
            if not _ok:
                continue

        # 回传未被拒的call索引给调用方 — 小欧 2026-07-18 修复
        # 2026-08-11 小欧: 用call对象id标识被拒调用,而非tool_name;
        #   原按tool_name过滤→同批同名工具(如2×edit)1个被拒全部误杀
        if _out is not None:
            _denied_call_ids = {id(d[2]) for d in _denied}
            _out[:] = [c for c in all_calls if id(c) not in _denied_call_ids]
        # 2026-08-11 小欧: _denied 回传调用方, 由 _add_denial_feedback 在 build_observation 后精确补写
        #   改 extend 追加(切片替换会抹掉调用方 pre-seed 的认领拒绝项; _out 过滤集仍替换)
        if _denied_out is not None:
            _denied_out.extend(_denied)

        return _events  # 单一列表出口返回事件(纯函数零并发副作用) — 小欧 2026-09-06

