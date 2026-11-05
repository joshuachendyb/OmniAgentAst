# -*- coding: utf-8 -*-
r"""vendor\opencode\driver.py — opencode CLI 驱动（方言唯一集中点, 1.8 D25）。

编写人: 小欧    创建时间: 2026-11-05 09:10:00
对齐: 6.3.3–6.3.7（定位/准入/RPC）; 7.1/7.3/7.4（时序/定向查询/事件流）;
     4.2/4.6/4.8.2（模型/计量/finish）; 4.7（错误映射）; 8.4/8.6（隔离/脱敏）
换第二案 = 新增 vendor\<案>\driver.py 实现 gateways\driver.py 的同名接口。
"""
from __future__ import annotations

import os
import re

import httpx

try:                                  # vendor\opencode\ 为 namespace package;
    from . import opencode_client as oc          # 兼容器: 同目录直跑时回退顶层导入
except ImportError:
    import opencode_client as oc      # （打包为插件目录 copy 时两者皆可, 9.5）

NAME = "opencode"
PROVIDER_ID = "opencode"
VERSION_RE = re.compile(r"^opencode v?(\d+\.\d+\.\d+)")          # 实测: opencode v2.2.0
PASSWORD_RE = re.compile(r"server password (\S+)")               # D17: 密码出自 stdout
PASSWORD_MASK = "server password ***"                            # 8.6 脱敏替身


class Driver:
    name = NAME
    provider_id = PROVIDER_ID
    version_re = VERSION_RE

    # --- 定位与环境（6.3.3 5 级解析; 8.4 XDG） -----------------------------

    def cli_candidates(self, config):
        """候选从 config 通用注记里取路径基点（runtime_dir/frozen 由 cli_manager 注入）。"""
        cli = config.get("cli") or {}
        frozen = bool(config.get("frozen"))
        allow_system = bool(cli.get("allow_system", True))
        if frozen and allow_system:
            config["system_probe_note"] = "disabled(packaged)"       # 6.3.6 硬约束
            allow_system = False
        out = []
        if str(cli.get("executable") or "").strip():                # 1 级: 显式钉死
            out.append({"path": cli["executable"].strip(), "level": 1})
        out.append({"path": os.path.join(str(config.get("runtime_dir")), "runtime",
                                         "opencode-cli.exe"), "level": 2})   # 2 级: 自带优先
        shared = os.path.join(str(config.get("machine_root")), "bin", "opencode-cli.exe")
        out.append({"path": shared, "level": 3})                    # 3 级: 用户级共享
        if allow_system:                                            # 4 级: 仅开发版
            out.append({"path": "opencode-cli", "level": 4, "probe": False})
        return out

    def env_overrides(self, tag):
        """8.4 出生前隔离: XDG 四目录按 tag（i0/i1/probe）分目录, 不读用户全局配置。"""
        root = os.path.join(str(config_root()), "xdg")
        paths = {}
        for var, sub in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
                         ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "state")):
            path = os.path.join(root, sub, tag)
            os.makedirs(path, exist_ok=True)
            paths[var] = path
        return paths

    # --- 进程（7.1.2 spawn; D17 密码; 7.1.3 就绪） -------------------------

    def spawn_args(self, exe, port):
        """只允许 serve 子命令——裸 opencode 会挂用户后台服务（8.4）。"""
        return ["serve", "--hostname", "127.0.0.1", "--port", str(port)]

    def credential(self, line):
        """stdout 行 → (脱敏行, 密码)。任何含密码的行都脱敏后再落盘（8.6）。"""
        match = PASSWORD_RE.search(line)
        if not match:
            return line, ""
        return PASSWORD_MASK, match.group(1)

    def auth(self, password):
        return ("opencode", password)               # 用户名固定（6.3.4 实测）

    def ready(self, port, auth):
        """7.1.3 就绪硬判定: /api/model 200 且 data 为 list。"""
        try:
            resp = httpx.get("http://127.0.0.1:%d/api/model" % port, auth=auth,
                             timeout=3, trust_env=False)        # 8.5: 不走系统代理
            return resp.status_code == 200 and isinstance(resp.json().get("data"), list)
        except Exception:
            return False

    # --- 会话与报文（7.3; 报文构造委托 vendor 纯函数, 使用纪律 1） ---------

    def session_body(self, model, permissions):
        return oc._session_body(model, title="ask-%s" % model,
                                permissions=permissions)

    def prompt_body(self, text, files):
        return oc._prompt_body(text, files=files or None)

    def path_create(self):
        return "/api/session"

    def path_prompt(self, sid):
        return "/api/session/%s/prompt" % sid

    def path_wait(self, sid):
        # 易错点（vendor 摘录点 2）: 阻塞式等待, 200/204 即执行结束, 无需轮询
        return "/api/experimental/session/%s/wait" % sid, {200, 204}

    def path_messages(self, sid):
        # 7.3 定向查询: type=assistant + desc + limit=1, 报文省 19%
        return "/api/session/%s/message" % sid, \
               {"type": "assistant", "order": "desc", "limit": 1}

    def path_interrupt(self, sid):
        return "/api/session/%s/interrupt" % sid

    def path_delete(self, sid):
        return "/api/session/%s" % sid

    def path_models(self):
        return "/api/model"

    def path_events(self):
        return "/api/event"

    # --- 事件与取数（7.4 / 4.6 / 4.8.2） -----------------------------------

    def event_session(self, payload):
        data = payload.get("data") or {}
        return data.get("sessionID") or None        # 并发过滤键（7.4 过滤行）

    def event_class(self, payload):
        """判别按内容形状; 事件类型名以实测 opencode v2.2.0 为准。

        FIX H 偏差记录（2026-11-05 小欧）: 实测(diag_events.py)本 CLI 事件为
        session.* 族——内容 delta 在 session.text.delta 的 data["delta"],
        收尾文本在 session.text.ended 的 data["text"], 终止判定为
        session.execution.succeeded（无 "idle" 事件名）。
        原 6.3.7 草案判据（'text' in kind / kind=='idle'）与实测不合:
        增量文本漏接 + idle 永不触发（read=60 s 超时 → 流破裂, 实测复现）。
        保留对旧版事件名("idle"/message.text.* 等)的宽松兼容。
        """
        data = payload.get("data") or {}
        kind = str(payload.get("type") or "")
        if data.get("error"):
            return {"kind": "error", "text": "", "error": data["error"]}
        if kind == "session.execution.failed":
            return {"kind": "error", "text": "",
                    "error": data or {"message": "下游执行失败"}}
        if kind in ("session.execution.succeeded", "session.idle", "idle"):
            return {"kind": "idle", "text": "", "error": None}
        if kind == "session.text.delta":
            return {"kind": "content", "text": data.get("delta") or "",
                    "ordinal": data.get("ordinal"), "error": None}
        if kind == "session.text.ended":
            # FIX I 偏差记录（2026-11-05 小欧）: 收尾事件携带全文, 与 delta 流重复——
            # 归一为 "final" 由通用层按 ordinal 记账去重; 消息无 delta 时仍可收字。
            return {"kind": "final", "text": data.get("text") or "",
                    "ordinal": data.get("ordinal"), "error": None}
        if kind == "session.text.started":
            return {"kind": "ignore", "text": "", "error": None}
        if data.get("reasoning") is not None or kind.startswith("session.reasoning"):
            return {"kind": "reasoning",
                    "text": data.get("reasoning") or data.get("delta") or data.get("text") or "",
                    "error": None}
        if data.get("text"):
            return {"kind": "content", "text": data.get("text") or "", "error": None}
        return {"kind": "ignore", "text": "", "error": None}

    def assistant_content(self, message):
        return "\n".join((part.get("text") or "") for part in
                         (message.get("content") or []) if part.get("type") == "text")

    def token_counts(self, message):
        tokens = message.get("tokens")
        if not isinstance(tokens, dict) \
                or (tokens.get("input") is None and tokens.get("output") is None):
            return None                              # 缺计量 → None, 绝不填 0（4.6）
        cache = tokens.get("cache") or {}
        return {"input": int(tokens.get("input") or 0),
                "written": int(cache.get("write") or 0),
                "cached": int(cache.get("read") or 0),
                "output": int(tokens.get("output") or 0),
                "reasoning": int(tokens.get("reasoning") or 0)}

    def finish_reason(self, message):
        finish = str(message.get("finish") or message.get("rawFinish") or "").strip()
        return "length" if finish == "length" else "stop"       # 4.8.2 兜底

    # --- 发现与错误（4.2 / 4.7 判读规则） -----------------------------------

    def models_from(self, resp_json):
        items, skipped = [], 0
        for item in (resp_json or {}).get("data") or []:
            mid = item.get("id") or item.get("modelID")          # id 回退 modelID（4.2）
            if not mid:
                skipped += 1                                     # 4.8.1: 必须自己数出来
                continue
            limit = item.get("limit") or {}
            caps = item.get("capabilities") or {}
            released = (item.get("time") or {}).get("released") or 0
            items.append({
                "id": mid,
                "object": "model",
                "created": int(released // 1000) if released else 0,
                "owned_by": self.provider_id,
                "name": item.get("name") or mid,
                "context_length": limit.get("context"),
                "max_output_length": limit.get("output"),
                "input_modalities": caps.get("input") or [],
                "output_modalities": caps.get("output") or [],
                "pricing": {"prompt": "0", "completion": "0"},
                "free": True,                       # 本网关只暴露免费层（4.2）
            })
        return items, skipped

    def map_error(self, error):
        """从下游错误对象到 4.7 统一分派 dict（v6.6 的 errors.from_downstream 原样下沉至此）。

        映射纪律（逐条来自 4.7 表 + 四条判读规则）: 通用层只认返回 dict;
        头值冷却只进 internal_cooldown_ms（R5 用, 不写响应头）。
        """
        error = error or {}
        etype = str(error.get("type") or "")
        msg = str(error.get("message") or "")
        status = int(error.get("status") or 0)
        cooldown = int(error.get("retryAfterMs") or 0)
        base = {"detail": (msg or "下游无错误详情")[:500],
                "internal_cooldown_ms": cooldown}

        if "free-limit" in etype or "FreeUsageLimit" in msg or "Free usage limit" in msg:
            return dict(base, status=429, type="free-limit",
                        message="免费额度受限（可能地区或频率），请稍后再试或更换出口")
        if status == 403 or "RegionError" in msg:
            return dict(base, status=403, type="region",
                        message="该地区不可用，请更换出口")
        if "no-route" in etype or status == 404:
            return dict(base, status=404, type="model-not-found",
                        message="模型不存在或未开放")
        if "context" in etype or status == 400:
            return dict(base, status=400, type="context-too-long",
                        message="上下文过长")
        if status == 401 or "auth" in etype:
            # 判读规则 1: 下游 Basic 鉴权失败是网关内部问题, 包 502 而非透传 401
            return dict(base, status=502, type="server",
                        message="网关内部错误（下游鉴权失败），请查看 logs\\cli-out.log")
        if "timeout" in etype or status == 504:
            return dict(base, status=504, type="timeout", message="模型响应超时")
        if "network" in etype or status in (502, 503):
            return dict(base, status=502, type="network", message="下游连接中断")
        return dict(base, status=502, type="server",
                    message="下游异常（debug 见 detail）")


def config_root():
    """机器级根目录（与_generic machine_root 同值; 驱动不吃通用层 import, 故就地实现）。"""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    return os.path.join(base, "opencli-gateway")
