# -*- coding: utf-8 -*-
"""
tool_executor — 工具执行逻辑

从universal_agent拆出 — 小沈 2026-06-17
"""

# 编辑历史:
# 2026-08-05 小欧 修复(三堂会审通过): auto_inject_from_search只对未加载分类调load_category并尊重返回值, 去掉对已加载分类的多余重复调用; 空实现分类不再被误标为已加载
# 2026-08-12 小欧 A1后半面(4.1.7定案): execute_tool 入口注入安全 hooks(经 ContextVar, try/finally reset),
#   并行/顺序两分支工具内 get_current_hooks() 读到注入值; getattr 通道支持子类自定义 hooks(OCP)
# 2026-08-13 小欧 A4收尾解耦: execute_tool 显式接收 retry_engine 依赖(去除对 agent._retry_engine 私有字段的强耦合, KISS-DIRECT);
#   两调用方(action_handler/tool_facade)显式传入同一引擎对象, 行为不变, 无退化; searchtool 自动注入仍走 agent 内部状态(领域正确)
# 2026-08-23 小欧 落盘文件A/B 实施(文档落码): execute_tool 加 on_attempt_recorded 形参并
#   双分支透传(parallel→try_once / 顺序→execute_tool_with_retry)——补透传链缺跳, 缺此 kwargs 调用必 TypeError
# 2026-10-19 小欧 缺库守卫: 注册期不可用的工具不回 retry_engine(免缺库被当瞬态失败反复重试),
#   改走一次运行期惰性自愈; 自愈的 pip 是同步阻塞 IO, 经 to_thread 卸载, 并加冷却窗防每次调用都起 pip。
# 2026-10-19 小欧 装包进度播报: pip 动辄数十秒, 期间 SSE 无帧则用户只见转圈、与卡死无异。装包经 to_thread
#   后事件循环空出, 才能在装前发一条 MetaStep(type=installing) 到前端任务信息条(文案只报在装哪些包)。
# 2026-10-19 小欧 播报文案补工具名: 原为"正在安装依赖 html2text", 用户不知是哪个工具触发的。
#   现为"正在为 <tool> 安装依赖 <pkgs>"(为哪个工具/装哪些包/进行中); 不带安装指令——
#   该条给用户看, 用户不执行命令; 要执行的 LLM 走缺库错误体 hint, 那里才有完整指令。
# 2026-10-20 15:45 小欧 纯文本任务LLM通道注入(北京老陈令, fetchpage prompt提取用): execute_tool 持 agent,
#   注入压缩摘要同源 call_llm_text_task 闭包到 tools/context 的 _current_text_task ContextVar(hooks 同款
#   try/finally reset 管道); 工具层守护禁 tools→app.services, 故工具内只经 get_current_text_task 消费回调,
#   零越层。agent 无 llm_client 不注入(工具自降级); 并行/顺序两分支统一覆盖。
# 2026-10-25 小欧 - 通知信封收敛(三堂会审 DRY): 删除模块级 _emit_notice 重复实现, 改调 agent._step_emitter.emit_notice();
#   _emit_installing 文案不变, 调用点3处统一迁移 — 小欧-2026-10-25
# 2026-10-25 小欧 - taskinfo 文案压缩(≤15汉字): installing notice 去冗余词, 工具名移括号 — 小欧-2026-10-25
import asyncio
import time
from typing import Any, Callable, Dict, List, Optional, Set

from app.tools.tool_types import ToolCategory
from app.tools.tool_response import is_success
from app.logger import logger
from app.services.agent.tool_cache_manager import invalidate_tool_cache, patch_search_desc
from app.safety.default_hooks import DefaultToolSecurityHooks  # A1: 默认 hooks 转发壳 — 小欧 2026-08-12
from app.tools.context import set_current_hooks, reset_current_hooks, \
    set_current_text_task, reset_current_text_task  # A1 安全hooks + 2026-10-20 纯文本LLM回调 — 小欧
from app.services.agent.llm_call import call_llm_text_task  # 2026-10-20 小欧 通用纯文本调用(全系统发起LLM调用唯一入口层, llm_call.py)

#: 缺库自愈冷却窗(秒): 装不上时窗内不再重复起 pip, 直接回缺库契约。
#: 取值权衡: pip 冷启动+下载常需数十秒, 窗太小则每次工具调用都拖一次 pip 阻塞。
_HEAL_COOLDOWN_SEC = 300.0
#: 各工具上次自愈尝试的时刻(模块级, 进程生命周期内有效)。
_last_heal_attempt: Dict[str, float] = {}


async def execute_tool(agent, tool_name: str, tool_params: Dict[str, Any],
                       retry_engine: Any,
                       parallel: bool = False,
                       on_retry_started: Optional[Callable] = None,
                       on_attempt_recorded: Optional[Callable] = None) -> Dict[str, Any]:
    """执行工具（单入口）— 根据parallel参数分派try_once或带重试执行
     
    职责（SRP：只决定「执行方式」，不重写重试逻辑）：
    1. parallel=True → 调retry_engine.try_once() → 一次执行，不重试
       适用场景：action_handler并行分支（asyncio.gather），瞬态失败概率低
    2. parallel=False → 调retry_engine.execute_tool_with_retry() → 带重试
       适用场景：单工具/顺序执行，需要自动重试瞬态失败
     
    无论哪种路径，统一处理：
    - 耗时统计 + 日志输出
    - is_success状态判断
    - searchtool自动注入（searchtool成功时自动注入整个工具类别给LLM）
     
    Args:
        agent: UniversalAgent实例
        tool_name: 工具名
        tool_params: 工具参数字典
        parallel: True=并行模式用try_once，False=顺序模式用execute_tool_with_retry
        on_retry_started: 仅在parallel=False时透传给execute_tool_with_retry
     
    小健 2026-06-26: 修复状态判断逻辑
    小欧 2026-07-09: 新增parallel/on_retry_started参数，支持并行无重试模式
    """
    
    start = time.time()
    # 2026-10-19 小欧 - 缺库守卫: 注册期已知不可用的工具不真调, 直接回统一缺库契约。
    #   放 retry_engine 之前, 免得缺库错误被重试引擎当成瞬态失败反复重试、白耗时长。
    _missing = await _missing_dep_guard(agent, tool_name)
    if _missing is not None:
        _log_single_tool(tool_name, tool_params, time.time() - start, "fail")
        return _missing

    # A1(4.1.7 定案): 注入安全 hooks 到 ContextVar — 并行/顺序两分支统一覆盖。
    #   getattr 通道: 子类可在 agent 上挂 _security_hooks 自定义实现(OCP), 缺省用 DefaultToolSecurityHooks。
    _hooks = getattr(agent, "_security_hooks", None) or DefaultToolSecurityHooks()
    _hook_token = set_current_hooks(_hooks)
    # 2026-10-20 15:45 小欧 注入纯文本任务LLM回调(压缩摘要 call_llm_text_task 同源封装):
    #   仅 agent 含 llm_client 时注入; 无则不注入, 工具经 get_current_text_task() 得 None 自行降级。
    _llm_connected = getattr(agent, "llm_client", None) is not None

    async def _invoke_text_task(messages):
        return await call_llm_text_task(agent, messages)

    _text_token = set_current_text_task(_invoke_text_task) if _llm_connected else None
    try:
        if parallel:
            # 并行分支：一次执行不重试，失败信息直接返回给LLM决策
            result = await retry_engine.try_once(tool_name, tool_params,
                                                 on_attempt_recorded=on_attempt_recorded)   # #18 — 小欧 2026-08-23
        else:
            # 单工具/顺序分支：带重试+回调通知
            result = await retry_engine.execute_tool_with_retry(
                tool_name, tool_params, on_retry_started=on_retry_started,
                on_attempt_recorded=on_attempt_recorded,   # #18 — 小欧 2026-08-23
            )
    finally:
        reset_current_hooks(_hook_token)
        if _text_token is not None:  # 2026-10-20 小欧 回调 token 采 get 置于 hooks 同一 finally, 零泄漏
            reset_current_text_task(_text_token)
    elapsed = time.time() - start
    
    # 小健 2026-06-26: 使用is_success函数判断状态，而非错误的result.get("code")
    status = "ok" if is_success(result) else "fail"
    _log_single_tool(tool_name, tool_params, elapsed, status)
    
    if tool_name == "searchtool":
        auto_inject_from_search(agent, result)
    return result


async def _emit_installing(agent, tool_name: str, pkgs: List[str]) -> None:
    """装包前播一条 notice(kind=installing, phase=start) 给前端 —— 小欧 2026-10-19

    pip 装包常需数十秒, 期间 SSE 无任何帧, 用户只看到转圈, 与"卡死"无法区分。
    装包已 to_thread 卸载, 事件循环空着, 这条消息才发得出去 —— 二者是同一处改动的两面。

    文案三要素: 为哪个工具 / 装哪些包 / 进行中。
    """
    if not pkgs:
        return
    await agent._step_emitter.emit_notice("installing", "start",
                       f"装{tool_name}依赖中({', '.join(pkgs)})")


async def _missing_dep_guard(agent, tool_name: str) -> Optional[Dict[str, Any]]:
    """缺库守卫: 返回错误体表示拦下了, 返回 None 表示可正常执行 — 小欧 2026-10-19

    先给一次惰性自愈机会(运行期装齐即原地恢复), 覆盖启动期批量装失败(离线/镜像不可达/打包版)。

    两处必须守住, 否则守卫本身变成故障源:
    1. 装包是同步 subprocess(pip 动辄数秒), 直接调会卡死事件循环, 故 to_thread 卸载;
       工作线程只装包不碰元数据, 元数据一律在本协程写(见 registry 两方法拆分说明);
    2. 装不上时每次调用都重试 = 每次都起一个 pip, 故加冷却窗, 窗内直接回契约不再试装。
    """
    from app.tools.registry import tool_registry
    from app.tools.tool_response import build_missing_dep_error

    meta = tool_registry.get_tool(tool_name)
    if meta is None or meta.available:
        return None

    now = time.time()
    if now - _last_heal_attempt.get(tool_name, 0.0) < _HEAL_COOLDOWN_SEC:
        return build_missing_dep_error(tool_name, meta.missing_deps)

    _last_heal_attempt[tool_name] = now
    _pending = registry_pending_deps(tool_name)
    if _pending:
        await _emit_installing(agent, tool_name, _pending)
    # pip 是同步阻塞 IO, 必须离开事件循环线程
    still = await asyncio.to_thread(tool_registry.heal_missing_deps, tool_name)
    if tool_registry.apply_heal_result(tool_name, still):
        await agent._step_emitter.emit_notice("installing", "done",
                           f"{tool_name} 依赖安装完成")
        return None
    await agent._step_emitter.emit_notice("installing", "failed",
                       f"{tool_name} 依赖安装失败")
    return build_missing_dep_error(tool_name, still)


def registry_pending_deps(tool_name: str) -> List[str]:
    """该工具当前缺失、且不在锁定包内的依赖名(供 installing 播报用)

    锁定包不进播报文案: 那类不自行安装(见 tool_response.build_missing_dep_error),
    报了"正在安装"却并没有安装动作, 属不实播报。
    """
    from app.tools.registry import tool_registry
    from app.utils.dependency import LOCKED_PACKAGES, normalize_dep, dependency_status
    meta = tool_registry.get_tool(tool_name)
    if meta is None:
        return []
    out = []
    for dep in (meta.dependencies or []):
        imp, pkg, ver, _pre = normalize_dep(dep)
        if not imp or pkg in LOCKED_PACKAGES:
            continue
        if not dependency_status(imp, pkg, ver):
            out.append(pkg)
    return sorted(dict.fromkeys(out))


def _log_single_tool(tool_name: str, params: Dict[str, Any], elapsed: float, status: str) -> None:
    """一行格式: [tool_executor] tool=xxx, 耗时=0.35s, 状态=ok, params无敏感字段"""
    keys = list(params.keys()) if params else []
    logger.info(f"[tool_executor] tool={tool_name}, 耗时={elapsed:.2f}s, 状态={status}, params={keys}")


def auto_inject_from_search(agent, result: Dict[str, Any]) -> None:
    """从searchtool结果自动注入整个工具类给LLM — 小欧 2026-06-23

    修复: 匹配到一个工具，就把该工具所在的整个类(如NETWORK)全部注入LLM。
    因为LLM知道类名后就能理解该类的所有工具，无需逐个注入。
    
    注意：注入(inject)是指将工具描述提供给LLM使用，工具函数已在启动时注册(register)
    """
    data = result.get("data", {})
    llm_matches = data.get("matches", [])
    if not llm_matches:
        return

    # 收集匹配工具所属的tool类别
    new_categories: Set[ToolCategory] = set()
    for m in llm_matches:
        cat_str = m.get("category", "")
        if cat_str:
            try:
                new_categories.add(ToolCategory(cat_str))
            except ValueError:
                continue

    if not new_categories:
        return

    # 只对尚未加载的分类调用load_category(单一权威, 见base_agent.load_category)
    # 2026-08-05 小欧 修复: 空实现分类load_category返回False, 不再被标记为已加载;
    #   同时去掉对已加载分类的多余重复调用
    loaded_any = False
    for cat in new_categories:
        if cat in agent._loaded_categories:
            continue
        if agent._tool_loader.load_category(cat):
            loaded_any = True

    if not loaded_any:
        return

    # 已加载分类的工具实现已在上方循环内写入_tools_dict
    invalidate_tool_cache(agent)
    patch_search_desc(agent)
