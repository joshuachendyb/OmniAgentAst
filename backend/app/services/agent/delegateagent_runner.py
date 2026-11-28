# -*- coding: utf-8 -*-
"""delegateagent_runner — 子 Agent 创建与运行

职责：
  1. 查 AgentRegistry 获取 AgentConfig
  2. 创建子 UniversalAgent（独立 task_id、工具子集）
  3. 组装子 Agent 的 task 描述（父传入的 task + context + 输出格式约束）
  4. 在私有事件总线 + 克隆上下文中跑有界 run_react_cycle
  5. 从 FinalStep.response 提取结果 + accumulated_usage，组装返回值

事件总线（关键设计）：
  run_react_cycle 入口强制 get_stream_buffer(task_id) 非空，否则抛 RuntimeError。
  子 Agent 在 _delegate_scope 内用 create_task_stream_buffer(sub_task_id, "") 领一张
  纯内存通行证（无 journal_sink / persist_sink）：不进父 SSE、不落 chat_task_steps。
  上下文副本使 clear_temp_auth（以及 task_id 等 set/reset 类操作）只作用于子作用域，父零污染。
  不用走 run_agent_in_background：那是用户任务语义（台账/取消/重连/统计），
  子过程是同步计算，套完整 runner 属类别错误。

递归防护（fail-closed，三层）：
  1. 配置层：子 Agent 分类先扣拒绝分类（AGENT/SYSTEM/MEDIA/宿主副作用），看不到 delegateagent
  2. 运行层：子作用域内 set_current_delegate_callback(None) → 工具即使被动态灌回也拿不到回调
  3. 深度层：_current_delegate_depth 硬顶（P0 上限 1 层），run_delegate 入口校验
  注：第 1 层单独不够 —— auto_inject_from_search 会按 searchtool 结果 load_category 把 AGENT
  整类灌回子 Agent，而 ToolRetryEngine 持有同一个 _tools_dict 引用。

编辑历史:
  2026-11-28 - 小欧 - 按参考设计落码：同步委托 + 私有 buffer + 上下文副本 +
    递归三层 fail-closed + 墙钟超时 + 父取消轮询 + 有界收口 + model 分支复用父池 +
    构造失败 _close_quietly；T16 用 spy 记录 close() 验证（共享池 close 为 no-op）
  2026-11-28 - OmniAgent - 三堂会审整改：清除注释中的文档章节号与阶段号引用，
    纯注释改动零行为变更
  2026-11-28 - 小欧 - 异步委托落地：wait=False 立即返回 delegate_id 并后台执行，完成后经既有 inbox 注入通知父任务；父取消联动复用 _run_child_guarded 的既有轮询
2026-11-28 小欧 - 整改：track_task 透传；精确 allow_delegate 真正放行嵌套委托且深度≤2；只读白名单 fail-closed 但不过度误拒 read 工具；provider/api_base 不再依赖 model；支持可选 api_key；异步委托 usage 合并父账
"""
import asyncio
import contextvars
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from app.logger import logger
from app.services.agent.universal_agent import UniversalAgent
from app.services.task.task_registry import inject_system_notice
from app.services.task.task_state import (
    create_task_stream_buffer,
    get_task_field,
    is_cancel_requested,
    reclaim_memory_buffer,
)
from app.tools.agent.agent_config import (
    DELEGATE_DENY_CATEGORIES,
    DELEGATE_DENY_TOOLS,
    AgentConfig,
    get_agent_registry,
)
from app.tools.context import (
    _current_delegate_depth,
    reset_current_delegate_callback,
    set_current_delegate_callback,
)
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory

MAX_DELEGATE_DEPTH = 1        # 默认 1 层委托；精确 allow_delegate=True 时放宽到 2 层，仍不超过 2
_POLL_S = 1.0                 # 取消/超时轮询步长（异步等待，不阻塞事件循环）
_CANCEL_GRACE_S = 5.0         # 取消后等待子任务真正退出的上限；超时即放弃等待并留错误日志

# 异步委托后台句柄表（delegate_id -> asyncio.Task） — 小欧 2026-11-28
# 只持强引用防任务被回收；生命周期由任务自身收口，父取消联动复用 _run_child_guarded 的既有轮询。
_background_delegates: Dict[str, asyncio.Task] = {}

# 子 Agent 只读能力白名单（fail-closed）：显式审计过的只读工具 + 元数据 read 工具可进；
# 拒绝分类/拒绝名单/需人工确认一律不进。显式白名单工具优先于 action_kind 元数据；
# 其余 read 工具按注册元数据放行，避免新增只读工具被无意义误拒，但写/未知工具仍拒绝。
DELEGATE_ALLOW_TOOLS = frozenset({
    "searchtool", "searchweb", "fetchpage", "timenow",
    "read", "find", "grep", "listdir", "tree",
    "httpget", "ping_port",
    "read_docx", "read_pdf", "read_pptx", "read_xlsx", "readmedia",
    "analyze_data", "filter_data", "get_db_schema", "query_sql",
})


@asynccontextmanager
async def _delegate_scope(sub_task_id: str):
    """私有事件总线 + 克隆上下文：子 Agent 的框架准入与全局状态隔离收口于此

    约束：返回的 ctx 只能交给一个 asyncio.create_task 使用 —— 同一个 Context 不能被两个
    任务同时进入（否则 RuntimeError: cannot enter context）。
    """
    create_task_stream_buffer(sub_task_id, "")   # journal_sink=None → 纯内存，无 SSE/DB sink；session_id 空串仅占位(不落库故无意义) — 小欧 2026-11-27
    ctx = contextvars.copy_context()
    try:
        yield ctx
    finally:
        # 走到这里时子任务必须已结束（成功/异常/取消都在 _run_child_guarded 收口），
        # 否则回收后子任务仍会往空 buffer 写 → publish/ask_question 抛 RuntimeError。
        reclaim_memory_buffer(sub_task_id)


async def _run_child_guarded(sub_agent, sub_task: str, max_steps: int, scope_ctx,
                             *, parent_task_id: str, timeout_s: float) -> None:
    """在子作用域内跑子 Agent：递归 fail-closed + 墙钟超时 + 父取消联动，收口在一处

    为什么不用 `await asyncio.create_task(...)` 直等：父任务被取消时，等的一方抛
    CancelledError 但**不会**取消被等的任务，子任务会继续跑；而 _delegate_scope 的
    finally 已经回收了 buffer → 子任务下一次 publish/ask_question 直接 RuntimeError。
    所以必须显式持有句柄：取消 → cancel() → 有界等待它真的结束 → 才允许回收
    （宽限期 `_CANCEL_GRACE_S` 内未退出则放弃等待并留错误日志，见 finally）。
    """
    async def _child():
        # 运行层 fail-closed：子作用域先清空委托回调；若子 Agent 精确放行嵌套委托，
        # 入口层在子 Agent 实际调用 delegateagent 时重新注入，仍受深度硬顶约束。
        _cb_token = set_current_delegate_callback(None)
        _d_token = _current_delegate_depth.set(_current_delegate_depth.get() + 1)
        try:
            await sub_agent.run_react_cycle(task=sub_task, max_steps=max_steps)
        finally:
            _current_delegate_depth.reset(_d_token)
            reset_current_delegate_callback(_cb_token)

    task = asyncio.create_task(_child(), context=scope_ctx, name=f"delegate:{sub_agent.task_id}")
    deadline = time.monotonic() + float(timeout_s)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=_POLL_S)
            if task in done:
                task.result()                    # 子 Agent 的异常原样抛出（含 CancelledError）
                return
            if is_cancel_requested(parent_task_id):
                raise asyncio.CancelledError(f"父任务 {parent_task_id} 已取消，终止子Agent")
            if time.monotonic() >= deadline:
                raise asyncio.TimeoutError(f"子Agent超时({timeout_s}s)已强制终止")
    finally:
        if not task.done():
            task.cancel()
            # 有界等待：cancel() 只是"请求取消"，子任务若正卡在同步工具里，取消要等工具返回才生效。
            # 无界 await 会把父任务的超时/取消一起拖长（违背"耗时有界"），故设二次上限。
            _done, _ = await asyncio.wait({task}, timeout=_CANCEL_GRACE_S)
            if task not in _done:
                # 放弃等待：buffer 会被上层回收，子任务后续 publish 会抛 RuntimeError 并被任务自身吞进
                # "Task exception was never retrieved" 日志。这是"宁可留日志也不挂死父任务"的取舍。
                logger.error(
                    f"[delegateagent_runner] 子Agent {sub_agent.task_id} 取消后 {_CANCEL_GRACE_S}s 仍未退出，"
                    f"放弃等待（其后续输出将因 buffer 已回收而报错）"
                )


def _is_delegate_readonly(name: str, meta) -> bool:
    """子 Agent 只读判定：拒绝分类/拒绝名单/需人工确认先拒；显式只读白名单或 read 元数据放行 — 小欧 2026-11-28"""
    if meta is None or not meta.visible_to_llm:
        return False
    if name in DELEGATE_DENY_TOOLS or meta.category in DELEGATE_DENY_CATEGORIES:
        return False
    if meta.needs_confirmation or meta.confirm_fn is not None:
        return False
    if name in DELEGATE_ALLOW_TOOLS:
        return True
    return meta.action_kind == "read"


def _find_unattended_blocker(sub_agent, *, allow_delegate: bool = False) -> Optional[str]:
    """剩余工具里出现"需人工确认/交互"者即返回其名 — 子 Agent 没有前端出口，宁可拒绝委托

    覆盖面：AGENT 分类 + needs_confirmation/confirm_fn；不可见工具跳过；精确 allow_delegate 只放行 delegateagent。
    只读面另由 _is_delegate_readonly 与 _excluded 同源过滤；写/未知工具默认拒绝。
    """
    for name in list(sub_agent._tools_dict.keys()):
        meta = tool_registry.get_tool(name)
        if meta is None:
            return f"{name}(未注册)"
        # 小欧 2026-11-28 BUG-5 整改：对 LLM 不可见的工具（缺依赖/expose=False）不应触发拒绝
        if not meta.visible_to_llm:
            continue
        # 精确多层委托只放行 delegateagent；AGENT 下的 question/schedule 等仍拒
        if name == "delegateagent" and allow_delegate:
            continue
        if meta.category is ToolCategory.AGENT or meta.needs_confirmation or meta.confirm_fn is not None:
            return name
    return None


async def _close_quietly(client) -> None:
    if client is None:
        return
    try:
        await client.close()
    except Exception as e:
        logger.warning(f"[delegateagent_runner] 关闭子 client 失败: {e}")


def _usage_of(sub_agent) -> Dict[str, int]:
    return dict(getattr(sub_agent, "accumulated_usage", {}) or {})


def _parent_http_client(parent_llm):
    """取父 Agent 的底层 httpx 连接池（供 model 分支子 client 复用）。

    小欧 2026-11-28 - 生产父 agent.llm_client 是 BaseAIService（无 .client，池在
    _shared_client，惰性建池走 ensure_client_pool）；设计参考代码按裸 LLMClient
    写的 .client。两处同源，按可用属性取，避免跨层摸私有。
    """
    direct = getattr(parent_llm, "client", None)
    if direct is not None:
        return direct
    ensure = getattr(parent_llm, "ensure_client_pool", None)
    if callable(ensure):
        return ensure()
    return getattr(parent_llm, "_shared_client", None)


async def run_delegate(
    agent,              # 父 Agent 实例（提供 llm_client / task_id）
    agent_id: str,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    wait: bool = True,  # True 同步等待结果；False 后台运行 + inbox 回灌
) -> Dict[str, Any]:
    """执行一次子 Agent 委托；wait=False 立即返回 delegate_id，完成后经 inbox 通知父任务"""
    from app.services.agent.status_table import AgentStatus

    registry = get_agent_registry()
    config = registry.get(agent_id)
    if config is None:
        available = registry.list_available()
        return {
            "status": "error",
            "summary": f"未知 agent_id '{agent_id}'，可用: {available}",
        }

    # 深度硬顶：默认 1 层；精确 allow_delegate 的 Agent 放宽到 2 层
    # 子作用域 allow_delegate 与目标 agent allow_delegate 任一满足即可进入第 2 层，仍不超过 2 层
    depth = _current_delegate_depth.get()
    source_allows_delegate = bool(getattr(agent, "_allow_delegate", False))
    max_depth = 2 if (config.allow_delegate or source_allows_delegate) else MAX_DELEGATE_DEPTH
    if depth >= max_depth:
        return {"status": "error",
                "summary": f"委托深度超限(当前 {depth}，上限 {max_depth})，子Agent不可再委托"}

    # 父任务已取消 → 不启动子 Agent（运行中的子 Agent 由 _run_child_guarded 轮询联动）
    if is_cancel_requested(agent.task_id):
        return {"status": "error", "summary": "父任务已取消，跳过委托"}

    if wait:
        return await _execute_delegate(agent, config, task, context, AgentStatus)

    # 异步：后台句柄表持引用；父任务取消由 _run_child_guarded 的既有轮询联动终止子 Agent
    delegate_id = "d-" + uuid.uuid4().hex[:12]
    parent_task_id = agent.task_id
    session_id = await get_task_field(parent_task_id, "session_id")

    async def _background():
        outcome = ""
        try:
            result = await _execute_delegate(agent, config, task, context, AgentStatus)
            outcome = f"异步委托 {delegate_id} 完成: {str(result.get('summary', ''))[:300]}"
            # 异步委托完成后同样记父账；记账失败不阻断 inbox 通知
            try:
                from app.services.agent.tool_executor import _merge_delegate_usage

                await _merge_delegate_usage(agent, result.get("usage") or {})
            except Exception as merge_error:
                logger.warning(f"[delegateagent_runner] 异步委托 {delegate_id} usage 合并失败: {merge_error}")
        except asyncio.CancelledError:
            outcome = f"异步委托 {delegate_id} 因父任务取消而终止"
            raise
        except Exception as e:
            outcome = f"异步委托 {delegate_id} 失败: {e}"
        finally:
            _background_delegates.pop(delegate_id, None)
            if session_id:
                await inject_system_notice(parent_task_id, outcome, session_id)
            else:
                logger.warning(
                    f"[delegateagent_runner] 异步委托 {delegate_id} 无父会话归属，跳过 inbox 通知"
                )

    _background_delegates[delegate_id] = asyncio.create_task(
        _background(), name=f"delegate-bg:{delegate_id}"
    )
    return {
        "status": "running", "delegate_id": delegate_id,
        "summary": "异步委托已启动，完成后经 inbox 通知父 Agent",
    }


async def _execute_delegate(agent, config: AgentConfig, task: str,
                            context: Optional[Dict[str, Any]], AgentStatus) -> Dict[str, Any]:
    """同步执行体（原 run_delegate 主体），同步/异步两条入口共用，零逻辑分叉"""
    agent_id = config.agent_id       # 日志与 sub_task_id 的单一取名源，与注册表键同源

    # 分类层：配置的 categories 再扣一遍拒绝分类（配置可能来自 manifest，不可信）。
    # 显式传集合：空集就是零工具；不可写 `or None` —— 那会回落到
    # UniversalAgent._INITIAL_CATEGORIES（含 AGENT），把刚剔除的分类工具又装回来。
    sub_categories = config.effective_categories()
    _allow_nested = bool(config.allow_delegate)

    # 只读白名单求差：已注册全集里不是只读者一律拒绝；再并拒绝清单，两层防线都保留。
    # 显式 allowlist + read 元数据均可放行，未知/写/需人工确认仍 fail-closed。
    _registered: set = set()
    for _cat in ToolCategory:
        _registered.update(tool_registry.get_implementations_by_category(_cat))
    _readonly_registered = {
        _name
        for _name in _registered
        if _is_delegate_readonly(_name, tool_registry.get_tool(_name))
    }
    _excluded = DELEGATE_DENY_TOOLS | (_registered - _readonly_registered)

    # 精确多层委托：只放行 delegateagent；question/schedule 等 AGENT 工具仍被拒绝清单挡住
    if _allow_nested:
        sub_categories = set(sub_categories) | {ToolCategory.AGENT}
        _excluded = _excluded - {"delegateagent"}

    # 创建子 Agent（独立 task_id；默认继承父 llm_client，零新建池）
    sub_task_id = f"sub-{agent.task_id}-{agent_id}-{uuid.uuid4().hex[:6]}"
    _sub_client = None
    # 指定模型 / 跨 provider / 自定义端点 / 自定义凭据任一出现，建独立子 client；
    # model 未指定时继承父模型；provider/api_base 不再依赖 model 非空。
    _needs_child_client = bool(config.model or config.provider or config.api_base or config.api_key)
    if _needs_child_client:
        # OCP 扩展位：新建 client。同 provider/同端点可复用父池；跨 provider/自定义端点不传 shared_client，
        # httpx 池与 base_url/凭据绑定，复用父池会错配到父端点。
        from app.db.models.chat_models import ModelRef
        from app.llm.client_sdk import create_llm_client
        _parent_model = agent.llm_client.llm_model
        _cross_endpoint = bool(config.provider or config.api_base)
        _model_ref = ModelRef(
            provider=config.provider or _parent_model.provider,
            model=config.model or _parent_model.model,
            api_base=config.api_base if config.api_base is not None else _parent_model.api_base,
        )
        _shared = None if (_cross_endpoint or config.api_key) else _parent_http_client(agent.llm_client)
        _api_key = config.api_key if config.api_key is not None else agent.llm_client.api_key
        _sub_client = create_llm_client(
            llm_model=_model_ref,
            api_key=_api_key,
            shared_client=_shared,
        )
        _llm_client = _sub_client
    else:
        _llm_client = agent.llm_client

    try:
        sub_agent = UniversalAgent(
            llm_client=_llm_client,
            task_id=sub_task_id,
            max_steps=config.max_steps,
            initial_categories=sub_categories,
            excluded_tools=_excluded,   # 只读：名单拒绝 ∪ (已注册全集 - 只读放行)，未知/写工具默认拒绝
            tool_names=config.tool_names,  # 名粒度放行：从 AgentConfig 透传，构造前生效；不能扩大只读面
            track_task=config.track_task,   # 与设计一致：子过程默认不落 tasks 台账；仅显式配置才建行
        )
    except Exception as e:
        # 构造失败（task_id 非法/依赖缺失等）必须在这里收口：下面的 try/finally 还没开始，
        # 独立 client 否则永远不关（共享 client 时 close 是 no-op，但独立池会漏）。
        await _close_quietly(_sub_client)
        logger.warning(f"[delegateagent_runner] 子Agent {agent_id} 构造失败: {e}")
        return {"status": "error", "summary": f"子Agent构造失败: {e}"}

    # 配置层已扣分类，这里按工具元数据兜底：剩余工具若有需确认/交互者，直接拒绝委托
    sub_agent._allow_delegate = _allow_nested
    _blocked = _find_unattended_blocker(sub_agent, allow_delegate=_allow_nested)
    if _blocked:
        await _close_quietly(_sub_client)
        return {"status": "error",
                "summary": f"agent_id={agent_id} 的工具集含需人工确认/交互工具 {_blocked}，"
                           f"子Agent无交互出口，已拒绝委托"}

    # system_prompt 注入：initialize_run_state 每轮以 _get_system_prompt() 重写 _sys_prompt，
    # 故必须在实例上覆盖该方法，直接设 _sys_prompt 会被下一轮覆盖。
    if config.system_prompt:
        sub_agent._get_system_prompt = lambda: (
            config.system_prompt + "\n\n" + sub_agent.prompts.build_full_system_prompt()
        )

    sub_task = _build_sub_task(config, task, context)

    # 同步执行体：同步入口直接等结果；异步入口在后台任务里跑同一段，零逻辑分叉。
    # 私有事件总线 + 克隆上下文：子 Agent 的终态清理（clear_temp_auth 等）与工具回调
    # set/reset 全落在副本，父作用域零污染。
    try:
        async with _delegate_scope(sub_task_id) as scope_ctx:
            await _run_child_guarded(
                sub_agent, sub_task, config.max_steps, scope_ctx,
                parent_task_id=agent.task_id, timeout_s=config.timeout_s,
            )
    except asyncio.TimeoutError as e:
        logger.warning(f"[delegateagent_runner] 子Agent {agent_id} 超时: {e}")
        return {"status": "error", "summary": str(e), "usage": _usage_of(sub_agent),
                "steps": sub_agent.llm_call_count}
    except asyncio.CancelledError:
        raise                                   # 父任务取消：继续向上取消，终态由父侧收口
    except Exception as e:
        logger.warning(f"[delegateagent_runner] 子Agent {agent_id} 异常: {e}")
        return {"status": "error", "summary": f"子Agent执行异常: {e}",
                "usage": _usage_of(sub_agent), "steps": sub_agent.llm_call_count}
    finally:
        await _close_quietly(_sub_client)       # 独立 client 归还（异常/取消路径同样清理）

    success = getattr(sub_agent, "status", None) == AgentStatus.COMPLETED
    summary = _extract_summary(sub_agent)
    usage = dict(sub_agent.accumulated_usage)  # 由 tool_executor 合并进父 Agent

    logger.info(
        f"[delegateagent_runner] 子Agent {agent_id} 完成: "
        f"status={'success' if success else 'failed'}, steps={sub_agent.llm_call_count}, "
        f"usage={usage}"
    )

    return {
        "status": "success" if success else "failed",
        "summary": summary,
        "usage": usage,
        "steps": sub_agent.llm_call_count,
    }


def _build_sub_task(config: AgentConfig, task: str, context: Optional[Dict[str, Any]]) -> str:
    """组装子 Agent 的 task 描述（自包含，不继承父历史，长度有界且截断留痕）"""
    _task = task[:500]
    if len(task) > 500:
        logger.warning(f"[delegateagent_runner] task 超长已截断: {len(task)}→500 字")
    parts = [f"## 任务\n{_task}"]
    if context:
        items = list(context.items())
        if len(items) > 20:
            logger.warning(f"[delegateagent_runner] context 键过多已截断: {len(items)}→20")
        lines = []
        for k, v in items[:20]:                            # 键数上限，防塞满
            _k = str(k)
            if len(_k) > 100:                              # 小欧 2026-11-28 BUG-4 整改：键名也须有界
                logger.warning(f"[delegateagent_runner] context 键名超长已截断: {len(_k)}→100 字")
                _k = _k[:100]
            _v = str(v)
            if len(_v) > 200:
                logger.warning(f"[delegateagent_runner] context[{k}] 超长已截断: {len(_v)}→200 字")
                _v = _v[:200]
            lines.append(f"- {_k}: {_v}")                  # 单值上限，防大段文本
        if lines:
            parts.append("## 附加上下文\n" + "\n".join(lines))
    # 输出要求：配置给自由文本就用配置，否则用默认摘要要求（不再有封闭枚举 + if/else）
    parts.append("## 输出要求\n" + (
        config.output_instruction or "请输出简洁摘要（≤300字），包含关键发现和结论"
    ))
    return "\n\n".join(parts)


def _extract_summary(sub_agent) -> str:
    """从子 Agent 终态提取结果：FinalStep.response 是正文，reasoning 只是推理轨迹"""
    steps = getattr(sub_agent, "steps", []) or []
    for step in reversed(steps):
        if getattr(step, "TYPE", "") == "final":
            return (getattr(step, "response", "") or getattr(step, "error_message", "")
                    or getattr(step, "reasoning", "") or "")
    return steps[-1].get_content() if steps else ""      # 无终态时降级取末步正文
