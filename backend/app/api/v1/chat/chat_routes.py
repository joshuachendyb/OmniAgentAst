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
# 2026-10-30 - 小欧 - 注释缩进修正(零逻辑): refs 关键字透传注释缩进对齐, 无行为变化 — 小欧-2026-10-30
# 2026-11-03 - 小欧 - [HITL-confirm] 缺 confirm_id / 已处理 两处 WARNING→DEBUG(请求侧参数问题) — 小欧-2026-11-03
# 2026-11-18 - 商量 - 新增 /chat/stream/answer 端点: question 工具答案收口, 与 confirm 端点同构(必有返回+失效码)
# 2026-11-24 - 商量 - 新增 GET /chat/events 全局生命周期事件流(SSE): 广播 task_started/task_ended/
#   task_status_changed/hitl_pending/hitl_settled 信封, 前端一条常驻连接即时接流; 替代 ChatPage 每 3 秒
#   查库轮询发现"后台 shell 完成续跑新建 task_id"。可靠性靠"信封可丢 + 重连对账", 不挂 seq/Journal
#   (与 /chat/stream/{task_id} 的内容流职责正交)
"""
chat_routes — Chat API 路由薄壳（A7 后仅保留路由与 DTO 解包）

编排逻辑迁至 services/chat/stream_orchestrator.py（方案4.7.3）
小健 - 2026-06-07 清理:删除save_step_to_db调用,改用统一save_execution_steps_to_db
"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.api.v1.chat.models import ChatRequest
from app.api.v1.chat.task_execution import (
    router as task_execution_router,  # v2.0 C1/C2 — 小欧 2026-08-19
)
from app.logger import (
    logger,  # 2026-09-08 小欧: cancel峰值入口留痕(仅文件, 不双写) — 小欧-2026-09-08
)
from app.services.chat.sse_events import (
    create_error_response,  # [63] 3.6.6 统一错误事件（定义 sse_events:47）
)
from app.services.chat.stream_orchestrator import (
    chat_stream_orchestrator,
    chat_stream_reconnect_orchestrator,
    validate_chat_config,
)
from app.services.task.event_bus import HEARTBEAT_SECONDS, bus  # 商量 2026-11-24: 全局生命周期事件流
from app.services.task.hitl_confirmation import list_pending_confirmations, resolve_confirmation
from app.services.task.hitl_question import list_pending_questions, resolve_question  # 2026-11-18 商量 - question 答案收口; 2026-11-24 增 list_pending_questions(待处理项对账)
from app.services.task.task_registry import pause_task, resume_task
from app.services.task.task_runtime import cancel_task

router = APIRouter()
task_router = APIRouter()
router.include_router(task_execution_router, tags=["task-execution"])  # v2.0 C1/C2 注册 — 小欧 2026-08-19


@router.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    # DTO 在 API 层解包，避免 services 层反向依赖 api/v1 — 方案4.7.3 DTO边界约定
    # link_enabled 用关键字传, 防与编排器后续新增形参错位 — 小欧 2026-10-03
    # 2026-10-13 小欧 - 文档[28] 4.1.6: refs 同样关键字透传，禁位置传参。
    #   必须在 API 层 model_dump 成 dict —— message_builder._render_refs_block 收 dict，
    #   直接透传 pydantic ChatRef 对象会被 isinstance(data, dict) 判定**整条丢弃**，
    #   功能表面接通实则全程空转（真实 BUG：单测喂自造 dict，全链路从未跑过）。
    #   这也正是本仓 DTO 边界约定：DTO 在 API 层解包，services 层不感知 pydantic。
    return StreamingResponse(
        chat_stream_orchestrator(
            request.messages,
            request.session_id,
            link_enabled=request.link_enabled,
            allow_interject=request.allow_interject,   # 2026-10-06 小欧 - 文档[11] 3.4.4: 关键字透传(防与编排器形参错位)
            refs=[r.model_dump() for r in (request.refs or [])],
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
            _log.debug("[HITL-confirm] 缺少confirm_id")  # 2026-11-03 小欧: 请求参数缺失, 降 DEBUG
            return {"success": False, "error": "missing confirm_id"}

        _log.info(f"[HITL-confirm] 收到确认: confirm_id={confirm_id}, confirmed={confirmed}, trust_session={trust_session}")
        ok = await resolve_confirmation(confirm_id, confirmed, trust_session)  # 5.1(2026-09-02 小欧): resolve 改 async, await 同步落库零竞态

        if not ok:
            _log.debug(f"[HITL-confirm] confirm_id不存在或已处理: confirm_id={confirm_id}")  # 2026-11-03 小欧: 资源状态, 降 DEBUG
            return {"success": False, "error": "confirm_id not found or already processed", "code": "confirm_stale"}

        _log.info(f"[HITL-confirm] 确认成功: confirm_id={confirm_id}")
        return {"success": True}
    except Exception as e:
        _log.error(f"[HITL-confirm] 异常: {e!r}")
        return {"success": False, "error": str(e)}


@task_router.post("/chat/stream/answer")
async def answer_question_endpoint(request: Request):
    """question 工具答案收口 — 商量 2026-11-18; 与 confirm 端点同构, 异常必有返回"""
    from app.logger import logger as _log
    try:
        body = await request.json()
        question_id = body.get("question_id")
        answers = body.get("answers") or []
        cancelled = bool(body.get("cancelled", False))

        if not question_id:
            _log.debug("[question-answer] 缺少 question_id")
            return {"success": False, "error": "missing question_id"}

        _log.info(f"[question-answer] 收到回答: question_id={question_id}, count={len(answers)}, cancelled={cancelled}")
        ok = await resolve_question(question_id, answers=answers, cancelled=cancelled)
        if not ok:
            _log.debug(f"[question-answer] question_id不存在或已处理: question_id={question_id}")
            return {"success": False, "error": "question_id not found or already processed", "code": "question_stale"}
        _log.info(f"[question-answer] 回答成功: question_id={question_id}")
        return {"success": True}
    except Exception as e:
        _log.error(f"[question-answer] 异常: {e!r}")
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


# ============================================================
# 全局生命周期事件流 — 商量 2026-11-24
# ============================================================

def _sse_frame(ev: dict) -> str:
    """信封 → SSE 单帧。仅 data 行(前端 processSSEData 只消费 data:), type 在 JSON 内
    (与 /chat/stream 的 event: 行风格不同, 因为前端这个流是独立解析器) — 商量 2026-11-24"""
    return f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"


async def _heartbeat_pump(q: "asyncio.Queue[dict]") -> None:
    """心跳泵: 定时往订阅队列塞 ping — 商量 2026-11-24

    一举两得: ①保活防中间代理按 idle 超时切流; ②让主循环的 q.get() 最多阻塞 HEARTBEAT_SECONDS,
    从而让 request.is_disconnected() 有机会被检查到(否则客户端半开连接会让协程永久挂住)。
    不注入 bus 的 ring 缓冲(它是传输层心跳, 不是业务事件)。
    """
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        try:
            q.put_nowait({"event_id": -1, "type": "ping", "session_id": None, "data": {}})
        except asyncio.QueueFull:
            pass  # 队列满说明消费者已滞后, 下一拍再试即可


@router.get("/chat/events")
async def chat_events_stream(
    request: Request,
    last_event_id: int = Query(0, ge=0, description="重连补发起点: ring 内 event_id > N 的信封"),
    epoch: Optional[int] = Query(None, description="总线纪元; 与当前不符(进程已重启)则忽略 last_event_id"),
):
    """全局生命周期事件流(SSE) — 商量 2026-11-24

    职责: 广播"变了"的信封(task 起停/状态变更/HITL 待处理), 让前端即时接流, 替代 3 秒查库轮询。
    与 GET /chat/stream/{task_id} 的分工(两者不可合并):
      本端点 = 变更通知, 无 seq 不落库, **允许丢**;
      任务流 = AI 正文, 有 seq + Journal + after_seq 续传, 不许丢。
    可靠性靠"重连对账"(前端连上后拉 GET /sessions/tasks/running 与本地锚点比对)
    """
    async def _gen():
        q = bus.subscribe()
        heartbeat = asyncio.create_task(_heartbeat_pump(q))
        try:
            # 首帧声明 epoch: 前端据此判断手里的 last_event_id 是否还属于当前总线
            yield _sse_frame({"event_id": 0, "type": "ready", "session_id": None,
                              "data": {"epoch": bus.epoch}})
            # 补发: epoch 不符(进程重启过)则忽略 last_event_id, 交由前端对账
            if epoch is None or epoch == bus.epoch:
                for _ev in bus.replay_since(last_event_id):
                    yield _sse_frame(_ev)
            while True:
                if await request.is_disconnected():
                    break
                _ev = await q.get()   # 心跳保证 ≤ HEARTBEAT_SECONDS 必返回, 断开不会被无限挂住
                yield _sse_frame(_ev)
        except asyncio.CancelledError:
            raise               # 客户端断开走正常取消语义, 不吞
        except Exception as exc:  # 单条连接异常不得影响总线与其他连接
            logger.warning(f"[EventBus] 事件流异常: {exc}")
        finally:
            heartbeat.cancel()
            bus.unsubscribe(q)

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 反代/nginx 不缓冲, 否则信封被攒成一坨才下发
        },
    )


@router.get("/chat/hitl/pending")
async def hitl_pending_endpoint(session_id: Optional[str] = None):
    """HITL 待处理项权威快照 — 商量 2026-11-24

    为什么需要它: hitl_pending 信封允许丢(信封可丢模型), 断线期间产生的待确认/待回答
    若只靠信封, 重连后就再也想不起来。本端点是"重连对账 + 首次加载"的真相源。

    与信封的分工(不可混): 信封只报"变了"(带 hitl_id + 定位), 详情(params/题目正文/安全级别)
    由内容流的 interact 帧提供; 本端点同信封口径, 只返回 id + 定位, 不搬运弹窗正文。

    session_id 可选: 传则只返回该会话的项(会话页用), 不传返回全部(顶栏角标用)。
    """
    try:
        items = list_pending_confirmations() + list_pending_questions()
        if session_id:
            items = [i for i in items if i.get("session_id") == session_id]
        items.sort(key=lambda i: i.get("created_at", 0))
        return {"success": True, "items": items, "count": len(items)}
    except Exception as e:  # 后端必有返回(北京老陈铁律), 异常不得让前端 await 死等
        logger.warning(f"[HITL] 待处理项查询失败: {e!r}")
        return {"success": False, "items": [], "count": 0, "error": str(e)}
