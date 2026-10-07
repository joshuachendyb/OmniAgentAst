# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 - 小欧 - StreamState 增 current_thought 字段, 运行期持有 thought 值
# 2026-07-18 - 小欧 - 消费者完全退出日志层: 删除prompt_logger全部5处引用(start_request/mark_completed/mark_error/save/import)
# 2026-07-22 - 小欧 - 修复: 模型不在 provider models 列表时, 不再抛 ValueError 致 ASGI 崩溃
#   背景: _validate_model_in_list raise ValueError → get_service() 在 generate() 外 → FastAPI 全局异常 → 长篇 traceback + 前端500
#   修复: get_service() 后通过 resolver.pop_model_warning() 获取 warning, 传入 step_start → send_start_step → MetaStep(warning=), 透传前端
#   合规: DRY + KISS + SLAP + SRP
# 2026-07-22 - 小欧 - 代码审查修复: import从函数内移至文件顶部(get_ai_config_resolver无循环依赖); validate_chat_config冗余import删除
# 2026-08-06 - 小欧 - TASK_START日志收口log_and_print统一双写: 原4条裸print(时间/TASK_START/task_id/user_input)不上日志文件+logger.info仅文件, 合并为2条log_and_print(logger.info+print双写, 首行已带完整时间戳), 修复7-23统一治理遗漏
# 2026-08-13 - 小欧 - A7(方案4.7.3步骤2): 编排逻辑一次性迁入 services/chat/stream_orchestrator.py, 本文件降为路由薄壳
#   (路由+DTO解包+调 orchestrator); 删除编排主体 generate/step_start/StreamState/_stream_with_control/chat_stream/
#   chat_stream_reconnect/generate_task_id/validate_chat_config 实现/_agent_tasks。无兼容 shim, 业务逻辑单一归属 orchestrator。
# 2026-08-14 - 小欧 - 改名名实相符: openai.py → chat_routes.py(实为自定义Chat路由薄壳, 无OpenAI协议)
# 2026-08-16 - 小欧 - S1(10.1.4②): chat_stream_endpoint 透传 request.context_link_mode 给 orchestrator(任务上下文链)
# 2026-08-19 - 小欧 - v2.0核心数据模型重构(9.6): 注册task_execution_router(C1任务详情统计+C2步骤回放,
#   嵌套于chat_router, 经main.py /api/v1前缀挂载为/api/v1/chat/execution/task/{task_id}路径)
# 2026-09-02 - 小欧 - 会话信任功能修复 v1.5 ①(北京老陈定案, 详见doc-9月优化/会话信任功能修复方案): confirm 端点调用改 `await resolve_confirmation(...)` — resolve_confirmation 由同步改 async 后, API 层路由必须 await(落库强一致, 反查失败 raise, 一处不改则运行时报错显性暴露)
# 2026-09-03 - 小欧/北京老陈 - confirm端点补日志: 改前无任何log, 问题排查全靠猜; 收到确认/确认成功/confirm_id不存在或已处理三处关键节点补info/warning
# 2026-09-03 - 小欧/北京老陈 - 后端必有返回: 全链路try兜底, 异常也返回success False, 杜绝前端await死等(北京老陈"后端不能没有返回"铁律)
# 2026-09-08 - 小欧 - 方案五(6.6.1): cancel 端点增 source query 参数(缺省 user_requested), 透传 task_runtime.cancel_task 落库; 支撑方案四断连超时来源区分
# 2026-09-08 - 小欧 - 北京老陈指令(console可见性): cancel 端点补 logger.info(仅文件, 不双写; 双写仅疑点5处)。
#   [背景] cancel 链路可靠日志已有: task_runtime.cancel_task 双写 + http关闭 info; 本处补 API 层入口留痕
#   (task_id/session_id/source), 排查"前端是否真发了取消"不再靠猜 — 小欧-2026-09-08
# 2026-09-19 - 小欧 - P-005契约化(北京老陈批准): confirm端点 confirm_id失效响应补 code="confirm_stale" 稳定字段,
#   前端改读 code 判定(替代字符串includes匹配), 从源头消除"后端message文案变更即前端失效"的脆弱链 — 小欧-2026-09-19
# 2026-09-29 小欧 - 重连端点包一层 _guarded 生成器兜住回放异常→persistence_degraded（不掐断流）。
#   try 须写在生成器体内：路由本身不迭代生成器，在路由层 try 捕不到。CancelledError 不捕 — 小欧 2026-09-29
# 2026-10-03 - 小欧 - 文档[4] 5.7 项7: /chat/stream 停止向编排器透传 context_link_mode(形参已废止)
# 2026-10-03 - 小欧 - 文档[4] 5.7.14 单元2: /chat/stream 改以关键字透传 link_enabled(会话 link 开关
#   开关真值随消息到达), 关键字传防与编排器后续新增形参错位。
"""
chat_routes — Chat API 路由薄壳（A7 后仅保留路由与 DTO 解包）

编排逻辑迁至 services/chat/stream_orchestrator.py（方案4.7.3）
小健 - 2026-06-07 清理:删除save_step_to_db调用,改用统一save_execution_steps_to_db
"""
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.logger import logger  # 2026-09-08 小欧: cancel峰值入口留痕(仅文件, 不双写) — 小欧-2026-09-08

from app.api.v1.chat.models import ChatRequest
from app.services.chat.stream_orchestrator import (
    chat_stream_orchestrator,
    chat_stream_reconnect_orchestrator,
    validate_chat_config,
)
from app.services.chat.sse_events import create_error_response   # [63] 3.6.6 统一错误事件（定义 sse_events:47）
from app.services.task.task_runtime import cancel_task
from app.services.task.task_registry import pause_task, resume_task
from app.services.task.hitl_confirmation import resolve_confirmation
from app.api.v1.chat.task_execution import router as task_execution_router  # v2.0 C1/C2 — 小欧 2026-08-19

router = APIRouter()
task_router = APIRouter()
router.include_router(task_execution_router, tags=["task-execution"])  # v2.0 C1/C2 注册 — 小欧 2026-08-19


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    # DTO 在 API 层解包，避免 services 层反向依赖 api/v1 — 方案4.7.3 DTO边界约定
    # link_enabled 用关键字传, 防与编排器后续新增形参错位 — 小欧 2026-10-03
    return StreamingResponse(
        chat_stream_orchestrator(
            request.messages,
            request.session_id,
            link_enabled=request.link_enabled,
            allow_interject=request.allow_interject,   # 2026-10-06 小欧 - 文档[11] 3.4.4: 关键字透传(防与编排器形参错位)
        ),
        media_type="text/event-stream",
    )


@task_router.post("/chat/stream/cancel/{task_id}")
async def cancel_stream_endpoint(task_id: str, session_id: Optional[str] = None, source: str = "user_requested"):
    """取消任务 — source 区分取消来源(A人工 user_requested / 方案四断连超时 client_disconnect_timeout 等), 随取消请求落库 — 北京老陈 2026-09-08 小欧"""
    logger.info(f"[Cancel] 收到取消请求 task={task_id}, session={session_id or '-'}, source={source}")  # 2026-09-08 小欧: API入口留痕(仅文件) — 小欧-2026-09-08
    return await cancel_task(task_id, session_id, source)


@task_router.post("/chat/stream/pause/{task_id}")
async def pause_stream_endpoint(task_id: str, session_id: Optional[str] = None):
    return await pause_task(task_id, session_id)


@task_router.post("/chat/stream/resume/{task_id}")
async def resume_stream_endpoint(task_id: str, session_id: Optional[str] = None):
    return await resume_task(task_id, session_id)


@task_router.post("/chat/stream/confirm")
async def confirm_stream_endpoint(request: Request):
    # 2026-09-03 小欧/北京老陈: confirm端点补日志 — 改前无任何log, 问题排查全靠猜
    # 2026-09-03 小欧/北京老陈: 后端必有返回 — 全链路try兜底, 异常也返回success False, 杜绝前端await死等
    from app.logger import logger as _log
    try:
        body = await request.json()
        confirm_id = body.get("confirm_id")
        confirmed = body.get("confirmed", True)
        trust_session = body.get("trust_session", False)

        if not confirm_id:
            _log.warning("[HITL-confirm] 缺少confirm_id")
            return {"success": False, "error": "missing confirm_id"}

        _log.info(f"[HITL-confirm] 收到确认: confirm_id={confirm_id}, confirmed={confirmed}, trust_session={trust_session}")
        ok = await resolve_confirmation(confirm_id, confirmed, trust_session)  # 5.1(2026-09-02 小欧): resolve 改 async, await 同步落库零竞态

        if not ok:
            _log.warning(f"[HITL-confirm] confirm_id不存在或已处理: confirm_id={confirm_id}")
            return {"success": False, "error": "confirm_id not found or already processed", "code": "confirm_stale"}

        _log.info(f"[HITL-confirm] 确认成功: confirm_id={confirm_id}")
        return {"success": True}
    except Exception as e:
        _log.error(f"[HITL-confirm] 异常: {e!r}")
        return {"success": False, "error": str(e)}


@router.get("/chat/validate")
async def validate_config_endpoint():
    return await validate_chat_config()


@router.get("/chat/stream/{task_id}")
async def chat_stream_reconnect(
    task_id: str,
    # Optional 而非 str：可缺省（缺失时归属无从校验，后端放行并留日志）— 小欧 2026-09-29
    session_id: Optional[str] = None,
    after_seq: int = Query(0, ge=0, description="续传起点(seq>=N)；禁负数否则首帧被误判缺口"),
):
    """SSE 重连端点：读同一任务的流态缓冲，不启动新 agent — 北京老陈 2026-07-12 小欧 2026-07-12"""
    # try 须写在 async generator 体内才有效（路由不迭代生成器，捕不到执行期异常）— 小欧 2026-09-29
    async def _guarded():
        try:
            async for chunk in chat_stream_reconnect_orchestrator(task_id, session_id, after_seq):
                yield chunk
        except Exception as exc:   # 仅兜回放异常；CancelledError（客户端断开）不捕，既有取消语义不变
            logger.warning(f"[SSE] 回放异常(task={task_id}): {exc}")   # logger :38 既有 import
            yield create_error_response(error_type="persistence_degraded",
                                        error_message="回放异常，实时流不受影响")
    return StreamingResponse(_guarded(), media_type="text/event-stream")