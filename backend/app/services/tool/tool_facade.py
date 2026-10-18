# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 新建: A4 工具门面(方案4.4.3步骤1) — list_tools 只读组装; execute_tool 复用 tool_executor
#   统一执行入口(tool_executor 内部已 ContextVar 注入 hooks), facade 只做安全预检 + task 上下文管理(try/finally reset)。
#   按真实代码实现: 安全预检用 get_path_tool_safety_checker().check_before_execute(设计4.4.3示例 check_tool_safety 不存在, 已按实测落地);
#   agent 构造带 _security_hooks(与 action_handler 对齐), 供 tool_executor getattr 通道识别。
# 2026-08-13 - 小欧 - 三堂会审修复: ①_FacadeAgent 补 _tool_loader/_loaded_categories/_tool_cache(searchtool 注入路径
#   需这些属性, 缺则 AttributeError)且复用以真实 ToolLoader(不假造); ②执行判定改 is_success(参数失败/工具未找到
#   不再被误报 success=True, 与 chat 路径同源); ③捕获错误 message 回传 tool_routes 展示。
#   2026-08-13 07:32 编写 — 小欧
# 2026-08-13 小欧 A4收尾解耦: _FacadeAgent 去除 _tools_dict/_retry_engine 伪造字段, retry_engine 由 facade 显式构建
#   (ToolRetryEngine(_get_tool_dict())) 经 execute_tool 的 retry_engine 显式依赖传入; _FacadeAgent 仅保留 _security_hooks
#   + searchtool 注入所需 _loaded_categories/_tool_loader/_tool_cache(领域正确, 非 YAGNI 过度供给), 消除 hot-path 私有字段耦合
# 2026-08-13 - 小沈 - 修复(三堂会审): ①_FacadeAgent 移至模块级(原函数内定义, 每次请求重建类对象);
#   ②_retry_engine 模块级单例(ToolRetryEngine 无状态, 复用同一实例, KISS-DIRECT); ③result 非 dict 时判失败(原 ok=True 误报成功)
# 2026-08-18 - 小健 - 三堂会审 修复(同源): result.llm_data.status 可能为 str, 新增 _safe_status_message 防御 AttributeError
# 2026-10-14 - 小欧 - SA1标注: 本文件=权限信任框架SA1(API直调入口,与safety_gate的Agent入口并列双入口,执行顺序第1步→SA3总闸) — 小欧-2026-10-14
# 2026-10-14 - 小欧 - 文档[33] 4.13(P3步14): 补 SA7 沙箱预检 + SA6 带守卫授权; 病根: 本链只做SA3, destructive 可绕过影子副本预检, 且白名单外授权无人grant致工具体内二次拦截
# 2026-10-15 - 小欧 - 文档[33] 5.21(P3收尾①②④): ①requires_confirmation 分支补设计注释(该分支恒拒绝是接口形态决定,
#   非漏实现 —— API 链无 session_id 故 skip_confirmation 恒 False 无法走会话豁免, 且无前端可裁决 HITL, 等待只会挂死调用方);
#   ④补文件末尾行尾换行(原缺, P3 实施时的漏项, 纯注释/字节零逻辑改动)。— 小欧-2026-10-15
# 2026-10-18 - 小欧 - 未知工具崩溃修复(实测 POST /api/v1/tool/execute {"tool_name":"nonexistent"} → 500):
#   execute_tool 直调安全层 check_before_execute, 而未注册工具使 get_tool 返回 None,
#   path_tool_safety_checker 解引用 tool_meta.check_fn 抛 AttributeError。门面层补注册校验早返
#   (success=False, fail-closed), 不改安全层契约(解析层仍是 Agent 链路唯一未注册拦截点)。
# 2026-10-18 - 小欧 - 归一化前置: /tool/execute 直调不经 L2 解析层, execute_tool 补
#   resolve_registered_tool(名归一) + normalize_params(参数名归一), 后续 safety/sandbox/执行统一用规范名与参数
#   (与 Agent 链路 L2 同口径, 防别名漏检)。
# 2026-10-18 - 小欧 - 三堂会审H2(等价收敛, 非缺陷修复): 名归一提前并与未注册判定合并, 用 resolve_registered_tool
#   返回的 meta 判未知(去 get_tool 重复查)。注: get_tool 内部本已调 normalize_tool_name(registry.py:283-294),
#   故原码对别名工具名不误判; 本次仅为单次归一/少一次查表的收敛, 行为等价。
"""
tool_facade — 工具门面(API 适配层)

职责(方案4.4.3, 小欧 2026-08-12):
  - list_tools: 工具列表只读组装(无安全检查);
  - execute_tool: 安全预检 + 复用 tool_executor 统一执行(注入 DefaultToolSecurityHooks, 消除双路径)。

依赖方向: services/tool → safety(checker) + services/agent(tool_executor) + tools(registry), 单向无环。
"""
import uuid
from typing import Optional

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.tools.tool_retry_engine import ToolRetryEngine
from app.tools.tool_response import is_success
from app.safety.path_tool_safety_checker import get_path_tool_safety_checker
from app.safety.default_hooks import DefaultToolSecurityHooks
from app.services.task.task_context import _current_task_id


def _safe_status_message(result: dict) -> str:
    """2026-08-18 小健 三堂会审 修复(同源): result.llm_data.status 可能为 str, 防御 .get AttributeError"""
    if not isinstance(result, dict):
        return ""
    _ld = result.get("llm_data")
    if not isinstance(_ld, dict):
        return ""
    _st = _ld.get("status")
    if not isinstance(_st, dict):
        return ""
    return _st.get("message", "")
from app.utils.cache import TTLCache
from app.constants import TOOL_CACHE_TTL as _TOOL_CACHE_TTL
from app.logger import logger
from app.services.agent.tool_loader import ToolLoader

# 模块级惰性缓存: 全量工具实现表(与 ToolLoader 同源的 registry 公共 API 构建, 不摸私有字段)。
# 供 _FacadeAgent._retry_engine(→tool_executor 非并行分支)复用 — 小欧 2026-08-12
_tools_dict: dict = {}


def _get_tool_dict() -> dict:
    global _tools_dict
    if not _tools_dict:
        _tools_dict = {}
        for cat in ToolCategory:
            _tools_dict.update(tool_registry.get_implementations_by_category(cat))
        logger.info(f"[tool_facade] 构建工具实现表, 共{len(_tools_dict)}个工具")
    return _tools_dict


# 修复(三堂会审 小沈 2026-08-13): _FacadeAgent 移至模块级(避免每次请求重建类对象);
#   _retry_engine 模块级单例(ToolRetryEngine 无状态, 复用同一实例, KISS-DIRECT)。
class _FacadeAgent:
    """工具执行所需的最小 agent 状态面(仅保留 execute_tool 真实依赖的字段) — 小欧 2026-08-13

    - _security_hooks: execute_tool 经 getattr(agent,"_security_hooks") 读取(OCP 自定义 hooks 通道);
    - _loaded_categories/_tool_loader/_tool_cache: searchtool 自动注入路径(auto_inject_from_search)
      依赖 agent 内部状态, 属领域正确需求, 非 YAGNI 过度供给;
    - retry_engine 不再伪造为 agent 字段, 由 facade 显式构建并经 execute_tool 的 retry_engine
      显式依赖传入(A4 收尾解耦, 去除 hot-path 私有字段耦合)。
    修复: 移至模块级, 避免每次 execute_tool 调用都重建类对象(性能+可测试性) — 小沈 2026-08-13
    """

    def __init__(self):
        self._security_hooks = DefaultToolSecurityHooks()
        self._loaded_categories = set()
        self._tool_loader = ToolLoader(self)
        self._tool_cache = TTLCache(ttl=_TOOL_CACHE_TTL)


# 修复: 模块级单例 retry_engine(无状态, 复用同一实例) — 小沈 2026-08-13
_retry_engine: Optional[ToolRetryEngine] = None


def _get_retry_engine() -> ToolRetryEngine:
    global _retry_engine
    if _retry_engine is None:
        _retry_engine = ToolRetryEngine(_get_tool_dict())
    return _retry_engine


def list_tools() -> dict:
    """供 API 调用的工具列表(只读, 无安全检查) — 小欧 2026-08-12"""
    tools = tool_registry.to_openai_tools()
    result = []
    for t in tools:
        func = t.get('function', {})
        name = func.get('name', '')
        desc = func.get('description', '')
        params = func.get('parameters', {})
        required = params.get('required', [])
        props = list(params.get('properties', {}).keys())
        required_set = set(required)
        result.append({
            "name": name,
            "description": desc[:100] if desc else "",
            "required_params": required,
            "optional_params": [p for p in props if p not in required_set],
            "inputSchema": params,
        })
    return {"total": len(result), "tools": result}


async def execute_tool(tool_name: str, params: dict) -> dict:
    """供 API 调用的安全工具执行入口 — 复用 tool_executor 统一执行路径 — 小欧 2026-08-12
    [SA1] 权限信任框架第1步API入口(与safety_gate的Agent入口并列): 安全预检同源SA3 check_before_execute — 小欧-2026-10-14

    返回结构对齐 health.py 原 /tool/execute 的 ToolExecuteResponse 语义:
    {success, result | error, tool_name}
    """
    # 2026-10-18 小欧 - 归一化前置: /tool/execute 直调不经 L2 解析层, 门面层补名归一 + 参数名归一,
    #   后续 safety/sandbox/执行统一用规范名与规范参数(与 Agent 链路 L2 同口径, 否则别名漏检)。
    #   名归一提到校验前并与未注册判定合并: get_tool 内部本已归一等价, 此处收敛为单次 resolve + 用其 meta 判未知(去重复查)。
    from app.tools.registry import resolve_registered_tool
    from app.tools.tools_alias_mapper import normalize_params
    tool_name, _tool_meta = resolve_registered_tool(tool_name)

    # 0. 未注册工具早返(2026-10-18 小欧 - API 直调崩溃修复): 安全层契约假设"只放已注册工具"
    #    (未注册判定收口解析层, 见 path_tool_safety_checker 头注 —— 解析层在 Agent 链路第一步拦截),
    #    但 /tool/execute 直调不经解析层, get_tool 返回 None → check_before_execute 解引用 None
    #    (tool_meta.check_fn) 抛 AttributeError → 500(实测 POST /api/v1/tool/execute {"nonexistent"}
    #    报 Unhandled Exception)。门面层是其入口适配, 补注册校验: 未知工具返 success=False(fail-closed,
    #    与 is_success 的"工具未找到"语义一致), 缺参/未实现不进入安全层。
    if _tool_meta is None:
        logger.warning(f"[tool_facade] 未知工具, 拒绝执行: {tool_name!r}")
        return {"tool_name": tool_name, "success": False,
                "result": {}, "error": f"未知工具: {tool_name}"}

    params, _ = normalize_params(tool_name, params or {})

    # 1. 安全预检(与 action_handler.check_safety_and_confirm 同源) — 小欧 2026-08-12
    # 4.4: 池快照现取现递，与 safety_gate 同口径 — 小欧 2026-10-16
    from app.tools.fundamental.shell_engine import get_pool_pids_snapshot
    safety = get_path_tool_safety_checker().check_before_execute(tool_name, params or {}, pool_pids=get_pool_pids_snapshot())
    if safety.blocked:
        return {"tool_name": tool_name, "success": False,
                "error": f"安全拦截: {safety.message}", "safety": safety}
    if safety.requires_confirmation and not safety.auto_confirm:
        # 测试接口无前端 HITL: 仅 auto_confirm(安全开关关闭)直放, 其余返回待确认
        # 2026-10-14 北京老陈裁定: 一并回传 SafetyResult, 调用方据字段区分拦截/待确认, 不靠中文串
        # 2026-10-15 小欧 - 文档[33] 5.21-①: 本分支恒拒绝而非弹窗, 是**接口形态决定**而非漏实现 ——
        #   check_before_execute 未传 skip_confirmation, API 链无 session_id(文档[33] 4.13-2 P2-2),
        #   故 skip_confirmation 恒 False, 无法走「会话信任豁免」; 且本链无前端可裁决 HITL,
        #   等待确认只会挂死调用方, 故直接拒绝(与上方 blocked 同级降级)。
        return {"tool_name": tool_name, "success": False,
                "error": f"需要用户确认工具执行({tool_name}), 测试接口不支持交互确认",
                "safety": safety}

    # 2. 沙箱预检 + 临时授权(SA7/SA6) — 2026-10-14 小欧, 文档[33] 4.13 P3步14
    #    病根: 本链此前只做 SA3, 不做 SA7/SA6 —— destructive 操作经 API 直调可绕过影子副本预检;
    #    白名单外授权请求无人 grant, 工具体内 validate_path 二次拦截, 表现为「弹了窗但仍被拦」。
    from app.safety.sandbox.executor import get_sandbox_executor
    pre = await get_sandbox_executor().pre_execute(tool_name, params or {})
    if not pre.passed:
        # API 链无前端可裁决, needs_ruling 亦直接拒绝(不弹窗), 与上方"需确认即拒"同一降级语义
        return {"tool_name": tool_name, "success": False,
                "error": f"沙箱预检未通过: {pre.blocked_reason}", "safety": safety}
    # 授权: 白名单外写预检已放行, 但工具体内 validate_path 仍查 temp_auth → 不 grant 会二次拦截。
    #   必须带 auth_path 守卫: shell 类确认(返回的 SafetyResult 不带 auth_path)裸调会传 None。
    #   单次调用作用域: 请求结束随 ContextVar 消亡, 不跨调用(API 链自建 task_id, 无"同 task"概念)。
    if getattr(safety, "auth_path", None):
        from app.safety.temp_auth import grant_temp_auth
        grant_temp_auth(safety.auth_path, recursive=True)

    # 3. 设置任务上下文(try/finally reset, 防 ContextVar 泄漏污染并发) — 小欧 2026-08-12
    task_id = str(uuid.uuid4())
    token = _current_task_id.set(task_id)
    try:
        # 3. 复用 tool_executor(统一执行入口): 构造轻量 agent, tool_executor 内 getattr(_security_hooks)→DefaultToolSecurityHooks,
        #    并 set/finally reset 到 ContextVar hooks — 与 chat 路径共享同一 executor + hooks, 消除双路径
        from app.services.agent.tool_executor import execute_tool as _exec

        # 修复: _FacadeAgent 模块级 + _retry_engine 模块级单例, 不再每次请求重建 — 小沈 2026-08-13
        result = await _exec(_FacadeAgent(), tool_name, params or {}, _get_retry_engine())
        # 用 is_success 判定(与 chat 路径 tool_executor 同源), 避免参数失败/工具未找到被误报 success=True — 三堂会审 小欧 2026-08-13
        # 修复: result 非 dict 时判失败(原 ok=True 误报成功) — 小沈 2026-08-13
        if not isinstance(result, dict):
            return {
                "tool_name": tool_name,
                "success": False,
                "result": {},
                "error": f"工具返回非字典结果: {type(result).__name__}",
            }
        ok = is_success(result)
        return {
            "tool_name": tool_name,
            "success": ok,
            "result": result if ok else {},
            "error": "" if ok else _safe_status_message(result),
        }
    finally:
        _current_task_id.reset(token)
