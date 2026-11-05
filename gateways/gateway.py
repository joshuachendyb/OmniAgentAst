# -*- coding: utf-8 -*-
"""gateway.py — FastAPI 应用与路由（薄: 校验 → 调用 → 打包; 通用层零方言）。

编写人: 小欧    创建时间: 2026-11-05 09:10:00
本文件不得出现下游路由字符串: 除本行外 grep 下游路由前缀应为 0。
启动即走 preflight(): 回环 + token + deny * + 驱动可装载, 任一失败拒绝启动。

编辑历史:
  2026-11-05 向下翻译收口 mapping.build_prompt; usage 计量迁 upward; 思考段经 assistant_reasoning 透传 -- 小欧
  2026-11-05 GatewayError 统一落日志(含 detail); 429 冷却由 _mapped_error 记账; 冷却只拦调模型 -- 小欧
  2026-11-05 命名对齐: _plain_chat→_complete_once, _stream_tools→_replay_tools_as_sse, _frames→_frame_of -- 小欧
  2026-11-05 命名对齐: _model_guard→_check_model_exists, _gate→_gateway_error_response; 删本文件 DRV 副本 -- 小欧
  2026-11-05 安全闸门提前到导入期(原挂 lifespan, --lifespan off/mount 下完全不执行) -- 小欧
  2026-11-05 _complete_once 全异步(同步 httpx 阻塞事件循环); 流式 release 移交 _SseResponse 必达 -- 小欧
  2026-11-05 读完 body 复检体积; 入参形状 400(原裸 traceback 500); 提交后错误记 ERROR 收口 -- 小欧
  2026-11-05 read 超时抬到静默窗之上; 启动清运过期日志; ordinal 缺失按哨兵键去重 -- 小欧
  2026-11-05 注释规范化: 压缩到两行内并统一署名日期 -- 小欧
  2026-11-05 运行期文案去节号: 413 体积上限、删会话失败 WARN -- 小欧
"""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import sys
import time
import uuid

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

import errors
import mapping
import upward
import streamer
from cli_manager import (CliManager, SESSION_PERMISSIONS, FROZEN,
                         runtime_dir, preflight)
from errors import GatewayError

APP = FastAPI(title="opencli-gateway", version="1.0.0")

_MAX_BODY_BYTES = 32 * 1024 * 1024        # 体积门: 请求体 ≤ 32 MB — 小欧 2026-11-05
_MANAGER = None                           # 唯一持有者: 驱动实例在 _MANAGER.driver（见文件末 _boot）— 小欧 2026-11-05


def _load_config(path):
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


CFG = _load_config(os.path.join(runtime_dir(), "config.json"))


def _err(status, etype, message, detail="", retry_after_s=None):
    """唯一 HTTP 错误出口: 一律走统一信封, 本文件禁止裸 JSONResponse 报错。— 小欧 2026-11-05"""
    code, headers, body = errors.make_error(status, etype, message, detail,
                                            retry_after_s)
    return JSONResponse(body, status_code=code, headers=headers)


def _log_error(exc: GatewayError, note=""):
    """错误统一落日志（detail 截 300）; note 标注处置差异（如响应头已提交）。— 小欧 2026-11-05"""
    _log("ERR %d %s %s detail=%s%s"
         % (exc.status, exc.etype, exc.message, str(exc.detail or "-")[:300],
            (" " + note) if note else ""))


def _gateway_error_response(exc: GatewayError):
    """GatewayError 唯一出口: 先落日志再出信封（原实现错误零日志, 429 冷却无从取证）— 小欧 2026-11-05"""
    _log_error(exc)
    return _err(exc.status, exc.etype, exc.message, exc.detail, exc.retry_after_s)


def _shape_problem(payload):
    """入参形状闸: 坏形状按 400 拒收, 避免裸 AttributeError 成 500 traceback。
    只校验下游翻译会无条件取用的形状, 多给字段一律放行。— 小欧 2026-11-05"""
    tools = payload.get("tools")
    if tools is not None and not isinstance(tools, list):
        return "tools 必须是数组"
    for item in tools or []:
        fn = item.get("function") if isinstance(item, dict) else None
        if not isinstance(fn, dict) or not isinstance(fn.get("name"), str) or not fn["name"]:
            return "tools[].function.name 必须是非空字符串"
        if fn.get("parameters") is not None and not isinstance(fn["parameters"], dict):
            return "tools[].function.parameters 必须是对象"
    for idx, msg in enumerate(payload.get("messages") or []):
        if not isinstance(msg, dict):
            return "messages[%d] 必须是对象" % idx
        role = msg.get("role")
        if role is not None and not isinstance(role, str):
            return "messages[%d].role 必须是字符串" % idx
        content = msg.get("content")
        if content is None or isinstance(content, str):
            continue
        if not isinstance(content, list):
            return "messages[%d].content 必须是字符串或数组" % idx
        for seg in content:
            if not isinstance(seg, dict):
                return "messages[%d].content[] 必须是对象" % idx
            if seg.get("type") == "text" and not isinstance(seg.get("text"), (str, type(None))):
                return "messages[%d].content[].text 必须是字符串" % idx
            if seg.get("type") == "image_url" and not isinstance(seg.get("image_url"), dict):
                return "messages[%d].content[].image_url 必须是对象" % idx
        for call in msg.get("tool_calls") or []:
            fn = call.get("function") if isinstance(call, dict) else None
            if not isinstance(fn, dict):
                return "messages[%d].tool_calls[].function 必须是对象" % idx
    return ""


def _mapped_error(mapped):
    """驱动映射 dict → GatewayError; 429 free-limit 顺手记内部冷却 — 小欧 2026-11-05"""
    if mapped["status"] == 429:
        _MANAGER.note_cooldown(mapped["internal_cooldown_ms"])
    return GatewayError(mapped["status"], mapped["type"], mapped["message"], mapped["detail"])


def _check_token(request):
    """Bearer + hmac.compare_digest 防时序侧信道。/healthz 免鉴权。— 小欧 2026-11-05"""
    expect = "Bearer " + CFG["token"]
    got = request.headers.get("Authorization", "")
    if not hmac.compare_digest(expect.encode("utf-8"), got.encode("utf-8")):
        return _err(401, "auth", "网关鉴权失败，请核对 api_key")
    return None


def _log(line):
    """日志规范: 永不写 token/密码/正文; 下游错误原文必须落（截 500 字）。
    文件 logs/gateway-YYYY-MM-DD.log 按天切分, 过期清运在启动期做。— 小欧 2026-11-05"""
    logs_dir = os.path.join(runtime_dir(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    path = os.path.join(logs_dir, "gateway-%s.log" % time.strftime("%Y-%m-%d"))
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("%s %s\n" % (time.strftime("%H:%M:%S"), str(line)[:2000]))
    except OSError:
        pass                             # 日志失败不阻断业务 — 小欧 2026-11-05


def _prune_logs():
    """启动清运: 删除 mtime 超过 log_keep_days 的 gateway-*.log — 小欧 2026-11-05"""
    keep = int(CFG.get("log_keep_days", 7))
    cutoff = time.time() - keep * 86400
    logs_dir = os.path.join(runtime_dir(), "logs")
    try:
        names = os.listdir(logs_dir)
    except OSError:
        return
    for name in names:
        if not (name.startswith("gateway-") and name.endswith(".log")):
            continue
        try:
            path = os.path.join(logs_dir, name)
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            pass


def _boot():
    """导入期安全闸门 + 池构造: 失败直接 raise 拒绝启动。
    原实现只挂 lifespan startup, --lifespan off / 被 mount / ASGITransport 直调时闸门不执行。— 小欧 2026-11-05"""
    problems = preflight(CFG)            # 代码级安全闸门 — 小欧 2026-11-05
    if problems:
        for line in problems:
            print("[preflight] " + line, file=sys.stderr)
        raise RuntimeError("安全闸门未通过，拒绝启动（详见 stderr）")
    _prune_logs()
    manager = CliManager(CFG)            # 复用已被 preflight 装载的驱动单例
    manager.start_reaper()               # 不依赖 lifespan: --lifespan off 时清扫照样跑 — 小欧 2026-11-05
    return manager


@APP.on_event("shutdown")
def _shutdown():
    if _MANAGER is not None:
        _MANAGER.shutdown()              # 网关退出 → 全部下游 terminate — 小欧 2026-11-05


@APP.get("/healthz")
def healthz():
    """/healthz: 聚合池状态、候选明细、冷却与退避。免鉴权 → 绝不含密钥。— 小欧 2026-11-05"""
    if _MANAGER is None:                 # 闸门被跳过时的降级形态, 不抛 500 — 小欧 2026-11-05
        return {"status": "down", "cli": "down",
                "version": "opencli-gateway 1.0.0",
                "detail": "网关未初始化（安全闸门未通过）"}
    snap = _MANAGER.health_snapshot()
    snap["version"] = "opencli-gateway 1.0.0"
    snap["model_source"] = "opencli 通过 %s 驱动接入本地 CLI（免费层）" % _MANAGER.driver.name
    return snap


@APP.get("/v1/models")
def list_models(request: Request):
    """模型发现。占用实例 → 按需启动（cli=idle 不是错误）。
    本端点同样必须过 Bearer token 门, 无/错 token 一律 401。— 小欧 2026-11-05"""
    denied = _check_token(request)
    if denied is not None:
        return denied                    # 鉴权失败先于其它判定 — 小欧 2026-11-05
    if _MANAGER is None:
        return _err(503, "server", "网关未初始化（安全闸门未通过）")
    try:
        inst = _MANAGER.acquire()
    except GatewayError as exc:
        return _gateway_error_response(exc)
    client = None
    try:
        inst.start()
        client = inst.http()
        resp = client.get(_MANAGER.driver.path_models(), timeout=10)
        if resp.status_code != 200:
            raise GatewayError(502, "server", "模型发现失败 HTTP %d" % resp.status_code,
                            resp.text[:500])
        items, skipped = _MANAGER.driver.models_from(resp.json())
        if skipped:
            _log("WARN models: %d 项缺 id 被跳过（宿主会静默丢弃）"
                 % skipped)
        _MANAGER.note_success()          # 成功即清零失败计数 — 小欧 2026-11-05
        return {"object": "list", "data": items}
    except GatewayError as exc:
        _MANAGER.on_downstream_failure(exc.etype)
        return _gateway_error_response(exc)
    except httpx.HTTPError as exc:    # 传输层异常归一 502 network — 小欧 2026-11-05
        _MANAGER.on_downstream_failure("network")              # 原样穿透会成 500 裸 traceback
        return _err(502, "network", "下游连接级失败（连接/超时）", repr(exc)[:300])
    finally:
        if client is not None:
            client.close()
        _MANAGER.release(inst)
@APP.post("/v1/chat/completions")
async def chat(request: Request):
    """/v1/chat/completions。分流: stream × tools 四象限;
    (1,1) 走整包再出帧, (0,1)/(0,0) 走非流式时序, (1,0) 走延迟提交流。— 小欧 2026-11-05"""
    denied = _check_token(request)
    if denied is not None:
        return denied                     # 鉴权失败先于其它判定 — 小欧 2026-11-05
    if _MANAGER is None:
        return _err(503, "server", "网关未初始化（安全闸门未通过）")
    if int(request.headers.get("content-length") or 0) > _MAX_BODY_BYTES:
        return _err(413, "gateway-too-large", "请求体超过 32 MB（体积上限）")
    raw = await request.body()
    if len(raw) > _MAX_BODY_BYTES:        # chunked 无 Content-Length: 读完复检 — 小欧 2026-11-05
        return _err(413, "gateway-too-large", "请求体超过 32 MB（体积上限）")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _err(400, "gateway-bad-request", "请求体不是合法 JSON")
    if not isinstance(payload, dict):
        return _err(400, "gateway-bad-request", "请求体必须是 JSON 对象")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return _err(400, "gateway-bad-request", "缺失必需字段 messages")
    if len(messages) > mapping.MAX_MESSAGES:
        return _err(400, "gateway-bad-request",
                    "messages 超过 %d 条上限" % mapping.MAX_MESSAGES)
    problem = _shape_problem(payload)
    if problem:
        return _err(400, "gateway-bad-request", "请求入参形状不合法", problem)
    for warn in mapping.collect_param_warns(payload):
        _log("WARN " + warn)              # 采样参数只 WARN, 不影响响应 — 小欧 2026-11-05

    tools = payload.get("tools") or []
    # 向下翻译唯一入口: 工具模式 1系统→2工具清单→3对话(+4压轴)→5行动提醒;
    # 纯文本 1系统→3/4对话（不追加任何尾句）— 小欧 2026-11-05
    prompt, attachments = mapping.build_prompt(messages, tools)

    try:
        _MANAGER.ensure_not_cooling()         # 只拦调模型; 模型发现不耗额度 — 小欧 2026-11-05
        inst = await asyncio.to_thread(_MANAGER.acquire)   # 池满会排队, 不能占事件循环 — 小欧 2026-11-05
    except GatewayError as exc:
        return _gateway_error_response(exc)
    handed_off = False
    try:
        if payload.get("stream"):
            if tools:                     # 起始标记可能在任意位置, SSE 无法回滚 — 小欧 2026-11-05
                return await _replay_tools_as_sse(inst, payload, prompt, attachments, tools)
            resp = await _stream_text(inst, payload, prompt, attachments)
            handed_off = True             # 释放权交给 _SseResponse: 流式体结束才 release — 小欧 2026-11-05
            return resp
        return await _complete_once(inst, payload, prompt, attachments, tools)
    except GatewayError as exc:
        await asyncio.to_thread(_MANAGER.on_downstream_failure, exc.etype)  # 计数达阈值会 stop 进程
        return _gateway_error_response(exc)
    except httpx.HTTPError as exc:    # 提交前的传输层异常归一信封 — 小欧 2026-11-05
        await asyncio.to_thread(_MANAGER.on_downstream_failure, "network")
        return _err(502, "network", "下游连接级失败（连接/超时）", repr(exc)[:300])
    finally:
        if not handed_off:
            _MANAGER.release(inst)
# —— 非流式整包 ——

async def _complete_once(inst, payload, prompt, attachments, tools):
    """一次完整下游往返: (0,0)/(0,1) 直接返, (1,1) 由 _replay_tools_as_sse 复用它再切帧。
    全异步: /wait 最长 900 s, 同步 httpx 会把事件循环整段挂住。— 小欧 2026-11-05"""
    model = str(payload.get("model") or "")
    client = None                      # aclient() 必须晚于 start() — 小欧 2026-11-05
    rid = "req_" + uuid.uuid4().hex[:8]
    started = time.time()
    sid = ""
    try:
        await asyncio.to_thread(inst.start)   # 按需启动: spawn + 就绪轮询是阻塞调用 — 小欧 2026-11-05
        # aclient() 的 auth 在客户端创建时即定型, 必须晚于 start() 捕获密码。
        # 否则冷启动后首个请求 auth 为空 → 下游 401。— 小欧 2026-11-05
        client = inst.aclient()
        err = await _check_model_exists(client, model)    # 未知模型 → 404（见函数）— 小欧 2026-11-05
        if err is not None:
            raise err
        body = _MANAGER.driver.session_body(model, SESSION_PERMISSIONS)    # 会话权限由驱动组装
        resp = await client.post(_MANAGER.driver.path_create(), json=body, timeout=10)
        if resp.status_code >= 300:
            raise GatewayError(502, "server", "建会话失败 HTTP %d" % resp.status_code,
                            resp.text[:500])
        sid = resp.json()["data"]["id"]   # 网关自建会话, 不复用不透传 — 小欧 2026-11-05

        prompt_body = _MANAGER.driver.prompt_body(prompt, attachments)
        resp = await client.post(_MANAGER.driver.path_prompt(sid), json=prompt_body,
                                 timeout=30)
        if resp.status_code >= 300:
            raise GatewayError(502, "server", "发消息失败 HTTP %d" % resp.status_code,
                            resp.text[:500])

        wait_path, wait_ok = _MANAGER.driver.path_wait(sid)          # 阻塞式等待
        resp = await client.post(wait_path, timeout=900)  # 服务端阻塞直至空闲
        if resp.status_code not in wait_ok:
            raise GatewayError(502, "server", "等待完成失败 HTTP %d" % resp.status_code,
                            resp.text[:500])

        # 定向查询: path 与参数由驱动给, 比全量拉取省报文 — 小欧 2026-11-05
        msg_path, msg_params = _MANAGER.driver.path_messages(sid)
        resp = await client.get(msg_path, params=msg_params, timeout=10)
        if resp.status_code >= 300:
            raise GatewayError(502, "server", "取消息失败 HTTP %d" % resp.status_code,
                            resp.text[:500])
        items = resp.json().get("data") or []
        assistant = items[0] if items else {}
        if assistant.get("error"):
            raise _mapped_error(_MANAGER.driver.map_error(assistant["error"]))

        content = _MANAGER.driver.assistant_content(assistant)
        reasoning = _MANAGER.driver.assistant_reasoning(assistant)      # 思考段上翻（无则空串）
        finish = _MANAGER.driver.finish_reason(assistant)
        message, finish_reason = {"role": "assistant"}, finish
        if reasoning:
            message["reasoning_content"] = reasoning

        if tools:
            parsed = upward.parse_calls(content, tools)     # 工具分支
            for warn in parsed["warns"]:                # 成功/降级都要写日志, 防静默
                _log("WARN " + warn)
            if parsed["calls"]:
                message["content"] = parsed["content"]
                message["tool_calls"] = parsed["calls"]
                finish_reason = "tool_calls"
            elif parsed["content"]:
                message["content"] = parsed["content"]  # 协议失败降级为文本
            else:
                raise GatewayError(502, "server",
                                "模型未按工具协议响应，请重试或更换模型",
                                "calls=0 invalid=%d" % parsed["invalid"])
        else:
            if not content:                             # 空响应
                raise GatewayError(502, "server",
                                "下游未返回内容（模型可能尝试了被禁用的内置工具）")
            message["content"] = content

        usage = upward.usage_from_counts(_MANAGER.driver.token_counts(assistant))   # 缺计数 → null
        # stream 值按请求实报: 硬编码 0 会把流式排障带偏 — 小欧 2026-11-05
        _log("%s model=%s stream=%d out_chars=%d tool_calls=%d usage=%s elapsed=%.1fs"
             % (rid, model, 1 if payload.get("stream") else 0, len(content),
                int(bool(message.get("tool_calls"))),
                ("p%d/c%d" % (usage["prompt_tokens"], usage["completion_tokens"]))
                if usage else "null", time.time() - started))
        inst.touch()                                    # 重置任务窗口 — 小欧 2026-11-05
        _MANAGER.note_success()                         # 成功收口 → 计数清零/退避复位 — 小欧 2026-11-05
        return JSONResponse({
            "id": "chatcmpl-" + uuid.uuid4().hex[:8],
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": message,
                         "finish_reason": finish_reason}],
            "usage": usage,
        })
    finally:
        if client is not None:
            await _cleanup_session_async(client, sid)   # finally 必达 — 小欧 2026-11-05
            await client.aclose()
# —— 流式（延迟提交 + 转发表 + 工具模式整包） ——

async def _replay_tools_as_sse(inst, payload, prompt, attachments, tools):
    """(stream=1, tools) 象限: 整包解析后一次性发帧, 不边流边判。— 小欧 2026-11-05"""
    base = await _complete_once(inst, payload, prompt, attachments, tools)
    if not isinstance(base, JSONResponse):
        return base                     # warm-up 失败 → 干净 HTTP 错误（延迟提交同样成立）
    data = json.loads(base.body.decode("utf-8"))
    choice = data["choices"][0]
    usage = data.get("usage")
    body_model = data.get("model") or payload.get("model", "")

    async def gen():
        yield streamer.first_frame()
        msg = choice["message"]
        # 未解析出调用时按普通文本切帧（200–400 字/帧）; 整段一帧会让宿主 UI 只看到 0/1 个块。
        # 思考段先于正文发（reasoning_content 帧）— 小欧 2026-11-05
        if msg.get("reasoning_content"):
            yield streamer.delta_frame(reasoning=msg["reasoning_content"])
        text = msg.get("content") or ""
        for i in range(0, len(text), 300):
            yield streamer.delta_frame(content=text[i:i + 300])
        if msg.get("tool_calls"):
            yield streamer.delta_frame(tool_calls=msg["tool_calls"])
        yield streamer.final_frame(body_model, usage, choice["finish_reason"])

    return _sse_response(gen())


async def _check_model_exists(client, model):
    """未知模型 → 404 model-not-found 的本地判定。
    下游对未知模型可能静默给空响应, 故用驱动 path_models+models_from 本地比对一次。— 小欧 2026-11-05"""
    resp = await client.get(_MANAGER.driver.path_models(), timeout=10)
    if resp.status_code != 200:
        return GatewayError(502, "server", "模型发现失败 HTTP %d" % resp.status_code,
                         resp.text[:500])
    items, _skipped = _MANAGER.driver.models_from(resp.json())
    if str(model or "") not in {it["id"] for it in items}:
        return GatewayError(404, "model-not-found",
                         "模型 %r 不存在或未开放" % str(model or ""))
    return None


class _SseResponse(StreamingResponse):
    """流式响应: 释放实例的回调必达。Starlette 的 background 异常/断连时会被跳过,
    池实例会永久停在 busy, 故在 ASGI 层 try/finally 兜住所有出口。— 小欧 2026-11-05"""

    def __init__(self, content, on_close=None, **kwargs):
        super().__init__(content, **kwargs)
        self._on_close = on_close

    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            if self._on_close is not None:
                self._on_close()


def _sse_response(gen, on_close=None):
    """流式响应的公共头（Cache-Control / X-Accel-Buffering）+ 必达释放回调。
    入参是异步生成器对象, 直接传给 _SseResponse, 不能再调用一次。— 小欧 2026-11-05"""
    return _SseResponse(gen, on_close, media_type="text/event-stream",
                        headers={"Cache-Control": "no-cache",
                                 "X-Accel-Buffering": "no"})


def _classify(item):
    """事件 → 驱动归一类别; http_error 由通用形状另行处理。— 小欧 2026-11-05"""
    if isinstance(item, dict) and item.get("kind") == "http_error":
        return {"kind": "http_error", "text": "", "status": item["status"]}
    return _MANAGER.driver.event_class(item)


_NO_ORDINAL = "__no_ordinal__"     # 下游未给 ordinal 时的统一记账键（同一条消息只收一份全文）— 小欧 2026-11-05


def _frame_of(info, streamed=None):
    """归一类别 → 0 或 1 个 SSE delta 帧（content→delta.content 等）。
    收尾全文与增量同属一条消息的 ordinal: 已流出增量的 ordinal 不再重发全文。— 小欧 2026-11-05"""
    ordinal = info.get("ordinal")
    key = _NO_ORDINAL if ordinal is None else ordinal
    if info["kind"] == "content":
        text = info.get("text") or ""
        if not text:
            return ""                    # 空 delta 不发帧, 也不占 ordinal — 小欧 2026-11-05
        if streamed is not None:
            streamed.add(key)
        return streamer.delta_frame(content=text)
    if info["kind"] == "final":
        if streamed is not None and key in streamed:
            return ""
        text = info.get("text") or ""
        if not text:
            return ""
        if streamed is not None:
            streamed.add(key)
        return streamer.delta_frame(content=text)
    if info["kind"] == "reasoning":
        text = info.get("text") or ""
        if not text:
            return ""
        return streamer.delta_frame(reasoning=text)
    return ""


def _error_of(info):
    """可映射错误 → GatewayError（提交响应头前抛出 = 干净状态码）; 不可映射 → None。— 小欧 2026-11-05"""
    if info["kind"] == "http_error":
        return GatewayError(502, "network", "事件订阅失败 HTTP %d" % info["status"])
    if info["kind"] == "error":
        return _mapped_error(_MANAGER.driver.map_error(info["error"]))
    return None
async def _stream_text(inst, payload, prompt, attachments):
    """(stream=1, tools=0) 象限: 延迟提交状态机。
    时序: 订阅先行 → 建会话 → 发消息 → 首帧前不提交头 → 首帧后提交 200 → 静默判据 → 末帧。— 小欧 2026-11-05"""
    model = str(payload.get("model") or "")
    rid = "req_" + uuid.uuid4().hex[:8]
    started = time.time()
    out_chars = 0
    sid = ""
    events = None
    ev_task = None                        # 等待任务引用, 出错时可取消 — 小欧 2026-11-05
    aclient = None                        # start() 后才有密码, client 只能随后建 — 小欧 2026-11-05
    try:
        await asyncio.to_thread(inst.start)   # 按需启动: spawn + 就绪轮询不占事件循环 — 小欧 2026-11-05
        # read 必须大于静默窗: read=60 会先于 180 s 判据抛 ReadTimeout → 502 network,
        # 504 timeout 语义永远到不了 — 小欧 2026-11-05
        aclient = inst.aclient(read_timeout=streamer.SILENT_S + 20)
        err = await _check_model_exists(aclient, model)   # 未知模型 → 404（提交前可改）
        if err is not None:
            raise err
        body = _MANAGER.driver.session_body(model, SESSION_PERMISSIONS)
        resp = await aclient.post(_MANAGER.driver.path_create(), json=body, timeout=10)
        if resp.status_code >= 300:
            raise GatewayError(502, "server", "建会话失败 HTTP %d" % resp.status_code,
                            resp.text[:500])
        sid = resp.json()["data"]["id"]

        # 订阅必须先行于发消息: 建→发→订阅会丢掉全部 part 事件 → 流式无内容可转。
        # iter_events 是惰性生成器, 此处置入即完成订阅排期。— 小欧 2026-11-05
        events = streamer.iter_events(aclient, sid, _MANAGER.driver)
        prompt_body = _MANAGER.driver.prompt_body(prompt, attachments)
        resp = await aclient.post(_MANAGER.driver.path_prompt(sid), json=prompt_body,
                                  timeout=30)
        if resp.status_code >= 300:
            raise GatewayError(502, "server", "发消息失败 HTTP %d" % resp.status_code,
                            resp.text[:500])

        first = None
        streamed = set()            # 已流出 ordinal 记账（warm-up 与 body 共享）— 小欧 2026-11-05
        deadline = time.time() + streamer.FIRST_FRAME_S
        while first is None:
            remain = deadline - time.time()
            if remain <= 0:
                raise GatewayError(504, "timeout", "模型响应超时（60 s 无首帧）")
            # 用 asyncio.wait 而非 wait_for: 超时不取消任务, 订阅保持存活 — 小欧 2026-11-05
            if ev_task is None:
                ev_task = asyncio.ensure_future(_next(events))
            done, _pend = await asyncio.wait({ev_task},
                                             timeout=min(remain, streamer.WAIT_SLICE_S))
            if not done:
                continue                       # 暂无事件 → 继续等（订阅依然存活）
            try:
                item = ev_task.result()        # StopAsyncIteration 在此浮出
            except StopAsyncIteration:
                raise GatewayError(502, "network", "事件流提前关闭")
            ev_task = None
            info = _classify(item)
            err = _error_of(info)                        # execution.failed 等 → 干净码
            if err is not None:
                raise err
            frames = _frame_of(info, streamed)
            if frames:
                first = frames
                if info["kind"] in ("content", "final"):
                    out_chars += len(info.get("text") or "")
    except GatewayError:
        await _aclose(events)
        if ev_task is not None and not ev_task.done():   # 弃任务前先取消 — 小欧 2026-11-05
            ev_task.cancel()
        if aclient is not None:          # client 已建过 → 就地清理会话与连接 — 小欧 2026-11-05
            await _cleanup_session_async(aclient, sid)
            await aclient.aclose()
        raise                                            # 状态码在提交前可改

    async def body():
        nonlocal out_chars
        try:
            yield streamer.first_frame()                 # 已过 warm-up: 首帧即提交 200 — 小欧 2026-11-05
            yield first
            last_emit = time.time()
            async for item in events:
                info = _classify(item)
                err = _error_of(info)
                if err is not None:
                    # 已提交 200 后状态码不可改 → 记 ERROR 并收口流 — 小欧 2026-11-05
                    _log_error(err, "（响应头已提交, 收口流）")
                    return
                frames = _frame_of(info, streamed)
                if frames:
                    last_emit = time.time()
                    if info["kind"] in ("content", "final"):
                        out_chars += len(info.get("text") or "")
                    yield frames
                elif info["kind"] == "idle":
                    break                                # 会话空闲 → 取末消息补 usage — 小欧 2026-11-05
                if time.time() - last_emit > streamer.SILENT_S:
                    raise GatewayError(504, "timeout", "模型响应超时（180 s 无新帧）")
            last = await _last_assistant(aclient, sid)
            usage = upward.usage_from_counts(_MANAGER.driver.token_counts(last or {}))
            finish = _MANAGER.driver.finish_reason(last or {}) or "stop"
            yield streamer.final_frame(model, usage, finish)
            # 纯文本流式此前无请求日志, 排障只能靠猜; 补一行。— 小欧 2026-11-05
            _log("%s model=%s stream=1 out_chars=%d tool_calls=0 usage=%s elapsed=%.1fs"
                 % (rid, model, out_chars,
                    ("p%d/c%d" % (usage["prompt_tokens"], usage["completion_tokens"]))
                    if usage else "null", time.time() - started))
            inst.touch()                                 # 重置任务窗口 — 小欧 2026-11-05
            _MANAGER.note_success()                      # 成功收口 → 计数清零/退避复位 — 小欧 2026-11-05
        except httpx.HTTPError as exc:   # 已提交响应头 → 只能记日志收口 — 小欧 2026-11-05
            _log_error(GatewayError(502, "network", "下游连接中断/超时", repr(exc)[:200]),
                       "（响应头已提交, 收口流）")
        finally:
            await _aclose(events)                        # [DONE] 后即退订 — 小欧 2026-11-05
            await _cleanup_session_async(aclient, sid)
            await aclient.aclose()

    return _sse_response(body(), on_close=lambda: _MANAGER.release(inst))


async def _next(agen):
    return await agen.__anext__()


async def _aclose(agen):
    if agen is not None:
        try:
            await agen.aclose()
        except Exception:
            pass


async def _cleanup_session_async(aclient, sid):
    """会话收尾: 先 interrupt 再 delete, 失败不阻断响应。— 小欧 2026-11-05"""
    if not sid:
        return
    try:
        await aclient.post(_MANAGER.driver.path_interrupt(sid), timeout=5)
    except Exception:
        pass
    try:
        await aclient.delete(_MANAGER.driver.path_delete(sid), timeout=10)
    except Exception as exc:
        _log("WARN 删会话失败 sid=%s detail=%s（不阻断响应）" % (sid, exc))


async def _last_assistant(aclient, sid):
    msg_path, msg_params = _MANAGER.driver.path_messages(sid)
    try:
        resp = await aclient.get(msg_path, params=msg_params, timeout=10)
        items = (resp.json().get("data") or []) if resp.status_code == 200 else []
        return items[0] if items else {}
    except Exception:
        return {}


# 导入期即过安全闸门并构造池, 不依赖 lifespan 形态; 否则 --lifespan off / 被 mount /
# ASGITransport 直调时闸门被整体绕过且全 500。— 小欧 2026-11-05
_MANAGER = _boot()


if __name__ == "__main__":
    uvicorn.run(APP, host=CFG["host"], port=int(CFG["port"]))
    # host 必须回环——preflight 已校验; 若配置被改, 这里也不会起在非回环地址。
