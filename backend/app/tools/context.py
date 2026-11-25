# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - A1工具层上下文(A2-越层延伸): _current_task_id ContextVar 从 services/task/task_context 下沉至 tools 层,
#   消除 tools→app.services.task 越层依赖(守护测试 tools 禁 app.services 规则); services/task/task_context 改为此处的薄壳
# 2026-08-12 - 小欧 - A1后半面(4.1.7 定案): 新增 _current_hooks ContextVar(get/set/reset), 承载入口层注入的安全 hooks。
#   默认值 None, 不预置 safety 实现(避免 tools→safety 违规), 由 tool_executor/health.py 两入口显式注入。
# 2026-08-13 - 小欧 - A1 类型对齐(三堂会审: 合规无环/合理类型增强/关联零行为变化): _current_hooks 标注 object→ToolSecurityHooks,
#   与设计 4.1.7 硬伤一保持一致(Protocol 仅 import typing, 同 tools 层无越层); 默认值仍 None, tool_executor getattr or 兜底不变。
# 2026-08-13 - 小沈 - 修复(三堂会审): 新增 get_current_hooks_or_noop() 兜底返回 NoOpHooks(非 None),
#   供工具内直接调用 .record_operation()/.execute_with_safety() 消除 NPE(入口未注入场景, 如测试直接调工具函数);
#   NoOpHooks 在 tools 层自给自足, 不破坏 A1 越层隔离。6 个文件工具改用本函数。
# 2026-10-20 - 北京老陈裁定(分层) - 会话工作区快照组迁至 app/session_workspace.py(四方共用, 置中立层解 safety→tools 越层); 本模块收窄为任务ID+安全钩子, 删 _current_ws 及相关旧历史(随代码迁走)。
# 2026-10-20 15:45 小欧 - 新增 _current_text_task ContextVar(get/set/reset): 承载入口层注入的"纯文本任务LLM调用回调"
#   (同压缩摘要 call_llm_text_task 一源的封装闭包)。工具层守护禁 tools→app.services, 故不像 hooks 一样预置实现,
#   而由 tool_executor 持 agent 在入口注入; 工具(如 fetchpage prompt提取)经 get_current_text_task 消费,
#   未注入时返回 None 由工具自行降级(零越层、零预设) — 小欧-2026-10-20
# 2026-10-26 小沈 - 新增 _current_notice_callback ContextVar(get/set/reset): 承载入口层注入的"notice消息回调"
#   (同 _current_text_task 模式, tool_executor 持 agent 注入 emit_notice 包装闭包)。
#   工具经 get_current_notice_callback 消费, 未注入时返回 None 由工具自行降级(零越层) — 小沈-2026-10-26
# 2026-11-18 商量 - 新增 _current_question_callback ContextVar(get/set/reset): 承载入口层注入的"阻塞问询回调"
#   (同 _current_notice_callback 模式, tool_executor 持 agent 注入 ask_question 包装闭包)。
#   签名 async (questions: List[Dict]) -> {"answers","cancelled","expired","reason"}; 工具层零越层, 未注入自行降级
# 2026-11-19 小欧 - notice 回调签名补可选 items 结构化载荷(schedule 清单): async (kind,phase,content,items=None);
#   工具层零越层不变, 未注入自行降级。
# 2026-11-19 小欧 - notice 回调签名再补 only_event(默认 False): async (...,items=None,only_event=False);
#   仅事件列表标记, schedule error 用, 其它工具零改动。
# 2026-11-20 小欧 - 新增 _current_generate_callback(生成回调): 入口层持 agent 注入, 闭包内用当前模型凭据调
#   generation 端点, 生成图像/生成视频工具层零越层拿产物 — 小欧-2026-11-20
# 2026-11-22 小欧 - 新增 _current_precheck_info ContextVar(get/set/reset): 承载沙箱预检纯静态检查结果,
#   由 sandbox_resolve(passed=True 分支)注入, 工具(如 shell)经 get_current_precheck_info 消费——
#   预检只做静态检查不执行不弹窗不拦截, 结果经此渠道给 tool 自行处理(零越层, 未注入返回 None 自行降级)。
# 2026-11-25 商量 - 新增 _current_session_id ContextVar(get/set/reset): 发起会话ID, tool_executor 从
#   agent._start_meta 注入; timer_set 消费——定时器触发时回到发起会话创建任务(持久调度器"到点自己干")
"""

tools/context — 工具层运行上下文

职责: 承载工具执行期间的请求作用域上下文(ContextVar), 供工具/日志等读取
会话工作区快照组已迁至 app/session_workspace.py(四方共用, 置中立层解 safety→tools 越层)
小欧 2026-08-12 A1下沉
"""
from contextvars import ContextVar
from typing import Optional

from app.tools.security_hooks import (  # 修复: NoOpHooks 兜底 — 小沈 2026-08-13
    NoOpHooks,
    ToolSecurityHooks,
)

_current_task_id: ContextVar[Optional[str]] = ContextVar("tool_task_id", default=None)
_current_hooks: ContextVar[Optional[ToolSecurityHooks]] = ContextVar("current_hooks", default=None)
# "纯文本任务LLM调用回调": 入口层(tool_executor)持 agent 注入, 签名 async (messages: List[Dict]) -> str — 小欧 2026-10-20
_current_text_task: ContextVar[Optional[object]] = ContextVar("current_text_task", default=None)
# "notice消息回调": 入口层(tool_executor)持 agent 注入, 签名 async (kind: str, phase: str, content: str) -> None — 小沈 2026-10-26
_current_notice_callback: ContextVar[Optional[object]] = ContextVar("current_notice_callback", default=None)
# "阻塞问询回调": 入口层(tool_executor)持 agent 注入, 签名 async (questions: List[Dict]) -> Dict — 商量 2026-11-18
_current_question_callback: ContextVar[Optional[object]] = ContextVar("current_question_callback", default=None)
# 2026-11-20 小欧 - 生成回调: 入口层(tool_executor)持 agent 注入, 签名 async (kind, model, prompt, **kwargs)->Dict;
#   闭包内用当前模型凭据调 generation 端点, 工具层零越层(不 import services/config) — 小欧-2026-11-20
_current_generate_callback: ContextVar[Optional[object]] = ContextVar("current_generate_callback", default=None)
# 2026-11-22 小欧 - 沙箱预检纯静态检查结果: sandbox_resolve(passed=True)注入, 工具(如 shell)经 get_current_precheck_info
#   消费——预检只做静态检查不执行不弹窗不拦截, 结果经此渠道给 tool 自行处理(零越层, 未注入返回 None 自行降级)
_current_precheck_info: ContextVar[Optional[dict]] = ContextVar("current_precheck_info", default=None)
# 2026-11-25 商量 - 发起会话ID: 入口层(tool_executor)持 agent._start_meta 注入, 工具(如 timer_set)
#   经 get_current_session_id 消费——定时器触发时回到该会话创建任务; 未注入返回 None 自行降级
_current_session_id: ContextVar[Optional[str]] = ContextVar("current_session_id", default=None)

def get_current_task_id() -> Optional[str]:
    """获取当前任务的 taskId — 小沈 2026-07-30(迁自 task_context)"""
    return _current_task_id.get()


def set_current_task_id(task_id: str):
    """设置当前任务的 taskId — 小沈 2026-07-30(迁自 task_context)"""
    _current_task_id.set(task_id)


def reset_current_task_id():
    """重置当前任务的 taskId — 小沈 2026-07-30(迁自 task_context)"""
    _current_task_id.set(None)


def get_current_hooks() -> Optional[ToolSecurityHooks]:
    """获取当前作用域的安全 hooks(入口层注入) — 小欧 2026-08-12
    返回 None 表示入口未注入(正常流程下 tool_executor/health.py 均已注入)。
    """
    return _current_hooks.get()


def get_current_hooks_or_noop() -> ToolSecurityHooks:
    """获取当前作用域 hooks, 未注入时返回 NoOpHooks 兜底(非 None) — 小沈 2026-08-13 修复

    供工具内直接调用 .record_operation()/.execute_with_safety() 使用,
    消除 `None.record_operation()` NPE(入口未注入场景, 如测试直接调工具函数)。
    NoOpHooks 不依赖 safety 层, tools 自给自足, 不破坏 A1 越层隔离。
    """
    return _current_hooks.get() or NoOpHooks()


def set_current_hooks(hooks: ToolSecurityHooks):
    """设置当前作用域 hooks, 返回 token 供 reset — 小欧 2026-08-12"""
    return _current_hooks.set(hooks)


def reset_current_hooks(token) -> None:
    """恢复上一个 hooks — 小欧 2026-08-12"""
    _current_hooks.reset(token)


def get_current_text_task() -> Optional[object]:
    """获取当前作用域的纯文本任务LLM调用回调(入口层注入) — 小欧 2026-10-20
    返回 None 表示未注入(直接调工具/无agent场景), 由工具自行降级。
    """
    return _current_text_task.get()


def set_current_text_task(callable_text_task):
    """设置当前作用域的纯文本任务LLM调用回调, 返回 token 供 reset — 小欧 2026-10-20"""
    return _current_text_task.set(callable_text_task)


def reset_current_text_task(token) -> None:
    """恢复上一个纯文本任务回调 — 小欧 2026-10-20"""
    _current_text_task.reset(token)


def get_current_notice_callback() -> Optional[object]:
    """获取当前作用域的notice消息回调(入口层注入) — 小沈 2026-10-26
    返回 None 表示未注入(直接调工具/无agent场景), 由工具自行降级。
    签名: async (kind: str, phase: str, content: str, items: Optional[List[Dict]] = None,
                only_event: bool = False) -> None
    2026-11-19 小欧 - items 可选结构化载荷(schedule 清单); only_event 仅事件列表标记(默认 False)
    """
    return _current_notice_callback.get()


def set_current_notice_callback(callback):
    """设置当前作用域的notice消息回调, 返回 token 供 reset — 小沈 2026-10-26"""
    return _current_notice_callback.set(callback)


def reset_current_notice_callback(token) -> None:
    """恢复上一个notice回调 — 小沈 2026-10-26"""
    _current_notice_callback.reset(token)


def get_current_question_callback() -> Optional[object]:
    """获取当前作用域的阻塞问询回调(入口层注入) — 商量 2026-11-18
    返回 None 表示未注入(直接调工具/无agent场景), 由 question 工具自行降级。
    签名: async (questions: List[Dict]) -> Dict[str, Any]
    """
    return _current_question_callback.get()


def set_current_question_callback(callback):
    """设置当前作用域的阻塞问询回调, 返回 token 供 reset — 商量 2026-11-18"""
    return _current_question_callback.set(callback)


def reset_current_question_callback(token) -> None:
    """恢复上一个阻塞问询回调 — 商量 2026-11-18"""
    _current_question_callback.reset(token)


def get_current_generate_callback() -> Optional[object]:
    """获取当前作用域的生成回调(入口层注入) — 小欧 2026-11-20
    返回 None 表示未注入(直接调工具/无agent), 由生成工具自行降级。
    签名: async (kind: str, model: str, prompt: str, **kwargs) -> Dict[str, Any]
      kind ∈ {image, video}; model=生成模型名; kwargs: image/i2i 图源、mode(视频 t2v/i2v)、images 等
      返回 {ok, settled, url, b64, reason}
    """
    return _current_generate_callback.get()


def set_current_generate_callback(callback):
    """设置当前作用域的生成回调, 返回 token 供 reset — 小欧 2026-11-20"""
    return _current_generate_callback.set(callback)


def reset_current_generate_callback(token) -> None:
    """恢复上一个生成回调 — 小欧 2026-11-20"""
    _current_generate_callback.reset(token)


def get_current_precheck_info() -> Optional[dict]:
    """获取当前作用域的沙箱预检纯静态检查结果(入口注入) — 小欧 2026-11-22
    返回 None 表示未注入(直接调工具/无沙箱预检场景), 由工具自行降级。
    预检只做静态检查不执行不弹窗不拦截, 结果经此渠道给 tool 自行处理(零越层)。
    """
    return _current_precheck_info.get()


def set_current_precheck_info(info: Optional[dict]):
    """设置当前作用域的沙箱预检纯静态检查结果, 返回 token 供 reset — 小欧 2026-11-22"""
    return _current_precheck_info.set(info)


def get_current_session_id() -> Optional[str]:
    """获取当前发起会话ID(入口层注入) — 商量 2026-11-25
    返回 None 表示未注入(直接调工具/无agent场景), 由工具自行降级。
    """
    return _current_session_id.get()


def set_current_session_id(session_id: Optional[str]):
    """设置当前发起会话ID, 返回 token 供 reset — 商量 2026-11-25"""
    return _current_session_id.set(session_id)


def reset_current_session_id(token) -> None:
    """恢复上一个发起会话ID — 商量 2026-11-25"""
    _current_session_id.reset(token)


def reset_current_precheck_info(token) -> None:
    """恢复上一个沙箱预检纯静态检查结果 — 小欧 2026-11-22"""
    _current_precheck_info.reset(token)
