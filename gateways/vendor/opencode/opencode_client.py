# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# 迁移说明（2026-11-05 复制入库, 按 [11] 方案 v6.8 §9.1.5）
#   来源: F:\agenttool\Zencode-20261104\code\opencode_client.py
#   版本: v1.1（2026-11-04 编写并自检通过, 内容原样未改写）
#   与本项目网关的分工: 本库只做下游协议封装（报文构造 / 结果分类 / 自检工具）,
#     进程起停、池与窗口、脱敏、准入与隔离由通用层 cli_manager.py 与网关侧承担;
#     正式链路报文只经 vendor\opencode\driver.py 委托本库纯函数（§9.1.5 使用纪律）
# ---------------------------------------------------------------------------
# -*- coding: utf-8 -*-
"""opencode_client.py — 把 opencode 本地服务 API 封装成可复用库（同步 + 异步）

编写人: 小欧    版本: v1.1    创建时间: 2026-11-04 21:29:26    更新时间: 2026-11-04 21:38:06

版本历史
--------
v1.0  2026-11-04 21:29:26  初版：同步/异步封装、AskResult、classify、多轮
v1.1  2026-11-04 21:38:06  ask() 增加 files / agents / skills / metadata /
                           delivery / resume / agent / permissions / parent_id /
                           extra_body 参数；新增 new_session()、as_attachment()

用途
----
给 agent 项目直接 import 用。对外只暴露两个类：

    OpenCodeClient       —— 同步（普通函数里用）
    AsyncOpenCodeClient  —— 异步（asyncio / FastAPI / LangGraph 等里用）

两边 API 完全一致，返回同一个 AskResult 结构体。

核心能力（从"发消息"到"解析消息"全包）
------------------------------------
    ask(model, text)     发一条消息，等模型答完，返回结构化结果
    list_models()        拉模型目录（可只取免费模型）
    health()             探活
    start() / close()    起停本地 opencode-cli.exe（也可以只连已有服务）

设计要点（都是 2026-11-04 实测踩出来的，别随意改）
------------------------------------------------
1. 纯 Python 不能直连 opencode.ai（恒 429），必须经本机 CLI 起的服务中转；
2. 建会话 body 里模型字段是 ``{"providerID": "opencode", "id": <模型>}``，
   注意键名是 ``id``，不是 ``modelID``；
3. 等待用 ``POST /api/experimental/session/<sid>/wait``，它是**服务端阻塞式**，
   不需要 Python 轮询；
4. 报文里 assistant 可能为 null（模型根本没出话），此时真错误只在 idle 消息上，
   所以错误对象要按 assistant → idle → session 三级回退取；
5. 免费层按**出口国家**放行：CN / CL 等出口会回 429 ``FreeUsageLimitError``，
   这是地区拒绝而非额度用尽，换 SG / JP 节点就好（详见 docs 第十章）。
   本库会用 ``kind`` / ``advice`` 字段把这件事直接告诉你，不用自己判。

最小示例（同步）
--------------
    from opencode_client import OpenCodeClient

    with OpenCodeClient() as oc:                     # 自动起 CLI、用完自动关
        r = oc.ask("big-pickle", "只回答两个字：可用")
        if r.ok:
            print(r.text, r.tokens)
        else:
            print(r.kind, r.advice)                  # 例如 region / 换 SG、JP 节点

请求参数（都能传，全部可选）
--------------------------
    r = oc.ask(
        "glm-5.3-flash-free",
        "这张图里的数字是多少？",
        files=[as_attachment(r"D:/pic.png")],        # 图片 / PDF / 文本，走 data: URL
        agent="build",                                # 建会话时指定 agent
        metadata={"user": "laochen"},                 # 会话 + 消息 metadata
        delivery="steer",                             # steer（默认）| queue
        session_id=None,                              # 传了就多轮
        extra_body={"whatever": 1},                   # 逃生口：协议将来加字段直接透传
    )

**没有** temperature / max_tokens：协议层不暴露采样参数，只能在 opencode 配置文件里
针对模型/agent 设。想加别的字段用 extra_body 透传。

附件辅助函数：
    as_attachment(path, name=None, description=None) -> {"uri": "data:...", "name": ...}

最小示例（异步）
--------------
    from opencode_client import AsyncOpenCodeClient

    async with AsyncOpenCodeClient() as oc:
        r = await oc.ask("deepseek-v4.1-flash-free", "你好")
        print(r.answer())

连已有服务（不起新进程）
----------------------
    oc = OpenCodeClient(base_url="http://127.0.0.1:4096", password="xxx")

命令行自检
----------
    python opencode_client.py                             # 用 big-pickle 跑一次
    python opencode_client.py --model big-pickle,beam-free --prompt "你好"
    python opencode_client.py --list                      # 列免费模型
    python opencode_client.py --async                     # 走异步实现自检
    python opencode_client.py --base-url http://127.0.0.1:4096 --password xxx
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import json
import os
import socket
import subprocess
import sys
import time
from typing import Any, Optional

import httpx

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

PROVIDER_ID = "opencode"

# 本地服务门禁密码（只保护 127.0.0.1，任意值即可，不是账号密码）
DEFAULT_PASSWORD = "zencode-local-20261104"

DEFAULT_USER = "opencode"
DEFAULT_TIMEOUT = 900.0        # 单次问答的总超时（秒）
DEFAULT_START_TIMEOUT = 60.0   # 起服务的就绪等待（秒）

_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

# 真客户端查找顺序：脚本同目录 → 上级 bin\（旧布局） → 桌面版安装目录
CLI_CANDIDATES = [
    os.path.join(_MODULE_DIR, "opencode-cli.exe"),
    os.path.normpath(os.path.join(_MODULE_DIR, "..", "bin", "opencode-cli.exe")),
    os.path.expandvars(r"%APPDATA%\ai.opencode.desktop\cli\2.2.0-x64\opencode-cli.exe"),
]

CF_TRACE = "https://www.cloudflare.com/cdn-cgi/trace"


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------


def now_str() -> str:
    """当前时间字符串（小欧 2026-11-04）"""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def find_cli() -> str:
    """按 CLICANDIDATES 顺序找真客户端，返回绝对路径（找不到返回最后一项，由调用方报错）"""
    for path in CLI_CANDIDATES:
        if os.path.exists(path):
            return path
    return CLI_CANDIDATES[-1]


def free_port() -> int:
    """取一个本机空闲端口（小欧 2026-11-04）"""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def egress_trace(timeout: float = 6.0) -> str:
    """本机当前出口（CF trace），失败返回 'trace失败: ...'。仅用于排障，不影响问答。"""
    try:
        r = httpx.get(CF_TRACE, timeout=timeout, trust_env=False,
                      headers={"User-Agent": "curl/8.21.0"})
        data = {}
        for line in r.text.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()
        return "ip=%s loc=%s colo=%s" % (data.get("ip", "?"), data.get("loc", "?"),
                                         data.get("colo", "?"))
    except Exception as exc:  # 排障辅助，不抛
        return "trace失败: %s" % exc


# ---------------------------------------------------------------------------
# 结果结构体
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class AskResult:
    """一次问答的完整结果（同步/异步共用）

    ok       : 是否拿到了正常文本
    kind     : 归一化的失败类型，取值见 KIND_* 常量
    advice   : 给调用方看的处置建议（中文，可直接展示）
    raw      : assistant / idle / session 三段原始 JSON，排障用
    """

    model: str
    ok: bool = False
    text: str = ""
    reasoning: str = ""
    finish: str = ""
    outcome: str = ""
    kind: str = "unknown"
    advice: str = ""
    error_type: str = ""
    error_message: str = ""
    error_status: int = 0
    retry_after_ms: int = 0
    tokens: dict = dataclasses.field(default_factory=dict)
    session_id: str = ""
    elapsed: float = 0.0
    started: str = ""
    finished: str = ""
    egress: str = ""
    raw: dict = dataclasses.field(default_factory=dict)

    def answer(self, default: str = "") -> str:
        """取回答文本，拿不到就给 default（方便 `print(r.answer('(空)'))`）"""
        return self.text or default

    def to_dict(self) -> dict:
        """转成普通 dict（写日志 / JSON 序列化用）"""
        return dataclasses.asdict(self)


# kind 取值（稳定，可被调用方按字符串分支）
KIND_OK = "ok"                  # 正常
KIND_FREE_LIMIT = "free-limit"  # 429：地区不在放行名单，或额度真用尽
KIND_REGION = "region"          # 403：地区限制（如 beam-free）
KIND_NO_ROUTE = "no-route"      # 模型不存在 / 无路由
KIND_AUTH = "auth"              # 401 / 密码不对
KIND_TRUNCATED = "truncated"    # finish=length，被截断
KIND_EMPTY = "empty"            # 没文本也没错误
KIND_TIMEOUT = "timeout"        # 读超时（断网 / 断 VPN 常见）
KIND_NETWORK = "network"        # 连不上本地服务
KIND_SERVER = "server"          # 本地服务返回 5xx / 4xx
KIND_UNKNOWN = "unknown"

# 各 kind 对应的处置建议（中文，直接可读）
_ADVICE = {
    KIND_OK: "",
    KIND_FREE_LIMIT: "出口地区不在免费层放行名单，或额度真用尽；先 --cf-trace 看 loc，换 SG / JP 节点后重试",
    KIND_REGION: "该模型对当前出口国家不开放（beam-free 白名单更窄）；换 SG / JP 节点",
    KIND_NO_ROUTE: "模型 ID 不在目录里，先 list_models() 取准确 ID",
    KIND_AUTH: "本地服务密码不对，检查 password / 是否连错端口",
    KIND_TRUNCATED: "输出被截断（finish=length），调小输入或提高模型输出上限",
    KIND_EMPTY: "模型没返回任何文本，查 raw 里的 assistant / idle",
    KIND_TIMEOUT: "读超时：多半是断网或 VPN 断开；确认出口可用后重试",
    KIND_NETWORK: "连不上本地服务：确认 opencode-cli.exe 已在跑、端口正确",
    KIND_SERVER: "本地服务报错，查 server 日志与 raw",
    KIND_UNKNOWN: "未知失败，看 raw 与提示信息",
}


def classify(finish: str, outcome: str, error: Optional[dict], text: str) -> tuple:
    """把 finish/outcome/error 归一化成 (kind, advice)

    判定顺序（按实测优先级，小欧 2026-11-04）：
      错误对象 > 文本里的 429/403 标记 > finish 截断 > 有无文本
    """
    err_type = (error or {}).get("type") or ""
    err_msg = (error or {}).get("message") or ""
    err_status = int((error or {}).get("status") or 0)

    kind = ""
    if "free-limit" in err_type or "FreeUsageLimitError" in err_msg or "Free usage limit" in (text or ""):
        kind = KIND_FREE_LIMIT
    elif "RegionError" in err_msg or (err_status == 403 and err_type.startswith("provider")):
        kind = KIND_REGION
    elif "no-route" in err_type:
        kind = KIND_NO_ROUTE
    elif err_status in (401, 403) and "auth" in err_type:
        kind = KIND_REGION if err_status == 403 else KIND_AUTH
    elif error or finish in ("error", "failed", "cancelled") or outcome in ("failed", "error"):
        kind = KIND_UNKNOWN
    elif finish == "length":
        kind = KIND_TRUNCATED
    elif text:
        kind = KIND_OK
    else:
        kind = KIND_EMPTY
    return kind, _ADVICE.get(kind, "")


# ---------------------------------------------------------------------------
# 报文解析（同步 / 异步共用）
# ---------------------------------------------------------------------------


def parse_messages(messages: list) -> dict:
    """从 /message 返回的 data[] 里抽出结构化信息

    返回 dict：text / reasoning / finish / error / tokens / outcome / idle / assistant
    错误对象按 assistant → idle 三级回退（assistant 可能为 null）。
    """
    assistant = None
    for item in reversed(messages):
        if item.get("type") == "assistant":
            assistant = item
            break
    idle = {}
    for item in reversed(messages):
        if item.get("type") == "idle":
            idle = item
            break

    text_parts, reasoning_parts = [], []
    for part in ((assistant or {}).get("content") or []):
        if part.get("type") == "text":
            text_parts.append(part.get("text") or "")
        elif part.get("type") == "reasoning":
            reasoning_parts.append(part.get("text") or "")

    error = (assistant or {}).get("error") or idle.get("error")
    return {
        "assistant": assistant,
        "idle": idle,
        "text": "\n".join(p for p in text_parts if p),
        "reasoning": "\n".join(p for p in reasoning_parts if p),
        "finish": (assistant or {}).get("finish") or (assistant or {}).get("rawFinish") or "",
        "error": error,
        "tokens": (assistant or {}).get("tokens") or {},
        "outcome": idle.get("outcome") or "",
    }


def _build_result(model: str, started: str, t0: float, session_id: str,
                  parsed: dict, session_info: dict, raw: dict) -> AskResult:
    """把解析结果装配成 AskResult（含分类与建议）"""
    error = parsed.get("error") or None
    kind, advice = classify(parsed.get("finish") or "", parsed.get("outcome") or "",
                            error, parsed.get("text") or "")
    return AskResult(
        model=model,
        ok=(kind == KIND_OK),
        text=parsed.get("text") or "",
        reasoning=parsed.get("reasoning") or "",
        finish=parsed.get("finish") or "",
        outcome=parsed.get("outcome") or (session_info.get("outcome") or ""),
        kind=kind,
        advice=advice,
        error_type=(error or {}).get("type") or "",
        error_message=(error or {}).get("message") or "",
        error_status=int((error or {}).get("status") or 0),
        retry_after_ms=int((error or {}).get("retryAfterMs") or 0),
        tokens=parsed.get("tokens") or (session_info.get("tokens") or {}),
        session_id=session_id,
        elapsed=time.time() - t0,
        started=started,
        finished=now_str(),
        raw=raw,
    )


def _fail_result(model: str, started: str, t0: float, kind: str, detail: Any,
                 session_id: str = "") -> AskResult:
    """传输层失败（超时 / 连不上 / 服务端 4xx-5xx）的统一结果"""
    return AskResult(
        model=model, ok=False, kind=kind, advice=_ADVICE.get(kind, ""),
        error_message=str(detail)[:800], session_id=session_id,
        elapsed=time.time() - t0, started=started, finished=now_str(),
        raw={"transport_error": str(detail)[:2000]},
    )


# ---------------------------------------------------------------------------
# 本地服务（起停 CLI）
# ---------------------------------------------------------------------------


class LocalServer:
    """本地 opencode-cli.exe serve 的生命周期管理（小欧 2026-11-04）

    - 只监听 127.0.0.1；密码走环境变量 OPENCODE_PASSWORD；
    - stdout/stderr 落 log_path，失败时好查真实原因；
    - 可重复 close()。
    """

    def __init__(self, cli: Optional[str] = None, password: str = DEFAULT_PASSWORD,
                 log_dir: Optional[str] = None, start_timeout: float = DEFAULT_START_TIMEOUT):
        self.cli = cli or find_cli()
        self.password = password
        self.log_dir = log_dir or os.path.normpath(os.path.join(_MODULE_DIR, "..", "reports", "server-logs"))
        self.start_timeout = start_timeout
        self.proc: Optional[subprocess.Popen] = None
        self.port = 0
        self.log_path = ""
        self.base_url = ""

    def start(self) -> str:
        if self.proc is not None and self.proc.poll() is None:
            return self.base_url
        if not os.path.exists(self.cli):
            raise FileNotFoundError(
                "找不到真客户端: %s（用 cli=... 指定 opencode-cli.exe 完整路径）" % self.cli)
        os.makedirs(self.log_dir, exist_ok=True)

        self.port = free_port()
        self.base_url = "http://127.0.0.1:%d" % self.port
        self.log_path = os.path.join(
            self.log_dir, "serve-%s.log" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))

        env = os.environ.copy()
        env["OPENCODE_PASSWORD"] = self.password
        flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
        with open(self.log_path, "wb") as log_file:
            self.proc = subprocess.Popen(
                [self.cli, "serve", "--port", str(self.port)],
                env=env, stdout=log_file, stderr=log_file, creationflags=flags)

        auth = (DEFAULT_USER, self.password)
        deadline = time.time() + self.start_timeout
        while time.time() < deadline:
            if self.proc.poll() is not None:
                tail = self.log_tail()
                self.close()
                raise RuntimeError("服务进程已退出（退出码 %s）\n日志 %s:\n%s"
                                   % (self.proc.returncode, self.log_path, tail))
            try:
                if httpx.get(self.base_url + "/api/info", auth=auth, timeout=3,
                             trust_env=False).status_code == 200:
                    return self.base_url
            except Exception:
                pass
            time.sleep(0.3)
        self.close()
        raise TimeoutError("服务在 %.0fs 内未就绪，日志: %s" % (self.start_timeout, self.log_path))

    def log_tail(self, lines: int = 40) -> str:
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as handle:
                return "".join(handle.readlines()[-lines:]).strip()
        except Exception:
            return ""

    def close(self):
        proc, self.proc = self.proc, None
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=8)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _timeout(total: float) -> httpx.Timeout:
    """HTTP 超时：连接/写入短，读长（模型可能几分钟）"""
    return httpx.Timeout(connect=10.0, read=total, write=120.0, pool=10.0)


# ---------------------------------------------------------------------------
# 请求体构造（把协议允许的字段都留出来；小欧 2026-11-04）
#
# 依据 packages/schema/src/prompt-input.ts 与 protocol/src/groups/session.ts：
#   POST /api/session          可传 id / parentID / title / agent / model /
#                              location / metadata / permissions
#   POST /api/session/:id/prompt  可传 text / files[] / agents[] / skills[] /
#                              metadata / delivery("steer"|"queue") / resume / id
# 注意：**没有** temperature / max_tokens 之类采样参数（协议里就没有，
#       只能通过 opencode 配置文件里的模型/agent 设定，API 层不暴露）。
# ---------------------------------------------------------------------------


def _session_body(model: str, title: Optional[str] = None, agent: Optional[str] = None,
                  metadata: Optional[dict] = None, permissions: Any = None,
                  parent_id: Optional[str] = None) -> dict:
    """建会话请求体；值为 None 的字段一律不传（避免协议校验失败）"""
    body = {"model": {"providerID": PROVIDER_ID, "id": model}}
    if title is not None:
        body["title"] = title
    if agent is not None:
        body["agent"] = agent
    if metadata is not None:
        body["metadata"] = metadata
    if permissions is not None:
        body["permissions"] = permissions
    if parent_id is not None:
        body["parentID"] = parent_id
    return body


def _prompt_body(text: str, files: Optional[list] = None, agents: Optional[list] = None,
                 skills: Optional[list] = None, metadata: Optional[dict] = None,
                 delivery: Optional[str] = None, resume: Optional[bool] = None,
                 message_id: Optional[str] = None, extra: Optional[dict] = None) -> dict:
    """发消息请求体

    files  : [{"uri": <data: URL 或本地路径>, "name": ..., "description": ...}]
    agents : [{"id"/"name"...}] 由协议 AgentAttachment 决定
    skills : [{"id": "<skill 名>"}]
    delivery: "steer"（默认，立即插入当前轮）或 "queue"（排队到下个空闲）
    resume: False 表示只入队、不触发执行
    extra  : 逃生口，原样合并进 body（协议新增字段时不用改库）
    """
    body = {"text": text}
    if files:
        body["files"] = files
    if agents:
        body["agents"] = agents
    if skills:
        body["skills"] = skills
    if metadata is not None:
        body["metadata"] = metadata
    if delivery is not None:
        body["delivery"] = delivery
    if resume is not None:
        body["resume"] = resume
    if message_id is not None:
        body["id"] = message_id
    if extra:
        body.update(extra)
    return body


def as_attachment(path: str, name: Optional[str] = None,
                  description: Optional[str] = None) -> dict:
    """把本地文件转成 files[] 里的附件项（走 data: URL，跨机器也能用）

    服务端支持三种 uri：data: URL / 本地路径 / media: 引用。
    data: 最稳（不依赖服务进程能否读到那个路径），代价是体积约 +33%。
    """
    import base64
    import mimetypes

    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as handle:
        payload = base64.b64encode(handle.read()).decode("ascii")
    item = {"uri": "data:%s;base64,%s" % (mime, payload)}
    item["name"] = name or os.path.basename(path)
    if description:
        item["description"] = description
    return item


# ---------------------------------------------------------------------------
# 同步客户端
# ---------------------------------------------------------------------------


class OpenCodeClient:
    """同步客户端。用 with 语句最省心：

        with OpenCodeClient() as oc:
            r = oc.ask("big-pickle", "你好")

    起服务是**懒**的：第一次 ask / list_models 才启动；close() 会关掉它起的进程。
    """

    def __init__(self, base_url: Optional[str] = None, password: str = DEFAULT_PASSWORD,
                 user: str = DEFAULT_USER, cli: Optional[str] = None,
                 timeout: float = DEFAULT_TIMEOUT, log_dir: Optional[str] = None):
        self.password = password
        self.user = user
        self.timeout = timeout
        self._server: Optional[LocalServer] = None
        self._client: Optional[httpx.Client] = None
        self.base_url = (base_url or "").rstrip("/")

        if not self.base_url:
            self._server = LocalServer(cli=cli, password=password, log_dir=log_dir)

    # --- 生命周期 ---------------------------------------------------------

    def start(self) -> str:
        """确保服务可用，返回 base_url"""
        if self._client is not None:
            return self.base_url
        if self._server is not None:
            self.base_url = self._server.start()
        self._client = httpx.Client(base_url=self.base_url, auth=(self.user, self.password),
                                    timeout=_timeout(self.timeout), trust_env=False)
        return self.base_url

    def __enter__(self) -> "OpenCodeClient":
        self.start()
        return self

    def __exit__(self, *exc_info):
        self.close()

    def close(self):
        if self._client is not None:
            try:
                self._client.close()
            finally:
                self._client = None
        if self._server is not None:
            self._server.close()

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self.start()
        assert self._client is not None
        return self._client

    @property
    def server_log(self) -> str:
        """本地服务日志路径（只连已有服务时为空）"""
        return self._server.log_path if self._server is not None else ""

    # --- 目录 / 探活 ------------------------------------------------------

    def health(self) -> bool:
        try:
            return self.client.get("/api/info").status_code == 200
        except Exception:
            return False

    def list_models(self, only_free: bool = False, only_chat: bool = True) -> list:
        """拉模型目录；only_free=True 时只留 cost.input==0 的免费模型"""
        resp = self.client.get("/api/model")
        resp.raise_for_status()
        out = []
        for item in resp.json().get("data", []):
            if item.get("enabled") is False:
                continue
            if only_chat and item.get("type") != "chat":
                continue
            if only_free:
                costs = item.get("cost") or []
                if not any((cost or {}).get("input") == 0 for cost in costs):
                    continue
            out.append(item)
        return out

    def free_model_ids(self) -> list:
        """免费模型 ID 列表（方便直接 for 循环）"""
        return [item.get("id") for item in self.list_models(only_free=True)]

    # --- 核心：一次问答 ---------------------------------------------------

    def new_session(self, model: str, title: Optional[str] = None,
                    agent: Optional[str] = None, metadata: Optional[dict] = None,
                    permissions: Any = None, parent_id: Optional[str] = None) -> str:
        """新建会话，返回 session_id（失败抛 RuntimeError）"""
        resp = self.client.post("/api/session",
                                json=_session_body(model, title or "ask-%s" % model,
                                                   agent, metadata, permissions, parent_id))
        if resp.status_code >= 300:
            raise RuntimeError("建会话 HTTP %s: %s" % (resp.status_code, resp.text[:400]))
        return resp.json()["data"]["id"]

    def ask(self, model: str, text: str, timeout: Optional[float] = None,
            title: Optional[str] = None, session_id: Optional[str] = None,
            files: Optional[list] = None, agents: Optional[list] = None,
            skills: Optional[list] = None, metadata: Optional[dict] = None,
            delivery: Optional[str] = None, resume: Optional[bool] = None,
            agent: Optional[str] = None, permissions: Any = None,
            parent_id: Optional[str] = None, extra_body: Optional[dict] = None) -> AskResult:
        """发消息 → 等服务端空闲 → 取消息 → 解析，返回 AskResult

        session_id : 复用已有会话（多轮）；不给则新建
        files      : 附件列表，用 as_attachment("图片.png") 生成（图片/PDF/文本都行）
        agents     : 附带 agent 附件（协议 AgentAttachment）
        skills     : 附带 skill，如 [{"id": "unit-tests"}]
        delivery   : "steer"（默认，立即插入当前轮）| "queue"（排到下个空闲）
        resume     : False 表示只入队不执行
        agent      : 建会话时指定 agent（如 "build" / "plan"）
        permissions: 建会话时的权限规则集（Permission.Ruleset）
        extra_body : 逃生口，原样合并进 prompt 请求体（协议新增字段时用）
        """
        started, t0 = now_str(), time.time()
        client = self.client
        if timeout is not None:
            client.timeout = _timeout(timeout)
        sid = session_id or ""

        try:
            if not sid:
                resp = client.post("/api/session",
                                   json=_session_body(model, title or "ask-%s" % model,
                                                      agent, metadata, permissions, parent_id))
                if resp.status_code >= 300:
                    kind = KIND_AUTH if resp.status_code in (401, 403) else KIND_SERVER
                    return _fail_result(model, started, t0, kind,
                                        "建会话 HTTP %s: %s" % (resp.status_code, resp.text[:400]))
                sid = resp.json()["data"]["id"]

            resp = client.post("/api/session/%s/prompt" % sid,
                               json=_prompt_body(text, files, agents, skills, metadata,
                                                 delivery, resume, extra=extra_body))
            if resp.status_code >= 300:
                return _fail_result(model, started, t0, KIND_SERVER,
                                    "发消息 HTTP %s: %s" % (resp.status_code, resp.text[:400]), sid)

            # 服务端阻塞式等待，直到本会话空闲（成功返回 204）
            resp = client.post("/api/experimental/session/%s/wait" % sid)
            if resp.status_code not in (200, 204):
                return _fail_result(model, started, t0, KIND_SERVER,
                                    "等待 HTTP %s: %s" % (resp.status_code, resp.text[:400]), sid)

            resp = client.get("/api/session/%s/message" % sid,
                              params={"limit": 200, "order": "asc"})
            if resp.status_code >= 300:
                return _fail_result(model, started, t0, KIND_SERVER,
                                    "取消息 HTTP %s: %s" % (resp.status_code, resp.text[:400]), sid)
            messages = resp.json().get("data", [])

            session_info = {}
            try:
                info = client.get("/api/session/%s" % sid)
                if info.status_code == 200:
                    session_info = info.json().get("data") or {}
            except Exception:
                pass

            parsed = parse_messages(messages)
            raw = {
                "assistant": parsed["assistant"],
                "idle": parsed["idle"],
                "session": {key: session_info.get(key) for key in
                            ("id", "outcome", "model", "tokens", "time")},
            }
            return _build_result(model, started, t0, sid, parsed, session_info, raw)

        except httpx.TimeoutException as exc:
            return _fail_result(model, started, t0, KIND_TIMEOUT, exc, sid)
        except httpx.ConnectError as exc:
            return _fail_result(model, started, t0, KIND_NETWORK, exc, sid)
        except Exception as exc:
            return _fail_result(model, started, t0, KIND_UNKNOWN,
                                "%s: %s" % (type(exc).__name__, exc), sid)


# ---------------------------------------------------------------------------
# 异步客户端（API 与同步版一致）
# ---------------------------------------------------------------------------


class AsyncOpenCodeClient:
    """异步客户端：

        async with AsyncOpenCodeClient() as oc:
            r = await oc.ask("deepseek-v4.1-flash-free", "你好")
    """

    def __init__(self, base_url: Optional[str] = None, password: str = DEFAULT_PASSWORD,
                 user: str = DEFAULT_USER, cli: Optional[str] = None,
                 timeout: float = DEFAULT_TIMEOUT, log_dir: Optional[str] = None):
        self.password = password
        self.user = user
        self.timeout = timeout
        self._server: Optional[LocalServer] = None
        self._client: Optional[httpx.AsyncClient] = None
        self.base_url = (base_url or "").rstrip("/")
        if not self.base_url:
            self._server = LocalServer(cli=cli, password=password, log_dir=log_dir)

    async def start(self) -> str:
        if self._client is not None:
            return self.base_url
        if self._server is not None:
            # 起进程是阻塞的，丢到线程里，别卡事件循环
            import asyncio
            loop = asyncio.get_running_loop()
            self.base_url = await loop.run_in_executor(None, self._server.start)
        self._client = httpx.AsyncClient(base_url=self.base_url,
                                         auth=(self.user, self.password),
                                         timeout=_timeout(self.timeout), trust_env=False)
        return self.base_url

    async def __aenter__(self) -> "AsyncOpenCodeClient":
        await self.start()
        return self

    async def __aexit__(self, *exc_info):
        await self.close()

    async def close(self):
        if self._client is not None:
            try:
                await self._client.aclose()
            finally:
                self._client = None
        if self._server is not None:
            self._server.close()

    async def _ensure(self) -> httpx.AsyncClient:
        if self._client is None:
            await self.start()
        assert self._client is not None
        return self._client

    @property
    def server_log(self) -> str:
        return self._server.log_path if self._server is not None else ""

    async def health(self) -> bool:
        try:
            client = await self._ensure()
            return (await client.get("/api/info")).status_code == 200
        except Exception:
            return False

    async def list_models(self, only_free: bool = False, only_chat: bool = True) -> list:
        client = await self._ensure()
        resp = await client.get("/api/model")
        resp.raise_for_status()
        out = []
        for item in resp.json().get("data", []):
            if item.get("enabled") is False:
                continue
            if only_chat and item.get("type") != "chat":
                continue
            if only_free:
                costs = item.get("cost") or []
                if not any((cost or {}).get("input") == 0 for cost in costs):
                    continue
            out.append(item)
        return out

    async def free_model_ids(self) -> list:
        return [item.get("id") for item in await self.list_models(only_free=True)]

    async def new_session(self, model: str, title: Optional[str] = None,
                          agent: Optional[str] = None, metadata: Optional[dict] = None,
                          permissions: Any = None, parent_id: Optional[str] = None) -> str:
        """新建会话，返回 session_id（失败抛 RuntimeError）"""
        client = await self._ensure()
        resp = await client.post("/api/session",
                                 json=_session_body(model, title or "ask-%s" % model,
                                                    agent, metadata, permissions, parent_id))
        if resp.status_code >= 300:
            raise RuntimeError("建会话 HTTP %s: %s" % (resp.status_code, resp.text[:400]))
        return resp.json()["data"]["id"]

    async def ask(self, model: str, text: str, timeout: Optional[float] = None,
                  title: Optional[str] = None, session_id: Optional[str] = None,
                  files: Optional[list] = None, agents: Optional[list] = None,
                  skills: Optional[list] = None, metadata: Optional[dict] = None,
                  delivery: Optional[str] = None, resume: Optional[bool] = None,
                  agent: Optional[str] = None, permissions: Any = None,
                  parent_id: Optional[str] = None,
                  extra_body: Optional[dict] = None) -> AskResult:
        """参数同同步版 ``ask``（files / delivery / agent / extra_body ...）"""
        started, t0 = now_str(), time.time()
        client = await self._ensure()
        if timeout is not None:
            client.timeout = _timeout(timeout)
        sid = session_id or ""

        try:
            if not sid:
                resp = await client.post("/api/session",
                                         json=_session_body(model, title or "ask-%s" % model,
                                                            agent, metadata, permissions, parent_id))
                if resp.status_code >= 300:
                    kind = KIND_AUTH if resp.status_code in (401, 403) else KIND_SERVER
                    return _fail_result(model, started, t0, kind,
                                        "建会话 HTTP %s: %s" % (resp.status_code, resp.text[:400]))
                sid = resp.json()["data"]["id"]

            resp = await client.post("/api/session/%s/prompt" % sid,
                                     json=_prompt_body(text, files, agents, skills, metadata,
                                                       delivery, resume, extra=extra_body))
            if resp.status_code >= 300:
                return _fail_result(model, started, t0, KIND_SERVER,
                                    "发消息 HTTP %s: %s" % (resp.status_code, resp.text[:400]), sid)

            resp = await client.post("/api/experimental/session/%s/wait" % sid)
            if resp.status_code not in (200, 204):
                return _fail_result(model, started, t0, KIND_SERVER,
                                    "等待 HTTP %s: %s" % (resp.status_code, resp.text[:400]), sid)

            resp = await client.get("/api/session/%s/message" % sid,
                                    params={"limit": 200, "order": "asc"})
            if resp.status_code >= 300:
                return _fail_result(model, started, t0, KIND_SERVER,
                                    "取消息 HTTP %s: %s" % (resp.status_code, resp.text[:400]), sid)
            messages = resp.json().get("data", [])

            session_info = {}
            try:
                info = await client.get("/api/session/%s" % sid)
                if info.status_code == 200:
                    session_info = info.json().get("data") or {}
            except Exception:
                pass

            parsed = parse_messages(messages)
            raw = {
                "assistant": parsed["assistant"],
                "idle": parsed["idle"],
                "session": {key: session_info.get(key) for key in
                            ("id", "outcome", "model", "tokens", "time")},
            }
            return _build_result(model, started, t0, sid, parsed, session_info, raw)

        except httpx.TimeoutException as exc:
            return _fail_result(model, started, t0, KIND_TIMEOUT, exc, sid)
        except httpx.ConnectError as exc:
            return _fail_result(model, started, t0, KIND_NETWORK, exc, sid)
        except Exception as exc:
            return _fail_result(model, started, t0, KIND_UNKNOWN,
                                "%s: %s" % (type(exc).__name__, exc), sid)


# ---------------------------------------------------------------------------
# 命令行自检
# ---------------------------------------------------------------------------


def _print_result(result: AskResult, show_raw: bool = False):
    print("模型    : %s" % result.model)
    print("状态    : %s（kind=%s）" % ("OK" if result.ok else "失败", result.kind))
    print("耗时    : %.1f 秒" % result.elapsed)
    print("finish  : %s   outcome: %s" % (result.finish or "-", result.outcome or "-"))
    print("tokens  : %s" % json.dumps(result.tokens, ensure_ascii=False))
    if result.session_id:
        print("会话ID  : %s" % result.session_id)
    if result.ok:
        print("回答    :")
        for line in result.text.splitlines():
            print("    " + line)
    else:
        if result.advice:
            print("建议    : %s" % result.advice)
        if result.error_type:
            print("错误    : type=%s status=%s retry_after_ms=%s"
                  % (result.error_type, result.error_status, result.retry_after_ms))
        if result.error_message:
            print("详情    : %s" % result.error_message)
    if show_raw and result.raw:
        print("原始    :")
        print(json.dumps(result.raw, ensure_ascii=False, indent=2)[:3000])


def _selftest_sync(args) -> int:
    models = [m.strip() for m in args.model.split(",") if m.strip()]
    with OpenCodeClient(base_url=args.base_url, password=args.password, cli=args.cli) as oc:
        print("服务    : %s" % oc.base_url)
        if args.list:
            for item in oc.list_models(only_free=True):
                caps = item.get("capabilities") or {}
                print("  %-32s 工具=%-5s 输入=%s"
                      % (item.get("id"), caps.get("tools", "-"),
                         ",".join(caps.get("input", [])) or "-"))
            return 0
        if not args.no_trace:
            print("出口    : %s" % egress_trace())
        files = [as_attachment(path) for path in (args.file or [])] or None
        failures = 0
        for model in models:
            print("-" * 72)
            result = oc.ask(model, args.prompt, files=files,
                            agent=args.agent or None, delivery=args.delivery or None)
            _print_result(result, args.raw)
            failures += 0 if result.ok else 1
        print("-" * 72)
        print("成功 %d/%d" % (len(models) - failures, len(models)))
        if oc.server_log:
            print("服务日志: %s" % oc.server_log)
    return 0 if failures == 0 else 1


def _selftest_async(args) -> int:
    import asyncio

    async def run() -> int:
        models = [m.strip() for m in args.model.split(",") if m.strip()]
        async with AsyncOpenCodeClient(base_url=args.base_url, password=args.password,
                                       cli=args.cli) as oc:
            print("服务    : %s（异步实现）" % oc.base_url)
            if args.list:
                for model_id in await oc.free_model_ids():
                    print("  " + model_id)
                return 0
            failures = 0
            files = [as_attachment(path) for path in (args.file or [])] or None
            for model in models:
                print("-" * 72)
                result = await oc.ask(model, args.prompt, files=files,
                                      agent=args.agent or None, delivery=args.delivery or None)
                _print_result(result, args.raw)
                failures += 0 if result.ok else 1
            print("-" * 72)
            print("成功 %d/%d" % (len(models) - failures, len(models)))
        return 0 if failures == 0 else 1

    return asyncio.run(run())


def main(argv: Optional[list] = None) -> int:
    try:
        os.system("chcp 65001 > nul")
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="opencode_client.py 自检（库用法见文件头注释）")
    parser.add_argument("--model", default="big-pickle", help="模型 ID，逗号分隔可多个")
    parser.add_argument("--prompt", default="只回答两个字：可用", help="提问内容")
    parser.add_argument("--base-url", default="", help="连已有服务，如 http://127.0.0.1:4096")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="本地服务密码")
    parser.add_argument("--cli", default="", help="opencode-cli.exe 路径（默认自动查找）")
    parser.add_argument("--list", action="store_true", help="只列免费模型")
    parser.add_argument("--raw", action="store_true", help="打印 assistant/idle/session 原始 JSON")
    parser.add_argument("--no-trace", action="store_true", help="不打印出口")
    parser.add_argument("--file", action="append", default=[],
                        help="附件（图片/PDF/文本），可重复；走 data: URL")
    parser.add_argument("--agent", default="", help="建会话时指定 agent，如 build / plan")
    parser.add_argument("--delivery", default="", choices=["", "steer", "queue"],
                        help="消息投递方式：steer（默认立即）或 queue（排队）")
    parser.add_argument("--async", dest="use_async", action="store_true", help="走异步实现自检")
    args = parser.parse_args(argv)
    return _selftest_async(args) if args.use_async else _selftest_sync(args)


if __name__ == "__main__":
    sys.exit(main())
