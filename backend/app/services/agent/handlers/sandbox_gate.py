# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-25 小欧 沙箱闸门逻辑从 action_handler 拆分(合规重构, 非重写):
#   [病根] action_handler.py 内以嵌套闭包 _sandbox_precheck/_sandbox_resolve 实现沙箱预检闸门,
#          违反 1.3 公用函数规范(分层存放/先查后建/登记FUNCTIONS.md) 与 KISS-DIRECT(隐式捕获约10个外层变量)。
#   [改法] 原逻辑逐字复制, 仅①去闭包改为模块级函数 ②隐式捕获改为显式参数 ③落点定在 Agent 编排层
#          (app/services/agent/handlers/, 与 action_handler 同层, 依赖方向 handler→sandbox 单向, 无环)。
#          业务语义/分支/状态机零改动(复制不重写)。
# 2026-09-01 小欧 紧急bug修复(前端badge卡paused): sandbox_resolve 用户裁决确认分支(:confirmed)补发
#   MetaStep(type="resumed"), 使 paused/resumed 事件成对, 前端badge据此回running恢复前端耗时秒表(秒实时)。
#   resumed 非业务step, stream_reader/agent_runner 剔除不入 current_execution_steps, 不影响 total_steps。
# 2026-09-03 小欧 沙箱用户裁决确认超时可配置化(北京老陈驱动): wait_for_confirmation_result 改读
#   security.hitl_timeout(config.yaml优先, HITL_TIMEOUT 默认120兜底), 与真HITL确认超时同源。
# 2026-09-03 小欧 Bug-16: sandbox paused 补齐 trust_path/auto_confirm/confirm_timeout/backend_timeout 四字段,
#   改前缺字段致前端倒计时与后端不一致(60s/120s 错位); auto_confirm 恒False, 计时取 security.hitl_timeout−LEAD。
# 2026-09-03 小欧 D2-02: _ct钳制max(5,bt-LEAD)避免0秒窗口（与action_handler同钳）
# 2026-09-03 小欧 D2-03: trust_path改复用_extract_trust_path(tool,params)消除别名盲区（path/file_path/source_path等），防通配污染
# 2026-09-03 小欧/老杨 17.1: 纠正16.3落盘偏差——硬编码7key含window_title误当文件路径授权，且_import路径错误（_extract_trust_path实定义于action_handler:567）；改函数内延迟import复用主链函数，与模块内既有延迟导入同模式
# 2026-09-03 小欧/北京老陈: 前端倒计时最小值改常量3(改前硬编码5)
# 2026-09-04 小健 DRY重构: 新增 run_sandbox_gate 统一入口, 消除 check_safety_and_confirm 三处重复调用
#   [问题] ①auto_confirm ②用户确认 ③循环体兜底 三处sandbox_precheck+sandbox_resolve调用逻辑几乎完全相同(DRY违规)
#   [改法] 新增 run_sandbox_gate(agent,step,call,tool_name,params,safety_result,denied) 统一入口,
#          封装 precheck→resolve→yield steps→check ok 逻辑; action_handler 三处改为一行调用
#   [效果] 三处20行重复代码→三处5行调用, 逻辑集中在sandbox_gate.py一个入口, DRY+KISS+SRP
# 2026-09-05 小欧 ISS-002修复(task006问题报告核验为真实问题): sandbox_resolve 确认分支 resumed 补
#   confirm_id(本函数入口 create_confirmation 返回值, 作用域内可用), 对齐主路resumed(action_handler带
#   confirm_id), 前端收到resumed可据此配对关闭对应弹窗, 两通道协议一致
# 2026-09-06 小欧 步骤3A落盘(test_path1_step3a_gateway_cutover.py T3A红→绿, 文档[6]5.3.2+5.3.3):
#   ① sandbox_resolve needs_ruling 分支"等待源头"收网关——删 create/wait/计时/trust_path扫描/paused/resumed
#     组装/SUSPENDED/EXECUTING, 改 ConfirmSpec+hitl_confirm(唯一暂停源头); StreamBuffer缺失显式失败不静默;
#     返回值仍(ok,steps), steps仅剩error类(paused/resumed由网关publish), 待收list留5.4.2(3B)
#   ② 单paused策略(4.4定案): sandbox_resolve/run_sandbox_gate 均加 main_confirmed 短路——主路已confirmed
#     则跳过二次裁决直接放行; bypass区传_bypass_confirmed/真HITL区传True/safe直通缺省False
# 2026-09-06 小欧 B2方案C(北京老陈裁定: 拒绝不是error事件): sandbox_resolve 用户拒绝分支
#   由 MetaStep(type="error", error_type="blocked") 改独立 type="user_rejected" 单独发(无 error_type/
#   severity, 不占 error 通道/liveErrorText); 前端 onDenied 独立回调聚合 deniedStepSet 停齿轮;
#   配套：react_dispatch 状态推断适配、agent_runner 仅SSE集合补入(不落库)。 — 小欧-2026-09-06
# 2026-09-06 小欧 BUG-2 拒绝计数记错工具修复(react_dispatch 死胡同机制, A/B实证): sandbox_resolve
#   拒绝分支构造 user_rejected 未传 tool_name(旧 error_type/blocked 亦不带, 计数一直落到主工具名下);
#   [修复] user_rejected 事件补 tool_name=tool_name(被拒工具名, 拒绝语义自包含) — 小欧-2026-09-06
# 2026-09-06 小欧 BUG-2 拒绝计数错键修复补全(问题挖掘文档六.6.2): 与 user_rejected 同根——危险型拦截 blocked
#   事件亦未带 tool_name(计数回退主工具名, 同键跨拦截累计漂移); [修复] blocked 事件补 tool_name=tool_name — 小欧-2026-09-06
"""沙箱执行闸门: 将 destructive 级工具调用的沙箱预检与结果处置集中在 Agent 编排层。

本模块只编排, 不实现沙箱能力(能力在 app/safety/sandbox/executor.SandboxExecutor)。
依赖方向: handlers → sandbox(单向), 故本模块可安全 import sandbox, 反之不可。
"""
from app.logger import logger
# 延迟导入: MetaStep/AgentStatus/set_status/create_confirmation/wait_for_confirmation_result/HITL_TIMEOUT/SENSITIVE_FIELDS
#   均延迟到函数内导入(小欧 2026-08-25 修复循环import回归): 本模块被 action_handler 顶层 import,
#   若在模块顶层 import agent.steps / task.hitl_confirmation 会构成
#   action_handler→sandbox_gate→hitl_confirmation→task_runtime→task_registry→...→action_handler 环,
#   致后端启动 ImportError(原内联实现为函数内局部 import, 拆分时误改为顶层 import 引入回归)


async def sandbox_precheck(safety_result, tool_name, params):
    """destructive级沙箱预检; 返回None=无需预检(safe级零开销直通)/异常兜底(M4)也返回None直通"""
    if not getattr(safety_result, "sandbox_required", False):
        return None
    try:
        from app.safety.sandbox import get_sandbox_executor
        pre = await get_sandbox_executor().pre_execute(tool_name, params)
        logger.info(f"[sandbox] 预检结果: tool={tool_name}, passed={pre.passed}, "
                    f"needs_ruling={pre.needs_ruling}, reason={pre.blocked_reason[:200]}")
        return pre
    except Exception as exc:
        # M4 兜底: 预检异常不阻断(降级为实施前行为直接放行执行), 绝不炸整批调用链
        logger.warning(f"[action_handler] 沙箱预检异常(M4兜底直接执行): tool={tool_name}, err={exc}")
        return None


async def sandbox_resolve(agent, step, call, tool_name, params, pre, safety_result, denied_list,
                          main_confirmed=False):
    """预检结果处置(DRY: 三处插入点共用)。返回(放行bool, 待下发steps列表)
    危险型失败→denied登记+error步骤; 未完成有效验证(超时/环境性)→复用HITL原语请用户裁决;
    杜绝LLM原样重发死循环"""
    # 延迟导入(修复循环import回归, 见模块顶部注释)
    from app.services.agent.steps import MetaStep
    # 3A: 等待/暂停/恢复组装、计时、SUSPENDED/EXECUTING 全部收 hitl_gateway,
    #   此处仅剩阻塞前直通分支与 error 组装消费 MetaStep — 小欧 2026-09-06
    if pre.passed:
        logger.info(f"[sandbox] 放行执行: tool={tool_name}")
        return True, []
    # 单paused(4.4双paused策略): 主路已confirmed时信任主路裁决, 直接放行不再二次弹窗 — 小健 2026-09-05
    if main_confirmed and pre.needs_ruling:
        logger.info(f"[sandbox] 主路已确认, 跳过二次裁决直接放行: tool={tool_name}")
        return True, []
    if pre.needs_ruling and safety_result.auto_confirm:
        # bypass免打扰语义(v1.13 V2): security.enabled=false即用户要求全自动,
        # 未完成有效验证不得挂起等裁决(否则E2E自动化无人在线必卡死, 与checker历史P0-02同根)
        logger.info(f"[sandbox] bypass下未完成有效验证,按bypass语义直接放行: tool={tool_name}, reason={pre.blocked_reason}")
        return True, []
    if not pre.needs_ruling:
        logger.warning(f"[sandbox] 危险型拦截拒绝: tool={tool_name}, reason={pre.blocked_reason[:200]}")
        denied_list.append((tool_name, f"沙箱预检未通过: {pre.blocked_reason}", call))
        return False, [agent._step_emitter.emit(MetaStep(
            step=step, type="error",
            content=f"沙箱预检未通过: {pre.blocked_reason}",
            error_type="blocked", severity="warn",
            tool_name=tool_name))]
    # needs_ruling: 改走网关(唯一暂停源头)。网关内统一:
    #   paused先于wait到达 / SUSPENDED→wait→EXECUTING / 脱敏 / trust_path / confirm_id回传 — 小健 2026-09-05
    from app.services.agent.handlers.hitl_gateway import ConfirmSpec, hitl_confirm       # 同层调用(hitl→task单向, 无环) — 小欧 2026-09-06
    from app.services.task.task_state import get_stream_buffer                            # 延迟import防环 — 小欧 2026-09-06
    logger.info(f"[sandbox] 转HITL用户裁决: tool={tool_name}")
    _buf = get_stream_buffer(agent.task_id)
    if _buf is None:  # buffer仅编排层建(stream_orchestrator.py:273); 直调无缓冲即显式失败, 不静默 — 小健 2026-09-05
        raise RuntimeError(f"[sandbox] StreamBuffer缺失(task={agent.task_id})")
    spec = ConfirmSpec(
        mode="hitl", tool_name=tool_name, params=params,
        content=f"沙箱未能完成有效预检,需用户裁决是否直接执行: {tool_name}",
        safety_level="destructive", auto_confirm=False)
    verdict = await hitl_confirm(agent, spec, _buf.publish)
    if verdict["confirmed"]:
        logger.info(f"[sandbox] 用户裁决: 确认执行: tool={tool_name}")
        return True, []          # paused/resumed 已由网关publish, 此处不再组Step — 小健 2026-09-05
    logger.warning(f"[sandbox] 用户裁决: 拒绝执行: tool={tool_name}")
    denied_list.append((tool_name, "沙箱预检未完成验证且用户拒绝执行", call))
    # 2026-09-06 小欧 B2(北京老陈裁定): 拒绝不是error事件, 独立 type="user_rejected" 单独发 (与 safety_gate 拒绝路径同构)
    # 2026-09-06 小欧 根因修复(b2 test_02/06/07): user_rejected 必须带被拒工具名 tool_name, 否则拒绝计数回退主工具致错键 — 小欧-2026-09-06
    return False, [agent._step_emitter.emit(MetaStep(
        step=step, type="user_rejected",
        content=f"用户拒绝执行(预检未完成验证): {tool_name}", tool_name=tool_name))]


# ════════════════════════════════════════════════════════════
# 统一入口: 消除 check_safety_and_confirm 三处重复调用 — 小健 2026-09-04
# ════════════════════════════════════════════════════════════

async def run_sandbox_gate(agent, step, call, tool_name, params,
                           safety_result, denied, main_confirmed=False) -> tuple:
    """统一沙箱闸门: 预检+resolve, 返回 (ok, steps)
    消除 check_safety_and_confirm 中 ①auto_confirm ②用户确认 ③循环体兜底 三处重复调用。
    DRY: 三处20行重复代码→一处调用。 — 小健 2026-09-04
    3A: main_confirmed 透传(单paused, 4.4) — 小欧 2026-09-06
    """
    pre = await sandbox_precheck(safety_result, tool_name, params)
    if pre is None:
        return True, []
    ok, steps = await sandbox_resolve(agent, step, call, tool_name, params,
                                       pre, safety_result, denied, main_confirmed)
    return ok, steps
