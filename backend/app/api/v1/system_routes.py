# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-16 小欧 - 新建: POST /api/v1/shutdown 优雅停机入口; 置 uvicorn Server.should_exit=True,
#   由 run_server.py 编程式启动时把 Server 挂到 app.state.uvicorn_server 供此处取用。
#   非编程式启动(裸 uvicorn app.main:app / 测试)无 Server 引用时返回 503, 引导用 关闭OmniAgent.bat。
"""system_routes — 系统级操作(优雅停机) — 小欧 2026-11-16

挂载走 main._mount 默认鉴权: 停机是高风险操作, 绝不豁免 token(区别于 /health 探活)。
"""
import threading
import time

from fastapi import APIRouter, HTTPException, Request

from app.logger import logger

router = APIRouter()


@router.post("/shutdown")
async def shutdown(request: Request) -> dict:
    """优雅停机: 触发 uvicorn 退出并走既有 lifespan shutdown(终止后台进程树/排空连接池)。

    Server 引用由 run_server.py 在 server.run() 前挂到 app.state.uvicorn_server。
    should_exit 由 uvicorn 主循环轮询, 可跨线程置位(与信号处理器同机制)。
    置位放到后台线程并延迟 0.5s: 先让本次 HTTP 响应完整返回客户端, 避免连接被提前切断。
    """
    server = getattr(request.app.state, "uvicorn_server", None)
    if server is None:
        raise HTTPException(
            status_code=503,
            detail="当前服务非编程式启动, 无法优雅停机; 请用 关闭OmniAgent.bat 或结束进程。",
        )
    logger.info("[shutdown] 收到 HTTP 停机请求, 触发优雅退出")

    def _trigger() -> None:
        time.sleep(0.5)
        server.should_exit = True

    threading.Thread(target=_trigger, daemon=True).start()
    return {"status": "shutting_down"}
