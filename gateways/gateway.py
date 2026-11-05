# -*- coding: utf-8 -*-
"""gateway.py — FastAPI 应用与路由（薄: 校验 → 调用 → 打包; 通用层零方言, D25）。

编写人: 小欧    创建时间: 2026-11-05 09:10:00
对齐: 4.1 端点总表 / 4.2–4.8 契约 / 5.6 工具模式 / 8.5 自身防护 / 7.3 时序 /
     3.5 SPI 硬边界（本文件不得出现下游路由字符串: 除本行外 grep 下游路由前缀应为 0）
     / 9.6 步骤 0

启动即走 preflight(): 回环 + token + deny * + 驱动可装载, 任一失败拒绝启动——
"安全闸门先行"是实施排期第 0 步（9.6）, 不是上线后的加固项（3.7 定位）。

编辑历史:
  2026-11-05 向下翻译收口 mapping.build_prompt(messages,tools), usage 计量迁 upward(原 fc); 思考段经 assistant_reasoning 透传 -- 小欧
  2026-11-05 GatewayError(原名 GateError) 统一落日志(含 detail); 429 冷却由 _mapped_error 记账; 冷却只拦调模型 -- 小欧
  2026-11-05 命名对齐: _plain_chat→_complete_once(非流式整包, 工具模式复用), _stream_tools→_replay_tools_as_sse(不流式),
             _frames→_frame_of(返回单帧字符串), _model_guard→_check_model_exists, _gate→_gateway_error_response;
             删本文件 DRV 副本(驱动唯一持有者 = _MANAGER.driver), fc.py→upward.py -- 小欧
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

_MAX_BODY_BYTES = 32 * 1024 * 1024        # 8.5 体积门: 请求体 ≤ 32 MB
_MANAGER = None                           # 唯一持有者: 驱动实例在 _MANAGER.driver, 启动期装载


def _load_config(path):
    with open(path, encoding="utf-8-sig") as handle:
        return json.load(handle)


CFG = _load_config(os.path.join(runtime_dir(), "config.json"))


def _err(status, etype, message, detail="", retry_after_s=None):
    """唯一 HTTP 错误出口: 一律走 4.8.4 信封, gateway 内禁止裸 JSONResponse 报错。"""
    code, headers, body = errors.make_error(status, etype, message, detail,
                                            retry_after_s)
    return JSONResponse(body, status_code=code, headers=headers)


def _gateway_error_response(exc: GatewayError):
    """GatewayError 唯一出口: 先落日志再出信封（原实现错误零日志, 429 冷却无从取证）— 小欧 2026-11-05"""
    _log("ERR %d %s %s detail=%s"
         % (exc.status, exc.etype, exc.message, str(exc.detail or "-")[:300]))
    return _err(exc.status, exc.etype, exc.message, exc.detail, exc.retry_after_s)


def _mapped_error(mapped):
    """4.7 映射 dict → GatewayError; 429 free-limit 顺手记 R5 冷却（同步/流式共用）— 小欧 2026-11-05"""
    if mapped["status"] == 429:
        _MANAGER.note_cooldown(mapped["internal_cooldown_ms"])
    return GatewayError(mapped["status"], mapped["type"], mapped["message"], mapped["detail"])


def _check_token(request):
    """Bearer + hmac.compare_digest（4.1 / 8.5 防时序侧信道）。/healthz 免鉴权。"""
    expect = "Bearer " + CFG["token"]
    got = request.headers.get("Authorization", "")
    if not hmac.compare_digest(expect.encode("utf-8"), got.encode("utf-8")):
        return _err(401, "auth", "网关鉴权失败，请核对 api_key")
    return None


def _log(line):
    """7.8 日志规范: 永不写 token/密码/正文; 下游错误原文必须落（截 500 字）。

    文件 logs/gateway-YYYY-MM-DD.log 按天切分, 保留 7 天（滚动删除由停止后
    清运或 log_keep_days 参数的清运线程承担——设计上不进热路径）。
    """
    logs_dir = os.path.join(runtime_dir(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    path = os.path.join(logs_dir, "gateway-%s.log" % time.strftime("%Y-%m-%d"))
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("%s %s\n" % (time.strftime("%H:%M:%S"), str(line)[:2000]))
    except OSError:
        pass                             # 日志失败不阻断业务（7.8 精神）


@APP.on_event("startup")
def _startup():
    global _MANAGER
    problems = preflight(CFG)            # 步骤 0 的代码级闸门（3.7 / 9.6）
    if problems:
        for line in problems:
            print("[preflight] " + line, file=sys.stderr)
        raise RuntimeError("安全闸门未通过，拒绝启动（详见 stderr）")
    _MANAGER = CliManager(CFG)           # 复用已被 preflight 装载的驱动单例
    _MANAGER.start_reaper()


@APP.on_event("shutdown")
def _shutdown():
    if _MANAGER is not None:
        _MANAGER.shutdown()              # 网关退出 → 全部下游 terminate（7.2）


@APP.get("/healthz")
def healthz():
    """/healthz: 聚合池状态、候选明细、冷却与退避（4.1）。免鉴权 → 绝不含密钥。"""
    snap = _MANAGER.health_snapshot()
    snap["version"] = "opencli-gateway 1.0.0"
    snap["model_source"] = "opencli 通过 %s 驱动接入本地 CLI（免费层）" % _MANAGER.driver.name
    return snap


@APP.get("/v1/models")
def list_models(request: Request):
    """模型发现（4.2 / 4.8.1）。占用实例 → R1 按需启动（cli=idle 不是错误）。

    FIX J 偏差记录（2026-11-05 小欧, 出处 4.7 第一层 + 用例 A3/A4/B8）:
    /v1/models 也必须过 Bearer token 门（拉模型返 401）——原实现只对 chat 校验,
    无/错 token 对本端点均 200（实测复现）。
    """
    denied = _check_token(request)
    if denied is not None:
        return denied                    # 401 只属于第一层（4.7 规则 1）
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
            _log("WARN models: %d 项缺 id 被跳过（宿主会静默丢弃, 4.8.1 风险项）"
                 % skipped)
        return {"object": "list", "data": items}
    except GatewayError as exc:
        _MANAGER.on_downstream_failure(exc.etype)
        return _gateway_error_response(exc)
    except httpx.HTTPError as exc:    # FIX B 偏差记录（2026-11-05 小欧）: 传输层异常
        _MANAGER.on_downstream_failure("network")              # （ConnectError 等）原样穿透
        return _err(502, "network",                     # 成 500 裸 traceback, 违反
                    "下游连接级失败（连接/超时）", repr(exc)[:300])  # 4.8.4; 归一 502 network
    finally:
        if client is not None:
            client.close()
        _MANAGER.release(inst)
@APP.post("/v1/chat/completions")
async def chat(request: Request):
    """/v1/chat/completions（4.1）。分流: stream × tools ∈ {0,1}, 四象限其中
    (stream,tools)=(1,1) 走 5.6 整包再出帧; (0,1)/(0,0) 走 7.3 非流式时序;
    (1,0) 走 4.5 延迟提交流。"""
    denied = _check_token(request)
    if denied is not None:
        return denied                     # 401 只属于第一层（4.7 规则 1）
    if int(request.headers.get("content-length") or 0) > _MAX_BODY_BYTES:
        return _err(413, "gateway-too-large", "请求体超过 32 MB（8.5 体积门）")
    raw = await request.body()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _err(400, "gateway-bad-request", "请求体不是合法 JSON")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        return _err(400, "gateway-bad-request", "缺失必需字段 messages")
    if len(messages) > mapping.MAX_MESSAGES:
        return _err(400, "gateway-bad-request",
                    "messages 超过 %d 条上限（4.3）" % mapping.MAX_MESSAGES)
    for warn in mapping.collect_param_warns(payload):
        _log("WARN " + warn)              # 采样参数忽略, 只 WARN 一次级（去重略）, 4.3

    tools = payload.get("tools") or []
    # 向下翻译（mapping.py 唯一入口）: 工具模式 1系统→2工具清单→3对话(+4压轴)→5行动提醒;
    # 纯文本 1系统→3/4对话（不追加任何尾句） — 小欧 2026-11-05
    prompt, attachments = mapping.build_prompt(messages, tools)

    try:
        _MANAGER.ensure_not_cooling()         # R5: 只拦调模型; /v1/models 不耗额度, 不拦
        inst = _MANAGER.acquire()         # 池满排队 / 队列满 429 gateway-busy
    except GatewayError as exc:
        return _gateway_error_response(exc)
    try:
        if payload.get("stream"):
            if tools:                     # 5.6: 起始标记可能在任意位置, SSE 无法回滚
                return await _replay_tools_as_sse(inst, payload, prompt, attachments, tools)
            return await _stream_text(inst, payload, prompt, attachments)
        return await _complete_once(inst, payload, prompt, attachments, tools)
    except GatewayError as exc:
        _MANAGER.on_downstream_failure(exc.etype)          # R4 计数; R5 冷却由内层记
        return _gateway_error_response(exc)
    except httpx.HTTPError as exc:    # FIX B 偏差记录（2026-11-05 小欧）: 提交前的
        _MANAGER.on_downstream_failure("network")          # 传输层异常归一信封（4.7/4.8.4）
        return _err(502, "network", "下游连接级失败（连接/超时）", repr(exc)[:300])
    finally:
        _MANAGER.release(inst)
# ---------------------------------------------------------------------------
# 非流式整包（7.3 时序步骤 1–12; 注释内标步骤号）
# ---------------------------------------------------------------------------

async def _complete_once(inst, payload, prompt, attachments, tools):
    """一次完整下游往返: (0,0)/(0,1) 直接返,(1,1) 由 _replay_tools_as_sse 复用它再切帧。"""
    model = str(payload.get("model") or "")
    client = None                      # FIX F: http() 必须晚于 start(), 见下注释
    rid = "req_" + uuid.uuid4().hex[:8]
    started = time.time()
    sid = ""
    try:
        inst.start()                      # 步骤 4: R1 按需启动（spec 记作
                                          # ensure_started, 即本方法 9.1.6;
                                          # cli=idle 不是错误, 4.7 规则 2）
        # FIX F 偏差记录（2026-11-05 小欧, 出处 7.3 步骤序 + 8.6 不落盘）:
        # http() 的 auth 在客户端创建时即定型, 必须晚于 start() 捕获密码。
        # 原序 client 先建——实例冷启动后的首个请求 auth 为空 → 下游 401
        #（实测复现: 新进程首请求 100% 失败; 此前 /v1/models 先到才掩盖此缺陷）。
        client = inst.http()
        err = await _check_model_exists(client, model)    # FIX K: 未知模型 → 404（见函数）
        if err is not None:
            raise err
        body = _MANAGER.driver.session_body(model, SESSION_PERMISSIONS)    # 步骤 5（8.2 规则）
        resp = client.post(_MANAGER.driver.path_create(), json=body, timeout=10)
        if resp.status_code >= 300:
            raise GatewayError(502, "server", "建会话失败 HTTP %d" % resp.status_code,
                            resp.text[:500])
        sid = resp.json()["data"]["id"]   # 网关自建, 不复用不透传（7.2.8）

        prompt_body = _MANAGER.driver.prompt_body(prompt, attachments)    # 步骤 6
        resp = client.post(_MANAGER.driver.path_prompt(sid), json=prompt_body, timeout=30)
        if resp.status_code >= 300:
            raise GatewayError(502, "server", "发消息失败 HTTP %d" % resp.status_code,
                            resp.text[:500])

        wait_path, wait_ok = _MANAGER.driver.path_wait(sid)          # 步骤 7: 阻塞式等待
        resp = client.post(wait_path, timeout=900)       # 服务端阻塞直至空闲
        if resp.status_code not in wait_ok:
            raise GatewayError(502, "server", "等待完成失败 HTTP %d" % resp.status_code,
                            resp.text[:500])

        # 步骤 8: 定向查询（7.3——由驱动给 path 与参数, 报文省 19%）
        msg_path, msg_params = _MANAGER.driver.path_messages(sid)
        resp = client.get(msg_path, params=msg_params, timeout=10)
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
            parsed = upward.parse_calls(content, tools)     # 步骤 9 工具分支（5.3）
            for warn in parsed["warns"]:                # 成功/降级都要写日志, 防静默
                _log("WARN " + warn)
            if parsed["calls"]:
                message["content"] = parsed["content"]
                message["tool_calls"] = parsed["calls"]
                finish_reason = "tool_calls"            # 5.3 末行
            elif parsed["content"]:
                message["content"] = parsed["content"]  # 协议失败降级为文本（5.5）
            else:
                raise GatewayError(502, "server",
                                "模型未按工具协议响应，请重试或更换模型",
                                "calls=0 invalid=%d" % parsed["invalid"])
        else:
            if not content:                             # 空响应（5.5）
                raise GatewayError(502, "server",
                                "下游未返回内容（模型可能尝试了被禁用的内置工具）")
            message["content"] = content

        usage = upward.usage_from_counts(_MANAGER.driver.token_counts(assistant))   # 4.6; 缺→null（向上翻译）
        # FIX N: stream 值按请求实报（原为硬编码 0, 曾把流式排障带偏）
        _log("%s model=%s stream=%d out_chars=%d tool_calls=%d usage=%s elapsed=%.1fs"
             % (rid, model, 1 if payload.get("stream") else 0, len(content),
                int(bool(message.get("tool_calls"))),
                ("p%d/c%d" % (usage["prompt_tokens"], usage["completion_tokens"]))
                if usage else "null", time.time() - started))
        inst.touch()                                    # 步骤 11: 重置任务窗口
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
        _cleanup_session(client, sid)                   # 步骤 10: finally 必达（7.7）


def _cleanup_session(client, sid):
    """7.7 finally 两件事（同步版）: 中断兜底 + 删会话; 连接由调用方关（失败仅 WARN 不阻断）。"""
    if not sid:
        return
    try:
        client.post(_MANAGER.driver.path_interrupt(sid), timeout=5)
    except Exception:
        pass                            # 未在跑时 interrupt 报错属正常, 吞掉
    try:
        client.delete(_MANAGER.driver.path_delete(sid), timeout=10)
    except Exception as exc:
        _log("WARN 删会话失败 sid=%s detail=%s（不阻断响应, 7.7）" % (sid, exc))
# ---------------------------------------------------------------------------
# 流式（4.5 延迟提交 + 7.4 转发表 + 5.6 工具模式整包）
# ---------------------------------------------------------------------------

async def _replay_tools_as_sse(inst, payload, prompt, attachments, tools):
    """(stream=1, tools) 象限: 整包解析后一次性发帧（5.6——不边流边判）。"""
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
        # FIX N（2026-11-05 小欧, 对齐 5.6）: 未解析出调用时按普通文本切帧
        # （200–400 字/帧）; 原实现整段一帧, 宿主 UI 只看到 0/1 个块。
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
    """FIX K 偏差记录（2026-11-05 小欧, 出处用例 C3 + 4.7 表）: 未知模型 →
    404 model-not-found 的本地判定。v6.8 假设下游对模型名报 404/no-route,
    实测 opencode v2.2.0 对未知模型静默给出空响应（错误映射无从触发, 实测
    落成 502 server"下游未返回内容"）。零方言实现: 复用驱动挂钩
    path_models()+models_from() 本地比对一次（回环毫秒级）。
    适配同步(In#st.http)/异步(aclient)两类客户端（D1 二跑实测 500 教训）。
    """
    if isinstance(client, httpx.AsyncClient):
        resp = await client.get(_MANAGER.driver.path_models(), timeout=10)
    else:
        resp = client.get(_MANAGER.driver.path_models(), timeout=10)
    if resp.status_code != 200:
        return GatewayError(502, "server", "模型发现失败 HTTP %d" % resp.status_code,
                         resp.text[:500])
    items, _skipped = _MANAGER.driver.models_from(resp.json())
    if str(model or "") not in {it["id"] for it in items}:
        return GatewayError(404, "model-not-found",
                         "模型 %r 不存在或未开放" % str(model or ""))
    return None


def _sse_response(gen):
    """流式响应的公共头（Cache-Control / X-Accel-Buffering, 4.8.3）。

    FIX G 偏差记录（2026-11-05 小欧）: 入参实为异步生成器对象（两处调用点
    _stream_text(body())/_replay_tools_as_sse(gen()) 均如此）, 原实现 gen() 会再调一次
    → TypeError 'async_generator' object is not callable（实测复现）。直接用对象。
    """
    return StreamingResponse(gen, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


def _classify(item):
    """事件 → 驱动归一类别; http_error 一并由驱动事件号之外的通用形状处理。"""
    if isinstance(item, dict) and item.get("kind") == "http_error":
        return {"kind": "http_error", "text": "", "status": item["status"]}
    return _MANAGER.driver.event_class(item)


def _frame_of(info, streamed=None):
    """归一类别 → 0 或 1 个 SSE delta 帧（7.4 映射: content→delta.content 等）。

    FIX I 偏差记录（2026-11-05 小欧）: "final" 类（下游收尾全文事件, 出处
    driver.event_class）与 incremental content 同属一条消息的 ordinal——已流出
    增量的 ordinal 不再重发全文; 无增量的 ordinal 则按 content 收字（兜底）。
    streamed: 调用方持有的已流出 ordinal 集合（跨事件共享）。
    """
    if info["kind"] == "content":
        text = info.get("text") or ""
        if not text:
            return ""                    # FIX N: 空 delta 不发帧, 也不占 ordinal
        if streamed is not None and info.get("ordinal") is not None:
            streamed.add(info["ordinal"])
        return streamer.delta_frame(content=text)
    if info["kind"] == "final":
        if streamed is not None and info.get("ordinal") in streamed:
            return ""
        text = info.get("text") or ""
        if not text:
            return ""
        if streamed is not None and info.get("ordinal") is not None:
            streamed.add(info["ordinal"])
        return streamer.delta_frame(content=text)
    if info["kind"] == "reasoning":
        text = info.get("text") or ""
        if not text:
            return ""
        return streamer.delta_frame(reasoning=text)
    return ""


def _error_of(info):
    """可映射错误 → GatewayError（提交响应头前抛出 = 干净状态码）; 不可映射 → None。"""
    if info["kind"] == "http_error":
        return GatewayError(502, "network", "事件订阅失败 HTTP %d" % info["status"])
    if info["kind"] == "error":
        return _mapped_error(_MANAGER.driver.map_error(info["error"]))
    return None
async def _stream_text(inst, payload, prompt, attachments):
    """(stream=1, tools=0) 象限: 4.5 延迟提交状态机的落地点。

    时序（7.3 说明行）: 订阅先行 → 建会话 → 发消息 → 首帧前不提交头 →
    首帧(≤60 s)后提交 200 → 心跳 15 s / 静默 180 s → idle → 取末消息 usage → 末帧。
    """
    model = str(payload.get("model") or "")
    rid = "req_" + uuid.uuid4().hex[:8]
    started = time.time()
    out_chars = 0
    sid = ""
    events = None
    ev_task = None                        # FIX D 守护: 等待任务的引用, 出错时可取消
    aclient = None                        # start() 后才有密码——client 只能随后建（8.6）
    try:
        inst.start()                      # R1; 密码在该调用后可用
        aclient = httpx.AsyncClient(
            base_url="http://127.0.0.1:%d" % inst.port,
            auth=_MANAGER.driver.auth(inst.password),
            timeout=httpx.Timeout(connect=10, read=60, write=30, pool=10),
            trust_env=False)              # 8.5: 网关自身 httpx 一律不走系统代理
        err = await _check_model_exists(aclient, model)   # FIX K: 未知模型 → 404（提交前可改）
        if err is not None:
            raise err
        body = _MANAGER.driver.session_body(model, SESSION_PERMISSIONS)
        resp = await aclient.post(_MANAGER.driver.path_create(), json=body, timeout=10)
        if resp.status_code >= 300:
            raise GatewayError(502, "server", "建会话失败 HTTP %d" % resp.status_code,
                            resp.text[:500])
        sid = resp.json()["data"]["id"]

        # FIX E 偏差记录（2026-11-05 小欧, 出处 7.3 时序"订阅先行"）: 订阅必须先行于
        # 发消息。原序（建→发→订阅）会在发消息返回前丢掉全部 part 事件 → 流式无内容
        # 可转。iter_events 是惰性生成器, 此处置入即完成订阅排期。
        events = streamer.iter_events(aclient, sid, _MANAGER.driver)
        prompt_body = _MANAGER.driver.prompt_body(prompt, attachments)
        resp = await aclient.post(_MANAGER.driver.path_prompt(sid), json=prompt_body,
                                  timeout=30)
        if resp.status_code >= 300:
            raise GatewayError(502, "server", "发消息失败 HTTP %d" % resp.status_code,
                            resp.text[:500])

        first = None
        streamed = set()            # FIX I: 已流出 ordinal 记账（warm-up 与 body 共享）
        deadline = time.time() + streamer.FIRST_FRAME_S
        while first is None:
            remain = deadline - time.time()
            if remain <= 0:
                raise GatewayError(504, "timeout", "模型响应超时（60 s 无首帧）")
            # FIX D 偏差记录（2026-11-05 小欧）: 原用 asyncio.wait_for(_next(events), …)
            # 超时会把 CancelledError 注进生成器内部 → 订阅被整体终止 → 下一次 _next
            # 立即 StopAsyncIteration（实测 502 "事件流提前关闭"）。改用 asyncio.wait:
            # 超时不取消任务, 订阅保持存活。
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
        if ev_task is not None and not ev_task.done():   # FIX D 守护: 弃任务前先取消
            ev_task.cancel()
        if aclient is not None:          # client 已建过 → 就地清理会话与连接
            await _cleanup_session_async(aclient, sid)
            await aclient.aclose()
        raise                                            # 状态码在提交前可改（4.5）

    async def body():
        nonlocal out_chars
        try:
            yield streamer.first_frame()                 # 已过 warm-up: 首帧即提交 200
            yield first
            last_emit = time.time()
            async for item in events:
                info = _classify(item)
                err = _error_of(info)
                if err is not None:
                    raise err                            # 已提交后: 记录并收口（罕见）
                frames = _frame_of(info, streamed)
                if frames:
                    last_emit = time.time()
                    if info["kind"] in ("content", "final"):
                        out_chars += len(info.get("text") or "")
                    yield frames
                elif info["kind"] == "idle":
                    break                                # 会话空闲 → 取末消息补 usage
                if time.time() - last_emit > streamer.SILENT_S:
                    raise GatewayError(504, "timeout", "模型响应超时（180 s 无新帧）")
            last = await _last_assistant(aclient, sid)
            usage = upward.usage_from_counts(_MANAGER.driver.token_counts(last or {}))
            finish = _MANAGER.driver.finish_reason(last or {}) or "stop"
            yield streamer.final_frame(model, usage, finish)
            # FIX N: 纯文本流式此前整条链路无请求日志, 排障只能靠猜; 补齐一行。
            _log("%s model=%s stream=1 out_chars=%d tool_calls=0 usage=%s elapsed=%.1fs"
                 % (rid, model, out_chars,
                    ("p%d/c%d" % (usage["prompt_tokens"], usage["completion_tokens"]))
                    if usage else "null", time.time() - started))
            inst.touch()                                 # 步骤 11: 重置任务窗口
        except httpx.HTTPError as exc:   # FIX B 偏差记录（2026-11-05 小欧）: 已提交
            raise GatewayError(502, "network",      # 窗口内传输异常同样归一（4.7 规则 2）
                            "下游连接中断/超时", repr(exc)[:200])
        finally:
            await _aclose(events)                        # 7.4 终止行: [DONE] 后即退订
            await _cleanup_session_async(aclient, sid)
            await aclient.aclose()

    return _sse_response(body())


async def _next(agen):
    return await agen.__anext__()


async def _aclose(agen):
    if agen is not None:
        try:
            await agen.aclose()
        except Exception:
            pass


async def _cleanup_session_async(aclient, sid):
    """7.7 finally 三件事（异步版, 语义与上文同步版 _cleanup_session 一致）。"""
    if not sid:
        return
    try:
        await aclient.post(_MANAGER.driver.path_interrupt(sid), timeout=5)
    except Exception:
        pass
    try:
        await aclient.delete(_MANAGER.driver.path_delete(sid), timeout=10)
    except Exception as exc:
        _log("WARN 删会话失败 sid=%s detail=%s（不阻断响应, 7.7）" % (sid, exc))


async def _last_assistant(aclient, sid):
    msg_path, msg_params = _MANAGER.driver.path_messages(sid)
    try:
        resp = await aclient.get(msg_path, params=msg_params, timeout=10)
        items = (resp.json().get("data") or []) if resp.status_code == 200 else []
        return items[0] if items else {}
    except Exception:
        return {}


if __name__ == "__main__":
    uvicorn.run(APP, host=CFG["host"], port=int(CFG["port"]))
    # host 必须回环——preflight 已校验; 若配置被改, 这里也不会起在非回环地址。
