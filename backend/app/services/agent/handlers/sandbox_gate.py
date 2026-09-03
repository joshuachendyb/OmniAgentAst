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


async def sandbox_resolve(agent, step, call, tool_name, params, pre, safety_result, denied_list):
    """预检结果处置(DRY: 三处插入点共用)。返回(放行bool, 待下发steps列表)
    危险型失败→denied登记+error步骤; 未完成有效验证(超时/环境性)→复用HITL原语请用户裁决;
    杜绝LLM原样重发死循环"""
    # 延迟导入(修复循环import回归, 见模块顶部注释)
    from app.services.agent.steps import MetaStep
    from app.services.agent.status_table import AgentStatus, set_status
    from app.services.task.hitl_confirmation import create_confirmation, wait_for_confirmation_result
    from app.constants import HITL_TIMEOUT
    from app.tools.tool_constants import SENSITIVE_FIELDS as _SENSITIVE_FIELDS
    if pre.passed:
        logger.info(f"[sandbox] 放行执行: tool={tool_name}")
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
            error_type="blocked", severity="warn"))]
    # needs_ruling: 走现有确认机制(create_confirmation/wait_for_confirmation_result, 本函数上方已import)
    logger.info(f"[sandbox] 转HITL用户裁决: tool={tool_name}")
    confirm_id = await create_confirmation(agent.task_id, tool_name)
    # 2026-09-03 小欧 Bug-16: sandbox paused 对齐主链四字段(trust_path/auto_confirm/confirm_timeout/backend_timeout),
    #   改前缺 4 字段 → 前端倒计时与后端不一致(60s vs 120s 计时错位)。sandbox 为真HITL裁决(非bypass),
    #   auto_confirm 恒 False, 计时与 security.hitl_timeout 对齐(backend 窗口 − HITL_CONFIRM_LEAD 提前量)
    from app.config import get_config as _get_cfg_sb2
    from app.constants import HITL_CONFIRM_LEAD  # HITL_TIMEOUT 第53行已导入, 不重复(DRY)
    _bt = int(float(_get_cfg_sb2().get("security.hitl_timeout", HITL_TIMEOUT)))
    # 2026-09-03 小欧 D2-02: 0窗钳制≥5s（与action_handler同钳）
    _ct = max(5, _bt - HITL_CONFIRM_LEAD)
    # 2026-09-03 小欧/老杨 17.1: 复用主链 _extract_trust_path（函数内延迟import规避循环，与模块内既有延迟导入同模式），纠正16.3硬编码7key及window_title误授权
    # 17.1补：_extract_trust_path对非FILE_OPERATION_TOOLS（如move_file vs move）返回None时，回落查常见文件路径键（不含window_title，防窗口标题误当文件路径）
    try:
        from app.services.agent.handlers.action_handler import _extract_trust_path as _sb_trust_path
        _sandbox_path = _sb_trust_path(tool_name, params)
    except Exception:
        _sandbox_path = None
    if _sandbox_path is None:
        for _k in ("path", "file_path", "source_path", "dest_path", "target", "dir_path"):
            _v = params.get(_k)
            if isinstance(_v, str) and _v:
                _sandbox_path = _v
                break
    steps = [agent._step_emitter.emit(MetaStep(
        step=step, type="paused",
        content=f"沙箱未能完成有效预检,需用户裁决是否直接执行: {tool_name}",
        confirm_id=confirm_id, tool_name=tool_name,
        params={k: v for k, v in params.items() if k not in _SENSITIVE_FIELDS},
        safety_level="destructive", severity="attention",
        trust_path=_sandbox_path, auto_confirm=False,
        confirm_timeout=_ct, backend_timeout=_bt))]
    set_status(agent, AgentStatus.SUSPENDED, f"等待用户裁决沙箱预检: {tool_name}")
    from app.config import get_config as _get_cfg_sb
    # 对应 config.yaml security.hitl_timeout(与真HITL用户确认超时同源,默认120); 未配置兜底用常量 HITL_TIMEOUT — 小欧 2026-09-03
    auth = await wait_for_confirmation_result(confirm_id, timeout=int(float(_get_cfg_sb().get("security.hitl_timeout", HITL_TIMEOUT))))
    set_status(agent, AgentStatus.EXECUTING, "沙箱预检用户裁决完成")
    if auth.get("confirmed"):
        logger.info(f"[sandbox] 用户裁决: 确认执行: tool={tool_name}")
        # 2026-09-01 小欧 - 紧急bug修复S3(前端badge卡paused): 沙箱用户裁决确认后恢复,
        #   补发resumed使paused/resumed成对, 前端badge据此回running恢复耗时秒表
        steps.append(agent._step_emitter.emit(MetaStep(
            step=step, type="resumed",
            content=f"沙箱预检已确认执行: {tool_name}", severity="info")))
        return True, steps
    logger.warning(f"[sandbox] 用户裁决: 拒绝执行: tool={tool_name}")
    denied_list.append((tool_name, "沙箱预检未完成验证且用户拒绝执行", call))
    steps.append(agent._step_emitter.emit(MetaStep(
        step=step, type="error",
        content=f"用户拒绝执行(预检未完成验证): {tool_name}",
        error_type="user_rejected", severity="warn")))
    return False, steps
